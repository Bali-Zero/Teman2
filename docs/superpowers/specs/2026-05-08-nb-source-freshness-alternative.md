# NB Source Freshness — Alternative Timestamp Source

**Date:** 2026-05-08
**Status:** Design — implementation pending sub-session
**Owner:** Zero (decision) + Claude Opus 4.7 (design)
**Tracking:** Mitochondrial Monitor `source_freshness_age_days` permanently NULL

## Problem

`apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/nlm_freshness.py::fetch_source_freshness_age_days`
exists to populate the `source_freshness_age_days` column in
`~/.agent/nb-mitochondrial/metrics.db`. It calls `nlm notebook get <uuid> --json`
and tries to compute median age from `sources[].updated_at` or `created_at`.

**Empirical reality (2026-05-08):** the `nlm` CLI returns
`{"value": {"sources": [{"id": "<uuid>", "title": "<filename>"}, ...]}}`
with **no timestamp fields per source**. The function returns `None` on every
real call. The DB column is permanently NULL.

This is one of the 5 inputs to the SENESCENT tier classifier (FASE 2 spec
§7.2). With it permanently NULL, the classifier loses one signal of "stale
content" and may misclassify NBs as IDLE when they should be SENESCENT.

## Constraints

- **No paid API** (CLAUDE.md hard rule). NLM cloud has no public timestamp
  endpoint we haven't already tried.
- **OSINT blindato** (Mata Garuda CLAUDE.md §1.2). Cannot query external services
  for source timestamps; must derive from data we already write/touch.
- **CLI-only** for any LLM-based extraction (Mata Garuda CLAUDE.md §1.1).
- **Best-effort semantics** — `None` is acceptable, partial is acceptable.
  We're not signing tax forms with this number.

## Candidates

### Option A — `knowledge` table with type='nlm_fed' in KB SQLite

**Empirical schema verified 2026-05-08** (ran live against `~/Desktop/nuzantara/apps/mata-garuda/data/knowledge.db`):

```sql
CREATE TABLE knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,        -- 'nlm_feeder' for feed events
    type TEXT NOT NULL,         -- 'nlm_fed' for feed events
    content TEXT NOT NULL,      -- "nlm_fed <url>"
    source TEXT,                -- the URL (or hash)
    confidence REAL DEFAULT 0.5,
    created_at TEXT DEFAULT (datetime('now')),  -- THIS is our timestamp
    ...
);
```

Sample row (live):
```
nlm_feeder | nlm_fed | http://arxiv.org/abs/2604.07350v1 | nlm_fed http://arxiv.org/abs/2604.07350v1 | 2026-04-09 23:57:33
```

**Total nlm_fed entries (live):** 853 rows.

**Critical gap discovered:** the row contains the source URL but **NOT** the
target NB UUID. `nlm_feeder` writes one row per fed URL globally, with no
back-pointer to which NB received it. So we can't directly query
`WHERE uuid = ?` like the original sketch assumed.

**Bridge needed: URL → NB UUID mapping.** Three sub-options:

- **A1** — Inspect `nlm_feeder.py` to see if the routing decision (which NB
  to feed) is logged elsewhere. If yes, a JOIN gives us the answer. If no,
  this option is dead.
- **A2** — Re-derive routing from scoring: re-run the `infer_domain` /
  scorer keyword fast-path on each fed URL to recover its target NB. Costs
  ~1ms per URL via keyword regex (no LLM call). For 853 rows: <1s.
  Risk: scorer rules drift over time, re-derivation may misclassify some
  historical entries.
- **A3** — Add an `nb_uuid` column to `knowledge` table going forward, and
  treat historical entries as "unknown destination" → freshness only
  computable for post-migration sources. 7-30 days of warmup before
  freshness signal becomes useful.

**Pro:**
- 853 historical rows + new ones at hourly cadence.
- Accurate to the second.
- One DB query (cheap).

**Con:**
- A1 likely dead-end (need to verify in nlm_feeder.py source).
- A2 introduces re-derivation noise.
- A3 has 7-30d warmup.

**Coverage estimate (post-bridge):** ~60-80% of NB-INTEL sources (depends
on bridge accuracy). ~10-30% of non-INTEL.

### Option B — Redis `garuda:alerts` stream entry IDs

