---
adversarial_review: gemini-4-argon-high
---

# B05 reproducible input bundle

The default historical mode reads versioned fixtures and the committed B06 metadata matrix. It requires no Git history or ignored agent receipts. Original digest values and generated operation-contracts JSON/CSV remain unchanged; the seven source snapshots preserve the AST evidence and line numbers at base 8061c88e0c43dd42e735fd012f9ed072df3ef3d6.

Run `python3 b05_contracts_validator.py --validate` from `research/operations/udb-wave8/B05`. To inspect current sources separately, run `python3 b05_contracts_validator.py --mode current --generate --validate --out-dir /path/to/output`. The latter writes only `current-source-observation.json`, containing static hashes and AST observations. Current contracts are UNASSESSED and the active denominator remains UNKNOWN. Neither mode proves production deployment or operational closure.

The bundle contains the original three DUX aggregate outputs, four metadata-only receipts and seven source snapshots. MANIFEST.json records their original digests. The already committed B06 matrix has the same 6029 identities and 33 census buckets; with the one recorded addition the historical union is 6030. No client rows were recovered or included. The original 23 historical contracts remain incomplete (0 complete).

## Adversarial review

The S3 cross-family Gemini review returned PASS (result SHA-256 `3331dd48f1a7e1bba9d2c5d5c93c547c750141cd5b77d71df6c8fe0ea471ff75`). Independent Astra reviews verified the historical pins, clean-checkout behavior, and metadata-only scope. A documentation path correction and digest-comment correction were separately verified. Runtime contracts remain UNASSESSED, the active denominator remains UNKNOWN, and production activation is not admitted.
