# Bali Zero Social SOTA 2026 — Research Design

**Date:** 2026-04-22
**Author:** Claude Opus 4.7 (brainstorming w/ Antonello "Zero" Siano)
**Status:** Design approved, plan next

---

## Goal

Produce a living research system that tells Bali Zero what to publish on social
media, how, and when — validated against real metrics and continuously
recalibrated. Research is not a document that ages; it is configuration that
WR2 reads, metrics that M13 collects, and weights that Council retrains.

**Pillar split (explicit weights):**

- 40% Lead generation — qualified contacts attributed to social, with GA4 +
  UTM + CRM triangulation.
- 30% Authority — SOV in Ahrefs Brand Radar, AI citations, domain rating
  growth, media pickup.
- 30% Audience — follower + subscriber growth, engagement rate, saves per
  post.

**Market:** Expat Bali primary (boomer retiree, techie PMA founder, Italian
AIRE). Domestic Indonesian professional secondary (konsultan KADIN, PMA
founder ID, UMKM digital) for future pivot — included in research but not
in Fase 0 publishing targets.

**SOTA level:** "Agentic / predictive" (per Q5 in brainstorm). Shot 10 days
+ rolling loop 90 days. Persona engine simulates audience response before
publication; M13 feedback loop closes post → measure → retrain cycle.

---

## Architecture

Three layers, five modules, integrated with existing WR2 pipeline.

```
LAYER 1 — TELEMETRY
  telemetry_bootstrap: GSC, GA4, IG Graph API, Ahrefs SOV + AI citations,
                       Brevo stats, CRM UTM attribution (currently broken —
                       fix is inside scope).

LAYER 2 — KNOWLEDGE ACQUISITION (3 parallel modules)
  empirical_ig:        25 posts @balizero0 (excluding last 4 too recent),
                       classified by hook/tone/format/cadence with metric
                       correlation.
  benchmark_competitor: 18 accounts × 15 posts = 270 rows (10 agencies +
                       8 expat influencers). Team member manual scrape for
                       IG+LinkedIn, Playwright MCP for TikTok.
  literature_synthesis: Gemini 3.1 Pro deep research + NotebookLM + existing
                       q01-q60 X research corpus.

LAYER 3 — SYNTHESIS
  consiglio_playbook:  Consiglio v1 orchestrates Claude + Gemini + DeepSeek
                       + NotebookLM. Produces playbook.md, personas.json
                       (6 personas), wr2_weights.json.

INTEGRATION — WR2 LIVE
  editorial_config.py reads playbook (cadence + format mix).
  Council v2 takes persona as input for tone selection.
  M13 Measurer closes loop T+24h/72h/7g → retrain weights.
```

Each module produces named artifacts in `research/sota-social-2026-v1/`.
Files are versioned; monthly retrain increments minor version.

---

## Scope decisions locked in brainstorming

| # | Decision | Brainstorm Q | Notes |
|---|----------|--------------|-------|
| 1 | Pillar weights 40/30/30 | Q2 D | Balanced |
| 2 | 14 channels in research | Q4 all | Publishing subset decided in playbook |
| 3 | SOTA agentic/predictive | Q5 C | Persona engine + M13 loop |
| 4 | Baseline-first target setting | Q6 D | No numeric target until telemetry runs 10d |
| 5 | 18 competitors (10 agencies + 8 influencers) | Q7 B | Tribes 3/4 for Cycle 2 |
| 6 | Research dimensions: Hook + Tone + Cadence + Format | Q8 A4 | Visual + narrative structure derived, not primary |
| 7 | Hands-off mode + 25 own posts as ground truth | Q9 A (custom) | Zero 20-30min/day Telegram approval |
| 8 | Hybrid agentic + empirical approach | Q10 C | |
| 9 | Budget $0 out-of-pocket (except ~$1 DeepSeek over 100d) | arsenale-first audit | Team 25h manual scrape replaces Apify |
| 10 | Fase 0 = 10d, Loop = 90d rolling | timeline | |

---

## Phase 0 — Intensive shot (10 working days)

Daily deliverables per Section 2 of design. Key constraints:

- Zero: 20-30 min/day Telegram approvals.
- Team member: ~25h total, days 2-6, manual IG scraping per runbook.
- All scripts run on Pro (launchd + Ollama local).
- Each gate is blocking; failure stops Fase 0 and asks Zero.

### Daily plan

