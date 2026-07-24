---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: gemini
---

All evidence gathered. Cleaning nothing (scratch stays in `/tmp/vo-w2-bridging/` for the verifying session: both primary PDFs + extracted text). Here is the full fact-base.

---

# Visa Oracle v2 — RulePack fact-base: BRIDGING VISA family

**As-of date:** 2026-07-24 (all sources re-checked today; primary PDFs re-downloaded and re-extracted today, not reused from the FASE 1 closeout).
**Prior art built on (not redone):** `research/visa/2026-07-17-bridging-visa-branch-d7ab-diaspora-closeout.md` — its partial-revocation resolution, lane table, and price ruling stand; this pass **newly grounds** (a) Ps. 94A(3) document/guarantor text verbatim, (b) the guarantor question post-Permen-Imipas-5/2025 from the primary text of 5/2025 itself, (c) the from/to transition matrix incl. the alih-status interplay, (d) the definitions (Penjamin/Penanggung Jawab/Hari) verbatim, (e) engine FactPath mapping.

---

### BRIDGING — Bridging Visa (Transitional Stay Permit) / Izin Tinggal Peralihan — formally *Izin Tinggal Kunjungan dalam rangka peralihan Izin Tinggal Keimigrasian*

**Not a Kepmen visa-index code** — a stay-permit class created by Permenkumham 11/2024 inserting Ps. 80(3)(f), 80(4)(d), 86A, 94A, 94B into Permenkumham 22/2023. Confirmed in force as of 2026-07-24 (BPK status: "Dicabut Sebagian" — the partial revocation via Permen Imipas 3/2025 touches only Ps. 43, 45, 52, 53, 54, 55 of 22/2023; the bridging articles are untouched).

- **catalog_entry:** category: `TRANSITIONAL_STAY_PERMIT` (pseudo-product; not in the 110-index catalog — attach to interview lane, per bonifica Table 2 + closeout §3.1) | covered_purposes: `OTHER` (purpose-neutral bridge; "kegiatan tertentu" per Dirjen, Ps. 86A(2)-(3) — the Dirjen list itself is UNVERIFIED, see uncertainty) | entry_policy: `NONE` (no entry function — onshore-granted; **voided by any exit**) | stay_policy: `FIXED_DAYS 60` (max, per issuance — start event UNVERIFIED, see uncertainty) | extension_policy: `not allowed` (Ps. 86A(1) "tidak dapat diperpanjang"; also absent from the Ps. 95(1) extension-eligible ITK list) | prohibited_activities: employment relationship per general ITK frame; specific activity list delegated to Dirjen (UNVERIFIED); exit from Indonesian territory terminates the permit | sponsor_types: `NONE_REQUIRED` — guarantor is **conditional, not mandatory** (Ps. 94A(3)(c): bukti penjaminan only "dalam hal Orang Asing memiliki Penjamin"); application may be filed by the foreigner, a Penjamin, or a Penanggung Jawab (Ps. 94A(1)) | legacy_codes: none (new instrument, 2024-04-01)

