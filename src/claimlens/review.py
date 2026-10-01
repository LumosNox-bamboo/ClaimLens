from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ReviewItem:
    candidate_id: str
    claim_id: str
    claim_type: str
    outbound_fields: dict[str, str]
    reason: str
    approved: bool = False


def build_review(claims_path: Path, out_path: Path) -> list[ReviewItem]:
    rows = json.loads(claims_path.read_text(encoding="utf-8"))
    items = []
    for row in rows:
        fields = {k: row.get(k, "") for k in ("title", "year", "organization", "journal", "doi", "patent_number", "award_name", "verification_query") if row.get(k)}
        items.append(ReviewItem(row["candidate_id"], row["claim_id"], row["claim_type"], fields, "Minimum fields proposed for public-source verification", False))
    payload = {
        "network_access": False,
        "warning": "Review every outbound field before any future network verification. Pseudonymized data is not necessarily anonymous.",
        "items": [asdict(x) for x in items],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


def review_summary(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    return len(items), sum(bool(x.get("approved")) for x in items)
