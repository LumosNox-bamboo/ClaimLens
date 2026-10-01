from collections import Counter

from .models import Status


def summary(records, total_candidates, failures):
    results = [r for d in records for r in d['results']]
    statuses = Counter(r['verification_status'] for r in results)
    types = Counter(r['claim_type'] for r in results)
    publications = [r for r in results if r['claim_type'] == 'publication']
    jif = sum(r['journal_metrics']['latest_jif'] is not None for r in publications)
    return dict(total_candidates=total_candidates, completed_candidates=len(records),
                total_claims=len(results), verification_status_counts={s.value: statuses[s.value] for s in Status},
                CV_UPDATE_AVAILABLE=sum(r['freshness_status'] == 'CV_UPDATE_AVAILABLE' for r in results),
                claim_type_counts=dict(types), publication_count=types['publication'],
                conference_count=types['conference_presentation'], award_count=types['award'],
                competition_count=types['competition'], education_count=types['education'],
                qualification_count=types['professional_qualification'], certification_count=types['certification'],
                patent_count=types['patent'], JIF_found=jif, JIF_unavailable=len(publications) - jif,
                processing_failures=len(failures),
                manual_review_anomaly_types=['prepared-input headings or non-factual statements',
                                           'truncated or incomplete citations',
                                           'missing recipient/presenter/inventor linkage',
                                           'inaccessible or ambiguous public sources',
                                           'substantive field conflicts, if any'],
                interpretation='NOT_FOUND is not FALSE. Public visibility is not candidate credibility. No candidate scores or ranking.')