- **eligibility_rules** (fact paths use the engine's existing `FactPath` vocabulary; `days_to_expiry` is a derived fact from `immigration.current_status_expiry` — same derived-fact pattern as `derived.age_years`):

1. `{stage: HARD_FILTER, fact_path: immigration.currently_in_indonesia, op: eq, value: true, reason_code: BRIDGING_ONSHORE_ONLY, on_unknown: EXCLUDE→HUMAN_REVIEW}` — Ps. 94A(1) "dari dalam wilayah Indonesia".
2. `{stage: HARD_FILTER, fact_path: derived.days_to_expiry, op: gte, value: 3, reason_code: BRIDGING_WINDOW_MISSED, on_unknown: EXCLUDE→HUMAN_REVIEW}` — Ps. 94A(4) + official gloss (file **and pay** no later than 3 calendar days before expiry; "Hari adalah hari kalender", def. 36). Values 0–2 → bridging unavailable (route to urgent/overstay lane; never auto-reject the *person*). **Boundary value exactly 3** → do not auto-pass; see rule 3.
3. `{stage: HUMAN_REVIEW, fact_path: derived.days_to_expiry, op: eq, value: 3, reason_code: BRIDGING_T3_BOUNDARY, on_unknown: n/a}` — filing-day inclusivity and expiry timestamp/timezone are genuinely unresolved in the sources (closeout §3.4); conservative handling.
4. `{stage: HARD_FILTER, fact_path: immigration.current_status_code, op: in, value: [ITK_FROM_VOA, ITAS, ITAP], reason_code: BRIDGING_SOURCE_STATUS_NOT_ELIGIBLE, on_unknown: HUMAN_REVIEW}` — Ps. 94A(2) exhaustive trio. **Load-bearing:** the engine's `current_status_code` vocabulary must distinguish ITK *by origin* (VOA-derived vs C/D-series e-visa-derived vs BVK-derived vs bridging) — a new required interview question ("how did you enter?", closeout §3.4). Non-listed statuses → HUMAN_REVIEW with honest copy, never auto-reject (Dirjen practice wider than the text cannot be excluded).
5. `{stage: HUMAN_REVIEW, fact_path: person.nationalities, op: intersects, value: CALLING_VISA_LIST, reason_code: BRIDGING_CALLING_VISA_OVERLAY, on_unknown: HUMAN_REVIEW}` — no bridging-specific calling-visa clause exists; adjacent ITK services route calling-visa cases to the Dirjen (5 working days). Conservative guard.
6. `{stage: HUMAN_REVIEW, fact_path: immigration.violation_history, op: intersects, value: [OVERSTAY, DEPORTATION, BLACKLIST, IMMIGRATION_INVESTIGATION], reason_code: BRIDGING_ADVERSE_HISTORY, on_unknown: HUMAN_REVIEW}` — no textual bar in 94A, but a pending overstay/violation makes the window math and approval discretionary; a person must look.
7. `{stage: ELIGIBILITY, fact_path: intent.requested_product_code, op: neq, value: null, reason_code: BRIDGING_REQUIRES_DESTINATION, on_unknown: NEEDS_INPUT}` — bridging is not a stand-alone product: Ps. 94A(3)(d) requires a statement of maksud/tujuan, and the official frame is "bridge to a NEW stay status". If the goal is a *plain extension* of the current permit, bridging is the wrong product (route to extension lane).

- **legal_basis:**
  - Permenkumham 11/2024 (ditetapkan 2024-04-01), Ps. 80(3)(f)/80(4)(d), 86A, 94A, 94B + def. 18/19/21/36 — https://peraturan.bpk.go.id/Details/285156/permenkumham-no-11-tahun-2024 (PDF re-extracted today; verbatim quotes below). Status as of 2026-07-24: **Dicabut Sebagian** (partial).
  - Permen Imipas 3/2025, Ps. 45 (partial revocation; bridging articles untouched) — https://peraturan.bpk.go.id/Details/316856/permen-imipas-no-3-tahun-2025 (ditetapkan 2025-02-07, berlaku 2025-05-06). Verified in the FASE 1 closeout (primary PDF); re-confirmed today via BPK metadata.
  - Permen Imipas 5/2025 (full revocation of Permenkumham 36/2021 Penjamin Keimigrasian) — https://peraturan.bpk.go.id/Download/378168/Permen%20Imipas%20Nomor%205%20Tahun%202025.pdf (primary PDF read today, full text below).
  - Ditjen Imigrasi press release 2024-04-24 — https://www.imigrasi.go.id/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri (live today; same text syndicated on kanwil sites, e.g. kupang.imigrasi.go.id).
  - Official alih-status ITK→ITAS service page — https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas (live today).

---

## Transition rules (from/to matrix) — HARD_FILTER / HUMAN_REVIEW candidates

These are the rule candidates for the *edges*, as requested. Each is grounded below the table.

| # | Edge | Verdict | Rule candidate |
|---|---|---|---|
| T1 | ITK-from-VOA → BRIDGING | **ALLOWED** (Ps. 94A(2)(a)) | pass rule 4 above |
| T2 | ITAS → BRIDGING | **ALLOWED** (Ps. 94A(2)(b)) | canonical case: ITAS "sudah tidak bisa lagi diperpanjang" (press release) |
| T3 | ITAP → BRIDGING | **ALLOWED** (Ps. 94A(2)(c)) | same frame |
| T4 | ITK-from-BVK (visa-free) → BRIDGING | **PROHIBITED** (by list silence; BVK-ITK arises under Ps. 80(3)(c), not from VKSK) | `{HARD_FILTER, current_status_code, neq, ITK_FROM_BVK, BRIDGING_FROM_BVK_PROHIBITED, on_unknown: HUMAN_REVIEW}` — inference-from-exhaustive-list, high confidence; BVK-ITK also cannot alih-status (official page) → BVK holders have **no onshore transition lane**; route to exit-and-reenter advice, human-first |
| T5 | ITK-from-C/D-series e-visa → BRIDGING | **PROHIBITED** (same list silence) | `{HARD_FILTER, current_status_code, not_in, [ITK_FROM_VISIT_C, ITK_FROM_VISIT_D], ..., on_unknown: HUMAN_REVIEW}` — **but** these holders CAN alih-status directly (only VOA/BVK are excluded on the official alih-status page) → route to `ONSHORE_CONVERSION`, subject to the T-30 deadline (T8) |
| T6 | BRIDGING → BRIDGING (bridge-to-bridge) | **PROHIBITED** (bridging ITK is not VOA-derived ITK, ITAS, or ITAP; 86A(1) non-extendable) | `{HARD_FILTER, current_status_code, neq, ITK_PERALIHAN, BRIDGING_TO_BRIDGING_PROHIBITED, on_unknown: HUMAN_REVIEW}` — inference-from-exhaustive-list |
| T7 | BRIDGING → ITAS (alih status) | **ALLOWED — the designed destination** (press release: bridging "dapat digunakan oleh WNA yang akan mengajukan alih status ke Izin Tinggal Terbatas") | downstream rule on the alih-status product, gated on the 11-activity list (tenaga ahli … kemanusiaan) |
| T8 | any ITK → ITAS alih status **deadline** | official page, verbatim: *"Permohonan alih status ITK menjadi ITAS diajukan dalam waktu paling lama 30 hari sebelum jangka waktu Izin Tinggal Kunjungan berakhir"* | `{HARD_FILTER, derived.days_to_expiry, gte, 30, ALIH_STATUS_T30_DEADLINE, on_unknown: HUMAN_REVIEW}` — parse: deadline **at T-30**, supported by the site's own house style ("paling cepat" = window-opening, "paling lama" = deadline, e.g. ITAS-extension and ITK-extension windows on the same pages); same construction as Ps. 94A(4) which the official gloss resolves as a deadline. Consequence: C-series holders inside their last 30 days can neither convert nor bridge → exit lane. **Flag the parse as official-page-only** (not re-verified against 22/2023's article text today). |
| T9 | ITAS → ITAP alih status | official page: same T-30 construction; activity list per amended Ps. 173 (pekerja, rohaniwan, PMA, penyatuan keluarga, repatriasi, rumah kedua) | same shape as T8 |
| T10 | BRIDGING → exit Indonesia | **permit VOID** | `{HARD_FILTER, —, —, BRIDGING_VOID_ON_EXIT}` — popularization-tier (press release: *"Izin tinggal ini tidak berlaku lagi apabila WNA keluar wilayah Indonesia"*); **not located in the primary articles** (closeout §3.2, honestly tiered) — outcome-card fact, not an engine gate |
| T11 | BRIDGING → ITK extension | **PROHIBITED** (86A(1); Ps. 95(1) extension list covers only ITK from single/multiple visit visas and VOA) | covered by catalog_entry extension_policy |
| T12 | ITAS/ITAP holder → new ITAS/ITAP via bridging | **ALLOWED** (press release: "pemegang ITAS dan ITAP yang sudah tidak bisa lagi diperpanjang, dapat memperoleh Izin Tinggal baru tanpa harus keluar wilayah") | destination mechanics (onshore VITAS grant while on bridging) are popularization-level — the engine should treat the destination grant as a separate product evaluation, with HUMAN_REVIEW on the mechanical chain |

