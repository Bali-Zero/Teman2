# S12 — CRM Automation Revive (forensic diagnosis)

**Session**: ONDA-3 S12 `crm-automation-revive` · **Frozen**: 2026-06-02T20:23Z
**Links to**: S1 (events_outbox `client_changed` gate-off, already on main)
**Method**: read-only. Code grep + `launchctl list` (authoritative for daemons) + crontab + OpenClaw cron config + asyncpg **SELECT-only** on prod DB. Every number derived from a tool call in this session. No DB mutation. No PII (aggregates only).

## Headline

S1 already revived the `client_changed` consumer — **the channel is ALIVE again**, draining in real time (~65 ms latency). The "215h gate-off" no longer holds: the live consumer `event_bus:client.changed` last consumed `2026-06-02 07:48:08Z`, identical to the newest event.

The CRM automation that actually runs in production is **not** the `services/crm/` modules — it is a standalone nightly crontab script, `apps/backend-rag/scripts/crm_automation_engine.py`, which reimplements quality/docs/renewals/stale inline and **does not import `services/crm/*`**. Three `services/crm/` automations are orphaned relative to the live runtime.

## Two parallel CRM-automation realities

1. **In-process EventBus** inside the Fly `nuzantara-rag` app — consumes PG `LISTEN/NOTIFY` (`client_changed`, `practice_changed`) in real time. Started in `app_factory.py` (EventBus @221, PracticeStatusListener @211). Fly `/health` = 200, DB connected → these are running.
2. **Standalone nightly crontab** `crm_automation_engine.py` (daily 23:00 UTC = 07:00 WITA) — own asyncpg/httpx logic, no `services/crm/` imports. 5 consecutive clean runs (05-29..06-02), last `2026-06-02 23:00:02Z` exit 0.

## events_outbox forensics (real query output)

| channel | total | unconsumed | live consumer | last consumed (live) |
|---|---|---|---|---|
| `client_changed` | 6390 | 554 | `event_bus:client.changed` (5535) | 2026-06-02 07:48:08Z |
| `practice_changed` | 802 | 82 | `event_bus:practice.status_changed` (234) | 2026-06-02 09:06:46Z |

- The **554 / 82 unconsumed** are stale `consumer=None` backlog from the pre-revival gap (`client_changed` orphans span 2026-05-12 → 2026-05-31). The OLD consumer last drained `2026-05-12 12:33`; the EventBus consumer took over `2026-05-15 23:59` and has run continuously since. Gap ≈ **83h**, now closed. These rows are dead backlog, **not** a live gate-off.

## Service × State matrix

| Service | Kind | State | Last run | Why |
|---|---|---|---|---|
| EventBus `client_changed` consumer | in-process PG LISTEN | **ALIVE** | 2026-06-02 07:48Z (real-time) | S1 fix held; Fly /health 200 |
| `PracticeStatusListener` | in-process PG LISTEN | **ALIVE** | 2026-06-02 09:06Z (real-time) | consumer real-time |
| `crm_automation_engine.py` (quality/docs/renewals/stale) | crontab daily | **ALIVE** | 2026-06-02 23:00Z exit 0 | 5 clean runs in jsonl |
| `automation.py` (Process/Completed/WaitingDocuments) | on-demand classes | **ON-DEMAND** | request-driven | no daemon; logic also duplicated inline in engine |
| `assignment.py` (lead assignment) | LangGraph workflow | **DEAD** | never wired | zero live callers repo-wide |
| `birthday_notifier_service.py` | daily task / HTTP endpoint | **DEAD** | no live trigger | scheduler enabled=False; OpenClaw target gone; no cron hits endpoint |
| `enrichment.py` birthplace | daily batch (Ollama) | **DEAD-IN-PROD** | no prod run | `_is_production` guard skips registration on Fly |

**Counts: 3 ALIVE · 1 ON-DEMAND · 2 DEAD · 1 DEAD-IN-PROD** (7 classified).

## What is NOT running that should be (revive plans — all SPEC + NEEDS-ANTONELLO)

### 1. Lead assignment (`assignment.py`) — DEAD, zero callers
`trigger_lead_assignment` / `assign_lead` / `create_lead_assignment_workflow` have **no live caller anywhere** (only the `lead_assignment_agent.py` shim + `__init__` export). The nightly engine has its OWN inline `run_lead_assignment` (round-robin SQL), but `"assignment"` is **not** in the nightly default module list `[quality, docs, renewals, stale]` — it runs only via manual `--module assignment`. The Telegram digest line "Lead Assignment: all assigned ✅" is the `assigned==0` fallback, i.e. it never ran.
**Revive**: pick ONE owner — (a) wire `services/crm/assignment.py` into the `on_client_changed` EventBus handler (auto-assign on INSERT), or (b) add `assignment` to the engine nightly modules. Two implementations exist; choose one, delete the other. Hard-to-reverse (prod consumer) → do not execute.

### 2. Birthday notifier — DEAD, stale migration
Disabled in `autonomous_scheduler` with comment "migrated to OpenClaw client-health-monitor". **The OpenClaw target job is gone** — `~/.openclaw/cron/jobs.json` has only 4 jobs (pro-readonly-health, mcp-smoke-readonly, weekly-lobster-audit, Memory Dreaming Promotion). No crontab / Pro script / LaunchAgent hits `POST /api/cron/notifiers/birthday`. No `birthday_notifier_enabled` kill-switch in `system_settings`. Reachable only by manual curl.
**Revive**: add a crontab line hitting the endpoint daily ~08:00 WITA with `X-API-Key`, plus a `system_settings` kill-switch (symmetry with visa/lkpm). Re-enabling in autonomous_scheduler is unsuitable (24h interval > Fly auto_stop uptime — the original reason it was disabled).

### 3. Birthplace enrichment — DEAD-IN-PROD, Ollama-guarded
Registered `enabled=True` but `_is_production` skips registration on Fly (no Ollama). `fly.toml` has `ENVIRONMENT=production`. The birthday notifier depends on birthplace data for personalization → both dead together.
**Revive**: belongs on Mini-Pro2 (H24 Ollama), not Fly. A Pro/Mini cron running `run_birthplace_enrichment_task` against prod DB with local Ollama.

## Optional cleanup (also NEEDS-ANTONELLO — touches prod outbox)
Replay or prune the 554 + 82 stale `consumer=None` rows. Read-only diagnosis leaves them untouched.
