# WR2 Supervisor — Event-Driven Pipeline Orchestrator

**Status:** v1, deployed 2026-04-26
**Code:** `scripts/wr2_supervisor.py`
**Plist:** `infra/launchagents/com.balizero.wr2.supervisor.plist`
**DB trigger:** migration `138_wr2_status_notify.sql`
**Reviewers:** Codex GPT-5.5, Gemini 3.1 Pro, DeepSeek Reasoner

---

## What it replaces

Six chained `launchd` plists scheduled at fixed WITA minutes (05:10..05:16) used to fire WR2 pipeline stages back-to-back. This was a chain-as-cron antipattern: a slow stage made the next one no-op, latency was 24h, throughput capped at one carousel per day.

After this refactor:
- `topic-selector` keeps its 05:10 cron as the **daily entry point**.
- The other five stages (`draft-generator`, `image-generator`, `fact-extractor`, `fact-checker`, `canva-apply`) lose their `StartCalendarInterval` and run **only** when the supervisor `launchctl kickstart`s them in response to a status transition.
- Latency: ~10–20 min topic→`rendered` (Canva-API variance dominates).
- Throughput: bounded by Gemini Ultra rate limits (~10 drafts/day practical).

## How it works

```
INSERT or UPDATE OF status ON war_room_drafts
        │
        ▼ (Postgres trigger)
   NOTIFY wr2_status_change
        │
        ▼ (asyncpg LISTEN via local pg-proxy)
  wr2_supervisor daemon
        │
        ▼ (per-draft asyncio.Lock + per-(draft, target) dedup
        │    + re-read DB to catch stale payloads)
  launchctl kickstart com.balizero.wr2.<next-stage>
        │
        ▼ (worker bulk-SELECTs all matching drafts and processes them)
   row.status updated → next NOTIFY → cascade continues
```

## State machine

| Transition | Triggers |
|------------|----------|
| `* → briefed` | `draft-generator` |
| `briefed → briefed_facted` | `draft-generator` |
| `briefed/briefed_facted → drafts` | `image-generator` |
| `drafts → drafts_imaged` | `fact-extractor` |
| `drafts_imaged → drafts_imaged_facted` | `fact-checker` |
| `drafts_imaged_facted → drafts_imaged_checked` | `canva-apply` |
| `* → rendered` | Telegram alert (review gate) |
| `* → fact_check_failed` | Telegram alert (manual triage) |
| `* → rejected` | log only |

`*` matches any prior status, including `NULL` for INSERT events.

## Reconciliation

Postgres `NOTIFY` is fire-and-forget: any messages emitted while the supervisor is down (Mac sleep, crash, network drop) are **lost**. The supervisor compensates with two reconciliation passes:

1. **Startup scan** — runs once when the daemon boots. Queries non-terminal drafts not updated in `WR2_RECONCILE_STALE_MIN` (default 30) minutes and re-kicks the right stage. Catches the "Mac slept overnight" case immediately on wake.
2. **Periodic sweep** — same query every `WR2_RECONCILE_INTERVAL_SEC` (default 300, i.e. 5 min) while the daemon runs. Belt-and-suspenders against transient connection drops.

Reconciliation respects the per-(draft, target) dedup set, so it never double-kicks a draft already dispatched in the last few seconds.

## Why no `launchctl kickstart -k`

The `-k` flag kills any current instance of the service before starting a new one. In a fast cascade (multiple drafts cascading through the same stage minutes apart), `-k` would abort an in-flight LLM call mid-flight. Workers always drain ALL pending drafts via a bulk `SELECT WHERE status = ...`, so a kickstart on an already-running stage is a benign no-op (rc=113 from `launchctl`, which we treat as success).

## Why per-draft locks

Postgres delivers `NOTIFY` in commit order on the same connection, but `_on_notification` schedules each payload as `asyncio.create_task` — those tasks run concurrently. Without serialisation, two transitions for the **same draft** could be processed out of order and kickstart the wrong next stage. The per-`draft_id` `asyncio.Lock` enforces in-order processing per draft while still allowing **different** drafts to cascade in parallel.

## Why per-(draft, target) dedup

The v1 plan used a per-plist cooldown ("don't kickstart the same plist twice within 5s"). Reviewers (Codex, Gemini, DeepSeek) all flagged the same bug: it would silently drop legitimate kickstarts for **different** drafts that happened to target the same plist within the cooldown window. Replaced with a per-`(draft_id, target_label)` dedup set: only exact duplicates are dropped.

