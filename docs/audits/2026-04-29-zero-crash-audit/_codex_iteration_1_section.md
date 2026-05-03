# Codex section - zero-crash resilience audit

Date: 2026-04-29 WITA
Host: Pro, `nuzantara@Nuzantara`
Scope: Nuzantara monorepo, local Pro guard layer, Fly/Vercel deploy path, Cell/Genoma nervous system.

## Evidence boundary

- Machine check: Pro confirmed. Peer Air was unreachable over SSH, so Pro/Air git sync could not be verified.
- Git check: user brief says branch `main`; local checkout at audit time was `ops/post-incident-vaccination-2026-04-29` at `720d54f5c fix(crm/drive-poll): add missing get_file_metadata to ServiceAccountDriveService`.
- MCP readiness: `playwright` reachable; `nuzantara-mcp` configured but not reachable; `postgres` configured but blocked by sandbox; `nuzantara-mcp-advanced`, `github`, `qdrant-readonly`, `sentry` unavailable in the active tool set.
- Counts verified locally where possible: 26 app directories plus 5 packages in the checkout, 140 Python files under `backend/app/routers` including `__init__.py`, 862 backend tests under `apps/backend-rag/backend/tests`, 79 user LaunchAgent plists, 58 Sentinel jobs checked, 16 open circuit breakers, 40 escalation cooldowns, 54 DLQ entries.
- Sacred books read first: `SYMBIOSIS.md`, `VADEMECUM.md`, `INDEX.md`, `AUTONOMOUS_OPS.md`, `CLAUDE.md`, `.claude/rules/cicatrix-scars.md`.
- Off-limits files were not edited: `apps/backend-rag/backend/prompts/zantara_core.py`, `apps/backend-rag/fly.toml`, `.env.production`, `apps/backend-rag/backend/alembic/env.py`.

Severity key:

- P0: a crash or dropped unit of work can happen now without durable recovery or restart.
- P1: degradation can happen without a reliable alert, or the alert exists but does not recover.
- P2: recovery exists but is manual, partial, slow, or only next-schedule.

## 1. Backend startup failure can stay HTTP 200 forever

Failure mode: `initialize_services()` raises, `app.state.startup_failed=True` is set in `apps/backend-rag/backend/app/setup/app_factory.py:114-118`, but `apps/backend-rag/backend/app/routers/health.py:147-266` never calls the existing `_check_startup_failed()` helper from `health.py:48-55`. The basic `/health` can keep returning `initializing` or `degraded` with HTTP 200, so Fly does not restart the machine. Scar: 2026-04-29 backend restart loop from `drive_poll_service` missing method, where `/health` alone was not enough to prove user paths.

Blast radius: 2 Fly machines for `nuzantara-rag`, 139 router surfaces, 512 service class surfaces per brief, 7 channels behind the same app process.

Current detection: logs and post-deploy `/health` grep for `"healthy"` in `.github/workflows/fly-deploy.yml:258-274`; local login healthcheck catches auth only.

Current recovery: none if `/health` remains 2xx; operator must read logs or wait for downstream probes.

Proposed fix: in `apps/backend-rag/backend/app/routers/health.py`, at the top of `health_check()`, call `_check_startup_failed(request.app)` and return HTTP 503 with the startup error. Add a `startup_failed` service record to `/health/detailed`. Add a Cell event `cell:scar`/Genoma skill named `backend_startup_failed_health_503` whenever this path trips. Conceptual diff:

```python
startup_error = _check_startup_failed(request.app)
if startup_error:
    response.status_code = 503
    return HealthResponse(
        status="unhealthy",
        version="v100-qdrant",
        database={"status": "startup_failed", "error": startup_error["error"]},
        embeddings={"status": "startup_failed"},
    )
```

Post-fix verification:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/app/routers/test_health_startup_failed.py -q
PYTHONPATH=. python -m uvicorn backend.app.main:app --port 8009
curl -si http://127.0.0.1:8009/health
```

Before: startup failure can be HTTP 200. After: startup failure is HTTP 503, Fly can restart.

Severity: P0
Auto-implementable by Claude L2: yes

## 2. SQL v2 migrations still run on the old Fly image

Failure mode: `.github/workflows/fly-deploy.yml:134-152` runs `python -m backend.db.migrate apply-all` through `flyctl ssh console` before the rolling deploy. That console attaches to the already-running old image, so newly added SQL v2 runner code or packaged migration files can be absent. Scar: `.claude/rules/cicatrix-scars.md`, open structural cicatrix PR #307.

Blast radius: 30 SQL v2 migrations, last migration 140 per brief, all DB-backed routers and workers. A schema-dependent deploy can boot code that expects columns/tables that were not applied.

Current detection: migration job can pass against old code; post-deploy health checks only `/health` and non-blocking RAG smoke.

Current recovery: manual `gh workflow run fly-deploy.yml` retrigger after merge, documented as a scar.

Proposed fix: split migrations into two gates without editing `fly.toml`: keep a pre-deploy "old-image-compatible status" check, then add a post-deploy SQL v2 apply step that runs after new image readiness and before post-deploy health. Replace the hard-coded image sentinel from migration 119 with a commit SHA or packaged `backend/db/migrations_v2` count check. File path: `.github/workflows/fly-deploy.yml`. Cell/Genoma: record a migration scar in `packages/cell-core` Genome when post-deploy apply finds pending migrations.

Post-fix verification:

```bash
gh workflow run fly-deploy.yml -f dry_run=true
gh run view --log | rg "SQL v2 post-deploy"
flyctl ssh console --app nuzantara-rag --command "/bin/sh -c 'cd /app && python -m backend.db.migrate status'"
```

Before: SQL v2 applies before deploy only. After: same run proves `pending=0` from the new image before health is declared green.

Severity: P0
Auto-implementable by Claude L2: yes for workflow patch, no for production rollout without operator window

## 3. Python post-deploy migrations are hard-coded and can leave live code degraded

Failure mode: `.github/workflows/fly-deploy.yml:184-236` runs only migrations 119, 120, 121. The image readiness sentinel checks for `apply_migration_119.py` only at lines 195-212. Any future Python migration is manual workflow editing; failure sends Telegram at lines 238-245 but does not rollback or quarantine feature traffic.

Blast radius: any new Python-idiom migration under `backend/migrations`, plus modules depending on it. User-facing effect is partial deploy: new code is live while a required migration failed.

Current detection: job failure and Telegram.

Current recovery: manual investigation; post-deploy health is skipped because it needs `run-python-migrations`.

Proposed fix: add `apps/backend-rag/backend/migrations/registry.py` or a CLI `python -m backend.migrations.apply_pending` that discovers `apply_migration_*.py`, orders by number, checks idempotence markers, and runs all pending. In the workflow, rollback automatically if a required migration fails. Cell/Genoma: emit `deploy.migration_python_failed` and record the failed migration number as a scar.

Post-fix verification:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/migrations/test_apply_pending.py -q
PYTHONPATH=. python -m backend.migrations.apply_pending --dry-run
```

Before: 3 migration numbers hard-coded. After: discovered count equals files on disk and each run is idempotent.

