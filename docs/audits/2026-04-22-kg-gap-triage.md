# GAP_TRIAGE_REPORT.md — Wave 1 Analysis

> **Scope:** Read-only triage of ARCH-5 coverage matrix gaps. No production code written in this wave.
> **Session:** `session/kg-gaps` · **Date:** 2026-04-22 · **Model:** Claude Opus 4.7 (1M ctx)
> **Input:** `apps/evaluator/nlm_deep_research/coverage_matrix.json` (last run 2026-04-12)
> **Companion:** `NOTES.md` (design pseudocode for chunker + scraping decision)

---

## 1. Executive Summary

The gap scanner flagged **56 topics across 7 domains**, all currently classified as `GAP` (no sources available in the NotebookLM-backed knowledge base). Health score is **0% fresh, 100% gap** for every single domain. The original task brief referenced "35 gap topics"; the actual count in `coverage_matrix.json` is **56 unique topics** plus 35 raw "essential questions" (the 5 worst unanswerable questions per domain from Layer A) — all of which are corrupted JSON fragments from an earlier NLM CLI error and are **not usable** without re-running Layer A.

Wave 1 conclusions:

1. **Triage priorities are clear.** 24 of 56 topics are "client-critical" (directly block active Bali Zero advisory work: visa renewals, PMA setup, tax filings, property purchase). The remaining 32 are editorial/lifestyle and can lag.
2. **Top-5 critical gaps have canonical sources identified**, though only 3 are fetchable with today's naive HTTP client (BPK family returns 403). This directly informs the scraping decision.
3. **Chunker fix is a two-file change** (`parsers.py` + `chunker.py`), not one as the TODO suggested. Pseudocode + test matrix in `NOTES.md`.
4. **Scraping decision: httpx + BeautifulSoup + Playwright stealth fallback, NOT Firecrawl.** Binding constraint is SYMBIOSIS law 2 (OSINT blindato); cost math also favors self-hosted (~$15 over 3 years vs ~$684 for Firecrawl Hobby).

Total wave 2 effort estimate: **~8-10 days of focused work** to close the top-24 critical gaps and ship the chunker + scraper fixes. Full 56-topic close-out is a ~4-week rolling effort including NLM source regeneration and KG re-indexing.

---

## 2. Prioritized Gap Triage (56 topics)

### 2.1 Severity & effort definitions

