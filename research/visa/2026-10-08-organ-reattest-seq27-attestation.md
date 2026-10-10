---
date: 2026-10-08
domain: visa
client_case: none — scheduled organ run, source-ledger attestation
sources:
  - research/visa/2026-10-08-organ-reattest-seq27/ (read ledger: receipts, judgements, saved visible text)
  - apps/backend-rag/backend/scripts/visa_engine/portal_read_receipt.py
  - apps/backend-rag/backend/scripts/visa_engine/portal_judge.py
  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_generic.py
adversarial_review: codex
---

# Organ re-attestation 2026-10-08 — candidate seq-27 (unsigned)

The organ read the OFFICIAL_PORTAL pages of the signed seq-26 pack as reader `organ-sonnet-20261008`
(judge `claude`) and folded `rulepack-prod-027.source.json` from that ledger. Nothing here is
signed or active. `verified_at` of the candidate is the earliest successful read in the ledger.

## Attested reads used as the fingerprint baseline

- `153beca1`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:34:11Z
- `2d090f3a`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:34:12Z
- `38242587`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:09Z
- `38a6cb08`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:13Z
- `3da72c7b`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:11Z
- `40523028`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:33:53Z
- `50457cd0`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:33:54Z
- `570f2bc4`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:33:52Z
- `5e64ec6b`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:09Z
- `86880290`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:34:10Z
- `950a9f63`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:33:51Z
- `bc309fa9`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:11Z
- `ca5a2ce8`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:34:13Z
- `cb1b7182`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:10Z
- `d3ad622e`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:08Z
- `dcf08e19`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:35:12Z
- `ecd22722`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:33:54Z
- `f9306203`: 2026-10-07-freshness-restamp-seq25@2026-10-07T13:34:10Z

## Baseline disagreements

- none

## Adversarial review

Done by the signing session on 2026-10-10, three independent seats, none of them the organ or
the build lane:

- **seq27-adversary** (read-only check): the fingerprint is the SHA-256 of the page's whole
  visible text (`portal_read_receipt.py:127-128`) — changing one fee digit or "1 tahun atau 2
  tahun" → "1 tahun" changes it; the baseline is one hop back, the 2026-10-07 seq-25 read judged
  by three readers with quoted sentences (8 `changed`, accepted one by one in `disposition.json`);
  a live re-read on 2026-10-10 with the organ's own fetch/extract gave 18/18 HTTP 200, equal
  fingerprint, key phrase present; every product and rule claim is still supported by the saved
  text. PASS.
- **codex** (codex-gpt-5.6-sol, council): 41 leaf differences = identity + 18×2 stamps; Ed25519
  OK on seq-26 and seq-27; the tests reject a changed rule, a wrong chain, a missing receipt and
  a false fingerprint judgement. PASS.
- **kimi** (kimi-code/k3, council): bundle verifies under the production key and chains to
  seq-26; 18/18 receipts and judgements hold; the CSRF-token regex matches nothing in the 18
  texts, so the hash covers the whole text. PASS.

Residual, accepted: the fingerprint ignores a changed 40-character alphanumeric token (none of
these pages carries one that matters). Record:
`evidence/2026-10/agent-air-m5-backend-rag-visa-seq27-land-bd6772fa/` (pack dissent + journal).
