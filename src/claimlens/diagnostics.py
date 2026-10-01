from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

SAFE_REASON_KEYS = {
    "HEADING_AS_CLAIM", "ORPHAN_FRAGMENT", "MIXED_CLAIM_TYPE",
    "PUBLICATION_WITHOUT_METADATA", "PATENT_WITHOUT_IDENTIFIER",
    "POSSIBLE_DUPLICATE", "AGGREGATE_PUBLICATION_SUMMARY",
}
FORBIDDEN_SAFE_KEYS = {
    "preview", "claim_text", "title", "authors", "organization", "journal",
    "award_name", "verification_query", "source_file", "source_folder",
    "candidate_name", "application_id", "raw_text", "text", "path",
}


def _safe_candidate_token(index: int) -> str:
    return f"DOC-{index:04d}"


def build_codex_safe_diagnostics(
    local_diagnostics: Iterable[dict[str, object]],
) -> dict[str, object]:
    """Aggregate structural failures without exporting CV content or identity fields."""
    reason_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    claim_type_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    documents: list[dict[str, object]] = []

    for index, payload in enumerate(local_diagnostics, 1):
        doc_reasons: Counter[str] = Counter()
        doc_sections: Counter[str] = Counter()
        doc_types: Counter[str] = Counter()
        for item in payload.get("diagnostics", []) or []:
            if not isinstance(item, dict):
                continue
            section = str(item.get("section", "unknown"))
            claim_type = str(item.get("claim_type", "unknown"))
            reasons = [
                str(r) for r in item.get("reasons", []) or []
                if str(r) in SAFE_REASON_KEYS
            ]
            doc_sections[section] += 1
            section_counts[section] += 1
            if claim_type != "unknown":
                doc_types[claim_type] += 1
                claim_type_counts[claim_type] += 1
            doc_reasons.update(reasons)
            reason_counts.update(reasons)
        flags = [str(x) for x in payload.get("health_flags", []) or []]
        flag_counts.update(flags)
        documents.append({
            "document": _safe_candidate_token(index),
            "claims_accepted": int(payload.get("claims_accepted", 0) or 0),
            "items_review": int(payload.get("items_review", 0) or 0),
            "items_dropped": int(payload.get("items_dropped", 0) or 0),
            "health_flags": flags,
            "reason_counts": dict(doc_reasons),
            "section_item_counts": dict(doc_sections),
            "claim_type_counts": dict(doc_types),
            "ready_for_verification": bool(payload.get("ready_for_verification", False)),
        })

    return {
        "schema": "claimlens.codex-safe-diagnostics.v1",
        "privacy": {
            "raw_cv_included": False,
            "raw_text_included": False,
            "identity_mapping_included": False,
            "claim_content_included": False,
            "application_ids_included": False,
            "paths_included": False,
        },
        "corpus": {
            "documents": len(documents),
            "ready_for_verification": sum(bool(x["ready_for_verification"]) for x in documents),
            "needs_extraction_review": sum(not bool(x["ready_for_verification"]) for x in documents),
        },
        "failure_patterns": {
            "health_flags": dict(flag_counts),
            "reasons": dict(reason_counts),
            "sections": dict(section_counts),
            "claim_types": dict(claim_type_counts),
        },
        "documents": documents,
    }


def assert_codex_safe(payload: object) -> None:
    """Fail closed if content-bearing or identity-bearing keys enter CODEX_SAFE."""
    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).casefold() in FORBIDDEN_SAFE_KEYS:
                    raise ValueError(f"CODEX_SAFE privacy guard rejected forbidden field: {key}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(payload)


def write_codex_safe(local_dir: Path, safe_dir: Path) -> Path:
    payloads = []
    for path in sorted(local_dir.glob("*.extraction.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    safe = build_codex_safe_diagnostics(payloads)
    assert_codex_safe(safe)
    safe_dir.mkdir(parents=True, exist_ok=True)
    out = safe_dir / "corpus_summary.json"
    out.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    (safe_dir / "README_PRIVACY.txt").write_text(
        "CODEX_SAFE contains aggregate structural extraction diagnostics only. "
        "It excludes candidate names, application IDs, file paths, raw CV text, "
        "claim text, titles, authors, organizations, journals and award names.\n",
        encoding="utf-8",
    )
    return out


def reject_unsafe_codex_input(path: Path) -> None:
    """Programmatic guard for any future command that hands files to an external agent."""
    lowered = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    forbidden_parts = {"resumes", "00_local_only", "local_only"}
    if lowered & forbidden_parts:
        raise ValueError("Unsafe Codex input: raw CV or LOCAL_ONLY path is forbidden")
    if name == "candidate_map.xlsx":
        raise ValueError("Unsafe Codex input: candidate identity map is forbidden")
    if suffix in {".pdf", ".docx"}:
        raise ValueError("Unsafe Codex input: raw document formats are forbidden")
    if "codex_safe" not in lowered:
        raise ValueError("Unsafe Codex input: only a CODEX_SAFE directory may be used")
