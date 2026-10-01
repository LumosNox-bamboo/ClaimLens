from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .models import Claim

CLAIM_HEADERS = [
    "candidate_id", "claim_id", "claim_type", "claim_text", "title", "year",
    "organization", "journal", "doi", "patent_number", "award_name", "authors",
    "verification_query", "privacy_risk", "source_file",
]


def export_claims(claims: list[Claim], out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [c.row() for c in claims]
    json_path = out_dir / "claims.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = out_dir / "claims.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CLAIM_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "claims"
    ws.append(CLAIM_HEADERS)
    for cell in ws[1]:\n        cell.font = Font(bold=True)
    for row in rows:\n        ws.append([row.get(h, "") for h in CLAIM_HEADERS])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        letter = col[0].column_letter
        ws.column_dimensions[letter].width = min(max(12, max(len(str(c.value or "")) for c in col) + 2), 60)
    xlsx_path = out_dir / "claims.xlsx"
    wb.save(xlsx_path)
    return json_path, xlsx_path, csv_path
