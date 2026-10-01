from claimlens.claims import extract_claims_v2
from claimlens.extraction import classify_item, quality_gate, reconstruct_document


def test_heading_is_not_a_claim():
    text = """SELECTED PUBLICATIONS
1. Example A, Example B.
A complete synthetic study title.
Example Journal. 2025;12(3):1-9.
doi:10.1234/example.2025.1
"""
    claims, diagnostics = extract_claims_v2(text, "C-SYN", ".pdf")
    assert len(claims) == 1
    assert claims[0].claim_type == "publication"
    assert "SELECTED PUBLICATIONS" not in claims[0].claim_text
    assert claims[0].doi == "10.1234/example.2025.1"


def test_multiline_publication_is_reconstructed_before_classification():
    text = """PUBLICATIONS
1. Example Author.
Mechanisms of synthetic data reconstruction in medicine.
Journal of Example Research.
2024;10(2):10-20.
"""
    items = reconstruct_document(text)
    assert len(items) == 1
    assert "Mechanisms of synthetic data reconstruction" in items[0].text
    assert "2024;10(2):10-20" in items[0].text
    assert classify_item(items[0]) == "publication"
    assert quality_gate(items[0], "publication").action == "PASS"


def test_patent_section_does_not_fall_back_to_publication():
    text = """PATENT FILINGS
1. Example Inventor. A synthetic device. Utility Model Patent.
CN202399999999.9
"""
    claims, _ = extract_claims_v2(text, "C-SYN", ".pdf")
    assert len(claims) == 1
    assert claims[0].claim_type == "patent"
    assert claims[0].patent_number.startswith("CN202399999999")


def test_orphan_fragment_is_withheld():
    text = """PUBLICATIONS
ternary nanoparticles.
"""
    claims, diagnostics = extract_claims_v2(text, "C-SYN", ".pdf")
    assert claims == []
    assert any(d["action"] == "REVIEW" for d in diagnostics)


def test_project_prose_is_not_publication_claim():
    text = """RESEARCH PROJECTS
Analyzing data and writing the research paper
Assisted in conducting synthetic experiments and writing the research paper
"""
    claims, _ = extract_claims_v2(text, "C-SYN", ".pdf")
    assert claims == []


def test_publication_summary_is_not_misread_as_individual_article():
    text = """PUBLICATIONS
22 peer-reviewed publications | 387 citations | h-index 10
"""
    claims, diagnostics = extract_claims_v2(text, "C-SYN", ".pdf")
    assert claims == []
    assert diagnostics
