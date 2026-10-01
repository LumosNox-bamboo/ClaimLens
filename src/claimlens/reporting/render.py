from __future__ import annotations

import json
from html import escape

from .data import MATERIAL_TYPES, PUBLIC_TYPES, TYPE_LABELS, safe_url

LABELS = {
    "VERIFIED": "Verified",
    "PARTIALLY_VERIFIED": "Partially verified",
    "CONFLICT": "Conflict",
    "NOT_FOUND": "Not found",
    "NEEDS_REVIEW": "Needs review",
    "DOCUMENT_REQUIRED": "Document required",
}


def e(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return escape(str(value or ""), quote=True)


def link(url, label="Open source ↗"):
    url = safe_url(url)
    return (
        f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>'
        if url
        else '<span class="muted">Source link unavailable</span>'
    )


def shell(title, body, asset_prefix="", data=None):
    payload = ""
    if data is not None:
        encoded = (
            json.dumps(data, ensure_ascii=False)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029")
        )
        payload = f'<script id="report-data" type="application/json">{encoded}</script>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>{e(title)} · ClaimLens</title><link rel="stylesheet" href="{asset_prefix}assets/styles.css"><script src="{asset_prefix}assets/report.js" defer></script></head>
<body>{body}{payload}</body></html>'''


def badge(status):
    return f'<span class="badge {e(status)}">{e(LABELS.get(status, status))}</span>'


def mini_summary(items):
    return (
        '<div class="summary-grid">'
        + "".join(
            f"<div><span>{e(label)}</span><strong>{count}</strong></div>" for label, count in items
        )
        + "</div>"
    )


def evidence_card(v):
    strength = v.get("evidence_strength") or "—"
    matched = ", ".join(v.get("matched_fields") or [])
    conflicting = ", ".join(v.get("conflicting_fields") or [])
    details = f'<p class="field-note">Matched: {e(matched)}</p>' if matched else ""
    if conflicting:
        details += f'<p class="conflict-text">Conflicting: {e(conflicting)}</p>'
    return f'<div class="evidence strength-{e(strength)}"><strong>{e(strength)} · {e(v.get("source_name"))}</strong><small>{e(v.get("source_type"))}</small>{details}{link(v.get("url"))}<small>Accessed {e(v.get("accessed_at"))}</small></div>'


def claim_card(r):
    status = r["verification_status"]
    d = r["display"]
    flags = badge(status)
    if r["extraction_issue"]:
        flags += '<span class="badge extraction">Extraction issue</span>'
    if r["freshness_status"] == "CV_UPDATE_AVAILABLE":
        flags += '<span class="badge update">CV update available</span>'
    metrics = r.get("journal_metrics")
    if metrics and metrics.get("latest_jif") is not None:
        flags += f'<span class="badge metric">JIF {e(metrics["latest_jif"])} · {e(metrics["jif_year"])}</span>'
    fields = "".join(
        f"<div><dt>{e(k.replace('_', ' ').title())}</dt><dd>{link('https://doi.org/' + str(v), str(v)) if k == 'doi' else e(v)}</dd></div>"
        for k, v in d.items()
        if k != "title" and v
    )
    checks = "".join(
        f'<div class="{key}"><strong>{label}</strong><span>{e(", ".join(r.get(key) or []))}</span></div>'
        for key, label in [
            ("matched_fields", "Matched"),
            ("unverified_fields", "Unverified"),
            ("conflicting_fields", "Conflicting"),
        ]
        if r.get(key)
    )
    reason = (
        f'<p class="review-reason"><strong>{e(r["review_category"])}.</strong> Reason: {e(r["review_reason"])}</p>'
        if status == "NEEDS_REVIEW"
        else ""
    )
    if status == "NOT_FOUND":
        reason += "<p>No sufficient public evidence found.<br><small>This does not indicate that the claim is false.</small></p>"
    elif status == "DOCUMENT_REQUIRED":
        reason += '<p class="muted">Public-source verification is not appropriate or sufficient for this claim. Review submitted supporting documents if required.</p>'
    elif status == "CONFLICT":
        reason += (
            '<p class="conflict-text">Public evidence conflicts with the submitted claim on the following field(s): '
            + e(", ".join(r["conflicting_fields"] or []))
            + ".</p>"
        )
    evidence = sorted(r["evidence"], key=lambda x: x.get("evidence_strength") or "Z")
    sources = "".join(evidence_card(v) for v in evidence[:3])
    if len(evidence) > 3:
        sources += (
            "<details><summary>Show all evidence</summary>"
            + "".join(evidence_card(v) for v in evidence[3:])
            + "</details>"
        )
    evidence_html = (
        '<div class="evidence-grid">' + sources + "</div>"
        if evidence
        else '<p class="muted">No supporting public evidence attached.</p>'
    )
    original = (
        r["original_claim"].get("claim_text")
        or r["original_claim"].get("title")
        or r["original_claim"]
    )
    freshness = ""
    if r["freshness_status"] == "CV_UPDATE_AVAILABLE":
        public = next(
            (v.get("verified_metadata") for v in evidence if v.get("verified_metadata")), {}
        )
        freshness = f'<div class="freshness"><h4>CV update available</h4><dl><div><dt>Current CV</dt><dd>{e(original)}</dd></div><div><dt>Public record</dt><dd>{e(public)}</dd></div><div><dt>Suggested update</dt><dd>{e(r.get("suggested_cv_update"))}</dd></div></dl></div>'
    metric_detail = (
        '<p class="muted">Journal metric not independently retrieved.</p>'
        if r["claim_type"] == "publication" and (not metrics or metrics.get("latest_jif") is None)
        else ""
    )
    if metrics and metrics.get("latest_jif") is not None:
        metric_detail = f"<p>Journal Impact Factor {e(metrics['latest_jif'])} ({e(metrics['jif_year'])}. Source: {e(metrics['metric_source'])}. Source quality: {e(metrics['metric_source_quality'])}. {link(metrics['metric_source_url'])}</p>"
    audit = r["audit_summary"]
    return f'''<article class="claim {e(status)}" id="{e(r["claim_id"])}" data-status="{e(status)}"><div class="claim-top"><small>{e(TYPE_LABELS.get(r["claim_type"], r["claim_type"]))} · {e(r["claim_id"])}</small><div>{flags}</div></div>
<h3>{e(d["title"])}</h3><dl class="metadata">{fields}</dl>{reason}<div class="field-checks">{checks}</div>{evidence_html}{freshness}
<details class="claim-details"><summary>Show extracted claim and verification details</summary><p>{e(original)}</p><p>{e(r.get("verification_notes"))}</p>{metric_detail}<p>Freshness: {e(r.get("freshness_status"))}</p>
<p>Search attempts: {audit["search_attempt_count"]} · Sources checked: {e(", ".join(audit["sources_checked"]))}</p></details></article>'''


def candidate_page(c, anonymous=False):
    name = c.get("candidate_name") or c["candidate_id"]
    st = c["status_counts"]
    heading = f'<header class="page-header"><div><a class="back" href="../index.html">← All candidates</a><h1>{e(name)}</h1><p>{e(c["application_id"])} · {e(c["candidate_id"])}</p></div><span class="local-label">{"Anonymous report" if anonymous else "Local identity report"}</span></header>'
    if st["CONFLICT"]:
        heading += '<div class="conflict-banner">Public evidence conflicts with the submitted claim on one or more fields. Review the highlighted claims and their sources.</div>'
    if c["verification_result_missing"]:
        heading += '<div class="integrity-warning">DATA_INTEGRITY_WARNING: Verification result missing. No claim counts inferred.</div>'
    elif not c["claims"]:
        heading += '<p class="notice">This prepared candidate package contains no claims. No inference about the candidate is made.</p>'
    stats = mini_summary(
        [
            ("Public claims", c["public_claims"]),
            ("Verified", st["VERIFIED"]),
            ("Partially verified", st["PARTIALLY_VERIFIED"]),
            ("Not found", st["NOT_FOUND"]),
            ("Needs review", st["NEEDS_REVIEW"]),
            ("Material/document claims", c["material_claims"]),
            ("CV updates", c["cv_updates"]),
        ]
    )
    filters = '<div class="claim-toolbar"><label>Show <select id="claim-filter"><option value="all">All claims</option><option value="review">Claims needing review</option><option value="VERIFIED">Verified</option><option value="PARTIALLY_VERIFIED">Partial</option><option value="NEEDS_REVIEW">Needs review</option><option value="NOT_FOUND">Not found</option><option value="CONFLICT">Conflict</option></select></label><span class="muted">Public visibility is not a candidate quality measure.</span></div>'
    groups = [
        ("Publications", ("publication",)),
        ("Awards & Competitions", ("award", "competition")),
        ("Patents", ("patent",)),
        ("Conference Presentations", ("conference_presentation",)),
    ]
    body = ""
    for label, types in groups:
        rs = [r for r in c["claims"] if r["claim_type"] in types]
        body += (
            f'<section class="claim-section"><h2>{label} <span class="count">{len(rs)}</span></h2>'
            + (
                "".join(claim_card(r) for r in rs)
                if rs
                else '<p class="muted compact">No claims in this category.</p>'
            )
            + "</section>"
        )
    materials = [r for r in c["claims"] if r["claim_type"] in MATERIAL_TYPES]
    counts = " · ".join(
        f"{TYPE_LABELS[t]} × {c['claim_type_counts'][t]}"
        for t in MATERIAL_TYPES
        if c["claim_type_counts"][t]
    )
    body += (
        f'<details class="material-section"><summary>Material-based verification · Education & Qualifications ({len(materials)})</summary><p class="muted">{e(counts)}</p>'
        + "".join(claim_card(r) for r in materials)
        + "</details>"
    )
    legend = "<footer>A: Authoritative primary/structured source · B: Official institutional source · C: Credible secondary source · D: Weak/self-reported source.<p>NOT_FOUND, NEEDS_REVIEW and DOCUMENT_REQUIRED do not indicate a false claim. JIF is separate from verification.</p></footer>"
    return shell(name, "<main>" + heading + stats + filters + body + legend + "</main>", "../")


def dashboard_page(candidates, dashboard):
    d = dashboard
    header = '<header class="page-header"><div><h1>ClaimLens</h1><p>SCDSG 2026 · CV Claim Review</p></div><span class="local-label">Local review directory</span></header>'
    warnings = d["data_integrity_warnings"]
    integrity = ""
    if warnings:
        integrity = (
            '<div class="integrity-warning"><strong>DATA_INTEGRITY_WARNING</strong><details><summary>Show reconciliation warnings</summary>'
            + "".join(
                f"<p>{e(w['field'])}: expected {e(w['expected'])}; observed {e(w['observed'])}; difference {e(w['difference'])}</p>"
                for w in warnings
            )
            + "</details></div>"
        )
    stats = mini_summary(
        [
            ("Candidates", d["candidates_rendered"]),
            ("Claims", d["total_claims"]),
            ("Public-verification claims", d["public_claims"]),
            ("Material-based claims", d["material_claims"]),
            ("Needs review", d["verification_status_counts"]["NEEDS_REVIEW"]),
            ("CV updates available", d["CV_UPDATE_AVAILABLE"]),
        ]
    )
    overview = (
        '<section class="overview"><h2>Claim Type Overview</h2><div class="type-overview">'
        + "".join(
            f"<div><strong>{d['claim_type_counts'].get(t, 0)}</strong><span>{TYPE_LABELS[t]}</span></div>"
            for t in PUBLIC_TYPES
        )
        + '</div><p class="muted">'
        + " · ".join(f"{TYPE_LABELS[t]} {d['claim_type_counts'].get(t, 0)}" for t in MATERIAL_TYPES)
        + "</p></section>"
    )
    statuses = (
        '<div class="status-strip">'
        + "".join(
            f"{badge(s)} <strong>{n}</strong>"
            for s, n in d["verification_status_counts"].items()
            if s != "DOCUMENT_REQUIRED" and (s != "CONFLICT" or n)
        )
        + "</div>"
    )
    conflicts = (
        '<p class="muted">No substantive conflicts detected in this run.</p>'
        if not d["verification_status_counts"]["CONFLICT"]
        else '<button type="button" class="conflict-banner" data-filter="CONFLICT">Review public evidence conflicts</button>'
    )
    explanation = '<p class="scope-note">Counts describe claims and available evidence. NOT_FOUND and NEEDS_REVIEW do not indicate that a claim is false. Sorting supports review workflow and does not rank candidate quality.</p>'
    filters = [
        ("all", "All"),
        ("VERIFIED", "Has VERIFIED"),
        ("PARTIALLY_VERIFIED", "Has PARTIALLY_VERIFIED"),
        ("NOT_FOUND", "Has NOT_FOUND"),
        ("NEEDS_REVIEW", "Has NEEDS_REVIEW"),
        ("CONFLICT", "Has CONFLICT"),
        ("CV_UPDATE_AVAILABLE", "Has CV_UPDATE_AVAILABLE"),
        ("publication", "Has publication"),
        ("patent", "Has patent"),
        ("award", "Has award"),
        ("queue", "High-value review queue"),
    ]
    sorts = [
        ("application", "Application ID"),
        ("name", "Name"),
        ("claims", "Most claims"),
        ("review", "Most needs review"),
        ("evidence", "Most public evidence"),
        ("updates", "Most CV updates"),
    ]
    controls = (
        '<section><h2>Candidates</h2><div class="filters"><label>Search<input id="search" type="search" placeholder="Name, application ID or candidate ID"></label><label>Filter<select id="candidate-filter">'
        + "".join(f'<option value="{k}">{v}</option>' for k, v in filters)
        + '</select></label><label>Sort<select id="candidate-sort">'
        + "".join(f'<option value="{k}">{v}</option>' for k, v in sorts)
        + '</select></label><span id="visible-count" aria-live="polite"></span></div>'
    )
    columns = [
        "Application ID",
        "Name",
        "Candidate ID",
        "Publications",
        "Awards / Competitions",
        "Patents",
        "Conferences",
        "Verified",
        "Partial",
        "Not found",
        "Needs review",
        "CV updates",
        "Open report",
    ]
    rows = []
    compact = []
    queue = []
    for c in candidates:
        st, t = c["status_counts"], c["claim_type_counts"]
        values = [
            c["application_id"],
            c["candidate_name"] or "Mapping unavailable",
            c["candidate_id"],
            t["publication"],
            t["award"] + t["competition"],
            t["patent"],
            t["conference_presentation"],
            st["VERIFIED"],
            st["PARTIALLY_VERIFIED"],
            st["NOT_FOUND"],
            st["NEEDS_REVIEW"],
            c["cv_updates"],
        ]
        cells = "".join(f"<td>{e(v) if isinstance(v, str) else v}</td>" for v in values)
        rows.append(
            f'<tr>{cells}<td><a href="named/{e(c["candidate_id"])}.html">View</a> <a href="anonymous/{e(c["candidate_id"])}.html">Anonymous</a></td></tr>'
        )
        compact.append({k: v for k, v in c.items() if k != "claims"})
        for r in c["claims"]:
            if r["claim_type"] in PUBLIC_TYPES and r["verification_status"] in (
                "CONFLICT",
                "PARTIALLY_VERIFIED",
                "NEEDS_REVIEW",
                "NOT_FOUND",
            ):
                queue.append(
                    dict(
                        candidate_id=c["candidate_id"],
                        application_id=c["application_id"],
                        candidate_name=c["candidate_name"],
                        claim_id=r["claim_id"],
                        claim_type=r["claim_type"],
                        title=r["display"]["title"],
                        status=r["verification_status"],
                        review_reason=r["review_reason"],
                        review_category=r["review_category"],
                        review_priority=r["review_priority"],
                    )
                )
    table = (
        '<div class="table-scroll"><table class="candidate-table"><thead><tr>'
        + "".join(f"<th>{e(v)}</th>" for v in columns)
        + '</tr></thead><tbody id="candidate-rows">'
        + "".join(rows)
        + "</tbody></table></div></section>"
    )
    queue_html = (
        f'<section class="queue-section"><div class="section-heading"><h2>Review Queue</h2><button data-filter="queue">High-value claims needing review <strong>{d["high_value_review_queue_count"]}</strong></button></div><p class="muted">Claim-level workflow: conflicts, partial core fields, identity linkage, extraction issues, then not found. Material-based claims are excluded.</p><details><summary>Show public-claim review queue</summary><div class="filters"><label>Reason<select id="queue-category"><option value="all">All reasons</option>'
        + "".join(
            f"<option>{e(v)}</option>"
            for v in [
                "Identity linkage issue",
                "Extraction issue",
                "Source issue",
                "Metadata issue",
                "Other",
            ]
        )
        + '</select></label><span id="queue-count"></span></div><div class="table-scroll"><table><thead><tr><th>Application ID</th><th>Claim</th><th>Status</th><th>Reason</th><th>Open</th></tr></thead><tbody id="queue-rows"></tbody></table></div></details></section>'
    )
    footer = "<footer><strong>Local identity information.</strong> Named reports and workbook must remain local. Anonymous outputs remove the name mapping but still need review before sharing.<p>A: Authoritative primary/structured · B: Official institutional · C: Credible secondary · D: Weak/self-reported.</p></footer>"
    return shell(
        "Batch review",
        "<main>"
        + header
        + integrity
        + stats
        + overview
        + statuses
        + conflicts
        + explanation
        + controls
        + table
        + queue_html
        + footer
        + "</main>",
        data=dict(
            candidates=compact,
            queue=sorted(
                queue, key=lambda r: (r["review_priority"], r["application_id"], r["claim_id"])
            ),
        ),
    )
