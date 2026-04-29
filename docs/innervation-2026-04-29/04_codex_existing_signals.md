
# Existing Implicit Signal Contract

Peer check: running on Pro (`nuzantara@Nuzantara`). Air was unreachable, so remote git sync could not be confirmed.

## Catalog Of Existing Signals

| Pattern | References | Trigger | Destination | Structure | Current Consumer |
|---|---|---|---|---|---|
| Organism canonical event helper | `apps/organism/organism/schemas.py:19`, `apps/organism/organism/emit.py:17`, `apps/organism/organism/emit.py:50`, `apps/organism/organism/redis_bus.py:18` | Explicit `emit_event()` calls from organism cron, git hook, actuators, guardians | JSONL first at `~/logs/organism/events.jsonl`, then Redis stream `organism:events` | Typed JSON: `ts`, `severity`, `source`, `kind`, `payload`, `correlation_id`, `is_actuation`, `host` | Organism supervisor reads Redis stream; JSONL is durable mirror |
| Organism supervisor heartbeat and decisions | `apps/organism/organism/supervisor/daemon.py:35`, `apps/organism/organism/supervisor/daemon.py:79`, `apps/organism/organism/heartbeat.py:15`, `apps/organism/organism/heartbeat.py:39` | Supervisor loop | Redis key `organism:supervisor:heartbeat`, decisions JSONL `~/logs/organism/decisions.jsonl` | Heartbeat JSON in Redis; decision JSONL with event kind, correlation id, actuator, confidence | Guardians call `get_supervisor_heartbeat()` before emitting |
| Organism scheduled/git/actuator events | `apps/organism/organism/scheduled_tick.py:16`, `apps/organism/organism/post_commit_hook.py:33`, `apps/organism/organism/actuators/base.py:39`, `apps/organism/organism/actuators/base.py:78` | Cron tick, post-commit new module, actuator success/failure | `emit_event()` plus actuator WAL under `~/logs/organism/wal` | Canonical organism event plus per-actuator WAL JSON | Supervisor consumes stream; WAL is local audit |
| System Doctor guardian events | `scripts/system_doctor.py:112`, `scripts/system_doctor.py:633`, `scripts/system_doctor.py:1339`, `scripts/system_doctor.py:1661`, `scripts/system_doctor.py:1675` | Cron-agent failures or stale NLM pipeline detection | `emit_event()` when supervisor alive; Telegram on NLM rerun failure; JSON report to stdout | Canonical organism event for `cron_agent_failure`; Telegram free text; NLM state JSON | Organism supervisor; human Telegram; caller parsing stdout |
| Zombie Hunter guardian events | `scripts/sentinel_lib/zombie_hunter.py:41`, `scripts/sentinel_lib/zombie_hunter.py:78`, `scripts/sentinel_lib/zombie_hunter.py:131` | Repeated bad launchd exits | State file `~/.agent/decisions/state/launchd_bad_exits.json`; `emit_event()` when supervisor alive | Rolling JSON history and canonical `zombie_detected` event | Sentinel/zombie detector; organism supervisor |
| Cron Agent framework | `/Users/nuzantara/scripts/cron-agent-python/agent_job.py:27`, `/Users/nuzantara/scripts/cron-agent-python/agent_job.py:130`, `/Users/nuzantara/scripts/cron-agent-python/agent_job.py:459`, `/Users/nuzantara/scripts/cron-agent-python/agent_job.py:486`, `/Users/nuzantara/scripts/cron-agent-python/agent_job.py:595` | Every Python cron job run | State file `~/.cron-agent-python/<job>.state.json`; Redis streams `cron:reports` and `cron:<job>`; Telegram on non-ok | State JSON with job/run/status/duration/side_effects/error/ledger; Redis XADD fields | `cron_dashboard.py`, `tech_orchestrator.py`, MCP server, humans via Telegram |
| Cron dashboard/orchestrator consumers | `/Users/nuzantara/scripts/cron-agent-python/cron_dashboard.py:31`, `/Users/nuzantara/scripts/cron-agent-python/tech_orchestrator.py:105`, `/Users/nuzantara/scripts/cron-agent-python/mcp_server.py:65` | Dashboard or orchestrator query | Redis `cron:reports`, fallback `.state.json` | Aggregated run status | Operator dashboard, orchestrator, MCP tools |
| Shell cron wrapper | `scripts/cron-wrapper.sh:29`, `scripts/cron-wrapper.sh:141`, `scripts/cron-wrapper.sh:146`, `scripts/cron-wrapper.sh:169` | Wrapped cron command completion/failure | JSONL `~/logs/cron/<job>.jsonl`; Sentinel state `~/.agent/decisions/state/<job>.last.json`; Telegram on final failure | JSONL `{job,status,exit_code,attempts,duration_s,host,ts}` and state JSON `{job,ts,status,host,source,duration_ms,last_error}` | Sentinel, Cell CronSensor, Prometheus cron exporter |
| Cron exporter | `scripts/exporters/cron_exporter.py:1`, `scripts/exporters/cron_exporter.py:45` | Prometheus scrape | Reads `~/logs/cron/*.jsonl` | Metrics derived from JSONL | Prometheus |
| Sentinel state mesh | `scripts/nuzantara-sentinel.py:43`, `scripts/nuzantara-sentinel.py:202`, `scripts/nuzantara-sentinel.py:740`, `scripts/nuzantara-sentinel.py:793`, `scripts/nuzantara-sentinel.py:852` | Sentinel cycle | Reads state files; writes `~/logs/sentinel.jsonl` and `~/.agent/decisions/sentinel_status.json`; Telegram alerts via alerter | JSONL run summary; JSON status snapshot | Operator, follow-up sentinel cycles, humans |
| Sentinel Telegram alerter | `scripts/sentinel_lib/alerter.py:9`, `scripts/sentinel_lib/alerter.py:22`, `scripts/sentinel_lib/alerter.py:72` | Alert-worthy Sentinel finding | Telegram Bot API; dedup/cooldown files | Free text with md5 dedup JSON | Human operator |
| Pro dead-man heartbeat | `scripts/nuzantara-sentinel.py:45`, `scripts/nuzantara-sentinel.py:307`, `reports/air-retirement/pro-crontab-before-2026-04-24.txt:13` | Hourly touch in Pro crontab snapshot | `~/.pro_heartbeat` mtime | File mtime only | Air Sentinel dead-man check |
| NLM ARCH-9 heartbeat | `apps/evaluator/nlm_deep_research/heartbeat_monitor.py:52`, `apps/evaluator/nlm_deep_research/heartbeat_monitor.py:102`, `apps/evaluator/nlm_deep_research/heartbeat_monitor.py:184`, `apps/evaluator/nlm_deep_research/scripts/run_nb2_pipeline.sh:43` | Pipeline success/failure | `~/.agent/decisions/state/heartbeat_<pipeline>.json`; Telegram on failure | JSON `{pipeline,last_success,duration_seconds}` | NLM heartbeat monitor, Sentinel state collector |
| Cell pulse | `apps/cell/cell/core/pulse.py:79`, `apps/cell/cell/core/pulse.py:300`, `apps/cell/cell/core/pulse.py:323`, `apps/cell/cell/core/pulse.py:637`, `apps/cell/cell/core/pulse.py:664` | CELL 60s pulse loop | Logger, Redis short-term memory, Postgres `cell_pulse_log`, episodic memory on significant event | `PulseResult`; Redis `Observation`; SQL row | Cell dashboard, weekly report, sensors, operator |
| Cell DB signal tables | `apps/cell/cell/core/db.py:29`, `apps/cell/cell/core/db.py:126`, `apps/cell/cell/memory/episodic.py:81` | Pulse, alert, episode | Postgres `cell_pulse_log`, `cell_alerts`, `cell_episodes` | SQL rows | `/api/cell/status`, weekly report, CELL memory |
| Cell status consumers | `apps/backend-rag/backend/app/routers/cell_status.py:16`, `apps/backend-rag/backend/app/routers/cell_status.py:61`, `apps/backend-rag/backend/app/routers/cell_status.py:88`, `apps/cell/scripts/cell_weekly_report.py:24` | Dashboard/API/report read | Postgres queries | JSON API response or Telegram report | Frontend/status dashboard, humans |
| Cell CronSensor | `apps/cell/cell/sensors/cron_sensor.py:1`, `apps/cell/cell/sensors/cron_sensor.py:81`, `apps/cell/cell/sensors/cron_sensor.py:137` | Cell sensor cycle | Reads `~/.agent/decisions/state/*.last.json` | File JSON `{job,ts,status,host}` | CELL pulse health classification |
| Backend EventBus outbox | `apps/backend-rag/backend/services/events/event_bus.py:45`, `apps/backend-rag/backend/services/events/event_bus.py:198`, `apps/backend-rag/backend/services/events/outbox.py:71`, `apps/backend-rag/backend/db/migrations_v2/146_eventbus_triggers_use_outbox.sql:34` | Backend domain event or DB trigger | `events_outbox` table plus `pg_notify` | JSON payload with `_outbox_id`; mapped PG channels | EventBus listeners, replay on reconnect |
| Backend PG LISTEN consumers | `apps/backend-rag/backend/services/events/event_bus.py:280`, `apps/backend-rag/backend/services/events/event_bus.py:395`, `apps/backend-rag/backend/services/crm/practice_status_listener.py:99` | PG notification | Dedicated asyncpg listeners | JSON notification payload enriched with metadata | In-process handlers, CRM automations |
| Ack-first inbound webhooks | `apps/backend-rag/backend/services/channels/inbound_webhook_repo.py:23`, `apps/backend-rag/backend/services/channels/inbound_webhook_repo.py:72`, `apps/backend-rag/backend/services/channels/inbound_webhook_repo.py:100`, `apps/backend-rag/backend/services/channels/webhook_processor.py:79` | WhatsApp/Telegram/Instagram/Twitter webhook receive | `inbound_webhooks` table plus `events_outbox` notify `inbound_webhook_queued`; 5s polling fallback | SQL row plus notify payload `{channel,dedup_key,inbound_webhook_id}` | `WebhookProcessor` |
| Ack-first routers | `apps/backend-rag/backend/app/routers/whatsapp_chat.py:623`, `apps/backend-rag/backend/app/routers/telegram_webhook.py:236`, `apps/backend-rag/backend/app/routers/twitter.py:120` | Channel webhook HTTP request | Same inbound webhook repo | Channel-specific payload persisted before processing | WebhookProcessor |
| Bridge outbox | `apps/backend-rag/backend/services/bridge/outbox.py:1`, `apps/backend-rag/backend/services/bridge/outbox.py:35`, `apps/backend-rag/backend/app/routers/bridge.py:50`, `apps/backend-rag/backend/services/events/handlers/_core.py:201` | Selected backend events for Pro sync | `bridge_outbox` table; `/api/bridge/events?after_id=` | SQL rows `{id,type,payload,created_at}` | Pro bridge poller |
| WR2 raw PG notify exception | `apps/backend-rag/backend/db/migrations_v2/138_wr2_status_notify.sql:1`, `apps/backend-rag/backend/db/migrations_v2/138_wr2_status_notify.sql:25`, `scripts/wr2_supervisor.py:426` | `war_room_drafts` insert/status change | Raw `pg_notify('wr2_status_change', json)` | JSON draft/status payload | `wr2_supervisor.py` |
| Post-publish queue | `apps/backend-rag/backend/app/routers/intel.py:549`, `apps/backend-rag/backend/app/routers/intel.py:566`, `apps/backend-rag/backend/app/routers/intel.py:609`, `apps/backend-rag/backend/app/routers/intel.py:633` | Intel post queued, polled, completed, failed | `post_publish_queue` DB rows; structured logger extras | SQL status row plus logger metadata | `post_publish_poller.py` and operators |
| LLM metrics stream | `apps/backend-rag/backend/llm/metrics_emitter.py:1`, `apps/backend-rag/backend/llm/metrics_emitter.py:35` | LLM call completion | Redis stream `llm:metrics` | XADD fields provider/model/latency/tokens/status | Future dashboard/alerting per module comment |
| Metabolic rollup | `scripts/metabolic_rollup.py:48`, `scripts/metabolic_rollup.py:93`, `scripts/metabolic_rollup.py:109`, `scripts/metabolic_rollup.py:125` | Metabolic rollup cron | Sentinel state, cron JSONL, Redis stream `organism:metrics`, optional Telegram | Cron-compatible state/log plus event envelope `{id,type,source,timestamp,priority,payload}` | Sentinel/CronSensor, Redis consumers, humans |
| KG cache invalidation | `apps/backend-rag/backend/services/rag/kg_cache.py:130` | KG cache invalidation | Redis pub/sub channel | JSON `{version,keys}` | Cache subscribers |
| Telegram notifications generally | `apps/cell/cell/effectors/telegram.py:14`, `/Users/nuzantara/scripts/cron-agent-python/agent_job.py:157`, `scripts/cron-wrapper.sh:89`, `scripts/sentinel_lib/alerter.py:72` | Failure, alert, report, action result | Telegram Bot API | Mostly free text/Markdown/HTML; some JSON HTTP body | Human operator only |

