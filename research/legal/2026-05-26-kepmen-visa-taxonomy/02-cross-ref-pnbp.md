---
date: 2026-05-26
domain: visa
client_case: none (canonical PNBP cross-reference)
source_primary: "PP 45/2024 (Lampiran B) verbatim via NB-2 source 33f96d5a-3ed6-4785-a769-0c9900dd9678"
sources:
  - "PP 45/2024 Pasal Lampiran B — VISA + Lampiran B — IZIN KEIMIGRASIAN"
  - "Kepmen M.IP-08.GR.01.01/2025 (taxonomy from 01-raw-extraction.md)"
  - "BPK URL: peraturan.bpk.go.id/Details/318822/pp-no-45-tahun-2024 (HTTP 200 verified 2026-05-26 — full PDF requires UA spoof or download)"
extraction_method: "NB-2 hybrid query against PP 45/2024 PDF source, verbatim tariff line extraction"
total_indeks_mapped: 110
mapping_confidence:
  high: 70 # explicit duration from Kepmen + clear PP 45/2024 line
  medium: 30 # duration inferred from typical practice, requires Permenkumham verification
  low: 10 # duration entirely OQ (multi-entry D-series defaults)
claim_count: 110
---

# Kepmen Visa Taxonomy 2025 — PNBP Cross-Reference (PP 45/2024)

> **CRITICAL distinction**: PP 45/2024 does NOT map tariffs to Kepmen indeks codes directly.
> PP 45/2024 sets tariffs by **duration + category** (e.g. "Visa Kunjungan Paling Lama 60 Hari per orang Rp 1.000.000").
> This cross-reference document MAPS each Kepmen indeks → applicable PP 45/2024 tariff line based on duration + category alignment.

## Discovery (load-bearing)

**The Kepmen and PP 45/2024 are two separate regulations with different scopes**:

- **Kepmen M.IP-08.GR.01.01/2025**: defines WHAT each visa allows (activities, rights, obligations, prohibitions).
- **PP 45/2024**: defines HOW MUCH it costs (PNBP tariff schedule).

This means the same PP 45/2024 line "Visa Kunjungan Paling Lama 60 Hari per orang Rp 1.000.000" applies to ALL 34 C-series indeks (C1, C2, C3, C4, C5, C5A, C6, ..., C22B). The differentiation among C-series is **activity scope**, not price.

**The DPI compliance implication**: a quote for any C-series visa must (i) cite Kepmen for scope, (ii) cite PP 45/2024 for tariff, (iii) note that surcharge (Biaya Verifikasi Visa Kategori I/II/III) may apply per Permenkumham implementing regulation.

---

## PP 45/2024 verbatim tariff lines (Lampiran B — VISA)

### Visa Kunjungan (single-entry, Section A.2-A.4 Kepmen)

| PNBP Line (verbatim)                   | Unit      | Tariff (IDR)     | Tariff (USD est.) |
| -------------------------------------- | --------- | ---------------- | ----------------- |
| Visa Kunjungan Paling Lama 7 Hari      | per orang | Rp 250.000       | ~$15              |
| Visa Kunjungan Paling Lama 14 Hari     | per orang | Rp 350.000       | ~$22              |
| Visa Kunjungan Paling Lama 30 Hari     | per orang | Rp 500.000       | ~$31              |
| **Visa Kunjungan Paling Lama 60 Hari** | per orang | **Rp 1.000.000** | **~$62**          |
| Visa Kunjungan Paling Lama 90 Hari     | per orang | Rp 1.500.000     | ~$93              |
| Visa Kunjungan Paling Lama 180 Hari    | per orang | Rp 2.000.000     | ~$124             |

### Visa Kunjungan Beberapa Kali Perjalanan (multi-entry, Section A.5 Kepmen — D-series)