## Environment

The supervisor is sourced via `~/.openclaw/bin/wr2/wr2-script-wrapper.sh`, which loads `~/.nuzantara-secrets.env` and `~/.nuzantara-backend-secrets.env`. Required:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | local pg-proxy DSN (port 15432 → Fly Postgres) |
| `TELEGRAM_BOT_TOKEN` | optional, review notifications |
| `TELEGRAM_OWNER_CHAT_ID` | optional, Zero's chat |
| `WR2_SUPERVISOR_DRY_RUN` | optional, `true` to log without kickstarts |
| `WR2_RECONCILE_INTERVAL_SEC` | optional, default 300 |
| `WR2_RECONCILE_STALE_MIN` | optional, default 30 |

## Observability

- **Log file**: `~/logs/wr2_supervisor.log`
- **launchd stderr**: `~/logs/wr2_supervisor.launchd.err.log`
- **Telegram alerts** on: `rendered`, `fact_check_failed`, kickstart failures (non-113 rc), supervisor startup (with reconcile count)
- **Healthcheck**: `launchctl print gui/$(id -u)/com.balizero.wr2.supervisor` should show `state = running`, `pid > 0`

## Install / uninstall

### Install (one-time)

```bash
# 1. Run the SQL migration on Fly Postgres
fly ssh console -a nuzantara-postgres -C \
  "psql nuzantara_rag -f /path/to/138_wr2_status_notify.sql"

# 2. Copy the plist into LaunchAgents
cp infra/launchagents/com.balizero.wr2.supervisor.plist \
   ~/Library/LaunchAgents/

# 3. Bootstrap the daemon
launchctl bootstrap gui/$(id -u) \
   ~/Library/LaunchAgents/com.balizero.wr2.supervisor.plist

# 4. Verify it's running
launchctl print gui/$(id -u)/com.balizero.wr2.supervisor | grep -E "state|pid"
tail -20 ~/logs/wr2_supervisor.log

# 5. Remove StartCalendarInterval from the 5 chained plists
#    (draft-generator, image-generator, fact-extractor, fact-checker,
#    canva-apply). topic-selector keeps its 05:10 cron.
```

### Uninstall

```bash
# Stop the supervisor
launchctl bootout gui/$(id -u)/com.balizero.wr2.supervisor

# Restore the chained-cron plists from your snapshot dir, then bootstrap
# them back. Run each downstream stage once to flush stranded drafts:
for stage in draft-generator image-generator fact-extractor fact-checker canva-apply; do
  launchctl kickstart gui/$(id -u)/com.balizero.wr2.$stage
  sleep 60
done

# (Only if rolling back permanently:) drop the trigger
psql nuzantara_rag -c "DROP TRIGGER wr2_status_change_trg ON war_room_drafts;"
psql nuzantara_rag -c "DROP FUNCTION wr2_status_change_notify();"
```

## Known limits

- **Throughput**: ~10 drafts/day before Gemini Ultra rate limits (silent throttling). Worth flagging if Bali Zero scales editorial output.
- **Mac sleep gap**: NOTIFYs fired while the Mac is asleep are lost. Reconciliation catches them on wake, but a draft that transitioned `briefed → drafts` during sleep will resume from `drafts` (not from `briefed` again — workers are idempotent so this is safe).
- **Single supervisor SPOF**: only one instance on Pro. launchd restarts it within 10s on crash. No HA — not warranted at this scale.
- **Canva render variance**: 2–15 min normal, the 30-min reconcile threshold accommodates worst-case.

## Tests

`scripts/tests/test_wr2_supervisor.py` — 17 unit tests covering:
- Transition resolution (exact, wildcard, alert-only, unknown sentinel)
- `kickstart` no-`-k`, rc=113 no-op, dry-run mode, real-failure alerting
- Per-draft serialisation lock
- Stale payload re-read fallback to current DB status
- Per-(draft, target) dedup blocks duplicates **but not different drafts**
- Reconciliation kicks stalled drafts and respects dedup
- Telegram alert on rendered
- Dedup set bounded growth
- `conn = None` UnboundLocalError protection (source-level assertion)

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest ../../scripts/tests/test_wr2_supervisor.py -v
```
