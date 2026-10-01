import json

import pytest

from claimlens.verification.aggregator import summary
from claimlens.verification.batch import run
from claimlens.verification.checkpoint import atomic_json, complete
from claimlens.verification.evidence import apply, evidence
from claimlens.verification.freshness import update
from claimlens.verification.models import Status, fingerprint, result, validate_result
from claimlens.verification.providers.crossref import metadata
from claimlens.verification.providers.http import FetchError
from claimlens.verification.router import Router


def claim(kind='publication'):
    return dict(claim_id='C-AAAAAA-001', claim_type=kind, title='A fictional experiment on synthetic samples', year='2020')


def test_status_enum_and_absence_is_not_conflict():
    assert {s.value for s in Status} == {'VERIFIED', 'PARTIALLY_VERIFIED', 'CONFLICT', 'NOT_FOUND', 'DOCUMENT_REQUIRED', 'NEEDS_REVIEW'}
    assert Status.NOT_FOUND != Status.CONFLICT
    with pytest.raises(ValueError):
        validate_result({**result(claim()), 'verification_status': 'CONFLICT'})


@pytest.mark.parametrize('kind', ['education', 'professional_qualification', 'certification'])
def test_document_required_without_network(kind):
    r, a = Router(None, None).verify(claim(kind), 'C-AAAAAA')
    assert r['verification_status'] == 'DOCUMENT_REQUIRED'
    assert not a['search_queries']
    assert r['journal_metrics'] is None


def test_freshness_independent_and_jif_missing():
    c = {**claim(), 'claim_text': 'Accepted 2020'}
    r = result(c, Status.PARTIALLY_VERIFIED)
    update(r, c, dict(publication_status='published', title=c['title'], year='2021', doi='10.0000/fictional'))
    assert r['verification_status'] == 'PARTIALLY_VERIFIED'
    assert r['freshness_status'] == 'CV_UPDATE_AVAILABLE'
    assert r['journal_metrics']['latest_jif'] is None
    assert r['journal_metrics']['jif_year'] is None


def test_evidence_aggregation_and_weak_source():
    r = result(claim())
    apply(r, evidence('Fictional publisher', 'official', 'https://example.org/work', 'A', ['title']))
    apply(r, evidence('Fictional index', 'index', 'https://example.org/index', 'C', ['year']))
    assert r['matched_fields'] == ['title', 'year']
    assert r['evidence_strength'] == 'A'
    r['verification_status'] = 'VERIFIED'
    validate_result(r)
    r['evidence'] = [evidence('Self report', 'personal', 'https://example.org/self', 'D', ['title'])]
    with pytest.raises(ValueError):
        validate_result(r)


def test_malformed_provider_result():
    with pytest.raises(FetchError):
        metadata({'DOI': '10.0000/synthetic', 'title': 'not a list'})


class Stub:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def verify(self, c, cid):
        self.calls += 1
        if self.fail and cid == 'C-AAAAAA':
            raise RuntimeError('synthetic failure')
        return result(c, Status.DOCUMENT_REQUIRED), {'claim_id': c['claim_id'], 'search_queries': []}


def packages(tmp_path):
    source = tmp_path / '01_CODEX_READY'
    out = tmp_path / '02_VERIFICATION_RESULTS'
    source.mkdir()
    for cid in ['C-AAAAAA', 'C-BBBBBB']:
        atomic_json(source / (cid + '.claims.json'), dict(candidate_id=cid, application_id='synthetic-application', claims=[{**claim('education'), 'claim_id': cid + '-001'}]))
    return source, out


def test_checkpoint_resume_and_corruption(tmp_path):
    source, out = packages(tmp_path)
    stub = Stub()
    run(source, out, stub)
    assert stub.calls == 2
    run(source, out, stub)
    assert stub.calls == 2
    (out / 'C-AAAAAA.verification.json').write_text('{}')
    run(source, out, stub)
    # Partial checkpoint reuses the completed claim while repairing candidate output.
    assert stub.calls == 2
    d = json.loads((source / 'C-AAAAAA.claims.json').read_text())
    assert complete(out / 'C-AAAAAA.verification.json', d)
    d['claims'][0]['year'] = '2022'
    atomic_json(source / 'C-AAAAAA.claims.json', d)
    run(source, out, stub)
    assert stub.calls == 3