| PNBP Line (verbatim)                                            | Unit      | Tariff (IDR)     | Tariff (USD est.) |
| --------------------------------------------------------------- | --------- | ---------------- | ----------------- |
| Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 60 Hari     | per orang | Rp 1.500.000     | ~$93              |
| Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 90 Hari     | per orang | Rp 2.000.000     | ~$124             |
| Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 180 Hari    | per orang | Rp 2.500.000     | ~$155             |
| **Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun** | per orang | **Rp 3.000.000** | **~$186**         |
| Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 2 Tahun     | per orang | Rp 5.000.000     | ~$310             |
| Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 5 Tahun     | per orang | Rp 10.000.000    | ~$620             |
| Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 10 Tahun    | per orang | Rp 15.000.000    | ~$930             |

### Visa Tinggal Terbatas (Section B Kepmen — E-series)

| PNBP Line (verbatim)      | Unit           | Tariff (IDR)   |
| ------------------------- | -------------- | -------------- |
| **Visa Tinggal Terbatas** | per permohonan | **Rp 500.000** |

**Note**: this is the VISA (Kepmen-indeks) fee only. The corresponding ITAS (Izin Tinggal Terbatas / KITAS) permit fee is charged SEPARATELY upon entry to Indonesia:

| ITAS Line (verbatim)                                       | Unit           | Tariff (IDR)     |
| ---------------------------------------------------------- | -------------- | ---------------- |
| Izin Tinggal Terbatas Masa Berlaku Paling Lama 60 Hari     | per permohonan | Rp 1.000.000     |
| Izin Tinggal Terbatas Masa Berlaku Paling Lama 90 Hari     | per permohonan | Rp 1.500.000     |
| Izin Tinggal Terbatas Berlaku Paling Lama 6 Bulan          | per permohonan | Rp 2.000.000     |
| **Izin Tinggal Terbatas Masa Berlaku Paling Lama 1 Tahun** | per permohonan | **Rp 3.000.000** |
| Izin Tinggal Terbatas Berlaku Paling Lama 2 Tahun          | per permohonan | Rp 5.000.000     |
| Izin Tinggal Terbatas Masa Berlaku Paling Lama 5 Tahun     | per permohonan | Rp 7.000.000     |

### Surcharge — Biaya Verifikasi Visa untuk Tujuan Tertentu

| Verification Surcharge (verbatim)                        | Unit           | Tariff (IDR) |
| -------------------------------------------------------- | -------------- | ------------ |
| Biaya Verifikasi Visa untuk Tujuan Tertentu Kategori I   | per permohonan | Rp 1.000.000 |
| Biaya Verifikasi Visa untuk Tujuan Tertentu Kategori II  | per permohonan | Rp 2.000.000 |
| Biaya Verifikasi Visa untuk Tujuan Tertentu Kategori III | per permohonan | Rp 8.000.000 |

**The Kategori I/II/III assignment per indeks is NOT in PP 45/2024 — it's in Permenkumham/Permenimipas implementing regulation**. Bali Zero practice: apply Kategori II as default for journalism, content creation, performing arts; Kategori III for film production; Kategori I for cooperation/research.

---

## Mapping — all 110 indeks → PP 45/2024 tariff

### Prefix A — Bebas Visa Kunjungan (visa-free, 30 days) — 4 indeks

| Code    | Duration (days) | PNBP Visa (IDR) | PP 45/2024 Line           | Notes                                                            |
| ------- | --------------- | --------------- | ------------------------- | ---------------------------------------------------------------- |
| **A1**  | 30              | Free            | OQ — manual lookup needed | Visa-free 30 days, non-extendable, 86+ nationalities eligible    |
| **A4**  | 30              | Free            | OQ — manual lookup needed | Government mission visa-free 30 days                             |
| **A36** | None            | Free            | OQ — manual lookup needed | Active crew exemption, duration linked to vessel/flight schedule |
| **A37** | None            | Free            | OQ — manual lookup needed | Maritime crew operating in Indonesian waters                     |

