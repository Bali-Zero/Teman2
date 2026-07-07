# SPEC — KBLI Navigator: Monumental Overhaul (2026-07-07)

> Mandate (Zero, verbatim intent): perfect ALL ~1600 KBLI one-by-one against sources of truth;
> BKPM-presentable aesthetics; per-code image perfection; killer content; simple UI/UX; identical
> availability on all machines + easy team access from tomorrow; code-by-code parity with
> balizero.com/kbli-navigator; an editorial article per perfected code with Bloomberg/NYT-grade cover.

## GROUND facts (all verified on disk/live TODAY 2026-07-07)

- PROD = `apps/mouth` → balizero.com/kbli (…/kbli-navigator 301→/kbli). Vercel auto-deploy on main.
- SSOT dataset: `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` — **1559 codes** (KBLI 2025 post-PP28).
- OSS ground truth: `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json` (2422 rec / 1559 5-digit, extracted 2026-06-19).
- **L0/L1 core is CLEAN**: re-audited today → 0 missing, 0 phantom, 0 judul divergence, 0 uraian sim<0.80.
- OSS `judul_en/uraian_en` fields contain INDONESIAN text → no official English exists. Our curated EN titles: ~180/1559.
- intel_2026 (L3 editorial): 100% coverage, structured (whatItMeans/whatYouNeed/whatChanged/zantaraOpener/baliContext/whoThisIsFor), quality NOT verified per-code.
- l4_bali: 100% coverage, 11 status enums (UI translates to EN labels correctly in BaliStatusBadge.tsx).
- Gold tier: 436 codes (kbli-gold-all.json) vs 1123 non-gold → view/content disparity.
- per_skala: 1458/1559; 101 missing, concentrated in special-regime sectors (84/85/87/88/91/94/64) — legitimate OSS absence, needs graceful "special regime" rendering.
- Tests: 39/39 green (vitest, 7 kbli suites).
- Hero images: `kbli-hero-images.ts` — hardcoded Unsplash HOTLINKS, gold codes only, duplicates, zero local files.
- Articles: 29 sector-level articles mapped by 2-digit prefix (`kbli-articles.ts`). No per-code articles.

## CONFIRMED error classes (live HTML, raw-grepped — not summarizer claims)

- E1. **Italian leaking into English pages**: `l4_bali.reason` in Italian on 5 codes (01111, 47111, 47112, 69102, 70209), injected raw into FAQ sentences + JSON-LD (`kbli-faq.ts:36`).
- E2. **"X" (X) duplication**: where no EN title exists, copy renders `"<judul ID>" (<judul ID>)` — silly duplication in FAQ/JSON-LD/keywords on ~1380 codes.
- E3. **Date format soup**: "13/5/26" vs "May 13, 2026" vs "2026-05-13" across sections.
- E4. **English title coverage 12%** → h1/title Indonesian-only on ~1380 codes for an English-audience product.
- E5. **Cover images**: Unsplash hotlinks (external dependency, generic stock, duplicated across codes, non-gold codes fall back), zero uniqueness per code.
- E6. **Licensing matrix gaps**: some pages show "8 scales" copy with only Mikro rendered (view gap) + 101 special-regime codes render sparse.
- E7. **intel_2026 unverified at per-code level** (the June generation covered all 1559; per-code factual QA never ran).
- E8. **3 divergent app forms**: apps/mouth (PROD) vs apps/kbli-navigator (standalone, stale data kbli-2025.json) vs native Swift app (out of repo). Scar family #1.

## Lint baseline (full-width, deterministic — scripts/kbli_dataset_lint.py, run 2026-07-07)

| Rule | Count | Nature |
|---|---|---|
| L1 italian-prose | 12 | 5 l4 reasons + 7 whatChanged |
| L2 en-title missing | 1186 | curated EN titles cover only 373 |
| L3 phantom code refs | 180 | 93 whatChanged (2020-mapping context, needs clean labeling) + **81 forward-looking refs to codes that don't exist in 2025** (youllAlsoNeed 48, whatYouNeed 18, baliContext 10, zantaraOpener 4, whatItMeans 1) + 6 l4 reasons |
| L4 date-format | 434 | ALL in l4_bali.reason → deterministic normalization safe |
| L6 risk mismatch | 128 | 127 distinct codes: prose contradicts per_skala risk |
| L7 per_skala empty | 101 | special-regime sectors (84/85/87/88/91/94/64) — render gracefully |
| L8 italian reason | 5 | subset of L1 |
| machine-artifact prose | 20 codes | "agent mapping:", "auto-matched to", "pp28 previous code(s):" leaked into copy |

## DESIGN

