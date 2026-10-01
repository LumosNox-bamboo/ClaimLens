from __future__ import annotations

import re
from pathlib import Path

from .models import Claim
from .privacy import detect_pii, redact_text

YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
PATENT_NO = re.compile(r"\b(?:CN|US|EP|WO|JP|KR)\s?\d{5,}[A-Z0-9]*\b", re.I)

HEADINGS = {
    "教育经历": "education",
    "代表性论文": "publications",
    "在研第一作者论文": "working_papers",
    "人工智能与科研系统开发": "projects",
    "荣誉、竞赛与学术奖励": "awards",
    "国际学术交流": "conferences",
    "专业资质与培训经历": "qualifications",
    "核心研究能力与特色": "skills",
    "个人概况": "profile",
}
ORDER = list(HEADINGS)

GENERIC_RULES = [
    ("publication", re.compile(r"论文|发表|期刊|journal|publication|published|doi|article|paper|proceedings", re.I)),
    ("patent", re.compile(r"专利|发明人|patent|inventor|utility model", re.I)),
    ("award", re.compile(r"获奖|奖项|一等奖|二等奖|三等奖|金奖|银奖|荣誉|award|prize|winner|medal|honou?r", re.I)),
    ("competition", re.compile(r"竞赛|比赛|挑战赛|大赛|competition|contest|olympiad|hackathon|challenge", re.I)),
    ("certification", re.compile(r"证书|认证|资格证|certificat(?:e|ion)|credential|licensed", re.I)),
    ("education", re.compile(r"教育经历|学历|学位|本科|硕士|博士|大学|学院|education|bachelor|master|ph\.?d|doctorate|university|college", re.I)),
    ("professional_qualification", re.compile(r"职业资格|执业|专业资格|注册.*师|professional qualification|board certified|licen[cs]e|registration", re.I)),
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" •\t-–—")


def _privacy_risk(text: str) -> str:
    findings = detect_pii(text)
    if any(x.risk == "high" for x in findings):
        return "high"
    return "medium" if findings else "low"


def _sections(text: str) -> list[tuple[str, str]]:
    marked = text
    for heading in ORDER:
        marked = marked.replace(heading, f"\n§§{heading}§§\n")
    matches = list(re.finditer(r"§§([^§]+)§§", marked))
    out = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(marked)
        out.append((HEADINGS.get(match.group(1), "other"), _clean(marked[start:end])))
    return out


def _split_numbered(body: str) -> list[str]:
    parts = re.split(r"(?=(?<!\d)(?:[1-9]\.|0?[1-9]｜)\s*)", body)
    return [_clean(part) for part in parts if _clean(part)]


def _split_year_items(body: str) -> list[str]:
    parts = re.split(r"(?=(?<!\d)(?:19|20)\d{2}(?:[.\-]\d{1,2})?)", body)
    return [_clean(part) for part in parts if _clean(part)]


def _split_education(body: str) -> list[str]:
    pattern = r"(?=(?<!\d)(?:19|20)\d{2}\.\d{2}[–-](?:至今|(?:19|20)\d{2}\.\d{2}))"
    parts = re.split(pattern, body)
    return [_clean(part) for part in parts if _clean(part)]


def _split_bullets(body: str) -> list[str]:
    return [_clean(part) for part in re.split(r"\s*[•●]\s*", body) if _clean(part)]


def _make_claim(
    candidate_id: str,
    index: int,
    claim_type: str,
    text: str,
    source_file: str,
    section: str,
    **kwargs: str,
) -> Claim:
    safe, _ = redact_text(_clean(text), "verification")
    years = YEAR.findall(safe)
    dois = DOI.findall(safe)
    patents = PATENT_NO.findall(safe)
    query = kwargs.pop("verification_query", "") or (dois[0] if dois else safe[:500])
    return Claim(
        candidate_id=candidate_id,
        claim_id=f"{candidate_id}-{index:03d}",
        claim_type=claim_type,
        claim_text=safe[:1500],
        year=kwargs.pop("year", years[0] if years else ""),
        doi=kwargs.pop("doi", dois[0].rstrip(".,;") if dois else ""),
        patent_number=kwargs.pop("patent_number", patents[0] if patents else ""),
        verification_query=query,
        privacy_risk=_privacy_risk(text),
        source_file=Path(source_file).suffix.lower() if source_file else "",
        source_section=section,
        **kwargs,
    )


