# Public prepared-claim verification

Run only on an existing pseudonymous `01_CODEX_READY` package:

```sh
claimlens verify-batch PATH/01_CODEX_READY --out PATH/02_VERIFICATION_RESULTS --pilot
claimlens verify-batch PATH/01_CODEX_READY --out PATH/02_VERIFICATION_RESULTS
```

The pilot completes two candidates. Review the schema, provenance and decision logic locally before the full run. Valid completed candidate records are skipped. Atomic per-claim checkpoints retain results and audits; input fingerprints invalidate stale checkpoints. A candidate failure is recorded and the batch continues. No raw résumé, identity mapping, HTML report, candidate score or ranking is used.

Public providers send DOI, cleaned publication title, patent number or a bounded event title as needed. Crossref and PubMed metadata precede public web discovery; publisher citation metadata is read on the original page. Search snippets are leads rather than proof. Author lists in citations are excluded from title queries. A generic or truncated title fragment cannot independently identify a work. Source failures and limited public visibility do not establish a conflict. `NOT_FOUND` never means false. Missing individual education, qualification or certificate records require documents.

Each candidate has a verification JSON and an audit JSON. Audit entries preserve actual queries, source URLs, rejection reasons and decision rationale, without source-page full text. Publication freshness is independent of verification, and JIF is independent of both. The latest completed JIF data year is sought explicitly; missing or undated JIF is null. Five-year JIF and CiteScore are never substituted. Reviewed official journal-level records can be applied with `enrichment.enrich_metrics`; it checks year and source provenance, updates checkpoints and audits, and does not repeat candidate searches or change factual verification status.

The output is validated with `verification.schema.json` plus semantic checks for evidence strength, conflicts, freshness and claim coverage. Synthetic tests exercise resume, interruption, corruption, status logic, missing JIF, malformed providers and candidate failure isolation. All actual candidate packages and derived results must remain local-only.
