# PPh 21 Monthly Tax Filing Deadlines Q3 2026 — PT PMA with WNA Staff

**Date**: 2026-05-09 · **Domain**: tax · **Author**: deep-researcher (Antonello/Bali Zero) · **Status**: draft
**partial**: false · **LLMs used**: Claude Opus 4.7 (synthesis) + WebSearch/WebFetch (7 sources) + DeepSeek Reasoner (red-team)
**devils-advocate**: 7 passes via DeepSeek-only (P1-P7, 2026-05-10) reached "regulatorially solid" status. **+ Pass 8 via NB-grounded v2 (2026-05-10 13:30)**: corrected hallucinated KEP series — KEP-37/PJ/2026, KEP-6/PJ/2026, KEP-9/PJ/2026, KEP-11/PJ/2026 all confirmed HALLUCINATIONS via NB-4 ground truth. Replaced with verified **KEP-55/PJ/2026** (real Coretax-transition penalty waiver, eff. 27 March 2026). Status: `draft` pending JDIH primary verification of: PMK 81/2024 text + predecessor (242/2014 vs 243/2014), PMK 168/2023 Lampiran A, SKB 3 Menteri 2026 decree number, PER for Coretax filing platform mandate.
**Raw sources**: /tmp/deep-research-pph21-q3-deadlines-livetest-sources.txt
**DA report (latest)**: /tmp/devils-advocate-pph21-q3-deadlines-livetest-report.json
**DA report (previous)**: /tmp/devils-advocate-pph21-q3-deadlines-livetest-deepseek.json

## Question

Indonesia PPh 21 monthly tax filing deadlines Q3 2026 for PT PMA with 5+ WNA staff.

## TL;DR (3 bullets)

> **Scope**: deadlines falling in calendar Q3 (Jul–Sep), covering masa pajak Jun–Aug. The alternative reading "masa pajak Q3 = Jul/Aug/Sep with deadlines in Aug/Sep/Oct" requires a separate research pass — confirm with the requesting party before use.

- Q3 2026 effective deadlines: setor **15 Jul / 18 Aug† / 15 Sep**; lapor **20 Jul / 20 Aug / 21 Sep‡** — two shifts: †15 Aug shifts to 18 Aug (Sat+Sun+Proklamasi); ‡20 Sep shifts to 21 Sep (Sunday).
- PMK 81/2024 is the current governing regulation (per secondary sources, replaces a prior PMK in the 242/2014 — 243/2014 series for PPh 21 payment deadlines and partially supersedes PMK 9/2018 — exact predecessor PMK and supersession scope unverified; secondary aggregators conflate "PMK 242" and "PMK 243" — confirm during JDIH lookup); SPT Masa PPh 21 are filed via Coretax DJP from 1 Jan 2026 (regulatory instrument creating the Coretax mandate not verified in this run — internal use only).
- No Indonesian regulation creates a special PPh 21 regime for PT PMA with "5+ WNA employees"; obligations are identical to any pemotong pajak — the distinction that matters is per-employee SPDN vs SPLN status.

## Key citations (secondary sources — pending primary verification)

> All passages below were retrieved via secondary aggregators (Ortax, Pajakku, MUC) — primary PMK PDFs at `pajak.go.id` were NOT directly fetched. Treat as **plausible content, unverified citation chain**. Re-validate against the JDIH primary text (`jdih.kemenkeu.go.id`, `jdih.pajak.go.id`) before any client deliverable.