| Day | Focus | Key output |
|-----|-------|-----------|
| 1 | Telemetry bootstrap | `00_baseline.json` ≥20 real metrics |
| 2 | Empirical IG classify + scrape start | `01_balizero_corpus.json` v0 |
| 3 | Literature research kickoff | `03_sota_literature.md` v0, ≥30 sources |
| 4 | Persona wave 1 (3 expat) | `04_personas.json` draft |
| 5 | Persona wave 2 (3 ID) + benchmark halfway | Combined personas |
| 6 | Consiglio v1 delibera wave 1 + scrape complete | `preliminary_playbook.md` |
| 7 | Empirical × benchmark reconciliation | `07_gap_analysis.md` + `05_format_matrix.json` |
| 8 | M13 wiring + WR2 Council v2 | M13 closed, Council reads persona |
| 9 | Consiglio v1 final delibera | `08_playbook.md` v2 final |
| 10 | Package + Zero approval + canary go-live | `11_go_live_canary.md` + Loop start |

### 7 blocking gates

1. **Gate 1 (EOD 1):** `00_baseline.json` has ≥20 numeric metrics (not N/A). Check: `jq '[.. | numbers] | length' 00_baseline.json`.
2. **Gate 2 (EOD 2):** 25 posts classified; no single tone register accounts for >60% of the `01_balizero_corpus.json` sample (skew check — if one tone dominates that heavily, classifier is broken or corpus is too narrow).
3. **Gate 3 (EOD 6):** ≥243 rows in `02_competitor_corpus.json` (270 target − 10% tolerance).
4. **Gate 4 (EOD 5):** 6 personas, each with ≥15 attributes + ≥3 verbatim quotes from real comments.
5. **Gate 5 (EOD 3):** `03_sota_literature.md` cites ≥30 distinct sources, ≥10 from 2025-26.
6. **Gate 6 (EOD 9):** Consiglio v1 has ≥3 of 4 LLMs agreeing on key claims. Disagreement flagged as "disputed".
7. **Gate 7 (Day 10):** Zero approves `08_playbook.md` + `11_go_live_canary.md` via Telegram before Loop starts.

### Fase 0 deliverables (12 artifacts)

The directory `research/sota-social-2026-v1/` will contain:

- `00_baseline.json` — ≥20 metrics timestamped
- `01_balizero_corpus.json` — 25 posts classified with correlations
- `02_competitor_corpus.json` — 270 rows (18 × 15)
- `03_sota_literature.md` — 20-35 pages, ≥30 sources
- `04_personas.json` — 6 personas (3 expat + 3 ID)
- `05_format_matrix.json` — 294 cells (14 channels × 3 objectives × 7 registers)
- `06_cadence_engine.json` — posting windows per channel × timezone
- `07_gap_analysis.md` — ≥15 gaps + ≥8 strengths
- `08_playbook.md` — 40-50 page operational playbook
- `09_wr2_weights.json` — Council tone selection weights + kill switches
- `10_m13_measurer_config.md` — spec for feedback loop closure
- `11_go_live_canary.md` — first 7 days runbook

---

## Loop 90 days — rolling system

Fully automated after go-live. Three cadence layers:

**Every 6 hours:** `scripts/m13_collect_post_metrics.py` pulls IG Graph +
LinkedIn API + GA4 for every post published in last 168h.

**Weekly (Sunday 06:00 WITA):** `scripts/m13_weekly_report.py` aggregates,
computes delta vs baseline, retrains `wr2_weights.json` if pattern emerges,
sends Telegram digest.

**Monthly (1st 04:30 WITA):** `scripts/m13_monthly_retrain.py` re-scrapes
competitors (MCP browser stealth), re-runs Ahrefs SOV, re-infers personas,
updates playbook if delta > 15% on KPI target.

**Milestones (days 30/60/90):** `scripts/m13_checkpoint.py` produces formal
go/pivot/kill decision per channel, requires Zero Telegram approval.

### Loop deliverables (accumulated)

- 13 weekly reports
- 3 monthly reports
- `retrain_log.jsonl` (append-only)
- `kpi_timeline.csv` (13 KPI time series)
- Playbook minor updates v1.1, v1.2, ... if deltas justify
- Playbook v2.0 at day 90 — consolidated with lessons learned

---

## WR2 integration — three injection points

### 1. `backend/services/war_room/editorial_config.py` (new file, day 8)

Populated from playbook. Contains:

- `CADENCE_BY_CHANNEL`: posts/day, optimal hours WITA per channel.
- `FORMAT_MIX_BY_OBJECTIVE`: distribution from `05_format_matrix.json`.
- `PERSONA_WEIGHT`: which persona each draft targets.

