# M13 Measurer — Feedback Loop Config

**Purpose:** close the post → measure → retrain loop (spec §WR2 integration point 3).

**Module:** `apps/backend-rag/backend/services/measurer/m13_feedback_loop.py` (to be implemented per spec Task 22-27 of the implementation plan).

**Spec reference:** `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md` §WR2 integration + §Loop 90 days.

---

## Collection horizons

For every post published by WR2, M13 collects metrics at three horizons
post-publication (in UTC hours):

- **T+24h** — early signal (impressions, likes, comments, saves)
- **T+72h** — mid signal (reach stabilizes; video views mature)
- **T+168h (7d)** — final signal (long-tail saves/shares, attributed leads)

Collection triggered by cron `scripts/m13_collect_post_metrics.py` every 6h.

Persistence: `post_metrics_history` table (migration 128, already applied
2026-04-22 in Task 1). Append-only — each row = one (post, horizon, metric).

---

## Metrics per horizon

| metric_name | source | applies_to | notes |
|-------------|--------|------------|-------|
| likes | ig_graph | IG, IG Reels | |
| comments | ig_graph | IG, IG Reels | |
| saves | ig_graph | IG | Primary engagement signal 2026 (Mosseri confirmed) |
| reach | ig_graph | IG | |
| impressions | — | — | **Deprecated by Meta Graph v22+** — no longer collected |
| video_views | ig_graph | IG Reels | Fails on certain media_product_type — swallow 400 |
| reactions | linkedin | LinkedIn | |
| shares | linkedin | LinkedIn | |
| click_through | ga4 | any channel with UTM link | Uses GA4 event funnel_click |
| conversions_attributed | ga4 | any channel | Uses GA4 conversion events |
| session_duration_sec | ga4 | any channel | |

Note on `impressions`: removed from collection because Graph API v22+
returns `(#100) The Media Insights API does not support the impressions
metric for this media product type` — observed during Task 2 live smoke
2026-04-23. `IGPostMetrics` dataclass keeps the field with default=0 for
forward compatibility if Meta reinstates it.

---

## Retrain trigger conditions

### Weekly (`scripts/m13_weekly_report.py`, Sunday 06:00 WITA)

1. Compare per-channel engagement rate vs baseline in `00_baseline.json`.
2. If delta > +10% or < -10% for any channel on any horizon → retrain.
3. Retrain: re-run Consiglio v1 with updated empirical corpus → new
   `09_wr2_weights.json` with smoothing (20%/week max change per weight).
4. Append decision to `retrain_log.jsonl`.

### Monthly (`scripts/m13_monthly_retrain.py`, 1st of month 04:30 WITA)

- Re-scrape competitors (MCP browser stealth, or request Vino re-scrape)
- Re-run Ahrefs Brand Radar + AI citations (once plan upgraded)
- Re-infer personas from new comments
- Full playbook minor bump (v1.1, v1.2, ...) if delta > 15%

### Threshold breach (any time)

- If any pillar drops >20% from baseline → immediate Telegram alert +
  auto-toggle `wr2_publisher_enabled_{channel}=false` for the regressing channel.

---

## Weight smoothing — prevent oscillation

Each retrain produces desired weights; the actual update is:

```
new_weight = old_weight + (desired_weight - old_weight) * 0.2
```

This caps change at 20% per weekly step — prevents oscillation observed
in Risk #6 (spec). If `retrain_log.jsonl` shows week-over-week weight
variance > 40% for 3 consecutive weeks → M13 disables its own retrain
and notifies Zero. Zero must re-enable via `/retrain on` (Telegram).

---

## Baseline reference values (2026-04-23)

The pillar KPI deltas are measured against these live values:

| Pillar | Metric | Baseline | 90d target | Uplift |
|--------|--------|----------|------------|--------|
| Lead | leads_social_90d | 5 | 45/month | 9× |
| Lead | leads_social_share_pct | 1.5% | 12% | 8× |
| Lead | utm_coverage_pct | 100% (post-backfill) | maintain 80% | steady |
| Lead | cr_target_pct | N/A | 3.0% | baseline |
| Authority | linkedin_followers_net_new | 0 | +800 | launch |
| Authority | ai_citations_90d | N/A (Ahrefs plan insufficient) | 25 | from-zero |
| Authority | saves_per_post_median | ~44 (empirical 25-post median) | 60 | 1.4× |
| Audience | instagram_followers | 10,360 | +2,500 | 12% of current base |
| Audience | ig_reach_per_week | ~9,500 (empirical avg) | 120,000/week | 12× |
| Audience | newsletter_subscribers | 0 | 1,500 | from-zero |

Values pulled from `00_baseline.json`, `01_balizero_corpus.json`, and
`09_wr2_weights.json::pillar_kpi_targets`.

---

## Instrumentation

Every collection + retrain logs to
`apps/backend-rag/backend/services/observability/llm_cost_recorder.py`
(or equivalent) with tags:

- `sota_m13_collect` (every 6h)
- `sota_m13_retrain_weekly` (Sunday)
- `sota_m13_retrain_monthly` (1st)
- `sota_m13_threshold_breach`

---

## References

- Migration 128: `apps/backend-rag/backend/db/migrations_v2/128_m13_feedback.sql`
- Spec: `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`
- Plan: `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-loop.md`
  (Tasks 23-27 — M13FeedbackLoop core + collect cron + weekly + monthly
  + checkpoint)
- PR #171 — canva_renderer + publisher kill switch (safety net for canary)

---

## Stop condition (M13 self-disable)

If M13 observes runaway weight variance (>40% week-over-week for 3
consecutive weeks), it freezes `09_wr2_weights.json` and sends Zero a
Telegram notification:

> 🚨 M13 retrain frozen — weights oscillating >40% for 3 weeks.
> Claude weight history in `retrain_log.jsonl`. Zero must review and
> reply `/retrain on` to re-enable.

This is the M13-side enforcement of Risk #6 mitigation.