Severity: P1
Auto-implementable by Claude L2: yes

## 4. Background workers are started without restart supervision

Failure mode: `asyncio.create_task()` starts the workflow queue and legal ingestion workers in `app_factory.py:170-183`; EventBus starts `_listen_loop()` at `event_bus.py:226-228`; DB health starts `_database_health_check_loop()` at `service_initializer.py:403-405`. There is a strong-ref helper `backend/services/common/background.py:1-54`, but these long-lived workers do not use a restart supervisor. If a task dies after startup, it can stay dead until process restart.

Blast radius: workflow queue, legal full ingestion, EventBus, DB health, practice notifications. These are cross-module recovery organs, not just feature workers.

Current detection: some `/health/detailed` service stats, logs, and maybe System Doctor if a downstream symptom appears.

Current recovery: none inside the process. Fly will not restart unless `/health` returns 503 or the process exits.

Proposed fix: add `backend/app/setup/task_supervisor.py` with `supervise(name, coro_factory, critical, restart_policy)` and done callbacks. Critical background workers should restart with exponential backoff; if restart budget is exhausted, set `app.state.startup_failed` or `app.state.background_failed[name]`, and basic health returns 503 for critical workers. File paths: `app_factory.py`, `service_initializer.py`, `event_bus.py`. Cell/Genoma: every exhausted worker restart writes Genome scar `worker_crash:<name>`.

Post-fix verification:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/setup/test_task_supervisor.py -q
PYTHONPATH=. pytest backend/tests/setup/test_background_workers_health.py -q
```

Before: killed task count can be 1 with `/health` still green. After: killed task restarts or health becomes 503 after budget exhaustion.

Severity: P0
Auto-implementable by Claude L2: yes

## 5. `DISABLE_BACKGROUND_WORKERS=1` silently removes nervous-system workers

Failure mode: `app_factory.py:151-160` skips Workflow Queue, Legal Ingestion, PracticeStatusListener, and EventBus when `DISABLE_BACKGROUND_WORKERS=1`. This is a valid emergency switch, but the app can appear healthy while core autonomous pathways are off.

Blast radius: 4 long-running workers and every feature depending on DB-triggered events or queue processing.

Current detection: one startup warning log. Basic `/health` does not expose the switch.

Current recovery: manual secret/env change and redeploy.

Proposed fix: expose `background_workers_disabled=true` in `/health/detailed`, publish `organism:events` and `cell:feedback`, and make System Doctor fail warning if the switch remains active for more than one deploy window. File paths: `app_factory.py`, `health.py`, `scripts/system_doctor.py`. Genoma: store an explicit "emergency switch active" scar instead of letting the state disappear in logs.

Post-fix verification:

```bash
DISABLE_BACKGROUND_WORKERS=1 PYTHONPATH=. pytest backend/tests/app/routers/test_health_background_switch.py -q
```

Before: 0 health fields. After: 1 explicit field and 1 emitted Cell/Organism event.

Severity: P1
Auto-implementable by Claude L2: yes

## 6. EventBus is PG NOTIFY plus in-process callbacks, not durable Redis Streams

Failure mode: `apps/backend-rag/backend/services/events/event_bus.py:1-12` documents optional Redis pub/sub, but the active implementation is PG LISTEN/NOTIFY and in-process subscribers. `emit()` at lines 140-196 calls handlers sequentially and only records errors in memory. PG notification callbacks use `asyncio.ensure_future()` at line 304 with no task registry. This violates Symbiosis Law 3: Redis Streams, no polling, no central orchestrator.

Blast radius: 7 PG channels, every handler in `backend/services/events/handlers`, client/practice/compliance/LKPM/war-room/intel/cognitive event propagation.

Current detection: `/api/event_bus` stats if the EventBus is running; logs on handler failures.

Current recovery: reconnect on DB listener failure, but no replay for handler failure, process crash between notification and handler completion, or consumer downtime.

Proposed fix: implement a durable Redis Streams backend: `xadd organism/events` or `backend:events`, consumer group per worker, handler ACK only after success, DLQ stream for failures, JSONL local mirror when Redis is down. Keep PG NOTIFY only as a trigger source. File paths: `backend/services/events/event_bus.py`, new `backend/services/events/redis_stream_bus.py`, migrations for event DLQ if PG mirror is needed. Cell/Genoma: every handler failure is a skill feedback event, not an in-memory counter.

Post-fix verification:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/events/test_redis_stream_bus.py -q
redis-cli XLEN backend:events
redis-cli XPENDING backend:events eventbus-workers
```

Before: Redis stream length is absent and handler errors are memory-only. After: events are replayable, `XPENDING=0` after successful handling, DLQ count is quantified.

Severity: P0
Auto-implementable by Claude L2: yes for code/tests, no for production activation without staged rollout

## 7. PG NOTIFY payload size warning does not truncate or fallback

Failure mode: `event_bus.py:209-216` logs when JSON payload is larger than 7500 bytes, but still calls `pg_notify($1, $2)`. PostgreSQL NOTIFY payload limit is about 8 KB, so large metadata can fail the emit path.

Blast radius: any bulk event payload, especially LKPM, war-room, intel, and cognitive events.

Current detection: log warning and then possible exception.

Current recovery: none. The event is not written to a durable queue first.

Proposed fix: enforce envelope pattern: store payload in `event_payloads` or Redis/JSONL, send only `{event_id, type}` through PG NOTIFY. File path: `backend/services/events/event_bus.py`. Cell/Genoma: record `event_payload_externalized` as a reusable scar/skill.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/services/events/test_large_payload_envelope.py -q
```

Before: payload >7500 bytes can error. After: payload >7500 bytes emits small envelope and can be replayed.

Severity: P1
Auto-implementable by Claude L2: yes

## 8. WhatsApp acknowledges before durable inbound persistence

Failure mode: `whatsapp_chat.py:617-703` returns 200 after scheduling `process_whatsapp_message` with FastAPI `BackgroundTasks` at lines 685-692. If the process crashes after HTTP 200 and before the background task persists/responds, Meta will not retry and the inbound message is lost.

Blast radius: WhatsApp live channel, one of 7 channels, likely highest business-critical intake path.

Current detection: webhook metric records success at lines 696-700 even though processing has not happened yet.

Current recovery: none for the lost inbound event.

Proposed fix: add a durable inbound outbox before 200: table `channel_inbound_events` or Redis Stream `channel:inbound`, unique on provider message id, then worker consumes idempotently. If durable write fails, return 503 so Meta retries. File paths: `backend/app/routers/whatsapp_chat.py`, new `backend/channels/inbound_queue.py`, SQL v2 migration. Cell/Genoma: publish `channel.inbound_queued` and record dropped enqueue failures.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/channels/test_whatsapp_inbound_outbox.py -q
```

Before: HTTP 200 can happen with 0 durable rows. After: HTTP 200 requires 1 durable row or duplicate idempotent row.

Severity: P0
Auto-implementable by Claude L2: yes

## 9. Instagram webhook returns HTTP 200 on routing failure

