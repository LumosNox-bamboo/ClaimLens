"""Apply reviewed journal-level metadata locally, without rerunning candidate searches."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .aggregator import summary
from .checkpoint import atomic_json, read_json
from .evidence import norm
from .models import empty_metrics, now, validate_candidate
from .providers.web import official_publisher


def enrich_metrics(output_dir, sources):
    output = Path(output_dir)
    index = {}
    for s in sources:
        m = s['journal_metrics']
        if (m['metric_name'] != 'Journal Impact Factor'
                or m['metric_source_quality'] != 'official_publisher'
                or not official_publisher(m['metric_source_url'])
                or m['jif_year'] != datetime.now(timezone.utc).year - 1
                or not isinstance(m['latest_jif'], (int, float))
                or not s.get('accessed_at') or not s.get('notes')):
            raise ValueError('Invalid or outdated journal-level source')
        index[norm(s['journal'])] = s
    atomic_json(output / '_logs' / 'journal_metrics_sources.json', sources)
    changed = 0
    records = []
    for path in sorted(output.glob('C-*.verification.json')):
        d = read_json(path)
        audit_path = output / '_logs' / (d['candidate_id'] + '.audit.json')
        a = read_json(audit_path)
        audits = {x['claim_id']: x for x in a['claims']}
        modified = False
        for r in d['results']:
            if r['claim_type'] != 'publication':
                continue
            journals = {norm(e.get('verified_metadata', {}).get('journal', '')) for e in r['evidence']}
            matches = [index[j] for j in journals if j in index]
            if len(matches) != 1:
                continue
            s = matches[0]
            if r['journal_metrics'] == s['journal_metrics']:
                continue
            r['journal_metrics'] = dict(s['journal_metrics'])
            audits[r['claim_id']]['metric_enrichment'] = s
            changed += 1
            modified = True
        if modified:
            validate_candidate(d)
            atomic_json(audit_path, a)
            partial_path = output / '_logs' / (d['candidate_id'] + '.partial.json')
            if partial_path.exists():
                partial = read_json(partial_path)
                partial['results'] = d['results']
                partial['audit'] = a['claims']
                partial['updated_at'] = now()
                atomic_json(partial_path, partial)
            atomic_json(path, d)
        records.append(d)
    old = read_json(output / 'batch_summary.json')
    report = summary(records, old['total_candidates'], read_json(output / 'failed_items.json'))
    report.update(updated_at=now(), run_complete=old['run_complete'])
    atomic_json(output / 'batch_summary.json', report)
    return changed


def metrics_record(journal, value, year, source_name, url, notes, query):
    m = empty_metrics()
    m.update(latest_jif=value, jif_year=year, metric_source=source_name,
             metric_source_url=url, metric_source_quality='official_publisher')
    return dict(journal=journal, journal_metrics=m, accessed_at=now(), notes=notes,
                search_query=query, retrieval_method='public web source inspection; no candidate information sent')