**Overstay interaction (rules):**
- `{stage: ELIGIBILITY, fact_path: derived.bridging_filed_and_paid_before_expiry, op: eq, value: true, reason_code: BRIDGING_OVERSTAY_SHIELD, on_unknown: n/a}` — Ps. 94A(5): application filed **AND** fee paid before expiry → no overstay counted if processing overruns. Both legs required (closeout §3.3(b)).
- If not filed+paid before expiry → normal overstay exposure; the per-day tariff (repo canon: Rp1,000,000/day, wave0 brief 2026-07-23) was **not re-verified against primary today** — defer the figure to the overstay lane; microcopy rule per wave0: exact or omit.
- Service-time promise (distinct clock): issuance ≤ **3 working days** after payment received, electronic delivery (Ps. 94B(2)-(3)).

**Guarantor requirements post-Permen-Imipas-5/2025 (resolution, primary text read today):**
- Permen Imipas 5/2025 is a **pure 2-article revocation instrument** — Pasal 1: *"Peraturan Menteri Hukum dan Hak Asasi Manusia Nomor 36 Tahun 2021 tentang Penjamin Keimigrasian … dicabut dan dinyatakan tidak berlaku."* Menimbang (a): revocation for *"reformasi birokrasi terhadap pengaturan penjamin … pelayanan yang lebih mudah, murah, dan cepat … sudah tidak sesuai dengan perkembangan hukum dan kebutuhan masyarakat"*. Ditetapkan 2025-02-07, diundangkan 2025-02-07/03-07 (BN 2025 No. 158), in force on promulgation. **No replacement instrument.**
- Operative guarantor rule for bridging is therefore only Ps. 94A(3)(c): *"bukti penjaminan **dalam hal** Orang Asing memiliki Penjamin"* — **conditional**: no Penjamin is required to apply; self-filing is explicit (Ps. 94A(1): "Orang Asing, Penjamin atau Penanggung Jawab"). Definitions (verbatim today): Penjamin = "orang atau korporasi yang bertanggung jawab atas keberadaan dan kegiatan Orang Asing" (def. 18); Penanggung Jawab = WNI spouse/parent/child ≥21 (def. 21); Jaminan Keimigrasian = funds/form substituting a Penjamin (def. 19).
- Engine consequence: **no guarantor HARD_FILTER for BRIDGING**; strip any legacy 36/2021-derived guarantor-validation rule touching this lane (matches R2 delta instruction). If the *destination* status has a Penjamin, the bukti penjaminan rides along as a document, not as an eligibility gate.

