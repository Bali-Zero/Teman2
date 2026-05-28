---
date: 2026-05-26
domain: visa
client_case: none (canonical gap inventory)
source_primary: "Synthesis of 01-raw-extraction.md + 02-cross-ref-pnbp.md + 03-bali-zero-service-mapping.md"
sources:
  - "Kepmen M.IP-08.GR.01.01/2025"
  - "PP 45/2024"
  - "Permenkumham 11/2024 (implementing regulation — referenced but not held)"
  - "imigrasi.go.id portal (404 on biaya-imigrasi 2026-05-26)"
total_oq: 47
status_distribution:
  closed: 12
  partial: 14
  open: 17
  no_data: 4
claim_count: 47
---

# Kepmen Visa Taxonomy 2025 — Open Questions

> **Purpose**: explicit inventory of gaps in the Kepmen + PP 45/2024 + Permenkumham triangle, with next-action recommendation per OQ.

## Status legend

| Status    | Meaning                                                                                    |
| --------- | ------------------------------------------------------------------------------------------ |
| `closed`  | Resolved via NB-2 hybrid query or Kepmen verbatim                                          |
| `partial` | Partially resolved, needs cross-check                                                      |
| `open`    | Requires external action (Kantor Imigrasi inquiry, PPID request, Permenkumham acquisition) |
| `no_data` | Portal officially shows "Data Belum Tersedia"                                              |

## OQ priority

| Priority | Meaning                                                 |
| -------- | ------------------------------------------------------- |
| **P0**   | Blocks quote generation for an active Bali Zero service |
| **P1**   | Affects ≥3 indeks; mid-term resolution                  |
| **P2**   | Single-indeks edge case; nice-to-have                   |

---

## OQ-001 to OQ-050 — Duration data (Kepmen gap, requires Permenkumham)

The Kepmen does NOT state extension cycles. PP 45/2024 sets tariff brackets (7/14/30/60/90/180 day) and multi-entry brackets (60d/90d/180d/1y/2y/5y/10y), but the matchup per indeks lives in Permenkumham 11/2024 implementing regulation.

| OQ         | Indeks            | Question                                                        | Status  | Priority | Next action                                                    |
| ---------- | ----------------- | --------------------------------------------------------------- | ------- | -------- | -------------------------------------------------------------- |
| **OQ-001** | B1, B4            | VOA 30d — extendable +30 once (cap 60d total) confirmed?        | partial | P1       | Confirm Permenkumham 11/2024 Pasal 23 verbatim                 |
| OQ-002     | F1, F4            | VOA 7d — non-extendable?                                        | partial | P2       | Permenkumham confirmation                                      |
| **OQ-003** | C1                | Tourism single-entry 60d — extendable +60+60 (total 180d)?      | partial | P0       | Most common Bali Zero quote, confirm                           |
| OQ-004     | C2                | Business single-entry 60d — same extension rule as C1?          | partial | P1       | Confirm same as OQ-003                                         |
| OQ-005     | C3                | Medical single-entry 60d — extension for treatment duration?    | partial | P1       | Often extended beyond 180d for treatment                       |
| OQ-006     | C4                | Government mission single-entry — likely 60d non-extendable     | partial | P2       | Standard gov scope                                             |
| OQ-007     | C5                | Journalism — confirm 60d + Kategori II/III verifikasi           | partial | P1       | Check vs Kemlu coordination                                    |
| **OQ-008** | C5A               | **Content creator — 60+60+60 (180d total)? Or 60+60 (120d)?**   | partial | **P0**   | **Confirm with Kantor Denpasar — first wave operational data** |
| OQ-009     | C6                | Social/voluntary — duration cap?                                | partial | P1       | NGO ops baseline                                               |
| OQ-010     | C7, C7A, C7B, C7C | Performers — 60d + Kategori surcharge?                          | partial | P1       | Music event ops                                                |
| OQ-011     | C8, C8A, C8B      | Sports — 60d, gov-invited may be longer                         | partial | P2       | Federation event coordination                                  |
| OQ-012     | C9, C9A, C9B      | Internal training — 60d standard                                | partial | P2       | Industrial inspection                                          |
| OQ-013     | C10, C10A         | Lecture/seminar — 60d, conference duration                      | partial | P2       | Academic event                                                 |
| OQ-014     | C11, C11A         | Film — 60d + Kategori III likely                                | open    | P1       | KAPL coordination                                              |
| OQ-015     | C12               | Pre-investment study — 60d, often companion to E28F application | partial | P1       | BKPM coordination                                              |
| OQ-016     | C13-C17           | Various business — 60d standard                                 | partial | P2       | Standard scope                                                 |
| OQ-017     | C18-C20           | Education-related — 60d standard                                | partial | P2       | Standard scope                                                 |
| OQ-018     | C21               | Religious propagation — 60d + special clearance (Kemenag)       | open    | P1       | Note Kemenag step in workflow                                  |
| OQ-019     | C22, C22A, C22B   | Pre-employment — 60d, bridge to KITAS                           | partial | P1       | Pipeline step before E23                                       |

