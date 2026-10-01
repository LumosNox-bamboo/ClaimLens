import re
import unicodedata
from difflib import SequenceMatcher

from .models import now


def norm(s):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', str(s)).casefold())


def title_match(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a == b or (min(len(a), len(b)) > 35 and SequenceMatcher(None, a, b).ratio() >= .96)))


def evidence(name, kind, url, strength, matched, conflicts=(), notes='Metadata inspected.'):
    return dict(source_name=name, source_type=kind, url=url, accessed_at=now(),
                evidence_strength=strength, matched_fields=list(matched),
                conflicting_fields=list(conflicts), notes=notes)


def apply(r, e):
    r['evidence'].append(e)
    r['matched_fields'] = sorted(set(r['matched_fields']) | set(e['matched_fields']))
    r['conflicting_fields'] = sorted(set(r['conflicting_fields']) | set(e['conflicting_fields']))
    r['unverified_fields'] = [f for f in r['unverified_fields'] if f not in r['matched_fields'] and f not in r['conflicting_fields']]
    r['evidence_strength'] = min(e['evidence_strength'] for e in r['evidence'])
    return r