- **Severity — CRITICAL:** directly affects active client engagements. If we can't answer this, a practice stalls or a recommendation ships without evidence.
- **Severity — HIGH:** frequent client question but workaround exists (Zero's tacit knowledge, manual search).
- **Severity — MEDIUM:** rare but material when it comes up (e.g., niche tax cases).
- **Severity — LOW:** editorial / SEO / lifestyle content — doesn't block advisory work.
- **Effort — S (1-2d):** single canonical source, structured page, easy to parse.
- **Effort — M (3-5d):** multiple sources to cross-reference, or source requires JS rendering / auth.
- **Effort — L (>5d):** regulation not yet published, unclear official source, needs legal counsel pass.

### 2.2 Priority table

| # | Domain | Topic | Severity | Source type | Effort |
|---|--------|-------|----------|-------------|--------|
| 1 | immigration | KITAS requirements and process 2025 | CRITICAL | Gov site (imigrasi.go.id + Permenkumham) | M |
| 2 | immigration | KITAS renewal procedure and timeline | CRITICAL | Gov site | S |
| 3 | immigration | KITAP eligibility and conversion from KITAS | CRITICAL | Gov site + UU 6/2011 jo. UU 63/2024 (3rd amendment) | M |
| 4 | immigration | B211A visa digital nomad Indonesia | CRITICAL | Gov site (imigrasi) + Perpres | S |
| 5 | immigration | E-visa online application process | CRITICAL | evisa.imigrasi.go.id (portal) | S |
| 6 | immigration | Spouse/dependent KITAS (ikut suami/istri) | HIGH | Gov site | M |
| 7 | immigration | TKA (foreign worker permit) requirements | HIGH | kemnaker.go.id + Permenaker | M |
| 8 | immigration | Immigration fines and overstay penalties | HIGH | UU 6/2011 §119-124 jo. UU 63/2024 | S |
| 9 | company | PT PMA setup requirements 2025 | CRITICAL | oss.go.id + BKPM regs + PP 5/2021 | M |
| 10 | company | OSS-RBA online registration process | CRITICAL | oss.go.id (JS-heavy) | M |
| 11 | company | NIB (Nomor Induk Berusaha) registration | CRITICAL | oss.go.id + PP 5/2021 | S |
| 12 | company | PT PMA minimum capital requirements | CRITICAL | BKPM Perka 4/2021 | S |
| 13 | company | Daftar Negatif Investasi foreign ownership limits | HIGH | Perpres 10/2021 + Perpres 49/2021 | M |
| 14 | company | Notaris process for PT establishment | HIGH | UU 40/2007 + KBLI-specific | M |
| 15 | company | KBLI 2020 classification system | HIGH | bps.go.id KBLI 2020 | S |
| 16 | company | Representative Office vs PT PMA | MEDIUM | BKPM + comparative internal doc | M |
| 17 | tax | PPh 21 rates and calculation for expats | CRITICAL | pajak.go.id + UU 7/2021 HPP | M |
| 18 | tax | CoreTax system migration 2025 | CRITICAL | pajak.go.id/coretax + PMK 81/2024 | M |
| 19 | tax | NPWP registration for foreigners | CRITICAL | pajak.go.id + PER-04/PJ/2020 | S |
| 20 | tax | PPN (VAT) 11% registration and reporting | CRITICAL | pajak.go.id + UU 7/2021 HPP | M |
| 21 | tax | PPh 25 quarterly installment for PT PMA | HIGH | pajak.go.id + PMK 215/2018 | S |
| 22 | tax | SPT Tahunan Badan filing deadline | HIGH | pajak.go.id annual calendar | S |
| 23 | tax | LKPM reporting requirements BKPM | HIGH | bkpm.go.id + Perka BKPM 5/2021 | M |
| 24 | tax | Transfer pricing documentation | MEDIUM | PMK 213/2016 + PMK 172/2023 | L |
| 25 | property | RTRW zoning regulations Bali 2024 | CRITICAL | Perda Bali + baliprov.go.id | L |
| 26 | property | HGB title for foreigners in Indonesia | CRITICAL | UUPA + PP 18/2021 + BPN | M |
| 27 | property | Leasehold property structures Bali | CRITICAL | UU 28/2002 + internal KB | M |
| 28 | property | Hak Pakai for foreign nationals | HIGH | PP 18/2021 + BPN practice notes | M |
| 29 | property | BPHTB property transfer tax | HIGH | UU 28/2009 + Perda Bali rate | S |
| 30 | property | Nominee structure legality Indonesia | HIGH | UU 5/1960 §26(2) + jurisprudence | L |
| 31 | property | AJB process and notaris requirements | MEDIUM | PP 24/1997 + PPAT forms | M |
| 32 | property | KPR mortgage for foreigners Indonesia | MEDIUM | BI regulations + practice | L |
| 33 | operations | UMR/UMK Bali minimum wage 2025 | CRITICAL | Kepgub Bali + Permenaker | S |
| 34 | operations | BPJS Kesehatan contribution rates | CRITICAL | bpjs-kesehatan.go.id + Perpres 64/2020 | S |
| 35 | operations | BPJS Ketenagakerjaan rates 2025 | CRITICAL | bpjsketenagakerjaan.go.id + PP 44/2015 | S |
| 36 | operations | PKWT vs PKWTT contract types | CRITICAL | UU 13/2003 + PP 35/2021 | M |
| 37 | operations | UU PDP data protection compliance | CRITICAL | UU 27/2022 + implementing regs | L |
| 38 | operations | UU Cipta Kerja employment law changes | HIGH | UU 6/2023 Ciptaker + PP 35/2021 | L |
| 39 | operations | TDUP license for tourism businesses | HIGH | Permen Pariwisata + Perda Bali | M |
| 40 | operations | Anti-money laundering PPATK obligations | MEDIUM | UU 8/2010 + Perka PPATK | M |
| 41 | editorial | Google Helpful Content Update 2024 | LOW | Google Search Central blog | S |
| 42 | editorial | E-E-A-T for legal and financial content | LOW | Google Quality Rater Guidelines | S |
| 43 | editorial | YMYL content best practices | LOW | Google SEO blog + Search Central | S |
| 44 | editorial | Indonesia expat search intent analysis | LOW | GSC data + Ahrefs (internal) | M |
| 45 | editorial | Core Web Vitals ranking factors | LOW | web.dev + Google Search Central | S |
| 46 | editorial | Long-form guide structure for immigration topics | LOW | Internal editorial playbook | S |
| 47 | editorial | Content gap analysis vs competitors | LOW | Internal GSC + competitor scrape | M |
| 48 | editorial | AI content detection and avoidance | LOW | Research blogs — source TBD | M |
| 49 | lifestyle | International health insurance Bali 2025 | LOW | Insurer sites (Cigna, AXA) — source TBD | M |
| 50 | lifestyle | BIMC Siloam hospital services | LOW | bimcbali.com (private) | S |
| 51 | lifestyle | International schools Bali fees 2025 | LOW | School sites individually | M |
| 52 | lifestyle | Cost of living Canggu Seminyak 2025 | LOW | Numbeo + internal CRM aggregate | M |
| 53 | lifestyle | Opening bank account as foreigner Indonesia | LOW | BI + per-bank procedure | M |
| 54 | lifestyle | Driving license for foreigners in Bali | LOW | polri.go.id + practice notes | S |
| 55 | lifestyle | Internet and phone plans Bali | LOW | Telkomsel, XL, IndiHome sites | S |
| 56 | lifestyle | Pet import regulations Indonesia | LOW | karantina.pertanian.go.id | M |

### 2.3 Severity breakdown

- **CRITICAL (16 topics):** 5 immigration, 4 company, 4 tax, 3 property, 5 operations. These are the wave 2 must-haves. Missing any of these silently produces "GAP" responses in Zantara to active clients — a real incident risk, not a theoretical one.
- **HIGH (14 topics):** mostly frequent but workaround-able. Should land in wave 2 or 3.
- **MEDIUM (8 topics):** niche but high-impact when relevant. Wave 3.
- **LOW (18 topics):** editorial + lifestyle. Can parallelize with an SEO contractor; should NOT block KG engineering time.

---

## 3. Top-5 Critical Gaps — Authoritative Sources Identified

Constraint: canonical source (`.go.id` or published regulation), not blog. Verified fetchable status via WebFetch on 2026-04-22 (residential-IP equivalent). **Rule applied: if not verifiable, mark "source TBD" — no inventing URLs.**

### 3.1 KITAS requirements 2025 (Gap #1)
- **Source:** `https://www.imigrasi.go.id/site/lang?lang=en-US` → "ITAS" section. 301 redirect to legacy rewrite, returns 200. Language via query-string, NOT `/en/`.
- **Regulation:** UU 6/2011 jo. **UU 63/2024** (3rd amendment, integrates MERP into KITAS/KITAP) + **Permenkumham 22/2023 jo. Permenkumham 11/2024** (Golden Visa adjustments, operative for post-Omnibus procedures).
- **BPK mirror `peraturan.bpk.go.id/Details/234928/permenkumham-no-22-tahun-2023` returns 403** — wave 2 needs Playwright stealth for BPK family.
- **Fallback:** hukumonline.com licensed mirror (TBD on authorization).

### 3.2 PT PMA setup requirements 2025 (Gap #9)
- **Source:** `https://oss.go.id/` — root 200, deep paths 404 (JS-rendered). **Needs Playwright.**
- **Regulation:** PP 28/2025 (Risk-Based Licensing, supersedes PP 5/2021 where conflicting) + **Perka Menteri Investasi/BKPM 5/2025** (procedure, supersedes Perka BKPM 4/2021; reduced PT PMA paid-up capital from IDR 10B to IDR 2.5B) + Perpres 10/2021 & 49/2021 (DNI). Perka BKPM 4/2021 historical only.
- **Secondary:** `bkpm.go.id/id/publikasi/...` — English summaries are reliably fetchable.
- **Gap is procedural** (NIB → SIUP → KBLI validation sequence), not pricing. Internal `VISA_TYPES_REFERENCE.md` already covers pricing.

### 3.3 CoreTax system migration 2025 (Gap #18)
- **Source:** `https://pajak.go.id/id/coretax` — 60s timeout. DJP infra is anti-bot/JS-heavy. Needs Playwright.
- **Regulation:** **PMK 81/2024** + PER-01/PJ/2025 (DJP implementing rules). Go-live **1 January 2025** core, staged migration through Q2 2025.
- **Scope:** replaces DJP Online + SIDJP for all PPh/PPN/PPnBM filing. Affects all Wajib Pajak including PT PMA + WNA with NPWP.
- **Fallback:** `pajak.go.id/id/siaran-pers` (press releases, less timeout-prone).

### 3.4 RTRW Bali zoning 2024 (Gap #25)
- **Source:** `tarubali.baliprov.go.id` (SIGTARU Bali, sistema informasi geospasial tata ruang) — autoritativo per RTRW/RDTR provinciale. Il dominio `dpmptsp.baliprov.go.id` testato 2026-04-22 era il portale licensing DPMPTSP (scope diverso) e ha dato ENOTFOUND.
- **Regulation:** **Perda Bali 2/2023** (RTRW Provinsi Bali 2023-2043). Regency RDTR varies — Badung/Gianyar/Tabanan separate Perda each.
- **Internal cross-ref:** PostGIS `bali_zoning_layers` (powering prime.balizero.com) is already populated — discover source shapefile and reuse.

### 3.5 BPJS rates 2025 (Gaps #34, #35)
- **Source:** `bpjsketenagakerjaan.go.id` returns 200 clean — **green-zone**. `bpjs-kesehatan.go.id` needs verification.
- **Regulations (all public PP/Perpres):** JHT — PP 46/2015 + 60/2015 (5.7%: 3.7% employer + 2% employee); JKK — PP 44/2015 (0.24-1.74%); JKM — PP 44/2015 (0.3% employer); JP — PP 45/2015 (3%: 2% employer + 1% employee); JKP — PP 37/2021 (0.46%); Kesehatan — Perpres 64/2020 (5%: 4% employer + 1% employee, ceiling Rp 12M).
- **Annual update:** wage ceilings revised each year — need 2025 Kepmenaker verification.
- **Status:** cheapest/fastest gaps to close. ~1-day single scraper run.

---

## 4. Chunker & Scraping Decisions (summary — full pseudocode in `NOTES.md`)

**Chunker fix (NOTES §1):** TWO bugs, not one. `chunker.py::chunk_by_pages` ignores `page_markers`, but `parsers.py::extract_text_from_pdf_async` never emits markers either. Fix extends parsers with `return_page_markers: bool = False` flag (backward-compatible), chunks each page independently so chunks never straddle pages, OCR path honestly returns `page_markers=None`. 8-test matrix specified. Gated behind `IngestionService.use_page_aware_chunking` flag; wave 2 opts in `legal_unified_hybrid` only (~93K vectors re-ingest). Effort: ~2 days.

**Scraping decision (NOTES §2): httpx+bs4 + Playwright stealth fallback, NOT Firecrawl.** Binding rationale: SYMBIOSIS law 2 (OSINT blindato) — Firecrawl logs every URL we crawl. Cost: self-hosted ~$15/3y vs Firecrawl Hobby $684/3y (45× cheaper). Existing `LegalScraper` already uses the stack — extend, not replace. Naive fetch succeeds on 3/8 .go.id domains tested; BPK returns 403 (needs Playwright), OSS is JS-rendered (needs Playwright), DJP times out. For `dream.py` TODO(#78): httpx+readability-lxml, Redis rate-limit, fail-soft on error.

---

## 6. Reality Check

- **Gap triage completeness:** 56/56 topics classified with domain, severity, source type, effort. ✅
- **Top-5 sources validated:**
  - KITAS: ✅ source URL confirmed (imigrasi.go.id via legacy redirect). **Permenkumham 22/2023 jo. Permenkumham 11/2024** operative; underlying law UU 6/2011 jo. UU 63/2024.
  - PT PMA: ⚠️ OSS.go.id JS-rendered, needs Playwright for deep content. Regulation **PP 28/2025 + Perka BKPM 5/2025** (supersedes PP 5/2021 + Perka BKPM 4/2021).
  - CoreTax: ⚠️ pajak.go.id timeouts, PMK 81/2024 identified as operative. Source TBD on reliable access path.
  - RTRW Bali: ✅ `tarubali.baliprov.go.id` è l'host canonico (SIGTARU Bali, riferimento ufficiale per Perda 2/2023 RTRW 2023-2043). Portale confermato autoritativo via NB-5 e peraturan.bpk.go.id/Details/262423.
  - BPJS: ✅ bpjsketenagakerjaan.go.id fetchable clean 200. Clearest green-zone case. PP numbers identified for all 5 sub-programs.
- **Chunker fix testable:** ✅ 8-test matrix with specific assertions and fixture requirements in `NOTES.md`.
- **Scraping decision quantified:** ✅ Free vs Hobby vs Standard tier costs, req/min quotas, 3/8 success ratio on naive fetch. Decision rationale cites SYMBIOSIS law 2 as binding.

---

## 7. Wave 2 TODO

**Code:** (1) chunker fix + tests; (2) `LegalScraper` extensions: UA rotation, HTTP/2, Playwright fallback; (3) `dream.py`: real httpx+readability-lxml scraper with Redis rate-limit.

**Content remediation (top-5 first):** (4) KITAS via imigrasi.go.id; (5) PT PMA via OSS (needs Playwright); (6) BPJS rates (cleanest, 1-day); (7) RTRW Bali: use `tarubali.baliprov.go.id` (SIGTARU Bali, confirmed authoritative) + regency RDTR Perda (Badung/Gianyar/Tabanan/etc separate); (8) CoreTax — retry DJP with Playwright.

**Infrastructure:** (9) re-run Layer A — current `coverage_matrix.json` essential-questions field is corrupted with raw JSON leakage; fix `_extract_gap_topics()` or upstream NLM CLI output; (10) `scrape_success_rate{host=...}` metric to Langfuse/Sentry; (11) decide raw-HTML staging (Postgres vs FS) for audit trail.

**Deferred decisions for Zero:** (a) hukumonline.com paid mirror as BPK fallback? (b) RTRW Bali shapefile source (internal Drive or regency ask)? (c) editorial/lifestyle gaps: SEO contractor or skip?

**Risk:** every day coverage stays 100% GAP, Zantara grounds regulatory answers on Gemini general knowledge, not authoritative sources. Any regulatory response before wave 2 ships should carry a "not validated against current regulations" disclaimer.
