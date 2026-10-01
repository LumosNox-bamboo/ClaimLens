from pathlib import Path

from claimlens.exporters import export_claims
from claimlens.models import Claim


def test_local_review_html_contains_only_claim_view(tmp_path: Path):
    claim = Claim(
        candidate_id="C-ABC123",
        claim_id="C-ABC123-001",
        claim_type="publication",
        claim_text="2025 Example study. Journal of Synthetic Results. doi:10.1234/example",
        title="Example study",
        year="2025",
        journal="Journal of Synthetic Results",
        doi="10.1234/example",
        verification_query="10.1234/example",
        privacy_risk="low",
        source_file=".pdf",
    )
    export_claims([claim], tmp_path)
    page = (tmp_path / "claims_review.html").read_text(encoding="utf-8")

    assert "Verification Review" in page
    assert "C-ABC123" in page
    assert "10.1234/example" in page
    assert "Original CV text" in page
    assert "Local preview" in page


def test_local_review_html_escapes_claim_content(tmp_path: Path):
    claim = Claim(
        candidate_id="C-SAFE001",
        claim_id="C-SAFE001-001",
        claim_type="award",
        claim_text="<script>alert('x')</script> Award",
        verification_query="<unsafe>",
    )
    export_claims([claim], tmp_path)
    page = (tmp_path / "claims_review.html").read_text(encoding="utf-8")

    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "&lt;unsafe&gt;" in page
