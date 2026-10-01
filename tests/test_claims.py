from claimlens.claims import extract_claims


def test_bilingual_claim_types():
    text = """2024 Published paper: Synthetic Biomarker Study. DOI: 10.1234/TEST.9
2023 获得示例医学创新大赛一等奖
2022 专利 CN123456789A 一种虚构装置
2021 Example University 医学博士 PhD
2025 Board Certified Example Specialist
2020 获得示例专业资格证书
"""
    claims = extract_claims(text, "C-ABC123", ".txt")
    types = {x.claim_type for x in claims}
    assert {"publication", "award", "patent", "education", "professional_qualification", "certification"} <= types
    pub = next(x for x in claims if x.claim_type == "publication")
    assert pub.doi == "10.1234/TEST.9" and pub.year == "2024"


def test_claim_text_redacts_direct_pii():
    claims = extract_claims("2024 Published paper DOI 10.1234/ABC.1 contact jane@example.test", "C-X")
    assert "jane@example.test" not in claims[0].claim_text
