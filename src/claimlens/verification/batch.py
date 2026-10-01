from __future__ import annotations

import argparse
import json
from pathlib import Path

from .aggregator import summary
from .checkpoint import atomic_json, complete, partial, read_json
from .metrics import Metrics
from .models import fingerprint, now, validate_candidate
from .providers.http import Client
from .router import Router


def discover(input_dir):
    input_dir = Path(input_dir).resolve()
    if input_dir.name != '01_CODEX_READY':
        raise ValueError('Input must be the prepared 01_CODEX_READY directory')
    files = sorted(input_dir.glob('C-*.claims.json'))
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError('Symlinks are not allowed as claim inputs')
    return files


def check_input(d, path):
    if not isinstance(d, dict) or d.get('candidate_id') != path.name.removesuffix('.claims.json'):
        raise ValueError('Invalid candidate ID')
    if not isinstance(d.get('application_id'), str) or not isinstance(d.get('claims'), list):
        raise ValueError('Invalid prepared package')
    ids = []
    for c in d['claims']:
        if not isinstance(c, dict) or not isinstance(c.get('claim_id'), str) or not isinstance(c.get('claim_type'), str):
            raise ValueError('Malformed claim')
        ids.append(c['claim_id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate claims')
    return d


def run(input_dir, output_dir, router=None, limit=None):
    files = discover(input_dir)
    output = Path(output_dir).resolve()
    if output == Path(input_dir).resolve() or output.name != '02_VERIFICATION_RESULTS':
        raise ValueError('Output must be separate 02_VERIFICATION_RESULTS directory')
    output.mkdir(parents=True, exist_ok=True)
    (output / '_logs').mkdir(exist_ok=True)
    if router is None:
        client = Client()
        router = Router(client, Metrics(client))
    failures = []
    records = []
    last = None
    processed = 0

    def progress():
        atomic_json(output / 'batch_progress.json', dict(total_candidates=len(files), completed=len(records),
                    failed=len(failures), remaining=len(files) - len(records) - len(failures),
                    last_completed_candidate=last, updated_at=now()))
        atomic_json(output / 'failed_items.json', failures)

    # A previous failure is retried in the current run; complete valid candidates are skipped.
    for path in files:
        cid = path.name.removesuffix('.claims.json')
        try:
            original = check_input(read_json(path), path)
            target = output / (cid + '.verification.json')
            audit_path = output / '_logs' / (cid + '.audit.json')
            if complete(target, original) and audit_path.is_file():
                records.append(read_json(target))
                last = cid
                continue
            if limit is not None and processed >= limit:
                continue
            processed += 1
            checkpoint = output / '_logs' / (cid + '.partial.json')
            results, audits = partial(checkpoint, original)
            for claim in original['claims']:
                if claim['claim_id'] not in results:
                    r, a = router.verify(claim, cid)
                    results[claim['claim_id']], audits[claim['claim_id']] = r, a
                    atomic_json(checkpoint, dict(candidate_id=cid, input_sha256=fingerprint(original),
                                                results=list(results.values()), audit=list(audits.values()), updated_at=now()))
            document = dict(candidate_id=cid, application_id=original['application_id'], verification_version='1.0',
                            verified_at=now(), claims_total=len(original['claims']), input_sha256=fingerprint(original),
                            results=[results[c['claim_id']] for c in original['claims']])
            validate_candidate(document, original)
            atomic_json(audit_path, dict(candidate_id=cid, input_sha256=fingerprint(original),
                                        verified_at=now(), claims=[audits[c['claim_id']] for c in original['claims']]))
            atomic_json(target, document)
            records.append(document)
            last = cid
            progress()
            print(f'completed {cid}: {len(document["results"])} claims', flush=True)
        except Exception as exc:
            # No exception message, raw claim or application identifier in terminal/log failures.
            failures.append(dict(candidate_id=cid, error_type=type(exc).__name__,
                                 reason='Candidate processing failed; inspect local input/checkpoint.', occurred_at=now()))
            progress()
            print(f'failed {cid}: {type(exc).__name__}', flush=True)
    progress()
    report = summary(records, len(files), failures)
    report['updated_at'] = now()
    report['run_complete'] = len(records) + len(failures) == len(files)
    atomic_json(output / 'batch_summary.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description='Verify only prepared pseudonymous claims, with per-claim checkpoints')
    p.add_argument('input', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--pilot', action='store_true', help='Complete first two candidates for local QC')
    args = p.parse_args()
    report = run(args.input, args.out, limit=2 if args.pilot else None)
    print(json.dumps({k: report[k] for k in ('completed_candidates', 'total_claims', 'verification_status_counts', 'processing_failures')}, ensure_ascii=False), flush=True)
    return 1 if report['processing_failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
