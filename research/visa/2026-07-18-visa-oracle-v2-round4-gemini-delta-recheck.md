---
date: 2026-07-18
domain: visa
client_case: none (Visa Oracle v2 engine — MANDATO S3 regulatory delta re-check)
sources:
  - https://imigrasi.go.id (Kepmen M.IP-08.GR.01.01/2025 reclassification)
  - https://kemenimipas.go.id (Permen Imipas 10/2026 BVK; Permen Imipas 5/2025 penjamin)
  - https://kompas.com (BVK +6 states coverage)
lane: gemini-3.1-pro-high via agy v1.1.3 (15m, 2026-07-18)
status: LEADS — two discrepancies vs round-2 baseline flagged UNRESOLVED below; W90 discipline applies (no engine/content claim ships without NB ground-truth + primary-source date check)
---

# Visa Oracle v2 — Round 4: Gemini regulatory delta re-check (MANDATO S3, point 5)

Re-verification of the round-2 regulatory delta baseline before FASE 2 content authoring and
RulePack `valid_from`/`valid_to` design. Lane output preserved verbatim below; orchestrator
annotations in the "Discrepancies" section.

## ⚠️ Discrepancies vs round-2 baseline (UNRESOLVED — arbitrate at FASE 2 grounding)

1. **BVK +6 list, "MO" ambiguity**: round-2 recorded the 6 added states as TR/BR/PE/KZ/MO/BY.
   This lane resolves MO = **Macau** and explicitly marks **Morocco as FALSE** [kompas.com].
   ISO note: MO = Macau, MA = Morocco — the round-2 two-letter shorthand was ambiguous at birth.
   Action: NB-2/primary-source arbitration before any content or rule uses the list. Until then
   neither reading ships.
2. **Kepmen M.IP-08/2025 effective date**: this lane says **2025-06-02**; the round-2 baseline
   (and the visaoracle corner LIVE STATE) recorded **2026-06-02**. One year apart, load-bearing
   for the `valid_from` of the entire 110-index reclassification layer. A "Tahun 2025" Kepmen
   effective mid-2025 is plausible; a 2026 effectiveness would imply a long vacatio legis.
   Action: resolve against the Kepmen text itself (JDIH/annex) before seeding RulePack dates.
   Until resolved, the catalog bundle metadata must carry the date as UNVERIFIED.

## Lane output (verbatim)

### 1. Kepmen M.IP-08/2025 (Visa Index Reclassification)
- **Effective Date:** June 2, 2025. [VERIFIED https://imigrasi.go.id]
- **Index Count Change:** Confirmed reduction from 133 to 110 indexes. [VERIFIED https://imigrasi.go.id]
- **Former B211* Indexes Mapping:** B211A, B211B, and B211C codes are DEAD. Under the new
  classification system, standard single-entry visitor visas are generally replaced by the
  **C-series** indexes (Visa Kunjungan). For visa-exempt nationalities, it maps to **A1**, and for
  Visa on Arrival (VoA), it maps to **B1**. [VERIFIED https://imigrasi.go.id]
- *Note:* The exact 1-to-1 sub-index mapping for every B211 variant into the C-series is
  [UNVERIFIED] without the full annex of the document, but the structural shift to A1/B1/C-series
  is confirmed.

### 2. Permen Imipas No. 10/2026 (Bebas Visa Kunjungan)
- **Nationality-Only Scope:** Confirmed. The BVK facility is granted based on specific countries,
  administrative regions, and specific entities. [VERIFIED https://kemenimipas.go.id]
- **+6 Added States Verification:** The regulation added **Turkey, Brazil, Peru, Kazakhstan,
  Macau (Makau), and Belarus**. The report of "Morocco" being added is FALSE; it was Macau that
  was added. [VERIFIED https://kompas.com]
- **Current BVK List Count:** 19 countries and territories. [VERIFIED https://kompas.com]
- **Effective Date:** July 9, 2026. [VERIFIED https://kemenimipas.go.id]

### 3. Permen Imipas No. 5/2025 (Guarantor/Penjamin Rules)
- **Scope of Revocation:** Completely revokes Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor
  36 Tahun 2021 tentang Penjamin Keimigrasian. [VERIFIED https://kemenimipas.go.id]
- **Corporate vs Individual Guarantor Changes:** This specific regulation acts purely as a
  revocation instrument for the 2021 law. Any substantive new requirements or deposits for
  corporate/individual guarantors are [UNVERIFIED] within *this* document, as they are likely
  stipulated in a separate replacement regulation. [VERIFIED https://kemenimipas.go.id]
- **Effective Date:** Promulgated and effective on March 7, 2025. [VERIFIED https://kemenimipas.go.id]

### 4. NEW EVENTS SWEEP (2026-06-01 to 2026-07-18)
- **Found Event:** Permenimipas Nomor 10 Tahun 2026 regarding the expansion of Bebas Visa
  Kunjungan (BVK) to 19 countries. Issued and effective July 9, 2026. [VERIFIED https://kemenimipas.go.id]
- **Other Events:** No other specific regulations (Permen, Kepmen, Kepdirjen, SE) affecting
  VoA/eVoA, KITAS/KITAP, bridging visas, overstay sanctions, onshore conversions, or golden visas
  were found to have been promulgated within this exact 6-week window. [UNVERIFIED]

### 5. Engine Action (Rule valid_from/valid_to Implication)
No transitional/grandfathering windows (masa transisi) were identified in the public announcements
for these regulations, meaning the engine should apply immediate temporal cutoffs on their
effective dates.

| regulation | number | effective_date | engine_action |
| :--- | :--- | :--- | :--- |
| Kepmen Klasifikasi Visa | M.IP-08.GR.01.01 Tahun 2025 | 2025-06-02 | `valid_from`: 2025-06-02. `valid_to` (for Kepmen M.HH-02.GR.01.04 Tahun 2023): 2025-06-02. |
| Permen Pencabutan Penjamin | 5 Tahun 2025 | 2025-03-07 | `valid_from`: 2025-03-07. `valid_to` (for Permenkumham 36/2021): 2025-03-07. |
| Permen Bebas Visa Kunjungan | 10 Tahun 2026 | 2026-07-09 | `valid_from`: 2026-07-09. `valid_to` (for Permenimipas 10/2025): 2026-07-09. |

## Engine design consequences (orchestrator)

- The bitemporal schema (PR4) and RulePack metadata must carry per-rule `legal_period` from day
  one — confirmed necessary by the ~3-4 month regulatory cadence and the two live date disputes
  above.
- The 110-code catalog bundle (pinned input, post-bonifica #2602) must record provenance dates as
  data, and the M.IP-08 effective date stays UNVERIFIED in bundle metadata until the Kepmen text
  arbitration.
- FASE 2 content: BVK nationality answers CANNOT ship until the Macau/Morocco arbitration closes
  (zero-wrong-answers bar).
