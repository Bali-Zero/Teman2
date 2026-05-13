# Intel Lake outbox drainer (Pro-local, Wave 4)

Pro-local cron LaunchAgent that drains the SQLite outbox
(`~/.intel-lake-outbox.db`) to Fly endpoint `/api/intel/lake/observations-batch`.

**Status**: tracking in repo from 2026-05-13 (this PR). Was Pro-local-only
since Wave 4 deploy. Versioning here preserves both the helper module
(`intel_lake_outbox.py`) used by producers AND the cron driver
(`intel-lake-outbox-drain.py`).

## Deploy paths on Pro

| File | Deployed path |
|---|---|
| `intel-lake-outbox-drain.py` | `~/scripts/intel-lake-outbox-drain.py` |
| `intel_lake_outbox.py` | `~/scripts/intel_lake_outbox.py` |

LaunchAgent: `~/Library/LaunchAgents/com.balizero.intel-lake.outbox-drain.minute.plist`
(StartInterval 60s).

## 2026-05-13 fix — Telegram alert on rejected items

The drainer's original Wave 4 design unconditionally marked all rows
`delivered_at=NOW()` regardless of backend `rejected` count, trusting
the `intel_lake_audit_log` table on Fly to record rejections. That
trust was misplaced: a regression on 2026-05-12 in
`apps/backend-rag/backend/services/intel/intel_lake_service.py:155`
(asyncpg cannot auto-bind ISO 8601 string to timestamptz) caused
every item with `published_at` to return HTTP 500. Producers
(`regulatory_watcher`, `intel_radar`) had **zero visibility** because
the drainer reported success.

Fix (this PR): when `rejected > 0` in the backend response, the
drainer now emits a Telegram alert (debounced 30min via
`~/logs/intel-lake-outbox-drain.alert-state.json`). The
`mark_delivered(ids)` call is preserved — we still avoid infinite
retry loops — but the silent-drop blind spot is closed.

The server-side root cause is fixed in the same PR in
`intel_lake_service.py` via a new `_parse_iso_datetime()` helper.

## Cross-references
- Pro-local nb-pusher (downstream consumer): `scripts/intel-lake-nb-pusher-a2/`
- Pro-local router (upstream classifier): `scripts/intel-lake-router-a2/`
- Discovery memo:
  `~/.claude/projects/-Users-nuzantara/memory/discovery_intel_lake_published_at_silent_drop_2026_05_13.md`