### D1 — Data perfection factory (BUILD B)
Per-code verification+enrichment over all 1559, waves of 50:
- Deterministic lints FIRST (no LLM): language-detect on every prose field (no Italian), no "X (X)" pattern,
  date format normalization, every KBLI code referenced in prose EXISTS in the 1559 set (anti-phantom lint),
  pma coherence (national closed ⇒ no "registrable in Bali"), reason-in-English.
- LLM wave 1 (Sonnet batches): **EN titles for all 1559** — professional investor-facing titles from judul+uraian, style guide anchored on the existing 180 curated (keep them verbatim).
- LLM wave 2 (Sonnet batches): per-code intel_2026 QA vs L0 uraian + L2 per_skala/PMA + l4 — flag+rewrite ONLY where factually divergent or vapid; facts only from provided layers (no memory).
- Verify pass (generator≠grader): separate agents re-check N% sample + ALL rewrites; deterministic lints re-run full.
- Output: dataset patch PRs + `kbli-perfection-ledger.json` (per-code: checks passed, wave, timestamp).

### D2 — Cover system (BUILD C) — hybrid curated-generative
- ~21 KBLI sections (A-U) × curated palette + visual language (brand tokens Warm Depth `--bz-accent #d4845a` family).
- Deterministic renderer (HTML/CSS → PNG via Playwright, reuse WR2 renderer decision): per-code UNIQUE cover
  composing: sector art layer + generative geometry seeded by code digits + editorial typography (code, EN title,
  section) + status accent. 1600×900 (OG) + hero crop. All LOCAL files (kill Unsplash hotlinks).
- Optional layer (phase 2, credit-bounded): FlowKit sector base-art (~21×4 variants) critic-gated, replacing
  geometric layer where it wins. NOT blocking wave 1.
- Acceptance: 1559 unique local covers, deterministic rebuild, no external hotlinks, wired as hero + og:image.

### D3 — Editorial article per code (BUILD D)
- Interpretation (declared): per-code long-form editorial guide PAGE on balizero.com (unique URL per code),
  article-formatted (headline, standfirst, body sections, pull-quotes, cover from D2), generated from
  L0+L2+L4+intel_2026 ONLY (anti-presunzione gate: any code/number/rule in prose must exist in the layers;
  lint rejects otherwise). Implemented as enriched /kbli/[code] "Guide" view — no 1559-post blog flood (SEO).
- Flagship sector articles (29 existing) keep cadence; per-code guides ARE the website articles, each with cover.

### D4 — UI/UX BKPM-grade (BUILD A)
- Bilingual title system: EN primary + ID official secondary everywhere (h1, title, JSON-LD) once E4 closes.
- Fix E1/E2/E3 structurally: reason normalized to EN in DATA; copy builders never duplicate; single date formatter.
- per_skala special-regime rendering (E6); licensing matrix renders ALL scale rows.
- Provenance strip on detail pages ("OSS RBA · PP 28/2025 · verified <date>") — BKPM-credibility.
- Print stylesheet (BKPM handout) + visual polish pass on index/sectors/detail.

### D5 — Parity + fleet + access (SHIP)
- apps/kbli-navigator standalone: ARCHIVE (README tombstone → PROD is apps/mouth) or align its dataset by symlink/build step; decision at build (red-team input).
- Swift app: PENDING-ARMS line (out of repo; SoT sync note) — not blocking.
- Deploy: PR → main → Vercel; live QA on N sample codes (raw HTML greps, code-by-code dataset stamp parity).
- Fleet: git pull --ff-only M5/Pro/Mini after merge; app itself is web = identical everywhere by construction.
- Team access: balizero.com/kbli announcement draft (Brevo, from zantara@balizero.com) after live QA passes.

## Budget shape (Gear 3 declaration)
- GROUND: 2 Explore agents + inline audits (done).
- BUILD B waves: ~32 batches × 2 passes ≈ 60-70 Sonnet agents via Workflow (batched, pipelined).
- BUILD C: deterministic (no agents) + optional critic loop later.
- BUILD D: ~32 batches Sonnet + verify sample agents.
- Council: NO full council (blueprint 2026-06-19 already fixed architecture); 1 red-team spalla (Codex) on this spec.
- Stop-loss: if a wave's verify pass rejects >30% of a batch, halt waves, rescope prompt, resume.

## Acceptance (falsifiable)
1. `audit_current_vs_oss.py` still 0/0/0/0 post-changes.
2. Deterministic lint suite: 0 Italian-language prose fields, 0 "X (X)", 1 date format, 0 phantom code references, EN title 1559/1559.
3. 1559 local cover files exist, sha-unique, wired (og:image + hero) — sampled visually.
4. Per-code guide sections render for 100% codes (SSG build passes, sample QA).
5. Live balizero.com/kbli/<code> raw HTML: E1/E2/E3 absent on the 5+3 known-bad codes + random 20.
6. vitest kbli suites green + new lint tests green.
7. Fleet HEADs identical; PENDING-ARMS updated for Swift app + any deferred item.
