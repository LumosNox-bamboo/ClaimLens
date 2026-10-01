from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from claimlens.verification.checkpoint import atomic_json
from claimlens.verification.models import now

from .data import REVIEW_STATUSES, load_batch, safe_url
from .render import candidate_page, dashboard_page

CANDIDATE_HEADERS = (
    "candidate_id",
    "application_id",
    "candidate_name",
    "public_claims",
    "verified",
    "partially_verified",
    "not_found",
    "needs_review",
    "conflict",
    "document_required",
    "cv_updates",
)
CLAIM_HEADERS = (
    "candidate_id",
    "application_id",
    "candidate_name",
    "claim_id",
    "claim_type",
    "title",
    "year",
    "verification_status",
    "evidence_strength",
    "freshness_status",
    "latest_jif",
    "jif_year",
    "review_reason",
    "evidence_count",
    "review_category",
    "extraction_issue",
    "review_priority",
    "evidence_urls",
)


def workbook_tables(candidates, anonymous=False):
    candidate_headers = [h for h in CANDIDATE_HEADERS if not (anonymous and h == "candidate_name")]
    claim_headers = [h for h in CLAIM_HEADERS if not (anonymous and h == "candidate_name")]
    cr = []
    claims = []
    for c in candidates:
        s = c["status_counts"]
        row = dict(
            candidate_id=c["candidate_id"],
            application_id=c["application_id"],
            candidate_name=c.get("candidate_name", ""),
            public_claims=c["public_claims"],
            verified=s["VERIFIED"],
            partially_verified=s["PARTIALLY_VERIFIED"],
            not_found=s["NOT_FOUND"],
            needs_review=s["NEEDS_REVIEW"],
            conflict=s["CONFLICT"],
            document_required=s["DOCUMENT_REQUIRED"],
            cv_updates=c["cv_updates"],
        )
        cr.append([row[h] for h in candidate_headers])
        for r in c["claims"]:
            m = r["journal_metrics"] or {}
            year = r["display"].get("year")
            row = dict(
                candidate_id=c["candidate_id"],
                application_id=c["application_id"],
                candidate_name=c.get("candidate_name", ""),
                claim_id=r["claim_id"],
                claim_type=r["claim_type"],
                title=r["display"]["title"],
                year=int(year) if str(year).isdigit() else year,
                verification_status=r["verification_status"],
                evidence_strength=r["evidence_strength"],
                freshness_status=r["freshness_status"],
                latest_jif=m.get("latest_jif"),
                jif_year=m.get("jif_year"),
                review_reason=r["review_reason"]
                if r["verification_status"] in REVIEW_STATUSES
                else "",
                evidence_count=len(r["evidence"]),
                review_category=r["review_category"]
                if r["verification_status"] in REVIEW_STATUSES
                else "",
                extraction_issue=r["extraction_issue"],
                review_priority=r["review_priority"]
                if r["verification_status"] in REVIEW_STATUSES
                else None,
                evidence_urls="\n".join(e["url"] for e in r["evidence"] if safe_url(e.get("url"))),
                suggested_update=json.dumps(r["suggested_cv_update"], ensure_ascii=False)
                if r["suggested_cv_update"]
                else "",
            )
            claims.append(row)
    queue = sorted(
        (r for r in claims if r["verification_status"] in REVIEW_STATUSES),
        key=lambda r: (r["review_priority"], r["application_id"], r["claim_id"]),
    )
    groups = {
        "Claims": claims,
        "Review Queue": queue,
        "Material Claims": [r for r in claims if r["verification_status"] == "DOCUMENT_REQUIRED"],
        "CV Updates": [r for r in claims if r["freshness_status"] == "CV_UPDATE_AVAILABLE"],
    }
    output = {"Candidates": dict(headers=candidate_headers, rows=cr)}
    for name, rows in groups.items():
        headers = claim_headers + (["suggested_update"] if name == "CV Updates" else [])
        output[name] = dict(headers=headers, rows=[[r.get(h) for h in headers] for r in rows])
    return output


def export_workbooks(candidates, anonymous, output, node, modules, preview_dir=None):
    # Local temporary JSON is removed after export and never printed or sent to an API.
    with tempfile.TemporaryDirectory(prefix="claimlens-report-xlsx-") as temp:
        temp = Path(temp)
        (temp / "node_modules").symlink_to(Path(modules).resolve(), target_is_directory=True)
        shutil.copyfile(Path(__file__).with_name("workbook.mjs"), temp / "workbook.mjs")
        atomic_json(
            temp / "input.json",
            dict(named=workbook_tables(candidates), anonymous=workbook_tables(anonymous, True)),
        )
        args = [str(node), str(temp / "workbook.mjs"), str(temp / "input.json"), str(output)]
        if preview_dir:
            args.append(str(preview_dir))
        process = subprocess.run(args, capture_output=True, text=True)
        if process.returncode:
            # Authoring exceptions may include cell contents; never echo runtime stderr.
            raise RuntimeError(
                "Local workbook export failed; reproduce with synthetic data for diagnostics"
            )


