from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl import Workbook

from .claims import extract_claims_v2
from .identity import candidate_id as make_candidate_id
from .parsers import embedded_image_count, extract_text
from .privacy import detect_pii, pii_summary, redact_text


@dataclass
class BatchCandidate:
    candidate_id: str
    application_id: str
    candidate_name: str
    application_type: str
    source_folder: str
    source_file: str
    claims: int
    pii_detected: dict[str, int]
    embedded_images: int
    status: str = "processed"
    error: str = ""


_FOLDER_RE = re.compile(
    r"^(?P<prefix>.*?)_?(?P<application_id>SCDSG\d{2}-[A-Z]-[A-Z0-9]+)_(?P<name>.+)$",
    re.I,
)


def parse_candidate_folder(folder_name: str) -> tuple[str, str, str]:
    match = _FOLDER_RE.match(folder_name.strip())
    if not match:
        return "", "", ""
    prefix = match.group("prefix").strip("_ ")
    return prefix, match.group("application_id"), match.group("name").strip()


def discover_cvs(root: Path, filename: str = "简历.pdf") -> list[Path]:
    return sorted(path for path in root.rglob(filename) if path.is_file())


def _write_local_map(rows: list[BatchCandidate], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "LOCAL_ONLY"
    headers = [
        "candidate_id", "application_id", "candidate_name", "application_type",
        "source_folder", "source_file", "claims", "pii_detected",
        "embedded_images", "status", "error",
    ]
    ws.append(headers)
    for row in rows:
        data = asdict(row)
        data["pii_detected"] = json.dumps(data["pii_detected"], ensure_ascii=False)
        ws.append([data[h] for h in headers])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def run_batch(
    root: Path,
    out: Path,
    salt: bytes,
    privacy_mode: str = "verification",
    filename: str = "简历.pdf",
) -> tuple[int, int, int]:
    local_dir = out / "00_LOCAL_ONLY"
    diagnostics_dir = out / "01_EXTRACTION_DIAGNOSTICS"
    codex_dir = out / "02_CODEX_READY"
    local_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    codex_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[BatchCandidate] = []
    total_claims = 0
    failures = 0

    for path in discover_cvs(root, filename):
        app_type, app_id, name = parse_candidate_folder(path.parent.name)
        cid = make_candidate_id(path, salt)
        try:
            text = extract_text(path)
            _, findings = redact_text(text, privacy_mode)
            claims, diagnostics = extract_claims_v2(text, cid, path.suffix)
            review_items = [d for d in diagnostics if d.get("action") == "REVIEW"]
            dropped_items = [d for d in diagnostics if d.get("action") == "DROP"]
            health_flags = []
            if not claims:
                health_flags.append("ZERO_EXTRACTION")
            if len(claims) > 60:
                health_flags.append("EXTREME_CLAIM_COUNT")
            if review_items:
                health_flags.append("EXTRACTION_REVIEW_REQUIRED")
            extraction_pass = not health_flags
            diagnostic_payload = {
                "candidate_id": cid,
                "claims_accepted": len(claims),
                "items_review": len(review_items),
                "items_dropped": len(dropped_items),
                "health_flags": health_flags,
                "ready_for_verification": extraction_pass,
                "diagnostics": diagnostics,
            }
            (diagnostics_dir / f"{cid}.extraction.json").write_text(
                json.dumps(diagnostic_payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            public_claims = []
            for claim in claims:
                if claim.verification_scope != "public":
                    continue
                row = claim.row()
                outbound = " ".join(
                    str(row.get(key, ""))
                    for key in (
                        "claim_text", "title", "organization", "journal", "doi",
                        "patent_number", "award_name", "authors", "verification_query",
                    )
                )
                forbidden = [
                    finding for finding in detect_pii(outbound)
                    if finding.kind != "claim_author_list"
                ]
                if forbidden:
                    # Defense in depth: no public verification payload is emitted when
                    # residual PII is detected after claim-level redaction.
                    continue
                public_claims.append(row)
            payload = {
                "candidate_id": cid,
                "application_id": app_id,
                "claims": public_claims,
                "privacy": {
                    "original_cv_included": False,
                    "raw_extracted_text_included": False,
                    "local_file_path_included": False,
                    "contact_fields_included": False,
                },
            }
            if extraction_pass:
                (codex_dir / f"{cid}.claims.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            image_count = embedded_image_count(path)
            candidates.append(
                BatchCandidate(
                    candidate_id=cid,
                    application_id=app_id,
                    candidate_name=name,
                    application_type=app_type,
                    source_folder=str(path.parent),
                    source_file=str(path),
                    claims=len(claims),
                    pii_detected=pii_summary(findings),
                    embedded_images=image_count,
                )
            )
            total_claims += len(claims)
        except Exception as exc:
            failures += 1
            candidates.append(
                BatchCandidate(
                    candidate_id=cid,
                    application_id=app_id,
                    candidate_name=name,
                    application_type=app_type,
                    source_folder=str(path.parent),
                    source_file=str(path),
                    claims=0,
                    pii_detected={},
                    embedded_images=0,
                    status="error",
                    error=str(exc),
                )
            )

    _write_local_map(candidates, local_dir / "candidate_map.xlsx")
    summary = {
        "source_root": str(root),
        "cv_filename": filename,
        "candidates_discovered": len(candidates),
        "processed": len(candidates) - failures,
        "failed": failures,
        "claims_extracted": total_claims,
        "extraction_v2": True,
        "verification_packages_are_quality_gated": True,
        "network_access_performed": False,
        "codex_ready_contains_local_identity_map": False,
        "note": "00_LOCAL_ONLY contains identifying mappings and must remain local.",
    }
    (local_dir / "batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (codex_dir / "README_PRIVACY.txt").write_text(
        "02_CODEX_READY contains only candidates that passed the extraction quality gate. It contains pseudonymous candidate IDs, application IDs, and public-scope "
        "verification claims only. It excludes original CV files, raw extracted text, local "
        "paths, contact details, and the local candidate-name mapping. Review before sharing.\n",
        encoding="utf-8",
    )
    return len(candidates), total_claims, failures
