# NB-2 Immigration & Visa — Full Pipeline Testing Report

> **Classification:** Internal — For AI Agent Review
> **Date:** 2026-03-28
> **Author:** Claude Opus 4.6 (Pipeline Architect) + Gemini 3.1 Pro + Codex GPT-5.4 + DeepSeek R1 671B
> **Notebook:** NB-2: Immigration & Visa — Indonesia 2025
> **NLM ID:** `cff93ab0-813a-42f2-a8de-36987e724271`
> **Verdict:** 🟢 GREEN — GO FOR PRODUCTION (8/8 phases pass, 0/7 hard-blockers)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Source Inventory — Complete Catalog](#3-source-inventory)
4. [Claim Registry — All 19 Claims](#4-claim-registry)
5. [Source Value Scores — Full Ranking](#5-source-value-scores)
6. [Testing Protocol — 8 Phases Detailed](#6-testing-protocol)
7. [Quality Verification Framework](#7-quality-verification-framework)
8. [Gap Analysis — What's Missing](#8-gap-analysis)
9. [Open Questions](#9-open-questions)
10. [Adversarial Review Results](#10-adversarial-review)
11. [Handoff Package Specification](#11-handoff-package)
12. [Failure Modes & Recovery](#12-failure-modes)
13. [NHS Health Tracking](#13-nhs-health)
14. [Production Deployment Plan](#14-production-plan)
15. [Appendices](#15-appendices)
16. [Gemini Master Query Batch — Complete Results](#16-gemini-master-query-batch)

---

## 1. Executive Summary

### What this pipeline does

The NLM Deep Research Pipeline is an automated nightly intelligence system that queries NotebookLM's NB-2 notebook (Immigration & Visa Indonesia), extracts verifiable claims from responses, scores them by confidence, and passes the best findings to the intel scraper and War Room as grounded intelligence.

### Testing results

| Metric                           | Value                                       |
| -------------------------------- | ------------------------------------------- |
| Test phases completed            | 8/8                                         |
| Hard-blockers                    | 0/7                                         |
| Total claims extracted           | 33                                          |
| VERIFIED claims                  | 17 (51.5%)                                  |
| PROVISIONAL claims               | 9 (27.3%)                                   |
| LOW/SOURCE_GAP claims            | 7 (21.2%)                                   |
| Sources in NB-2                  | 51                                          |
| T0 National sources              | 9 (6 full text, 2 metadata, 1 partial OCR)  |
| ESSENTIAL sources (SVS ≥ 0.70)   | 6                                           |
| VALUABLE sources (SVS 0.45-0.69) | 9                                           |
| Notebook Health Score (NHS)      | 0.801 (EXCELLENT)                           |
| Gemini Master Query Batch        | 24/24 completed                             |
| NLM API calls consumed           | ~25                                         |
| Total test duration              | ~5 hours (2 sessions)                       |
| Production start date            | Monday 2026-03-31, 01:10 WITA               |
| Guide errors found & corrected   | 1 (Golden Visa E28B 10yr: USD 5M, not 2.5M) |

### Design methodology

Each of the 7 design steps was developed through parallel consultation with Gemini 3.1 Pro (1M context, search-grounded), Codex GPT-5.4 (sandbox execution), and DeepSeek R1 671B (chain-of-thought reasoning). Claude Opus 4.6 served as the synthesizing architect, resolving conflicts and merging contributions into unified specifications.

---

## 2. Pipeline Architecture

### 2.1 Operational Window

```
01:00 WITA ─── Pre-flight checklist (12 points)
01:10 WITA ─── L1 Monitoring Query (Bahasa Indonesia, Cluster A-E rotating)
01:25 WITA ─── L1 results: import sources, extract claims, compute SVS
01:35 WITA ─── L2 Comparative Query (with L1 context injection)
01:50 WITA ─── L2 results: cross-query dedup, new claims, corroboration boost
01:55 WITA ─── Daily triage: QUARANTINE→ACTIVE, consolidation check
02:10 WITA ─── Handoff package generation (latest.json)
02:15 WITA ─── NHS computation, Telegram alert if < 0.60
02:20 WITA ─── Pipeline IDLE
       ↓
03:00 WITA ─── Intel scraper reads handoff (independent, runs regardless)
```

### 2.2 Weekly Rotation

| Day       | Cluster                        | Topics                                                              | Query Level        |
| --------- | ------------------------------ | ------------------------------------------------------------------- | ------------------ |
| Monday    | A — Work Permits               | RPTKA, TKA, DKPTKA, KITAS Kerja, KITAS Investor                     | L1 + L2            |
| Tuesday   | B — Stay Permits               | KITAP, ITAS Sponsor, Family Reunification                           | L1 + L2            |
| Wednesday | C — Visit Visas                | B211A, VOA, e-VOA, Visa-Free                                        | L1 + L2            |
| Thursday  | D — Special + L3               | Second Home, Retirement, Digital Nomad, Golden Visa + Deep Analysis | L1 + L3            |
| Friday    | E — Compliance + Consolidation | Overstay, Reporting, Enforcement + Weekly Digest                    | L1 + Consolidation |
| Weekend   | OFF                            | Indonesian gazette publishes Mon-Fri only                           | —                  |

### 2.3 Query Levels

| Level  | Purpose                            | Frequency          | Example                                                               |
| ------ | ---------------------------------- | ------------------ | --------------------------------------------------------------------- |
| **L1** | Monitoring — What changed?         | Daily (2/day)      | "Peraturan terbaru tentang RPTKA dan izin kerja TKA tahun 2025-2026"  |
| **L2** | Comparative — How did it change?   | Daily (follows L1) | "Bandingkan prosedur DKP-TKA sebelum dan sesudah PP 34/2021"          |
| **L3** | Deep analysis — Why? Implications? | Weekly (Thursday)  | "Dampak UU 63/2024 terhadap ekosistem keimigrasian Bali"              |
| **L4** | Cross-domain — Connections?        | Monthly            | "Hubungan antara perubahan visa kerja dan regulasi properti PMA 2026" |

### 2.4 Language Strategy

| Language         | Weight | Target Sources                    | Used For                                       |
| ---------------- | ------ | --------------------------------- | ---------------------------------------------- |
| Bahasa Indonesia | 60-70% | .go.id, hukumonline, Kompas       | Regulations, circulars, official announcements |
| English          | 20-30% | Jakarta Globe, law firms, BKPM EN | Analysis, comparison, international coverage   |
| Mixed bridge     | 10-15% | Cross-taxonomy                    | When term is ID but market searches EN         |

### 2.5 State Files

| File                          | Location                                     | Format              | Purpose                                                      |
| ----------------------------- | -------------------------------------------- | ------------------- | ------------------------------------------------------------ |
| `nlm_nb2_pipeline_state.json` | `apps/evaluator/`                            | JSON                | Pipeline status, NHS, circuit breakers, schedule, invariants |
| `nlm_nb2_sources.json`        | `apps/evaluator/`                            | JSON                | Source registry with SVS, claims, dedup, metadata            |
| `nlm_nb2_claims.jsonl`        | `apps/evaluator/`                            | JSONL (append-only) | Claim extraction database                                    |
| `latest.json`                 | `~/.agent/decisions/nlm_to_scraper/handoff/` | JSON                | Scraper handoff package                                      |

### 2.6 Design Documents

| Step | Document                           | Scope                                                |
| ---- | ---------------------------------- | ---------------------------------------------------- |
| 1    | `01_query_design.md`               | 20 templates, 5 clusters, dual-language, anti-noise  |
| 2    | `02_sequencing.md`                 | 01:00-02:20 WITA, 2 queries/day, weekly rotation     |
| 3    | `03_quality_verification.md`       | 7-tier sources, confidence scoring, claim extraction |
| 4    | `04_source_management.md`          | 70 ACTIVE cap, 6-stage lifecycle, SVS, NHS           |
| 5    | `05_scraper_integration.md`        | File-based handoff, TRS, NLMEnricher adapter         |
| 6    | `06_failure_modes.md`              | 30 failure modes, 10 invariants, 3 circuit breakers  |
| 7    | `07_testing_protocol.md`           | 98 unit/integration/regression tests + 8 live phases |
| 7b   | `07b_testing_protocol_deepseek.md` | Baselines, KPIs, statistical tests, cost model       |

---

## 3. Source Inventory — Complete Catalog

### 3.1 Summary

| Metric                   | Value                                                                           |
| ------------------------ | ------------------------------------------------------------------------------- |
| Total sources in NB-2    | 51                                                                              |
| Total in source registry | 50 (registry update pending for errata)                                         |
| ACTIVE                   | 51                                                                              |
| QUARANTINE               | 0                                                                               |
| ARCHIVED                 | 0                                                                               |
| T0 full-text PDFs        | 4 (Permenkumham 22/2023, Permenkumham 11/2024, PP 34/2021, Permenimipas 5/2025) |
| Errata Corrige sources   | 1 (Golden Visa E28B threshold correction)                                       |

### 3.2 Category Distribution

| Category      | Count | Budget (Design) | Status                            |
| ------------- | ----- | --------------- | --------------------------------- |
| canonical     | 34    | 15-25           | ⚠️ ABOVE — needs reclassification |
| working       | 0     | 25-35           | ⚠️ BELOW — same issue             |
| master_digest | 4     | 4-8             | ✅ OK                             |
| reference     | 6     | 3-6             | ✅ OK                             |

**Note:** ~15 curated guide sources (`*_guida_2025.txt`) are classified as `canonical` but should be `working`. They are internal operational documents, not laws. This is a Day 1 production fix.

### 3.3 Tier Distribution

| Tier      | Label                    | Count                           | V_tier | Description                                                                 |
| --------- | ------------------------ | ------------------------------- | ------ | --------------------------------------------------------------------------- |
| T0        | National Primary Law     | 9                               | 1.00   | UU, PP, Permen — highest authority (6 full text, 2 metadata, 1 partial OCR) |
| T1        | National Implementation  | 5                               | 0.90   | Circulars, Ditjen guides                                                    |
| T2        | Regional/Local Authority | 27                              | 0.80   | Bali-specific guides, procedures                                            |
| T3        | Local Enforcement        | 3                               | 0.65   | Claims DB, FAQ, pricing reference                                           |
| MD        | Master Digest            | 4                               | 0.50   | Our synthesized documents                                                   |
| Errata    | Correction Notes         | 1                               | 0.95   | Guide error corrections backed by T0                                        |
| **TOTAL** |                          | **49** (+2 metadata duplicates) |        |                                                                             |

**T0 Source Availability Matrix (updated 2026-03-28 22:00):**

| T0 Source                                 | Full Text in NB-2?                                | Action                       |
| ----------------------------------------- | ------------------------------------------------- | ---------------------------- |
| UU 6/2011 (Immigration Law)               | ✅ via BPK                                        | —                            |
| UU 63/2024 (Amendment)                    | ✅ 2 sources (provisions + BPK)                   | —                            |
| PP 34/2021 (TKA Employment)               | ⚠️ Partial (Penjelasan only, body may be scanned) | Consider OCR or re-download  |
| Permenkumham 22/2023 (Visa Index)         | ✅ Full PDF (115 pages)                           | —                            |
| Permenkumham 11/2024 (VITAS/ITAS)         | ✅ Full PDF                                       | —                            |
| Permenkumham 29/2021 (Implementation)     | ✅ via BPK                                        | —                            |
| Permenimipas 5/2025 (Penjamin Revocation) | ✅ Full PDF (3 pages)                             | —                            |
| PP PNBP (Fee Schedule)                    | ❌ Not in NB-2                                    | Source not yet identified    |
| Perda Bali 6/2023 (Tourist Levy)          | ❌ Not in NB-2                                    | Local Perda, not national T0 |

### 3.4 Complete Source List — Tier T0 (National Primary Law)

| #   | NLM Source ID                          | Title                                 | SVS   | Class    | Claims | Pinned |
| --- | -------------------------------------- | ------------------------------------- | ----- | -------- | ------ | ------ |
| 1   | `0e1fd3f8-2e7d-47eb-9cfb-e69d2e48b934` | UU No. 6 Tahun 2011 (Keimigrasian)    | 0.500 | VALUABLE | 0      | Yes    |
| 2   | `4061643c-5660-4f8c-83b4-c507565f47d0` | UU No. 63 Tahun 2024 (BPK Full Text)  | 0.500 | VALUABLE | 0      | Yes    |
| 3   | `adc39025-f3ec-4a51-adc0-57f7c0c212ce` | UU No. 63 Tahun 2024 — Key Provisions | 0.623 | VALUABLE | 2      | Yes    |
| 4   | `60025a37-f8cb-4aeb-a8e2-634f8661d61b` | PP No. 31 Tahun 2013                  | 0.300 | MARGINAL | 0      | Yes    |
| 5   | `452d8a6f-2867-4adc-aa27-c993ad8907fa` | PP No. 48 Tahun 2021                  | 0.300 | MARGINAL | 0      | No     |

**Analysis:**

- UU 63/2024 is present in two formats: key provisions text (actively cited, 2 claims) and BPK full text (no claims yet). Cross-linked as known duplicates.
- UU 6/2011 (the predecessor immigration law) has no claims — NLM references it via UU 63/2024's amendments.
- PP 31/2013 and PP 48/2021 have no claims — they are structural anchors for PNBP fee schedules and RPTKA framework.

**GAPS IDENTIFIED:**

- ❌ **UU No. 1 Tahun 2026 (Imigrasi)** — Referenced in query designs but NOT in NB-2. OQ-003 tracks whether this law exists.
- ❌ **PP No. 34 Tahun 2021** — The regulation that abolished IMTA and reformed RPTKA. Cited in 3 claims but NOT present as a direct T0 source in NB-2. Currently only referenced through guide documents.
- ❌ **Permenkumham No. 22 Tahun 2023** — The regulation establishing E23 visa index. Cited in claims but only available through guide documents, not as a T0 direct source.
- ❌ **Permenaker on RPTKA/TKA (latest)** — Referenced in design but not individually sourced.
- ❌ **Permenaker on DKPTKA (latest)** — Referenced in design but not individually sourced.
- ❌ **Permenimipas No. 5 Tahun 2025** — New guarantor rules, cited by NLM but not individually sourced.

### 3.5 Complete Source List — Tier T1 (National Implementation)

| #   | NLM Source ID                          | Title                                          | SVS   | Class     | Claims |
| --- | -------------------------------------- | ---------------------------------------------- | ----- | --------- | ------ |
| 1   | `9fbfd84a-b059-4a9d-8b8e-add475c51066` | jabatan_tka_kepmen228_settori_ammessi_2025.txt | 0.808 | ESSENTIAL | 3      |
| 2   | `2e37838b-b0d0-48d6-9cd2-f8aabf8b36b2` | jabatan_tka_vietate_kepmen349_2025.txt         | 0.721 | ESSENTIAL | 2      |
| 3   | `8abf1fe6-c884-4bc2-aa7d-6fd509c5ec54` | nb2_immigration_circulars.txt                  | 0.696 | VALUABLE  | 2      |
| 4   | `bd2cd5d2-1d7f-4d86-b479-a994366aa655` | nb2_tka_rptka_guide.txt                        | 0.621 | VALUABLE  | 2      |
| 5   | `db80b1c3-05e7-4190-a5f3-f8b9b4cb9f6e` | rptka_dkp_tka_guida_2025.txt                   | 0.485 | VALUABLE  | 1      |

**Analysis:**

- Kepmenaker 228/2019 (permitted positions) and 349/2019 (prohibited positions) guides are the top T1 sources — both ESSENTIAL with 2-3 claims each.
- Immigration circulars document includes SE 3/836/PK.04/I/2026 (One Sponsor Policy) and SIAPKerja cross-check requirements.
- All 5 T1 sources are actively cited by NLM.

**GAPS IDENTIFIED:**

- ❌ **Surat Edaran Ditjen Imigrasi (latest 3)** — Design calls for 3 SE sources. Only nb2_immigration_circulars.txt covers SE content, bundled as one.
- ❌ **BKPM Investment Guidelines (PMA)** — Referenced in design seed list but not present. Critical for Cluster A (KITAS Investor).
- ❌ **OSS-RBA operating procedures** — Referenced in design but not individually sourced. OSS information comes indirectly through guide documents.
- ❌ **Kepmenaker 228/2019 original regulation text** — Only the analysis guide is present, not the actual regulation PDF/text. Same for 349/2019.

### 3.6 Complete Source List — Tier T2 (Regional/Local Authority)

**Cluster A — Work Permits (with claims):**

| #   | Title                                        | SVS   | Class     | Claims | Notes                                                   |
| --- | -------------------------------------------- | ----- | --------- | ------ | ------------------------------------------------------- |
| 1   | izin_kerja_tka_procedura_completa_2025.txt   | 0.861 | ESSENTIAL | 6      | Top source overall. Complete TKA work permit procedure. |
| 2   | kitas_e23_tka_guida_2025.txt                 | 0.819 | ESSENTIAL | 4      | KITAS E23 specifics, cited in every L1/L2.              |
| 3   | alih_status_offshore_autogate_guida_2025.txt | 0.671 | VALUABLE  | 2      | Alih Status procedures, enforcement divergence flagged. |
| 4   | merp_rientro_guida_2025.txt                  | 0.596 | VALUABLE  | 2      | MERP integration under UU 63/2024.                      |

**Cluster B — Stay Permits (no claims yet — not queried):**

| #   | Title                                              | SVS   | Class    | Notes                           |
| --- | -------------------------------------------------- | ----- | -------- | ------------------------------- |
| 5   | kitap_guida_2025.txt                               | 0.399 | MARGINAL | KITAP permanent residence guide |
| 6   | kitas_e31_famiglia_guida_2025.txt                  | 0.399 | MARGINAL | Family KITAS                    |
| 7   | kitas_religioso_second_home_guida_2025.txt         | 0.399 | MARGINAL | Religious + second home KITAS   |
| 8   | imk_itk_itb_itp_documenti_soggiorno_guida_2025.txt | 0.399 | MARGINAL | Stay document types overview    |

**Cluster C — Visit Visas (no claims yet):**

| #   | Title                                  | SVS   | Class    | Notes                              |
| --- | -------------------------------------- | ----- | -------- | ---------------------------------- |
| 9   | visto_c1_turismo_guida_2025.txt        | 0.399 | MARGINAL | C1 tourist visa                    |
| 10  | visto_c2_c7_c8_guida_2025.txt          | 0.399 | MARGINAL | C2/C7/C8 business/cultural/medical |
| 11  | visto_c12_c18_c22_guida_2025.txt       | 0.399 | MARGINAL | C12/C18/C22 other visit categories |
| 12  | visto_d2_d12_multiplo_guida_2025.txt   | 0.399 | MARGINAL | D2/D12 multiple entry              |
| 13  | visto_diplomatico_dinas_guida_2025.txt | 0.399 | MARGINAL | Diplomatic/service visas           |
| 14  | visto_voa_b1b2b3b4_guida_2025.txt      | 0.399 | MARGINAL | VOA and B-series visas             |

**Cluster D — Special (no claims yet):**

| #   | Title                                      | SVS   | Class    | Notes                            |
| --- | ------------------------------------------ | ----- | -------- | -------------------------------- |
| 15  | kitas_e28b_e28c_golden_visa_guida_2025.txt | 0.399 | MARGINAL | Golden Visa (E28B/E28C)          |
| 16  | kitas_e33e_silver_hair_guida_2025.txt      | 0.399 | MARGINAL | Silver Hair retirement visa      |
| 17  | kitas_e33f_pensionati_guida_2025.txt       | 0.399 | MARGINAL | Retirement (pensioner) visa      |
| 18  | kitas_e33g_remote_work_guida_2025.txt      | 0.399 | MARGINAL | Digital nomad / remote work visa |
| 19  | visto_e28a_investitore_guida_2025.txt      | 0.399 | MARGINAL | Investor visa (E28A)             |

**Cluster E — Compliance (no claims yet):**

| #   | Title                                      | SVS   | Class    | Notes                            |
| --- | ------------------------------------------ | ----- | -------- | -------------------------------- |
| 20  | cekal_deportazione_sanzioni_guida_2025.txt | 0.399 | MARGINAL | Deportation/sanctions guide      |
| 21  | garante_penjamin_guida_2025.txt            | 0.399 | MARGINAL | Guarantor (penjamin) obligations |
| 22  | passaporto_dinas_servizio_guida_2025.txt   | 0.399 | MARGINAL | Service passport guide           |
| 23  | passaporto_indonesiano_guida_2025.txt      | 0.399 | MARGINAL | Indonesian passport guide        |

**Other T2 (cross-cluster reference):**

| #   | Title                         | SVS   | Class    | Notes                      |
| --- | ----------------------------- | ----- | -------- | -------------------------- |
| 24  | nb2_visa_procedures_guide.txt | 0.399 | MARGINAL | General visa procedures    |
| 25  | nb2_visa_types_final.txt      | 0.399 | MARGINAL | Visa type reference table  |
| 26  | nb2_golden_visa.txt           | 0.399 | MARGINAL | Golden Visa specific guide |
| 27  | nb_kitas_renewal.txt          | 0.399 | MARGINAL | KITAS renewal procedures   |

**GAPS IDENTIFIED:**

- ❌ **Perda/Pergub Bali on foreign workers** — Design seed list calls for this. Not present.
- ❌ **DPMPTSP Bali requirements guide** — Referenced in design. Not individually sourced.
- ❌ **Bali tourist levy regulation (2024)** — Referenced in design. Not present.
- ❌ **B211A specific guide** — The most common non-work visa for Bali Zero clients. No dedicated source.
- ❌ **VOA/e-VOA specific guide** — `visto_voa_b1b2b3b4_guida_2025.txt` may cover this, but confirmation needed.
- ❌ **Overstay penalties and procedures** — Critical for Cluster E. No dedicated source.
- ❌ **LKPO (Laporan Keberadaan Orang Asing) reporting guide** — Compliance obligation for sponsors. Not sourced.

### 3.7 Complete Source List — Tier T3 (Reference)

| #   | NLM Source ID                          | Title                       | SVS   | Class    | Claims |
| --- | -------------------------------------- | --------------------------- | ----- | -------- | ------ |
| 1   | `c5e5b5c0-14f4-45a8-84fa-e735dc517680` | claims_db_immigration.txt   | 0.361 | MARGINAL | 0      |
| 2   | `7be0b5e0-9a36-4f1b-b0ee-631f2e84e1d0` | nb2_faq_clienti.txt         | 0.361 | MARGINAL | 0      |
| 3   | `8ec5dd2a-c3eb-4da5-a54a-565ef9133aed` | nb2_pricing_immigration.txt | 0.361 | MARGINAL | 0      |

**Analysis:** These are operational reference documents. None have been cited by NLM in testing — expected, as they are FAQ/pricing tables rather than regulatory documents.

### 3.8 Complete Source List — Master Digests

| #   | NLM Source ID                          | Title                         | SVS   | Class    | Claims | Purpose                                      |
| --- | -------------------------------------- | ----------------------------- | ----- | -------- | ------ | -------------------------------------------- |
| 1   | `42a3f083-0205-4d9a-9e0c-f666f4284885` | [NB2-MD] Change Log           | 0.425 | MARGINAL | 0      | Tracks regulatory changes chronologically    |
| 2   | `c46cbb51-81f2-4f10-81f1-9f3b505ec614` | [NB2-MD] Operations Status    | 0.486 | VALUABLE | 1      | System/portal status, BPJS/WLKP compliance   |
| 3   | `6d336e6b-de51-4da0-84be-07a772e3c6b0` | [NB2-MD] Cross-Domain Impacts | 0.425 | MARGINAL | 0      | Visa↔tax↔property intersections              |
| 4   | `d818b8ec-a5ca-450e-8478-6504fdc57d6e` | [NB2-MD] Open Questions       | 0.425 | MARGINAL | 0      | Unresolved questions requiring investigation |

**Key finding:** MDs were cited as first-class sources by NLM in L2 queries. The Change Log was cited twice (citations [5] and [13]) in Phase 4, confirming that MDs actively participate in NLM's synthesis — they are not passive notes but active intelligence sources.

---

## 4. Claim Registry — All 33 Claims

### 4.1 Summary Statistics

| Metric                         | Value                                  |
| ------------------------------ | -------------------------------------- |
| Total claims                   | 19                                     |
| VERIFIED (≥ 0.75)              | 10 (52.6%)                             |
| PROVISIONAL (0.55-0.74)        | 8 (42.1%)                              |
| LOW (< 0.55)                   | 1 (5.3%)                               |
| Enforcement divergence flagged | 2                                      |
| Unique categories              | 8 of 10 defined                        |
| Source coverage                | 11 of 44 sources back at least 1 claim |
| Avg confidence (VERIFIED)      | 0.803                                  |
| Avg confidence (PROVISIONAL)   | 0.606                                  |

### 4.2 Claims by Category

#### LEGAL_CHANGE (4 claims)

| ID         | Text                                                                                                                                                                                              | Conf | Class       | Sources                                 | Scope    | Flags                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | ----------- | --------------------------------------- | -------- | ------------------------------------------- |
| NB2-P1-001 | PP 34/2021 abolished IMTA as separate document; RPTKA approval now serves as work authorization                                                                                                   | 0.82 | VERIFIED    | izin_kerja_tka (T2), nb2_tka_rptka (T1) | NATIONAL | —                                           |
| NB2-P1-002 | SE Kemnaker 3/836/PK.04/I/2026 requires ITK sponsor to match RPTKA sponsor (One Sponsor Policy), effective 2026-01-15                                                                             | 0.55 | PROVISIONAL | nb2_immigration_circulars (T1)          | NATIONAL | needs_jdih_verification                     |
| NB2-P2-001 | UU 63/2024 MERP integration applies to ALL KITAS types (E23 worker, E28 investor, E31 family, E33e/f/g) and KITAP, not just E23                                                                   | 0.78 | VERIFIED    | UU 63/2024 (T0), merp_rientro (T2)      | NATIONAL | Resolves OQ-002                             |
| NB2-P4-002 | Starting January 2026, SIAPKerja system performs automatic cross-check of BPJS Ketenagakerjaan compliance and WLKP reporting before RPTKA approval; non-compliance results in automatic rejection | 0.62 | PROVISIONAL | nb2_immigration_circulars (T1)          | NATIONAL | source_is_circular, needs_jdih_verification |

#### ELIGIBILITY_RULE (3 claims)

| ID         | Text                                                                                                                                  | Conf | Class    | Sources                            | Scope    | Flags                                             |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---- | -------- | ---------------------------------- | -------- | ------------------------------------------------- |
| NB2-P1-003 | Kepmenaker 228/2019 defines approximately 2374 permitted TKA positions across 20 KBLI sectors                                         | 0.78 | VERIFIED | jabatan_tka_kepmen228 (T1)         | NATIONAL | freshness_check_needed (7yr old)                  |
| NB2-P1-004 | Kepmenaker 349/2019 prohibits 19 specific positions for TKA, predominantly HR management roles                                        | 0.80 | VERIFIED | jabatan_tka_vietate_kepmen349 (T1) | NATIONAL | —                                                 |
| NB2-P1-005 | Direktur Utama (CEO) position for TKA is permitted ONLY in KBLI 06 (oil and gas), requiring S1 degree and minimum 15 years experience | 0.80 | VERIFIED | jabatan_tka_kepmen228 (T1)         | NATIONAL | nlm_error_corrected: NLM said 05-09, actual is 06 |

#### FEE_CHANGE (3 claims)

| ID         | Text                                                                                                           | Conf | Class       | Sources                                 | Scope    | Flags                         |
| ---------- | -------------------------------------------------------------------------------------------------------------- | ---- | ----------- | --------------------------------------- | -------- | ----------------------------- |
| NB2-P1-008 | DKP-TKA (Dana Kompensasi Penggunaan TKA) is USD 100 per month per position, prepaid for full contract duration | 0.76 | VERIFIED    | izin_kerja_tka (T2), rptka_dkp_tka (T1) | NATIONAL | —                             |
| NB2-P1-009 | VITAS E23 application fee is USD 150 (PNBP)                                                                    | 0.62 | PROVISIONAL | kitas_e23_tka (T2)                      | NATIONAL | —                             |
| NB2-P1-010 | RPTKA application processing through OSS/Molina portal is free of charge (no government fee)                   | 0.48 | LOW         | nb2_tka_rptka (T1)                      | NATIONAL | unsourced, needs_verification |

**Hard gate compliance:** All 3 FEE_CHANGE claims checked against gate rule. P1-008 (VERIFIED) has T1+T2 backing ✅. P1-009 and P1-010 are PROVISIONAL/LOW so not gated.

#### PROCEDURAL_STEP (2 claims)

| ID         | Text                                                                                                                                                                | Conf | Class    | Sources             | Scope    |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | -------- | ------------------- | -------- |
| NB2-P1-006 | KITAS for TKA now uses index E23 per Permenkumham 22/2023, replacing previous C312 index                                                                            | 0.85 | VERIFIED | kitas_e23_tka (T2)  | NATIONAL |
| NB2-P4-001 | DKP-TKA billing code generated by Molina system expires in 3 working days; late payment invalidates the code and requires regeneration before VITAS E23 can proceed | 0.80 | VERIFIED | izin_kerja_tka (T2) | NATIONAL |

#### OPERATIONAL_CHANGE (2 claims) — Both have enforcement_divergence

| ID         | Text                                                                                                                                                                                             | Conf | Class       | Sources                   | Scope      | Flags                  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---- | ----------- | ------------------------- | ---------- | ---------------------- |
| NB2-P2-002 | Alih Status for KITAS E23 TKA: nationally allowed but Bali immigration requires RPTKA to be pre-approved before processing. If RPTKA pending and visa expiring, client must use Offshore Scheme. | 0.65 | PROVISIONAL | alih_status_offshore (T2) | LOCAL_BALI | enforcement_divergence |
| NB2-P2-003 | C1 tourist visa to E33G remote work KITAS: nationally possible via alih status but Bali has 'prassi variabile' (inconsistent practice), may require offshore processing                          | 0.60 | PROVISIONAL | alih_status_offshore (T2) | LOCAL_BALI | enforcement_divergence |

**Critical note:** These two claims demonstrate the pipeline's ability to detect **national vs. local divergence** — a key value proposition for Bali Zero clients. The national law says one thing; Bali practice is different. Both claims are flagged `enforcement_divergence: true` so the RAG system can present both perspectives.

#### SYSTEM_STATUS (2 claims)

| ID         | Text                                                                                                                                       | Conf | Class       | Sources                                 | Scope    |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---- | ----------- | --------------------------------------- | -------- |
| NB2-P1-007 | UU 63/2024 integrates MERP (Multiple Exit Re-entry Permit) automatically into KITAS, no separate application needed                        | 0.58 | PROVISIONAL | merp_rientro (T2)                       | NATIONAL |
| NB2-P4-003 | Full TKA work permit process timeline reduced from 3-6 months (pre-PP 34/2021) to 4-10 weeks with integrated digital system (Molina + OSS) | 0.78 | VERIFIED    | izin_kerja_tka (T2), kitas_e23_tka (T2) | NATIONAL |

#### BASELINE_EXISTING (2 claims)

| ID         | Text                                                                                                                                                          | Conf | Class       | Sources                                                                             | Scope    | Flags                  |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | ----------- | ----------------------------------------------------------------------------------- | -------- | ---------------------- |
| NB2-P2-004 | Kepmenaker 228/2019 and 349/2019 TKA position lists still fully in force per March 2026, no amendments found. Freshness check recommended (7 years old).      | 0.55 | PROVISIONAL | jabatan_tka_kepmen228 (T1), jabatan_tka_vietate_kepmen349 (T1), [NB2-MD] Ops Status | NATIONAL | freshness_check_needed |
| NB2-P4-005 | UU 63/2024 does NOT change DKP-TKA amounts or procedures (under Kemnaker jurisdiction); it only reforms the immigration phase that follows (MERP elimination) | 0.82 | VERIFIED    | UU 63/2024 (T0), izin_kerja_tka (T2)                                                | NATIONAL | clarification_claim    |

#### PROCESSING_TIME (1 claim)

| ID         | Text                                                                                                                                 | Conf | Class       | Sources                                 | Scope      |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---- | ----------- | --------------------------------------- | ---------- |
| NB2-P4-004 | After TKA arrival in Bali, KITAS E23 physical card conversion at local immigration office (e.g., Ngurah Rai) takes 7-14 working days | 0.65 | PROVISIONAL | izin_kerja_tka (T2), kitas_e23_tka (T2) | LOCAL_BALI |

### 4.3 Missing Claim Categories

The design defines 10 claim categories. The following 2 have **zero claims** after testing:

| Category            | Description                                 | Why Missing                                                                                                  | Action Needed              |
| ------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------- |
| ENFORCEMENT_ACTION  | Specific enforcement events (raids, sweeps) | Cluster A testing only covers work permits, not enforcement. Cluster E (Friday rotation) will produce these. | Wait for Cluster E queries |
| ENFORCEMENT_PATTERN | Repeated enforcement trends                 | Same as above                                                                                                | Wait for Cluster E queries |

**Note:** The design also defines `POLICY_SIGNAL`, `LOCAL_REGULATION`, `DOCUMENT_REQUIREMENT`, and `UNCLASSIFIED_SIGNAL`. These are not in the current claim taxonomy but map to existing categories (LEGAL_CHANGE covers policy signals and local regulations, PROCEDURAL_STEP covers document requirements).

---

## 5. Source Value Scores — Full Ranking

### 5.1 SVS Formula

```
SVS = min(1.0,
    0.25 × V_tier          # Source authority tier
  + 0.25 × V_claims        # min(1.0, claims_extracted / 8)
  + 0.20 × S(t, type)      # Staleness: exp(-ln(2)/half_life × t_effective)
  + 0.15 × V_citations     # min(1.0, times_cited / 5)
  + 0.15 × V_uniqueness    # unique_claims / max(1, total_claims)
  + min(0.15, BONUS)       # Pinned (+0.05), MD (+0.05), sole T0-T2 backer (+0.10)
)
```

### 5.2 Staleness Half-Lives

| Source Type                     | Half-Life | S at 7d | S at 30d | S at 90d |
| ------------------------------- | --------- | ------- | -------- | -------- |
| LAW_IN_FORCE                    | Infinite  | 1.00    | 1.00     | 1.00     |
| MASTER_DIGEST                   | 180 days  | 0.97    | 0.89     | 0.71     |
| ANALYSIS_REPORT / KNOWLEDGE_DOC | 120 days  | 0.96    | 0.84     | 0.59     |
| REGULATION_CIRCULAR             | 90 days   | 0.95    | 0.79     | 0.50     |
| OFFICIAL_PORTAL                 | 60 days   | 0.92    | 0.71     | 0.35     |
| OFFICIAL_SOCIAL                 | 30 days   | 0.85    | 0.50     | 0.13     |
| NEWS_ARTICLE                    | 15 days   | 0.72    | 0.25     | 0.02     |

**Staleness fix applied:** `t_effective = min(days_since_publication, days_since_last_confirmed)`. KNOWLEDGE_DOC sources with placeholder dates get `last_confirmed_valid` set to ingestion date.

### 5.3 SVS Classification Thresholds

| SVS Range | Classification | Action                                   |
| --------- | -------------- | ---------------------------------------- |
| ≥ 0.70    | **ESSENTIAL**  | Never auto-archive                       |
| 0.45-0.69 | **VALUABLE**   | Keep unless at hard capacity             |
| 0.25-0.44 | **MARGINAL**   | First candidates for consolidation       |
| < 0.25    | **EXPENDABLE** | Auto-archive if V_claims=0 and age > 14d |

### 5.4 Complete SVS Ranking (all 44 sources)

| Rank  | SVS         | Class     | Tier  | Claims | Title                                           |
| ----- | ----------- | --------- | ----- | ------ | ----------------------------------------------- |
| 1     | 0.861       | ESSENTIAL | T2    | 6      | izin_kerja_tka_procedura_completa_2025.txt      |
| 2     | 0.819       | ESSENTIAL | T2    | 4      | kitas_e23_tka_guida_2025.txt                    |
| 3     | 0.808       | ESSENTIAL | T1    | 3      | jabatan_tka_kepmen228_settori_ammessi_2025.txt  |
| 4     | 0.721       | ESSENTIAL | T1    | 2      | jabatan_tka_vietate_kepmen349_2025.txt          |
| 5     | 0.696       | VALUABLE  | T1    | 2      | nb2_immigration_circulars.txt                   |
| 6     | 0.671       | VALUABLE  | T2    | 2      | alih_status_offshore_autogate_guida_2025.txt    |
| 7     | 0.623       | VALUABLE  | T0    | 2      | UU No. 63 Tahun 2024 — Key Provisions           |
| 8     | 0.621       | VALUABLE  | T1    | 2      | nb2_tka_rptka_guide.txt                         |
| 9     | 0.596       | VALUABLE  | T2    | 2      | merp_rientro_guida_2025.txt                     |
| 10    | 0.500       | VALUABLE  | T0    | 0      | UU No. 6 Tahun 2011                             |
| 11    | 0.500       | VALUABLE  | T0    | 0      | UU No. 63 Tahun 2024 (BPK Full Text)            |
| 12    | 0.486       | VALUABLE  | MD    | 1      | [NB2-MD] Operations Status                      |
| 13    | 0.485       | VALUABLE  | T1    | 1      | rptka_dkp_tka_guida_2025.txt                    |
| 14    | 0.425       | MARGINAL  | MD    | 0      | [NB2-MD] Change Log                             |
| 15    | 0.425       | MARGINAL  | MD    | 0      | [NB2-MD] Cross-Domain Impacts                   |
| 16    | 0.425       | MARGINAL  | MD    | 0      | [NB2-MD] Open Questions                         |
| 17-44 | 0.300-0.399 | MARGINAL  | T0-T3 | 0      | (28 sources from clusters B-E, not yet queried) |

**Distribution:** 4 ESSENTIAL, 9 VALUABLE, 31 MARGINAL, 0 EXPENDABLE.

**Note on MARGINAL sources:** The 28 MARGINAL sources covering clusters B-E are NOT low quality — they simply haven't been queried yet. After one full week of rotation (all 5 clusters queried), most will accumulate claims and their SVS will rise. The expected steady-state is ~20 ESSENTIAL/VALUABLE + ~30 MARGINAL + ~5-10 newly imported WORKING sources.

---

## 6. Testing Protocol — 8 Phases Detailed

### Phase 0: Environment Setup ✅

**Date:** 2026-03-28 17:05
**Duration:** ~15 min

| Check                      | Result | Detail                                               |
| -------------------------- | ------ | ---------------------------------------------------- |
| NB-2 accessible            | ✅     | notebook_get returns 44 sources                      |
| Duplicate removed          | ✅     | UU 6/2011 duplicate (7625b0cd) deleted               |
| State files initialized    | ✅     | pipeline_state.json, sources.json, claims.jsonl      |
| 4 Master Documents created | ✅     | Change Log, Ops Status, Cross-Domain, Open Questions |
| Handoff directory created  | ✅     | `~/.agent/decisions/nlm_to_scraper/handoff/`         |
| 10/10 invariants pass      | ✅     | INV-1 through INV-10                                 |
| Baseline NHS computed      | ✅     | **0.668 (NORMAL)**                                   |

### Phase 1: First L1 Query ✅

**Date:** 2026-03-28 17:30
**Duration:** ~25 min (including adversarial review)
**Query:** Cluster A — Work permits/TKA (Bahasa Indonesia)

| Metric              | Value               |
| ------------------- | ------------------- |
| Citations           | 37                  |
| Sources used        | 10/42 (24%)         |
| Claims extracted    | 10                  |
| VERIFIED            | 5                   |
| PROVISIONAL         | 3                   |
| LOW                 | 1                   |
| NLM error corrected | 1 (KBLI 05-09 → 06) |

**4-Voice Adversarial Review:**

| Voice          | Score      | Top Finding                                                |
| -------------- | ---------- | ---------------------------------------------------------- |
| V1 Gemini      | 6.5/10     | KBLI factual error, "One Sponsor Policy" may be fabricated |
| V2 Codex       | 7.0/10     | Super-source risk, 8 claims, handoff TRS, no T0 used       |
| V3 DeepSeek R1 | 6.5/10     | Codebase IMTA contradiction, 5 missing reasoning chains    |
| V4 Claude      | 7.5/10     | UU 63/2024 untracked T0, monitoring-vs-explaining problem  |
| **Aggregate**  | **7.0/10** | **PASS (PROVISIONAL) — GO to Phase 2 with conditions**     |

**Actions taken from adversarial review:**

1. UU 63/2024 ingested as T0 source ✅
2. `kg_subgraph_visa.py:180-186` IMTA→RPTKA fix applied ✅
3. Master Documents seeded with Phase 1 findings ✅
4. KBLI error corrected in claim NB2-P1-005 ✅

### Phase 2: L2 Comparative Query ✅

**Date:** 2026-03-28 18:15
**Duration:** ~15 min
**Query:** Cluster A — Pre/post-2026 comparative (with context injection)

| Metric                 | Value                                  |
| ---------------------- | -------------------------------------- |
| Citations              | 27                                     |
| Sources used           | 11/43 (25.6%)                          |
| Context injection      | conversation_id from Phase 1           |
| New claims             | 4                                      |
| Master Documents cited | MD-1, MD-2, MD-4 (first-class sources) |

**Key findings:**

- OQ-002 RESOLVED: MERP applies to ALL KITAS types + KITAP
- 2 enforcement_divergence claims discovered (Alih Status E23, C1→E33G)
- NLM propagated confidence levels from MDs — cited PROVISIONAL (0.55) for One Sponsor Policy

**Verdict:** STRONG PASS — L2 demonstrates comparative synthesis beyond L1 capability.

### Phase 3: Triage + SVS ✅

**Date:** 2026-03-28 19:00
**Duration:** ~20 min

| Check                         | Result                                             |
| ----------------------------- | -------------------------------------------------- |
| Registry sync (38→44 sources) | ✅ 6 missing entries added                         |
| Claims linked to sources      | ✅ 11 sources with claims, all references resolved |
| SVS computed for 44 sources   | ✅ 4 ESSENTIAL, 9 VALUABLE, 31 MARGINAL            |
| 4-level dedup                 | ✅ 0 real duplicates (6 corroborations)            |
| Hard gate enforcement         | ✅ 4/4 gated claims pass                           |
| Confidence consistency        | ✅ 14/14                                           |
| Staleness fix applied         | ✅ t_effective = min(pub, confirmed)               |
| NHS recalculated              | ✅ **0.798 (EXCELLENT)**, up from 0.668            |

### Phase 4: L2 Cross-Query Dedup ✅

**Date:** 2026-03-28 19:15
**Duration:** ~15 min
**Query:** Cluster A — DKP-TKA/RPTKA procedures (different sub-topic)

| Metric                        | Value                              |
| ----------------------------- | ---------------------------------- |
| Citations                     | 20                                 |
| Sources used                  | 7/44 (16%)                         |
| Source overlap with Phase 1+2 | 5/7 (expected — same cluster)      |
| New sources activated         | 2 (MD Change Log, imk_itk_itb_itp) |
| New claims                    | 5 (0 duplicates)                   |
| Pre/post source count         | 44/44 (unchanged)                  |

**Verdict:** PASS — cross-query dedup works. Claims are additive, not redundant.

### Phase 5: Source Lifecycle ✅

**Date:** 2026-03-28 19:25
**Duration:** ~5 min

| Check                   | Result                                                    |
| ----------------------- | --------------------------------------------------------- |
| QUARANTINE              | 0 (all ACTIVE) ✅                                         |
| Consolidation triggers  | None (topic_age < 14d) ✅                                 |
| Category budgets        | ⚠️ canonical 34 (max 25), working 0 (min 25) — reclassify |
| Auto-archive candidates | 0 ✅                                                      |

### Phase 6: Handoff Package ✅

**Date:** 2026-03-28 19:25
**Duration:** ~5 min

| Check                   | Result                         |
| ----------------------- | ------------------------------ |
| Schema validation       | ✅ All required fields present |
| Integration mode        | ENRICH (avg confidence 0.742)  |
| Findings                | 5 (top by TRS)                 |
| Topics                  | 5 with search queries          |
| TRS distribution        | 18 HANDOFF + 1 CANDIDATE       |
| File size               | 6,660 bytes                    |
| balizero.com in handoff | ❌ (correctly excluded)        |

### Phase 7: Failure/Recovery ✅

**Date:** 2026-03-28 19:30
**Duration:** ~5 min

| Test | Scenario                                            | Result |
| ---- | --------------------------------------------------- | ------ |
| 1    | State corruption → detect + recover                 | ✅     |
| 2    | CB-NLM FSM (CLOSED→OPEN→HALF_OPEN→CLOSED + cascade) | ✅     |
| 3    | Capacity 70 → block → prune → 69                    | ✅     |
| 4    | INV-4 feedback loop enforcement                     | ✅     |

### Phase 8: Go/No-Go ✅

**Date:** 2026-03-28 19:35

| Criterion     | Result                           |
| ------------- | -------------------------------- |
| Phases passed | 8/8                              |
| Hard-blockers | 0/7                              |
| **VERDICT**   | **🟢 GREEN — GO FOR PRODUCTION** |

---

## 7. Quality Verification Framework

### 7.1 Source Authority Hierarchy (7 Tiers)

| Tier | Name                     | Authority   | V_tier | Examples                                         |
| ---- | ------------------------ | ----------- | ------ | ------------------------------------------------ |
| T0   | National Primary Law     | Highest     | 1.00   | UU, PP, Perpres, Permenkumham, JDIH Gazette      |
| T1   | National Implementation  | High        | 0.90   | Ditjen Imigrasi site, Surat Edaran, circulars    |
| T2   | Regional/Local Authority | Medium-High | 0.80   | Kanwil Bali, Kantor Imigrasi Ngurah Rai, Pemprov |
| T3   | Local Enforcement        | Medium      | 0.65   | Tim Pora Bali, joint operation reports           |
| T4   | Official Social Media    | Medium-Low  | 0.50   | Instagram @kanaboraingurahrai, @ditaborasi       |
| T5   | Reputable Press          | Low         | 0.35   | Bali Post, NusaBali, Kompas, Tempo               |
| T6   | Community/Unverified     | Minimal     | 0.10   | Blogs, forums, expat groups                      |

**Key principle (Two-Axis Authority):**

- **Legal axis:** T0 > T1 > T2 > T3 (for what the LAW says)
- **Operational axis:** T2/T3/T4 can outrank T0/T1 on what actually HAPPENS at local offices

**Indonesia-specific insight:** Government offices routinely announce operational changes on Instagram 3-7 days BEFORE updating websites. Official government Instagram accounts are T4 (not T5/T6) because they are institutional, not personal.

### 7.2 Confidence Scoring Formula

```
Confidence = max(0, min(1.0,
    0.30 × S_auth + 0.25 × S_corr + 0.15 × S_spec
  + 0.12 × S_type + 0.10 × S_recency + 0.08 × S_geo - Penalty
))
```

### 7.3 Hard Gates (Override Confidence Score)

| Gate                                            | Effect                                  |
| ----------------------------------------------- | --------------------------------------- |
| T6-only source (forums)                         | NEVER reaches brief regardless of score |
| LEGAL_CHANGE without JDIH/official confirmation | Capped at PROVISIONAL                   |
| ENFORCEMENT_ACTION from single news source      | Capped at PROVISIONAL                   |
| Visa eligibility/fee/deadline claim             | Must have T0-T2 source for VERIFIED     |

### 7.4 Local-National Contradiction Rules

| Scenario                                  | Handling                                                                                          |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Local adds requirements beyond national   | Both correct. Tag `geographic_scope: bali_specific`                                               |
| Local practice diverges from written law  | Both factually correct. Tag `enforcement_divergence: true`. Local practice prevails for advisory. |
| Local contradicts national directly       | National prevails legally. Local flagged `operational_alert`. NEVER silently discard.             |
| Bali practice extrapolated Indonesia-wide | NEVER generalize without national corroboration                                                   |

---

## 8. Gap Analysis — What's Missing

### 8.1 Missing T0 Sources (Critical)

These are referenced in claims or designs but not individually present as T0 sources in NB-2:

| #   | Regulation                                          | Why Needed                                                                                                                         | Priority         |
| --- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| 1   | **PP No. 34 Tahun 2021** (RPTKA reform)             | Cited in 3 claims (P1-001, P4-003, P4-005). The regulation that abolished IMTA. Currently only accessible through guide docs.      | HIGH             |
| 2   | **Permenkumham No. 22 Tahun 2023** (E23 visa index) | Cited in claim P1-006. Established the E23 classification replacing C312.                                                          | HIGH             |
| 3   | **UU No. 1 Tahun 2026** (New Immigration Law)       | Referenced in query designs. OQ-003 tracks its existence — may or may not exist. If it exists, it's the most important missing T0. | HIGH (if exists) |
| 4   | **Permenaker on RPTKA/TKA** (latest)                | Design seed list item. RPTKA procedure is only available through guides.                                                           | MEDIUM           |
| 5   | **Permenaker on DKPTKA** (latest)                   | Design seed list item. DKP-TKA amounts sourced from guides only.                                                                   | MEDIUM           |
| 6   | **Permenimipas No. 5/2025** (Guarantor rules)       | New regulation (post-ministry restructure). NLM referenced it but no dedicated source.                                             | MEDIUM           |
| 7   | **PP PNBP Kemenkumham** (latest fee schedule)       | Design seed list item. Fee claims sourced from guides.                                                                             | MEDIUM           |

**Impact of missing T0 sources:** Claims backed only by T1-T2 guides cannot reach VERIFIED status on eligibility/fee/deadline categories (hard gate). Adding direct T0 regulation texts would immediately upgrade several PROVISIONAL claims to VERIFIED.

### 8.2 Missing T1-T2 Sources

| #   | Source                                      | Cluster | Why Needed                                                          |
| --- | ------------------------------------------- | ------- | ------------------------------------------------------------------- |
| 1   | **BKPM Investment Guidelines (PMA)**        | A       | KITAS Investor requirements, PMA minimum capital, KBLI restrictions |
| 2   | **OSS-RBA operating procedures**            | A       | OSS system procedures for RPTKA and NIB verification                |
| 3   | **Surat Edaran Ditjen Imigrasi** (3 latest) | All     | Individual SE documents, not bundled in one guide                   |
| 4   | **Perda/Pergub Bali on foreign workers**    | E       | Local regulation on foreign worker supervision                      |
| 5   | **DPMPTSP Bali requirements guide**         | A, D    | Bali investment licensing authority requirements                    |
| 6   | **Bali tourist levy regulation (2024)**     | C, E    | Affects all visitors, compliance requirement                        |
| 7   | **Kepmenaker 228/2019 original text**       | A       | Full regulation (not just the guide analysis)                       |
| 8   | **Kepmenaker 349/2019 original text**       | A       | Full regulation (not just the guide analysis)                       |

### 8.3 Missing Cluster Coverage (Zero Claims)

| Cluster          | Sources Present | Sources With Claims | Gap                    |
| ---------------- | --------------- | ------------------- | ---------------------- |
| A — Work Permits | 6               | 6                   | None — fully tested    |
| B — Stay Permits | 4               | 0                   | 100% — not queried yet |
| C — Visit Visas  | 6               | 0                   | 100% — not queried yet |
| D — Special      | 5               | 0                   | 100% — not queried yet |
| E — Compliance   | 4               | 0                   | 100% — not queried yet |

**Resolution:** Clusters B-E will be queried in the first production week (Tue-Fri rotation). After one week, all clusters will have claims.

### 8.4 Missing Source Types

The current collection is 100% comprised of:

- Government regulations (T0 laws, PPs)
- Internal curated guides (T2 KNOWLEDGE_DOC)
- Reference tables (T3)
- Master Digests (MD)

Missing source types that the design explicitly calls for:

| Source Type           | Tier  | Example                                         | Why Needed                                                       |
| --------------------- | ----- | ----------------------------------------------- | ---------------------------------------------------------------- |
| Official social media | T4    | Instagram @kanaboraingurahrai                   | Real-time operational alerts, processing delays, office closures |
| Reputable press       | T5    | Bali Post, NusaBali, Kompas                     | Enforcement reporting, early signals, public commentary          |
| Official portal pages | T1-T2 | evisa.imigrasi.go.id FAQ, molina.kemnaker.go.id | Current portal status, system requirements                       |
| Law firm analyses     | T5    | SSEK, Fragomen, local firms                     | Expert interpretation of new regulations                         |
| JDIH gazette entries  | T0    | jdih.kemenkumham.go.id                          | Direct regulation texts (not through guides)                     |

**Note:** These source types will be added by the pipeline's `research_start` deep research function, which searches the web and imports new sources into NB-2. The current collection is the seed set; production operation will grow it.

### 8.5 Depth Assessment

| Topic                        | Current Depth                 | Ideal Depth                              | Gap    |
| ---------------------------- | ----------------------------- | ---------------------------------------- | ------ |
| RPTKA/TKA procedure          | Deep (6 claims, 3 sources)    | Adequate                                 | Low    |
| DKP-TKA fees/payment         | Good (3 claims, 3 sources)    | Adequate                                 | Low    |
| KITAS E23 specifics          | Deep (4 claims, 2 sources)    | Adequate                                 | Low    |
| Kepmenaker position lists    | Good (3 claims, 2 sources)    | Need original regulation text            | Medium |
| UU 63/2024 impact            | Good (3 claims, 2 sources)    | Need more cross-domain analysis          | Medium |
| Alih Status / Offshore       | Moderate (2 claims, 1 source) | Need more Bali-specific data             | Medium |
| MERP integration             | Good (2 claims, 2 sources)    | Adequate                                 | Low    |
| SE 3/836 One Sponsor         | Thin (1 claim, 1 source)      | Need JDIH verification                   | HIGH   |
| Golden Visa                  | Zero claims                   | Need Cluster D queries                   | HIGH   |
| B211A / VOA                  | Zero claims                   | Need Cluster C queries                   | HIGH   |
| KITAP conversion             | Zero claims                   | Need Cluster B queries                   | HIGH   |
| Digital Nomad E33G           | Zero claims                   | Need Cluster D queries                   | HIGH   |
| Enforcement patterns         | Zero claims                   | Need Cluster E queries + T4/T5 sources   | HIGH   |
| Reporting obligations (LKPO) | Zero claims                   | Need Cluster E queries + specific source | HIGH   |
| Overstay penalties           | Zero claims                   | Need Cluster E + specific source         | HIGH   |

---

## 9. Open Questions

| ID     | Question                                                                                                                             | Status       | Impact                                         | Resolution Path                                                                                                                                                       |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------ | ------------ | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OQ-001 | Verify SE 3/836/PK.04/I/2026 on JDIH — is the "One Sponsor Policy" a real circular or NLM hallucination?                             | OPEN         | HIGH — affects claim P1-002 (PROVISIONAL 0.55) | Search JDIH Kemnaker for SE 3/836. If found, upgrade to VERIFIED. If not found, downgrade to LOW and flag as potential fabrication.                                   |
| OQ-002 | Does MERP integration under UU 63/2024 apply to ALL KITAS types or only E23?                                                         | **RESOLVED** | Was HIGH                                       | Resolved in Phase 2: applies to ALL KITAS (E23, E28, E31, E33e/f/g) and KITAP. Claim NB2-P2-001 (VERIFIED 0.78).                                                      |
| OQ-003 | Does "UU No. 1 Tahun 2026 tentang Imigrasi" exist? Multiple NLM references but no JDIH entry found.                                  | OPEN         | CRITICAL                                       | Search JDIH, BPK, hukumonline. If exists, it's the most important missing T0. If not, all references are confabulation.                                               |
| OQ-004 | Are Kepmenaker 228/2019 and 349/2019 still current after 7 years? Any amendments or replacements?                                    | OPEN         | MEDIUM                                         | Claim P2-004 says "still in force, no amendments found" (PROVISIONAL 0.55). Need fresh JDIH search to confirm. 7-year-old regulations with no updates are suspicious. |
| OQ-005 | Permenimipas vs Permenkumham naming — Is the ministry still Kemenkumham or restructured to Kemenimipas under Prabowo cabinet (2024)? | OPEN         | LOW (naming)                                   | NLM references both names. Need to confirm current official ministry name to avoid confusion in client communications.                                                |

---

## 10. Adversarial Review Results

### 10.1 Phase 1 — 4-Voice Review

**Query reviewed:** L1 Cluster A — Work permits/TKA

**Aggregate score: 7.0/10 (PASS PROVISIONAL)**

#### V1 — Gemini 3.1 Pro (6.5/10)

**Top findings:**

1. **KBLI factual error**: NLM said CEO position permitted in KBLI 05-09. Actual per IMM-395 in source is KBLI 06 only (oil and gas). Corrected in claim P1-005.
2. **"One Sponsor Policy" fabrication risk**: SE 3/836 cited as requiring sponsor matching, but this may be NLM synthesis rather than a real SE. OQ-001 created.
3. **No T0 sources used**: NLM didn't cite any T0 laws directly. All citations through T1-T2 guides.
4. **Super-source dominance**: `izin_kerja_tka_procedura_completa_2025.txt` (T2) accounted for ~40% of citations. Risk of single-source dependency.

#### V2 — Codex GPT-5.4 (7.0/10)

**Top findings:**

1. **8 claims extractable** (later expanded to 10 in full extraction).
2. **Handoff TRS** on extracted claims would produce 5+ HANDOFF-quality topics.
3. **Missing operational monitoring**: Query is explaining existing regulations rather than detecting changes. Need to differentiate "what IS the law" from "what CHANGED in the law."
4. **Source diversity OK**: 10/42 sources used is reasonable for Cluster A.

#### V3 — DeepSeek R1 671B (6.5/10)

**Top findings:**

1. **Codebase IMTA contradiction**: `kg_subgraph_visa.py:180-186` still references IMTA, contradicting PP 34/2021 which abolished it. Fix applied.
2. **5 missing reasoning chains**: Claims about DKPTKA calculation, RPTKA timeline, KITAS duration, renewal process, and telex visa — all stated without explicit regulatory citation chains.
3. **38% of claims rated HIGH confidence** — too aggressive for first-pass extraction without cross-validation.
4. **Temporal anchoring weak**: Most claims lack effective dates. "PP 34/2021" is anchored, but "RPTKA takes 5-20 days" is undated.

#### V4 — Claude Opus 4.6 (7.5/10)

**Top findings:**

1. **UU 63/2024 untracked T0**: The most important recent immigration law wasn't in NB-2 as a tracked source. Added immediately.
2. **Monitoring-vs-explaining problem**: L1 queries should detect CHANGES, but NLM's response explained EXISTING procedures. L2 comparative queries needed.
3. **MD seeding plan needed**: Master Documents initialized empty — need to seed with Phase 1 findings for context injection in Phase 2.
4. **Local enforcement gap**: Zero Bali-specific operational intelligence. Need T4 sources (Instagram) and enforcement reporting.

---

## 11. Handoff Package Specification

### 11.1 Schema v1.0

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO8601",
  "pipeline_run_id": "nb2_YYYYMMDD_HHMM",
  "notebook_id": "UUID",
  "query_cluster": "A|B|C|D|E",
  "integration_mode": "IGNORE|ENRICH|PRIORITIZE",
  "findings": [
    {
      "claim_id": "NB2-PX-NNN",
      "claim_text": "...",
      "confidence": 0.00-1.00,
      "confidence_label": "VERIFIED|PROVISIONAL|LOW",
      "category": "LEGAL_CHANGE|...",
      "tier_highest": "T0|T1|...",
      "geographic_scope": "NATIONAL|LOCAL_BALI",
      "enforcement_divergence": false,
      "source_chain": [{"tier": "T0", "name": "...", "url": "...", "date": "..."}],
      "tags": ["kitas", "rptka", "..."]
    }
  ],
  "suggested_topics": [
    {
      "topic": "...",
      "search_queries": ["...", "..."],
      "priority": "HIGH|MEDIUM|LOW",
      "rationale": "...",
      "linked_claims": ["NB2-P1-001"]
    }
  ],
  "scraper_hints": {
    "avoid_urls": ["..."],
    "priority_domains": ["jdih.kemenkumham.go.id", "..."],
    "suppress_categories": []
  }
}
```

### 11.2 Integration Modes

| Mode       | Condition                              | Scraper Behavior                                                    |
| ---------- | -------------------------------------- | ------------------------------------------------------------------- |
| IGNORE     | No handoff file, or corrupted          | Scraper operates normally (pre-NLM behavior)                        |
| ENRICH     | Avg confidence < 0.75                  | Add `nlm_*` metadata to matching articles, don't change ranking     |
| PRIORITIZE | Avg confidence ≥ 0.75 AND ≥ 1 VERIFIED | Boost quality_score of matching articles, prioritize related topics |

### 11.3 TRS Formula (Topic Relevance Score)

```
TRS = 0.25 × F_confidence + 0.25 × F_novelty + 0.20 × F_client_impact
    + 0.15 × F_editorial_value + 0.15 × F_source_tier + min(0.10, BONUS_timely)
```

| TRS Range | Classification | Action                             |
| --------- | -------------- | ---------------------------------- |
| ≥ 0.65    | HANDOFF        | Include in handoff package (max 5) |
| 0.45-0.64 | CANDIDATE      | Include if room, lower priority    |
| < 0.45    | FILTERED       | Not in handoff                     |

### 11.4 Testing Result

| Metric              | Value                    |
| ------------------- | ------------------------ |
| Findings in handoff | 5                        |
| Topics generated    | 5                        |
| Integration mode    | ENRICH                   |
| Avg confidence      | 0.742                    |
| TRS distribution    | 18 HANDOFF + 1 CANDIDATE |
| File size           | 6,660 bytes              |
| Schema valid        | ✅                       |
| No balizero.com     | ✅                       |

---

## 12. Failure Modes & Recovery

### 12.1 Ten Invariants

| ID     | Invariant                      | Enforcement                          | Tested             |
| ------ | ------------------------------ | ------------------------------------ | ------------------ |
| INV-1  | ACTIVE sources ≤ 70            | Hard cap, block import               | ✅ Phase 7 Test 3  |
| INV-2  | ILM < 0.05 for consolidation   | Reject consolidation if exceeded     | ✅ Design verified |
| INV-3  | No balizero.com sources        | Domain denylist                      | ✅ Phase 7 Test 4  |
| INV-4  | No feedback loop (own content) | Provenance tagging, domain exclusion | ✅ Phase 7 Test 4  |
| INV-5  | Master Documents ≥ 4           | Alert if below                       | ✅ Phase 0         |
| INV-6  | QUARANTINE ≤ 30                | Oldest-first triage                  | ✅ Phase 5         |
| INV-7  | claims.jsonl append-only       | Never modify/delete existing claims  | ✅ All phases      |
| INV-8  | Dedup before import            | 4-level check                        | ✅ Phase 3         |
| INV-9  | Atomic writes                  | temp + rename pattern                | ✅ Design verified |
| INV-10 | Audit every mutation           | JSONL audit trail                    | ✅ Design verified |

### 12.2 Three Circuit Breakers

| CB             | Trigger                           | Recovery                                | Cascade                    |
| -------------- | --------------------------------- | --------------------------------------- | -------------------------- |
| CB-NLM         | 3 consecutive NLM API failures    | Auto-close after 4h (HALF_OPEN → probe) | Open > 5d → CB-SOURCE      |
| CB-SOURCE      | Manual only (data quality crisis) | Manual close                            | Open > 7d → CB-INTEGRATION |
| CB-INTEGRATION | 3 handoff schema failures         | Auto-close after 12h                    | None (terminal)            |

### 12.3 Degradation Levels

| Level       | Condition                         | Pipeline Behavior                             |
| ----------- | --------------------------------- | --------------------------------------------- |
| NOMINAL     | All CBs closed, NHS > 0.60        | Normal operation                              |
| DEGRADED_L1 | CB-NLM open OR NHS 0.45-0.60      | Skip L2 queries, L1 only                      |
| DEGRADED_L2 | CB-SOURCE open OR NHS < 0.45      | Skip all queries, handoff from cache          |
| HALTED      | CB-INTEGRATION open OR NHS < 0.30 | Pipeline stops. Manual intervention required. |

**Cardinal rule:** At ANY degradation level, the intel scraper and War Room operate identically to pre-NLM behavior. The pipeline adds value but never breaks existing workflows.

### 12.4 Failure Test Results (Phase 7)

| Test | Scenario                  | Expected                       | Actual                              | Status  |
| ---- | ------------------------- | ------------------------------ | ----------------------------------- | ------- |
| 1    | Truncated JSON state file | Detect, recover to DEGRADED_L1 | Detected JSONDecodeError, recovered | ✅ PASS |
| 2a   | 3 NLM API failures        | CB-NLM opens                   | State = OPEN after 3 failures       | ✅ PASS |
| 2b   | 4h timeout                | CB-NLM → HALF_OPEN             | State = HALF_OPEN after timeout     | ✅ PASS |
| 2c   | 1 success in HALF_OPEN    | CB-NLM → CLOSED                | State = CLOSED, failure_count = 0   | ✅ PASS |
| 2d   | CB-NLM open > 5 days      | Cascade to CB-SOURCE           | check_cascade returns "CB-SOURCE"   | ✅ PASS |
| 3a   | 70 ACTIVE sources         | Block new import               | Import rejected (INV-1)             | ✅ PASS |
| 3b   | Emergency prune           | Archive lowest SVS non-pinned  | sim_src_051 archived, count = 69    | ✅ PASS |
| 4a   | balizero.com URL          | Reject at import               | Domain denylist blocks              | ✅ PASS |
| 4b   | kita.balizero.com URL     | Reject at import               | Subdomain also blocked              | ✅ PASS |
| 4c   | Handoff package clean     | No balizero.com in output      | Verified clean                      | ✅ PASS |

---

## 13. NHS Health Tracking

### 13.1 NHS Formula

```
NHS = 0.20 × H_capacity + 0.25 × H_freshness + 0.25 × H_quality
    + 0.15 × H_coverage + 0.15 × H_dedup
```

### 13.2 NHS History

| Date       | Phase            | NHS   | Class     | H_cap | H_fresh | H_qual  | H_cov | H_dedup | Note                        |
| ---------- | ---------------- | ----- | --------- | ----- | ------- | ------- | ----- | ------- | --------------------------- |
| 2026-03-28 | PHASE_0_INIT     | 0.668 | NORMAL    | 0.764 | 0.700\* | 0.400\* | 0.600 | 1.000   | Baseline (\* = estimates)   |
| 2026-03-28 | PHASE_3_TRIAGE   | 0.798 | EXCELLENT | 0.800 | 0.950   | 0.455   | 0.910 | 1.000   | SVS computed, staleness fix |
| 2026-03-28 | PHASE_4_L2_DEDUP | 0.801 | EXCELLENT | 0.800 | 0.950   | 0.466   | 0.910 | 1.000   | 5 new claims, 4 ESSENTIAL   |
| 2026-03-28 | GO_NO_GO         | 0.801 | EXCELLENT | 0.800 | 0.950   | 0.466   | 0.910 | 1.000   | GREEN — production approved |

### 13.3 NHS Classification

| NHS Range | Classification   | Action                                |
| --------- | ---------------- | ------------------------------------- |
| ≥ 0.75    | EXCELLENT        | Normal operation, all features active |
| 0.60-0.74 | NORMAL           | Normal operation                      |
| 0.45-0.59 | ATTENTION_NEEDED | Reduce to L1 only, alert on Telegram  |
| < 0.45    | CRITICAL         | Pipeline halted, manual intervention  |

---

## 14. Production Deployment Plan

### 14.1 Pre-Production Tasks (Day 0 — Sunday March 30)

| #   | Task                                           | Duration | Owner       |
| --- | ---------------------------------------------- | -------- | ----------- |
| 1   | Reclassify ~15 canonical guides → working      | 30 min   | Claude Code |
| 2   | Verify nlm CLI auth on Pro                     | 5 min    | Claude Code |
| 3   | Configure OpenClaw cron job (01:10 WITA daily) | 15 min   | Claude Code |
| 4   | Verify handoff directory exists on Pro         | 2 min    | Claude Code |

### 14.2 Week 1 Schedule

| Date    | Day     | Cluster                        | Query Levels       | Expected Claims |
| ------- | ------- | ------------------------------ | ------------------ | --------------- |
| Mar 31  | Mon     | A — Work Permits               | L1 + L2            | 3-6 new claims  |
| Apr 1   | Tue     | B — Stay Permits               | L1 + L2            | 4-8 new claims  |
| Apr 2   | Wed     | C — Visit Visas                | L1 + L2            | 4-8 new claims  |
| Apr 3   | Thu     | D — Special + L3               | L1 + L3            | 4-8 new claims  |
| Apr 4   | Fri     | E — Compliance + Consolidation | L1 + Consolidation | 3-5 new claims  |
| Apr 5-6 | Sat-Sun | OFF                            | —                  | —               |

**Expected end-of-week-1:** ~35-55 total claims (19 current + 16-36 new), 44-55 sources, NHS ≥ 0.70.

### 14.3 Monitoring Protocol

| Metric            | Threshold | Alert Channel | Frequency      |
| ----------------- | --------- | ------------- | -------------- |
| NHS               | < 0.60    | Telegram      | After each run |
| CB-NLM state      | OPEN      | Telegram      | Immediate      |
| QUARANTINE count  | > 15      | Telegram      | After each run |
| Claims per run    | 0         | Log only      | After each run |
| Handoff staleness | > 30h     | Telegram      | Scraper checks |

### 14.4 Week 4 Go/No-Go (Production Retention)

Per `07b_testing_protocol_deepseek.md`:

- **PROMOTE** (continue): Claim verification accuracy ≥ 85%, NHS stable > 0.60, IVA 0.20-0.55
- **EXTEND** (more testing): 70-85% accuracy OR NHS oscillating
- **REDESIGN** (major changes): < 70% accuracy OR NHS trending down

### 14.5 Cost Model

| Component                                            | Monthly Cost                |
| ---------------------------------------------------- | --------------------------- |
| NLM API (notebook_query × 2/day × 22 days)           | ~$0 (included in NLM Ultra) |
| NLM Deep Research (research_start × 2/day × 22 days) | ~$0 (included in NLM Ultra) |
| Compute (OpenClaw Pro, within existing allocation)   | ~$0 incremental             |
| NLM Ultra subscription                               | $20/month                   |
| Storage (state files, <1MB)                          | ~$0                         |
| **Total**                                            | **~$20/month**              |

**ROI estimate (DeepSeek R1 calculation):**

- Value per enriched article: ~$80 (time saved in manual research + accuracy improvement)
- Articles enriched per month (conservative): 10
- Monthly value: ~$800
- **ROI: ~3,900%** (pessimistic estimate: 292% using 3 enriched articles)

---

## 15. Appendices

### Appendix A: Domain Denylist

```
tripadvisor.com, expat.com/forum, kaskus.co.id, nomadicmatt.com,
thepointsguy.com, reddit.com, quora.com, medium.com/@, youtube.com,
tiktok.com, pinterest.com, booking.com, agoda.com, skyscanner.com,
lonelyplanet.com, balizero.com
```

### Appendix B: Claim Category Taxonomy

| Category            | Description                      | Example                                      |
| ------------------- | -------------------------------- | -------------------------------------------- |
| LEGAL_CHANGE        | New/amended regulation           | "Permenkumham X/2026 changes B211A max stay" |
| OPERATIONAL_CHANGE  | Same law, different practice     | "Ngurah Rai requires original degree certs"  |
| ENFORCEMENT_ACTION  | Specific enforcement event       | "Tim Pora swept 30 businesses in Canggu"     |
| ENFORCEMENT_PATTERN | Repeated enforcement trend       | "Third KITAS delay report this week"         |
| ELIGIBILITY_RULE    | Who qualifies for what           | "CEO position only for KBLI 06"              |
| FEE_CHANGE          | Official tariff changes          | "DKP-TKA USD 100/mo/position"                |
| PROCEDURAL_STEP     | Process/system changes           | "E-visa portal requires biometric page"      |
| PROCESSING_TIME     | Duration claims                  | "KITAS conversion 7-14 working days"         |
| SYSTEM_STATUS       | Portal/system operational status | "Molina down for maintenance"                |
| BASELINE_EXISTING   | Confirmation of unchanged status | "Kepmenaker 228/2019 still in force"         |

### Appendix C: Query Templates (20 production queries)

Refer to `01_query_design.md` Section 6 for the complete set of 20 query templates:

- 8 L1 Monitoring (2 per cluster A-D, bilingual)
- 4 L2 Comparative
- 4 L3 Deep Analysis
- 4 L4 Cross-Domain

### Appendix D: SVS Worked Examples

**Example 1: NusaBali press article (T5, 12 days old, 2 claims)**

```
V_tier = 0.35, V_claims = 0.25, S(12, NEWS) = 0.57
V_citations = 0.20, V_uniqueness = 0.50, BONUS = 0
SVS = 0.088 + 0.063 + 0.114 + 0.030 + 0.075 = 0.370 → MARGINAL
```

**Example 2: JDIH Gazette T0 (60 days old, 4 claims, 7 citations)**

```
V_tier = 1.00, V_claims = 0.50, S(60, LAW_IN_FORCE) = 1.00
V_citations = 1.00, V_uniqueness = 0.75, BONUS = 0.10
SVS = 0.250 + 0.125 + 0.200 + 0.150 + 0.113 + 0.100 = 0.938 → ESSENTIAL
```

### Appendix E: NB-2 NLM Source IDs (Quick Reference)

```
T0 National Law:
  0e1fd3f8  UU No. 6/2011 (Keimigrasian)
  4061643c  UU No. 63/2024 (BPK Full Text)
  adc39025  UU No. 63/2024 (Key Provisions)
  60025a37  PP No. 31/2013
  452d8a6f  PP No. 48/2021

T1 National Implementation:
  9fbfd84a  Kepmenaker 228/2019 — Permitted positions
  2e37838b  Kepmenaker 349/2019 — Prohibited positions
  8abf1fe6  Immigration circulars (SE 3/836 etc.)
  bd2cd5d2  TKA RPTKA guide
  db80b1c3  RPTKA DKP-TKA guide

T2 Regional (with claims):
  a1f41caa  izin_kerja_tka_procedura_completa
  723bfcd6  kitas_e23_tka_guida
  84333773  alih_status_offshore_autogate_guida
  27394849  merp_rientro_guida
  076cde21  imk_itk_itb_itp_documenti_soggiorno

Master Digests:
  42a3f083  [NB2-MD] Change Log
  c46cbb51  [NB2-MD] Operations Status
  6d336e6b  [NB2-MD] Cross-Domain Impacts
  d818b8ec  [NB2-MD] Open Questions
```

### Appendix F: Conversation IDs for Context Injection

| Phase | Conversation ID                        | Query Topic                                          |
| ----- | -------------------------------------- | ---------------------------------------------------- |
| P1-P4 | `3e8fe6db-8873-4689-9bff-226ee875c09d` | Cluster A — Work Permits (all queries share context) |

### Appendix G: File Locations

| File                  | Path                                                          | Size         |
| --------------------- | ------------------------------------------------------------- | ------------ |
| Pipeline state        | `apps/evaluator/nlm_nb2_pipeline_state.json`                  | ~3KB         |
| Source registry       | `apps/evaluator/nlm_nb2_sources.json`                         | ~40KB        |
| Claims database       | `apps/evaluator/nlm_nb2_claims.jsonl`                         | ~8KB         |
| Handoff package       | `~/.agent/decisions/nlm_to_scraper/handoff/latest.json`       | ~7KB         |
| This report           | `docs/superpowers/specs/nlm-deep-research/NB2_FULL_REPORT.md` | ~50KB        |
| Progress tracker      | `docs/superpowers/specs/nlm-deep-research/PROGRESS.md`        | ~15KB        |
| Design docs (7 steps) | `docs/superpowers/specs/nlm-deep-research/0*.md`              | ~200KB total |

---

## 16. Gemini Master Query Batch — Complete Results (2026-03-28 Session 2)

### 16.1 Overview

24 adversarial queries designed by Gemini 3.1 Pro executed against NB-2. Purpose: stress-test T0 source coverage, identify guide errors, measure cluster depth, and validate enforcement divergence claims.

**Conversation ID:** `3e8fe6db-8873-4689-9bff-226ee875c09d`

### 16.2 T0 PDF Uploads (Session 2)

| Source                                | Pages | Size  | NLM Source ID                          | Quality                                                          |
| ------------------------------------- | ----- | ----- | -------------------------------------- | ---------------------------------------------------------------- |
| PP 34/2021 (JDIH Kemnaker)            | 40    | 3.1MB | `62596ac1-d961-47b9-9626-bba630cd0db8` | ⚠️ Body may be scanned — NLM reads only Penjelasan (Pasal 15-29) |
| Permenimipas 5/2025 (peraturan.go.id) | 3     | 342KB | `359c4c5f-90ca-4ae9-a6ba-c2704c6e42f3` | ✅ Full text — Pasal 1-2 cited directly                          |

### 16.3 Complete Query Results (24/24)

| #   | Query                         | Cluster        | Result | Key Finding                                                     |
| --- | ----------------------------- | -------------- | ------ | --------------------------------------------------------------- |
| Q01 | UU 1/2026 destruction test    | Kill-Switch    | ✅     | NLM admitted hallucination, confirmed UU 63/2024                |
| Q02 | CEO KBLI correction           | Kill-Switch    | ✅     | Self-corrected: Kepmenaker 228 for TKA only                     |
| Q03 | Physical card vs e-ITAS       | Kill-Switch    | ✅     | Hybrid system: e-ITAS + physical card 15 days                   |
| Q04 | SE 3/836 validation           | Kill-Switch    | ✅     | Full detail: One Sponsor, exceptions                            |
| Q05 | PP 34/2021 T0 trigger         | T0             | ⚠️     | Metadata only → re-test after PDF upload: partial OCR           |
| Q06 | Permenkumham 22/2023 T0       | T0             | ✅     | T0 works! Cited Pasal 13, 15, 33, 70                            |
| Q07 | Permenimipas 5/2025 T0        | T0             | ✅     | After PDF upload: cites Pasal 1-2, pencabutan confirmed         |
| Q08 | PP PNBP fee schedule          | T0             | ❌     | Source not in notebook                                          |
| Q09 | KITAS→KITAP conversion        | B — Stay       | ✅     | 3yr wait, 2yr marriage, Rp15B shares                            |
| Q10 | LKPO sponsor reporting        | B — Stay       | ⚠️     | LKPO specific not found, guarantor obligations extracted        |
| Q11 | Family E31 vs E23 dep         | B — Stay       | ✅     | E31A exempt from Penjamin, Apostille replaces dual legalization |
| Q12 | VOA/e-VOA extensions          | C — Visit      | ✅     | VOA=60d, C1=180d, 10 citations                                  |
| Q13 | C1 visa run limits            | C — Visit      | ✅     | 60d initial, max 180d, 2x extension of 60d each                 |
| Q14 | C2/C7/C8 activities           | C — Visit      | ✅     | Detailed per-index, Tim Pora warning                            |
| Q15 | Tourist Levy Perda            | C — Visit      | ❌     | Perda Bali 6/2023 not in NB-2 (local, not national)             |
| Q16 | Digital Nomad E33G            | D — Special    | ✅     | USD 60K/yr, USD 2K/mo, no local clients                         |
| Q17 | Golden Visa E28B/C            | D — Special    | ✅     | **FOUND GUIDE ERROR!** E28B 10yr = USD 5M not 2.5M              |
| Q18 | Second Home vs Retirement     | D — Special    | ✅     | E33B no age/USD 130K, E33E 60+/USD 50K, E33F 55+/USD 3K/mo      |
| Q19 | Overstay penalties            | E — Compliance | ✅     | Rp 1M/day, 60d threshold, auto-deportation                      |
| Q20 | Deportation SOP               | E — Compliance | ✅     | 3-step SOP, 7d exit, Penangkalan = permanent                    |
| Q21 | Sponsor deportation liability | E — Compliance | ✅     | Absolute liability, Jaminan covers repatriation costs           |
| Q22 | Tim Pora operations           | E — Compliance | ❌     | No Bali-specific operational intel (documented gap)             |
| Q23 | Enforcement Divergence        | Bali           | ✅     | Prassi variabile confirmed, One Sponsor blocks alih status      |
| Q24 | OSS zoning block              | Bali           | ❌     | Cross-domain impacts not yet documented                         |

**Score: 18 ✅ full answers + 2 ⚠️ partial + 4 ❌ expected gaps = 20/24 substantive (83.3%)**

### 16.4 Updated Cluster Depth

| Cluster          | Before Batch | After Batch (24 queries) | Target (≥3) | Status      |
| ---------------- | ------------ | ------------------------ | ----------- | ----------- |
| A — Work Permits | 4            | 4                        | ≥3          | ✅ Exceeded |
| B — Stay Permits | 1            | **4**                    | ≥3          | ✅ Exceeded |
| C — Visit Visas  | 1            | **4**                    | ≥3          | ✅ Exceeded |
| D — Special Visa | 1            | **4**                    | ≥3          | ✅ Exceeded |
| E — Compliance   | 1            | **4**                    | ≥3          | ✅ Exceeded |

**All 5 clusters now ≥ 4 depth.** Pipeline ready for production.

### 16.5 Critical Finding: Guide Error Correction

**Query Q17** cross-validated T0 (Permenkumham 11/2024) against T2 guide and found:

- `kitas_e28b_e28c_golden_visa_guida_2025.txt` lists E28B 10yr as USD 2,500,000
- Permenkumham 11/2024 Pasal 40 Ayat (2) specifies USD 5,000,000
- **Errata Corrige source added** (`3780543f-7670-4ed8-a48a-32a4cd894d3b`)
- This validates the entire NLM pipeline thesis: T0 sources catch T2 guide errors

### 16.6 Identified Gaps (4 queries returned TIDAK DITEMUKAN)

| Gap                              | Priority | Resolution Path                                               |
| -------------------------------- | -------- | ------------------------------------------------------------- |
| PP PNBP (fee schedule)           | HIGH     | Identify and ingest the correct PP/Permen on immigration fees |
| Tourist Levy (Perda Bali 6/2023) | MEDIUM   | Add Perda as local T2 source (not T0)                         |
| Tim Pora operations (Bali)       | HIGH     | Monitor Kantor Imigrasi Ngurah Rai Instagram (T4 source)      |
| OSS-RBA zoning block             | LOW      | Cross-domain monitoring, will emerge from NB-3 (Company)      |

### 16.7 New Claims Added (14 from Session 2)

33 total claims in `nlm_nb2_claims.jsonl`:

- 17 VERIFIED (51.5%)
- 9 PROVISIONAL (27.3%)
- 4 SOURCE_GAP (12.1%)
- 3 LOW (9.1%)

---

## Revision History

| Date       | Author          | Change                                                                                                                           |
| ---------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 2026-03-28 | Claude Opus 4.6 | Initial report — full pipeline testing complete, GREEN verdict                                                                   |
| 2026-03-28 | Claude Opus 4.6 | Session 2: 24/24 Gemini queries completed, 2 T0 PDFs uploaded, Golden Visa error corrected, 14 new claims, all clusters ≥4 depth |

---

_End of report. Total: ~4,000 lines, covering 51 sources, 33 claims, 8 test phases, 24 adversarial queries, gap analysis, and production deployment plan._
