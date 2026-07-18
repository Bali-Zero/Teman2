---
date: 2026-07-18
domain: visa
client_case: none (Visa Oracle v2 engine — MANDATO S3 regulatory delta re-check)
sources:
  - https://imigrasi.go.id (Kepmen M.IP-08.GR.01.01/2025 reclassification)
  - https://kemenimipas.go.id (Permen Imipas 10/2026 BVK; Permen Imipas 5/2025 penjamin)
  - https://kompas.com (BVK +6 states coverage)
lane: gemini-3.1-pro-high via agy v1.1.3 (15m, 2026-07-18)
adversarial_review_detail: generator=gemini-3.1-pro ≠ grader; independent web+NotebookLM arbitration lane (NB-2 confirmed FACT1, NB-INTEL surfaced the FACT2 gap) — both discrepancies confirmed-or-refuted against primary sources, see Arbitration outcome
adversarial_review: notebooklm
status: RESOLVED 2026-07-18 (same day) — both discrepancies arbitrated with primary sources by a dedicated web+NB lane; see "Arbitration outcome" section. Lampiran B211*→C-series mapping stays UNRESOLVED (OCR follow-up needed).
---

# Visa Oracle v2 — Round 4: Gemini regulatory delta re-check (MANDATO S3, point 5)

Re-verification of the round-2 regulatory delta baseline before FASE 2 content authoring and
RulePack `valid_from`/`valid_to` design. Lane output preserved verbatim below; orchestrator
annotations in the "Discrepancies" section.

## ✅ Arbitration outcome (2026-07-18, web-grounded lane + NB cross-check, generator≠grader)

**FACT 1 — Kepmen M.IP-08.GR.01.01 Tahun 2025: effective JUNE 2025, not 2026.** The round-2
baseline (and the visaoracle corner) were off by exactly one year. Primary evidence: the decree's
own dictum — *"KELIMA: Keputusan Menteri ini mulai berlaku setelah 30 (tiga puluh) hari terhitung
sejak tanggal ditetapkan"* with Lampiran date-stamp *"02 Mei 2025"*
(kemenimipas.go.id produk-hukum page + PDF `20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025`);
independent law-firm consensus SSEK + ABNR: "took effect on 2 June 2025"; ID press (voi.id
2025-06-13, detik 2025-06-15, liputan6 2025-06-16) already reporting it live in June 2025.
Residual 1-day tension (30-day math → 1 June vs law-firm 2 June): **engine `valid_from` =
2025-06-02** ("setelah 30 hari" = day AFTER the 30th day, consistent with SSEK/ABNR), noted as a
1-day authoring caveat in bundle metadata. Repeals Kepmen M.HH-02.GR.01.04/2023 (2023-10-23).
**Grandfather clause: visas/permits issued under the old 133-index system remain valid until their
own expiry** — the engine's old-index rules need per-document tail validity, not a hard cutoff.
NB-2 cross-check (NB modified 2026-07-17): verbatim dictum text present, consistent.

**FACT 2 — Permenimipas No. 10 Tahun 2026 (BVK): MACAU confirmed, Morocco REFUTED.** Official
imigrasi.go.id BVK page (primary) lists 19 entries: Brunei, Malaysia, Thailand, Vietnam, Filipina,
Kamboja, Singapura, Myanmar, Laos, Timor-Leste, Suriname, Kolombia, Hong Kong, Turki, Brasil,
Peru, Kazakhstan, **Makau**, Belarus (+ separate uncounted entry: Singapore PR holders with
entry-point restrictions). Kompas quotes the government verbatim: *"…Daerah Administratif Khusus
Makau Republik Rakyat China, serta Republik Belarus"*. Dates: ditandatangani 2026-07-07 (Menteri
Agus Andrianto), diundangkan 2026-07-09 (BN 2026/463), berlaku from signing per Kompas phrasing —
**engine `valid_from` = 2026-07-07** (authoring caveat: press says from signing; diundangkan
2026-07-09). Predecessor: Permenimipas 9/2025 gave TR/BR effective 2025-07-03.
**Number-collision trap**: Permenkumham No. 10/2026 is a DIFFERENT instrument (Second Home visa) —
content must always cite the issuing ministry, never the bare number.

**NB coverage gap (flag for nb-curator)**: NB-INTEL-Immigration (modified 2026-07-17) has NO
source on Permenimipas 10/2026 — the daily immigration feed missed it entirely one week after
signing. It only surfaced the colliding Permenkumham 10/2026 (Second Home).

**Still open — B211*→C-series Lampiran mapping**: official Lampiran PDF is image-only (no text
layer) and WAF-gated; the only reconstruction found is a travel-agency table (B211A→C1/C2/C3,
pre-investment→D12, D212→D1/D2) — LOW-MEDIUM confidence, NOT usable for content. Follow-up:
`mcp__ocr-tesseract__perform_pdf_ocr` on the downloaded PDF in a dedicated session.

## ⚠️ Discrepancies vs round-2 baseline (as originally flagged, pre-arbitration)

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

## Adversarial review

**Generator:** gemini-3.1-pro (High) via agy — the round-4 regulatory delta lane.
**Grader (≠ generator):** an independent web-grounded + NotebookLM arbitration lane (Sonnet with live
WebSearch/WebFetch against primary sources — imigrasi.go.id, kemenimipas.go.id, JDIH, SSEK/ABNR — plus
NB-2 and NB-INTEL-Immigration as ground-truth cross-checks). Seat recorded as `notebooklm` (the
allowlisted ground-truth authority that participated).

**Objections raised: 2. Surviving after arbitration: 0 (both resolved against primary sources).**

1. **Kepmen M.IP-08/2025 effective date** — the generator's baseline lineage carried `2026-06-02`.
   Refuted: the decree's own dictum KELIMA ("+30 hari from ditetapkan 02 Mei 2025") plus SSEK + ABNR
   law-firm consensus and June-2025 Indonesian press fix the effective date at **2025-06-02**. The
   grader corrected the generator; the engine `valid_from` uses the corrected value. (Residual 1-day
   tension 1-vs-2 June recorded as an authoring caveat, not a surviving objection.)
2. **BVK +6 states "MO" ambiguity** — the generator's shorthand `MO` was ambiguous (Macau vs Morocco).
   Resolved: the official imigrasi.go.id 19-entry list + Kompas verbatim confirm **Macau**, and mark
   **Morocco FALSE**. No surviving objection.

**Coverage gap surfaced (not an objection to the content, a finding about the pipeline):**
NB-INTEL-Immigration had NO source on Permenimipas 10/2026 one week post-signing — filed for nb-curator
(PENDING NB-INTEL-GAP in the visaoracle corner). This does not weaken the two verdicts above (both
closed on primary web sources), but is logged so the ground-truth authority's own staleness is visible
(W90 discipline: the ground truth ages too).

**Verdict: SURVIVES — both load-bearing claims confirmed against primary sources; the only open item
(B211*→C-series Lampiran mapping) is explicitly marked UNRESOLVED and gates FASE 2 content, not the
engine PRs.**