def input_hashes(batch):
    batch = Path(batch)
    files = [
        batch / "00_LOCAL_ONLY/candidate_map.xlsx",
        batch / "02_VERIFICATION_RESULTS/batch_summary.json",
    ]
    files += sorted((batch / "02_VERIFICATION_RESULTS").glob("C-*.verification.json"))
    files += sorted((batch / "02_VERIFICATION_RESULTS/_logs").glob("C-*.audit.json"))
    return {str(p.relative_to(batch)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def generate(
    batch, output=None, include_application_id=True, node=None, modules=None, preview_dir=None
):
    batch = Path(batch).resolve()
    output = Path(output).resolve() if output else batch / "03_REPORTS"
    if output == batch or output.name != "03_REPORTS":
        raise ValueError("Reports must use a separate 03_REPORTS directory")
    before = input_hashes(batch)
    candidates, anonymous, dashboard, gaps, missing, names = load_batch(
        batch, include_application_id
    )
    for folder in ("named", "anonymous", "assets", "data"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    for asset in ("styles.css", "report.js"):
        shutil.copyfile(Path(__file__).parent / "assets" / asset, output / "assets" / asset)
    (output / "index.html").write_text(dashboard_page(candidates, dashboard), encoding="utf-8")
    for collection, kind in ((candidates, "named"), (anonymous, "anonymous")):
        for c in collection:
            text = candidate_page(c, kind == "anonymous")
            if kind == "anonymous" and any(name in text for name in names):
                raise ValueError("Local identity found in anonymous report")
            (output / kind / (c["candidate_id"] + ".html")).write_text(text, encoding="utf-8")
    atomic_json(output / "data/dashboard.json", dashboard)
    atomic_json(output / "data/candidates_named.json", candidates)
    atomic_json(output / "data/candidates_anonymous.json", anonymous)
    atomic_json(output / "data/journal_metric_gaps.json", gaps)
    if node and modules:
        export_workbooks(candidates, anonymous, output, node, modules, preview_dir)
    privacy = """LOCAL REPORT DIRECTORY

named/, verification_results.xlsx and data/candidates_named.json contain candidate identity information.
named reports contain local identity mappings and must remain local.
index.html also contains the local candidate-name mapping.
Do not upload these files to public repositories or external services.

anonymous/, verification_results_anonymous.xlsx and data/candidates_anonymous.json remove the local candidate-name mapping but may still contain application IDs and public professional claims.
Review before external sharing. Anonymous pages link back to the named dashboard; do not share the whole directory as an anonymous package.

All assets are local. Opening the report makes no verification requests. Evidence links open only when explicitly clicked.
No candidate scores or rankings are generated. Review order concerns individual claims only.
NOT_FOUND, NEEDS_REVIEW and DOCUMENT_REQUIRED do not indicate that a claim is false.
"""
    (output / "README_PRIVACY.txt").write_text(privacy, encoding="utf-8")
    report = dict(
        candidates_expected=load_json_summary(batch).get("total_candidates"),
        candidates_rendered=len(candidates),
        named_reports=len(candidates),
        anonymous_reports=len(anonymous),
        claims_rendered=dashboard["total_claims"],
        status_counts=dashboard["verification_status_counts"],
        high_value_review_queue_count=dashboard["high_value_review_queue_count"],
        material_claim_count=sum(
            r["verification_status"] == "DOCUMENT_REQUIRED" for c in candidates for r in c["claims"]
        ),
        extraction_issue_count=dashboard["extraction_issue_count"],
        cv_update_count=dashboard["CV_UPDATE_AVAILABLE"],
        jif_available_count=dashboard["JIF_found"],
        jif_missing_count=dashboard["JIF_unavailable"],
        unique_journals_missing_metrics=len(gaps["journals"]),
        **missing,
        data_integrity_warnings=dashboard["data_integrity_warnings"],
        xlsx_generated=bool(node and modules),
        generated_at=now(),
        identity_join="Exact candidate_id; no name-based matching or deduplication of claims.",
        source_files_unchanged=before == input_hashes(batch),
    )
    if not report["source_files_unchanged"]:
        raise RuntimeError("Read-only source fingerprint check failed")
    atomic_json(output / "report_generation_summary.json", report)
    return report


def load_json_summary(batch):
    return json.loads((batch / "02_VERIFICATION_RESULTS/batch_summary.json").read_text())


def main():
    p = argparse.ArgumentParser(
        description="Generate offline review reports from local verification results and identity mapping"
    )
    p.add_argument("batch", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--omit-application-id", action="store_true")
    p.add_argument("--xlsx-node", type=Path, required=True)
    p.add_argument("--xlsx-modules", type=Path, required=True)
    args = p.parse_args()
    report = generate(
        args.batch, args.out, not args.omit_application_id, args.xlsx_node, args.xlsx_modules
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "candidates_rendered",
                    "claims_rendered",
                    "high_value_review_queue_count",
                    "extraction_issue_count",
                    "cv_update_count",
                    "xlsx_generated",
                )
            },
            ensure_ascii=False,
        )
    )
    print("data_integrity_warning_count", len(report["data_integrity_warnings"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
