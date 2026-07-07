# IG Insights — Insufficient Data — 2026-06-23

**Run**: weekly manual, 2026-06-23 (8th consecutive weekly run)
**Data window**: 2026-03-25 to 2026-06-23 (90 days)
**Action**: STOP. Minimum attribute-dimension requirements not met. No analysis run.

---

## Threshold check

| Requirement | Value | Threshold | Status |
|---|---|---|---|
| Published carousels with likes >= 1 in window | **14** | >= 10 | PASS |
| Distinct domains tagged | **0** | >= 3 | FAIL |
| Distinct tone registers tagged | **0** | >= 3 | FAIL |
| Distinct layout families tagged | **0** | >= 2 | FAIL |

Three of four minimum requirements fail. Analysis cannot proceed without attribute segmentation.

---

## What changed this week

Previous 7 runs (2026-05-10 through 2026-06-22) reported N=0 carousels with engagement metrics. This week N=14, because the Graph API backfill ran today (2026-06-23). All 14 items carry engagement_metrics.source = graph_api_backfill_2026-06-23. The engagement data now exists; the blocking gap is attribute tagging, not data scarcity.

---

## Raw engagement summary (no segmentation possible)

N = 14 carousels published 2026-04-06 through 2026-06-18.

| Stat | Likes | Save/Like |
|---|---|---|
| Mean | 162.0 | 1.00 |
| Median | 37 | 1.31 |
| Min | 12 | 0.20 |
| Max | 1070 | 1.84 |

share/like and engaged/reach cannot be computed: comments are present but shares are absent from the backfill payload.

Sorted by likes (descending):

| Date | Likes | Saves | Reach | Save/Like |
|---|---|---|---|---|
| 2026-04-29 | 1070 | 217 | 30357 | 0.20 |
| 2026-05-18 | 745 | 239 | 34011 | 0.32 |
| 2026-05-08 | 108 | 63 | 5956 | 0.58 |
| 2026-06-02 | 75 | 98 | 4532 | 1.31 |
| 2026-05-22 | 56 | 86 | 4775 | 1.54 |
| 2026-05-11 | 44 | 13 | 2784 | 0.30 |
| 2026-04-09 | 43 | 57 | 2711 | 1.33 |
| 2026-04-06 | 31 | 57 | 1835 | 1.84 |
| 2026-04-14 | 25 | 15 | 1811 | 0.60 |
| 2026-05-05 | 20 | 23 | 1404 | 1.15 |
| 2026-05-02 | 13 | 7 | 855 | 0.54 |
| 2026-06-15 | 13 | 19 | 1013 | 1.46 |
| 2026-06-18 | 13 | 19 | 860 | 1.46 |
| 2026-04-13 | 12 | 17 | 1115 | 1.42 |

Observations (not amendments — attribute segmentation absent):

1. Two outliers: April 29 (1070 likes, 30K reach) and May 18 (745 likes, 34K reach). Both are 7-29x the corpus median on likes but produce Save/Like ratios of 0.20 and 0.32 — well below the internal baseline threshold of >= 0.5. These look like viral-but-low-utility carousels by the empirical-metrics framework. Without domain/tone/layout tags, cause is unidentifiable.

2. The 12 non-outlier carousels have a mean Save/Like of 1.21, which exceeds the internal gold-standard mean of 0.72 (8-carousel reference set). But this cannot be credited to any design attribute without tags.

3. Mean corpus Save/Like (1.00) beats the internal baseline for 5 of 8 reference carousels. The regime is not broken; the learning loop is blocked by missing tagging.

---

## Blocking path

All 45 published carousels in the queue have domain = null, tone_register_primary = null, layout_family_primary = null. The attribute tagging step (Damar manual review queue) has not been executed for any published carousel.

To unblock analysis on the next weekly run (2026-06-30):

1. Damar tags the 14 in-window carousels with domain (regulatory / visa / tax / property / environmental), tone_register_primary, layout_family_primary. Minimum viable: 10 tagged with >= 3 distinct domains.
2. _import-damar-tags.py propagates tags back into the queue JSON.
3. No code changes required. Queue and scraper are functional; only the tagging layer is absent.

Secondary unblock: wr2-episodic.db carousel_runs table has 0 rows. If WR2 pipeline populates this table per run, it provides structural attributes (hero_count, body_word_count, critic verdicts, layout_families_used) without depending on manual tagging. Current state: pipeline does not write to the DB.

---

## Sources read this run

- human-review-queue.json: 62 total items, 45 published, 14 with likes >= 1 in 90-day window.
- wr2-episodic.db: 0 carousel_runs (table empty).
- past/*/metadata.json: 64 historical carousels. Domain: regulatory(30), visa(16), property(12), health(4), unknown(2). Tone: analitico(16), militante(14), pedagogico(12), ironico(12), rituale(4), tecnico(2), poetico(2), unknown(2). Layout: cover-photo(32), photo-headline-yellow-sub(16), dark-status-list(8), statement-bomb(6), unknown(2). No engagement data.
- _empirical-metrics-2026-05-12.md: 8-carousel gold standard. Internal baseline read.
- _external-bench-2026-06.md: SOTA patterns June 2026. External baseline read.

No Gemini call issued (attribute threshold not met).