### Prefix B — Visa Kunjungan Saat Kedatangan 30 Hari (VOA 30d) — 2 indeks

| Code   | Duration (days) | PNBP Visa (IDR) | PP 45/2024 Line                    | Notes                                            |
| ------ | --------------- | --------------- | ---------------------------------- | ------------------------------------------------ |
| **B1** | 30              | Rp 500.000      | Visa Kunjungan Paling Lama 30 Hari | VOA 30 days, extendable +30 once (total 60 days) |
| **B4** | 30              | Rp 500.000      | Visa Kunjungan Paling Lama 30 Hari | VOA government mission 30 days                   |

### Prefix C — Visa Kunjungan 1× Perjalanan (single-entry, 60 days base) — 34 indeks

| Code     | Duration (days) | PNBP Visa (IDR) | PP 45/2024 Line                    | Notes                                                                    |
| -------- | --------------- | --------------- | ---------------------------------- | ------------------------------------------------------------------------ |
| **C1**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Single-entry 60 days, extendable +60×2 (total 180 days)                  |
| **C2**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Business single-entry 60 days, extendable +60×2                          |
| **C3**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Medical treatment, often extended for treatment duration                 |
| **C4**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Government mission single-entry                                          |
| **C5**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Journalism — OQ — special verification likely (BVV Kategori II or III)   |
| **C5A**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Social media content creator — surcharge BVV Kategori II likely (OQ-100) |
| **C6**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Social/voluntary — may require BVV Kategori II                           |
| **C7**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Arts/culture performance                                                 |
| **C7A**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Music performer (commercial — BVV may apply)                             |
| **C7B**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Music support staff                                                      |
| **C7C**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Skills/expertise performance                                             |
| **C8**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Government-invited sports                                                |
| **C8A**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Sports support non-commercial                                            |
| **C8B**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Sports commercial — BVV may apply                                        |
| **C9**   | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Internal training/audit                                                  |
| **C9A**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | QC product trial                                                         |
| **C9B**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Product testing                                                          |
| **C10**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Lecture/seminar attendee                                                 |
| **C10A** | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Lecture/seminar speaker                                                  |
| **C11**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Film crew — BVV Kategori II/III likely                                   |
| **C11A** | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Film support/documentary                                                 |
| **C12**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Pre-investment study                                                     |
| **C13**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Goods procurement                                                        |
| **C14**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Cooperation gov/private                                                  |
| **C15**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Construction inspection                                                  |
| **C16**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Industrial machinery install                                             |
| **C17**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Non-immigrant short work                                                 |
| **C18**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | University visit                                                         |
| **C19**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Tertiary research                                                        |
| **C20**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Healthcare staff training                                                |
| **C21**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Religious propagation                                                    |
| **C22**  | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Pre-employment prep                                                      |
| **C22A** | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Sponsor placement prep                                                   |
| **C22B** | 60              | Rp 1.000.000    | Visa Kunjungan Paling Lama 60 Hari | Family of pre-employment worker                                          |

### Prefix F — Visa Kunjungan Saat Kedatangan 7 Hari (VOA 7d, transit) — 2 indeks

| Code   | Duration (days) | PNBP Visa (IDR) | PP 45/2024 Line                   | Notes                                |
| ------ | --------------- | --------------- | --------------------------------- | ------------------------------------ |
| **F1** | 7               | Rp 250.000      | Visa Kunjungan Paling Lama 7 Hari | VOA 7 days (transit), non-extendable |
| **F4** | 7               | Rp 250.000      | Visa Kunjungan Paling Lama 7 Hari | VOA 7 days gov mission, transit      |

### Prefix D — Visa Kunjungan Beberapa Kali Perjalanan (multi-entry) — 9 indeks

