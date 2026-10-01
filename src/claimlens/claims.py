from __future__ import annotations

import re
from pathlib import Path

from .models import Claim
from .privacy import detect_pii, redact_text

YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
PATENT_NO = re.compile(r"\b(?:CN|US|EP|WO|JP|KR)\s?\d{5,}[A-Z0-9]*\b", re.I)

RULES = [
    ("publication", re.compile(r"论文|发表|期刊|著作|journal|publication|published|doi|article|paper|proceedings", re.I)),
    ("patent", re.compile(r"专利|发明人|patent|inventor|utility model", re.I)),
    ("award", re.compile(r"获奖|奖项|一等奖|二等奖|三等奖|金奖|银奖|荣誉|award|prize|winner|medal|honou?r", re.I)),
    ("competition", re.compile(r"竞赛|比赛|挑战赛|大赛|competition|contest|olympiad|hackathon|challenge", re.I)),
    ("certification", re.compile(r"证书|认证|资格证|certificat(?:e|ion)|credential|licensed", re.I)),
    ("education", re.compile(r"教育经历|学历|学位|本科|硕士|博士|大学|学院|education|bachelor|master|ph\.?d|doctorate|university|college", re.I)),
    ("professional_qualification", re.compile(r"职业资格|执业|专业资格|注册.*师|professional qualification|board certified|licen[cs]e|registration", re.I)),
]


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" •\t-–—")


def _privacy_risk(line: str) -> str:
    findings = detect_pii(line)
    if any(x.risk == "high" for x in findings):
        return "high"
    return "medium" if findings else "low"


def extract_claims(text: str, candidate_id: str, source_file: str = "") -> list[Claim]:
    """Transparent bilingual rule-based extraction; conservative by design for v0.1."""
    claims: list[Claim] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = _clean(raw)
        if len(line) < 6 or line in seen:
            continue
        for claim_type, pattern in RULES:
            if not pattern.search(line):
                continue
            seen.add(line)
            years, dois, patents = YEAR.findall(line), DOI.findall(line), PATENT_NO.findall(line)
            safe_line, _ = redact_text(line, "verification")
            idx = len(claims) + 1
            title = safe_line[:500] if claim_type == "publication" else ""
            claim = Claim(
                candidate_id=candidate_id,
                claim_id=f"{candidate_id}-{idx:03d}",
                claim_type=claim_type,
                claim_text=safe_line[:1500],
                title=title,
                year=years[0] if years else "",
                doi=dois[0] if dois else "",
                patent_number=patents[0] if patents else "",
                award_name=safe_line[:300] if claim_type == "award" else "",
                verification_query=safe_line[:500],
                privacy_risk=_privacy_risk(line),
                source_file=Path(source_file).suffix.lower() if source_file else "",
            )
            claims.append(claim)
            break
    return claims
