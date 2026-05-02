# WR2 IPC mechanism audit (Event-driven Law compliance) — Sprint 0 Track B2

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Audit WR2 IPC: filesystem o EventBus"

## Symbiosis Law 4 (relevant text)

> Event-driven. Redis Streams e consumer groups. Nessun polling, nessun
> orchestratore centrale. Se Redis e' down, ogni agente funziona in isolamento.

Reality (per cicatrix-scars.md): the substrate is **PostgreSQL LISTEN/NOTIFY
+ events_outbox** (migration 144 + 146), not Redis Streams. Same intent
("durable async event bus"), different runtime. The Law's spirit holds:
no polling, no central orchestrator.

## What was audited

For each of the 13 WR2 LaunchAgents in `infra/launchagents/com.balizero.wr2.*.plist`
(plus 4 Pro-only sourced from `scripts/wr2_*.py`), determine **how it
publishes its work product to downstream consumers**:

- **DB INSERT/UPDATE on a triggered table** → effectively `pg_notify` via
  trigger function (good; respects Event-driven Law)
- **Direct `pg_notify(channel, payload)` call** → also good
- **Filesystem write** (json/log files in `~/.openclaw/workspace/`) → bad;
  violates Event-driven Law; downstream consumer must poll
- **Telegram message only** (no DB write) → grey area; Telegram is a
  human-facing sink, not a substrate for inter-organelle IPC, but if no
  cell consumes the output it's fine
- **HTTP call to Fly backend** → grey area; the backend may or may not
  re-publish via EventBus

## Empirical findings (per organelle)

| Organelle | Cognitive Level | Output | Channel | Verdict |
|---|---|---|---|---|
| `oracle` | L4 | INSERT into `ultra_moves` (mig 114) | `cognitive_event` | ✅ Event-driven |
| `strategos` | L3 | INSERT into `weekly_strategic_briefs` (mig 114) | `cognitive_event` | ✅ Event-driven |
| `connector` | L1 | INSERT into `cross_dossier_theses` (mig 114) | `cognitive_event` | ✅ Event-driven |
| `supervisor` | L2 | LISTEN on `wr2_status_change` (mig 138) + chain steps | n/a (consumer, not producer) | ✅ Event-driven (consumer) |
| `pg-proxy` | L2 | TCP proxy to Postgres flycast — substrate | n/a (infra, no IPC events) | ✅ neutral |
| `learner-nightly` | L1 | INSERT into M14 retrain log + skills/scars (mig 114) | `cognitive_event` (anomaly side) + skills/scars (cell-core) | ✅ Event-driven |
| `trend-hunter` | L1 | INSERT into `trend_signals` (mig 113) | `intel_event` | ✅ Event-driven |
| `measurer` | L1 | INSERT into `post_metrics_history` + `m13_retrain_log` | (no trigger registered → silent) | ⚠️ DB write but NO NOTIFY — needs trigger |
| `dossier-compiler` | L1 | INSERT/UPDATE on `research_dossiers` (mig 113) | `intel_event` | ✅ Event-driven |
| `topic-selector` (Pro-only) | operational | INSERT into `war_room_drafts` (mig 112 + 138) | `war_room_event` + `wr2_status_change` | ✅ Event-driven (dual emitter) |
| `draft-generator` (Pro-only) | operational | UPDATE `war_room_drafts.status` (status='drafted') (mig 138) | `wr2_status_change` | ✅ Event-driven |
| `image-generator` (Pro-only) | operational | UPDATE `war_room_drafts` (image fields) | (only on status change → fires `wr2_status_change`) | ✅ Event-driven |
| `canva-apply` (Pro-only) | operational | UPDATE `war_room_drafts` to status='reviewed' | `wr2_status_change` | ✅ Event-driven |
| `canva-renderer` (repo-only orphan) | operational | shell script, every 300s — likely renders Canva exports to disk | filesystem only | ⚠️ pure filesystem — see Sprint 0 follow-up |
| `newsletter` | operational | NewsletterPublisher writes to `apps/web/blog/` MDX files; INSERT into `war_room_posts` | `war_room_event` | ✅ Event-driven (after MDX commit) |
| `sla-worker` | operational | UPDATE `war_room_drafts.status` (timeout → status='abandoned') | `wr2_status_change` | ✅ Event-driven |
| `hardening` | operational | runs 3 hardening CLIs; output to launchd logs + Telegram | filesystem + Telegram | ⚠️ no DB write — see "operational hardening" below |

## Two violations + one grey area

### Violation 1 — `measurer` writes to DB but no trigger fires

`backend.services.measurer.scheduler_cli` does `INSERT INTO post_metrics_history`
and `INSERT INTO m13_retrain_log`. Neither table has a `pg_notify` trigger
registered (cf. migrations 112-114). Downstream consumers (dashboard SSE,
M14 learner) must poll.

