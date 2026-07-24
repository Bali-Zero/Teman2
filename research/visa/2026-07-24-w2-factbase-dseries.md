---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: gemini
---

I have everything needed. Compiling the final fact-base now.

---

# FACT-BASE — D-series multiple-entry visit visas (Visa Oracle v2 RulePack factory, W2 lane)

**Lane:** D-family (D1, D2, D12 + all other D* in the 110-index) · **As-of date:** 2026-07-24 · **Method:** live per-code fetches of `imigrasi.go.id/wna/daftar-visa-indonesia/{CODE}` today (WebFetch-style extraction + raw curl/HTML grep with the closeout's "Data Belum Tersedia" empty-body discriminator and a B211A known-dead control), cross-checked against the repo's bonified catalog (`research/visa/2026-07-17-visa-catalog-bonifica-110-remap.md`), the D12/C12 verification (`research/visa/2026-07-21-c12-d12-verification.md`), the diaspora closeout (`research/visa/2026-07-17-bridging-visa-branch-d7ab-diaspora-closeout.md`), and on-disk engine/seed/pricing files.

**D-family in the 110-index (13 codes):** D1, D2, D3, D4, D7, D7A, D7B, D8, D8A, D8B, D12, D14, D17. No other D* surfaced in any source (bonifica + closeout corpus diff + today's probes).

## Family-level frame (applies to all D codes unless a per-code entry overrides)

- **Legal basis stack (identical on every live D page today):** PP 45/2024 (PNBP tariffs) · Permenkumham 11/2024 jo. Permenkumham 22/2023 (Visa & Stay Permits) · **Kepmen Imipas M.IP-08.GR.01.01/2025 (Klasifikasi Visa, the 110-index)** · PMK 9/PMK.02/2022 · PMK 82/2023. Kepmen effective 2025-06-02 per repo panel sources (the shared brief says 2025-06-01 — 1-day discrepancy, Kepmen PDF still WAF-blocked → exact day UNVERIFIED).
- **Stay math (official ITK table, [imigrasi.go.id/wna/izin-tinggal-keimigrasian](https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian), live today):** Multiple-Entry Visitor Visa (Indeks D), *exception D12* → first ITK **60 days**, extendable each time by 60 days up to **max 180 days total per entry**. D12 → first ITK **180 days**, extendable each time by 180 days up to **max 12 months total per entry**. Stay counted from arrival date ("dihitung sejak tanggal kedatangan").
- **Extension mechanics (same ITK page):** apply ≥14 days before expiry at the earliest, before ITK expiry at the latest; payment before expiry = no overstay; extension ITK starts 1 day after previous ends; processing ≤3 working days after payment (calling-visa nationals ≤5 wd via DGI); PNBP per extension: ITK 60d = Rp 2.000.000, ITK 180d = Rp 6.000.000. Extension sponsor: same guarantor as the visa ("jika menggunakan Penjamin"); changing guarantor needs objection + release letters.
- **No D-code converts to ITAS** — every D page states the stay permit "tidak dapat dikonversikan/dialihkan menjadi Izin Tinggal Terbatas".
- **Application channel:** evisa.imigrasi.go.id; processing **5 working days** after payment received (all D pages today).
- **Common documents:** passport valid ≥6 months (≥12 months for non-national travel documents), 3-month bank statement, color photo (<1 yr), **CV, travel itinerary** (D-series requires both — unlike C12). Stateless persons / non-national travel-doc holders additionally need a re-entry permit to the application country + return/onward ticket.
- **Visa validity:** counted from issuance date ("Masa berlaku visa terhitung sejak tanggal penerbitan"). The PNBP tiers label validity ("Biaya visa 1/2/5 tahun") — the "Masa tinggal 1 tahun" phrasing on the pages is the *visa validity tier*, not a per-entry stay grant.
- **Calling-visa overlay:** applicants from calling-visa states route through DGI clearance — engine HUMAN_REVIEW. List count conflicts in-repo (7 vs 8 states; gemini R2 delta says 8: Afghanistan, Guinea, Israel, Cameroon, North Korea, Liberia, Nigeria, Somalia) → exact list UNVERIFIED here (another lane owns it).
- **D-vs-C boundary (verified):** C = single entry, one continuous stay (C1/C2: 60d → extend to 180d total; C12: 180d → 12mo, **onshore ITAS-convertible**). D = multiple entries across a 1/2/5-year validity, stay clock resets per arrival (60d/entry, D12 180d/entry, extendable per entry), **never ITAS-convertible**. Rule of thumb the engine already encodes (`match_tree.py:237-240`, FitTag.MULTI_ENTRY −0.30): D for repeated in/out trips; C for one continuous stay. C12→KITAS onshore conversion vs D12 "tidak bisa dialihkan" is the sharpest boundary (verbatim-verified 2026-07-21).
- **Legacy codes:** D212 (pre-2023 multiple-entry index, covered family/business/government-duty/pre-investment) → split into D1/D2/D3/D4/etc. Secondary source only (Baker McKenzie Global Employer handbook 2022) → **UNVERIFIED at primary level**. B211* belongs to the C-series, never to D.

## The "D12 diaspora/ex-WNI variant" — VERIFIED AS NON-EXISTENT

Checked against the diaspora closeout + today's live fetch of [imigrasi.go.id/…/global-citizen](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/global-citizen) + the Permen Imipas 3/2025 structure: **there is no D12 (or any D-series) diaspora/ex-WNI variant.** All diaspora products are **Visa Tinggal Terbatas** in the E31/E32 families (GCI: E31A/B/C, E32E/F/G/H per the official kemenimipas enumeration; E32A-D "Golden Visa"-branded). D12 is strictly pre-investment. The only family-ties bridge in the D-series is D1/D2's alternative special requirement: a letter from a WNI spouse/parent + family card. Agent marketing (e.g. lmiconsultancy.com) uses "diaspora visa" as an umbrella marketing term — establishes no D-code variant. **Engine rule: ex-WNI visit intent → D1/D2 (family-letter path) for visits, E32-family (GCI) for residence; never emit a "D12 diaspora" product.**

---

### D1 — Visit Visa Tourism (Multiple Entry) / Visa Kunjungan Wisata (Beberapa Kali Perjalanan)

- **catalog_entry:** Multiple-Entry Visit | purposes: TOURISM, FAMILY, TRANSIT, BUSINESS_MEETINGS (participant-only MICE: "menghadiri pertemuan, insentif, konvensi, dan pameran … (sebagai peserta)") | entry_policy: MULTIPLE | stay_policy: FIXED_DAYS 60 per entry (per-entry cap 180 after extensions) | extension_policy: allowed, 60 days per extension, max 2 per entry (60+2×60=180; "beberapa kali hingga maksimal 180 hari" — page phrasing is "several times", ITK table gives 60d increments → max 2 in practice) | prohibited_activities: selling goods/services; receiving remuneration/wages from Indonesian persons/corporations ("dilarang menjual barang atau jasa atau menerima imbalan, upah, atau sejenisnya atas kerja/usahanya dari perorangan atau korporasi di Indonesia") | sponsor_types: NONE (self-application, own evisa account) — but an institutional letter/invitation OR WNI-family letter is required as a document | legacy_codes: D212 (UNVERIFIED, secondary)
- **eligibility_rules:**
  - {HARD_FILTER, person.nationalities, intersects, [ID], APPLICANT_IS_INDONESIAN_CITIZEN, NEEDS_INPUT} (global rule, applies to all codes)
  - {ELIGIBILITY, documents.passport_validity_months, gte, 6, PASSPORT_VALIDITY_INSUFFICIENT, NEEDS_INPUT} — verbatim "paling singkat 6 bulan"
  - {ELIGIBILITY, documents.bank_statement_min_usd, gte, 2000, PROOF_OF_FUNDS_D1, NEEDS_INPUT} — 3-month statement, foreigner's or guarantor's name, "minimal USD2000 atau setara"
  - {ELIGIBILITY, documents.travel_itinerary, eq, true, ITINERARY_REQUIRED, NEEDS_INPUT}
  - {ELIGIBILITY, documents.cv, eq, true, CV_REQUIRED, NEEDS_INPUT}
  - {ELIGIBILITY, documents.invitation_letter, any_of, [INSTITUTIONAL_LETTER, WNI_FAMILY_LETTER], SUPPORT_LETTER_REQUIRED, NEEDS_INPUT} — institutional letter/invitation/correspondence OR letter from WNI spouse/parent + family card
  - {HUMAN_REVIEW, person.nationalities, intersects, [CALLING_VISA_STATES], CALLING_VISA_OVERLAY, NEEDS_INPUT}
  - {HUMAN_REVIEW, person.travel_document_class, neq, NATIONAL_PASSPORT, STATELESS_OR_NON_NATIONAL_DOC, NEEDS_INPUT} — extra docs (re-entry permit + return ticket)
  - {ELIGIBILITY, visa.validity_tier, in, [1Y, 2Y, 5Y], D1_TIER_SELECT, NEEDS_INPUT} — PNBP Rp 4.0M / 6.0M / 11.0M (components 3M+1M / 5M+1M / 10M+1M Verifikasi I)
- **legal_basis:** Kepmen M.IP-08.GR.01.01/2025 (index) + Permenkumham 22/2023 jo. 11/2024 (mechanics) + PP 45/2024 (PNBP); canonical: [imigrasi.go.id/wna/daftar-visa-indonesia/D1](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D1) — in force per Kepmen 2025-06-02; **checked live 2026-07-24** (populated, no empty marker).
- **Bali Zero price (PricingTool SSOT, not a legal fact):** 1Y IDR 6.000.000 · 2Y IDR 8.000.000 · 5Y IDR 12.900.000 (`bali_zero_official_prices_2026.json`). ⚠ Seed script + migration_122 carry 14.000.000 for 5Y — **price discrepancy, unresolved**.
- **uncertainty:** the page's extension/billing boilerplate mentions "sponsor" while the application section is self-service (same internal inconsistency the D12 verification documented); who files extensions for no-guarantor D1 holders = UNVERIFIED. Remote work is not addressed by the official page (only Indonesian-sourced income is prohibited) — do not encode WORK_REMOTE as a covered purpose without an owner decision.

### D2 — Visit Visa Business (Multiple Entry) / Visa Kunjungan Bisnis

- **catalog_entry:** Multiple-Entry Visit | purposes: BUSINESS_MEETINGS (rapat; pembicaraan/pembahasan/negosiasi/penandatanganan perjanjian bisnis; pembelian barang; pengecekan barang di kantor/pabrik/tempat produksi), TOURISM, FAMILY | entry_policy: MULTIPLE | stay_policy: FIXED_DAYS 60 per entry (cap 180 after extensions) | extension_policy: allowed, 60d increments, max ~2 per entry (→180) | prohibited_activities: standard D prohibition **plus** "dilarang melakukan supervisi secara terus menerus dari kegiatan produsen atau penjualan" (no continuous supervision of production/sales) | sponsor_types: NONE (self-application; institutional letter or WNI-family letter required as document) | legacy_codes: D212 (UNVERIFIED, secondary)
- **eligibility_rules:** same set as D1 (passport ≥6mo; funds **USD 2,000**; CV; itinerary; institutional-or-WNI-family letter; calling-visa → HUMAN_REVIEW; non-national doc → HUMAN_REVIEW) + {ELIGIBILITY, visa.validity_tier, in, [1Y, 2Y, 5Y], D2_TIER_SELECT, NEEDS_INPUT} — PNBP identical to D1: Rp 4.0M / 6.0M / 11.0M.
- **legal_basis:** same stack; canonical [imigrasi.go.id/wna/daftar-visa-indonesia/D2](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D2) — **checked live 2026-07-24** (populated).
- **Bali Zero price:** 1Y IDR 6.500.000 · 2Y IDR 9.000.000 (JSON SSOT). **No Bali Zero 5Y D2 product** although the official 5Y PNBP tier exists.
- **uncertainty:** same sponsor-boilerplate ambiguity as D1. The "no continuous supervision" clause is the sharpest D2-vs-employment boundary — worth a dedicated prohibited-activity reason_code.

### D12 — Visit Visa Pre-Investment (Multiple Entry) / Visa Kunjungan Pra-Investasi

- **catalog_entry:** Multiple-Entry Visit | purposes: INVESTMENT (pre-investment: "survei lapangan dan/atau studi kelayakan", starting a business), TOURISM, FAMILY | entry_policy: MULTIPLE | stay_policy: FIXED_DAYS **180 per entry** (cap 12 months after extension) | extension_policy: allowed, **once**, +180 days → max 12 months per entry ("bisa diperpanjang untuk 180 hari berikutnya"; "satu kali hingga keseluruhan … 12 bulan (1 tahun)") | prohibited_activities: standard D prohibition (no selling goods/services, no Indonesian-sourced remuneration) | sponsor_types: **NONE — explicit**: "Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini" (verbatim-verified from raw HTML 2026-07-21; today's fetch shows the self-application phrasing but the extractor dropped the sponsor header) — institutional letter/invitation still required | legacy_codes: D212 (UNVERIFIED, secondary)
- **eligibility_rules:**
  - {ELIGIBILITY, documents.passport_validity_months, gte, 6, PASSPORT_VALIDITY_INSUFFICIENT, NEEDS_INPUT} (12 for non-national docs)
  - {ELIGIBILITY, documents.bank_statement_min_usd, gte, 5000, PROOF_OF_FUNDS_D12, NEEDS_INPUT} — verbatim "minimal USD5000"
  - {ELIGIBILITY, documents.cv, eq, true, CV_REQUIRED, NEEDS_INPUT}
  - {ELIGIBILITY, documents.travel_itinerary, eq, true, ITINERARY_REQUIRED, NEEDS_INPUT}
  - {ELIGIBILITY, documents.invitation_letter, eq, INSTITUTIONAL_LETTER, SUPPORT_LETTER_REQUIRED, NEEDS_INPUT} — government-institution or private-entity letter explaining the relationship
  - {HARD_FILTER, goal.onshore_kitas_conversion, eq, true, D12_NOT_CONVERTIBLE, NEEDS_INPUT} — "tidak bisa dialihkan menjadi izin tinggal terbatas"; a D12 holder wanting KITAS must apply for a new KITAS offshore (practice nuance: Investor KITAS after PT PMA is a fresh application — confirmed in the 2026-07-21 verification's Disagreements section)
  - {ELIGIBILITY, visa.validity_tier, in, [1Y, 2Y], D12_TIER_SELECT, NEEDS_INPUT} — **no 5Y tier**; PNBP Rp 5.0M (3M + 2M Verifikasi II) / Rp 7.0M (5M + 2M)
  - calling-visa → HUMAN_REVIEW; non-national doc → HUMAN_REVIEW (as family)
- **legal_basis:** same stack; canonical [imigrasi.go.id/wna/daftar-visa-indonesia/D12](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12) — **checked live 2026-07-24** (populated); corroborated by kemlu.go.id consular page (D12 1-Year listed) and ANTARA enforcement news citing "B1 dan D12" (2026-05-08).
- **Bali Zero price:** 1Y IDR 7.500.000 · 2Y IDR 10.000.000 (JSON SSOT; seed script carries 7.5M flat).
- **uncertainty:** the page's "keseluruhan masa tinggal paling lama 12 bulan (1 tahun) **atau 2 tahun**, bergantung pada durasi visa" — the "or 2 years" clause conflicts with the ITK table's 12-month per-entry cap; plausible reading is cumulative-across-entries on a 2Y visa, but **UNVERIFIED — do not encode >12-month presence as a rule; HUMAN_REVIEW**. Sponsor-boilerplate inconsistency (extensions/billing mention "sponsor") documented 2026-07-21.

### D3 — Visit Visa Medical Treatment (Multiple Entry) / Visa Kunjungan Perawatan Kesehatan

- **catalog_entry:** Multiple-Entry Visit | purposes: MEDICAL, TOURISM, FAMILY | MULTIPLE | FIXED_DAYS 60/entry (→180 with extensions) | extension: allowed, 60d increments → 180/entry | prohibited: standard D prohibition | sponsor_types: **SPONSOR_REQUIRED** ("Penjamin (sponsor) harus memiliki akun di evisa…") | legacy_codes: D212 (UNVERIFIED)
- **eligibility_rules:** funds USD 2,000; passport ≥6mo; CV + itinerary; special: letter from government institution/private entity/foreigner's statement that they will undergo medical treatment in Indonesia; tiers 1Y/2Y — **PNBP Rp 3.0M / 5.0M, verification fee Rp 0** (cheapest D product). Calling-visa/non-national-doc → HUMAN_REVIEW.
- **legal_basis:** same stack; […/D3](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D3) — live today (populated). No Bali Zero product ("Contact for Quote" in seed).
- **uncertainty:** none material beyond family-level ones.

### D7 — Visit Visa Arts & Culture Performance (Multiple Entry) / Visa Kunjungan Penampilan Seni dan Budaya

- **catalog_entry:** Multiple-Entry Visit | purposes: OTHER (arts/culture performance incl. theatre & circus), TOURISM, FAMILY | MULTIPLE | FIXED_DAYS **30 per entry** | extension_policy: **NOT allowed** ("tidak bisa diperpanjang atau dialihkan") — *carve-out from the generic D ITK rule* | prohibited: **honorarium/facilities ALLOWED** ("diperkenankan menerima imbalan atau fasilitas atas aktivitasnya"), employment relationship prohibited ("dilarang bekerja dalam hubungan kerja") | sponsor_types: SPONSOR_REQUIRED | special docs: organizer invitation (general arts) **or** impresariat visa request + performer-organizer cooperation contract (music) | PNBP: Rp 2.500.000 per issuance (1.5M visa + 1M Verifikasi I)
- **legal_basis:** same stack; […/D7](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D7) — live today.
- **uncertainty:** visa validity duration not stated on the page (no 1/2/5Y tier shown) → UNVERIFIED. The generic ITK table names only D12 as a D exception; D7/D7A/D7B/D8A/D8B's non-extendability rests on the per-code pages — per-code text treated as controlling, tension flagged.

### D7A — Visit Visa Music Performance (Multiple Entry) / Visa Pertunjukan Musik — and D7B — Music Performance Crew / Visa Kru Pertunjukan Musik

- **catalog_entry (both):** Multiple-Entry Visit | purposes: OTHER (D7A: music performer; D7B: supporting crew), TOURISM, FAMILY | MULTIPLE | FIXED_DAYS **30/entry** | extension: NOT allowed, not convertible | prohibited: honorarium allowed, employment relationship prohibited | sponsor_types: SPONSOR_REQUIRED (files via evisa) | funds USD 2,000 | PNBP Rp 2.500.000 (1.5M + 1M Verif I)
- **legal_basis:** same stack; live-verified today (both populated, zero empty markers) — raw-HTML greps this session; existence settled by the diaspora closeout (dead-code controls + live product directory) 2026-07-17.
- **uncertainty:** curation caveats from the closeout (unpopulated heading slot; D7B "Visa D7" copy slip) — carry into the RulePack gate. Validity duration UNVERIFIED. Not in the 114-seed — proposed rows exist in the closeout §2.4 (110→114 index rows).

### D8A — Visit Visa Athlete (Multiple Entry) / Visa Olahraga (Atlet) — and D8B — Sports Official / Visa Olahraga (Ofisial)

- **catalog_entry (both):** Multiple-Entry Visit | purposes: OTHER (non-commercial sport: government-invited events, international championships, events by international sports organizations — D8A athlete, D8B official), TOURISM, FAMILY | MULTIPLE | FIXED_DAYS **60/entry** | extension: **NOT allowed** ("tidak bisa diperpanjang atau dialihkan") | prohibited: standard D prohibition (no honorarium carve-out — unlike D7) | sponsor_types: SPONSOR_REQUIRED | funds USD 2,000 | PNBP Rp 2.500.000 (1.5M + 1M Verif I)
- **legal_basis:** same stack; live-verified today (populated) + closeout 2026-07-17.
- **uncertainty:** validity duration UNVERIFIED; not in the 114-seed (proposed rows, closeout §2.3/§2.4).

### D14 — Visit Visa Film Production (Multiple Entry) / Visa Kunjungan Pembuatan dan Produksi Film

- **catalog_entry:** Multiple-Entry Visit | purposes: OTHER (film, music video, reality show, documentary, TV/radio production using Indonesian locations), TOURISM, FAMILY | MULTIPLE | FIXED_DAYS 60/entry (→180) | extension: allowed → 180/entry | prohibited: standard D prohibition | sponsor_types: SPONSOR_REQUIRED | special doc: **filming location permit from the relevant government institution** | funds USD 2,000; tiers 1Y/2Y; PNBP Rp 5.0M / 7.0M (Verif II)
- **legal_basis:** same stack; […/D14](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D14) — live today.

### D17 — Visit Visa Audit, QC & Inspection (Multiple Entry) / Visa Kunjungan Audit, Kendali Mutu, dan Inspeksi Perusahaan

- **catalog_entry:** Multiple-Entry Visit | purposes: OTHER (audit, production quality control, inspection at Indonesian company branches — closest engine vocab: BUSINESS_MEETINGS is a stretch, keep OTHER), TOURISM, FAMILY | MULTIPLE | FIXED_DAYS 60/entry (→180) | extension: allowed → 180/entry | prohibited: standard D prohibition | sponsor_types: SPONSOR_REQUIRED | special doc: invitation letter from government institution or private entity as activity organizer | funds USD 2,000; tiers 1Y/2Y; PNBP Rp 5.0M / 7.0M (Verif II)
- **legal_basis:** same stack; […/D17](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D17) — live today.

### D4 — Visit Visa Government Assignment / Visa Kunjungan Penugasan Pemerintah — ⚠ PAGE EMPTY TODAY

- Catalog row (bonifica KEEP, official label 'VISA PENUGASAN PEMERINTAH…' — actually "Penugasan Pemerintah", per-code-verified with specific title 2026-07-17). **Today 2026-07-24 the per-code page returns the empty-body signature** (39,206 bytes, 1× "Data Belum Tersedia") — byte-comparable to the B211A known-dead control (39,201 bytes), vs 57–59KB populated siblings. **D8's parent page shows the identical empty signature today** while D8A/D8B are live. Change signal vs 2026-07-17, cause unknown (withdrawal / CMS maintenance). **Fact-base: all D4 and parent-D8 facts UNVERIFIED pending re-probe; do not author rules on either until the pages repopulate; keep catalog rows but gate them.** Family-pattern inference (60d/entry, extendable, USD 2,000, sponsor-filed for D4 government duty) is NOT asserted.

---

## Existing-content discrepancies found (rule-authoring agent: do NOT inherit these)

1. `apps/backend-rag/backend/services/visa_check/catalogue.py:229-241` — **D12 `duration_days=365, extensions=(1, 365)` contradicts the official page** (180/entry, extend once +180, max 12mo/entry, never convertible).
2. `catalogue.py:216-228` — **D2 `extensions=(0,0)` "re-enter instead of extending" contradicts the official page** (extendable in 60d increments to 180/entry). D2 purposes also mislabeled (`WORK_REMOTE, INVESTOR` — official D2 is business meetings; remote work unaddressed; investment is D12).
3. `apps/backend-rag/scripts/generate_visa_cards.py:405-454` — **D1 card factually wrong**: USD 5,000 funds (official: USD 2,000), "no extension, must exit after 60 days" (official: extendable to 180), passport 18 months (official: 6), price IDR 5–7M (SSOT: 6/8/12.9M).
4. `generate_visa_cards.py:456-507` — **D12 card wrong**: USD 2,000 funds (official: **USD 5,000** — the two cards have the figures swapped), "Extendable +60 days (max 240/entry)" (official: +180, max 12mo), "Sponsor/guarantor letter" required (official: no sponsor for D12).
5. `apps/backend-rag/backend/services/visa_check/pricing_bridge.py:48` — D2's first price hint is `"D12 Business Investigation (1 Year)"` → fuzzy-matches D12's price onto D2 (already flagged in `docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md:103`); real D2 rows exist in the JSON (6.5M/9M).
6. `apps/backend-rag/backend/tests/services/visa_engine/gold_harness/fixtures/gold_rule_pack.json:549-591` — the "D1" fixture is synthetic and regulatory-wrong (MEDICAL, SINGLE entry, 2×30d extensions, pricing key `d1_medical`). Do not mine it for D1 facts.
7. D1 5Y Bali Zero price split: JSON SSOT **12.900.000** vs seed `seed_visa_types_complete_2026.py` + `migration_122` **14.000.000** — unresolved; PricingTool JSON is SSOT per AGENTS.md, but flag for owner.
8. The official ITK page's own *Dasar Hukum* block is stale: cites the **revoked** Kepmen M.HH-02.GR.01.04/2023 and omits PP 45/2024 — its extension table remains the operative popularization (consistent with per-code pages), but cite per-code pages where they differ.

## UNVERIFIED items (explicit)

- Exact Kepmen in-force day (2025-06-01 brief vs 2025-06-02 repo panel) — Kepmen PDF unread (WAF).
- D212 → D-series split mapping (secondary only).
- D7/D7A/D7B/D8A/D8B visa validity durations (pages show no 1/2/5Y tier).
- D12 "atau 2 tahun" cumulative-stay clause (conflicts with 12-month per-entry cap) — HUMAN_REVIEW.
- Who files extensions for no-guarantor D1/D2/D12 holders (page boilerplate vs ITK page "jika menggunakan Penjamin").
- D4 and parent-D8: entire fact set (pages empty today).
- Calling-visa state list exact membership (7 vs 8 conflict).
- Remote-work treatment on any D code (official pages silent; prohibition is on Indonesian-sourced income only) — owner decision needed before encoding REMOTE_WORK anywhere in the family.
## Adversarial review

Gemini 3.1 Pro (High), 2026-07-24 — SHIP. Bonus findings now tracked: the lane caught TWO LEGACY-SYSTEM DATA BUGS (D12/D1 swapped proof-of-funds values and synthetic D1 fixtures in the legacy catalog) — the new pack must NOT inherit them; filed for the catalog owner. The "D12 diaspora" marketing myth is authoritatively refuted (diaspora products are E31/E32 VITAS). None survived, 0 blocking.
