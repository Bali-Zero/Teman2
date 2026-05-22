---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W16 Pro<->Mini Redis split-brain detector + diagnosis
sources: 4
---

# W16: Pro<->Mini Redis split-brain detector

## Context

Loop iteration 16. W15 cap-gate shipped (`a7840334d`) but never fired
in production logs. Investigation traced root cause to a DIFFERENT
issue: **producer/consumer Redis host mismatch** creating silent
split-brain.

## Discovery sequence

1. **Lag dashboard normal**: only ner=73 pending, others clean.
2. **nlm-feeder cron processed=0** across 5 fires — gate not exercised.
3. **Force kickstart nlm-feeder**: still processed=0.
4. **Suspicion**: worker not reaching items. Probed both hosts:

| Stream          | Pro Redis (127.0.0.1)        | Mini Redis (100.93.236.6) | Drift    |
| --------------- | ---------------------------- | ------------------------- | -------- |
| garuda:enriched | 4337 entries, last 11:38     | 1145 entries, last 02:01  | **9.6h** |
| garuda:alerts   | 290 entries, last 2026-05-13 | 250 entries, last 11:00   | **210h** |
| garuda:raw      | (same)                       | (same)                    | OK       |

5. **Worker config**: nlm-feeder plist has `GARUDA_REDIS_HOST=100.93.236.6`
   per 2026-05-06 cicatrix → reads ONLY Mini Redis. Misses Pro's 4337
   intel_scraper items entirely.
6. **W10 lag monitor blind**: probes only the configured single host.
   Never compares Pro vs Mini. Architecturally unaware of split-brain.

## Root cause

The 2026-05-06 cicatrix fixed worker `redis-cli` to honor
`GARUDA_REDIS_HOST` env var, expecting all producers + consumers on
same host. Real world drifted:

| Worker                          | Host             | Writes to                       |
| ------------------------------- | ---------------- | ------------------------------- |
| sentinel.daily (Mini)           | Mini             | Mini Redis (garuda:raw, alerts) |
| intel_scraper (Pro)             | Pro              | Pro Redis (garuda:enriched)     |
| normalizer/ner/classifier (Pro) | Pro              | Pro Redis (no env = localhost)  |
| nlm-feeder cron (Pro)           | Pro but env=Mini | reads **Mini** Redis only       |

`nlm-feeder` reads from Mini → sees sentinel's rss/arxiv but misses
intel_scraper's web scrapes, kompasiana, travel&tourworld, etc.
Worse: scorer-on-Pro's alerts haven't reached the consumer for 9 days.

## Fix shipped (diagnostic-only)

`apps/mata-garuda/scripts/check_redis_split_brain.py`:

- Probes 3 streams (`garuda:raw`, `garuda:enriched`, `garuda:alerts`)
  on both Pro + Mini in parallel.
- Compares `last-generated-id` timestamps.
- Emits one WARNING JSON line per split stream to stderr (matches W10
  lag-monitor format for downstream alert pipelines).
- Exits 1 if drift > 1h on any stream, 0 if all in sync OR one host
  unreachable.

**Live empirical 2026-05-22 11:35 WITA**:

```json
{"level":"WARNING","tag":"redis-split-brain","stream":"garuda:enriched","stale_host":"mini","fresh_host":"pro","drift_h":9.6,"stale_length":1145,"fresh_length":4337}
{"level":"WARNING","tag":"redis-split-brain","stream":"garuda:alerts","stale_host":"pro","fresh_host":"mini","drift_h":210.1,"stale_length":290,"fresh_length":250}
```

Two real split-brains detected: enriched drift 9.6h (Pro fresh, Mini
stale), alerts drift 210h (Mini fresh, Pro 9 days behind).

## Tests

`apps/mata-garuda/tests/test_check_redis_split_brain.py` (7 tests):

- Constants locked (hosts, threshold, streams)
- `host_stream_state` parses XINFO STREAM output correctly
- Returns None on missing stream + on unreachable host
- `detect_split_brain` emits alert when drift > threshold
- Silent when in sync (<5min)
- Silent when only one host alive (not split, just down)

**7/7 PASS** in 0.03s.

## Root-cause fix DEFERRED to Antonello

Diagnostic alone doesn't unblock the production NLM feed. Four options
for the actual fix:

### Option A — Two-feeder (operational, low-risk)

Add second nlm-feeder LaunchAgent on Pro that reads **Pro Redis**
(unset GARUDA_REDIS_HOST). Both feeders run independently; each Redis
has its own `nlm_feeder` consumer group. Solves intel_scraper-on-Pro
path but doubles cron count + log volume.

### Option B — Centralize on Pro

Kill sentinel.daily on Mini, move to Pro. Single Redis source of truth
on Pro. Loses Mini's role as a quiet long-running worker host. Requires
Mini cron rewrite + offset migration.

### Option C — Replicate

Redis MASTER/REPLICA Pro→Mini (or vice versa). Eliminates split-brain
at the cost of one-way data flow + Redis 7 configuration + ACL
re-engineering.

### Option D — Status quo + alerting

Keep split-brain by design. Wire W16 detector into hourly cron with
Telegram alert. Operator manually decides when intel_scraper items
need to be fed (e.g., on-demand Pro-feeder kickstart).

**Recommendation**: Option A is the smallest delta with highest unblock
value. Two plists, 30 lines of bash wrappers, no architectural rework.
Defer Option C/B until traffic volume forces it.

## Cross-tree gotcha (no recurrence this iteration)

Edit + cross-tree sync worked cleanly via worktree absolute paths +
explicit `cp worktree → main`. W14/W15 lessons internalized.

## Operator runbook

```bash
# On-demand split-brain check
$ python3 ~/Desktop/nuzantara/apps/mata-garuda/scripts/check_redis_split_brain.py
# exit=0: all in sync (silent stdout JSON report)
# exit=1: drift > 1h on one or more streams (alerts on stderr)

# Per-host stream snapshot for manual investigation
$ redis-cli -h 127.0.0.1 XINFO STREAM garuda:enriched | head -10
$ redis-cli -h 100.93.236.6 XINFO STREAM garuda:enriched | head -10

# Pro-feeder one-shot test (would solve Pro-stale enriched lag)
$ GARUDA_REDIS_HOST= /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python \
    /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_nlm_feeder_stream.py
```

## Open questions (deferred)

- **Root-cause fix Option A/B/C/D**: needs Antonello sign-off.
- **garuda:alerts Pro stale 9 days**: separate root cause from W16.
  scorer-on-Pro must have stopped writing to Pro's alerts stream, OR
  regulation_alert_agent was moved to Mini. Producer audit needed.
- **W17 candidate**: launchd plist for split-brain detector (Telegram
  alert on stderr non-empty).
- **W14/W15/W13 deferred items**: still all open.
- **Wave 16-commit branch PR readiness**: noted.

## Sources

1. W15 cicatrix open questions (commit `a7840334d`)
2. `redis-cli XLEN garuda:enriched` on both Pro + Mini hosts 2026-05-22
3. `~/Library/LaunchAgents/com.matagaruda.nlm-feeder-stream.hourly.plist`
   (env GARUDA_REDIS_HOST=100.93.236.6)
4. `ssh mini "launchctl list | grep matagaruda"` showing
   sentinel.daily, intel-bridge.daily, ner-worker, normalizer on Mini
