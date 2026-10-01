# Offline review reports

Run `claimlens report BATCH_DIRECTORY --xlsx-node /path/to/node --xlsx-modules /path/to/node_modules`.
The Node runtime must provide `@oai/artifact-tool`; Python dependencies are already listed in pyproject.toml.
The generator reads local verification JSON, audit logs, batch_summary.json and candidate_map.xlsx, without parsing CVs or making network calls. Open the resulting `03_REPORTS/index.html` directly in a browser. No web server is needed.

Identity joins use exact candidate_id. Duplicate mappings retain the verification record, omit the ambiguous name, and produce integrity warnings. Missing verification records produce visible candidate placeholders. Counts are recalculated from claim records and compared with the saved batch summary; discrepancies retain expected, observed and difference. Input SHA-256 fingerprints are checked before and after generation.

The homepage review queue includes public claim types with CONFLICT, PARTIALLY_VERIFIED, NEEDS_REVIEW or NOT_FOUND. Workbook Review Queue includes all claims with those statuses. DOCUMENT_REQUIRED appears separately in Material Claims. Claim review priority is conflict, partial, identity linkage review, other review, then not found. These are workflow counts and priorities, without candidate scores.

Named output includes the local identity mapping. Anonymous output removes mapping names and local-only metadata, but retains public claims and application IDs. Use `--omit-application-id` to suppress those IDs. See the generated README_PRIVACY.txt before sharing. All real report bundles are ignored by Git. Tests and workbook previews must use synthetic data only.
