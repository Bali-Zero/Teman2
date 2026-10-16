---
date: 2026-10-15
domain: visa
client_case: none
mandate: "Zero 2026-10-15 — close the E28 (Investor KITAS) family end to end"
pack: rulepack-prod-029.signed.json (seq-29, ACTIVE since 2026-10-13T11:19:00Z, payload 3f3b45ed…9295)
base: origin/main c68ae57f15
sources:
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28A (fetched 2026-10-15T14:22:47Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28B (fetched 2026-10-15T14:22:47Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28C (fetched 2026-10-15T14:22:48Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28D (fetched 2026-10-15T14:22:49Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28E (fetched 2026-10-15T14:22:49Z)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28F (fetched 2026-10-15T14:22:50Z)
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-029.signed.json
adversarial_review: codex
adversarial_review_detail: codex gpt-5.6-sol (read-only, 2026-10-15) — verdict UNSOUND; dispositions in §Adversarial review
---

# E28 family audit matrix — 2026-10-15

## Sources

- **Signed pack seq-29**, `apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-029.signed.json`.
  The E28 products are E28A, E28B, E28C, E28D and E28F. E28E and E28G are not in the pack.
- **Official pages, saved today.** `research/visa/2026-10-15-e28-pages/`, with receipts in `e28-pages.receipts.jsonl`
  and the text in `text/`. Six pages were fetched, `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28{A,B,C,D,E,F}`,
  at 2026-10-15T14:22:47Z–14:22:50Z, reader `e28-audit-opus-20261015`. All six returned HTTP 200. E28E reads
  "Data Belum Tersedia".
- **The Pro conductor's investor audit**, `~/visa-night/investor/audit.json` on Pro, generated 2026-10-12 against seq-27.
  It holds 107 confirmed findings in 29 root causes, 21 PRs (9 decision-free) and 12 owner decisions INV-OD-I1..I12.
  For surface 1 this matrix reuses it and does not repeat it. The status of its PRs, re-read today:
  - merged: I-X01 #8379, I-X02 #8312 and I-M04 #8429 (proven live 2026-10-13);
  - shipped in seq-29: only SEQ29-F1;
  - still queued: I-M01..I-M03 and I-T01..I-T03;
  - still owner-blocked: I-T04..I-T09, I-M05, I-M06, I-P01 and I-P02, plus the SEQ29-A1/A2/B1/B2/C1/D1/N1/X1/P1/P2/S1
    rule items, now seq-30 candidates.
- **Four read lanes of this session**, on `origin/main c68ae57f15`. Every DRIFT cited below was re-read on disk by the
  orchestrator this turn.

## What the sources say (truth table)

| Code | Pack seq-29 | Official page 2026-10-15 |
|---|---|---|
| E28A | "Investor Visa (E28A)". 730 days. Extension 365/ext, VERIFIED. Pricing key "Investor KITAS 2 Years (Offshore)", which is IDR 17.000.000. Prohibited: operational work beyond management and ownership. Supported when INVESTMENT, PT PMA committed, role shareholder-director or commissioner, company paid-up ≥ IDR 2.5 bn and company investment ≥ IDR 10 bn. | 1 or 2 years. Sponsor required. The applicant's **own shares ≥ Rp 10.000.000.000** in the sponsoring company. Below that, with a board post, a work visa. Kemenkumham deed, company account 2 months. Director/commissioner allowed. No selling except as the work needs. 5 working days after payment. Passport ≥ 6 months. |
| E28B | Company Establishment. 1825–3650 days. Extension UNKNOWN. Price on consultation (key null). Prohibited: operational_work. | 5 or 10 years, extendable, **no sponsor**. Commit ≥ USD 2.5M (5y) / 5M (10y) within 90 days. Audited foreign-company shares and turnover. Director/commissioner allowed. |
| E28C | Capital Market. 1825–3650 days. Key null. Prohibited: operational_work, corporate_establishment. | "Visa Investor Pasar Modal". No sponsor. Bonds, listed shares or funds ≥ USD 350k (5y) / 700k (10y), or an apartment ≥ USD 1M (10y). |
| E28D | Branch or Subsidiary. 1825–3650 days. Key null. | Director/commissioner of an Indonesian branch or subsidiary of a foreign company. No sponsor. Commit ≥ USD 25M (5y) / 50M (10y). **No turnover requirement.** |
| E28F | IKN Subsidiary. 1825–3650 days. Key null. | As E28D, in IKN. USD 5M (5y) / 10M (10y). |
| E28E | not in pack | page empty |
| E28G | not in pack | no page (legacy KB file only) |

## Matrix

Legend:
- **OK**: the surface agrees with the pack or the page.
- **DRIFT**: the surface contradicts them; see finding F-n.
- **MISS**: the surface omits a fact it should carry.
- **n/a**: the surface does not name the product.

| Product | 1 Oracle | 2 Catalogue | 3 /book · /services | 4 Brochure | 5 Zantara | 6 Qdrant | 7 Legacy matcher | 8 Articles + llms | 9 MCP |
|---|---|---|---|---|---|---|---|---|---|
| E28A | DRIFT F2 F3 · MISS F1 F5 F6 · OK F4 (Q9) | OK (17/19/18 M) · MISS F20 | OK price · MISS F21 · DRIFT F23 F69 | OK (Rp 17.000.000) | DRIFT F30 F31 F32 | OK price · DRIFT F40 | DRIFT F50 F51 F52 F53 | DRIFT F60–F66 · OK llms.txt | DRIFT F70 F71 |
| E28B | DRIFT F7 F9 · MISS F5 | OK (no row = on consultation) | MISS F22 (nav) · DRIFT F71 | OK (not listed) | DRIFT F34 | DRIFT F41 | MISS F54 | DRIFT F62 | DRIFT F72 |
| E28C | DRIFT F7 · MISS F5 | OK | MISS F22 · DRIFT F71 | OK | DRIFT F34 | OK (missing 1M apartment) | MISS F54 | DRIFT F62 | MISS F73 |
| E28D | DRIFT F7 F8 F9 F11 · MISS F5 | OK | MISS F22 · DRIFT F70 | OK | DRIFT F34 | DRIFT F42 | MISS F54 | DRIFT F62 | OK (no thresholds) |
| E28F | DRIFT F7 F9 F11 · MISS F5 | OK | MISS F22 | OK | DRIFT F34 | DRIFT F43 | MISS F54 | DRIFT F62 | OK (no thresholds) |
| E28E (listed, no data) | OK (absent) | OK | OK | OK | OK | OK | OK | DRIFT F63 (invented threshold) · OK llms.txt | OK |
| E28G (phantom) | OK (absent) | OK | OK | OK | DRIFT F35 | DRIFT F44 | OK | DRIFT F63 | DRIFT F74 |

There is no PNBP or government-fee split on any client surface. The single all-inclusive price holds everywhere a price
is shown. The one contradiction of that rule is the terms page, F23.

## Findings

### Surface 1 — Visa Oracle (`apps/mouth/src/app/(visa-oracle)/visa-oracle/`)

These findings are owned by the conductor's queue (I-M01..I-M03 and I-T01..I-T03) unless this session takes them over
(see Plan).

- **F1. The E28A support reason names one of the two figures.** `_lib/engine-adapter.ts:446-448`:
  "…with paid-up capital of IDR 2.5 billion or more." Rule `el.e28a.investment` also requires
  `investment.investment_capital_idr gte 10000000000`. This is the conductor's RC03 / I-M02.
- **F2. E28A attributes the company tests to the visa; the page tests the applicant's own shares.**
  `_lib/engine-adapter.ts:968-975` gives E28A_TOTAL_INVESTMENT_BELOW_MIN as "total investment capital of at least IDR
  10,000,000,000". Page E28A: "Bukti kepemilikan saham paling sedikit Rp10.000.000.000,00 … pada perusahaan penjamin".
  The copy is true to the pack; the RULE is the defect. This is RC01, the seq-30 rule item SEQ29-A1.
- **F3. The E28A role is required, though the page only permits it.** `el.e28a.investment` requires `proposed_role in
  {SHAREHOLDER_DIRECTOR, SHAREHOLDER_COMMISSIONER}`. Page: a board post is allowed, and only below Rp 10 bn does a board
  post force a work visa. This is RC02, SEQ29-A2, a rule item.
- **F4. Processing time.** `apps/backend-rag/backend/data/bali_zero_processing_times_2026.json:52-76` gives E28A–E28F
  `"min": 7, "max": 10` and the card shows "Typically 7–10 working days". Every page says "lima hari kerja setelah
  pembayaran visa diterima". This is the Bali Zero end-to-end window, not the government stage. Owner decision OD-I10.
- **F5. No documents checklist for any E28 code.** `documentation_for` returns UNKNOWN, because
  `bali_zero_documentation_catalog_2026.json` has only E33 keys. The pages list the base documents and the special
  requirements. MISSING; backlog.
- **F6. No stay-length or renewal line for E28A.** `_lib/engine-adapter.ts:2427`:
  `STAY_PERMIT_LENGTH_DAYS = new Set([365, 1825])`. 730 is absent, and the renewal key `365:100` has no copy. MISSING.
- **F7. Golden routes rest on one self-declared boolean with no figure.** `investment.meets_published_threshold` is
  shared by E28B, E28C, E28D and E28F. This is RC04, SEQ29-B1, a rule item. The copy names no figure, by design:
  `engine-adapter.ts:809-811`.
- **F8. E28D promises a turnover check its page does not have.** `_lib/engine-adapter.ts:847`: "…confirm the investment
  and turnover figures…". The ID text says "angka investasi dan omzetnya". The same wording is in `_lib/i18n.ts:421`
  (ID `:1479`). The E28D page states only the USD 25M / 50M commitment; turnover belongs to E28B. This is I-M03.

### Surfaces 2–4 — catalogue, /book, /services, brochure

- **F20. The Investor KITAS rows have no `validity`, no all-inclusive note and no eligibility words.**
  `bali_zero_official_prices_2026.json:274-302`. Row descriptions read "…valid 2 years for shareholders of a PT PMA".
  MISSING, LOW. The "All-inclusive price." note waits on OD-I8.
- **F21. The FAQ uses a generic sponsor and threshold.** `apps/mouth/src/data/services_data.ts:135-136`: "Valid sponsor
  (company or individual)" and "Meet minimum investment (for investor visa)". For E28A the sponsor is the company, and
  the figure is own shares ≥ Rp 10 bn. LOW.
- **F22. The "Golden Visa" navigation is a dead end.** `apps/mouth/src/app/v2/_components/Footer.tsx:22`:
  `{ label: "Golden Visa", href: "/services/visa" }`. The target page has no Golden product, not even "price on
  consultation". MEDIUM; owner decision Q11.
- **F23. The terms page splits the price.** `apps/mouth/src/app/visa/terms/page.tsx:94-95`: "Government fees are
  separate and are set by Indonesian authorities." This contradicts the all-inclusive card ("Government fees and Bali
  Zero service included.", `i18n.ts:894-896`) and ruling R1. It is OD-I8 / I-M06 and blocks on Zero's confirmation that
  17 M is all-inclusive.
- Sync check: `python3 scripts/sync_frontend_prices.py --check` → `INFO OK … in sync`, exit 0.
- The live brochure PDF (`https://balizero.com/static/brochure_balizero_en.pdf`, identical to the repo copy) prints
  "Investor KITAS, 2 years · Offshore · Rp 17.000.000". OK.

### Surface 5 — Zantara (`apps/backend-rag/backend/`)

- **F30. KG routes name E28A as a worker's KITAS.**
  - `services/rag/kg_enhanced_retrieval.py:473`: "…or hire with KITAS E28A (Worker)".
  - `:498`: "…or E28A (Worker/Director)".
  - `:545`: "Worker enters Indonesia, converts to KITAS E28A at immigration office".
  - The pack prohibits operational work. HIGH.
- **F31. PT PMA capital stated as a flat IDR 10 bn.**
  - `kg_enhanced_retrieval.py:388-389` (route `pt_pma_setup`): "Minimum capital: IDR 10 billion" and "Paid-up capital:
    minimum 25%".
  - The same flat figure appears at `:440`, `:482` and `:643`.
  - `prompts/few_shot_examples.py:134` and `prompts/whatsapp_persona.py:360`: "10 billion IDR … subscribed capital you
    commit to invest over time".
  - These contradict `prompts/zantara_core_v4.py:194`: paid-up ≥ Rp 2.5 bn, investment > Rp 10 bn, "NEVER describe
    Rp10.000.000.000 as paid-up capital". MEDIUM.
- **F32. Vague E28A requirements.** `prompts/zantara_core_v3.py:141-150` and `zantara_core_v4.py:336-349`: "a PT PMA as
  sponsor, the OSS-registered minimum capital, and BKPM clearance". These omit own shares ≥ Rp 10 bn and the board-post
  rule. LOW–MEDIUM.
- **F33. Route `investor_kitas_retirement` is correct but incomplete.** `:513-535` gives role and 2 years only. OK;
  already fixed in #8527.
- **F34. Route `visa_golden` collapses the tiers.** `kg_enhanced_retrieval.py:897-914`:
  - It applies one "USD 2.5 million in Indonesia (business, property, government bonds)" figure to every route.
  - It gives "Property investment: minimum USD 350,000 in designated areas".
  - The pages say: E28B 2.5M/5M; E28C 350k/700k in bonds, listed shares or funds, or a 1M apartment (10y only);
    E28D 25M/50M; E28F 5M/10M.
  - HIGH.
- **F35. E28G named as the current Investor KITAS** in 8 route steps: `kg_enhanced_retrieval.py:447, 473, 498, 577, 609,
  640, 667, 775`. Two more places use the same phrasing in a docstring and a test fixture, `services/rag/kg_graph_nodes.py:895-896`
  and `tests/services/rag/test_confidence.py:92,105`. The routes the mandate named, `investor_kitas_retirement` and
  `pt_pma_setup`, do not cite E28G. HIGH.

### Surface 6 — Qdrant (read-only scroll from Pro, 2026-10-15 ~14:35Z)

`bali_zero_pricing_hybrid` holds 67 points. Its 4 investor rows match the catalogue (17/19/18/55 M). `visa_oracle` holds
90 points, 14 of them on the subject.

- **F40.** E28A point `762c2f04…` gives `stay_extension_days 730`; the pack has 365 per extension. The note "KITAP
  threshold INCREASED to Rp 15 billion (Pasal 176(2)(c))" is unverified against a saved page. LOW.
- **F41.** E28B point `b5213b2e…`: "Direct KITAP-INV after 5y (no language test). 10y variant also requires proof of
  prior Indonesia entry". Neither claim is on the page. MEDIUM.
- **F42.** E28D point `a2bc3a9d…`: "Investor Branch/Representative Office". The page says branch or subsidiary. LOW.
- **F43.** E28F point `6ecc8c5b…`: "Investor Real Estate (IKN Nusantara or property-based). Threshold Rp 5 billion+
  property." The page describes an IKN branch or subsidiary of a foreign company, USD 5M/10M. HIGH.
- **F44.** E28G point `225aed53…`: "Golden 10Y Real Estate — Rp 5 billion+ property". Concept note `b50440ec…`:
  "E28B/E28G Golden Visa". Neither product exists. HIGH.
- The writes need owner authorization (Q10); this is precedent from the E33 purge, "entrambi si".

### Surface 7 — legacy matcher (`/api/visa/match`)

- **F50. Invented budget band.** `services/visa_check/catalogue.py:275`: `min_budget_idr=500_000_000`. It renders as
  "(requires ≥ IDR 500M)" next to `:276` "(~IDR 10bn capital)". HIGH.
- **F51. Extension too long.** `catalogue.py:273-274`: `extensions=(1, 365 * 2)` → "Covers 1460 days total". The pack
  has 365 per extension. MEDIUM.
- **F52. Passport validity.** `services/visa_check/match_tree.py:129`: "Passport valid ≥ 24 months". The page says ≥ 6
  months. MEDIUM.
- **F53. Incorporation and processing time.** `match_tree.py:125` says "(or plan ready to incorporate on arrival)";
  the page requires a Kemenkumham deed and a sponsoring company. `app/routers/visa_check.py:166` returns 25 days; the
  page says 5 working days. MEDIUM.
- **F54. E28B/C/D/F absent from the legacy enum.** `catalogue.py:36-52`. MISSING, LOW. The legacy matcher stays, per
  Zero 2026-10-14; this is a backlog item, not a cure.

### Surface 8 — articles and llms files

Files: `apps/mouth/src/content/articles/immigration/e28a-investor-kitas-guide.mdx` and its ID twin `.id.mdx`. The ID
file carries every EN drift line for line.

- **F60. Render bug.** The ID page renders without its body. Live `?lang=id`: HTTP 200, 106,177 bytes, no article text
  on the server; the EN page is 412,838 bytes with the article.
  - The cause is a bare `<` before a digit at `.id.mdx:531` ("<183 hari") and `.id.mdx:617` ("anak-anak <21"). The EN
    file escapes both.
  - The parked lane `e4fccc5d8b` + `83debabf15` fixes both lines and adds an all-articles MDX guard.
  - **Open PR #8564** (the hourly bot, armed) rewrites the ID file. It re-introduces "<183" and keeps every content
    drift below. It must not merge as-is.
- **F61. Work rights inverted.**
  - `.mdx:77`: "…do not perform active work functions like management, operations, or board duties".
  - `.mdx:44`: "No. E28A is strictly for passive investors … you need E25B Director KITAS".
  - The page says: "diperkenankan untuk beraktivitas sebagai anggota direksi atau anggota dewan komisaris".
  - HIGH.
- **F62. The sub-variants are wrong.**
  - `.mdx:71`: "the seven sub-variants (E28A through E28G)".
  - `.mdx:182-212` gives each of B–G an "IDR 10B" threshold.
  - The pages publish USD tiers and say no sponsor is needed. HIGH.
- **F63. Phantom products.** E28E is described as an "SEZ Investor … IDR 10B+" (`.mdx:197-200`), but its page is empty.
  E28G is described as "Representative of Parent Company" (`.mdx:209`), but it is not in the pack.
- **F64. Passport validity.** `.mdx:227`: "Valid for minimum 18 months". The page says 6 months. MEDIUM.
- **F65. Processing time.** "5-7 working days" at `.mdx:90,177,278,579,726`; the page says 5 working days after payment.
  LOW.
- **F66. Extension contradicts itself.** `.mdx:567,577` say "another 2 years … IDR 18,000,000"; `:411` says "1 year";
  the pack has 365 per extension. MEDIUM. The sponsor line is MISSING.
- **F67.** `apps/mouth/public/llms.txt:88`: "E28E - KEK Investor KITAS: Contact". E28E is not a product. LOW.
- **F68.** `apps/mouth/public/llms-id.txt:8228`: "Investor asing kini secara kategoris bebas dari kebutuhan untuk
  memiliki sponsor lokal Indonesia". The E28A page says "Anda membutuhkan penjamin/sponsor". MEDIUM.
  - The live `llms-id.txt` is regenerated: 6.7 MB, dated 2026-10-15, 264 lines differ from the repo.
  - The cure goes to its producer, not the static copy.
- Backlog only: 20 other investor and golden articles state an E28A price or "IDR 10B". The list is in the read lane's
  (d) output. One of them, `visa-agent-vs-diy-indonesia.mdx:93,106`, carries prices that conflict with the catalogue.

### Surface 9 — MCP `nuzantara-knowledge`

Read live today:
- `search_service_pricing("investor KITAS E28A")` returns the 3 Investor KITAS rows and the KITAP row. OK.
- `search_service_pricing("golden visa investor")` returns no Golden rows. OK, on consultation.
- `get_visa_details(E28A..G)` is served from the PROD `visa_types` table, seeded by
  `migrations/scripts/seed_visa_types_complete_2026.py`.

- **F70.** E28A: `cost_visa` reads "17.000.000 - 19.000.000 IDR" (a range across two rows). `requirements` lists
  "Passport photo 4x6 red background" and "Return/onward ticket", neither on the page; the page's bank statement, CV and
  itinerary are missing. MEDIUM.
- **F71.** E28A: `allowed_activities` carries document requirements, such as "Proof of share ownership min Rp 10
  billion…" and "Company bank statements". This is the wrong field. LOW.
- **F72.** E28B: "Investasi minimal Rp 2.5 miliar"; the page says **USD** 2.5M (5y) / 5M (10y). The name "Golden Visa
  5Y" also omits the 10y tier. HIGH.
- **F73.** E28C omits the 10y tier (USD 700k, or a USD 1M apartment). LOW.
- **F74.** E28G is served as "E28G - Investor KITAS (Golden Visa 10Y)" with "Investasi Rp 5 miliar+". The product does
  not exist. HIGH.

## Adversarial review (Codex gpt-5.6-sol, read-only, 2026-10-15) — dispositions

Codex returned **UNSOUND**. Each point and what it changed:

- **Downgraded:**
  - F1 → MISS (an omission, not a contradiction).
  - F4 → OK. The Oracle labels 7–10 as Bali Zero's indicative window from complete documents, and Zero kept it (Q9).
  - F20 → MISS, the all-inclusive note only.
  - F22 → MISS (dead navigation).
  - F31 → LOW (`pt_pma_setup` separates 10 bn from 25 % paid-up). The real defect is the few-shot "subscribed capital".
  - F53 → only "plan ready to incorporate" stands. The 25 days is the matcher's end-to-end estimate.
- **Withdrawn:**
  - F21 for the generic KITAS checklist. Only the investor-scoped bullet "Meet minimum investment (for investor visa)" stays, as MISS.
  - F67 and the "phantom" label for E28E. The official list names E28E ("Visa Investor Kawasan Ekonomi Khusus", "Data Belum Tersedia"), so llms.txt "Contact" is consistent. Only invented E28E thresholds are DRIFT (F63).
- **Reconciled:** F33 was both OK and DRIFT. It is OK (fixed by #8527).
- **Added from the truth-table review:**
  - **F9:** pack `sponsor_types: ["INVESTMENT"]` on E28B/E28D/E28F, while each page says "Anda tidak membutuhkan penjamin/sponsor". Rule item S1.
  - **F10:** E28A `extension_policy` VERIFIED 365 × 100, while the page states no extension length. Rule item X1.
  - **F11:** E28D/E28F do not test the director/commissioner role the pages define. Rule item D1.
- **Added from missed drifts (verified on disk by the orchestrator):**
  - **F69:** `apps/mouth/src/content/visa/kitas/page.mdx:34`, "E28A … ≥ Rp 10 billion paid-in capital … 20–30 hari". The page tests own shares.
  - **F70:** same file `:35` and `:59`, "E28D — Director KITAS … Representative office directors (Kantor Perwakilan) … KPPA/KP3A". The page describes a branch or subsidiary of a foreign company, USD 25M/50M, 5/10 years. HIGH.
  - **F71:** `golden-visa-indonesia-complete-guide.mdx:420-428`, "Golden Visa (ITAP): Permanent residence, 5-10 year validity, IDR 350M+ investment". The Golden routes are limited-stay ITAS, priced in USD (E28C USD 350k). HIGH, because Zero's Q11 makes this article the nav target.
  - **F72:** `investor-kitas-guide.mdx:73`, a director needs E25B (rights inverted, as F61). Its ID description `:31` reads "IDR 10M" for 10 bn.
  - **F73 (backlog):** `services_data.ts:125`, passport 18 months on the generic KITAS checklist. The E28 pages say 6 months. Generic list, outside the E28 scope.
  - Also outside the e28a scope (backlog): `golden-visa-2026-updates.mdx:49,65` and `indonesia-golden-visa-2025-no-sponsor-no-merp-usd-25m-minimum.mdx:38`.
- **Plan defects accepted:**
  - PR C cannot fix Qdrant or `visa_types` by bytes. A data PR (C2) ships an idempotent `visa_types` migration and a payload-only Qdrant fixer (dry-run, backup, no embedding call), plus the source script fix. The orchestrator runs it on PROD after merge under Zero's Q10 authorization.
  - PR E traceability: F2/F3/F7/F9/F10/F11 map to the seq-30 rule items. F7 also needs interview/fact-mapper work (conductor items I-T05..I-T08, I-M05, after seq-30).
  - PR A is true to the ACTIVE pack, not to the page, for the E28A capital test. It names the figures the pack checks; I-M05 re-words it once seq-30 re-keys the rule (Zero Q1).
  - F6 (E28A "2-year stay permit") is consistent with Zero Q6 (no 1-year E28A).
- **Plan updates:** PR D now also carries F69–F72, and E28E is no longer deleted anywhere.

## Meta-pattern

Most drifts come from one belief: **"E28 = one investor KITAS with an IDR 10 bn capital test, plus seven variants
E28A–G sharing it."** That belief predates both Kepmen M.IP-08.GR.01.01/2025 and BKPM 5/2025. It survives in every layer
nobody re-grounded after the pack was built: KG routes, the legacy matcher, the Qdrant notes, the `visa_types` seed and
the e28a article. The pack itself carries a cousin of it in F2, F3 and F7.

## Plan (5 PRs at most, grouped by owner)

| PR | Covers | Findings |
|---|---|---|
| A | Oracle copy, decision-free. Conductor items I-M01, I-M02 and I-M03 (adapter), plus I-T01 and I-T03 (tree), taken over by this session through the conductor inbox | F1, F6, F8 (+ the conductor's RC03/RC04 copy findings) |
| B | Pricing, /services and terms: the terms sentence (after OD-I8), the FAQ sponsor line, the Golden Visa nav (after Q11), the all-inclusive note on the Investor rows | F20–F23 |
| C | Zantara, backend: KG routes, few-shot, v3/v4, the WhatsApp persona, the legacy matcher E28A entry, the `visa_types` E28 rows (migration), the Qdrant `visa_oracle` E28 points (after Q10) | F30–F35, F40–F44, F50–F53, F70–F74 |
| D | Articles: the e28a EN+ID content + the ID render fix (adopt the lane), llms.txt E28E line, the llms-id producer sentence | F60–F68 |
| E | Rule items for seq-30 (SEQ29-A1/A2/B1/B2/C1/D1/N1/P1/P2/S1/X1), sent with Pasal citations to the conductor inbox; signed only on READY-TO-SIGN | F2, F3, F7 |

Backlog, with owner and proof in PENDING-ARMS:
- F5, the documents checklist;
- F54, Golden in the legacy enum;
- the 20 other investor articles;
- F4, if Zero rules (b).