### 2. `backend/services/council/deliberation.py` (modified)

Council v2 takes `persona: Persona` as input. Each LLM receives persona
profile + tone resonance matrix. Example: `persona=id_konsultan_kadin` →
tone `tecnico` + `analitico` weighted high, `ironico` zero, register Bahasa
formal, hook cites BKPM regulation.

### 3. `backend/services/measurer/m13_feedback_loop.py` (new, day 8)

Closes the loop currently open in WR2 design:

```python
class M13FeedbackLoop:
    async def collect_post_metrics(self, post_id: UUID, horizon: str): ...
    async def compute_delta_vs_prediction(self, post_id: UUID): ...
    async def retrain_weights_if_needed(self): ...
    async def notify_zero_if_threshold_breach(self): ...
```

Triggers: cron every 6h (collect), weekly (aggregate + retrain), monthly
(full retrain if delta >15%).

---

## Arsenal mapping

Zero paid APIs for Anthropic (hard rule). DeepSeek Reasoner the only
tolerated paid path (~$1 total over 100 days, logged in llm_cost_recorder).

| Module | Stack |
|--------|-------|
| **telemetry_bootstrap** | GSC sensor + GA4 sensor (existing) + NEW IG Graph API sensor (~4h dev) + Ahrefs MCP Brand Radar/SOV/AI citations + NEW Brevo stats client + CRM UTM fix |
| **empirical_ig** | IG Graph API + Playwright+Ollama qwen2.5vl:7b OCR fallback + Claude OAuth classify hook + Gemini 1M ctx classify tone (25 posts together) + DeepSeek correlation (~$0.05) |
| **benchmark_competitor** | Team member manual Google Sheet (IG 18 × 15, LinkedIn 10 × 10) + Playwright MCP TikTok scraping + Gemini 3.1 video analysis + Ahrefs social-media-* + keywords-explorer-* + site-explorer-organic-keywords |
| **literature_synthesis** | Gemini 3.1 Pro Deep Research grounded + NotebookLM research_start + existing `docs/x-research-april-2026/` q01-q60 |
| **consiglio_playbook** | Claude Opus 4.7 (coordinator) + Gemini 3.1 Pro 1M ctx (benchmark analyst) + Codex GPT-5.4 (telemetry engineer, M13 wiring) + DeepSeek Reasoner (red-team falsification, ~$0.30 total) + NotebookLM (authority validator) + Ollama qwen2.5vl:7b (batch classify 300 competitor screenshots overnight) + Ollama gemma4:26b (IT→ID translation for personas) |

### Cost breakdown

- Claude Max OAuth: $0 (subscription)
- Gemini 3.1 Pro: $0 (Google AI Ultra)
- Codex GPT-5.4: $0 (ChatGPT Plus)
- NotebookLM: $0 (Google free tier)
- Ahrefs MCP: $0 (subscription)
- Ollama local: $0 (self-hosted Pro)
- DeepSeek Reasoner: ~$0.30 Fase 0 + ~$1 across 90d Loop
- Team member: 25h (not cash)
- Dev time (Claude): ~8h for IG Graph API + Brevo stats + Grafana wiring

**Total out-of-pocket: ~$1.30 for 100 days.**

---

## Grafana dashboard (operational UI for Zero)

Single URL: `grafana.balizero.com/dashboard/social-sota` (new subdomain
or under prime.balizero.com). Tech: Grafana Cloud free tier + Postgres Fly
(reuses existing infrastructure).

Three main panels:

- **Lead pillar** — leads/month attributed to social, CR%, funnel view.
- **Authority pillar** — SOV, AI citations, DR, media pickup.
- **Audience pillar** — follower growth per channel, engagement rate, saves.

Plus: heatmap of optimal posting hours (updated weekly), top 10 posts by
engagement × persona target.

Alert thresholds: any pillar dropping >20% from baseline → immediate
Telegram alert + auto-toggle publisher OFF for degrading channel.

---

## Risk matrix

Ten scenarios, each with detector + mitigator. Nothing is "hope it doesn't
happen".