**What:** Redis stream entry IDs are millisecond timestamps. The
`nlm-feeder-stream` worker reads from `garuda:alerts` and feeds whatever
makes it past the dedup filter to NotebookLM. We can scan the stream
backwards from `+` and bucket entry IDs by `nb_target` (or by URL → uuid
lookup if nb_target isn't in the entry).

**Pro:**
- Covers items the moment they enter the pipeline (slightly earlier than
  `nlm_fed` write time).
- Stream is on Mini Redis post-2026-05-06; cross-node access via
  `GARUDA_REDIS_HOST=100.93.236.6`.

**Con:**
- Stream has retention cap (we don't know exact MAXLEN — need to check).
  Old sources fed >7d ago may already be evicted.
- Mapping entry → NB requires reading the entry payload and decoding the
  same field that the feeder uses; more code than Option A.
- Mini→Pro cross-node call adds 62ms RTT per query (vs local SQLite for A).

### Option C — bali-intel-scraper `articles` publish_date

**What:** When `nlm-feeder-stream` feeds a source URL that originated from
`bali-intel-scraper`, the article record in
`apps/bali-intel-scraper/data/articles.db` has a `publish_date` (the actual
article publication date, not feed time).

**Pro:**
- Closest semantic match to what `source_freshness_age_days` is supposed to
  mean: how old is the *content* of this NB?
- Independent of pipeline timing.

**Con:**
- Only covers intel-scraper sources (~60-70% of NB-INTEL-Immigration,
  ~20-40% of others, 0% of research NBs).
- Requires URL-matching across two databases.
- `publish_date` is sometimes the scrape date, not the article date, when
  the page lacks structured metadata. Noise.

### Option D — drop the column

**What:** Remove `source_freshness_age_days` from `nb_metrics` schema, simplify
classifier to use the other 4 signals (read_freq_7d, read_freq_30d,
skill_derivation_count, downstream_cite_rate), document that "freshness as
measured by source recency is not currently tracked".

**Pro:** Honest about what we measure. No code complexity.

**Con:** Lose one classifier signal. Upstream classifier rules in spec §7.2
may need re-tuning to avoid biasing toward "any NB with high read_freq is
healthy regardless of content staleness".

## Recommendation (revised post-empirical)

**Option A3 — add `nb_uuid` column to `knowledge` table going forward + Option D for the current 7 NBs until warmup completes.**

Why revised:
- A1 verified DEAD: empirical inspection of `nlm_feeder.py` lines 303 and 380-394 confirms
  `kb.store(agent='nlm_feeder', type='nlm_fed', content=marker, source=url)` — there is
  **no `nb_uuid` or `nb_key`** in the row. We have URL + timestamp, no bridge to NB.
- A2 re-derivation via scorer: feasible but introduces noise (scorer rules drift).
  Reserve as fallback only for backfilling historical 853 rows if A3 proves needed
  for them too.
- A3 is the cleanest forward path: 1 column, 1 migration, modify the 2 `kb.store`
  call-sites in `nlm_feeder.py` to pass `nb_key` (already known at that scope). 7 days
  warmup before classifier sees real data, then it's accurate forever.
- Option D (drop column) for the warmup window — set `source_freshness_age_days = NULL`
  consistently and tune the SENESCENT classifier to ignore-None instead of error-None.

Implementation order:
1. (PR-A, this PR) — fix `info → get` so the cookie/auth check works (DONE).
2. (PR-B, sub-session next) — A3 column add + 2 callsite changes + classifier
   `ignore_None` policy in run.py.
3. (Background) — 7d warmup, then non-NULL freshness data starts populating.
4. (Optional, +30d later) — A2 backfill of historical 853 rows if classifier
   wants pre-warmup data; ship only if classifier proves to need it.

## Sub-session brief (next session)

```
Goal: implement Option A3 (nb_uuid column going forward) + classifier
ignore-None policy.

Files to touch:
  - apps/mata-garuda/mata_garuda/runtime/knowledge.py
    (add nb_uuid: str | None = None param to store())
  - apps/mata-garuda/data/knowledge.db (live)
    via Python migration: ALTER TABLE knowledge ADD COLUMN nb_uuid TEXT
  - apps/mata-garuda/mata_garuda/workers/nlm_feeder.py L303 + L380-394
    (pass nb_key → resolve to UUID via NLM_NOTEBOOKS map → kb.store(..., nb_uuid=resolved))
  - apps/mata-garuda/mata_garuda/scripts/nb_monitor/collectors/nlm_freshness.py
    (replace fetch_source_freshness_age_days body to query knowledge table by nb_uuid)
  - apps/mata-garuda/mata_garuda/scripts/nb_monitor/run.py L222-224 + classifier
    (treat None → "freshness signal not available" without error,
     SENESCENT classifier ignore-None instead of None→stale)
  - apps/mata-garuda/tests/...

Empirical pre-checks (60s, run before designing implementation):
  1. Verify nb_key → uuid map exists at spawn time:
     grep -n "NLM_NOTEBOOKS\s*=" apps/mata-garuda/mata_garuda/workers/nlm_feeder.py
     (if it's a dict literal: easy. If imported from elsewhere: trace to source.)
  2. Verify ALTER TABLE works on live DB without locking out feeder:
     test on a backup copy first — knowledge.db is hot during feeder cron.
  3. Verify classifier reads source_freshness_age_days:
     grep -n "source_freshness_age_days" apps/mata-garuda/mata_garuda/scripts/nb_monitor/
     If classifier doesn't actually use it yet (FASE 2 spec promised, but
     may not be wired) — option D becomes preferable. Confirm with Zero.

Output: PR-B `feat(nb-monitor): persist nb_uuid in knowledge.db nlm_fed
rows + classifier ignore-None freshness`, auto-merge L2.

Done when:
- Migration applied live (alter column)
- nlm_feeder writes nb_uuid on next cron tick (verify: SQL query on
  type='nlm_fed' shows non-NULL nb_uuid for new rows)
- monitor cron next run computes freshness for any NB with ≥1 new
  row post-migration
```

## Out of scope

- Re-classifier tuning (separate PR after we have ≥7 days of non-NULL data
  to see actual distribution)
- Adding TCC bridge if launchd-spawned shell can't access `knowledge.db`
  (tackle if it manifests; sub-session uses same monitor plist context)
- Mini-side `nlm_fed` mirror (Mini doesn't write to nlm_fed; pipeline runs
  on Pro)