## Implicit Contract

Pattern A: local durable liveness files are the oldest and widest contract. Cron wrapper, Sentinel, NLM, Zombie Hunter, Cell CronSensor, and cron-agent all use local JSON state files before any network side effect. The dominant shapes are `*.last.json` in `~/.agent/decisions/state` and `*.state.json` in `~/.cron-agent-python`.

Pattern B: backend domain events use durable SQL first, volatile wakeup second. `events_outbox` plus `pg_notify` is explicit in `outbox.py` and migration `146_eventbus_triggers_use_outbox.sql`. Ack-first webhooks follow the same law: persist row, notify best-effort, poll fallback.

Pattern C: Redis streams are already used as operational buses, but not one bus. Existing streams include `organism:events`, `cron:reports`, `cron:<job>`, `llm:metrics`, and `organism:metrics`. The organism stream already has the best envelope and JSONL mirror.

Pattern D: Telegram is notification, not state. It is widespread, deduped in Sentinel, and recorded as a side effect in cron-agent, but no code treats Telegram as authoritative system state.

Logger-only signals are weak contracts. They exist around pulse summaries, EventBus lifecycle, post-publish queue actions, and webhook processing, but consumers are mainly humans/log tooling unless coupled to DB, Redis, or state files.

## Minimum Unification

