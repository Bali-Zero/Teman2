---
date: 2026-10-08
domain: visa
client_case: none — scheduled organ run, source-ledger attestation
sources:
  - research/visa/2026-10-08-organ-reattest-seq27/ (read ledger: receipts, judgements, saved visible text)
  - apps/backend-rag/backend/scripts/visa_engine/portal_read_receipt.py
  - apps/backend-rag/backend/scripts/visa_engine/portal_judge.py
  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_generic.py
adversarial_review: seq27-adversary (independent read-only check, PASS) + council codex-gpt-5.6-sol PASS + kimi-code/k3 PASS — recorded in evidence/2026-10/agent-air-m5-backend-rag-visa-seq27-land-bd6772fa/
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

Pending. The session that signs this candidate reviews the judge verdicts and reads every
`changed` page itself, then replaces `pending-session` in the frontmatter with the reviewer.