Failure mode: `instagram_chat.py:163-227` returns `{"status":"error"}` on route failure but leaves HTTP status 200. Lines 189-204 also return early inside loops, so one non-message event can stop processing later valid entries in the same webhook payload.

Blast radius: Instagram live channel, inbound messages and replies.

Current detection: error metric and log.

Current recovery: no provider retry if Meta treats 200 as accepted.

Proposed fix: same durable inbound queue as WhatsApp. For parse errors and route enqueue failures, return non-2xx. Process all entries before returning. File path: `backend/app/routers/instagram_chat.py`. Cell/Genoma: record `instagram_webhook_200_error` scar.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/channels/test_instagram_webhook_retries.py -q
```

Before: routing exception returns HTTP 200. After: durable enqueue is required for HTTP 200; route errors are retried from queue.

Severity: P0
Auto-implementable by Claude L2: yes

## 10. Twitter/X CRC is intentionally disabled with no degraded replacement

Failure mode: `router_registration.py:122` and `254-256` disable Twitter because CRC/OAuth is broken. User brief marks `twitter[CRC broken]`.

Blast radius: 1 of 7 channels is unavailable. It does not crash the platform, but any X/Twitter inbound workflow is dead until manual repair.

Current detection: comments and channel absence; not an active health alarm.

Current recovery: none.

Proposed fix: add channel health status that reports `twitter=disabled_crc_broken` to `/api/channels/health`, System Doctor, and Cell. Implement CRC fixture tests before re-enabling. File paths: `backend/app/routers/twitter.py`, `router_registration.py`, `backend/tests/channels/test_twitter_crc.py`. Genoma: record the disabled channel as an explicit known wound until healed.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/channels/test_twitter_crc.py -q
curl -s https://nuzantara-rag.fly.dev/api/channels/health | jq '.twitter'
```

Before: channel disabled in code comments. After: disabled state is measurable and alarms if still disabled after a deadline.

Severity: P2
Auto-implementable by Claude L2: yes, but re-enabling production webhook needs Meta/X console access

## 11. Outbound channel DLQ can still lose messages

Failure mode: `DeliveryManager.persist_failed()` writes to PG, then Redis fallback. If both are unavailable, `optimizations.py:385-398` logs `message LOST`. `BaseChannel.send_response_safe()` exists at `base.py:182-218`, but the central router streams via `adapter.stream_response()` at `router.py:164-165`, so channel-specific direct send paths can bypass the DLQ wrapper.

Blast radius: all outbound channel replies, especially WhatsApp/Telegram/Instagram.

Current detection: log error, no guaranteed alert.

Current recovery: none if both PG and Redis are down.

Proposed fix: add a filesystem spool fallback under a Fly volume path, for example `/data/channel_dlq_spool/*.jsonl`, with a drain worker and corruption quarantine. Enforce a lint/test that adapters use `send_response_safe()` or an equivalent DLQ-aware stream wrapper. File paths: `backend/channels/optimizations.py`, `backend/channels/base.py`, channel adapters. Cell/Genoma: failed spool writes become `channel.dlq_spool_failed` scars.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/channels/test_delivery_manager_spool.py -q
```

Before: PG down plus Redis down produces `message LOST`. After: 1 spool file exists and drains when PG returns.

Severity: P0
Auto-implementable by Claude L2: yes

## 12. Channel inbound dedup is in-memory only

Failure mode: `ChannelRouter.route_message()` dedups at `router.py:123-130`, but the dedup implementation is in-process memory. A deploy, restart, or second Fly machine can process the same provider retry twice.

Blast radius: 7 channels, duplicate client replies, duplicate CRM rows, duplicate actions.

Current detection: log when duplicate is detected in the same process window only.

Current recovery: none across processes.

Proposed fix: Redis SET/PG unique-key dedup keyed by provider message id and channel. The inbound outbox from entries 8 and 9 should make dedup durable. File paths: `backend/channels/optimizations.py`, `backend/channels/router.py`. Genoma: add a `durable_channel_dedup` skill.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/channels/test_cross_process_dedup.py -q
```

Before: duplicate after process restart is accepted. After: duplicate insert is idempotent and counted.

Severity: P1
Auto-implementable by Claude L2: yes

## 13. Router manifest is not the actual registration source of truth

Failure mode: `router_manifest.py:1-18` says the manifest makes missed router registration structurally impossible, but `router_registration.py:23-379` still manually imports and includes routers. The scar in `router_manifest.py:4-7` says PR #54/#55/#60 shipped routers missing from production light process. That can still recur because the manifest is not driving `include_routers()` and `include_light_routers()`.

Blast radius: 139 router surfaces. A router can pass file/manifest tests and still 404 in one Fly process group.

Current detection: `backend/tests/setup/test_router_manifest.py`, but it does not prove app route table equals manifest.

Current recovery: manual patch after 404 discovery.

Proposed fix: make `router_registration.py` iterate `ROUTER_MANIFEST` for both process groups, with explicit disabled-router list and conditions. Add a route table test that constructs the app and compares registered paths to manifest entries. File paths: `router_registration.py`, `router_manifest.py`, `backend/tests/setup/test_router_registration_from_manifest.py`. Cell/Genoma: record router 404 scars as Genome entries and make `genome.search("router 404")` part of the add-router checklist.

Post-fix verification:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py backend/tests/setup/test_router_registration_from_manifest.py -q
```

Before: manual include list can drift. After: manifest count equals registered router count per process group.

Severity: P0
Auto-implementable by Claude L2: yes

## 14. `dependencies.py` import gate is too narrow for a 139-router app

Failure mode: deploy gate checks only `from backend.app.dependencies import get_current_user` in `.github/workflows/fly-deploy.yml` and `tests.yml`. A dependency import, router import, or dependency factory used by another route can still crash at request time.

Blast radius: all routers importing `backend.app.dependencies`, plus auth, DB, rate-limit, and current-user dependencies.

Current detection: one import chain check and unit tests.

Current recovery: Fly restart only if import failure occurs during startup; request-time dependency crashes return 500.

Proposed fix: add a CI test that imports every router module in `backend/app/routers`, builds both light and rag app route tables, and resolves dependency signatures without network calls. File path: `backend/tests/setup/test_dependency_surface.py`. Cell/Genoma: add a `dependencies_spof_import_surface` scar.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/setup/test_dependency_surface.py -q
```

Before: 1 dependency symbol checked. After: all router modules and declared dependencies checked.

Severity: P1
Auto-implementable by Claude L2: yes

## 15. Qdrant/search criticality conflicts with graceful degradation

Failure mode: `service_initializer.py:55-143` marks search/Qdrant as critical. If Qdrant is unreachable, background startup fails. Because entry 1 leaves health ambiguous, the app can be alive but not useful. Separately, `/health` uses `get_qdrant_stats()` at `health.py:228-239`; if stats fail, the basic response can still be healthy with 0 collections/documents depending on helper behavior.

Blast radius: 12 Qdrant collections, 93K to 104K vector documents depending source, all RAG/KBLI/search endpoints.

Current detection: startup verification, `/health/detailed`, `rag_canary.py` in job registry but circuit `rag_canary_pro` status depends on Sentinel.