Use the existing organism `Event` schema as the target contract. Do not invent another envelope. It already has severity, source, kind, payload, correlation id, host, and graceful degradation via JSONL-first writes.

Add bridges, not edits to 50 jobs:

1. State-file bridge: scan `~/.agent/decisions/state/*.last.json`, `~/.agent/decisions/state/heartbeat_*.json`, `~/.agent/decisions/state/launchd_bad_exits.json`, and `~/.cron-agent-python/*.state.json`. Convert fresh changes into `organism:events` and the JSONL mirror. Existing writers remain unchanged and local-first.

2. Cron Redis bridge: read `cron:reports` and re-envelope significant entries into `organism:events`. Alternatively, one low-risk central change in `AgentJob._publish_redis_event()` can call `emit_event()` after writing the local state and existing Redis stream.

3. Backend outbox bridge: mirror `events_outbox`, `bridge_outbox`, and `inbound_webhooks` terminal states into `organism:events`. The backend already has SQL durability and replay, so the bridge can be a consumer without changing webhook ack behavior.

4. Cell pulse bridge: tail `cell_pulse_log` and emit `cell.pulse` events with severity mapped from green/yellow/red. Keep Postgres write first because the dashboard and weekly report already depend on it.

5. Treat Telegram as a sink only. Preserve it as human notification and include `telegram_sent` or `side_effects` in event payloads when known.

Law 4 remains intact if every bridge writes no earlier than the existing local durable write. Redis failure must never prevent local JSON, SQL, or JSONL writes. For new bridge code, use the same rule as organism `RedisBus`: append JSONL first, then best-effort XADD to `organism:events`.

## TOP 3 patterns to bridge first

1. State-file mesh: `~/.agent/decisions/state/*.last.json`, `heartbeat_*.json`, and `~/.cron-agent-python/*.state.json`. This captures Sentinel, CronSensor, cron-agent, NLM, and launchd health with one bridge and no emitter changes.

2. Backend SQL outboxes: `events_outbox`, `bridge_outbox`, and `inbound_webhooks`. This captures domain events and PR #360 ack-first webhook signals while preserving DB durability and polling fallback.

3. Cell pulse log: `cell_pulse_log`. This is the strongest existing live health signal for the organism layer and can be bridged from one table without touching every sensor/effecter.