**Key verbatim primary anchors (extracted today, `/tmp/vo-w2-bridging/permenkumham-11-2024.txt`):**
- Ps. 86A(1): *"…diberikan untuk jangka waktu paling lama 60 (enam puluh) hari dan tidak dapat diperpanjang."*
- Ps. 94A(2): *"…dapat diajukan bagi: a. Orang Asing pemegang Izin Tinggal Kunjungan yang berasal dari Visa Kunjungan Saat Kedatangan; b. Orang Asing pemegang Izin Tinggal Terbatas; atau c. Orang Asing pemegang Izin Tinggal Tetap."*
- Ps. 94A(4): *"…diajukan dalam jangka waktu paling lama 3 (tiga) hari sebelum Izin Tinggal yang dimiliki berakhir."* + def. 36: *"Hari adalah hari kalender."*
- Ps. 94A(5): *"…yang telah diajukan dan dilakukan pembayaran biaya imigrasi sebelum berakhir jangka waktu Izin Tinggalnya, tidak diperhitungkan overstay jika penyelesaiannya melebihi jangka waktu Izin Tinggalnya."*

**Engine integration anchors (existing, verified in repo today):** `ApplicationChannel.STATUS_BRIDGING` (`enums.py:269`); `FactPath.PROCESS_APPLICATION_CHANNEL` allowed_values `{OFFSHORE, ONSHORE_CONVERSION, STATUS_BRIDGING}` (`fact_registry.py:357`); gold-fixture pattern `review.e28a.status-bridging` (HUMAN_REVIEW on `process.application_channel == STATUS_BRIDGING`) in `_gold_fixtures.py:401`. Needed-new: controlled vocabulary for `immigration.current_status_code` origin-distinguishing ITK values, and a `derived.days_to_expiry` fact. Client price: IDR 3,500,000 all-inclusive (PricingTool SSOT; internal, owner ruling — not a legal fact; no PNBP split on client surfaces).