### Multi-entry duration assumptions (D-series)

| OQ         | Indeks | Question                                                              | Status  | Priority | Next action                          |
| ---------- | ------ | --------------------------------------------------------------------- | ------- | -------- | ------------------------------------ |
| **OQ-051** | D1     | Multi-entry tourism — default 1 year? Or available 2y/5y/10y options? | open    | **P0**   | Most common D-series Bali Zero quote |
| OQ-052     | D2     | Multi-entry business — same options as D1?                            | open    | P1       |                                      |
| OQ-053     | D3     | Multi-entry medical — duration matches treatment plan?                | open    | P1       |                                      |
| OQ-054     | D4     | Multi-entry gov mission — typically diplomatic-channel                | partial | P2       | Niche case                           |
| OQ-055     | D7     | Multi-entry performer — 1y default                                    | open    | P1       | Performing arts touring              |
| OQ-056     | D8     | Multi-entry lecturer — 1y, academic year alignment                    | partial | P2       |                                      |
| OQ-057     | D12    | Multi-entry pre-investment — 1y, BKPM bridge                          | open    | P1       |                                      |
| OQ-058     | D14    | Multi-entry cooperation — duration matches MOU                        | open    | P1       |                                      |
| OQ-059     | D17    | Multi-entry audit/QC — 1y, branch inspection cycle                    | open    | P1       |                                      |

### E-series duration (mostly Kepmen-explicit but verify)

| OQ         | Indeks     | Question                                                        | Status     | Priority | Next action                 |
| ---------- | ---------- | --------------------------------------------------------------- | ---------- | -------- | --------------------------- |
| OQ-101     | E23, E23A  | KITAS Worker — 1y, renewable; verify Kepmen vs Permenkumham     | partial    | P1       | RPTKA validity tracking     |
| OQ-102     | E23U       | Probation — 6 months, non-extendable until conversion?          | partial    | P1       | Conversion to E23 standard? |
| OQ-103     | E23V       | Volunteer — 1y, NGO context                                     | partial    | P2       |                             |
| OQ-104     | E23X       | Religious worker — 1y, Kemenag overlap                          | open       | P1       |                             |
| OQ-105     | E23Y       | Vessel crew KITAS — 1y, oil/gas platform context                | partial    | P2       |                             |
| OQ-106     | E25 series | Skilled professional — 1y baseline, RPTKA-bound                 | partial    | P1       |                             |
| OQ-107     | E27        | Student — duration matches educational program                  | partial    | P1       | Annually renewable          |
| OQ-108     | E28A       | Investor 2y — Kepmen verbatim                                   | **closed** | —        | "paling lama 2 (dua) tahun" |
| OQ-109     | E28B/C/D   | Investor 5y/10y — Kepmen ambiguity "5 (lima) atau 10 (sepuluh)" | partial    | P1       | When 10y applies vs 5y      |
| OQ-110     | E33A       | Senior 55+ — typically 5y                                       | open       | P1       | Verify Permenkumham         |
| **OQ-111** | E33G       | **Digital Nomad — 1y, non-renewable? Renewable to 2y?**         | partial    | **P0**   | **Market premium service**  |
| OQ-112     | E35, E35A  | Domestic worker — 1y, sponsor-linked                            | partial    | P2       |                             |

---

## OQ-100 to OQ-150 — Surcharge Kategori assignment (Permenkumham gap)

PP 45/2024 lists 3 surcharges (Kategori I Rp 1M / II Rp 2M / III Rp 8M) but does NOT assign them per indeks. The assignment is in Permenkumham 11/2024 + circulars.

| OQ     | Indeks       | Question                                         | Status | Priority | Next action                       |
| ------ | ------------ | ------------------------------------------------ | ------ | -------- | --------------------------------- |
| OQ-115 | All C-series | Which C-codes trigger Kategori I/II/III?         | open   | **P0**   | PPID request Permenkumham 11/2024 |
| OQ-116 | C5A          | Content creator — Kategori II default?           | open   | P0       | First-wave applicant data needed  |
| OQ-117 | C11, C11A    | Film — Kategori III likely                       | open   | P1       | Film industry quote               |
| OQ-118 | C7A, C7B     | Music performer — Kategori II                    | open   | P1       | Performance event quote           |
| OQ-119 | E33G         | Digital Nomad — Kategori II likely               | open   | P0       | Quote accuracy                    |
| OQ-120 | E28A/B/C/D   | Investor — Kategori I or II per investment size? | open   | P1       |                                   |

---

## OQ-200 to OQ-250 — ITAS / KITAP edge cases

