from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .models import Claim

CLAIM_HEADERS = [
    "candidate_id", "claim_id", "claim_type", "claim_text", "title", "year",
    "organization", "journal", "doi", "patent_number", "award_name", "authors",
    "verification_query", "privacy_risk", "source_file",
]

TYPE_LABELS = {
    "publication": "Publication / 论文",
    "award": "Award / 奖项",
    "patent": "Patent / 专利",
    "competition": "Competition / 竞赛",
    "certification": "Certification / 证书",
    "education": "Education / 教育",
    "professional_qualification": "Professional qualification / 职业资质",
}


def _write_review_html(claims: list[Claim], path: Path) -> None:
    groups: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        groups[claim.candidate_id].append(claim)
    counts = Counter(c.claim_type for c in claims)
    summary = "".join(
        f'<span class="chip">{escape(TYPE_LABELS.get(k, k))}: {v}</span>'
        for k, v in sorted(counts.items())
    ) or '<span class="muted">No verifiable claims extracted.</span>'

    candidate_sections = []
    for candidate_id, items in sorted(groups.items()):
        cards = []
        for claim in items:
            fields = [
                ("Year / 年份", claim.year),
                ("DOI", claim.doi),
                ("Journal / 期刊", claim.journal),
                ("Organization / 机构", claim.organization),
                ("Patent / 专利号", claim.patent_number),
                ("Award / 奖项", claim.award_name),
                ("Authors / 作者", claim.authors),
            ]
            field_html = "".join(
                f'<div><dt>{escape(label)}</dt><dd>{escape(str(value))}</dd></div>'
                for label, value in fields if value
            )
            if not field_html:
                field_html = '<div><dt>Parsed fields / 已解析字段</dt><dd class="muted">No additional structured field yet</dd></div>'
            cards.append(f"""
<article class="claim">
  <div class="claim-head">
    <span class="type">{escape(TYPE_LABELS.get(claim.claim_type, claim.claim_type))}</span>
    <span class="risk risk-{escape(claim.privacy_risk)}">privacy: {escape(claim.privacy_risk)}</span>
  </div>
  <h3>{escape(claim.claim_text)}</h3>
  <dl>{field_html}</dl>
  <details>
    <summary>Verification payload preview / 待核验查询预览</summary>
    <p>{escape(claim.verification_query)}</p>
    <small>Nothing on this page is sent over the network. Future online verification still requires Privacy Review approval.</small>
  </details>
  <div class="claim-id">{escape(claim.claim_id)}</div>
</article>""")
        candidate_sections.append(
            f'<section><h2>{escape(candidate_id)} <span class="muted">· {len(items)} claim(s)</span></h2>{"".join(cards)}</section>'
        )

    body = "".join(candidate_sections) or """
<section class="empty">
  <h2>No verifiable claims extracted / 未提取到待核验事实</h2>
  <p>ClaimLens intentionally does not display the original CV text here.</p>
</section>"""

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClaimLens · Verification Review</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; }}
body {{ max-width: 1080px; margin: 0 auto; padding: 40px 24px 80px; line-height: 1.5; }}
header {{ border-bottom: 1px solid #8885; padding-bottom: 24px; margin-bottom: 28px; }}
h1 {{ margin: 0 0 8px; font-size: 2rem; }} h2 {{ margin-top: 34px; }}
.notice {{ padding: 12px 14px; border: 1px solid #8885; border-radius: 10px; margin: 16px 0; }}
.chip, .type, .risk {{ display: inline-block; padding: 4px 9px; margin: 3px; border: 1px solid #8886; border-radius: 999px; font-size: .82rem; }}
.claim {{ border: 1px solid #8885; border-radius: 14px; padding: 18px; margin: 14px 0; }}
.claim-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
.claim h3 {{ font-size: 1rem; font-weight: 600; margin: 14px 3px; }}
dl {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 10px; }}
dl div {{ padding: 9px 11px; border-radius: 8px; background: #8881; }}
dt {{ font-size: .76rem; opacity: .65; }} dd {{ margin: 3px 0 0; overflow-wrap: anywhere; }}
details {{ margin-top: 12px; padding: 10px 12px; border-top: 1px solid #8884; }}
details p {{ overflow-wrap: anywhere; }}
.muted, small, .claim-id {{ opacity: .6; }} .claim-id {{ font-size: .72rem; margin-top: 10px; }}
.risk-high {{ border-color: #b44; }} .risk-medium {{ border-color: #a80; }}
.empty {{ text-align: center; padding: 60px 10px; }}
</style>
</head>
<body>
<header>
  <h1>ClaimLens · Verification Review</h1>
  <p>Only extracted factual claims that may need verification are shown. Original CV text, contact details, addresses and images are not intentionally displayed.</p>
  <div class="notice"><strong>Local preview.</strong> Opening this file does not perform network verification or upload CV data.</div>
  <div>{summary}</div>
</header>
{body}
</body>
</html>"""
    path.write_text(html, encoding="utf-8")


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
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([row.get(h, "") for h in CLAIM_HEADERS])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        letter = col[0].column_letter
        ws.column_dimensions[letter].width = min(
            max(12, max(len(str(c.value or "")) for c in col) + 2), 60
        )
    xlsx_path = out_dir / "claims.xlsx"
    wb.save(xlsx_path)
    _write_review_html(claims, out_dir / "claims_review.html")
    return json_path, xlsx_path, csv_path