def test_one_failure_does_not_stop_batch(tmp_path):
    source, out = packages(tmp_path)
    report = run(source, out, Stub(fail=True))
    assert report['processing_failures'] == 1
    assert report['completed_candidates'] == 1
    assert (out / 'C-BBBBBB.verification.json').exists()
    assert json.loads((out / 'batch_progress.json').read_text())['failed'] == 1


def test_claim_checkpoint_resume_after_interruption(tmp_path):
    source, out = packages(tmp_path)
    d = json.loads((source / 'C-AAAAAA.claims.json').read_text())
    d['claims'].append({**claim('education'), 'claim_id': 'C-AAAAAA-002'})
    atomic_json(source / 'C-AAAAAA.claims.json', d)

    class Interrupt(Stub):
        def verify(self, c, cid):
            if c['claim_id'].endswith('002'):
                raise KeyboardInterrupt()
            return super().verify(c, cid)

    first = Interrupt()
    with pytest.raises(KeyboardInterrupt):
        run(source, out, first)
    assert first.calls == 1
    resumed = Stub()
    run(source, out, resumed)
    assert resumed.calls == 2


def test_summary_has_no_candidate_scoring():
    report = summary([{'results': [result(claim(), Status.NOT_FOUND)]}], 1, [])
    assert report['verification_status_counts']['NOT_FOUND'] == 1
    assert 'candidate_ranking' not in report


def test_input_changed_invalidates_checkpoint():
    assert fingerprint({'title': 'synthetic one'}) != fingerprint({'title': 'synthetic two'})


def test_citation_author_prefix_is_not_article_title():
    from claimlens.verification.router import public_title
    c = {'title': '3. Fiction A, Invented B, Synthetic C. A fictional experiment on synthetic samples[J]. Fictional Journal, 2020. DOI: 10.0000/synthetic'}
    assert public_title(c) == 'A fictional experiment on synthetic samples'


def test_generic_fragment_does_not_create_year_conflict():
    r = result({**claim(), 'title': 'international population based cohort study', 'year': '2018'})
    a = {'sources_rejected': []}
    m = dict(title='Protocol for a fictional international population based cohort study', year='2025', years=['2025'], doi='10.0000/fictional', metadata_url='https://example.org/work')
    router = Router(None, None)
    assert not router.compare_publication(r['original_claim'], r, a, m, 'Synthetic source')
    assert r['verification_status'] == 'NEEDS_REVIEW'
    assert not r['conflicting_fields']


def test_jif_year_citescore_and_five_year_are_not_substitutes():
    from claimlens.verification.metrics import extract_jif
    assert extract_jif('Journal Impact Factor: 4.4 (2025) 5-year Journal Impact Factor: 4.8 (2025)', 2025) == 4.4
    assert extract_jif('5-year Journal Impact Factor: 4.8 (2025)', 2025) is None
    assert extract_jif('CiteScore 9.8 (2025)', 2025) is None
    assert extract_jif('Impact Factor 4.4 (2024)', 2025) is None
    assert extract_jif('Impact Factor 4.4', 2025) is None
    assert extract_jif('2025 Impact Factor 4.4', 2025) == 4.4


def test_metric_enrichment_rejects_outdated_and_secondary_sources(tmp_path):
    from claimlens.verification.enrichment import enrich_metrics, metrics_record
    record = metrics_record('Fictional journal', 4.4, 1999, 'Fictional publisher', 'https://example.org/journal', 'Synthetic fixture', 'fictional journal')
    with pytest.raises(ValueError):
        enrich_metrics(tmp_path, [record])
