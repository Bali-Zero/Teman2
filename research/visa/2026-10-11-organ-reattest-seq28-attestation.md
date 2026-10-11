---
date: 2026-10-11
domain: visa
client_case: none — scheduled organ run, source-ledger attestation
sources:
  - research/visa/2026-10-11-organ-reattest-seq28/ (read ledger: receipts, judgements, saved visible text)
  - apps/backend-rag/backend/scripts/visa_engine/portal_read_receipt.py
  - apps/backend-rag/backend/scripts/visa_engine/portal_judge.py
  - apps/backend-rag/backend/scripts/visa_engine/fold_pack_generic.py
adversarial_review: codex
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

Done by the signing session `nuzantara-57` (M5) on 2026-10-12, plus an independent read-only
adversary seat that is neither the organ nor the build lane. The candidate that the organ folded
(pure re-stamp, JCS digest `6db76810d95a`) was reproduced byte for byte by the generic fold in the
seq-28 PR; the signed pack adds the four owner-decided edits on top of it.

- **W141 check (independent seat, read-only):** the ledger holds 17 rows with `judge: fingerprint`
  and 1 model-judged row (`3da72c7b`, the Bridging page, no `judge` key). 18/18 fingerprints
  recomputed from the saved texts equal the receipt's `visible_text_sha256`. A live re-read with the
  organ's own `portal_read_receipt.py` gave 18/18 HTTP 200, live fingerprint equal to the ledger's,
  key phrase present, saved text byte-equal. Chain for the 17 fingerprint rows: the seq-28 read
  equals the receipt bound by the seq-27 judgement (one hop back, the attested read of
  2026-10-08), and those rows were themselves `judge: fingerprint` over the 2026-10-07 reads that
  three readers judged with quoted sentences (two fingerprint hops back to a reader-judged read).
  No `changed` verdict anywhere, so no `disposition.json` is needed and none exists.
- **Bridging page `3da72c7b` (the one model-judged row):** its fingerprint moved (4483 to 4467
  characters). The independent seat diffed it against the attested seq-27 text and found only the
  latest-news sidebar changed (three headlines dated 2 Oct became three dated 11 Oct 2026). The
  signing session read the page itself: "Masa berlaku Izin Tinggal Peralihan yakni 60 hari dan
  hanya berlaku secara onshore" is present, which is exactly the pack's `BRIDGING` `FIXED_DAYS 60`
  with no extension. Verdict `none`, confirmed.
- **Independent adversary (persona check on the folded source):** no blocking defect; E33G 59,999
  excluded and 60,000 admitted with unknown income asking for input; AGE_BELOW_55 now only under
  RETIREMENT; E33E quoted at 45,000,000 on the 5-year key.
- **Council:** codex `gpt-5.6-sol` and kimi `k3`, both `SIGN`, recorded in the evidence journal.

No `changed` verdict, no disposition needed. Record:
`evidence/2026-10/agent-mini-pro2-backend-rag-vo-seq28c-fold-1011-c669824d/` (pack + journal).