Current recovery: fail-fast was intended, but health gap can prevent restart; degraded non-RAG API process is not cleanly separated by user-visible status.

Proposed fix: define process-specific criticality: `main_rag` returns 503 if search unavailable; light API stays healthy but explicitly reports `rag_unavailable`. Add a Qdrant canary that verifies collection count >= expected floor and a known embedding query. File paths: `service_initializer.py`, `health.py`, `scripts/rag_canary.py`. Cell/Genoma: store Qdrant outage facts in Genome with collection count and embedding model `text-embedding-3-small` locked.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/app/routers/test_qdrant_health_canary.py -q
PYTHONPATH=. python scripts/rag_canary.py
```

Before: health can be green while search quality is broken. After: rag process health is 503 on search outage; api process degrades explicitly.

Severity: P1
Auto-implementable by Claude L2: yes

## 16. DB pool exhaustion is measured but not a restart or circuit signal

Failure mode: `service_initializer.py:348-358` sets pool max 10 and `health.py:207-221` updates pool gauges, but basic health does not fail if idle connections stay 0 or acquire waits pile up. Worker failures from disk-full/DB cascades are a known scar class in comments at `app_factory.py:145-150`.

Blast radius: every DB-backed route, workers, channels, portal, CRM, auth.

Current detection: metrics and some detailed health.

Current recovery: DB health loop can expire stale connections, but sustained pool starvation does not trip Fly restart or worker throttling.

Proposed fix: add pool pressure circuit: if `idle=0` and acquire latency > threshold for N consecutive checks, pause non-critical workers, return degraded for API and 503 for rag only if user traffic cannot acquire. File paths: `service_initializer.py`, `health.py`, new `backend/app/core/db_pool_guard.py`. Cell/Genoma: publish `db.pool_pressure` with pool size/idle numbers.

Post-fix verification:

```bash
PYTHONPATH=. pytest backend/tests/core/test_db_pool_guard.py -q
```

Before: pool idle 0 is just a gauge. After: pool pressure is a state machine with throttle/recovery counts.

Severity: P1
Auto-implementable by Claude L2: yes

## 17. Golden Rule #10 async client lifecycle is not enforced by CI

Failure mode: many services have persistent `httpx.AsyncClient` done correctly, but there is no AST gate preventing new per-call clients or unclosed module clients. The 2026-04-29 crash came from an integration-service method mismatch; the same class of lifecycle contract drift is not structurally blocked.

Blast radius: 512 backend service surfaces per brief, 7 channel adapters, MCP clients.

Current detection: code review and ad hoc `rg`.

Current recovery: process restart if leaks become fatal; no automatic localizer.

Proposed fix: add `scripts/check_async_client_lifecycle.py` that flags `httpx.AsyncClient()` outside approved factories/context managers and verifies app shutdown closes module-level clients. Wire into `tests.yml` and `fly-deploy.yml` pre-deploy. File paths: `scripts/check_async_client_lifecycle.py`, `.github/workflows/tests.yml`, `.github/workflows/fly-deploy.yml`. Cell/Genoma: record each allowed exception with expiry.

Post-fix verification:

```bash
python scripts/check_async_client_lifecycle.py apps/backend-rag/backend
```

Before: no numeric gate. After: output is `0 violations`, or CI fails with file/line.

Severity: P1
Auto-implementable by Claude L2: yes

## 18. Frontend Service Worker caches authenticated API GET responses

Failure mode: `apps/mouth/public/sw.js:15-63` intercepts every same-origin GET under `/api/` and caches any `networkResponse.ok`. The Next proxy sets `Cache-Control: no-store` in `apps/mouth/src/app/api/[...path]/route.ts:272`, but the SW ignores that. Cache keys are URL-based, not user/session based. A user can receive stale or cross-session authenticated JSON after logout/login or auth changes.

Blast radius: 423 frontend API route files/handlers counted under `apps/mouth/src/app/api`, plus all proxied backend GETs under `/api/*`.

Current detection: none. Browser QA page-load tests do not test SW cache poisoning.

Current recovery: user clears site data or SW version changes from `v8`.

Proposed fix: only cache an explicit public allowlist, for example `/api/blog/*` or `/api/kbli/gold`, and never cache responses when `Authorization`, `Cookie`, or `Set-Cookie` is involved. Respect `Cache-Control: no-store`. Add a logout/session-switch purge message. File path: `apps/mouth/public/sw.js`. Cell/Genoma: record `mouth_sw_auth_cache_poisoning` scar.

Post-fix verification:

```bash
cd apps/mouth
npx playwright test tests/service-worker-auth-cache.spec.ts --project=chromium
```

Before: cached `/api/*` GET can be served while offline or after session switch. After: authenticated API GET returns network/503 and is never cached.

Severity: P1
Auto-implementable by Claude L2: yes

## 19. i18n provider placement can regress to a white screen

Failure mode: `useTranslation()` throws if no `I18nProvider` exists (`apps/mouth/src/i18n/index.tsx:74-77`). Providers exist in `(blog)`, `(book)`, `(workspace)`, and a few standalone pages, but root layout does not provide it globally. Scar: PR #273 i18n provider route-group white screen.

Blast radius: all route groups using translated components, especially public nav and workspace.

Current detection: some layout tests, but no global route-group provider invariant.

Current recovery: React error boundary can show a generic refresh message for some client paths; SSR/layout crashes can still white-screen.

Proposed fix: add a static test that scans TSX imports of `useTranslation` and proves the page belongs under an `I18nProvider` layout, or move provider to root if bundle impact is acceptable. File paths: `apps/mouth/src/i18n/index.tsx`, `apps/mouth/src/app/*/layout.tsx`, `apps/mouth/src/__tests__/i18n-provider-coverage.test.ts`. Cell/Genoma: save scar `mouth_i18n_provider_route_group`.

Post-fix verification:

```bash
cd apps/mouth
npx vitest run src/__tests__/i18n-provider-coverage.test.ts
npx playwright test smoke/page-load.spec.ts --project=chromium
```

Before: provider coverage unknown. After: every `useTranslation` route group is counted and protected.

Severity: P1
Auto-implementable by Claude L2: yes

## 20. SSO cookie logic has two setters and an unresolved Air escalation

Failure mode: `apps/mouth/src/app/api/auth/login/route.ts:36-68` manually builds `Set-Cookie`; the catch-all proxy also rewrites login cookies in `apps/mouth/src/app/api/[...path]/route.ts:292-337`. The middleware maps only `mail`, `calendar`, `drive`, `knowledge`, `prime`, `kita`, `my`, `zantara`, `visa`, and `tax` cases in `apps/mouth/src/middleware.ts`. Air escalation `air-a1-auth-surface` has been pending 11 days for `apps/web` SSO policy.

Blast radius: 8 subdomains in the brief, workspace login, portal login, satellite apps.

Current detection: `~/scripts/login-healthcheck.sh` probes `POST https://kita.balizero.com/api/auth/login` every 5-15 minutes and alerts after 2 failures. It does not cover every subdomain redirect or `apps/web`.

