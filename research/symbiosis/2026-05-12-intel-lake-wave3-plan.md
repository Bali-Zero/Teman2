---
date: 2026-05-12
wave: 3
producers: imigrasi_monitor, pajak_monitor, oss_monitor
status: implemented
---

# Wave 3 — imigrasi/pajak/oss_monitor → Intel Lake

## Scope

3 cron-agent-python monitors that fetch from Indonesian government sites and feed `~/.intel_scraper/incoming/` (imigrasi+pajak) or Redis hash (oss). All run on Pro via cron. Output is fragmented across filesystem + Redis + Telegram with no single source of truth — the Intel Lake observation channel fixes this.

## Patches applied

All 3 files in `~/scripts/cron-agent-python/` (NOT tracked in git — these are operator-managed scripts on Pro). Pattern identical to Wave 2 t4_monitor/yt_monitor: best-effort enqueue to local SQLite outbox after the existing write completes.

### imigrasi_monitor.py

After `feed_file.write_text(...)` in `_write_intel_feed()`, call `intel_lake_outbox.enqueue` with:

- `producer_name=imigrasi_monitor`
- `source_domain=imigrasi.go.id`
- `language=id`, `jurisdiction=ID-national`
- `topic_tags=['visa','immigration', item.type]`
- `raw_payload={"pipeline":"intel_stage1", "type": item.type}`

### pajak_monitor.py

Same pattern in `_write_intel_feed()`:

- `producer_name=pajak_monitor`
- `source_domain=pajak.go.id`
- `topic_tags=['tax','pajak', item.type]`

### oss_monitor.py

Special case — writes to Redis HSET, not filesystem. Enqueue inside `_mark_seen()` per-announcement:

- `producer_name=oss_monitor`
- `source_domain=oss.go.id`
- `topic_tags=['pma','bkpm','oss','regulation','announcement']`
- `canonical_url` falls back to `oss://announcement/{redis_hash}` when URL missing

## Verification

Syntax check all 3 with `ast.parse`: PASS.

Smoke test enqueue from Python: enqueued row, stats={'pending': 1, 'delivered': 2, 'abandoned': 0} — outbox works.

## Volume estimate (24h)

- `imigrasi_monitor`: daily 06:00 — ~5-15 new items/day
- `pajak_monitor`: daily 08:00 — ~3-10 new items/day
- `oss_monitor`: every 2h 08:00-22:00 = 8 runs/day × ~5 items first scrape, ~0-2 deltas later → ~10-20/day average

Combined: ~20-50 observations/day. Drain worker (`~/scripts/intel-lake-outbox-drain.py`, every 60s) handles this volume easily.

## What goes in this PR vs what stays local

This PR contains ONLY:

- `research/symbiosis/2026-05-12-intel-lake-wave3-plan.md` (this file — design record)

The patches themselves live in `~/scripts/cron-agent-python/` which is NOT a git-tracked directory. Operator must `rsync` or manually copy to Mini if dual-host execution becomes the model. Currently Pro-only.

## Wave 4 prerequisite

Wave 4 (regulatory-watcher + peraturan_ingestion_trigger) starts when:

- Wave 1 backend deployed on Fly + migration 168 applied ← needs verification post-PR #621 merge
- Drain worker LaunchAgent bootstrapped (`com.balizero.intel-lake.outbox-drain.minute`)
- 24h observation of intel_lake_audit_log shows no 5xx and accepted>0 from one Wave 3 producer