**uncertainty (all explicitly UNVERIFIED or inference-tier):**
1. **PNBP tariff for the bridging ITK** — no dedicated "peralihan" line found on any official fee page (PP 45/2024 lampiran is a non-extractable scan; imigrasi.go.id today lists ITK 60-day = Rp2,000,000/permohonan; jakartapusat page listed Rp1,000,000 on 2026-07-17 — conflicting official pages). Client surfaces unaffected (owner ruling). UNVERIFIED.
2. **60-day clock start event** — Ps. 86A(1) states the max duration but not the start (contrast Ps. 85's explicit "sejak tanggal diberikannya Tanda Masuk"). Presumably from issuance; not stated in primary or popularizations. UNVERIFIED — do not hard-code start math.
3. **Permitted-activities Dirjen list** (Ps. 86A(3)) — no Perdirjen located. UNVERIFIED.
4. **T4/T5/T6 exclusions are inferences from the exhaustive-list structure of Ps. 94A(2)** — high confidence, and T4 is corroborated by the official alih-status page's VOA/BVK exclusion, but no source states "BVK/bridging holders cannot bridge" in so many words. Keep `on_unknown: HUMAN_REVIEW`; never auto-reject copy.
5. **T8/T9 T-30 deadline parse** — official-page text + house-style argument only; the underlying 22/2023 article was not re-extracted today. Mark official-page-tier.
6. **Void-on-exit (T10)** — popularization-tier (2 official sources), absent from the primary articles.
7. **Filing-day inclusivity + expiry timestamp/timezone at T-3** — genuinely open (closeout §6); handled by the T3-boundary HUMAN_REVIEW rule.
8. **Destination-grant mechanics on bridging** (onshore VITAS→ITAS issuance without exit) — press-release-tier; treat as HUMAN_REVIEW chain, not an automated promise.
9. **Currency as of 2026-07-24:** no instrument after Permen Imipas 3/2025 / 5/2025 touches Ps. 86A/94A/94B (July 2026's Permen Imipas 10/2026 expands BVK nationalities — it widens the T4-excluded population but changes no bridging rule). Checked today via BPK metadata + web sweep; the FASE 1 closeout's currency verdict stands.

**Caution — bad secondary in circulation:** balivisaadvisor.com (2025-11-21) describes bridging as an "automatic legal status … no separate registration" activated by any pending application — **contradicts the primary text** (bridging requires its own application + payment, Ps. 94A/94B). Do not let agency-blog framing leak into rules or copy.
## Adversarial review

Gemini 3.1 Pro (High), 2026-07-24 — FIX-FIRST, 3 findings, orchestrator dispositions (ALL ACCEPTED as load-bearing caveats for authoring):
1. T7/T12 alih-status vs onshore-VITAS conflation — ACCEPTED: the bridging→ITAS destination mechanic must be grounded on Permenkumham 22/2023 (as amended) primary text at authoring; if it is an alih-status product, the T-30 question becomes load-bearing.
2. T-30 as terminal outcome on an official-page-only parse — ACCEPTED: **T-30 is demoted from HARD_FILTER-terminal to HUMAN_REVIEW** until the parse is confirmed against the primary article text; C-series holders inside 30 days must never be auto-routed to the exit lane on an unverified reading.
3. Overstay-shield payment clock — ACCEPTED: the rule must model `payment_settled_before_expiry` (billing cleared), not merely `filed_before_expiry`; the T-3 window closing makes filing-before-expiry tautological and the settlement lag is the real risk.
