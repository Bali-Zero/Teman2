---
date: 2026-07-29
domain: compliance
client_case: none-product-research
sources:
  - apps/mouth/src/data/services_data.ts
  - apps/mouth/data/kbli-gold-all.json
  - apps/mouth/data/KBLI_2025_FINAL_CLEAN.json
  - apps/mouth/src/lib/kbli-gold-codes.ts
  - apps/mouth/src/lib/kbli-data.server.ts
  - apps/mouth/src/components/services/ServicePricing.tsx
  - apps/mouth/src/app/(blog)/services/[slug]/page.tsx
  - docs/pricing/Bali_Zero_Price_List_2026.md
  - apps/backend-rag/backend/data/bali_zero_official_prices_2026.json
  - apps/backend-rag/backend/services/rag/agentic/tools.py
  - apps/backend-rag/backend/services/pricing/pricing_service.py
  - apps/backend-rag/backend/services/compliance/lkpm_service.py
  - apps/backend-rag/backend/services/compliance/lkpm_deadline_notifier.py
  - apps/backend-rag/backend/services/compliance/lkpm_ready_pack.py
  - apps/backend-rag/backend/services/compliance/lkpm_validator.py
  - apps/backend-rag/backend/app/routers/lkpm.py
  - apps/backend-rag/backend/app/routers/cron_notifiers.py
  - apps/backend-rag/backend/services/intake/
  - research/agent-craft/proposed-agents/compliance-deadline-sentinel.md
  - postgres-nuzantara (read-only MCP) — companies, clients, client_company_links, practices, practice_types
---

# SLHS — Lane D: Internal Asset Audit

Auditor stance: every number below was produced by a command executed in this turn.
Where a probe returned zero, a sibling positive-control probe on the same apparatus is
reported alongside it, per the repo's "an empty set disguises itself as everything and
as nothing" discipline.

## 1. Inventory — exists / consumed / live-in-prod