Current recovery: manual policy decision and code patch.

Proposed fix: create a single cookie helper used by both login routes and proxy route. Add a Playwright SSO matrix: `kita`, `my`, `mail`, `calendar`, `drive`, `knowledge`, `prime`, `zantara`, plus `apps/web` once Zero chooses policy. File paths: `apps/mouth/src/lib/auth/cookies.ts`, `apps/mouth/src/middleware.ts`, `apps/web/middleware.ts` if gating is chosen. Cell/Genoma: convert `air-a1-auth-surface` into a tracked Genome scar with deadline and selected policy.

Post-fix verification:

```bash
cd apps/mouth
npx playwright test tests/sso-subdomain-matrix.spec.ts --project=chromium
bash ~/scripts/login-healthcheck.sh
```

Before: 1 login endpoint checked; Air policy unresolved. After: 8+ subdomain auth paths quantified with pass/fail.

Severity: P1
Auto-implementable by Claude L2: no for `apps/web` policy, yes after Zero decision

## 21. Vercel build/runtime environment drift is not gated

Failure mode: `apps/mouth/next.config.ts` and proxy routes depend on `NUZANTARA_API_URL`, `NEXT_PUBLIC_API_URL`, `COOKIE_DOMAIN`, Sentry variables, and public URLs. There is no repo-local gate proving Vercel has the expected env matrix before deploy.

Blast radius: frontend routing, auth cookies, API proxy, Sentry, analytics, service worker behavior.

Current detection: Vercel build failure or user/browser probe after deploy.

Current recovery: manual Vercel env update and redeploy.

Proposed fix: add `scripts/vercel-env-check.mjs` with required/optional env schema and a Vercel workflow step or local `vercel env pull` comparison. File paths: `apps/mouth/env.schema.ts` or `scripts/vercel-env-check.mjs`, `.github/workflows/tests.yml`. Cell/Genoma: record env drift as `frontend_env_contract`.

Post-fix verification:

```bash
node scripts/vercel-env-check.mjs --app mouth --environment production --offline-schema
```

Before: env drift detected after failure. After: missing/changed env count fails deploy.

Severity: P2
Auto-implementable by Claude L2: yes for schema, no for reading live Vercel secrets in this sandbox

## 22. Post-deploy browser QA is not part of the deploy gate

Failure mode: `tests.yml` Playwright job runs local "page Page" tests only (`tests.yml:319-329`). `fly-deploy.yml` has no production browser flow. `scripts/post-deploy-verify.sh:98-127` only checks backend `/health` DB status.

Blast radius: production frontend, login, SSO, service worker, chat UI, route group white screens.

Current detection: manual browser QA or healthcheck login endpoint.

Current recovery: manual rollback/redeploy; Vercel auto-deploy may already be live.

Proposed fix: add a post-deploy production browser smoke script using Playwright/agent-browser: public home, `/kbli`, `kita` login, portal redirect, chat shell, service worker unregister/reload, console error threshold. File path: `apps/mouth/tests/prod-smoke.spec.ts`, `scripts/post-deploy-verify.sh`. Cell/Genoma: browser smoke failures emit `frontend.prod_smoke_failed`.

Post-fix verification:

```bash
cd apps/mouth
PLAYWRIGHT_BASE_URL=https://kita.balizero.com npx playwright test tests/prod-smoke.spec.ts --project=chromium
```

Before: 0 production browser assertions in deploy path. After: at least 6 route assertions and console-error count are reported.

Severity: P1
Auto-implementable by Claude L2: yes

## 23. Local LaunchAgents mostly do not restart on crash

Failure mode: local scan found 79 LaunchAgent plists; among Nuzantara/BaliZero/Cell/Garuda/OpenClaw/Claude-related labels, only 9 had `KeepAlive=true`, 45 had `KeepAlive=false`, and 16 had no `KeepAlive`. `~/scripts/launchagent-state-bridge.py` monitors only 5 labels in `UNMONITORED`.

Blast radius: 58 Sentinel jobs checked, 34 job registry entries, Mata Garuda jobs, War Room jobs, cost/disk/restart monitors, login healthcheck, DLQ autopilot. Critical local organs can fail until next schedule or forever if schedule is broken.

Current detection: Sentinel state files, job registry, launchagent bridge for 5 labels, logs.

Current recovery: partial. Some jobs have `restart_cmd`; many scheduled jobs just wait for next interval. `com.nuzantara.sentinel` itself reports `KeepAlive=false`.

Proposed fix: generate LaunchAgent registry from `scripts/automation_catalog.json` plus `~/.agent/decisions/job_registry.json`, require `KeepAlive` for daemons, `StartInterval` plus state heartbeat for one-shots, and monitor every Nuzantara-related plist. Expand `launchagent-state-bridge.py` from 5 labels to all local labels with explicit type metadata. Cell/Genoma: every LaunchAgent gets a Genome identity and last heartbeat.

Post-fix verification:

```bash
python scripts/check_launchagents_resilience.py
jq '.jobs_total,.jobs_circuit_open,.dlq_entries' ~/.agent/decisions/sentinel_status.json
```

Before: 5 bridged labels and 45 `KeepAlive=false`. After: 0 unclassified Nuzantara labels, daemon crash restarts automatically, one-shot failures enter DLQ with restart command.

Severity: P1
Auto-implementable by Claude L2: yes

## 24. Sentinel currently has open circuits and DLQ terminal work

Failure mode: `~/.agent/decisions/sentinel_status.json` reports 58 jobs checked, 16 circuit-open, 7 terminal, 54 DLQ entries, 0 healing actions in 24h. `circuit_breakers.json` local parse shows 16 OPEN. Open circuits cause Sentinel to skip jobs.

Blast radius: 28 percent open circuits per user brief; local file has 16 open circuits. A skipped job is a silent non-recovery state unless surfaced and retired.

Current detection: Sentinel status JSON and Telegram escalations.

Current recovery: stale circuits forced HALF_OPEN after 2h in `nuzantara-sentinel.py`, but many jobs have hundreds of failures. DLQ entries include `needs_aider`, `needs_claude_code`, and `TERMINAL`.

Proposed fix: make open-circuit count a P1 health metric. If `jobs_circuit_open > 0` for two Sentinel cycles, emit an Organism event and a Cell scar. Add automatic "safe retire or repair" classification for terminal DLQ: either disable the automation with owner-visible reason, or repair it. File paths: `scripts/nuzantara-sentinel.py`, `scripts/dlq_autopilot.py`, `scripts/system_doctor.py`. Genoma: terminal DLQ entries become scars with owners.

Post-fix verification:

```bash
python scripts/nuzantara-sentinel.py --once
jq '{open:.jobs_circuit_open, terminal:.jobs_circuit_terminal, healing:.healing_actions_24h}' ~/.agent/decisions/sentinel_status.json
```

Before: 16 open and 7 terminal can persist. After: every open/terminal has active repair, quarantine, or owner decision record.

Severity: P1
Auto-implementable by Claude L2: yes

## 25. Pro cannot currently verify Air recovery paths