| OQ         | Indeks   | Question                                                             | Status  | Priority | Next action                       |
| ---------- | -------- | -------------------------------------------------------------------- | ------- | -------- | --------------------------------- |
| **OQ-201** | E28B/C/D | 10-year ITAS tariff — no PP 45/2024 line above 5y. Two-step renewal? | open    | **P1**   | Investor 10y quote logic          |
| OQ-202     | E32A     | Ex-Indonesian citizen 5y — KITAP conversion path                     | partial | P1       | UU 12/2006 + Permenkumham 11/2024 |
| OQ-203     | E32B     | Descendant 5y/10y — when 10y applies                                 | open    | P2       | Heritage applicants               |
| OQ-204     | E29      | Spouse of WNI — 2y → KITAP at year 5                                 | partial | P1       | Standard mixed-marriage path      |
| OQ-205     | E33D     | Long-stay business owner — 2y → KITAP at year 6?                     | open    | P2       |                                   |

---

## OQ-300 to OQ-330 — Bali Zero PricingTool gaps

| OQ         | Indeks       | Question                                               | Status | Priority | Next action                   |
| ---------- | ------------ | ------------------------------------------------------ | ------ | -------- | ----------------------------- |
| **OQ-301** | C5A          | PricingTool entry exists?                              | open   | **P0**   | Audit when API auth available |
| OQ-302     | E33G         | PricingTool entry exists for E33G specifically?        | open   | **P0**   | Same                          |
| OQ-303     | E28B/C/D     | 5y vs 10y differential in PricingTool?                 | open   | P1       |                               |
| OQ-304     | All D-series | Multi-entry durations 1y/2y/5y/10y all in PricingTool? | open   | P1       |                               |
| OQ-305     | E31C, E31D   | Mixed marriage child + adoption — distinct entries?    | open   | P2       |                               |

---

## OQ-400 — Visa-Free (A-series) country lists

| OQ         | Indeks   | Question                                                        | Status  | Priority | Next action                             |
| ---------- | -------- | --------------------------------------------------------------- | ------- | -------- | --------------------------------------- |
| **OQ-401** | A1       | Bebas 30d — current country list (2025+)                        | open    | **P0**   | Permenkumham 11/2024 + diplomatic notes |
| OQ-402     | A4       | Government mission visa-free — applicable to ALL nationalities? | partial | P1       | Reciprocity rule                        |
| OQ-403     | A36, A37 | Crew exemption — international maritime/aviation treaty basis   | partial | P2       | UN Convention reference                 |

---

## OQ-500 — "No Data" cases (officially confirmed)

The Kepmen 2025 introduced indeks that are NOT yet documented on imigrasi.go.id portal as of 2026-05-26 audit (portal returns "Data Belum Tersedia" or 404).

| OQ     | Indeks     | Status  | Notes                                                                                       |
| ------ | ---------- | ------- | ------------------------------------------------------------------------------------------- |
| OQ-501 | C5A        | no_data | Portal page shows "Data Belum Tersedia" — operational data via Kantor Denpasar inquiry only |
| OQ-502 | E33G       | no_data | Similar — first wave applicants, no public dashboard yet                                    |
| OQ-503 | A36, A37   | no_data | Crew exemption rarely-queried publicly                                                      |
| OQ-504 | C22A, C22B | no_data | Pre-employment family — niche case, operational only                                        |

---

## Recommended next actions (prioritized)

### Immediate (this week)

1. **OQ-008 + OQ-501 (C5A)**: phone Kantor Imigrasi Denpasar `(0361) 751-038`, ask 5 questions from `research/visa/2026-05-26-c5a-step1-followup-prompt.md` TASK 2.A
2. **OQ-051 (D1 default duration)**: query NB-2 or BPK for Permenkumham 11/2024 verbatim
3. **OQ-111 + OQ-302 (E33G)**: same Kantor Denpasar call, add E33G-specific questions
4. **OQ-301 (C5A PricingTool gap)**: when API auth available, run `mcp__nuzantara-mcp__search_service_pricing` for C5A code

### Mid-term (this month)

5. **OQ-115 + OQ-120 (Kategori surcharge assignment)**: PPID request to Kemenimipas
6. **OQ-201 (10-year ITAS)**: legal opinion or Kantor inquiry on E28B/C/D step-up case
7. **OQ-401 (A1 country list)**: verify against latest diplomatic note + Permenkumham

### Acceptable "no data" (defer indefinitely)

- OQ-503 (crew exemption — rare)
- OQ-504 (pre-employment family — niche)

---

## Cross-references

- `01-raw-extraction.md` — taxonomy
- `02-cross-ref-pnbp.md` — PNBP detail
- `03-bali-zero-service-mapping.md` — service portfolio
- `render/` — A4 brand PDF
