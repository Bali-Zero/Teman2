---
adversarial_review: gemini
date: 2026-07-23
domain: visa
client_case: none
author: Kimi (Air-M5) — W5 decision-support lane
status: INPUT FOR OWNER DECISION D1
---

# D1 decision pack — real traffic vs G-a thresholds (receipts inside)

Purpose: give Zero measured data, not estimates, for the D1 call (G-a semantics + threshold),
per Fable-delta-7 ("receipts owed"). All queries re-runnable.

## Receipt 1 — prod DB (read-only, re-run 2026-07-23T17:01Z)

`visa_checks` = 28 rows total, last 2026-04-21 · `visa_decisions` / `visa_rule_packs` /
`visa_ruleset_activations` / `visa_source_records` = 0 rows. (Query in
`2026-07-23-architect-state-analysis.md` §receipts; re-run via postgres read-only MCP.)

## Receipt 2 — GA4 live traffic (90 days → yesterday, property balizero.com)

| Page | Views | Sessions | Users |
|---|---|---|---|
| `/visa` | 105 | 72 | 58 |
| `/visa/match` | 37 | 30 | 25 |
| `/visa/clock` | 18 | 15 | 13 |
| `/visas/*` (107 article URLs, top 25 pulled) | ~5–20 each | — | — |

Derived rates:

- `/visa/match` entry page: **~0.33 sessions/day** (30 in 90d).
- Whole `/visa` funnel entry: **~0.8 sessions/day**.
- Historical best (launch spike, April): 28 submissions / ~4 days ≈ **7/day** — 20× the
  steady state, and still 20× short of the gate.
- The gate asks **1,000 completions in ≥7 days ≈ 143/day**. Gap vs steady organic:
  **~400×**. At steady organic, 1,000 completions take **~8 years**; even converting 100% of
  `/visa` sessions, ~3.4 years.
- The launch-week 7/day proves a push can spike the funnel — but sustaining 143/day
  organically needs a traffic program, not a fix.

## What this means for D1 (Fable split applied)

- **G-a-vol (real requests, reported):** any fixed threshold ≥1,000/7d is unreachable without
  a paid/owned traffic program. Realistic proposal: **≥100 distinct real requests over a
  ≥14-day window with zero unexplained engine errors** — evaluator-logic failures fail the
  gate; transient infrastructure errors (deploys, 5xx from unrelated systems) are excluded
  but must be explained in the window report (Gemini R1 objection, adopted). Reachable in
  ~2–4 weeks with the modest traffic push below, and honest about what it measures
  (stability under real load, not coverage).
- **G-a-breadth (7 categories / 30 codes):** corpus-driven per Fable-delta-2 — gold-persona
  fleet extended to the 30 priority codes, explicitly labeled `traffic_source=synthetic`
  (needs migration 256). Real usage will never cover business/diaspora/bridging lanes in
  measurable time.
- **Window traffic source (Fable-delta-4):** real-fact rows come from the live v2 interview
  (shadow-POST while rendering curated). To get even 100 real requests the v2 surface needs
  placement: homepage feature, newsletter send (subscriber base exists), blog embeds
  (`ArticleToolEmbed` already supports `visa-match`), and removal of `noindex` only at
  ENFORCE. Optional: targeted Ads micro-budget (~€200) if Zero wants the window in days
  instead of weeks.

## Traffic levers inventory (existing assets, no new build)

- 107 `/visas/*` article URLs already indexed (SEO base, 5–20 views each per 90d).
- `ArticleToolEmbed` mapping `visa-match` → `/visa/match`. The v1 wizard is FIXED since
  2026-07-24 (PR #3032 merged; live smoke 201 + row in `visa_checks`), so the embed works
  today; re-pointing to `/visa-oracle` is a separate Track-C-time decision at ENFORCE.
- Newsletter subscribers (MCP `list_subscribers`), WhatsApp broadcast lists, IG via WR2.
- Ditjen-demo angle (Track D) doubles as an authority backlink source once G-b is green.

## Recommendation (for the D1 call)

Adopt the Fable split: **G-a-vol = ≥100 real / ≥14d / zero engine errors** (owner may set
higher); **G-a-breadth = corpus-labeled**; run one funded traffic push during the window so
the real-volume number means something. If Zero instead wants 1,000/7d strictly real:
budget a real acquisition campaign (~2 orders of magnitude over current organic) or accept a
multi-month window — the data says there is no third way.

## Adversarial review

Gemini R1 pass (2026-07-24): P1 'zero engine errors conflates infra with evaluator failures' — ADOPTED, criterion rewritten ('zero unexplained engine errors', infra excluded but must be explained). P2 'contradictory embed re-pointing' — clarified (v1 fixed via #3032; re-point is a Track-C-time decision). None survived, 2 raised.