def extract_claims(text: str, candidate_id: str, source_file: str = "") -> list[Claim]:
    """Extract factual CV claims with section-aware rules and a legacy line fallback."""
    claims: list[Claim] = []

    def add(claim_type: str, item: str, section: str, **kwargs: str) -> None:
        claims.append(
            _make_claim(
                candidate_id,
                len(claims) + 1,
                claim_type,
                item,
                source_file,
                section,
                **kwargs,
            )
        )

    sections = _sections(text)
    if not sections:
        seen: set[str] = set()
        for raw in text.splitlines():
            line = _clean(raw)
            if len(line) < 6 or line in seen:
                continue
            for claim_type, pattern in GENERIC_RULES:
                if pattern.search(line):
                    seen.add(line)
                    add(
                        claim_type,
                        line,
                        "unsectioned",
                        title=line[:500] if claim_type == "publication" else "",
                        award_name=line[:300] if claim_type == "award" else "",
                    )
                    break
        return claims

    for section, body in sections:
        if section == "education":
            for item in _split_education(body):
                if re.search(
                    r"大学|学院|University|College|本科|硕士|博士|Bachelor|Master|Ph\.?D",
                    item,
                    re.I,
                ):
                    add("education", item, section, verification_priority="high")

        elif section == "publications":
            for item in _split_numbered(body):
                if DOI.search(item) or re.search(
                    r"Accepted|\b20\d{2}\b|Journal|Medicine|Sciences?",
                    item,
                    re.I,
                ):
                    add(
                        "publication",
                        item,
                        section,
                        title=item[:500],
                        verification_priority="high",
                    )

        elif section == "working_papers":
            for item in _split_bullets(body):
                if len(item) > 20:
                    add(
                        "working_paper",
                        item,
                        section,
                        title=item[:500],
                        verification_scope="self_reported",
                        verification_priority="low",
                        verification_query="",
                    )

        elif section == "awards":
            graduation = "本科及硕士毕业均获上海市优秀毕业生（Top 2%）"
            award_body = body.replace(graduation, "").strip()
            for item in _split_year_items(award_body):
                if re.search(
                    r"奖|优秀|Winner|Gold|Silver|Top|名|入选|award|prize|medal|competition|大赛|竞赛",
                    item,
                    re.I,
                ):
                    is_competition = re.search(
                        r"大赛|竞赛|挑战赛|competition|contest|第\s*\d+\s*名",
                        item,
                        re.I,
                    )
                    claim_type = "competition" if is_competition else "award"
                    add(
                        claim_type,
                        item,
                        section,
                        award_name=item[:300] if claim_type == "award" else "",
                        verification_priority="high",
                    )
            if "本科及硕士毕业均获上海市优秀毕业生" in body:
                add(
                    "award",
                    graduation,
                    section,
                    award_name="上海市优秀毕业生",
                    verification_priority="high",
                )

        elif section == "conferences":
            for item in _split_year_items(body):
                if re.search(r"Congress|Conference|Kongress|研讨会|学术", item, re.I):
                    add(
                        "conference_presentation",
                        item,
                        section,
                        verification_priority="medium",
                    )

        elif section == "qualifications":
            relevant = re.split(r"临床心理实践[:：]|语言[:：]", body, maxsplit=1)[0]
            chunks = re.sub(r"专业资质[:：]", "；", relevant)
            for item in [_clean(x) for x in re.split(r"[；;]", chunks) if _clean(x)]:
                if re.search(
                    r"医师资格|资格证|执业|licen[cs]e|certif|course|课程|培训|training",
                    item,
                    re.I,
                ):
                    is_professional = re.search(
                        r"医师资格|资格证|执业|licen[cs]e",
                        item,
                        re.I,
                    )
                    claim_type = (
                        "professional_qualification" if is_professional else "certification"
                    )
                    add(
                        claim_type,
                        item,
                        section,
                        verification_priority=(
                            "high" if claim_type == "professional_qualification" else "low"
                        ),
                    )

        # profile, skills and projects are intentionally excluded.
    return claims
