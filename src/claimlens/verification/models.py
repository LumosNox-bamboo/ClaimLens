"""Strict local verification records; no candidate-level scoring."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = json.loads(Path(__file__).with_name("verification.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


class Status(str, Enum):
    VERIFIED = 'VERIFIED'
    PARTIALLY_VERIFIED = 'PARTIALLY_VERIFIED'
    CONFLICT = 'CONFLICT'
    NOT_FOUND = 'NOT_FOUND'
    DOCUMENT_REQUIRED = 'DOCUMENT_REQUIRED'
    NEEDS_REVIEW = 'NEEDS_REVIEW'


FACT_FIELDS = ('title', 'year', 'journal', 'doi', 'authors', 'organization',
               'patent_number', 'award_name', 'claim_text')


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def empty_metrics():
    return dict(latest_jif=None, jif_year=None, metric_name='Journal Impact Factor',
                metric_source=None, metric_source_url=None, metric_source_quality=None)


def result(claim, status=Status.NEEDS_REVIEW, notes=''):
    return dict(claim_id=claim['claim_id'], claim_type=claim['claim_type'],
                original_claim={k: claim[k] for k in FACT_FIELDS if claim.get(k)},
                verification_status=status.value, matched_fields=[], conflicting_fields=[],
                unverified_fields=[k for k in FACT_FIELDS if claim.get(k)],
                evidence_strength=None, evidence=[], freshness_status='UNKNOWN',
                suggested_cv_update=None,
                journal_metrics=empty_metrics() if claim['claim_type'] == 'publication' else None,
                verification_notes=notes)


def validate_result(r):
    required = set(result({'claim_id': 'synthetic', 'claim_type': 'publication'}))
    if not isinstance(r, dict) or not required.issubset(r):
        raise ValueError('missing result fields')
    Status(r['verification_status'])
    if r['freshness_status'] not in {'CURRENT', 'CV_UPDATE_AVAILABLE', 'UNKNOWN'}:
        raise ValueError('invalid freshness')
    if not all(isinstance(r[k], str) for k in ('claim_id', 'claim_type', 'verification_notes')):
        raise ValueError('invalid result identity')
    if not isinstance(r['original_claim'], dict):
        raise ValueError('invalid original claim')
    for k in ('matched_fields', 'conflicting_fields', 'unverified_fields'):
        if not isinstance(r[k], list) or not all(isinstance(v, str) for v in r[k]):
            raise ValueError('invalid field list')
    if r['evidence_strength'] not in (None, 'A', 'B', 'C', 'D'):
        raise ValueError('invalid evidence strength')
    if not isinstance(r['evidence'], list):
        raise ValueError('invalid evidence list')
    for e in r['evidence']:
        for k in ('source_name', 'source_type', 'url', 'accessed_at', 'notes'):
            if not isinstance(e.get(k), str) or not e[k]:
                raise ValueError('invalid evidence provenance')
        if not e['url'].startswith(('https://', 'http://')):
            raise ValueError('invalid evidence URL')
        if e.get('evidence_strength') not in ('A', 'B', 'C', 'D'):
            raise ValueError('invalid evidence level')
        for k in ('matched_fields', 'conflicting_fields'):
            if not isinstance(e.get(k), list) or not all(isinstance(v, str) for v in e[k]):
                raise ValueError('invalid evidence fields')
    if r['verification_status'] == 'CONFLICT' and not r['conflicting_fields']:
        raise ValueError('conflict requires substantive conflicting fields')
    if r['verification_status'] in ('VERIFIED', 'PARTIALLY_VERIFIED'):
        if not r['matched_fields'] or not any(e['evidence_strength'] in 'ABC' for e in r['evidence']):
            raise ValueError('supported decision requires non-self-reported evidence')
    if r['verification_status'] == 'VERIFIED' and not any(e['evidence_strength'] in 'AB' for e in r['evidence']):
        raise ValueError('verified requires strong source')
    if r['freshness_status'] == 'CV_UPDATE_AVAILABLE' and not r['suggested_cv_update']:
        raise ValueError('freshness update requires factual suggestion')
    m = r['journal_metrics']
    if r['claim_type'] != 'publication':
        if m is not None:
            raise ValueError('non-publication metrics must be null')
    else:
        if not isinstance(m, dict) or set(m) != set(empty_metrics()):
            raise ValueError('invalid metrics shape')
        if m['metric_name'] != 'Journal Impact Factor':
            raise ValueError('invalid metric')
        if m['latest_jif'] is not None:
            if isinstance(m['latest_jif'], bool) or not isinstance(m['latest_jif'], (float, int)):
                raise ValueError('invalid JIF')
            if not isinstance(m['jif_year'], int) or not all(m[k] for k in ('metric_source', 'metric_source_url', 'metric_source_quality')):
                raise ValueError('JIF requires year and source')
    return r


def validate_candidate(d, original=None):
    errors = list(VALIDATOR.iter_errors(d))
    if errors:
        raise ValueError("JSON schema validation failed")
    for k in ('candidate_id', 'application_id', 'verification_version', 'verified_at'):
        if not isinstance(d.get(k), str):
            raise ValueError('invalid candidate header')
    if d['verification_version'] != '1.0' or not isinstance(d.get('results'), list):
        raise ValueError('invalid verification version/results')
    if d.get('claims_total') != len(d['results']):
        raise ValueError('incomplete results')
    ids = [validate_result(r)['claim_id'] for r in d['results']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate claim IDs')
    if original:
        if d['candidate_id'] != original['candidate_id'] or d['application_id'] != original['application_id']:
            raise ValueError('candidate identity mismatch')
        if d.get('input_sha256') != fingerprint(original):
            raise ValueError('input changed')
        if ids != [c['claim_id'] for c in original['claims']]:
            raise ValueError('claim coverage mismatch')
        for r, c in zip(d['results'], original['claims']):
            if r['claim_type'] != c['claim_type'] or r['original_claim'] != result(c)['original_claim']:
                raise ValueError('original claim changed')
    return d
