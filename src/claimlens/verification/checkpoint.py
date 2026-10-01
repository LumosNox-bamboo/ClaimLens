from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import fingerprint, result, validate_candidate, validate_result


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def complete(path, original):
    try:
        validate_candidate(read_json(path), original)
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def partial(path, original):
    try:
        d = read_json(path)
        if d['input_sha256'] != fingerprint(original):
            return {}, {}
        claims = {c['claim_id']: c for c in original['claims']}
        results = {}
        audits = {a['claim_id']: a for a in d['audit']}
        for r in d['results']:
            c = claims.get(r['claim_id'])
            if c and r['claim_id'] in audits:
                validate_result(r)
                if r['claim_type'] == c['claim_type'] and r['original_claim'] == result(c)['original_claim']:
                    results[r['claim_id']] = r
        return results, audits
    except (OSError, ValueError, TypeError, KeyError):
        return {}, {}
