from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .models import PIIFinding, PrivacyMode


@dataclass(frozen=True)
class PatternSpec:
    kind: str
    pattern: re.Pattern[str]
    risk: str = "high"


SPECS = [
    PatternSpec("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    PatternSpec("chinese_id", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    PatternSpec("phone", re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{6,}\d)(?!\w)")),
    PatternSpec("dob", re.compile(r"(?i)(?:(?:date\s+of\s+birth|d\.?o\.?b\.?|出生日期|出生年月|生日)\s*[:：]?\s*)(?:19|20)\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?")),
    PatternSpec("age", re.compile(r"(?i)(?:(?:age|年龄)\s*[:：]?\s*)\d{1,3}(?:\s*(?:years?\s*old|岁))?"), "medium"),
    PatternSpec("passport", re.compile(r"(?i)(?:(?:passport(?:\s*(?:no|number|#))?|护照(?:号|号码)?)\s*[:：#]?\s*)[A-Z0-9]{5,20}")),
    PatternSpec("driver_license", re.compile(r"(?i)(?:(?:driver'?s?\s*licen[cs]e(?:\s*(?:no|number|#))?|驾驶证(?:号|号码)?)\s*[:：#]?\s*)[A-Z0-9-]{5,25}")),
    PatternSpec("wechat", re.compile(r"(?i)(?:(?:wechat|weixin|微信(?:号)?)\s*[:：]?\s*)[A-Z][-_A-Z0-9]{5,19}")),
    PatternSpec("qq", re.compile(r"(?i)(?:(?:QQ)\s*[:：]?\s*)[1-9]\d{4,11}")),
    PatternSpec("whatsapp", re.compile(r"(?i)(?:(?:whatsapp)\s*[:：]?\s*)\+?\d[\d ()-]{6,}\d")),
    PatternSpec("telegram", re.compile(r"(?i)(?:(?:telegram|tg)\s*[:：]?\s*)@[A-Z0-9_]{5,32}")),
    PatternSpec("social_handle", re.compile(r"(?i)(?:(?:twitter|x|instagram|linkedin|github|微博|小红书)\s*[:：]?\s*)@?[A-Z0-9_.-]{3,40}"), "medium"),
    PatternSpec("personal_url", re.compile(r"(?i)\bhttps?://[^\s<>()]+|\bwww\.[^\s<>()]+"), "medium"),
    PatternSpec("address", re.compile(r"(?im)(?:(?:home|postal|mailing|residential)?\s*address|家庭住址|家庭地址|通信地址|通讯地址|现住址|地址)\s*[:：]\s*[^\n]{5,160}")),
    PatternSpec("english_name", re.compile(r"(?im)^(?:(?:full\s*)?name)\s*[:：]\s*[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){1,4}\s*$")),
    PatternSpec("chinese_name", re.compile(r"(?m)(?:^|\n)(?:姓名|名字)\s*[:：]\s*[\u3400-\u9fff·]{2,12}(?=\s*(?:/|$))")),
    PatternSpec("emergency_contact", re.compile(r"(?im)^(?:emergency\s+contact|紧急联系人)\s*[:：].{2,180}$")),
    PatternSpec("reference_contact", re.compile(r"(?im)^(?:referee|reference\s+contact|推荐人|证明人)\s*[:：].{2,180}$")),
    PatternSpec("claim_author_list", re.compile(r"(?im)^(?:authors?|作者)\s*[:：]\s*[^\n]{2,300}$"), "medium"),
]


def detect_pii(text: str) -> list[PIIFinding]:
    found: list[PIIFinding] = []
    for spec in SPECS:
        for match in spec.pattern.finditer(text):
            found.append(PIIFinding(spec.kind, match.group(0), match.start(), match.end(), spec.risk))
    # Prefer broad labelled spans (address/reference) and avoid duplicate overlapping replacements.
    found.sort(key=lambda x: (x.start, -(x.end - x.start)))
    result: list[PIIFinding] = []
    for item in found:
        if any(item.start >= kept.start and item.end <= kept.end for kept in result):
            continue
        result.append(item)
    return result


STRICT_EXTRA = {"personal_url", "social_handle"}
VERIFICATION_KEEP = {"claim_author_list"}  # author lists can be necessary to disambiguate publications.


def redact_text(
    text: str,
    mode: PrivacyMode | str = PrivacyMode.VERIFICATION,
    *,
    keep: Iterable[str] = (),
    remove: Iterable[str] = (),
) -> tuple[str, list[PIIFinding]]:
    mode = PrivacyMode(mode)
    keep_set, remove_set = set(keep), set(remove)
    findings = detect_pii(text)
    selected: list[PIIFinding] = []
    for finding in findings:
        if finding.kind in keep_set:
            continue
        should_remove = mode in {PrivacyMode.STRICT, PrivacyMode.VERIFICATION}
        if mode is PrivacyMode.CUSTOM:
            should_remove = finding.kind in remove_set
        if mode is PrivacyMode.VERIFICATION and finding.kind in VERIFICATION_KEEP:
            should_remove = False
        if should_remove:
            selected.append(finding)
    out = text
    for finding in sorted(selected, key=lambda x: x.start, reverse=True):
        out = out[: finding.start] + f"[REDACTED_{finding.kind.upper()}]" + out[finding.end :]
    return out, findings


def pii_summary(findings: Iterable[PIIFinding]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.kind] = summary.get(finding.kind, 0) + 1
    return summary