- **PMK 81/2024** (per Ortax / Pajakku) — "penyetoran PPh Pasal 21 yang dipotong oleh Pemotong PPh 21/26 harus disetor paling lama tanggal 15 bulan berikutnya setelah masa pajak berakhir"
- **PMK 81/2024** (per Ortax / Pajakku) — "Pelaporan PPh 21 paling lambat dilakukan tanggal 20 bulan berikutnya"
- **PMK 81/2024** (per Ortax / Pajakku) — "Apabila bertepatan dengan hari libur, maka pelaporan dan penyetoran mundur ke hari kerja berikutnya. Hari libur yang dimaksud yaitu hari Sabtu, hari Minggu, libur nasional, hari yang diliburkan untuk penyelenggaraan pemilihan umum, atau cuti bersama secara nasional."
- **PMK 168/2023** (per practitioner summaries) — "Tarif efektif langsung dikenakan atas penghasilan bruto yang diterima WNA dalam sebulan" (for SPDN-classified foreign workers)
- **PMK 168/2023 — bukti potong obligation** (via WebSearch summary; muc.co.id returned 403, primary PDF not fetched) — paraphrase: pemotong pajak tetap diwajibkan menyampaikan Bukti Pemotongan PPh 21/26 kepada penerima penghasilan. **Specific Pasal/ayat pinning (earlier draft cited "Pasal 4 ayat (1)") removed — the WebSearch summary did not provide a verified ayat number and the primary URL returned 403.** Treat as "the obligation exists per PMK 168/2023" without ayat citation until JDIH PDF is consulted.
- **SKB 3 Menteri 2026 (Hari Libur Nasional dan Cuti Bersama)** — `[NUMBERS_PENDING_VERIFICATION]`. Earlier draft cited "Nomor 1497/2025, 2/2025, 5/2025" sourced from a WebSearch summary; DeepSeek red-team flagged that the actual 2026 SKB is more likely Nomor 1504/2025 + 3/2025 + 6/2025 (released Oct 2025). NEITHER trio is independently confirmed against the SKB PDF in this research run. The HOLIDAY DATES themselves (17 Agu Proklamasi, 25 Agu Maulid) cross-checked against Liputan6 + multiple kalender sources are reliable; the SKB DECREE NUMBER citation is not. Verify against `kemenag.go.id` SKB PDF before any client deliverable.
- **KEP DJP — Coretax-transition penalty waiver**: the verified KEP is **KEP-55/PJ/2026** (effective 27 March 2026), which extends SPT Tahunan 2025 deadline + waives sanctions through 30 April 2026 (NB-4 ground-truth verified 2026-05-10). **HISTORICAL CORRECTION**: earlier drafts of this file cited "KEP-37/PJ/2026", "KEP-6/PJ/2026", "KEP-9/PJ/2026", "KEP-11/PJ/2026" — DeepSeek red-team via NotebookLM ground-truth verification (2026-05-10) confirmed all four are HALLUCINATIONS (not present in `jdih.pajak.go.id`, no DJP press references). The real Coretax-transition penalty waiver is KEP-55/PJ/2026. Do NOT conflate with KEP-71/PJ/2026 (different domain — SPT Tahunan PPh Badan corporate extension). For client work concerning **SPT Masa PPh 21 specifically** (this research's scope, NOT Tahunan), no DJP-numbered transition waiver was identified for monthly periods — refer to general DJP Coretax-transition announcements without quoting a KEP number until JDIH lookup confirms.

## Findings

### 1. Q3 2026 Exact Deadlines (with holiday/weekend shifts)

The base rule: payment (setor) by the 15th, reporting (lapor) by the 20th, of the month following the masa pajak. When either date falls on Saturday, Sunday, national holiday, or cuti bersama, it shifts to the next working day. This rule derives from PMK 81/2024 (per secondary sources Ortax, Pajakku — primary text not directly fetched; verify at pajak.go.id).

**National holidays confirmed in Q3 window (cross-checked Liputan6 + multiple kalender sources; SKB 3 Menteri decree number pending JDIH lookup):**

- 17 Agustus 2026 (Monday) — Proklamasi Kemerdekaan
- 25 Agustus 2026 (Tuesday) — Maulid Nabi Muhammad SAW (lunar — confirmed by SKB; government may adjust ±1 day if hisab differs from rukyat near date)
- July 2026: zero national libur nasional. Idul Adha 1447H falls **27 May 2026** (per BHR Kemenag rukyat, well before Q3) — does NOT impact masa Juni setor 15 Jul. No Tahun Baru Islam 1448H within Q3 (1 Muharram 1448H projected ~mid-June 2026, also pre-Q3). Verified zero Q3 lunar conflicts.
- September 2026: zero national libur nasional.

> **Verification gap**: lunar holiday dates depend on government rukyat decision near the date itself. The 25 Aug Maulid figure could shift ±1 day if SKB is amended; the deadline arithmetic (lapor 20 Aug, setor 18 Aug) is INSULATED from any such shift because both fall before 25 Aug. Idul Adha 27 May is INSULATED from any shift up to ~+18 days before it would touch Q3.

**Calculated effective deadlines:**

| Masa Pajak   | Setor nominal | Day       | Adjusted setor  | Reason                        | Lapor nominal | Day      | Adjusted lapor  | Reason     |
| ------------ | ------------- | --------- | --------------- | ----------------------------- | ------------- | -------- | --------------- | ---------- |
| Juni 2026    | 15 Jul 2026   | Wednesday | **15 Jul 2026** | No shift                      | 20 Jul 2026   | Monday   | **20 Jul 2026** | No shift   |
| Juli 2026    | 15 Aug 2026   | Saturday  | **18 Aug 2026** | Sat→Sun→Proklamasi Mon→Tue 18 | 20 Aug 2026   | Thursday | **20 Aug 2026** | No shift   |
| Agustus 2026 | 15 Sep 2026   | Tuesday   | **15 Sep 2026** | No shift                      | 20 Sep 2026   | Sunday   | **21 Sep 2026** | Sun→Mon 21 |

_The setor shift for masa Juli is triple: Saturday (15 Aug) + Sunday (16 Aug) + Proklamasi Monday (17 Aug) = first available day is Tuesday 18 August 2026._

**Filing platform**: SPT Masa PPh 21/26 are to be submitted via Coretax DJP from 1 Jan 2026 (per DJP announcements + multiple practitioner aggregators); the specific PER/KEP number creating the platform mandate was NOT verified in this research run. Treat as "Coretax is the operative platform" without citing a regulation number; verify the underlying instrument before any client-facing assertion that legacy DJP Online / e-Form is prohibited. Bali Zero internal practice is to file 3 business days before the statutory deadline to absorb Coretax system congestion + bank cut-off times — workflow heuristic, not a regulatory requirement.

### 2. PPh 21 vs PPh 26 — per-employee determination for WNA

The "5+ WNA staff" framing suggests concern about aggregate employer burden. In Indonesian tax law, obligations are determined per employee, not per headcount group.

**For each WNA employee, the employer must determine:**

**SPDN (Subjek Pajak Dalam Negeri)** — triggers PPh 21:

- Holds KITAS or KITAP
- Has been/intends to be in Indonesia >183 days in a 12-month window
- Has family in Indonesia
- Has contract duration >183 days

**SPLN (Subjek Pajak Luar Negeri)** — triggers PPh 26:

- Stays <183 days, no KITAS
- 20% flat final tax on gross Indonesian-source income
- No annual SPT obligation for the employee

This distinction must be made individually for each WNA staff member and can change status mid-year (e.g., if an SPLN crosses the 183-day threshold, they become SPDN from day 1 and PPh 21 applies retroactively).

### 3. TER (Tarif Efektif Rata-rata) for WNA staff under PMK 168/2023

Applicable from January 2024 (fully in force 2026):

- **Months January–November**: TER monthly rate applied directly to gross income
- **Month December (Masa Pajak Terakhir)**: full-year reconciliation using progressive PPh 21 rates (5%–35%)
- WNA SPDN: TER applied on bruto income. **Specific bracket rate intentionally omitted from this research — the earlier draft included a "~34% practitioner estimate" which DeepSeek red-team flagged as a hazardous in-line number that disclaimer cannot neutralize.** For any client payroll, fetch the exact TER rate from PMK 168/2023 Lampiran A bracket matching (a) bruto monthly amount, (b) PTKP status. Do NOT estimate.
- WNA SPLN: flat 20% PPh 26, final, no TER applicable

**Split-payroll trap (high relevance for PT PMA with expats on secondment):** If a WNA works for an Indonesian entity, ALL compensation — whether paid by the Indonesian entity or by the overseas parent — is subject to Indonesian income tax. **Withholding mechanics differ from taxability**: UU PPh Article 21 binds the Indonesian pemotong to withhold on what it actually pays. When the overseas parent pays the WNA directly without reimbursement charge-back to the Indonesian entity, the Indonesian entity mechanically cannot withhold on a disbursement it does not make. Such "shadow payroll" structures require either (a) a deemed-employer / cross-charge arrangement that routes the offshore-paid component through Indonesian payroll, or (b) treaty-based analysis with the WNA's home jurisdiction. The income remains taxable in either case; the operational question is who withholds and how. Consult tax counsel before confirming a withholding workflow for split-payroll WNAs.

### 4. Coretax WNA-specific complications (2026)

**NPWP activation for WNA in Coretax:**

- WNA accesses Coretax using old NPWP + "0" prefix (e.g., old NPWP 01.234.567.8-901.000 → 001.234.567.8-901.000) (per pajaknow.id — single secondary source; verify against Coretax UI before applying to any WNA payroll run)
- PTKP default for WNA: TK/0 (unmarried, no dependents)
- Family status update requires in-person contact with tax office or Kring Pajak under PER-7/PJ/2025

**NIK not registered in Coretax (common for newly-arrived WNA):**

1. Employer enters WNA's NIK in Coretax
2. System flags: NIK not registered
3. Employer may issue bukti potong under a **temporary identifier** until employee completes NIK-NPWP matching. The exact temporary identifier format used by Coretax (whether old-NPWP-with-"0"-prefix per pajaknow, or a system-generated dummy 16-digit per other sources) is contradictory across secondary sources and must be confirmed in Coretax UI before payroll execution. **The earlier draft cited the literal string `9990000000999000` (16 digits) as the temporary NPWP — this string is unverified and contradicts source #8 (pajaknow) which describes only the "+0 prefix" mechanism on the existing 15-digit NPWP. Do NOT use the 16-digit literal in client-facing material until verified in Coretax.**
4. CRITICAL: bukti potong issued under any temporary identifier **will not be recognized as a tax credit by DJP until NIK-NPWP matching is completed** — the credit is suspended (not forfeited): once matching completes and the employer files pembetulan referencing the now-active NIK, the employee can claim the credit against their annual PPh. The exact recognition mechanism (whether DJP back-dates the credit or whether it counts only from the pembetulan date) requires confirmation against PER or DJP circular before any client-facing assertion.
5. Employee must complete NIK-NPWP matching at their tax office (or via Coretax self-service if available)
6. Employer must file SPT corrections (pembetulan) for all periods that used the temporary identifier

This creates operational complexity for PT PMA with 5 WNA staff: if even 1-2 WNA have unresolved NIK issues, the employer accumulates correction obligations.

### 5. Absence of a "5+ WNA employees" regulatory threshold

No regulation reviewed (PMK 81/2024, PMK 168/2023, the Coretax-transition KEP series, PER-7/PJ/2025) creates a special category for employers with 5 or more foreign employees. The question premise should be reframed: PT PMA's obligations are the standard pemotong pajak obligations applied separately to each WNA employee based on their SPDN/SPLN status.

## Numerical analysis

**Deadline shift calculation (Python-verified, 2026-05-09):**

```
National holidays in Q3 window:
  17 Aug 2026 (Mon) = Proklamasi Kemerdekaan [reported SKB 3 Menteri — decree number pending JDIH verification]
  25 Aug 2026 (Tue) = Maulid Nabi Muhammad SAW [reported SKB 3 Menteri — decree number pending JDIH verification]

Masa Juni setor 15 Jul (Wed)  → unchanged → 15 Jul 2026
Masa Juni lapor 20 Jul (Mon)  → unchanged → 20 Jul 2026

Masa Juli setor 15 Aug (Sat)  → +1 Sun 16 Aug (weekend)
                               → +1 Mon 17 Aug (Proklamasi)
                               → +1 Tue 18 Aug → EFFECTIVE 18 Aug 2026
Masa Juli lapor 20 Aug (Thu)  → unchanged → 20 Aug 2026

Masa Ags  setor 15 Sep (Tue)  → unchanged → 15 Sep 2026
Masa Ags  lapor 20 Sep (Sun)  → +1 Mon 21 Sep → EFFECTIVE 21 Sep 2026
```

**INTERNAL HEURISTIC (Bali Zero operational practice — NO regulatory basis; the 3-business-day buffer is a workflow choice, not a DJP advisory):**

|                    | Statutory deadline | Bali Zero internal target | Buffer |
| ------------------ | ------------------ | ------------------------- | ------ |
| Setor masa Juni    | 15 Jul 2026 (Wed)  | **10 Jul 2026 (Fri)**     | 3 BD   |
| Lapor masa Juni    | 20 Jul 2026 (Mon)  | **15 Jul 2026 (Wed)**     | 3 BD   |
| Setor masa Juli    | 18 Aug 2026 (Tue)  | **12 Aug 2026 (Wed)**     | 3 BD   |
| Lapor masa Juli    | 20 Aug 2026 (Thu)  | **14 Aug 2026 (Fri)**     | 3 BD   |
| Setor masa Agustus | 15 Sep 2026 (Tue)  | **10 Sep 2026 (Thu)**     | 3 BD   |
| Lapor masa Agustus | 21 Sep 2026 (Mon)  | **16 Sep 2026 (Wed)**     | 3 BD   |

> All rows carry a 3-BD buffer (counting from the internal target **inclusive** up to but not including the statutory deadline). For masa-Juli specifically, business-day arithmetic is mandatory: the naive "3 calendar days early" count would land on 15 Aug for the 18 Aug setor — and 15 Aug is itself a Saturday, defeating the buffer's purpose. The internal targets 12 Aug (setor) / 14 Aug (lapor) are derived by counting 3 BD backward from the shifted statutory deadlines (18 Aug Tue / 20 Aug Thu), correctly skipping Sat 15 Aug, Sun 16 Aug, and Proklamasi Mon 17 Aug as non-business. Verification: setor masa Juli buffer = {12, 13, 14} (Aug Wed/Thu/Fri) = 3 BD before 18 Aug Tue.

> The internal targets above are NOT enforceable by DJP and have no legal weight — only the statutory column carries penalty risk. The 3-business-day buffer is selected by Bali Zero practice to absorb Coretax system congestion + bank cut-off times + same-day pembetulan opportunity, not derived from any DJP circular.

Note: the naive "3 calendar days early" heuristic (e.g., 15 Aug for an 18 Aug deadline) fails for masa Juli setor because 15 Aug is itself a Saturday. Business-day arithmetic is mandatory for August.

**TER illustrative calculation — INTENTIONALLY DEFERRED:**

- Monthly gross: IDR 50,000,000 (WNA SPDN TK/0)
- TER rate: `[LOOKUP REQUIRED — PMK 168/2023 Lampiran A, TK/0 bracket at IDR 50M gross — not fetched in this research run]`
- Monthly PPh 21 withheld: `[derive from rate above; do NOT use any prior practitioner estimate]`
- December: full-year progressive reconciliation per PPh 21 progressive tariff schedule (PPh 21 brackets — verify current rates against UU PPh / latest PMK before December reconciliation)

## Disagreements / open questions

- **"Q3 2026" definition (SCOPE — INTERPRETATION B ONLY)**: The question asks about "Q3 2026" filing deadlines. Two interpretations exist: (A) masa pajak Q3 = Juli/Agustus/September, with deadlines falling in Aug/Sep/Oct; (B) deadlines that fall in Q3 = payment/reporting dates in Jul/Aug/Sep, covering masa pajak Jun/Jul/Aug. **This research covers ONLY interpretation B** (deadlines in calendar Q3, masa pajak Jun-Aug). For interpretation A (masa pajak Sep, with deadlines setor 15 Oct + lapor 20 Oct 2026), a separate research note is required: nominal 15 Oct (Thu) and 20 Oct (Tue) — both weekdays in 2026, no weekend/holiday shifts apparent, but verify against final SKB 2026 holiday list.
- **Maulid Nabi 25 August**: Confirmed by SKB 3 Menteri decree (Liputan6, multiple sources). Islamic holidays can be adjusted by government closer to date if lunar calculation differs. The 25 August figure is from the formal SKB; the setor and lapor deadlines for masa Juli (18 Aug and 20 Aug respectively) both fall **before** 25 August, so Maulid Nabi does NOT affect Q3 main deadlines in any case.
- **5+ WNA threshold**: No regulation found. If user's question originates from a consultant quoting this threshold, it may refer to internal compliance complexity, not a statutory threshold. Flag to ask client/source.
- **PMK 81/2024 full text**: Not directly fetched; all citations are via secondary sources (Ortax, Pajakku). Secondary sources are internally consistent. Verbatim internal citations should be verified against the primary at pajak.go.id before client-facing use.
- **PMK 168/2023 Pasal 4 ayat (1) citation**: Obtained via WebSearch summary (muc.co.id returned 403). Citation text as written is plausible given context, but not verified against primary PDF. High-stakes claim — verify before client delivery.

## Checklist for action

- [ ] **Verify each WNA's SPDN/SPLN status** against 183-day and KITAS/KITAP criteria — do this before the first Q3 payroll run (latest by end June 2026).
- [ ] **Check Coretax NIK registration for all 5 WNA employees**: login to Coretax, attempt to create bukti potong for each — flag any that return "NIK not registered" and initiate NIK-NPWP matching immediately.
- [ ] **For masa pajak Juni**: settle payment by **15 July 2026** and file SPT Masa PPh 21 by **20 July 2026** — no holiday shifts. Internal safe deadline: 10 Jul (setor), 15 Jul (lapor).
- [ ] **For masa pajak Juli**: payment deadline is **18 August 2026** (NOT 15 Aug — shifts Sat+Sun+Proklamasi). Reporting: **20 August 2026** (no shift). Internal safe deadlines: **12 Aug (setor)**, **14 Aug (lapor)**. Calendar-alert both dates now.
- [ ] **For masa pajak Agustus**: payment **15 September 2026** (no shift). Reporting **21 September 2026** (NOT 20 Sep — shifts Sunday). Internal safe deadlines: **10 Sep (setor)**, **16 Sep (lapor)**. Calendar-alert.
- [ ] **December reconciliation (masa Desember 2026)**: switch from TER to full-year progressive recalculation for all WNA SPDN. Nominal deadline 15 Jan 2027 (setor) and 20 Jan 2027 (lapor) — verify holiday status in January 2027 separately.
- [ ] **For any WNA with split payroll (Indonesia + overseas parent)**: ensure the employer has a withholding mechanism for ALL compensation components — either direct payment via Indonesian payroll, or a deemed-employer / cross-charge arrangement that routes the offshore-paid component through Indonesian payroll. Income remains taxable regardless of payment route; the operational question is who withholds. Consult tax counsel for shadow-payroll structures.
- [ ] **File pembetulan if any temporary identifier was used in Coretax** for any WNA in Jan–May 2026 SPT Masa — these corrections are required for the employee to claim tax credits. Confirm exact temporary-identifier format (15-digit "+0 prefix" vs system-generated dummy) by inspecting the actual bukti potong record in Coretax UI before drafting the pembetulan.
- [ ] **Confirm PMK 81/2024 primary text** at `jdih.kemenkeu.go.id` (NOT secondary aggregator), **PMK 168/2023 Lampiran A** TER tables, **SKB 3 Menteri 2026** decree number at `kemenag.go.id`, and the actual KEP DJP number for the Coretax-transition Desember 2025 waiver, before presenting deadline schedule or rate figures to client. Earlier draft of this research mis-cited "KEP-37/PJ/2026" and "SKB Nomor 1497/2/5 Tahun 2025" — both flagged by DeepSeek red-team as unverifiable WebSearch-summary artifacts.

## Sources

1. WebSearch 2026-05-09: "PPh 21 monthly filing deadline 2026 Indonesia DJP batas waktu penyetoran pelaporan" — general deadline framework (15th/20th rule)
2. Q3 2026 deadline dates cross-checked via Python datetime arithmetic (Source #9) against Liputan6 + Ortax holiday tables — the kiakrikil.com Q3 calendar was an early input but is excluded from the verified citation chain (third-party kalender, not a regulator).
3. [ortax.org — Ketentuan Batas Waktu Setor dan Lapor PPh Pasal 21](https://ortax.org/ketentuan-batas-waktu-setor-dan-lapor-pph-pasal-21) (fetched 2026-05-09) — PMK 81/2024 verbatim citations
4. [Liputan6 — Kalender Libur Nasional 2026](https://www.liputan6.com/bisnis/read/6315357/cek-kalender-libur-nasional-2026-dan-jadwal-cuti-bersama) (fetched 2026-05-09) — 17 Aug Proklamasi + 25 Aug Maulid Nabi confirmed
5. WebSearch 2026-05-09: "libur nasional Juli Agustus September 2026 Indonesia SKB tiga menteri tanggal" — July zero national libur, September zero national libur (cross-checked across multiple aggregators). SKB 3 Menteri 2026 decree numbers NOT confirmed in this run — see Key Citations §6 for full disclosure of conflicting WebSearch results between "Nomor 1497/2/5 Tahun 2025" and "Nomor 1504/3/6 Tahun 2025"; primary verification at `kemenag.go.id` required before citing any decree number.
6. [skaiwork.com — Pajak Tenaga Kerja Asing](https://skaiwork.com/id/pajak-tenaga-kerja-asing/) (fetched 2026-05-09) — PPh 21 vs PPh 26 SPDN/SPLN distinction, TER rates, split-payroll trap
7. WebSearch 2026-05-09: "PPh 21 Coretax 2026 NIK WNA NPWP sementara bukti potong employer" — Coretax temporary-identifier process for unregistered NIK, and reference to a DJP transition waiver for Desember 2025 SPT Masa PPh 21 (specific KEP number not confirmed in this run; do NOT cite "KEP-37/PJ/2026")
8. [pajaknow.id — WNA aktivasi Coretax](https://pajaknow.id/kantor-pajak-edukasi-warga-asing-soal-spt-tahunan-dan-aktivasi-coretax/) (fetched 2026-05-09) — NPWP + "0" prefix procedure, PTKP TK/0, PER-7/PJ/2025
9. Python datetime calculation (2026-05-09) — exact shift arithmetic against SKB holiday list + internal deadline 3-business-day recalculation (full derivation: /tmp/deep-research-pph21-q3-deadlines-livetest-sources.txt)
10. WebSearch 2026-05-09: "PMK 243/PMK.03/2014 batas waktu PPh 21 tanggal 15 20" — confirmed PMK 81/2024 supersedes PMK 243/2014 and PMK 9/2018 (per secondary sources)
