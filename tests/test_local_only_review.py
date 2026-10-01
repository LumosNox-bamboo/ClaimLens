import json
from pathlib import Path

from claimlens.exporters import export_claims
from claimlens.models import Claim
from claimlens.review import build_review


def test_self_reported_claim_not_proposed_for_network(tmp_path: Path):
    claims = [
        Claim(
            "C-X",
            "C-X-001",
            "publication",
            "Published",
            verification_query="doi",
            verification_scope="public",
        ),
        Claim(
            "C-X",
            "C-X-002",
            "working_paper",
            "Pending",
            verification_scope="self_reported",
        ),
    ]
    json_path, _, _ = export_claims(claims, tmp_path)
    build_review(json_path, tmp_path / "privacy_review.json")
    payload = json.loads((tmp_path / "privacy_review.json").read_text())
    assert [x["claim_id"] for x in payload["items"]] == ["C-X-001"]
    html = (tmp_path / "claims_review.html").read_text()
    assert "Local-only" in html
    assert "Pending" in html