Failure mode: session machine check showed Air `UNREACHABLE`. `shared/escalations_air.jsonl` contains unresolved `air-a1-auth-surface` HIGH escalation. Sentinel has Air dead-man logic, but Pro cannot confirm Air state when SSH is down.

Blast radius: Air 16GB server-H24 role, Drive polling, OAuth/token watchdogs, cron jobs, `apps/web` SSO issue, Pro/Air sync architecture.

Current detection: session-start peer check and shared escalation file if synced.

Current recovery: manual network/SSH investigation.

Proposed fix: bidirectional heartbeat independent of SSH: each machine writes a signed small heartbeat to shared sync plus local Redis/JSONL, and each side alerts if peer heartbeat age exceeds threshold. Include git HEAD, branch, LaunchAgent counts, circuit counts. File paths: `scripts/pro_air_heartbeat.py`, `docs/PRO_AIR_CONNECTION.md`, `scripts/system_doctor.py`. Cell/Genoma: heartbeat facts are Cells, not ad hoc session checks.

Post-fix verification:

```bash
python scripts/pro_air_heartbeat.py --check
cat shared/heartbeats/pro.json shared/heartbeats/air.json | jq '.host,.git_head,.age_seconds'
```

Before: peer unreachable blocks sync confidence. After: heartbeat age and git head mismatch are quantified even when SSH fails.

Severity: P1
Auto-implementable by Claude L2: yes on Pro side, no for Air install while Air unreachable

## 26. Cell has launchd restart but weak crash-loop and alert handling

Failure mode: `apps/cell/com.cell.organism.plist` and installed `com.cell.organism` use `KeepAlive=true`, so process death restarts. But `apps/cell/scripts/launch_cell.sh:8-13` exits if `.env` is missing; `cell/main.py` logs Telegram disabled if env is missing and continues. Redis/Ollama/DB init failures before the pulse loop can cause a launchd crash loop with only local logs.

Blast radius: Cell nervous system, pulse loop, safety gate, LTM/episodic memory, Dreamer/Journal, all proposed Genoma scars.

Current detection: local log, launchd, maybe Cell widget if backend can read status. Not all failures enter Sentinel.

Current recovery: launchd restarts process; no automatic fix for missing env/Redis/Ollama.

Proposed fix: add a minimal external Cell heartbeat checker in Sentinel and System Doctor. If Cell restarts >N times or heartbeat stale >2 intervals, use `LocalEffector`/launchctl restart or raise Telegram plus local outbox. Add a preflight that writes a health record before heavy init. File paths: `apps/cell/cell/main.py`, `apps/cell/scripts/launch_cell.sh`, `scripts/system_doctor.py`. Genoma: Cell writes its own crash-loop scar locally before full startup.

Post-fix verification:

```bash
launchctl kickstart -k gui/$(id -u)/com.cell.organism
python scripts/check_cell_heartbeat.py
```

Before: crash loop can be log-only. After: heartbeat stale and restart count are first-class numbers.

Severity: P1
Auto-implementable by Claude L2: yes

## 27. Organism supervisor is still shadow/uninstalled relative to design

Failure mode: `apps/organism/organism/supervisor/daemon.py` documents W1 shadow mode and logs decisions; active dispatch is not implemented at lines 124-128. Repo has launchd plists under `apps/organism/organism/launchd`, but local `~/Library/LaunchAgents` list did not show `com.nuzantara.organism.supervisor`; only `com.cell.organism` was present.

Blast radius: the autonomic layer promised in `AUTONOMOUS_OPS.md` and design spec. Guardians still do local ad hoc repair; no active centralized event-to-actuator recovery.

Current detection: Redis heartbeat if supervisor runs; System Doctor fallback writes emergency-mode key if absent.

Current recovery: local guardians continue, but Wave 2 active self-healing is not live.

Proposed fix: install the supervisor LaunchAgent, keep `ORGANISM_SHADOW_MODE=true` until 24h clean, then activate only safe actuators (`restart-agent`, `cleanup-log`, `notify-telegram`). Add `/stats` to report real processed counts instead of placeholder. File paths: `apps/organism/organism/supervisor/daemon.py`, `apps/organism/organism/control_panel.py`, LaunchAgent install docs. Cell/Genoma: supervisor heartbeat becomes a Cell, and inactive shadow mode is recorded as an explicit maturity state.

Post-fix verification:

```bash
launchctl list | rg 'com.nuzantara.organism.supervisor'
redis-cli GET organism:supervisor:heartbeat
tail -n 5 ~/logs/organism/decisions.jsonl
```

Before: supervisor absent/shadow. After: heartbeat age <300s and decisions count increases.

Severity: P1
Auto-implementable by Claude L2: yes for repo/install script, no for turning active mode without observation window

## 28. Mata Garuda local OSINT jobs are not uniformly supervised

Failure mode: many Mata Garuda plists exist (`com.matagaruda.*`, `com.garuda.*`), mostly `KeepAlive=false` or missing. The app has local data stores (`apps/mata-garuda/data/knowledge.db`, `sentinel_cell.db`) and HGT/Redis stream components, but launchd/state coverage is inconsistent.

Blast radius: OSINT harvesters, knowledge graph workers, gap consumer, public channel, daily briefing, NLM expansion. Law 2 says OSINT data never leaves Pro, so cloud fallback is not allowed.

Current detection: per-job logs, some Sentinel jobs, some LaunchAgent state bridge coverage.

Current recovery: next scheduled run or manual kickstart.

Proposed fix: keep OSINT raw data local, but publish sanitized health events to `organism:events` and Cell HGT. Every Mata Garuda plist gets job registry metadata, state file, and restart/kickstart command. File paths: `apps/mata-garuda/scripts/*.sh`, `mata_garuda/cell/runner.py`, `~/scripts/launchagent-state-bridge.py`. Genoma: only skills/scars/health, never raw OSINT content, are inherited.

Post-fix verification:

```bash
python scripts/check_mata_garuda_supervision.py
find ~/.agent/decisions/state -name 'matagaruda*.last.json' | wc -l
```

Before: only partial state files. After: every Mata Garuda LaunchAgent has a heartbeat or declared exemption.

Severity: P2
Auto-implementable by Claude L2: yes

## 29. MCP servers have no independent restart/readiness layer

Failure mode: `.mcp.json` configures `nuzantara-mcp` 115 tools, `nuzantara-mcp-advanced` 14 tools, and browser MCP 6 tools. MCP readiness check in this session reported primary MCP configured but unreachable and advanced not available. Primary server uses a persistent httpx client (`apps/nuzantara-mcp/nuzantara_mcp/server.py:35-58`) but no lifespan close or external supervisor. `.mcp.json` also contains literal secrets, making secret rotation and leakage a resilience issue.

Blast radius: 115 + 14 + 6 tool surfaces, guided workflows, Google/Drive/comms/admin operations.

Current detection: `python3 ~/.codex/mcp_readiness_check.py` manually.

Current recovery: MCP client restarts subprocess when invoked, but no proactive health/restart, no Cell record.

