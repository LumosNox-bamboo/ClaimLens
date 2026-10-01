# ClaimLens

**Privacy-first, local-first CV and résumé claim verification.**

> **Your original CVs stay on your machine.** ClaimLens P0 parses and minimizes CV data locally. It makes no network requests, calls no LLM/API, sends no telemetry, and does not upload CVs or extracted text.

ClaimLens turns Chinese, English, and mixed-language CV/résumé documents into reviewable factual claims while creating an explicit privacy boundary before any future online verification. It is intended for recruitment, academic review, talent assessment, and similar workflows where specific factual claims need evidence.

**ClaimLens does not determine whether a person is “honest” or “dishonest”. It verifies specific factual claims against available evidence.**

**Absence of online evidence is not evidence that a claim is false.**

## What it does

P0 supports local text extraction from text-based PDF, DOCX, and TXT; bilingual direct-PII detection and redaction; keyed pseudonymous candidate IDs; structured claim extraction; XLSX/JSON/CSV export; and a human Privacy Review artifact that is unapproved by default. Supported claim categories are publications, awards, patents, competitions, certifications, education, and professional qualifications.

```text
CV / PDF / DOCX
        │
        ▼
Local text extraction
        │
        ▼
Local PII detection ──► local redaction / pseudonymization
        │
        ▼
Structured claim extraction
        │
        ▼
PRIVACY REVIEW  ◄──── exact outbound fields + reason
        │              (network boundary; approval required)
        ▼
Future verification providers
        │
        ▼
Evidence + verification report
```

## Privacy model

ClaimLens has three privacy modes. `verification` is the default: direct PII unrelated to factual verification is removed while claim-relevant facts such as publication titles, institutions, journals, award organizations, and patent identifiers can remain. `strict` applies maximum supported direct-identifier removal before data leaves the local environment. `custom` lets the user choose detected PII categories to remove or keep.

Detected categories currently include labelled Chinese/English names, dates of birth, age, phone numbers, email, postal/home addresses, Chinese ID patterns, labelled passport and driver's-license identifiers, WeChat, WhatsApp, Telegram, QQ, labelled social handles, personal URLs, emergency contacts, and referee/reference contact lines. ClaimLens does **not** indiscriminately remove schools, employers, research institutions, publication authors, journals, or awarding bodies because they may be necessary to verify a claim.

**Pseudonymized data is not necessarily anonymous.** A paper title, rare award, institution, patent, or combination of fields may re-identify a person even after names and contact details are removed. PII detection is best-effort and must not be treated as an anonymization guarantee. Human review remains required before external disclosure.

Photographs/avatars embedded in PDF/DOCX are not exported by the P0 text pipeline, but P0 does not yet perform reliable image detection/removal from source documents. Treat source files as containing images and never send them to a verifier.

## Installation

ClaimLens requires Python 3.10+.

```bash
git clone https://github.com/LumosNox-bamboo/ClaimLens.git
cd ClaimLens
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

For development, install `pip install -e ".[dev]"`.

## Quick start

Put CVs in a local directory that is outside Git or named `resumes/` (gitignored), then run:

```bash
claimlens extract ./resumes --out ./review
claimlens review ./review
```

ClaimLens creates a random local HMAC salt at `.claimlens/project.salt`; `.claimlens/` is gitignored. Back this secret up securely if stable candidate IDs matter. Never commit, log, email, or share the salt. Candidate IDs look like `C-7F2A91` and are derived from file content with HMAC-SHA256, not a real name.

To create local redacted text for inspection:

```bash
claimlens redact ./resumes --out ./review --privacy verification
claimlens redact ./resumes --out ./review-strict --privacy strict
claimlens redact ./resumes --out ./review-custom --privacy custom --remove email --remove phone
```

The CLI intentionally logs pseudonymous IDs rather than source filenames. Output directories and candidate XLSX files are ignored by the repository defaults.

## Privacy Review and network boundary

`claimlens extract` creates `privacy_review.json`. For every claim it shows the minimum fields proposed for a future public-source query and why those fields would leave the machine. Every item starts with `approved: false`.

```bash
claimlens review ./review
claimlens verify ./review
```

`verify` refuses to cross the verification boundary until every outbound item is explicitly approved. In P0, no network providers are enabled even after approval, so the command still performs no network access. Future providers must implement the same declaration/approval contract. Raw CVs and full extracted text are never provider inputs.

## Structured claims

Exports include `candidate_id`, `claim_id`, `claim_type`, `claim_text`, `title`, `year`, `organization`, `journal`, `doi`, `patent_number`, `award_name`, `authors`, `verification_query`, `privacy_risk`, and a non-identifying `source_file` type. P0 extraction is deliberately transparent and rule-based; ambiguous claims should be corrected during human review rather than silently guessed by an external model.

## Verification philosophy and architecture

Verification is evidence-based and claim-specific. The evidence model reserves `VERIFIED`, `PARTIALLY_VERIFIED`, `CONFLICT`, `NOT_FOUND`, and `NEEDS_REVIEW`; it never maps `NOT_FOUND` to false. Each future check should record source, evidence URL, retrieval date, matching fields, conflicting fields, evidence strength, and notes.

Providers implement a small interface that declares outbound fields before `verify()` can be called. Planned source priority is: DOI/Crossref, PubMed, ORCID and official publisher pages for publications; official patent databases for patents; official awarding-body/winner pages and institutional announcements for awards/competitions; and official certification authorities for credentials. No provider is silently enabled.

## Supported languages and formats

Chinese, English, and mixed Chinese/English text are supported by the P0 rules. Formats are text-based PDF, DOCX, and TXT. Scanned/image-only PDF is detected when no embedded text is available and fails with an explicit OCR-not-enabled message; an OCR parser interface can be added later without making cloud OCR the default.

## Development and testing

All test CV content is synthetic. Do not contribute real résumés or candidate data.

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q
```

GitHub Actions runs lint and tests on Python 3.10–3.13.

## Limitations

P0 uses deterministic patterns rather than a full local multilingual NER model, so unlabeled names, unusual addresses/IDs, and free-form identifying prose can be missed. Claim extraction favors explainability over recall and does not yet parse every field into journal/organization/authors. Source-document images are not scrubbed. OCR is not implemented. Verification providers and evidence reports are architecture-only in P0. These constraints are reasons for the mandatory Privacy Review, not reasons to assume remaining data is safe.

## Roadmap

P1 adds opt-in DOI/Crossref verification, evidence persistence, and a verification report while preserving the approval gate. P2 adds ORCID/PubMed, official patent sources, award/competition and certification providers. P3 may add a localhost GUI while keeping raw documents and privacy review local-first. Optional local NER and local OCR are candidates for earlier hardening.

## Security and responsible use

Use ClaimLens for objective, relevant claims that a candidate has provided for evaluation. Do not use it to infer sensitive traits, investigate unrelated private life, or automate consequential decisions without human review. Keep raw CVs, derived candidate data, review files, salts, and secrets out of source control. See `SECURITY.md`.

## Contributing

See `CONTRIBUTING.md`. Contributions should preserve privacy-safe defaults, make network behavior explicit, and use only synthetic fixtures/tests.

## License

Apache License 2.0. Apache-2.0 is used because it is permissive for academic and commercial adoption while also providing an explicit patent grant and patent-termination terms, which are useful for a reusable verification toolkit.
