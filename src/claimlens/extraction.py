from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_ALIASES = {
    "education": ("教育经历","教育背景","学历","education","academic background","education and training"),
    "publications": ("代表性论文","论文发表","科研论文","发表论文","publications","selected publications","published articles","research publications"),
    "working_papers": ("在研第一作者论文","在研论文","working papers","manuscripts","articles to be published"),
    "awards": ("荣誉、竞赛与学术奖励","荣誉与奖励","荣誉奖项","获奖情况","honors & awards","honours & awards","awards","honors"),
    "patents": ("专利","发明专利","patents","patent filings","publications/patent","publications and patent filings"),
    "conferences": ("国际学术交流","学术会议","conference presentations","conferences","presentations"),
    "qualifications": ("专业资质与培训经历","专业资质","资格证书","certifications","professional qualifications","licenses"),
    "projects": ("人工智能与科研系统开发","科研项目","research projects","projects"),
    "skills": ("核心研究能力与特色","技能","skills","research skills"),
    "profile": ("个人概况","个人简介","profile","summary"),
}
HEADING_ONLY = {x.casefold() for values in SECTION_ALIASES.values() for x in values}
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
PATENT_RE = re.compile(r"\b(?:CN|US|EP|WO|JP|KR)\s?\d{5,}[A-Z0-9.]*\b", re.I)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
BULLET_RE = re.compile(r"^\s*(?:[•●▪■◆◇*]|[-–—]|\d{1,3}[.)、]|\[\d+\])\s*")
PUB_SIGNAL = re.compile(r"\b(?:doi|journal|vol(?:ume)?|issue|pp?\.|accepted|published|et al\.?|in press)\b", re.I)
AWARD_SIGNAL = re.compile(r"奖|获奖|一等奖|二等奖|三等奖|金奖|银奖|award|prize|medal|winner|honou?r", re.I)
PATENT_SIGNAL = re.compile(r"专利|patent|utility model|inventor|发明人", re.I)

@dataclass
class LogicalItem:
    section: str
    text: str
    source_lines: list[str] = field(default_factory=list)

@dataclass
class QualityDecision:
    action: str
    reasons: list[str] = field(default_factory=list)

def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()

def detect_heading(line: str) -> str | None:
    normalized = clean_line(line).strip(":：").casefold()
    if not normalized:
        return None
    for section, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            a = alias.casefold()
            if normalized == a or (len(normalized) <= len(a) + 3 and normalized.startswith(a)):
                return section
    return None

def is_heading_only(text: str) -> bool:
    normalized = clean_line(text).strip(":：").casefold()
    return normalized in HEADING_ONLY or bool(re.fullmatch(
        r"(?:selected |research )?(?:publications?|patents?|awards?|honou?rs?|education|certifications?|presentations?)",
        normalized, re.I))

def _looks_new_item(line: str) -> bool:
    return bool(BULLET_RE.match(line))

def _continuation_score(current: str, nxt: str, section: str) -> int:
    score = 0
    if not current:
        return 0
    if current[-1:] in ",;:(" or not re.search(r"[.!?。！？)]$", current):
        score += 2
    if nxt and (nxt[0].islower() or nxt.startswith(("doi", "DOI", "http", "www."))):
        score += 2
    if section == "publications":
        if DOI_RE.search(nxt) or PUB_SIGNAL.search(nxt):
            score += 2
        if re.search(r"\b\d+\s*\(\d+\)\s*[:;,]\s*\d+", nxt):
            score += 1
    if section == "patents" and (PATENT_RE.search(nxt) or PATENT_SIGNAL.search(nxt)):
        score += 2
    return score

def reconstruct_document(text: str) -> list[LogicalItem]:
    lines = [clean_line(x) for x in text.splitlines()]
    lines = [x for x in lines if x]
    items: list[LogicalItem] = []
    section = "unsectioned"
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            joined = clean_line(" ".join(BULLET_RE.sub("", x, count=1) for x in current))
            if joined:
                items.append(LogicalItem(section=section, text=joined, source_lines=current[:]))
        current = []

    for line in lines:
        heading = detect_heading(line)
        if heading:
            flush()
            section = heading
            continue
        if is_heading_only(line):
            flush()
            continue
        if _looks_new_item(line):
            flush()
            current = [line]
            continue
        if not current:
            current = [line]
            continue
        if section in {"publications", "patents", "awards", "conferences"} and _looks_new_item(current[0]):
            current.append(line)
            continue
        joined = clean_line(" ".join(current))
        if _continuation_score(joined, line, section) >= 2:
            current.append(line)
        else:
            flush()
            current = [line]
    flush()
    return items

def classify_item(item: LogicalItem) -> str | None:
    text, section = item.text, item.section
    if is_heading_only(text) or len(text) < 8:
        return None
    if section == "publications":
        if PATENT_RE.search(text) or PATENT_SIGNAL.search(text):
            return "patent"
        return "publication"
    if section == "patents":
        return "patent"
    if section == "awards":
        return "competition" if re.search(r"竞赛|大赛|challenge|competition|contest", text, re.I) else "award"
    if section == "conferences":
        return "conference_presentation"
    if section == "education":
        return "education"
    if section == "qualifications":
        return "professional_qualification" if re.search(r"执业|医师资格|licen[cs]e|registration", text, re.I) else "certification"
    if section == "working_papers":
        return "working_paper"
    if section in {"projects","skills","profile"}:
        return None
    if PATENT_RE.search(text) or PATENT_SIGNAL.search(text):
        return "patent"
    if DOI_RE.search(text) or PUB_SIGNAL.search(text):
        return "publication"
    if AWARD_SIGNAL.search(text):
        return "award"
    return None

def quality_gate(item: LogicalItem, claim_type: str) -> QualityDecision:
    text = item.text
    reasons: list[str] = []
    if is_heading_only(text):
        return QualityDecision("DROP", ["HEADING_AS_CLAIM"])
    if len(text) < 12:
        return QualityDecision("REVIEW", ["ORPHAN_FRAGMENT"])
    if claim_type == "publication":
        if re.search(r"\b\d+\s+(?:peer[- ]reviewed\s+)?publications?\b|\bh[- ]?index\b|\bcitations?\b", text, re.I) and not DOI_RE.search(text):
            return QualityDecision("REVIEW", ["AGGREGATE_PUBLICATION_SUMMARY"])
        signals = sum(bool(x) for x in (
            DOI_RE.search(text), YEAR_RE.search(text), PUB_SIGNAL.search(text),
            re.search(r"\b(?:journal|medicine|science|research|nature|cell|lancet|bmj)\b", text, re.I),
        ))
        if PATENT_RE.search(text):
            return QualityDecision("REVIEW", ["MIXED_CLAIM_TYPE"])
        if signals < 2:
            reasons.append("PUBLICATION_WITHOUT_METADATA")
    elif claim_type == "patent":
        if not PATENT_RE.search(text):
            reasons.append("PATENT_WITHOUT_IDENTIFIER")
    if re.search(r"\b(?:publications?|selected publications?|honors?\s*&\s*awards?)\b\s*$", text, re.I):
        reasons.append("HEADING_AS_CLAIM")
    return QualityDecision("PASS" if not reasons else "REVIEW", reasons)
