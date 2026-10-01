# ClaimLens

**Privacy-first, local-first CV and résumé claim verification.**

> **Your original CVs stay on your machine.** ClaimLens P0 parses and minimizes CV data locally. It makes no network requests, calls no LLM/API, sends no telemetry, and does not upload CVs or extracted text.

ClaimLens turns Chinese, English, and mixed-language CV/résumé documents into reviewable factual claims while creating an explicit privacy boundary before any future online verification. It is intended for recruitment, academic review, talent assessment, and similar workflows where specific factual claims need evidence.

**ClaimLens does not determine whether a person is “honest” or “dishonest”. It verifies specific factual claims against available evidence.**

**Absence of online evidence is not evidence that a claim is false.**

## What it does

P0 supports local text extraction from text-based PDF, DOCX, and TXT; bilingual direct-PII detection and redaction; keyed pseudonymous candidate IDs; structured claim extraction; XLSX/JSON/CSV export; a local HTML verification-review page; and a human Privacy Review artifact that is unapproved by default. Supported claim categories are publications, awards, patents, competitions, certifications, education, and professional qualifications.

## Installation

ClaimLens requires Python 3.10+.

```bash
git clone https://github.com/LumosNox-bamboo/ClaimLens.git
cd ClaimLens
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Try one CV locally

Put one text-based PDF, DOCX, or TXT CV in the gitignored `resumes/` directory, for example `resumes/test.pdf`, then run:

```bash
claimlens extract ./resumes/test.pdf --out ./review
```

Open `review/claims_review.html` in your browser. This page is a local, structured review surface: it intentionally shows only extracted factual claims that may need verification, grouped under a pseudonymous candidate ID. It does not intentionally display the original CV, contact details, addresses, or embedded images. Each card shows the claim category, minimized claim text, fields already parsed (such as year/DOI/patent number), privacy risk, and a collapsed preview of the future verification query. Opening the HTML performs no network request.

The same run also creates `claims.xlsx`, `claims.json`, `claims.csv`, `privacy_manifest.json`, and `privacy_review.json`. These are local derived candidate data and are gitignored.

## Privacy model

Privacy modes are `verification` (default), `strict`, and `custom`. The default removes supported direct PII unrelated to factual verification while retaining claim-relevant facts such as publication titles, institutions, journals, award organizations, and patent identifiers.

Detected categories currently include labelled Chinese/English names, dates of birth, age, phone numbers, email, postal/home addresses, Chinese ID patterns, labelled passport and driver's-license identifiers, WeChat, WhatsApp, Telegram, QQ, labelled social handles, personal URLs, emergency contacts, and referee/reference contact lines.

**Pseudonymized data is not necessarily anonymous.** A paper title, rare award, institution, patent, or combination of fields may re-identify a person. PII detection is best-effort; human review remains required before external disclosure.

Photographs/avatars embedded in PDF/DOCX are not exported by the P0 text pipeline. P0 does not scrub the source document itself, so never send the original source file to a verifier.

## CLI

```bash
claimlens extract ./resumes --out ./review
claimlens redact ./resumes --out ./review --privacy verification
claimlens review ./review
claimlens verify ./review
```

Candidate IDs look like `C-7F2A91` and are derived from file content with HMAC-SHA256 using a random local salt at `.claimlens/project.salt`. The CLI logs pseudonymous IDs rather than source filenames.

## Privacy Review and network boundary

`claimlens extract` creates `privacy_review.json`. Every future outbound verification item starts with `approved: false`. `claimlens verify` refuses to cross the verification boundary until approval. In P0 no network provider is enabled even after approval, so all current commands remain local.

## Structured claims

Exports include `candidate_id`, `claim_id`, `claim_type`, `claim_text`, `title`, `year`, `organization`, `journal`, `doi`, `patent_number`, `award_name`, `authors`, `verification_query`, `privacy_risk`, and a non-identifying source-file type. P0 extraction is deliberately transparent and rule-based; ambiguous claims should be corrected during human review rather than silently guessed by an external model.

## Verification philosophy

The evidence model reserves `VERIFIED`, `PARTIALLY_VERIFIED`, `CONFLICT`, `NOT_FOUND`, and `NEEDS_REVIEW`. It never maps `NOT_FOUND` to false. Future checks should record source, evidence URL, retrieval date, matching fields, conflicting fields, evidence strength, and notes.

## Supported languages and formats

Chinese, English, and mixed Chinese/English text are supported by the P0 rules. Formats are text-based PDF, DOCX, and TXT. Scanned/image-only PDFs fail with an explicit OCR-not-enabled message.

## Development and testing

All test CV content is synthetic. Do not contribute real résumés or candidate data.

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q
```

GitHub Actions runs lint and tests on Python 3.10–3.13.

## Limitations

P0 uses deterministic patterns rather than a full local multilingual NER model, so unlabeled names, unusual addresses/IDs, and free-form identifying prose can be missed. Claim extraction favors explainability over recall and does not yet parse every field into journal/organization/authors. The local HTML therefore represents extracted candidates for human review, not a guarantee that every relevant claim was found. Source-document images are not scrubbed. OCR and online verification are not implemented.

## Roadmap

P1 adds opt-in DOI/Crossref verification, evidence persistence, and a verification report while preserving the approval gate. P2 adds ORCID/PubMed, official patent sources, award/competition and certification providers. P3 may add a localhost GUI while keeping raw documents and privacy review local-first.

## Security and responsible use

Use ClaimLens for objective, relevant claims that a candidate has provided for evaluation. Do not use it to infer sensitive traits, investigate unrelated private life, or automate consequential decisions without human review. Keep raw CVs, derived candidate data, review files, salts, and secrets out of source control. See `SECURITY.md`.

## Contributing

See `CONTRIBUTING.md`. Contributions should preserve privacy-safe defaults, make network behavior explicit, and use only synthetic fixtures/tests.

## License

Apache License 2.0. Apache-2.0 is permissive for academic and commercial adoption and includes an explicit patent grant and patent-termination terms.
