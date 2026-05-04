# Sprint 6 — events_outbox prune cron

**Goal**: close the audit P0-2 phase 3 partial — install a daily prune
LaunchAgent on Pro that removes consumed `events_outbox` rows older than
30 days, preventing unbounded table growth.

## Background

The `events_outbox` table (migration 144, 2026-04-29) backs the EventBus
durability layer. Every `pg_notify` triggered by a DB write also lands a
row in `events_outbox`, with `consumed_at` set when the listener
acknowledges. Phase 1+2 (Sprint 3 W2) made the writes atomic. Phase 3
(this sprint) handles the cleanup.

Without pruning, the table accumulates. Audit snapshot 2026-05-05 02:00
WITA showed 3,512 rows after 5 days of operation, dominated by
`cell_pulse_observed` heartbeats (3,071 rows = 87 %). At that rate the
table reaches 250 k rows/year — large enough to slow scans on the
partial indexes that the EventBus replay path uses.

## What this sprint adds

Three artifacts on Pro:

| Path | Purpose |
|------|---------|
| `scripts/events_outbox_prune.py` | Python entry-point — calls `outbox.prune_consumed(conn, older_than_days=30)`. Reuses the helper, no copy-paste. |
| `scripts/events_outbox_prune_wrapper.sh` | LaunchAgent shim — sources `~/.nuzantara-secrets.env` (mode 0600) for `DATABASE_URL_LOCAL`, picks the venv Python, exec's the entry-point. |
| `infra/launchagents/com.matagaruda.events-outbox-prune.plist` | Daily 04:30 WITA schedule (`KeepAlive=false`, log to `~/logs/`, no inline secrets). |

Plus 17 unit tests in
`apps/backend-rag/backend/tests/scripts/test_events_outbox_prune.py`
covering script structure, wrapper env handling, and plist hardening
contracts.

## Schedule rationale (04:30 WITA)

| Slot | Pre-existing job | Why we don't collide |
|------|------------------|----------------------|
| 00:30 WITA | `com.balizero.indexing-sweep.daily` | Different table |
| 03:00 WITA | `auto-sentinel` | Different table |
| 04:13 WITA | `com.matagaruda.invalidation-sweep` | **Important — this writes to events_outbox** via the trigger on asset_provenance UPDATE. Must finish BEFORE we prune. 17-minute gap is generous. |
| **04:30 WITA** | **events-outbox-prune** | This sprint |
| 06:00 WITA | drive-watchdog | Different concern |

## Deploy procedure (Pro-only)

```bash
# Stage Pro-local copies (independent of any worktree)
mkdir -p ~/scripts/mata_garuda
cp scripts/events_outbox_prune.py ~/scripts/mata_garuda/
cp scripts/events_outbox_prune_wrapper.sh ~/scripts/mata_garuda/
chmod 0755 ~/scripts/mata_garuda/events_outbox_prune*

# Install plist (mode 0444 — cf. cicatrix P0-3 secrets-leak hardening)
chmod u+w ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist 2>/dev/null || true
install -m 0444 infra/launchagents/com.matagaruda.events-outbox-prune.plist \
    ~/Library/LaunchAgents/

# Bootstrap
launchctl bootstrap gui/$(id -u) \
    ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist

# Verify schedule
launchctl print gui/$(id -u)/com.matagaruda.events-outbox-prune | grep -E "Hour|Minute|next"

# Smoke-test (manual fire — should be no-op for ~25 days post-mig-144)
launchctl kickstart gui/$(id -u)/com.matagaruda.events-outbox-prune
tail -f ~/logs/events-outbox-prune.stdout.log
```

## Rollback

```bash
launchctl bootout gui/$(id -u)/com.matagaruda.events-outbox-prune
chmod u+w ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist 2>/dev/null
rm ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist
```

The script + helper are read-then-DELETE; rollback is just "stop
running it". No schema changes. Manually remove the wrapper / Python
files from `~/scripts/mata_garuda/` if you need a clean slate.

## Operational notes

- **First-time eligibility**: until 2026-05-29 (≥30 days post mig-144
  deploy on prod), every run logs `eligible_before=0 deleted=0`. That
  is the expected steady state — the cron is preventive infrastructure.
- **Unconsumed rows are NEVER pruned**: phase 1's contract was
  "auto-ack on dispatch_fn return"; phase 3 honors it by leaving
  `consumed_at IS NULL` rows alone. Future per-handler ack (phase 4)
  may reduce the unconsumed pool.
- **Concurrent invalidation-sweep**: 04:13 WITA writes UPDATE-trigger
  rows to events_outbox. By 04:30 those writes are committed but their
  `consumed_at` is still NULL (the listener ack happens at next event
  dispatch, not on insert). They are NOT pruned because of the
  `consumed_at IS NOT NULL` filter.
- **Row count growth telemetry**: each run logs
  `events_outbox remaining rows: <N>` to `~/logs/events-outbox-prune.stdout.log`.
  Plot `N` over time to detect runaway growth.