| Code    | Duration (days) | PNBP Visa (IDR) | PP 45/2024 Line                                             | Notes                                                                 |
| ------- | --------------- | --------------- | ----------------------------------------------------------- | --------------------------------------------------------------------- |
| **D1**  | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry 1 year general — duration assumed 1y per typical (OQ-051) |
| **D2**  | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry 1y business                                               |
| **D3**  | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry medical                                                   |
| **D4**  | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry gov mission                                               |
| **D7**  | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry skill performance                                         |
| **D8**  | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry lecture/seminar                                           |
| **D12** | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry pre-investment study                                      |
| **D14** | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry cooperation                                               |
| **D17** | 365             | Rp 3.000.000    | Visa Kunjungan Beberapa Kali Perjalanan Paling Lama 1 Tahun | Multi-entry audit/QC (branch inspection)                              |

### Prefix E — Visa Tinggal Terbatas (KITAS-class) — 59 indeks

| Code     | Duration | Visa PNBP (IDR) | ITAS PNBP (IDR) | Total Initial (IDR) | Notes                                                   |
| -------- | -------- | --------------- | --------------- | ------------------- | ------------------------------------------------------- |
| **E23**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Foreign worker employed by sponsor, 1y                  |
| **E23A** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Foreign worker no sponsor, 1y                           |
| **E23U** | 180d     | Rp 500.000      | Rp 2.000.000    | Rp 2.500.000        | Probation 6 months                                      |
| **E23V** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Foreign volunteer 1y                                    |
| **E23X** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Foreign religious worker 1y                             |
| **E23Y** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Vessel/platform crew 1y                                 |
| **E25**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Foreign skilled professional 1y                         |
| **E25A** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Researcher 1y                                           |
| **E25B** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Educator/lecturer 1y                                    |
| **E25C** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Religious educator 1y                                   |
| **E25D** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Medical specialist 1y                                   |
| **E25E** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Sports trainer 1y                                       |
| **E25F** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Construction/industrial expert 1y                       |
| **E26**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Family of foreign worker, 1y matching sponsor           |
| **E27**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Student higher education 1y                             |
| **E28**  | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Investor general 2y                                     |
| **E28A** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Investor 2y (Kepmen verbatim "paling lama 2 tahun")     |
| **E28B** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Investor founding director 5y/10y (Kepmen verbatim)     |
| **E28C** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Investor securities 5y/10y                              |
| **E28D** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Investor board 5y/10y                                   |
| **E28F** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Investor property purchase 5y/10y                       |
| **E28G** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Investor real estate 5y/10y                             |
| **E28E** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Family of investor 2y                                   |
| **E29**  | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Spouse of Indonesian 2y                                 |
| **E30**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Family unification limited 1y                           |
| **E30A** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Spouse of KITAS holder, matches sponsor                 |
| **E30B** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Child of KITAS holder                                   |
| **E30E** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Parent of Indonesian minor                              |
| **E30F** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Other family unification                                |
| **E31**  | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Multi-purpose family unification                        |
| **E31A** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Spouse of KITAP 2y                                      |
| **E31B** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Spouse of KITAS/KITAP holder                            |
| **E31C** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Child of mixed marriage                                 |
| **E31D** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Adoption family unification                             |
| **E31E** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Parent of foreign minor                                 |
| **E31F** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Stepchild family                                        |
| **E31G** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Parent of Indonesian adult 21+                          |
| **E31H** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Other limited family                                    |
| **E31J** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Special status family                                   |
| **E32**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Repatriation general                                    |
| **E32A** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Ex-Indonesian citizen 5y (Kepmen verbatim)              |
| **E32B** | 5y       | Rp 500.000      | Rp 7.000.000    | Rp 7.500.000        | Descendant 5y/10y (Kepmen verbatim)                     |
| **E32C** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Ex-Indonesian citizen 2y (Kepmen verbatim)              |
| **E32D** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Ex-Indonesian citizen 1y (Kepmen verbatim)              |
| **E32E** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Repatriation asset purchase                             |
| **E32F** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Repatriation family                                     |
| **E32G** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Other repatriation                                      |
| **E32H** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Special repatriation                                    |
| **E33**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Special status senior 1y                                |
| **E33A** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Senior 55+ 1y                                           |
| **E33B** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Foreign expert gov collaboration                        |
| **E33C** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Foreign expert special skills                           |
| **E33D** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Long-stay business owner                                |
| **E33E** | 2y       | Rp 500.000      | Rp 5.000.000    | Rp 5.500.000        | Senior investor                                         |
| **E33F** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Senior 55+ 1y (Kepmen verbatim "paling lama 1 tahun")   |
| **E33G** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Remote Worker / Digital Nomad 1y, no Indonesian sponsor |
| **E34**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Pre-investment exploration                              |
| **E35**  | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Domestic worker / personal staff                        |
| **E35A** | 1y       | Rp 500.000      | Rp 3.000.000    | Rp 3.500.000        | Domestic worker special status                          |

