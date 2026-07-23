---
date: 2026-07-23
domain: visa
vertical: E33 Second Home
adversarial_review: pending
---

# E33 letter-response tracker

Six official letters sent **2026-07-21** requesting written confirmations on the
Second Home Visa (E33) operational details. Answers pending. When a reply
arrives: update the fact in `e33-fact-registry.json` (status → confirmed/disputed,
confidence → JELAS/BERSYARAT, source → the reply), then propagate to the platform
surfaces in the last column.

Letter numbering: `NNN/BZ-EXT/E33/VII/2026`.

- **001** — Bank Mandiri
- **002** — Bank BRI
- **003** — Bank BNI
- **004** — Bank BTN
- **005** — Bank BSI (sharia)
- **006** — Ditjen Imigrasi

> Question numbers below follow each letter's internal question order as logged
> at send time. Reconcile against the sent PDFs before quoting a reply
> (the PDFs live outside the repo).

## Platform surfaces legend

| Surface | Where |
|---|---|
| **registry** | `research/secondhome/e33-fact-registry.json` (this directory) |
| **catalogue** | `apps/backend-rag/backend/services/visa_check/catalogue.py` |
| **pricing** | `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json` (owner-gated) |
| **content** | `apps/backend-rag/data/curated_qa/*.jsonl` + operator-gated re-harvest (`scripts/curated_qa_harvest.py`) |
| **prompts** | `apps/backend-rag/backend/prompts/zantara_core.py` (only via its own edit rules) |

## Letter 006 — Ditjen Imigrasi

| Q | Question topic | Registry fact id | Status | Apply answer to |
|---|---|---|---|---|
| Q1 | Proof-of-deposit format accepted | `bank_proof_format` | pending | registry → content, catalogue notes |
| Q2 | Split deposit across banks accepted | `split_deposit_accepted` | pending | registry → content, prompts |
| Q3 | PNBP 5y written confirmation + refundability | `pnbp_5y_amount_and_refundability` | pending | registry → pricing, content |
| Q4 | 90-day entry window + force majeure | `entry_window_90d_and_force_majeure` | pending | registry → content |
| Q5 | Annual maintenance proof + FX grace | `annual_maintenance_proof_and_fx_grace` | pending | registry → content, catalogue notes |
| Q6 | Dependent codes (E31B/E31E/E31H/E31J) + concurrent filing | `dependent_codes_confirmation` | pending | registry → content, catalogue (E31 meta) |
| Q7 | ITAP after 3 years — criteria | `itap_after_3y_criteria` | pending | registry → content, prompts, marketing (owner-gated) |
| Q8 | Processing time 4 working days | `processing_time_4wd` | pending | registry → content, catalogue notes |

## Letters 001–005 — state banks (Mandiri / BRI / BNI / BTN / BSI)

Same question set per bank; BSI (005) carries one extra question (Q1).

| Letter | Q | Question topic | Registry fact id | Status | Apply answer to |
|---|---|---|---|---|---|
| 005 | Q1 | BSI sharia placement qualifies as state-bank deposit | `bsi_sharia_accepted` | pending | registry → content, catalogue, pricing (BSI conditional offer, owner-gated) |
| 001–005 | Q1* | KYC / onboarding of non-resident applicant | `bank_kyc_nonresident` | pending | registry → content, client journey |
| 001–005 | Q2 | Confirmation-letter format + issuance timing | `bank_confirmation_letter_format_and_timing` | pending | registry → content, ops SOP |
| 001–005 | Q3 | Split-placement operations (bank side) | `bank_split_placement_operations` | pending | registry → content |
| 001–005 | Q4 | USD deposit rates + LPS cap confirmation | `usd_deposit_rates_and_lps_cap_confirmation` | pending | registry → content (rates are DINAMIS — never hardcode) |
| 001–005 | Q5 | Documents for annual proof | `bank_annual_proof_documents` | pending | registry → content, ops SOP |
| 001–005 | Q6 | Fund-release process at permit end/cancellation | `fund_release_process` | pending | registry → content |
| 001–005 | Q7 | Named liaison contact | `bank_liaison_contact` | pending | registry → ops SOP (PII boundary: contact details stay internal) |

\* For letter 005 the bank-common questions shift by one (Q2–Q8) because Q1 is
the sharia-equivalence question — verify against the sent PDF.

## Reply-intake procedure (per reply)

1. File the reply under `research/secondhome/replies/` (scan + transcription).
2. Update the fact(s) in `e33-fact-registry.json`: status, confidence, source
   (reply reference + date), notes.
3. Propagate to surfaces per the tables above. Content changes go through the
   curated_qa corrections flow (new round in
   `research/curated-qa-corrections-*/`) — never edit prod Qdrant/Redis directly.
4. Pricing/marketing changes are owner-gated — surface them, don't apply them.
5. Adversarial-review the interpretation of any reply that contradicts a
   currently-confirmed fact (R1 gate, generator≠grader).