| Asset | Exists (grep) | Consumed by | Live in prod |
|---|---|---|---|
| SLHS service card, `services_data.ts:773` | Yes, 1 hit | `ServicePricing.tsx` → rendered by `app/(blog)/services/[slug]/page.tsx` for `slug="company"` | **YES** — `https://www.balizero.com/services/company` returns HTTP 200, `grep -c "SLHS"` = 1. Control probes on sibling cards on the same page ("NPBBKC"/"Alcohol License" = 1, "Company Revision" = 1) confirm the probe methodology produces positives, so the SLHS positive is not an artifact of a broken grep. |
| `kbli-gold-all.json` SLHS content | Yes — **32 raw occurrences across 26 of 428 gold-tier KBLI codes** (not 28, not 32-as-code-count; see Method note below) | `apps/mouth/src/lib/kbli-data.server.ts` (loads `data/kbli-gold-all.json` at build time, `gold.baliContext` / `gold.whatChanged` / `gold.whatYouNeed` / `gold.zantaraOpener` render **directly** on `/kbli/[code]`) + `apps/mouth/src/lib/kbli-gold-codes.ts` (gold-code membership set) | Live for the 428 codes that have gold content and are in the currently-published gold set (not independently re-verified per-code in this pass — that's the KBLI-corpus lane's job, not asset-inventory's). |
| `docs/pricing/Bali_Zero_Price_List_2026.md` | **0 occurrences** of SLHS/hygiene/sanitasi/sanitation (264 lines, confirmed) | N/A | N/A — SLHS is not in the human-facing price sheet at all. |
| `apps/backend-rag/backend/services/routing/keyword_matcher.py` | **0 occurrences** (the file exists but has no SLHS string — team-lead's starting pointer was stale/wrong) | — | — |
| `apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py` | **0 occurrences** (same — file exists, no SLHS string) | — | — |
| **PricingTool backing data** (`bali_zero_official_prices_2026.json`, the file `PricingService`/`PricingTool` actually reads — `pricing_service.py:112`) | **0 occurrences** of SLHS | Consumed by the agentic RAG `PricingTool` (mandatory-first-call for all price questions) | The website card says "Check live pricing" for SLHS, but the authoritative pricing store the bot/tool would query has **zero SLHS line items**. The CTA points at a well that's empty. |

**Method note on the count discrepancy** (28 vs 32 vs "26 codes"): `grep -c` counts *matching lines*, not occurrences, and the JSON is pretty-printed with each field on its own line — so line-count ≠ occurrence-count ≠ code-count. Parsing the JSON directly (not grepping it) gives the ground truth: **26 distinct KBLI codes** contain the string "SLHS" somewhere in their gold content, for a total of **32 raw string occurrences** (one code, `56102`, alone accounts for 7 of them — it has the only structured, multi-field SLHS treatment; the other 25 codes each mention SLHS exactly once, always inside the free-text `baliContext` field). Anyone who cites "32" as "codes with SLHS content" is over-counting by 6.

## 2. Quality of the KBLI gold content on SLHS

Of the 26 codes, **25 mention SLHS in one sentence inside `baliContext`** — a colloquial, LLM-generated "insider tip" paragraph, not a structured fact block. Only **one code, `56102`** (food truck / non-permanent food structure), has SLHS-adjacent content in the structured fields (`whatChanged`, `whatYouNeed`, `zantaraOpener`) with real procedural detail: a Label HSP vs. Sertifikat SLHS distinction, a step-by-step permit sequence, concrete timelines (NIB 1–3 days, Label HSP ~2–4 weeks, total 4–8 weeks), a capital figure (IDR 10B stated / Rp 2.5B paid-up), and a norm citation ("PP28/2025's updated obligation framework").

### Isolated factual claims

| KBLI | Claim (verbatim, condensed) | Type | Verifiable? |
|---|---|---|---|
| 56102 | "Label Higiene Sanitasi Pangan (HSP)… is a label… NOT the full Sertifikat SLHS… required for permanent restaurants (56101)" | obbligo (distinction of instrument) | Yes — checkable against Dinas Kesehatan / Permenkes rules on food-hygiene labeling vs. certification. |
| 56102 | Cites "PP28/2025's updated obligation framework" as the source for the Label HSP vs SLHS split | norma | Yes — a PP number+year is a falsifiable citation. Not verified in this pass (out of scope for Lane D); flag for the norm-verification lane. |
| 56102 | "Label HSP — apply to Dinas Kesehatan kabupaten/kota; basic hygiene inspection… (~2–4 weeks)" | tempo | Yes, in principle — but note this is a *different* instrument (Label HSP) than the SLHS the website card and the other 25 codes describe. |
| 56102 | Total PT PMA → operational timeline "4–8 weeks" and "IDR 10 billion stated capital (Rp 2.5B paid-up)" | tempo + costo | The capital figure matches the known BKPM 5/2025 paid-up threshold ([[fact_bkpm_5_2025_paidup_capital_2_5_mld_2026_07_16]] in memory) — internally consistent with other repo knowledge, not independently re-derived here. |
| 55101–55104, 55202, 55204, 55209, 55901, 55909, 56101, 56210, 56290, 56301, 85574, 86995, 93196, 96220, 96230 | "You need TDUP and SLHS" / "SLHS mandatory for kitchen/F&B operations" (18 codes) | obbligo | Plausible in shape (hospitality/F&B needs a hygiene cert) but stated with zero specificity — no timeline, no cost, no issuing authority beyond "Dinas Kesehatan" mentioned once (56101). Not independently falsifiable as written; it's a generic assertion repeated with cosmetic rewording per code. |
| 41017 | "Your PBG is a strict prerequisite for the operational TDUP **or** SLHS" | obbligo | **Suspect.** Phrases TDUP and SLHS as alternatives ("or"), but every other code in this same dataset treats them as two *separate, both-required* permits ("TDUP **and** SLHS" — see 55204, 55209, 55901, 55909, 56301). This is an internal contradiction, not a nuance — one code says "either", the rest say "both". |
| 68112 | SLHS glossed as "**Standard Certificate for Hospitality**" | norma (naming) | **Wrong on its face.** SLHS = *Sertifikat Laik Higiene Sanitasi* (a hygiene/sanitation feasibility certificate), not a generic "hospitality standard certificate" — that description is closer to what "Sertifikat Standar" or TDUP mean elsewhere in the *same* dataset. This is the clearest internal inconsistency: three different codes give three different definitions of what the same acronym stands for. |
| 70201 | SLHS glossed as "health certificate" | norma (naming) | Directionally correct but generic; doesn't match the 56102 entry's precise expansion (*Sertifikat Laik Higiene Sanitasi*). |
| 93196 | SLHS glossed as "Sanitation and Hygiene Certificate" | norma (naming) | Closest of the loose glosses to the correct meaning. |
| `services_data.ts:773` (site card, not gold JSON) | "3-4 weeks processing" for SLHS | tempo | **Uncorroborated.** No code in the 26-code gold-content set states a timeline for the *full* Sertifikat SLHS (as opposed to 56102's Label HSP, which is a different, lighter instrument at "~2-4 weeks"). The site's "3-4 weeks" figure for the real SLHS has no traceable source in this repo's own KBLI data. |

### Verdict on content quality

**The strongest evidence the content is LLM-invented rather than researched is the acronym itself carrying three incompatible glosses** ("Standard Certificate for Hospitality" at 68112 vs. "health certificate" at 70201 vs. "Sanitation and Hygiene Certificate" at 93196 vs. the correct *Sertifikat Laik Higiene Sanitasi* only spelled out once, at 56101 and 56102) **and one code (41017) contradicting all the others on whether TDUP and SLHS are alternative or cumulative requirements.** Outside code 56102, every SLHS mention is a single decorative sentence with no procedural payload (no authority, no cost, no timeline, no form number) — consistent with a model generating a plausible-sounding compliance detail to round out a "baliContext" paragraph rather than transcribing a researched fact. Code 56102 is the outlier: it has real structure and a real norm citation, and is the one artifact in this set actually worth fact-checking against the cited PP28/2025.

## 3. The installed base (aggregates only — zero PII)

DB reachable: **YES** (`postgres-nuzantara` MCP, read-only role). Schema check first
(`information_schema.columns`) found KBLI/sector lives on `companies.kbli_code` /
`companies.kbli_description`, linked to `clients` via `client_company_links`
(client_id/company_id join table) — `companies` has no direct client FK.

- **Total companies in CRM**: 1,778. With a non-empty `kbli_code`: 736.
- **F&B / hospitality companies**: **161**, using KBLI-code prefix (`56xxx`/`55x`) OR a
  word-boundary-safe regex over `kbli_description` (`restoran|restaurant|cafe|café|
  catering|hotel|villa|bar|warung|akomodasi|accommodation|hospitality|kuliner|makanan|
  minuman`).
  - **Correction caught mid-audit**: a naive `kbli_description ILIKE '%bar%'` gives
    **269**, not 161 — but only **11** of those 158 "bar" hits are the actual word "bar"
    (`~* '\ybar\y'`); the other **147 are substring false-positives** inside unrelated
    Indonesian words (e.g. *besar*, *sebagai*, *Barang*). This is a live instance of
    this repo's documented "guard-over-match / substring trapping" failure mode — the
    naive query would have overstated the F&B cohort by ~67%. **161 is the corrected,
    word-boundary-safe figure.**
- **Historical SLHS/hygiene/sanitasi practices**: **0 of 749 total practices**, checked
  across `title`/`description`/`notes`/`internal_notes` for `SLHS` (ILIKE) and for
  `higiene|hygiene|sanitasi|sanitation` (word-boundary regex). Also checked the
  `practice_types` catalog directly: **there is no `SLHS`/hygiene/sanitation entry in
  `practice_types` at all** — it isn't just that we've never closed one, the ops system
  has no defined service line for it. Strong, unambiguous fact: Bali Zero has never
  once fulfilled an SLHS engagement through the practice-tracking pipeline.
- **Geographic distribution of the 161 F&B/hospitality companies** (kabupaten,
  case/spelling variants collapsed): Badung 72 (incl. Kuta 12, Canggu/Mengwi 5),
  Denpasar 31, Gianyar 16 (incl. Ubud 5), missing/blank 19, Karangasem 3, everything
  else (Lombok, Jakarta, Tangerang Selatan, Bima, etc.) 1 each. Concentrated exactly
  where expected — greater Badung + Denpasar + Gianyar = 119/161 (~74%).
- **Cross-sell cohort (company-setup closed in the last 12 months, F&B/hospitality
  KBLI)**: **could not be reliably computed — reported honestly rather than guessed.**
  Two independent attempts, both dead ends for different reasons:
  1. Joining `practices` (filtered to `practice_type_code IN
     ('company_pt_pma','new_pt','pt_pma_setup')`, `status='completed'`) to
     `client_company_links`/`companies`: the *entire* `practices` table only has **2
     rows total** (not just in the last 12mo — ever) tagged with those company-setup
     type codes (1 completed, 1 cancelled). Company creation is evidently not tracked
     through `practices` in this system — that table is not a usable proxy for
     "setup closed" events.
  2. Falling back to `companies.created_at >= now() - 12 months`: this returns
     **161 — identical to the whole F&B cohort**, which is the tell that it's wrong.
     `date_trunc('month', created_at)` shows **1,723 of 1,778 companies (97%) were all
     created in a single month, March 2026** — a bulk CRM migration, not real onboarding
     dates. `created_at` is a migration timestamp for nearly the entire table, not a
     signal of when the client actually onboarded.
  **Conclusion: this repo's CRM currently has no reliable field to answer "which F&B
  clients closed setup recently" — neither `practices` (too sparse) nor
  `companies.created_at` (dominated by migration noise) can answer it.** Answering it
  for real would need either a real "date PT went live" field (akta date? NIB issue
  date? — both exist as columns, `akta_pendirian_date`/checked for a KBLI-linked
  company but not tested here) or fixing the practices-linkage gap. Flagging as a data
  gap, not a zero.

## 4. Adjacent capabilities already built (reuse candidates)

| Capability | Path | What it does | Reusability | What's missing for SLHS |
|---|---|---|---|---|
| **LKPM quarterly compliance cycle** | `apps/backend-rag/backend/services/compliance/{lkpm_service.py, lkpm_deadline_notifier.py, lkpm_ready_pack.py, lkpm_validator.py}` (2,757 lines total) + `app/routers/lkpm.py` + wired into `app/routers/cron_notifiers.py` (`POST /lkpm-deadlines`, live cron endpoint) | Deterministic (no-AI-on-numbers) quarterly deadline tracking, per-client config (`lkpm_client_config.kbli_codes` — **already keys eligibility off KBLI code array**, exactly the shape SLHS-per-KBLI eligibility would need), assignee routing to named tax consultants, PDF "ready pack" generation, deadline notifier on a schedule. | **ALTO** — this is the closest existing template to "periodic compliance obligation tied to a KBLI code, with deadline tracking + PDF + notification". An SLHS-renewal cycle is structurally the same shape (client has KBLI X → obligation Y → recurring deadline → PDF/notify) just with a different periodicity and a different document. | A new `slhs_client_config` (client × KBLI × renewal-date) table/model, an `SLHSDeadlineNotifier` mirroring the LKPM one, and — since SLHS is a Dinas Kesehatan issuance rather than an OSS self-report — a PDF/checklist template instead of LKPM's specific report format. |
| **Compliance-deadline-sentinel agent** | `research/agent-craft/proposed-agents/compliance-deadline-sentinel.md` | Daily sentinel scanning CRM for approaching/lapsed statutory deadlines (KITAS, LKPM, SPT, NIB/izin) | **Not built** — this is a *proposal doc* only, not present in `.claude/agents/`, not wired to any cron. Listed here because it's the right shape to extend to SLHS renewal, but don't count it as an existing asset — it would need to be built, and SLHS added to its obligation catalog when it is. | Everything — the agent itself doesn't exist yet. |
| **PricingTool + PricingService** | `apps/backend-rag/backend/services/pricing/pricing_service.py`, `services/rag/agentic/tools.py::PricingTool`, backing file `backend/data/bali_zero_official_prices_2026.json` | Mandatory-first-call pricing lookup for the agentic RAG bot, categories `visa/kitas/business_setup/tax_consulting/legal/all` | **ALTO** for the mechanism, **ZERO** for SLHS content today — confirmed 0 SLHS entries in the backing JSON (§1). Adding SLHS is a data-entry task, not an engineering one; the tool and category (`business_setup`) already exist. | An actual price for SLHS in `bali_zero_official_prices_2026.json`. |
| **Document intake / OCR pipeline** | `apps/backend-rag/backend/services/intake/` + `app/routers/{intake_review.py,intake_gate.py}` + migrations `212_intake_unified.sql` through `246_clients_wa_intake_autocreate.sql` | WhatsApp/Drive document ingestion → OCR (local `qwen2.5vl:7b`, UU PDP-scope) → classify → route → attach-to-client, with a review-queue gate | **ALTO** — an SLHS application needs document intake too (business location photos, kitchen layout, existing NIB, KTP of PIC). This pipeline is generic-document-shaped already; it would need an SLHS-specific document-type classifier added to its taxonomy (`232_intake_category_taxonomy_cleanup.sql` shows the taxonomy is a maintained, extensible list, not hardcoded). | An "SLHS supporting docs" category in the intake taxonomy; no new pipeline. |
| **client-case-quote-generator agent** | (agent roster, not a repo path — Opus + Kimi K3 hybrid synthesis, per CLAUDE.md/agent definitions) | Generates a branded PDF client quote (cost/timeline/risk/deliverables) from `PricingTool` + brand skill | **ALTO**, contingent on the pricing-data gap above being closed first — the generator is service-agnostic; it just needs an SLHS price to quote. | Same dependency as PricingTool: a real price. |
| **KBLI pages / gold-content pipeline** | `apps/mouth/src/lib/kbli-data.server.ts`, `apps/kbli-navigator/scripts/generate_gold_content.py`, `apps/kbli-navigator/lib/kbli-gold-content.ts` | The SSG `/kbli/[code]` pages, 428-code gold tier, plus the KBLI Navigator app's own gold-content generator script | **MEDIO** — it's the delivery surface, not a service pipeline; useful as a distribution channel for corrected SLHS facts (once §2's inconsistencies are fixed) but doesn't do any of the SLHS *operational* work itself. | Fixing the acronym-inconsistency and the TDUP/SLHS "or" bug found in §2, ideally sourced from a verified fact, not regenerated by another LLM pass. |

## Bottom line

- **Vetrina**: the SLHS card is genuinely live on `balizero.com/services/company` (verified by direct curl, not assumed) — but its price CTA ("Check live pricing") resolves to an authoritative pricing store with **zero SLHS entries**, so a live agent/bot asked for an SLHS price today would come up empty against the very tool it's required to use first.
- **Contenuto KBLI**: 26 codes mention SLHS, 25 of them in one decorative, unverifiable sentence each; the acronym is glossed three incompatible ways across the dataset and one code (41017) contradicts the other 17 on whether SLHS and TDUP are alternative or both-required. Only 56102 has real procedural depth and a checkable norm citation (PP28/2025) — everything else reads as plausible filler, not researched fact.
- **Base installata**: 161 F&B/hospitality clients in CRM (word-boundary-corrected; a naive substring query overstates this by 67%), concentrated in Badung/Denpasar/Gianyar as expected, **zero** historical SLHS practices and **zero** definition of SLHS as a service line in `practice_types` — Bali Zero has sold proximity to this certificate (via the website card, via 26 KBLI pages) but has never once operationally delivered it. The "immediate cross-sell cohort" (recent company-setup + F&B KBLI) is not answerable from current CRM data — both plausible proxies (`practices` linkage, `companies.created_at`) are broken for different reasons, honestly reported rather than estimated.
- **Riuso**: the LKPM compliance-cycle codebase (2,757 lines, live, cron-wired, already keys obligations off a KBLI-code array) is the strongest existing asset to fork for an SLHS renewal-tracking product — closer to "adapt a working quarterly-obligation engine" than "build a compliance tracker from zero."