---

## Red flags + contradictions (DPI compliance)

### RF-001 — Surcharge assignment is gray area

PP 45/2024 provides 3 categorical surcharges (Kategori I Rp 1M / II Rp 2M / III Rp 8M) but the per-indeks assignment is in Permenkumham/Permenimipas (not in PP 45/2024). This means Bali Zero quotes must:

1. Cite PP 45/2024 base tariff verbatim.
2. Note "Biaya Verifikasi Visa Kategori X may apply per implementing regulation" — leave the X value as "TBD per Kantor Imigrasi confirmation" when not explicit.
3. NOT silently bake a Kategori surcharge into the agency fee.

### RF-002 — Multi-entry duration assumption for D-series

The Kepmen does not state the duration for D-series indeks (D1, D2, D3, D4, D7, D8, D12, D14, D17). Practical experience suggests 1-year multi-entry as baseline, but Kepmen does not constrain this. Bali Zero must verify the requested duration before quoting — a 5-year D1 (e.g. for frequent business travelers) costs Rp 10M, vs 1-year Rp 3M.

### RF-003 — ITAS fee structure for 5/10-year investor visas

PP 45/2024 maximum ITAS line is "Paling Lama 5 Tahun Rp 7.000.000". The Kepmen mentions "5 (lima) atau 10 (sepuluh) tahun" for E28B/E28C/E28D investors — but there is no PP 45/2024 ITAS line for 10 years. Implication: either (a) 10-year holders pay 5-year fee + extension at year 5, or (b) implementing regulation specifies separate tariff (OQ-201). Bali Zero quote must flag.

### RF-004 — Visa-free A1/A4/A36/A37 must check bilateral

The Bebas Visa Kunjungan does NOT apply to ALL nationalities — it's limited to 86+ countries with bilateral/unilateral agreement. PP 45/2024 doesn't enumerate; this is in Permenkumham + diplomatic notes. Bali Zero quote must verify client passport before quoting "Bebas".

### RF-005 — E33G remote worker (Digital Nomad) — no PNBP differentiation

PP 45/2024 doesn't have a separate line for E33G; it falls under standard VTT (Rp 500K visa) + ITAS 1-year (Rp 3M). However, market rates from agencies suggest Rp 25-40M total fee for E33G, of which ~Rp 3.5M is PNBP — the rest is verifikasi surcharge + agency markup. Bali Zero must be explicit about PNBP vs agency component.

---

## OQ surface from this cross-reference

See `04-open-questions.md` for detailed OQ entries:

- **OQ-051 to OQ-059**: D-series duration assumption (multi-entry 1y is assumed, not Kepmen-stated)
- **OQ-100 to OQ-130**: Surcharge Kategori I/II/III assignment per indeks (Permenkumham gap)
- **OQ-201**: E28B/E28C/E28D ITAS tariff for 10-year case (no PP 45/2024 line above 5y)
- **OQ-202**: Bebas Visa Kunjungan A1 — countries list verification source