Proposed fix: move secrets from `.mcp.json` into env/secret files, add `scripts/mcp_readiness_gate.py`, and register MCP readiness in System Doctor and Cell. Add FastMCP lifespan shutdown to close `_http_client`. File paths: `.mcp.json` template, `apps/nuzantara-mcp/nuzantara_mcp/server.py`, `scripts/system_doctor.py`. Genoma: `mcp_server_unreachable` scar with per-server tool count.

Post-fix verification:

```bash
python3 ~/.codex/mcp_readiness_check.py
python scripts/mcp_readiness_gate.py --expect nuzantara-mcp,nuzantara-mcp-advanced,nuzantara-browser
```

Before: readiness is manual and failed in this session. After: readiness is a scheduled, alerting, counted check.

Severity: P1
Auto-implementable by Claude L2: yes, except secret rotation needs operator handling

## 30. System Doctor misses several failure classes by downgrading them to OK/warning

Failure mode: `scripts/system_doctor.py` treats some collector failures as OK or warning: backend unreachable can be "cold/sleeping", Dependabot/token/log fetch failures can return OK, frontend checks are HTTP/body-size only, and browser white screens are not detected. It runs at 08:00 per brief but is not a complete recovery oracle.

Blast radius: backend health, frontend route groups, logs, Dependabot/security, cron-agent observations.

Current detection: daily report and some auto-fixes.

Current recovery: limited auto-fixes (reset OpenClaw consecutive errors, chmod, log rotate). It does not restart backend/frontend or repair most root causes.

Proposed fix: split collector result states into `ok`, `warn`, `unknown`, `critical`; unknown must not be counted as ok. Add browser canary results, Sentinel circuit counts, MCP readiness, Cell heartbeat, and LaunchAgent unclassified count. File path: `scripts/system_doctor.py`. Cell/Genoma: every "unknown" repeated twice becomes a Cell curiosity/repair task.

Post-fix verification:

```bash
python scripts/system_doctor.py --json > /tmp/doctor.json
jq '.summary | {critical,warn,unknown}' /tmp/doctor.json
```

Before: skipped collectors can report ok. After: skipped collectors are counted as unknown and trigger recovery/escalation.

Severity: P1
Auto-implementable by Claude L2: yes

## 31. Telegram alerting is a single notification path with cooldown blind spots

Failure mode: `scripts/sentinel_lib/alerter.py` returns false or prints locally if Telegram token/chat is missing. Alert dedup/cooldowns are active: 40 escalation cooldowns local. `~/scripts/login-healthcheck.sh` and `fly-restart-loop-detector.sh` also silently continue if Telegram credentials are missing or Telegram POST fails.

Blast radius: all human escalation paths, including Zero last-resort decisions.

Current detection: local logs; no guaranteed secondary channel.

Current recovery: none if Telegram is down or credentials are missing.

Proposed fix: implement `AlertOutbox`: write every alert to local JSONL first, then Telegram, then optional email to `healthcheck@balizero.com` or owner mailbox if Telegram fails. Add a cooldown digest every N hours summarizing still-open alerts instead of suppressing indefinitely. File paths: `scripts/sentinel_lib/alerter.py`, shell scripts in `~/scripts` mirrored into repo, `scripts/system_doctor.py`. Genoma: every suppressed alert remains queryable as a scar/fact.

Post-fix verification:

```bash
TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= python scripts/tests/test_alert_outbox.py
tail -n 1 ~/.agent/decisions/alert_outbox.jsonl
```

Before: alert can vanish into logs. After: every alert has a durable local outbox row and delivery status.

Severity: P1
Auto-implementable by Claude L2: yes

## 32. Login healthcheck covers one endpoint, not the full auth surface

Failure mode: `~/scripts/login-healthcheck.sh` probes only `POST https://kita.balizero.com/api/auth/login` and checks token presence. It does not load protected pages, SSO subdomains, portal role redirects, service worker cache, or `apps/web`.

Blast radius: 8 subdomains, client portal, workspace, satellites, one active Air HIGH escalation.

Current detection: 2 consecutive login endpoint failures.

Current recovery: Telegram alert only.

Proposed fix: turn login healthcheck into a Playwright auth journey using `healthcheck@balizero.com`: login, visit `/dashboard` or role-appropriate page, verify cookie attributes, visit SSO subdomains, logout, verify no stale SW data. File path: new `apps/mouth/tests/prod-login-journey.spec.ts` and wrapper script. Cell/Genoma: auth journey failures become `auth_surface` scars with subdomain name.

Post-fix verification:

```bash
HEALTHCHECK_EMAIL=... HEALTHCHECK_PIN=... npx playwright test apps/mouth/tests/prod-login-journey.spec.ts
```

Before: 1 HTTP endpoint. After: at least 8 browser auth assertions.

Severity: P1
Auto-implementable by Claude L2: yes, but needs existing healthcheck credentials in local secrets

## 33. Fly restart-loop detector does not prove restart count or auto-remediate

Failure mode: `~/scripts/fly-restart-loop-detector.sh` checks `nuzantara-rag` and `nuzantara-postgres` started/unhealthy states, with `nuzantara-qdrant` explicitly suspended. It sets `RESTART_THRESHOLD=10`, but the shown code does not parse Fly events to calculate restarts in the last hour.

Blast radius: Fly backend and Postgres. Qdrant is cloud-backed via secret now, but any future local qdrant app state is excluded.

Current detection: status/unhealthy checks every 15 minutes, Telegram cooldown 30 minutes.

Current recovery: alert only; no rollback, scale, or Cell action.

Proposed fix: parse `fly events` or GraphQL machine events and persist restart counts per machine. If restarts exceed threshold, emit Organism event, freeze deploys, and run a safe rollback if last deploy is inside window and health is failing. File path: repo copy of `scripts/fly-restart-loop-detector.sh` or `scripts/fly_restart_loop_detector.py`. Cell/Genoma: record `fly_restart_loop:<machine_id>`.

Post-fix verification:

```bash
bash ~/scripts/fly-restart-loop-detector.sh
jq '.apps["nuzantara-rag"].restart_count_1h' ~/.agent/decisions/fly_restart_monitor.json
```

Before: restart threshold constant unused. After: restart count is a number and drives escalation/recovery.

Severity: P2
Auto-implementable by Claude L2: yes

## 34. Fly deploy health gate is too shallow and RAG smoke is non-blocking

Failure mode: `.github/workflows/fly-deploy.yml:258-309` passes deploy when `/health` contains `"healthy"`. RAG smoke is informational and `continue-on-error=true`. `scripts/post-deploy-verify.sh:98-127` only requires HTTP 200 and `.database.status == connected`.

Blast radius: backend RAG, auth, channels, Qdrant, KG, pricing, visa/business answers.

Current detection: health and non-blocking smoke.

Current recovery: automatic rollback only if basic health fails.

Proposed fix: make a deploy readiness matrix: `/health`, `/health/ready`, login probe, RAG smoke with known answer shape, Qdrant collection count floor, DB migration pending count, one channel DLQ count. Block deploy on critical matrix failure. File paths: `.github/workflows/fly-deploy.yml`, `scripts/post-deploy-verify.sh`, new `scripts/backend_prod_smoke.py`. Cell/Genoma: failed deploy matrix writes a scar with failed row.

