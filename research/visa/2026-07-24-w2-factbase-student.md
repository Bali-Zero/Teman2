---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: gemini
---

All evidence gathered. Compiling the fact-base.

---

# FACT-BASE — Student family (E30 + study-adjacent codes), Visa Oracle v2 RulePack factory

**Lane:** Student codes (formal education KITAS). **As-of:** every fetch/extraction below was done live **2026-07-24**. **Scope note:** the formal-education KITAS family in the 110-index is E30/E30A/E30B/E30E/E30F. The "language/dharma variants" from the lane brief do **not** exist as E-series codes in the 110-index — they live in the C-series visit visas (C9/C9A/C9B); internships are C22/C22A/C22B. Both adjacency sets are included below because they answer the lane's internship/language/dharma questions. Confirmed against repo catalog: `apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py` (E30 ×5, C9 ×3, C22 ×3) and `research/visa/2026-07-17-visa-catalog-bonifica-110-remap.md` (all five E30 codes KEEP, per-code page titles exact-matched).

**Primary sources extracted in full this session (PDF → text, on disk in /tmp):**
- Kepmen M.IP-08.GR.01.01/2025 (110-index), signed 2025-05-02, dictum KELIMA: in force 30 days after signing → **2025-06-01**. [kemenimipas.go.id PDF](https://kemenimipas.go.id/attachments/2025/peraturan/20250813_09_Kepmen_No_M.IP-08.GR.01.01_Th_2025_Tentang_Klasifikasi_Visa.pdf). Dictum KEEMPAT revokes M.HH-02.GR.01.04/2023 (→ B211* and all 2023-letter codes as *classifications* are dead; see legacy_codes).
- Permenkumham 22/2023 (Visa dan Izin Tinggal), [BPK PDF](https://peraturan.bpk.go.id/Download/330147/Permenkumham%20Nomor%2022%20Tahun%202023.pdf) — Pasal 33, 42, 79, 105, 113–115, 201 extracted verbatim.
- Permenkumham 11/2024 (amendment), [BPK PDF](https://peraturan.bpk.go.id/Download/344251/Permenkumham%20Nomor%2011%20Tahun%202024.pdf) — Pasal 105(7) replacement + Pasal 86A/94A/94B (bridging).
- Permenimipas 3/2025, [BPK PDF](https://peraturan.bpk.go.id/Download/378164/Permen%20Imipas%20Nomor%203%20Tahun%202025.pdf) — diaspora-focused; its Pasal 45 revokes only Pasal 43, 45, 52–55 of 22/2023 (none touch students; Pasal 42 and the bridging articles remain in force).
- [imigrasi.go.id E30A](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30A) and [E30B](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30B) per-code pages (fully populated); [evisa.imigrasi.go.id student FAQ](https://evisa.imigrasi.go.id/front/faq/08cdfd2e-873e-4de7-9eeb-8f485828c155) (official, English, prohibition list).
- UU 6/2011 Pasal 48/54/56/122 via [bphn.go.id PDF](https://bphn.go.id/data/documents/11uu006.pdf), [imigrasi.go.id/uu_imigrasi/bab-5](https://www.imigrasi.go.id/uu_imigrasi/bab-5), [indonesia.go.id](https://indonesia.go.id/layanan/keimigrasian/sosial/izin-tinggal-bagi-orang-asing-di-indonesia).

**Kepmen E30-family legal text (verbatim, Lampiran pp. 57–60):** all five codes share Hak = (1) education activities, (2) bring family per immigration regs, (3) exit/re-enter while IMK valid, (4) tourism/shopping/family-friends; Larangan = (1) overstay, (2) selling goods/services, (3) *"Melakukan kegiatan lain selain jenis kegiatannya … kecuali telah melakukan pengajuan **rangkap jenis kegiatan** atau **perubahan jenis kegiatan**"*. No "bekerja" right is granted anywhere in the family (contrast E31A, whose Hak 1 explicitly allows work).

---

### E30 — Education Visa (umbrella) / Visa Pendidikan
- catalog_entry: LIMITED_STAY | [STUDY] | SINGLE (visa, 90-day validity to enter; IMK on the auto-issued ITAS gives MULTIPLE re-entry while ITAS valid — PP 40/2023 Pasal 32; UU 63/2024 MERP integration) | stay_policy: ITAS 1 or 2 years from arrival (Permenkumham 22/2023 Pasal 105(7) as replaced by 11/2024: 1/2/**4** years permitted family-wide; imigrasi operationalizes 1/2 on E30A, 1/2/4 on E30B) | extension: allowed, per extension ≤ LoA study duration (Pasal 113(4)), online via evisa.imigrasi.go.id; student extensions decided at Kepala Kantor level (Pasal 114(1)) | prohibited: work/employment; selling goods/services; receiving wages/rewards from Indonesian persons/corporations ([evisa FAQ](https://evisa.imigrasi.go.id/front/faq/08cdfd2e-873e-4de7-9eeb-8f485828c155) items 7.4–7.6); political activity (izin belajar declaration) | sponsor_types: [EDUCATION, INDIVIDUAL_WNI] (Pasal 42(1)(b): "Korporasi/lembaga pendidikan … atau warga negara Indonesia") | legacy_codes: [E30 (2023-classification umbrella)]
- eligibility_rules:
  - {HARD_FILTER, intent.purposes, intersects, [STUDY], NO_PURPOSE_OVERLAP, on_unknown: BLOCK}
  - {ELIGIBILITY, study.admission_confirmed, eq, true, ADMISSION_LETTER_REQUIRED, on_unknown: NEEDS_INPUT} — "bukti yang menyatakan Orang Asing diterima pada Korporasi/lembaga pendidikan di Indonesia yang menjelaskan jangka waktu lama pendidikan" (Pasal 42(2))
  - {ELIGIBILITY, study.sponsor_confirmed, eq, true, GUARANTEE_LETTER_REQUIRED, on_unknown: NEEDS_INPUT} — matches gold-pack `el-e30-student`
  - {ELIGIBILITY, study.funds_usd (proposed fact), gte, 2000, LIVING_COST_USD2000, on_unknown: NEEDS_INPUT} — bank statement last 3 months, applicant's **or sponsor's** name (imigrasi page; amount set by Dirjen per Pasal 42(3))
  - {ELIGIBILITY, person.passport_validity_months (proposed), gte, 6, PASSPORT_6M, on_unknown: NEEDS_INPUT}
  - {HUMAN_REVIEW, study.izin_belajar_issued (proposed), eq, true, STUDY_PERMIT_KEMDIKBUD, on_unknown: HUMAN_REVIEW} — education-ministry gate, not in the immigration doc list; required in practice for higher-ed (see E30B)
  - {HUMAN_REVIEW, person.nationalities, intersects, [AF, GN, IL, CM, KP, LR, NG, SO], CALLING_VISA_OVERLAY, on_unknown: PASS} — 8-nation overlay per bonifica §5 (VERIFIED-OFFICIAL); ≥2-year ITAS extensions for calling-visa nationals need Dirjen approval (Pasal 114(2))
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 Lampiran B row 6 "Mengikuti pendidikan" (eff. 2025-06-01) · Permenkumham 22/2023 Pasal 33(2)(g), 42 · Permenkumham 11/2024 (Pasal 105(7) replacement) · PP 45/2024 (PNBP) · UU 6/2011 Pasal 48 (as amended UU 63/2024) — all checked 2026-07-24.
- uncertainty: the bare-E30 imigrasi page exists (title confirmed) but content is **"Data Belum Tersedia"** as of 2026-07-24 — treat E30 as family container; sub-codes are the sellable products.

### E30A — Primary/Secondary Education Visa / Visa Pendidikan Dasar dan Menengah
- catalog_entry: LIMITED_STAY | [STUDY] | SINGLE + IMK multiple re-entry | stay: 1 or 2 years (imigrasi page: *"1 atau 2 tahun"*; 4-year option NOT offered on this page) | extension: allowed, ≤ LoA period, online | prohibited: same family set | sponsor_types: [EDUCATION, INDIVIDUAL_WNI] | legacy_codes: [E30A (2023)]
- eligibility_rules: umbrella set, **plus**
  - {HARD_FILTER, study.level, in, [PRIMARY, SECONDARY], LEVEL_BAND_DASMEN, on_unknown: NEEDS_INPUT} — Kepmen: *"jenjang pendidikan dasar dan menengah"*; imigrasi: *"sekolah menengah atas dan jenjang di bawahnya"* (SMA and below). **No age limit exists in immigration law** — the band is by education level, not applicant age.
  - {HUMAN_REVIEW, derived.age_years, lt, 18, MINOR_CONSENT_GUARDIAN, on_unknown: PASS} — **UNVERIFIED exact doc set** (see uncertainty): no primary text found for parental-consent/guardian documents; sponsor may be the school or a WNI individual (Pasal 42(1)(b)); standard practice (agency tier) is parental consent letter + birth certificate + parents' passports + local guardian arrangement. Rule should route minor E30A applicants to human review, never auto-approve.
- legal_basis: same chain + [imigrasi.go.id E30A page](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30A) (fees: 1 yr Rp6.000.000 / 2 yr Rp8.500.000; components visa Rp500k + ITAS Rp3jt/Rp5jt + IMK Rp1.5jt/Rp2jt + Verifikasi I Rp1jt; visa validity 90 days; processing 5 working days after payment) — checked 2026-07-24.
- uncertainty: minor consent/guardian doc requirements UNVERIFIED from primary sources; whether the 4-year ITAS (legal since 11/2024) will be offered for dasar/menengah operationally — currently not on the page.

### E30B — Higher Education Visa / Visa Pendidikan Tinggi
- catalog_entry: LIMITED_STAY | [STUDY] | SINGLE + IMK multiple re-entry | stay: **1, 2, or 4 years** from arrival | extension: allowed, ≤ LoA study period | prohibited: family set (explicit on evisa FAQ) | sponsor_types: [EDUCATION, INDIVIDUAL_WNI] | legacy_codes: [**E30B, E30C, E30D (2023)**] — the 2023 master's (E30C) and doctoral (E30D) codes were merged into E30B in the 110-index; Kepmen E30B text: *"pendidikan tinggi yang mencakup program pendidikan diploma, sarjana, magister, atau doktor"*. Sources for the old codes: [ITS 2024 guidebook](https://www.its.ac.id/international/wp-content/uploads/sites/66/2024/03/Visa-Guidebook-for-International-Students_2024.pdf), [balisuperhost 2024 brochure](https://balisuperhost.com/wp-content/uploads/2024/05/Legal-Brochure-Package.pdf), [imigrasi.go.id leftover page listing E30C/E30D names](https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian/perpanjangan-izin-tinggal-tetap) (VERIFIED-SECONDARY — the 2023 Kepmen PDF itself is image-scan only, not text-extractable).
- eligibility_rules: umbrella set, **plus**
  - {HARD_FILTER, study.level, in, [DIPLOMA, UNDERGRADUATE, MASTERS, DOCTORAL], LEVEL_BAND_DIKTI, on_unknown: NEEDS_INPUT}
  - {HUMAN_REVIEW, study.izin_belajar_issued, eq, true, STUDY_PERMIT_KEMDIKBUD, on_unknown: HUMAN_REVIEW} — Kemendikbudristek study permit via izinbelajar.kemdikbud.go.id (Ditjen Diktiristek, Direktur Pembinaan Kelembagaan PT); docs: university application letter, LoA, passport, **signed declaration not to work and not to join political activities**, sponsor statement, financial guarantee, health certificate ([ITB](https://partnership.itb.ac.id/visa-e30b-for-study-periods-longer-than-2-months/), [UNSRI guide](https://cdnc.heyzine.com/files/uploaded/8a81aa422d40bdce1559fb08d0c927af3244e207.pdf), [FTSP Trisakti quoting the portal](https://ftsp.trisakti.ac.id/wp-content/uploads/sites/16/2024/05/JUKNIS-FTSP-2023-2024-TEKNIK-SIPIL.pdf), [UMA handbook showing the issued permit with "tidak bekerja" condition](https://kui.uma.ac.id/wp-content/uploads/2025/03/Foreign-Student-Handbook.pdf)). Universities process it; the permit letter is cc'd to the immigration office.
- legal_basis: same chain + [imigrasi.go.id E30B page](https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E30B) (fees: 1 yr Rp6.000.000 / 2 yr Rp8.500.000 / **4 yr Rp12.000.000** — components 500k + ITAS 3/5/7jt + IMK 1.5/2/3.5jt + 1jt) · Permenkumham 11/2024 Pasal 105(7) (verbatim: *"a. 1 tahun; b. 2 tahun; atau c. 4 tahun"*) — checked 2026-07-24.
- uncertainty: the izin belajar's **governing regulation number** is UNVERIFIED (portal + university practice verified; no specific Permendikbudristek number pinned). University-level operational asks beyond the immigration list (health insurance, good-conduct certificate — ITB) are institution practice, not immigration law. ITS 2025 guidebook still routes exchange students via E30B *"including student exchange program"* — operational overlap with E30F.

### E30E — SEZ Education Visa / Visa Pendidikan Kawasan Ekonomi Khusus
- catalog_entry: LIMITED_STAY | [STUDY] | (assume family defaults — UNVERIFIED) | prohibited: family set | sponsor_types: [EDUCATION] | legacy_codes: [E30E (2023)]
- eligibility_rules: umbrella set **plus** {HARD_FILTER, study.institution_in_kek (proposed fact), eq, true, KEK_INSTITUTION_ONLY, on_unknown: NEEDS_INPUT} — Kepmen: *"Mengikuti pendidikan pada lembaga pendidikan di Kawasan Ekonomi Khusus"*.
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 Lampiran (row verbatim above); Kepmen preamble grounds KEK codes in **PP 40/2021 tentang Penyelenggaraan Kawasan Ekonomi Khusus** — checked 2026-07-24.
- uncertainty: imigrasi per-code page exists (title confirmed) but content **"Data Belum Tersedia"** as of 2026-07-24 — fees, stay options, any KEK-specific facilitations all UNVERIFIED. Do not hardcode.

### E30F — Student Exchange Visa / Visa Pertukaran Pelajar
- catalog_entry: LIMITED_STAY | [STUDY] | (assume family defaults — UNVERIFIED) | prohibited: family set | sponsor_types: [EDUCATION] | legacy_codes: [E30F (2023)]
- eligibility_rules: umbrella set **plus** {HARD_FILTER, study.is_exchange_program (proposed fact), eq, true, EXCHANGE_PROGRAM_ONLY, on_unknown: NEEDS_INPUT} — Kepmen: *"pendidikan dasar, menengah, dan tinggi … dalam rangka pertukaran pelajar"* (covers all levels, unlike E30A/E30B split).
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 Lampiran (row verbatim) — checked 2026-07-24.
- uncertainty: page content not yet populated (2026-07-24); exchange-specific document set (sending-institution letter, inter-institution agreement/MoU) UNVERIFIED. Operational reality: universities currently route exchange students through E30B (ITS 2025 guidebook) — flag for human review rather than auto-routing.

---

## Adjacency set A — short study / language / dharma (visit visas, NOT KITAS)

**C9 / C9A / C9B** — *Visa Kunjungan Studi Singkat / Pelatihan Singkat Keagamaan / Pelatihan Singkat Bahasa Indonesia*. Kepmen Lampiran rows (verbatim extracted): C9 = "studi banding, kursus singkat, dan pelatihan singkat"; C9A = short religious training; C9B = short Indonesian-language training. Larangan includes **"Menerima imbalan, upah, atau sejenisnya dari perorangan atau korporasi di Indonesia"** (no wages). Single-journey visit visas (Kepmen §A.4). These are the **only** language/dharma study products in the 110-index — formal long-term language/religious *KITAS* variants do not exist; engine must not offer E30 for short courses. Duration/extension specifics for C9 family: generic single-journey visit frame (180 days initial per PP 40/2023 Pasal 136 for visit visas; extension specifics for C9 not pinned this session — UNVERIFIED).

## Adjacency set B — internships (the "can students intern" answer)

**C22 / C22A / C22B** — *Visa Kunjungan Pemagangan / Akademik / Kompetensi* (Kepmen §A.4, verbatim extracted): C22 = internship at educational institution, company, or other place; C22A = internship **required by a foreign academic curriculum**; C22B = competency development at a company/office. Verified rules:
- Document: internship agreement or letter from the organizing institution (Permenkumham 22/2023 Pasal re visit-visa docs: *"untuk pemagangan, berupa perjanjian pemagangan atau keterangan dari instansi pemerintah atau lembaga swasta selaku penyelenggara kegiatan"*).
- Extension: **180 days per extension, total stay ≤ 12 months** (Permenkumham 22/2023 Pasal 79(6), verbatim). No wages allowed (Kepmen Larangan).
- Repo guide corroborates: `apps/backend-rag/scripts/generated_guides/immigration/visto_c12_c18_c22_guida_2025.txt` (C22 section).

**Work/internship verdict for E30 holders (the lane's priority question):**
1. E30 = **no work, no paid internship, no wages** — triple-grounded: evisa FAQ prohibition list; Kepmen Larangan; Kemendikbudristek izin belajar signed declaration "tidak akan bekerja selama belajar di Indonesia". Criminal exposure: UU 6/2011 **Pasal 122 huruf a** — misuse of stay permit, up to 5 years + Rp500jt ([ANTARA](https://www.antaranews.com/berita/4975533/imigrasi-surabaya-amankan-tujuh-wna-terkait-izin-tinggal)); administrative exposure: Pasal 75 deportation.
2. The only in-permit mechanism to add an activity is **rangkap jenis kegiatan / perubahan jenis kegiatan** (Permenkumham 22/2023 **Pasal 201**; verbatim: rangkap *"dapat dilaksanakan tanpa ada pembatasan selama memenuhi syarat"*, Dirjen approval, ≤5 working days). No student-specific ban exists in the text, but approval is discretionary and there is **no published facility** for student→work rangkap → **HUMAN_REVIEW, never auto-offer**. UNVERIFIED in practice.
3. Structured internships route through **C22 family** (above), not the E30.

## Graduation transition edges (student → work)

1. **Perubahan jenis kegiatan** (Pasal 201(1): no new permit issued, continues existing ITAS; needs the new activity's document set — for work: employer sponsor + RPTKA/notification + DKP-TKA). In-country E30→E23 switch is legally possible via this mechanism; discretionary → HUMAN_REVIEW. Note precision: this is NOT "alih status" in the UU sense — UU 6/2011 **Pasal 56(2)** defines alih status as ITK→ITAS and ITAS→ITAP only.
2. **Bridging permit** (ITK peralihan, Permenkumham 11/2024 Pasal 86A/94A/94B; survives Permenimipas 3/2025 partial revocation — repo closeout §3.2a, primary-verified): 60 days, non-extendable; ITAS holders eligible; file+pay ≥3 (calendar) days before ITAS expiry; overstay shield; onshore-only, voided on any exit; issuance ≤3 working days. Canonical gap-shield when the work permit isn't ready at graduation.
3. **EPO + offshore re-application** (classic): exit, employer secures RPTKA, new E23 VITAS.
4. **No ITAP shortcut**: UU 6/2011 **Pasal 54(1)** alih-status-to-ITAP list = rohaniwan/pekerja/investor/lanjut usia (+family, ex-WNI) — **pendidikan is not listed**; a student must first convert to a qualifying ITAS.
5. **No graduate job-seeker visa** exists in the 110-index (checked all Kepmen rows this session) — do not offer one.

## Cross-cutting rules for the pack

- Dependents: E30 holders may bring family (Kepmen Hak #2 all five codes) → dependents ride E31B (spouse of ITAS holder) / E31E (child of ITAS holder) — family lane's codes.
- Calling-visa overlay: bonifica lists **8** nations (Afghanistan, Guinea, Israel, Cameroon, North Korea, Liberia, Nigeria, Somalia); the bridging doc's corner record says **7** — discrepancy flagged; use HUMAN_REVIEW either way.
- Fees: PP 45/2024 is the operative PNBP (its lampiran is scan-only per repo note; figures above are from the authoritative imigrasi.go.id product pages). Old PP 28/2019-era pricing (ITS 2024: US$150 + Rp2.7jt) is superseded.
- Kepmen effective date: dictum KELIMA = 30 days post-signing → **2025-06-01** (one top-tier secondary, [SSEK/Lexology](https://www.lexology.com/library/detail.aspx?g=0b461e79-00fa-47ad-a6a8-f2ce56335b15), says June 2 — immaterial 1-day conflict, flagged).
- Engine alignment: gold-pack `el-e30-student` (STUDY ∩ admission ∩ sponsor → SUPPORT; on_unknown NEEDS_INPUT) matches the verified law; persona `10_student_blocked_unknown_eligibility` behavior confirmed correct against Pasal 42. Sponsor vocabulary should be extended: current gold pack has only `EDUCATION`; law allows `INDIVIDUAL_WNI` too (Pasal 42(1)(b) angka 2).
- Mapping notes: engine VisaPurpose has no INTERNSHIP — suggest C22A → STUDY, C22B → OTHER (flag for rule-author); C9/C9A/C9B → STUDY as visit products with no-wages prohibition.

**Global UNVERIFIED register:** (1) minor consent/guardian doc set; (2) izin belajar governing regulation number; (3) E30E/E30F operational details (fees/stay/docs) — pages unpopulated; (4) student rangkap/perubahan approval practice; (5) E30C/D→E30B merge rests on strong secondary sources (2023 Kepmen PDF is image-only); (6) 7-vs-8 calling-visa states; (7) C9-family extension specifics.
## Adversarial review

Gemini 3.1 Pro (High), 2026-07-24 — FIX-FIRST, 3 findings, ALL ACCEPTED as authoring constraints: (1) E30A minor-consent check `on_unknown: PASS` → must be `NEEDS_INPUT` (never silently skip guardian consent); (2) bridging-window-missed consequence (EPO + offshore re-application) must be explicit in the affected rules; (3) E30B Kemendikbudristek Izin Belajar is a de-facto HARD dependency of the sponsor letter → model as ELIGIBILITY-hard, not soft HUMAN_REVIEW.
