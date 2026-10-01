import json
from pathlib import Path
from claimlens.review import build_review, review_summary


def test_review_defaults_to_unapproved(tmp_path: Path):
    claims = [{"candidate_id":"C-ABC123","claim_id":"C-ABC123-001","claim_type":"publication","title":"Synthetic paper","year":"2024","doi":"10.1234/TEST.1"}]
    cp=tmp_path/"claims.json"
    cp.write_text(json.dumps(claims), encoding="utf-8")
    rp=tmp_path/"privacy_review.json"
    build_review(cp, rp)
    total, approved = review_summary(rp)
    assert (total, approved) == (1, 0)
    payload=json.loads(rp.read_text())
    assert payload["network_access"] is False