**Migration target (Sprint 1 or Sprint 2):** add a trigger on
`post_metrics_history` AFTER INSERT firing `pg_notify('measurer_event',
{...})` and register `measurer_event` in PG_CHANNEL_MAP. Squawk-lint will
require `-- squawk-ignore: …` directives for the trigger creation on a
table with existing data.

### Violation 2 — `canva-renderer` is pure filesystem

The `canva-renderer` plist (orphan in repo, may already be deprecated on
Pro per Track B1) runs a shell script every 300s. No DB write, no event.
Not a real organelle — likely a legacy auto-render daemon that should be
deleted.

**Action (Sprint 0 follow-up):** confirm with Antonello whether
`canva-renderer` is still useful. If not, remove the plist from repo (and
unload from Pro if present). If yes, document its consumer (probably a
filesystem watcher in `scripts/wr2_canva_apply.py` — needs verification).

### Grey area — `hardening` chain output is filesystem + Telegram

The `wr2-hardening-chain.sh` runs 3 backend CLIs (`missed_runs_cli`,
`token_watchdog_cli`, `quota_cli`) and aggregates their JSON exits. The
output is launchd logs + Telegram alerts; no DB write, no event emitted.

This is not a violation per-se: hardening is "operational maintenance",
not "cell IPC". The right tier for it is the **observed-shell tier**
(Sprint 0 Track C2) — the script should `await ObservedShellBus.emit(
"wr2.hardening.run", "ok"|"error", payload, trace_id)` so monitoring
catches silent failures. NOT a Symbiosis Law 4 violation, but it would
benefit from the new tier.

## What's NOT a violation

- `pg-proxy` is the substrate itself. No events to emit.
- `supervisor` is a **consumer**, not a producer (it LISTENs on
  `wr2_status_change` and chains steps). Consumers don't owe Event-driven
  Law on output side.
- Telegram messages from `oracle`/`strategos`/`learner-nightly` for
  human-facing alerts: those go through `oracle_delivery.py` /
  `strategos_delivery.py` separately, AFTER the DB insert. The DB
  insert is what triggers the event; the Telegram message is delivery,
  not IPC.

## `wr2_status_change` is NOT in PG_CHANNEL_MAP

This is documented as a structural choice in `cicatrix-scars.md` (P0-2
phase 2 footnote). The `wr2_status_change` channel is consumed only by
`scripts/wr2_supervisor.py` (a launchd daemon outside the FastAPI
process), so the EventBus reconnect-hook has no need to replay it.
Its events are ALSO emitted by trigger 112 as `war_room_event` (a
duplicated path), so the in-process FastAPI consumers still get the
fanout via the durable substrate. **No action needed.**

## Verdict

| Question | Answer |
|---|---|
| Do all 13 (+4 Pro-only) WR2 LaunchAgents respect Symbiosis Law 4 (Event-driven)? | **Effectively yes**, with 1 narrow violation (`measurer` write-without-trigger), 1 orphan to clean (`canva-renderer`), and 1 grey area (`hardening` chain — fits observed-shell tier). |
| Is the migration to PG NOTIFY needed, as round 2 brainstorm Gemini suggested? | **NO migration needed for the cognitive set.** Triggers from migrations 112+113+114 already cover oracle/strategos/connector/learner-nightly/trend-hunter/dossier-compiler. The 4 Pro-only operational organelle update `war_room_drafts` and trigger 138 fires correctly. |
| Specific deltas? | (a) Add trigger on `post_metrics_history` (`measurer`); (b) decide fate of `canva-renderer` orphan; (c) wire `wr2-hardening-chain.sh` to ObservedShellBus.emit (Track C2). |

## Action items (post-merge / Sprint 1)

1. **Sprint 1 W1:** add `measurer_event` channel + trigger on
   `post_metrics_history` (squawk-ignore directives, ROLLBACK marker).
2. **Sprint 0 follow-up (this PR or next):** verify `canva-renderer`
   plist is dead code; if so, delete from `infra/launchagents/`.
3. **Sprint 0 (this PR Track C2):** ObservedShellBus to emit hardening
   chain results — sample integration line in observed-shell-tier.md.

## References

- `apps/backend-rag/backend/services/events/event_bus.py` (PG_CHANNEL_MAP)
- `apps/backend-rag/backend/db/migrations_v2/112_war_room_tables.sql` (`war_room_event` trigger)
- `apps/backend-rag/backend/db/migrations_v2/113_intel_radar_findings.sql` (`intel_event` trigger)
- `apps/backend-rag/backend/db/migrations_v2/114_cognitive_layer_tables.sql` (`cognitive_event` trigger)
- `apps/backend-rag/backend/db/migrations_v2/138_wr2_status_notify.sql` (`wr2_status_change`)
- `apps/backend-rag/backend/db/migrations_v2/146_eventbus_triggers_use_outbox.sql` (durability layer)
- `scripts/wr2_supervisor.py` (LISTEN consumer)
- `scripts/wr2_topic_selector.py`, `wr2_draft_generator.py`, `wr2_image_generator.py`, `wr2_canva_apply.py` (operational organelle)
- `cicatrix-scars.md` § "EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams"