| # | Risk | Detector | Mitigator |
|---|------|----------|-----------|
| 1 | Team member doesn't finish scraping by day 6 | Gate 3 blocking + daily progress Telegram | Playwright automation for missing accounts |
| 2 | IG Graph API rate limit during telemetry | Sensor logs 429 errors | Exponential backoff + Ollama OCR screenshot fallback |
| 3 | Consiglio v1 persistent disagreement (Gate 6 fails) | DeepSeek falsification detects >40% disagreement | Flag claim as "disputed" in playbook, Zero final decision |
| 4 | Ollama vision classifier unreliable | 10% sample spot-check by Claude | Fallback Gemini 3.1 Pro vision + log accuracy delta |
| 5 | Playbook overfitting 25 own posts | Cross-validation empirical vs 270 competitor: predictions diverge >30% | Monthly retrain + external (benchmark) weight > internal (empirical) |
| 6 | M13 retrain loop unstable | retrain_log.jsonl: week-over-week weight variance >40% | Gradual update 20%/week max; disable retrain if variance persists |
| 7 | Publisher accidentally auto-on during 7d canary | PR #171 kill switch check fail-closed | Default `wr2_publisher_enabled=unset`, explicit ON required per channel |
| 8 | Pillar metric drops >20% from baseline | Grafana alert thresholds + M13 weekly report | Immediate Telegram + publisher auto-OFF for regressing channel + spec review |
| 9 | Off-brand content | Telegram Review Gate mandatory per publication | Already deployed PR #171. Canva edit URL review before approve |
| 10 | DeepSeek budget exceeds $2 | llm_cost_recorder tracking + soft limit | Hard cap: switch to Gemini free tier for red-team if cumulative >$2 |

### Telegram kill switches (Zero can send anytime)

- `/research pause` — stops Fase 0 or Loop
- `/research resume` — restarts
- `/publisher off [channel]` — disables publisher
- `/retrain off` — freezes `wr2_weights.json`
- `/personas reset` — reverts to day-9 manually-approved version
- `/cron disable [script]` — stops one of four cron scripts
- `/playbook freeze` — blocks automatic playbook updates

---

## Definition of Done

### Fase 0 done when ALL true

1. 12 artifact files in `research/sota-social-2026-v1/` (`00_` through `11_`)
2. 7 blocking gates all passed (days 1-10)
3. Grafana dashboard live + accessible
4. M13 feedback loop wired (tests green)
5. Zero approves `08_playbook.md` + `11_go_live_canary.md` via Telegram
6. Canary go-live: 1 IG post/day, publisher OFF (manual Review Gate approve only)
7. Cron scripts installed on Pro (launchd verified)
8. Telegram kill switch commands all tested

### Loop 90 days done when ALL true

1. 13 weekly + 3 monthly reports saved
2. Checkpoints 30/60/90 all approved by Zero
3. `playbook.md v2.0` produced (consolidated + lessons learned)
4. KPI dashboard: ≥2 of 3 pillars show +30% or more vs the day-1 baseline captured in `00_baseline.json`
5. Go/pivot/kill decision documented per channel
6. Draft spec for Cycle 2 (days 91-180) prepared

---

## Open questions (to resolve before or during plan-writing)

1. **Team member identification** — which team member will do 25h manual
   scraping days 2-6? Needs to be blocked from other work.
2. **Grafana instance** — new Cloud free account or extend existing? Check
   if Nuzantara has one already.
3. **IG Graph API OAuth** — Meta Business token: is the existing
   `@balizero0` Instagram Business connection's token still valid, or does
   a fresh OAuth flow need to run day 1?
4. **CRM UTM fix scope** — the CRO audit 2026-04-19 flagged "tracking CTA
   rotto". Fixing this is inside telemetry_bootstrap. Confirm scope
   acceptable (adds ~4h to day 1).
5. **Phyllo substitute accuracy** — Socialblade + NotJustAnalytics free
   tier give 3/5 demographic dimensions. Age/gender breakdown remains
   qualitative (NotebookLM persona inference). Acceptable or escalate to
   $30 Phyllo for 1 month?

---

## References

- `docs/war-room-2.0-design.md` — source for WR2 architecture
- `docs/x-research-april-2026/` — existing research corpus (q01-q60) on
  X/Twitter algorithms and video retention
- PR #171 — canva_renderer + Review Gate Canva URL + Publisher kill switch
- CLAUDE.md §8 (Deploy Architecture), §12 (AI Dispatch)
- CRO audit 2026-04-19 — UTM attribution broken, bait-and-switch bug

---

## Changelog

- 2026-04-22 — v1 initial design after 10-question brainstorm with Zero.

---

## Next step

Invoke `superpowers:writing-plans` to produce a detailed implementation
plan breaking this spec into bite-sized tasks with exact files, commands,
and tests.
