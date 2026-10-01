from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path


def generate_salt() -> bytes:
    return secrets.token_bytes(32)


def load_salt(path: Path) -> bytes:
    raw = path.read_bytes().strip()
    if len(raw) < 32:
        raise ValueError("ClaimLens salt must contain at least 32 bytes")
    return raw


def ensure_salt(path: Path) -> bytes:
    if path.exists():
        return load_salt(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = generate_salt()
    path.write_bytes(salt)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return salt


def candidate_id(path: Path, salt: bytes) -> str:
    """Stable within a project, keyed, and independent of a candidate's real name."""
    digest = hmac.new(salt, path.read_bytes(), hashlib.sha256).hexdigest()[:6].upper()
    return f"C-{digest}"
