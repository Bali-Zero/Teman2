---
date: 2026-10-11
domain: visa
client_case: none — scheduled organ run, source-ledger attestation
sources:
  - research/visa/2026-10-11-organ-reattest-seq28/ (read ledger: receipts, judgements, saved visible text)
  - apps/backend-rag/backend/scripts/visa_engine/portal_read_receipt.py
  - apps/backend-rag/backend/scripts/visa_engine/portal_judge.py
  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_generic.py
adversarial_review: pending-session
---

# Organ re-attestation 2026-10-11 — candidate seq-28 (unsigned)

The organ read the OFFICIAL_PORTAL pages of the signed seq-27 pack as reader `organ-sonnet-20261011`
(judge `claude`) and folded `rulepack-prod-028.source.json` from that ledger. Nothing here is
signed or active. `verified_at` of the candidate is the earliest successful read in the ledger.

## Attested reads used as the fingerprint baseline

- `153beca1`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:29Z
- `2d090f3a`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:29Z
- `38242587`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:32Z
- `38a6cb08`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:33Z
- `3da72c7b`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:23Z
- `40523028`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:25Z
- `50457cd0`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:26Z
- `570f2bc4`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:25Z
- `5e64ec6b`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:31Z
- `86880290`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:28Z
- `950a9f63`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:24Z
- `bc309fa9`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:22Z
- `ca5a2ce8`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:30Z
- `cb1b7182`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:32Z
- `d3ad622e`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:30Z
- `dcf08e19`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:23Z
- `ecd22722`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:27Z
- `f9306203`: 2026-10-08-organ-reattest-seq27@2026-10-08T13:21:27Z

## Baseline disagreements

- none

## Adversarial review

Pending. The session that signs this candidate reviews the judge verdicts and reads every
`changed` page itself, then replaces `pending-session` in the frontmatter with the reviewer.