Post-fix verification:

```bash
python scripts/backend_prod_smoke.py --base-url https://nuzantara-rag.fly.dev --strict
```

Before: RAG failure does not fail deploy. After: strict smoke nonzero blocks or rolls back.

Severity: P1
Auto-implementable by Claude L2: yes

## 35. CI test gates mask schema drift with `create_all()`

Failure mode: `tests.yml:111-131` bootstraps SQLModel tables with `scripts/ci_bootstrap_schema.py` because some base tables have no migration file. This can hide production migration gaps: tests pass because CI creates schema outside the migration path.

Blast radius: DB-backed routers and services; migrations v2 source-of-truth discipline.

Current detection: migration-lint for SQL v2 and runtime migration manager.

Current recovery: manual migration creation when prod fails.

Proposed fix: add a "migration-only schema" CI job that starts from empty Postgres and applies only SQL v2 plus approved legacy bootstrap, then runs schema invariant tests. Any table created by models but absent from migrations fails. File paths: `scripts/ci_bootstrap_schema.py`, `backend/tests/db/test_schema_from_migrations.py`. Genoma: schema drift is a scar class.

Post-fix verification:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/db/test_schema_from_migrations.py -q
```

Before: create_all can mask missing migration. After: migration-only schema has expected table/column counts.

Severity: P1
Auto-implementable by Claude L2: yes

## 36. Squawk migration lint has no bypass ledger

Failure mode: `.github/workflows/migration-lint.yml` uses Squawk for changed SQL files, but there is no repo gate that counts `squawk-ignore` comments or requires a reason/expiry. `version: latest` also makes lint behavior temporally unstable.

Blast radius: 30 SQL v2 migrations and future migrations.

Current detection: PR lint if migration file changed.

Current recovery: manual review.

Proposed fix: pin Squawk version and add `scripts/check_squawk_ignores.py` requiring `squawk-ignore <rule> -- reason=<...> -- expires=<date>`. File path: `.github/workflows/migration-lint.yml`. Cell/Genoma: expired bypasses become scars.

Post-fix verification:

```bash
python scripts/check_squawk_ignores.py apps/backend-rag/backend/db/migrations_v2
```

Before: bypass count unknown. After: bypass count is 0 or all have reasons/expiry.

Severity: P2
Auto-implementable by Claude L2: yes

## 37. Langfuse/OpenLLMetry is dormant by default

Failure mode: `backend/core/observability.py:37-54` disables Langfuse when keys are missing or `LANGFUSE_ENABLED=false`. This is safe for cost/PII, but it means RAG/LLM failures can lack traces unless manually activated. PR #312 is documented as dormant.

Blast radius: RAG, tool routing, confidence scoring, LLM fallback/retry paths.

Current detection: logs and user reports.

Current recovery: manually set Langfuse keys and ask for reproduction.

Proposed fix: activate privacy-safe metrics-only tracing for errors, ABSTAIN/CAUTIOUS responses, timeouts, and tool failures with `LANGFUSE_TRACE_LLM_MESSAGES=false`. Keep raw messages hidden. File path: `backend/core/observability.py` plus confidence/router instrumentation. Cell/Genoma: low-confidence traces create learning events without raw PII.

Post-fix verification:

```bash
flyctl ssh console --app nuzantara-rag --command 'python -c "from backend.core.observability import is_enabled; print(is_enabled())"'
```

Before: tracing disabled when keys absent. After: if keys are configured, trace count for error/low-confidence paths is >0 and message content hidden.

Severity: P2
Auto-implementable by Claude L2: yes for code, no for setting production secrets

## 38. Restore drill exists but restore recency is not in local health

Failure mode: `.github/workflows/restore-drill.yml` runs monthly and alerts Telegram. Local System Doctor/Cell health does not appear to include last successful restore drill age. A failed or skipped monthly workflow could leave backups unproven until someone checks GitHub.

Blast radius: Postgres disaster recovery.

Current detection: GitHub Actions and Telegram on failure.

Current recovery: manual restore investigation.

Proposed fix: write restore drill result to a small artifact or repo/secret-backed status endpoint consumed by System Doctor and Cell. Alert if last successful drill age >35 days. File paths: `.github/workflows/restore-drill.yml`, `scripts/system_doctor.py`, `apps/cell/cell/sensors/backup_sensor.py`. Genoma: restore drill pass/fail becomes a memory.

Post-fix verification:

```bash
python scripts/system_doctor.py --json | jq '.checks.restore_drill'
```

Before: restore age absent locally. After: age days and last run URL are visible.

Severity: P2
Auto-implementable by Claude L2: yes

## 39. Secret rotation can crash services without preflight

Failure mode: backend, frontend, MCP, Cell, and local scripts all depend on env/secrets. `.mcp.json` currently contains literal API keys instead of env references. `launch_cell.sh` exits on missing `.env`; login healthcheck exits 78 on missing credentials. A rotated/missing secret can turn into a crash loop or silent disabled alerting.

Blast radius: backend auth/RAG/Qdrant/Redis, MCP 135 total tools, Cell, Telegram alerts, healthcheck account.

Current detection: startup logs, failed readiness checks, manual secret checks.

Current recovery: manual secret repair.

Proposed fix: create a non-secret schema inventory: `config/required_secrets.schema.json` with per-surface required/optional, validators that only check presence/shape, and per-surface preflight commands. Replace literal values in MCP config with env refs. File paths: `.mcp.json.example`, `scripts/check_secrets_shape.py`, `fly-secrets-check.yml`, Cell launch wrapper. Genoma: secret class failures become scars without values.

Post-fix verification:

```bash
python scripts/check_secrets_shape.py --surface backend --surface mcp --surface cell --redacted
```

Before: missing/invalid secret discovered at runtime. After: redacted preflight fails before deploy/start.

Severity: P1
Auto-implementable by Claude L2: yes, except rotating/removing exposed secret values needs operator action

## 40. Open structural cicatrix summary

The highest-risk recovery gaps to fix first, in order:

1. Make backend startup failure return HTTP 503 from `/health`.
2. Move SQL v2 migration apply to post-new-image in the same deploy run.
3. Add durable inbound queues for WhatsApp and Instagram before HTTP 200.
4. Replace PG/in-process EventBus delivery with Redis Streams plus DLQ and local mirror.
5. Make router registration manifest-driven.
6. Add supervised restart loops for backend long-lived tasks.
7. Expand LaunchAgent/Sentinel coverage so all local organs are classified and every open circuit has a repair/quarantine path.
8. Remove authenticated API caching from the service worker.
9. Install and monitor Organism supervisor, then activate only safe actuators after a clean shadow window.
10. Upgrade deploy verification from basic `/health` to backend plus browser plus auth plus RAG matrix.

All proposed fixes preserve graceful degradation by avoiding a new single point of failure: every centralizing change includes local fallback, queue replay, or explicit degraded state. Cell + Genoma are included as the memory/safety layer for each durable fix rather than as a blocking orchestrator.
