# Codex GPT-5.5 - Zero-Crash Resilience Audit

Date: 2026-04-29
Machine: Pro (`nuzantara@Nuzantara`)
Scope: empirical filesystem and CLI audit from `/Users/nuzantara/Desktop/nuzantara`, branch `main`

## Startup Constraints And Evidence Limits

- Pro/Air check: Pro confirmed. Air was unreachable over SSH during this run, so remote git sync could not be verified. Local HEAD: `720d54f5c fix(crm/drive-poll): add missing get_file_metadata to ServiceAccountDriveService`.
- MCP readiness: only Playwright was reachable in this sandbox. `nuzantara-mcp`, `nuzantara-mcp-advanced`, `postgres`, `qdrant-readonly`, `github`, and `sentry` were not reachable here. The audit therefore uses native filesystem and CLI evidence first, as required by the Nuzantara hierarchy.
- No off-limits files were edited or proposed as primary edit targets: `apps/backend-rag/backend/prompts/zantara_core.py`, `apps/backend-rag/fly.toml`, `.env.production`, `alembic/env.py`.
- Local count drift is itself a resilience smell: local scan saw 26 app directories, 5 packages, 140 backend router files, 607 service files, 25 workflow files. The brief says 27 apps, 5 packages, 139 routers, 512 services. Do not use docs-only counts as health gates.

## Highest-Risk Patch Order

1. Fix backend `/health` so `startup_failed=True` returns HTTP 503. Today a failed critical startup can keep returning 2xx and block Fly auto-restart.
2. Fix channel optimization imports so the DLQ retry loop and deduplicator actually use the objects created by `initialize_optimizations()`.
3. Move SQL v2 migrations to a post-deploy rerun after the new image is live, closing PR #307 permanently.
4. Make Cell classify semantic health, not just HTTP 200, and connect Cell decisions/scars to `packages/cell-core` Genome.
5. Reconcile LaunchAgents, Organism, and automation registry so the local recovery plane itself has restart guarantees.

---

## Surface 1 - Backend `/health` Masks Critical Startup Failure

- **Failure mode:** `apps/backend-rag/backend/app/setup/app_factory.py` catches critical `RuntimeError` from service initialization, sets `app.state.startup_failed=True`, and returns. `apps/backend-rag/backend/app/routers/health.py` defines `_check_startup_failed()`, but `health_check()` does not call it before returning `healthy` or `initializing`. A broken RAG process can therefore remain HTTP 200 instead of triggering Fly restart. Scar link: PR #307 and previous startup/import cicatrices prove bad deploy states can remain live.
- **Blast radius:** 100% of the RAG process; user-facing RAG, KBLI, CRM RAG, KG, and channel flows can be down while `/health` is green. Local scope: 140 router files and 607 service files depend on app startup truth.
- **Current detection:** Post-deploy health greps `"healthy"` in `.github/workflows/fly-deploy.yml`; Cell `PulseEngine` treats `reachable && status_code == 200` as green. Neither sees `startup_failed` if the endpoint stays 200.
- **Current recovery:** Fly auto-restart only happens on crash or non-2xx health. Current path can avoid both.
- **Proposed fix:** File path: `apps/backend-rag/backend/app/routers/health.py`. Conceptual diff: call `_check_startup_failed(request.app)` at the top of `health_check()` before search-service warmup logic; if present, set `response.status_code = 503` and return `HealthResponse(status="unhealthy", message="startup_failed: ...")`. Add a unit test in `apps/backend-rag/backend/tests/app/routers/test_health_startup_failed.py`. Cell/Genome reference: add Genome scar `backend_health_startup_failed_503` and a Cell HealthSensor rule that treats body status `startup_failed`, `unhealthy`, or `degraded` as non-green even when HTTP is 200.
- **Post-fix verification:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/app/routers/test_health_startup_failed.py -q`. Before: simulated `startup_failed=True` can still be hidden by 2xx health. After: HTTP 503 and Cell red/yellow classification.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes

## Surface 2 - Cell Health Triage Trusts HTTP 200 Over Semantic Body

- **Failure mode:** `apps/cell/cell/sensors/health_sensor.py` returns body but does not classify it. `apps/cell/cell/core/pulse.py` sets HTTP status green solely when `reading.reachable and reading.status_code == 200`. This misses semantic failures such as `"status":"startup_failed"`, `"status":"initializing"` forever, or partial dependency death.
- **Blast radius:** Cell is the nervous system. If it reads false green, automatic restart/alert decisions are suppressed for backend, DB, Qdrant, Vercel, and cron sensors. Current sentinel snapshot: 58 jobs total, only 10 healthy, 16 circuit breakers open, 54 DLQ entries.
- **Current detection:** Secondary DB/Qdrant sensors inspect body subsets, but the primary HTTP green path is too coarse.
- **Current recovery:** Cell may choose no action because the primary health signal is green.
- **Proposed fix:** File paths: `apps/cell/cell/sensors/health_sensor.py`, `apps/cell/cell/core/pulse.py`. Conceptual diff: add a `semantic_status` field to `HealthReading`; map body `status` to green/yellow/red; make `PulseEngine` aggregate semantic status before HTTP 200. Cell/Genome reference: wire `PulseEngine` to `packages/cell-core` Genome so every auto-restart and false-positive correction records `record_skill()` or `record_scar()`.
- **Post-fix verification:** `cd apps/cell && pytest tests/test_pulse.py -q` plus a new fixture where `/health` returns HTTP 200 with `{"status":"startup_failed"}`. Before: green. After: red and action candidate `restart_service`.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes

## Surface 3 - Cell Fly Effector Can Restart The Wrong Machine And Leaks Clients

- **Failure mode:** `apps/cell/cell/effectors/fly_effector.py` restarts the first running Fly machine only. With two Fly machines, the unhealthy machine may not be first. The class docstring says "instantiate once, reuse across pulses", but each action opens a new `httpx.AsyncClient`.
- **Blast radius:** Fly `nuzantara-rag` currently has 2 machines. A single bad machine can stay bad while Cell restarts a healthy sibling; repeated pulses can create extra HTTP client churn.
- **Current detection:** Fly status and Cell pulse logs only; no machine-specific health correlation.
- **Current recovery:** Best effort restart of `machines[0]`, not targeted restart of the failing instance.
- **Proposed fix:** File path: `apps/cell/cell/effectors/fly_effector.py`. Conceptual diff: create one persistent client on the effector; add `restart_machine(machine_id: str)`; teach HealthSensor/FlySensor to map failing health-check instance to machine ID where possible; otherwise restart one unhealthy/non-responding machine, not the first started machine. Cell/Genome reference: record a Genome skill for successful targeted restart and a scar when restart target selection is ambiguous.
- **Post-fix verification:** Add a unit test with two fake machines where the second is unhealthy. Before: restart call targets index 0. After: target is the unhealthy machine ID. Command: `cd apps/cell && pytest tests/test_fly_effector.py -q`.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 4 - Channel DLQ Retry Loop Never Starts After Initialization

- **Failure mode:** `apps/backend-rag/backend/app/setup/service_initializer.py` imports `delivery_manager` by value before `initialize_optimizations()`. `initialize_optimizations()` then mutates the module global, but the local imported binding remains `None`. Result: `if delivery_manager and db_pool:` is false and `start_retry_loop()` is never called.
- **Blast radius:** 7 channels are affected: WhatsApp, Telegram, Instagram, Twitter/X, web, GChat, Slack. Failed outbound messages can be persisted but not retried. Local sentinel already shows 54 DLQ entries, 7 terminal.
- **Current detection:** Logs can say channels are ready; no startup assertion that `_retry_task` exists. There is no Cell sensor for channel DLQ backlog.
- **Current recovery:** Manual DLQ inspection/replay only.
- **Proposed fix:** File path: `apps/backend-rag/backend/app/setup/service_initializer.py`. Conceptual diff: replace `from backend.channels.optimizations import delivery_manager, initialize_optimizations` with `import backend.channels.optimizations as channel_opt`; call `channel_opt.initialize_optimizations(db_pool=db_pool)`, then `if channel_opt.delivery_manager and db_pool: await channel_opt.delivery_manager.start_retry_loop(...)`. Cell/Genome reference: emit `organism:events` when DLQ retry loop starts/stops and record Genome scar `channel_dlq_retry_loop_stale_import`.
- **Post-fix verification:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_delivery_retry_loop.py -q`. Before: retry task absent after init. After: retry task present and DLQ entries decrease on fake adapter success.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes

## Surface 5 - Channel Deduplicator Is Also A Stale Import

- **Failure mode:** `apps/backend-rag/backend/channels/router.py` imports `message_deduplicator` by value at module import time. `initialize_optimizations()` later assigns the real deduplicator in the module global, but the router keeps the original `None`. Duplicate webhook deliveries can be processed twice.
- **Blast radius:** All active incoming channel webhooks. This can duplicate inbound DB rows, trigger duplicate AI responses, double-send WhatsApp/Telegram/Instagram messages, and inflate escalation/cooldown noise.
- **Current detection:** No runtime assertion. Duplicates show up as symptoms in conversation history or provider rate limits.
- **Current recovery:** None; human cleanup or downstream idempotency if present.
- **Proposed fix:** File path: `apps/backend-rag/backend/channels/router.py`. Conceptual diff: import the module, not the variable, or inject the deduplicator into `ChannelRouter` after initialization. Use `optimizations.message_deduplicator` at routing time. Cell/Genome reference: Cell channel sensor should count duplicate drops per channel; Genome records dedup false-negative scars.
- **Post-fix verification:** Add a test that initializes optimizations after importing `ChannelRouter`, sends the same message twice, and asserts the second route exits before persistence. Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_router_dedup.py -q`.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes

## Surface 6 - Delivery Manager Has No Disk Spool When DB And Redis Are Both Down

- **Failure mode:** Channel send failures can be persisted to DB or Redis-backed structures, but if both persistence layers are unavailable the message is logged as lost. That is graceful degradation for process survival, not for customer communication recovery.
- **Blast radius:** All outbound channel replies and notifications during DB+Redis outage. With 7 channels, one outage can lose customer-visible responses irreversibly.
- **Current detection:** Log-only, and only if logs are retained. No `organism:events` DLQ terminal event.
- **Current recovery:** None.
- **Proposed fix:** File path: `apps/backend-rag/backend/channels/optimizations.py`. Conceptual diff: add append-only JSONL disk spool under `/data/channel_spool/` on Fly when DB/Redis persist fails; add bounded replay on startup and a spool-size health metric. Cell/Genome reference: Cell reads spool count from `/api/cell/metrics`; Genome records `channel_spool_replay_success` as skill.
- **Post-fix verification:** Integration test with fake DB and Redis failures; assert JSONL spool gets one record and replay removes it after DB recovers. Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_delivery_spool.py -q`.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes

## Surface 7 - SQL v2 Migrations Still Run On Old Image

- **Failure mode:** `.github/workflows/fly-deploy.yml` runs `python -m backend.db.migrate apply-all` before `flyctl deploy`. `flyctl ssh console` executes inside the currently deployed image, so new SQL migration files in the commit are invisible. Scar: PR #307.
- **Blast radius:** Any route that expects new schema can throw 500s after deploy. Worst case: 100% of backend paths touching the changed table. Restart cannot fix because the database remains unmigrated.
- **Current detection:** Production errors such as missing columns/tables; manual rerun of workflow after merge.
- **Current recovery:** Manual `gh workflow run` after merge. This violates the 2026-04-30 zero-crash goal.
- **Proposed fix:** File path: `.github/workflows/fly-deploy.yml`. Conceptual diff: keep pre-deploy migration status as informational, but add `run-sql-v2-migrations-post-deploy` after the new image is live and before final post-deploy health. Use a generic image readiness sentinel (`python -m backend.db.migrate status` from new image), then run `python -m backend.db.migrate apply-all`. Cell/Genome reference: emit a migration event with image SHA and applied count; Genome records PR #307 closure scar.
- **Post-fix verification:** Create a harmless test SQL migration in a branch and confirm post-deploy logs show the new migration name on first run. Command: `gh workflow run fly-deploy.yml -f dry_run_migration_probe=true` after adding a safe workflow-dispatch input. Before: new SQL not visible pre-deploy. After: visible post-deploy.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes

## Surface 8 - Migration Tracking Split Can Lie About Applied State

- **Failure mode:** SQL migration manager and Python-style migrations use different tracking tables/paths (`_schema_versions` versus `schema_migrations` patterns in local code). Status can say clean while another runner re-applies or skips incorrectly.
- **Blast radius:** 30 SQL v2 migrations per brief, plus Python-idiom migrations 119-122+ and legacy migration files. Any mismatch can produce schema drift across all DB-backed surfaces.
- **Current detection:** `Check migration status` in deploy is informational and continues on error.
- **Current recovery:** Manual DB inspection and manual migration.
- **Proposed fix:** File paths: `apps/backend-rag/backend/db/migrate*.py`, `apps/backend-rag/backend/migrations/*`, tests under `apps/backend-rag/backend/tests/db/`. Conceptual diff: create one canonical migration ledger view/table and a compatibility bridge that backfills both old ledgers into the canonical one; deploy gate fails on split-brain state. Cell/Genome reference: Cell migration sensor compares ledger count and latest ID; Genome records migration anomalies as scars.
- **Post-fix verification:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/db/test_migration_ledger_consistency.py -q`. Before: two ledgers can disagree. After: one canonical count and latest ID.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 9 - Router Manifest Does Not Drive Actual Router Registration

- **Failure mode:** `apps/backend-rag/backend/app/setup/router_manifest.py` is documented as canonical, but `router_registration.py` still manually imports/includes routers. Example: `team_members` is documented disabled in the manifest comments but still appears in `include_light_routers()` include path.
- **Blast radius:** 139/140 router surface can diverge between tests and production process groups. Scar link: PR #54/#55/#60 missed route registration for Cell endpoints.
- **Current detection:** Manifest tests only verify the manifest; they do not prove the app actually registers only manifest entries.
- **Current recovery:** Manual discovery when a route 404s or duplicates.
- **Proposed fix:** File paths: `apps/backend-rag/backend/app/setup/router_registration.py`, `apps/backend-rag/backend/app/setup/router_manifest.py`, `apps/backend-rag/backend/tests/setup/test_router_manifest.py`. Conceptual diff: iterate `routers_for_group("api"|"rag"|"both")` for registration; import `RouterEntry.import_path`, `attr`, and `prefix` dynamically; keep only true special cases outside the manifest with explicit tags. Cell/Genome reference: Cell route canary compares `/openapi.json` route count to manifest count; Genome records route drift scars.
- **Post-fix verification:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py backend/tests/setup/test_router_registration_matches_manifest.py -q`. Before: a disabled router can still be included. After: disabled routers absent from app routes.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 10 - Background Tasks Can Die Silently After Startup

- **Failure mode:** `app_factory.py` starts workflow queue, legal ingestion, EventBus listener, DB health loop, and Redis listener with `asyncio.create_task()` but not all tasks use the shared `backend/services/common/background.py::spawn()` pattern or a restart supervisor. A task exception can stop the worker while the HTTP app remains healthy.
- **Blast radius:** Workflow queue, legal ingestion, practice status listener, EventBus, and health loops can stop independently. This affects CRM workflows, KG/legal ingestion, and event-driven recovery.
- **Current detection:** Logs only unless a downstream stale job sensor catches it later.
- **Current recovery:** Process restart may recreate tasks, but no automatic restart of the failed task itself.
- **Proposed fix:** File paths: `apps/backend-rag/backend/app/setup/app_factory.py`, `apps/backend-rag/backend/app/setup/service_initializer.py`, `apps/backend-rag/backend/services/common/background.py`. Conceptual diff: wrap every long-running task in a supervisor that records failures, applies bounded restart with jitter, marks service_registry degraded after N failures, and emits an `organism:events` record. Cell/Genome reference: Genome stores worker crash scars with task name and exception class.
- **Post-fix verification:** Inject a failing fake worker; assert it restarts once and then marks degraded after threshold. Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/setup/test_background_supervisor.py -q`.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 11 - EventBus Violates Redis Streams Law And Loses Events

- **Failure mode:** `apps/backend-rag/backend/services/events/event_bus.py` uses PostgreSQL LISTEN/NOTIFY plus in-process handlers, not Redis Streams. PG NOTIFY is volatile; events published while listener is down are lost. Handler failures are logged but not persisted to DLQ.
- **Blast radius:** Cross-process events for war room, intel, bridge, alerts, and recovery paths. Law 3 promises Redis Streams/event-driven/no central orchestrator; current backend path does not provide replay.
- **Current detection:** Handler error counters/logs; no durable backlog count.
- **Current recovery:** Reconnect loop for the listener, but no replay for missed notifications.
- **Proposed fix:** File path: `apps/backend-rag/backend/services/events/event_bus.py`. Conceptual diff: keep PG NOTIFY for compatibility, but mirror every emitted event to Redis Stream `backend:events` with bounded `MAXLEN`, and store handler failures in `backend_event_dlq` or a `/data/event_dlq.jsonl` fallback. If Redis is down, write local JSONL and process in isolation per Law 4. Cell/Genome reference: Cell reads stream lag/DLQ metrics; Genome records lost-event scars.
- **Post-fix verification:** Kill the listener, emit 10 events, restart listener, assert all 10 are replayed from Redis/JSONL. Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/events/test_event_bus_replay.py -q`.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 12 - DB Pool Exhaustion From Ad-Hoc Connections

- **Failure mode:** Local search found many direct `asyncpg.connect()` and `asyncpg.create_pool()` calls in routers/services, including `system_observability.py`, `google_drive.py`, `admin_drive_health.py`, `prime_nexus_service.py`, and `golden_router_service.py`. This bypasses the shared app pool and can exhaust DB connections under load.
- **Blast radius:** All DB-backed surfaces: CRM, portal, Drive, Prime, KG, channel history, migrations, analytics. The shared pool is configured max 10 in startup, but ad-hoc pools/connections are not globally bounded.
- **Current detection:** `/health` exposes some DB state, but no saturation threshold is tied to restart/degraded health.
- **Current recovery:** Connection timeouts, manual restart, or DB recovery. No automatic throttling at the source.
- **Proposed fix:** File paths: high-traffic routers/services first (`system_observability.py`, `google_drive.py`, `prime.py`, `prime_nexus_service.py`, `golden_router_service.py`). Conceptual diff: route all web-request DB access through `app.state.db_pool` or dependency injection; allow direct pool creation only in CLI/migration allowlist. Add health metric `db_pool_available/max` and set degraded after sustained saturation. Cell/Genome reference: Cell DB sensor consumes saturation metric; Genome records pool exhaustion scars.
- **Post-fix verification:** `rg -n "asyncpg\\.(connect|create_pool)" apps/backend-rag/backend/app/routers apps/backend-rag/backend/services` should shrink to allowlisted CLI/worker paths. Add load test that keeps p95 below threshold with pool max 10.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes for guardrail and top offenders; full conversion is incremental

## Surface 13 - Async HTTP Client Leaks And Sync HTTP Calls Remain Broad

- **Failure mode:** Local search found many `async with httpx.AsyncClient(...)` inside request/task paths and sync `httpx.post`/`urllib.request` in backend services. Golden Rule #10 says persistent clients, async-first I/O, never `requests`; the codebase still has many short-lived clients and sync stdlib HTTP calls.
- **Blast radius:** 607 backend service files plus routers. High-risk surfaces include attendance monitor, dashboard, CRM enhanced, publisher services, oracle ingest, legal ingestion, and notification scripts.
- **Current detection:** No CI gate beyond some style checks. Socket churn manifests as latency, FD exhaustion, or OOM before a clear root cause.
- **Current recovery:** Fly restart may clear sockets, but deterministic leak patterns recur.
- **Proposed fix:** File path: add `scripts/check_http_client_policy.py` and CI step in `.github/workflows/fly-deploy.yml`; refactor high-traffic services to receive persistent clients from app lifespan. Conceptual diff: allow short-lived clients only in explicit CLI/test allowlist; fail deploy on new violations. Cell/Genome reference: Genome records `persistent_http_client_refactor` skill; Cell tracks FD/socket count if available.
- **Post-fix verification:** `python scripts/check_http_client_policy.py --fail-on-new`. Before: many hits. After first pass: zero new violations and top 10 high-traffic paths converted.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes for guardrail; full cleanup needs staged PRs

## Surface 14 - Qdrant Degradation Can Become Silent Empty Retrieval

- **Failure mode:** Qdrant client has retries/backoff and often degrades by returning empty results rather than crashing. That preserves uptime but can silently degrade answer quality. Cell `QdrantSensor` expects only 8 collections, while the brief says 12 live collections and local health code counts collections dynamically.
- **Blast radius:** 12 Qdrant collections, 93k+ documents per brief, embedding `text-embedding-3-small` 1536 dimensions frozen. RAG answers, KBLI, visa/legal retrieval, KG seed retrieval.
- **Current detection:** `/health` Qdrant stats and Cell collection/doc drop heuristic, but baseline is stale (`_EXPECTED_COLLECTIONS = 8`).
- **Current recovery:** Retry only; no collection canary or automatic quality fallback alert.
- **Proposed fix:** File paths: `apps/cell/cell/sensors/qdrant_sensor.py`, `apps/backend-rag/backend/app/routers/health.py`, `apps/backend-rag/backend/core/qdrant_db.py`. Conceptual diff: make expected collection count an env/config baseline generated from live source of truth; add a RAG canary that queries known docs and asserts non-empty results without changing embedding model/dimensions. Cell/Genome reference: Cell emits Qdrant canary failures; Genome records collection-drop scars.
- **Post-fix verification:** `cd apps/cell && pytest tests/test_qdrant_sensor.py -q` with expected 12; `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/rag/test_qdrant_canary.py -q`.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 15 - KG Subgraph Generation Fails Per Request Instead Of Being Isolated

- **Failure mode:** KG orchestration is lazily constructed in routes such as `kg_agentic.py` and `kbli_notebook_chat.py`. Failures fall back in some paths, but visual graph/subgraph generation can still return 500 and expensive traversals can pressure DB/Qdrant.
- **Blast radius:** KG has 108k nodes and 243k edges per brief. A bad subgraph query can degrade multi-domain RAG and KBLI chat.
- **Current detection:** Core KG tests in deploy gate, but runtime KG canary is not blocking and graph generation failures are request-local logs.
- **Current recovery:** Some route-level fallback to KBLI-only; no automatic circuit breaker keyed to KG subgraph failure rate.
- **Proposed fix:** File paths: `apps/backend-rag/backend/app/routers/kg_agentic.py`, `apps/backend-rag/backend/services/rag/kg_langgraph_orchestrator.py`, `apps/backend-rag/backend/tests/services/rag/`. Conceptual diff: add a KG circuit breaker around expensive subgraph generation, cache last-known-good graph metadata, and expose breaker state to `/health/detailed`. Cell/Genome reference: Cell reads KG breaker state; Genome records KG fallback skill.
- **Post-fix verification:** Simulate DB timeout in KG visual graph endpoint; before 500. After fallback returns degraded payload and breaker metric increments. Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/app/routers/test_kg_agentic_resilience.py -q`.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 16 - Frontend i18n Provider Is Still Per Route Group

- **Failure mode:** Next.js `apps/mouth` wraps `I18nProvider` in some route groups (`(workspace)`, `(blog)`, `(book)`) and local pages, but not globally. Components such as `PublicNav`, `PublicFooter`, `StatsCounter`, `KitaCommandPalette`, and blog category pages call `useTranslation()`. PR #273 scar: missing route-group provider can white-screen.
- **Blast radius:** Mouth Next.js 16/React 19 frontend; 8 subdomains and marketing/workspace/blog/book surfaces. A white-screen is a customer-visible crash even if Vercel keeps serving.
- **Current detection:** Some route tests and comments, but no structural test mapping `useTranslation()` usage to provider coverage.
- **Current recovery:** Vercel auto-recovers serverless instances, but client white-screen persists until code fix.
- **Proposed fix:** File paths: `apps/mouth/src/app/layout.tsx` or route layouts, `apps/mouth/src/i18n`, `apps/mouth/src/__tests__/i18n-provider-coverage.test.ts`. Conceptual diff: either provide a safe root-level `I18nProvider` or add a static coverage test that every route importing a component with `useTranslation()` is under a provider. Cell/Genome reference: Cell/Vercel sensor adds Playwright smoke for route groups; Genome records PR #273 scar closure.
- **Post-fix verification:** `cd apps/mouth && npm run test -- i18n-provider-coverage` and Playwright smoke for `/`, `/blog`, `/kbli`, `/chat`, `/portal/login-upgraded`. Before: uncovered routes possible. After: test blocks merge.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 17 - Service Worker Caches All GET `/api/*`

- **Failure mode:** `apps/mouth/public/sw.js` caches any same-origin GET `/api/*` using stale-while-revalidate. Auth, health, portal, and dynamic API responses can be served stale while backend is broken or after permissions change. This is not a server crash, but it can hide backend failure from the user and from browser QA.
- **Blast radius:** Mouth PWA clients with installed SW. All GET `/api/*` responses in scope, including proxy and portal data.
- **Current detection:** None specific. Browser smoke without SW reset can read stale success.
- **Current recovery:** Cache version bump only; no kill switch or endpoint denylist.
- **Proposed fix:** File path: `apps/mouth/public/sw.js`. Conceptual diff: denylist `/api/auth`, `/api/portal`, `/api/chat`, `/api/health`, `/api/[...path]` proxy, streaming endpoints, and any request with cookies/authorization; cache only explicit public immutable GET endpoints. Add deploy ID to cache name and a remote kill-switch message. Cell/Genome reference: Cell browser QA runs with SW enabled and disabled; Genome records SW poisoning scars.
- **Post-fix verification:** `cd apps/mouth && npm run test -- service-worker` plus Playwright: prime `/api/health` healthy, force backend 503, assert browser receives 503 and not cached 200.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 18 - `apps/web` SSO Surface On Air Remains Unresolved

- **Failure mode:** Air escalation `air-a1-auth-surface` is unresolved for 11 days. `apps/web` is a separate app surface and does not appear to share the Mouth middleware/token handling. Its API client defaults to local backend unless configured and only sends auth if token is explicitly set.
- **Blast radius:** Apps/web SSO path; can show unauthenticated behavior or backend 401 loops while the main 8-subdomain Mouth SSO works.
- **Current detection:** One HIGH escalation on Air; no automated closure.
- **Current recovery:** Manual product/security decision and code fix.
- **Proposed fix:** File paths: `apps/web/src/lib/api/client.ts`, `apps/web` auth boundary, Air escalation registry. Conceptual diff: choose one mode: public demo with explicit degraded auth-free UI, or gated SSO using `nz_access_token`/backend session parity. Until Zero decides, add safe 401 handling and visible login redirect instead of crashing/looping. Cell/Genome reference: Cell tracks Air escalation age; Genome records unresolved-auth scar until closed.
- **Post-fix verification:** Browser test on Air URL: unauthenticated request returns login/degraded state, authenticated request forwards token. Before: HIGH escalation age 11 days. After: escalation closed and recurring test green.
- **Severity:** P1
- **Auto-implementable by Claude L2:** no for product decision; yes for defensive 401 handling

## Surface 19 - Vercel Build Env And Runtime Smoke Are Not A Recovery Loop

- **Failure mode:** Missing Vercel env vars or runtime config can produce serverless 500s after deploy. Vercel keeps old deployment on build failure, but runtime misconfig can still ship if build passes.
- **Blast radius:** Mouth and subdomain routes, especially auth proxy, Prime, portal, Sentry, and backend proxy paths.
- **Current detection:** Frontend tests and Vercel build status; no mandatory post-deploy browser QA across 8 subdomains in the backend deploy workflow.
- **Current recovery:** Vercel rollback/manual redeploy.
- **Proposed fix:** File paths: `apps/mouth/scripts/check-env.ts`, `.github/workflows/*vercel*` or a new frontend QA workflow. Conceptual diff: add a non-secret env schema check using required key names only; add Playwright post-deploy smoke across 8 subdomains and auth proxy. Cell/Genome reference: Cell Vercel sensor ingests deployment status and browser QA result; Genome records env-missing scars.
- **Post-fix verification:** `cd apps/mouth && npm run build && npm run test:e2e -- smoke-subdomains`. Before: env drift can be discovered by users. After: deploy marked degraded/failed before promotion or immediate rollback alert.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes for schema and smoke; no for setting missing secrets

## Surface 20 - LaunchAgents And Automation Registry Are Out Of Sync

- **Failure mode:** Local audit found 53 project-ish LaunchAgents, but the registry/catalog paths account for far fewer launchd jobs; only 7 live plists had `KeepAlive=true`, 11 had no `KeepAlive`, 5 lacked `EnvironmentVariables`, and 6 logged to `/tmp`. Processes without `KeepAlive` can die and stay dead.
- **Blast radius:** Pro/Air local recovery plane: Cell, Organism, cron wrappers, Drive polling, backup, KG builder, sentinels, docs guardians, and auxiliary daemons.
- **Current detection:** `system_doctor.py` scans selected logs and some launchd bad exits, but not complete plist-vs-registry drift.
- **Current recovery:** launchd only for plists configured correctly; otherwise manual `launchctl kickstart`.
- **Proposed fix:** File paths: `scripts/automation_catalog.json`, `~/.agent/decisions/job_registry.json`, `scripts/audit_launchagents.py`. Conceptual diff: generate a canonical inventory from live plists, catalog, and registry; fail audit if a project plist lacks `KeepAlive` for daemon jobs, explicit `PATH`/`HOME`, logs under `~/logs`, and `restart_cmd`. Cell/Genome reference: Cell local sensor emits LaunchAgent drift; Genome records daemon restart success/failure.
- **Post-fix verification:** `python scripts/audit_launchagents.py --strict`. Before: 53 live, 7 KeepAlive true, 11 absent. After: 0 critical daemon plists without KeepAlive/restart_cmd and 0 `/tmp` logs for critical jobs.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes for repo/catalog/plist templates; live launchctl changes need operator context

## Surface 21 - Cron Wrapper Exists But Is Not Universal

- **Failure mode:** `scripts/cron-wrapper.sh` has lock/retry/timeout/Telegram/JSON logging, but not every scheduled automation is forced through it. Cron or launchd jobs that bypass it can fail silently or overlap.
- **Blast radius:** 12+ Air/Pro scheduled jobs per brief plus OpenClaw jobs. Current sentinel: 58 jobs total, 10 healthy, 16 circuit breakers open.
- **Current detection:** Sentinel and system doctor see selected logs/states, not every scheduler entry.
- **Current recovery:** Wrapper-managed jobs can retry; unmanaged jobs depend on their own behavior.
- **Proposed fix:** File paths: `scripts/automation_catalog.json`, `scripts/cron-wrapper.sh`, new `scripts/validate_automation_catalog.py`. Conceptual diff: every non-daemon scheduled job must declare wrapper command, timeout, lock ID, retry count, restart command, owner, and Cell event kind. Cell/Genome reference: Cell treats uncatalogued job as yellow; Genome records recurring cron failures.
- **Post-fix verification:** `python scripts/validate_automation_catalog.py --require-wrapper --strict`. Before: catalog/live drift. After: zero critical uncatalogued schedules.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 22 - Organism Is Still Shadow-Mode And Active Dispatch Is Placeholder

- **Failure mode:** `apps/organism/organism/supervisor/daemon.py` consumes `organism:events`, decides, writes JSONL, and acks. When `shadow_mode=False`, it only logs "active mode dispatch not yet implemented". That means the autonomic layer observes but does not repair.
- **Blast radius:** All event-driven self-healing expected from Organism. If Cell depends on Organism for structural recovery, the repair path is manual.
- **Current detection:** Decisions log and heartbeat key. Control panel stats are not enough proof of active repair.
- **Current recovery:** None from Organism; shadow only.
- **Proposed fix:** File paths: `apps/organism/organism/supervisor/daemon.py`, `apps/organism/organism/supervisor/dispatch.py`, `apps/organism/rules/base.yaml`. Conceptual diff: implement whitelisted safe actuators behind circuit breaker and Consiglio gate: `launchctl kickstart`, local service restart, DLQ replay, non-destructive workflow rerun. Keep structural/destructive actions Telegram-only. Cell/Genome reference: Organism decisions must call Genome `record_skill()` for successful safe repair and `record_scar()` for failed dispatch.
- **Post-fix verification:** `cd apps/organism && pytest tests/supervisor/test_dispatch.py tests/supervisor/test_daemon.py -q` with `shadow_mode=False` fixture. Before: no dispatch. After: whitelisted fake actuator called and event acked only after success.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes for safe actuators; production activation needs staged rollout

## Surface 23 - Organism LaunchAgents May Not Be Loaded Live

- **Failure mode:** Repo contains `apps/organism/organism/launchd/com.nuzantara.organism.supervisor.plist` and control-panel plist, but live LaunchAgent inventory during this run did not show those exact labels in the project-ish set that was already summarized in `07_dispatch_resilience_log.md`.
- **Blast radius:** If Organism is not loaded, `organism:events` decisions are not consumed at all.
- **Current detection:** Heartbeat key only if the process is running. System Doctor does not assert expected organism plist labels are loaded.
- **Current recovery:** Manual `launchctl load/bootstrap`.
- **Proposed fix:** File paths: `scripts/audit_launchagents.py`, `apps/organism/organism/launchd/*.plist`, automation registry. Conceptual diff: add expected-label checks and `restart_cmd` for Organism supervisor/control-panel; alert if heartbeat stale or label not loaded. Cell/Genome reference: Cell local sensor records missing Organism label as red; Genome records `organism_not_loaded` scar.
- **Post-fix verification:** `python scripts/audit_launchagents.py --expect com.nuzantara.organism.supervisor --expect com.nuzantara.organism.control-panel`. Before: labels not proven loaded. After: labels loaded, heartbeat fresh.
- **Severity:** P0
- **Auto-implementable by Claude L2:** yes for checks/templates; loading live agent requires local command execution context

## Surface 24 - MCP Servers Are Operationally Useful But Not Recovery-Critical

- **Failure mode:** MCP readiness failed in this sandbox for `nuzantara-mcp` and `nuzantara-mcp-advanced`; dispatch log shows Codex batch execution can crash or degrade when an unrelated MCP OAuth token is expired. MCP stdio servers themselves are not supervised by the product runtime.
- **Blast radius:** Developer/agent operations: 115 primary MCP tools, 14 advanced tools, 6 browser tools per brief. Production user traffic should degrade because backend native tools exist, but autonomous maintenance can lose semantic leverage.
- **Current detection:** Manual `python3 ~/.codex/mcp_readiness_check.py`; no scheduled Cell event from this check.
- **Current recovery:** Restart caller/session; refresh OAuth token manually.
- **Proposed fix:** File paths: `~/.codex/mcp_readiness_check.py`, `.mcp.json`, `scripts/automation_catalog.json`, `apps/nuzantara-mcp-advanced/server.py`. Conceptual diff: schedule MCP readiness as a non-prod operational sensor; split noninteractive Codex/Claude profile from optional MCP profile; in advanced server use `sys.executable` or explicit backend `.venv/bin/python` instead of plain `python` subprocesses. Cell/Genome reference: Cell records MCP readiness as yellow, never red for production; Genome stores token-expiry scars.
- **Post-fix verification:** `python3 ~/.codex/mcp_readiness_check.py` emits structured JSON to Cell. Before: hidden startup crash. After: one yellow operational event, no production fail.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes for repo-side subprocess/readiness; no for OAuth refresh

## Surface 25 - `.mcp.json` And LaunchAgents Contain Secret-Like Runtime Env

- **Failure mode:** Local config includes inline API-key/token-like environment variables and credential paths. This is not quoted here. Secrets in process manager config make rotation brittle and increase blast radius when files are copied or logged.
- **Blast radius:** MCP servers, local agents, and any automation reading those plists/configs.
- **Current detection:** No mandatory secret scanner for local MCP/LaunchAgent config.
- **Current recovery:** Manual secret rotation and config edit.
- **Proposed fix:** File paths: `.mcp.example.json`, `scripts/check_local_secret_config.py`, LaunchAgent templates. Conceptual diff: move secrets to Keychain/env files excluded from git, keep only variable names in tracked examples, and add a local scanner that reports secret-shaped values without printing them. Cell/Genome reference: Cell local sensor treats secret-in-config as yellow; Genome records secret-rotation scars.
- **Post-fix verification:** `python scripts/check_local_secret_config.py --paths .mcp.json ~/Library/LaunchAgents --redact --strict`. Before: secret-shaped inline values detected. After: zero inline secret values, only references.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes for scanner/templates; live secret movement needs operator action

## Surface 26 - Drive Polling OAuth Expiry Is A Timed Manual Failure

- **Failure mode:** Drive polling depends on OAuth/token material with a 90-day expiry risk per brief. Current repo also has `cron-drive-poll.yml` hitting backend `/api/admin/drive/poll`, but token expiry still requires manual auth recovery if not service-accounted.
- **Blast radius:** CRM document ingestion, portal document freshness, Drive-backed workflows.
- **Current detection:** GitHub cron failure alert and selected System Doctor log checks; no proactive days-to-expiry check in Cell.
- **Current recovery:** Manual OAuth re-login or secret update.
- **Proposed fix:** File paths: `apps/backend-rag/backend/app/routers/admin_drive_health.py`, `scripts/drive_token_watchdog.py`, `scripts/automation_catalog.json`. Conceptual diff: expose token expiry/refresh health without secret values; watchdog alerts at 30/14/7 days; service-account paths must be preferred where domain permissions allow. Cell/Genome reference: Cell reads token expiry metric; Genome records `drive_oauth_renewal` skill.
- **Post-fix verification:** `python scripts/drive_token_watchdog.py --dry-run --redact`. Before: expiry unknown until failure. After: days-to-expiry number and alert thresholds.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes for watchdog; no for OAuth re-auth

## Surface 27 - Fly Crash Watchers Alert But Do Not Repair

- **Failure mode:** Fly watcher/restart detector workflows run on intervals and alert on app state, but they do not automatically restart a bad machine or promote rollback outside deploy context. If a machine is wedged but still not covered by Fly health due Surface 1, alert-only is insufficient.
- **Blast radius:** Backend Fly app, Postgres/Qdrant checks, potentially all API traffic depending on which machine is hit.
- **Current detection:** `cron-fly-watcher.yml`, `cron-fly-restart-detector.yml`, healthcheck probe.
- **Current recovery:** Deploy workflow rollback only during deploy health failure; runtime issues require manual flyctl or Cell.
- **Proposed fix:** File paths: GitHub Fly watcher workflows, `apps/cell/cell/effectors/fly_effector.py`. Conceptual diff: keep GitHub watchers alert-only; let Cell perform bounded local repair for safe actions: one targeted restart after N failed probes, cooldown, and Telegram notice. Avoid making GitHub Actions a central orchestrator. Cell/Genome reference: this is a Cell-owned recovery action with Genome skill/scar records.
- **Post-fix verification:** Simulate one unhealthy machine in Fly API mock; before watcher sends alert only. After Cell targeted restart called once with cooldown.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes in Cell tests; live activation needs token and safety gate

## Surface 28 - Post-Deploy RAG Smoke Is Non-Blocking

- **Failure mode:** `.github/workflows/fly-deploy.yml` runs a RAG smoke test after health but marks it informational with `continue-on-error: true`. A deploy can be "OK" while the actual chat/RAG path is broken.
- **Blast radius:** Primary business intelligence workflow: RAG chat, KBLI, legal/visa guidance, channel answers.
- **Current detection:** Non-blocking log line and later user/doctor discovery.
- **Current recovery:** Manual rollback/fix.
- **Proposed fix:** File path: `.github/workflows/fly-deploy.yml`. Conceptual diff: make RAG smoke blocking for changes under RAG/chat/channel/embedding paths; keep informational only for unrelated backend changes. Add canary response quality minimum and Qdrant collection count check. Cell/Genome reference: Cell receives post-deploy canary result; Genome records smoke-failure scars.
- **Post-fix verification:** Break `/api/chat/query` in a test branch; before deploy can still pass. After post-deploy job fails and rollback/alert triggers.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 29 - Browser QA Does Not Cover The Full User Crash Surface

- **Failure mode:** System Doctor checks frontend URLs by HTTP/body length. That misses JS white-screens, hydration crashes, i18n provider errors, Service Worker staleness, cookie SSO loops, and visual blank pages.
- **Blast radius:** 8 subdomains plus Mouth route groups.
- **Current detection:** HTTP-level checks, not browser-level checks.
- **Current recovery:** Manual browser discovery or user report.
- **Proposed fix:** File paths: `apps/mouth/e2e/smoke.spec.ts`, workflow for post-deploy browser QA. Conceptual diff: Playwright smoke across 8 domains/routes with console error fail, visible content assertions, auth-cookie redirect checks, and SW reset/enabled variants. Cell/Genome reference: Cell browser sensor stores last QA timestamp/result; Genome records frontend crash scars.
- **Post-fix verification:** `cd apps/mouth && npx playwright test e2e/smoke.spec.ts --project=chromium`. Before: HTTP 200 can pass blank UI. After: blank UI fails.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 30 - System Doctor Misses Key Recovery Gaps

- **Failure mode:** `scripts/system_doctor.py` checks backend `/health`, selected frontend URLs, SSL, Fly RAM/logs, selected cron logs, and OpenClaw jobs. It misses semantic startup failure, DLQ retry-loop existence, router manifest drift, EventBus replay lag, MCP readiness, Organism active-mode status, Service Worker stale cache, and full LaunchAgent registry drift.
- **Blast radius:** The primary 08:00 health summary can be green while core recovery mechanisms are dead.
- **Current detection:** Partial.
- **Current recovery:** Partial auto-fixes; many are reports only.
- **Proposed fix:** File path: `scripts/system_doctor.py`. Conceptual diff: add plugin-style checks for the surfaces above, each returning numbers: DLQ backlog, retry task status if exposed, route count vs manifest, event stream lag, Organism heartbeat and mode, LaunchAgent drift, MCP readiness, browser QA latest result. Cell/Genome reference: System Doctor should emit its own findings to Cell/Organism; Genome records repeated blind spots.
- **Post-fix verification:** `python3 scripts/system_doctor.py --dry-run --json` contains all new check IDs and non-zero findings for current drift.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 31 - Telegram Alert Dedup/Rate Limit Is File-Based And Not Atomic

- **Failure mode:** `scripts/sentinel_lib/alerter.py` uses md5 dedup and cooldown files under `~/.agent/decisions`, but read/write is not locked or atomic. Concurrent jobs can corrupt state or double-send/suppress incorrectly. It also uses `print()` in failure paths.
- **Blast radius:** Owner Telegram chat `1125336968`, all Sentinel alerts, 40 active escalation cooldowns per brief. Alert failure can hide crash/recovery failures.
- **Current detection:** None for dedup file corruption except JSON decode fallback.
- **Current recovery:** Fallback treats corrupt file as empty, causing alert storms or lost cooldown.
- **Proposed fix:** File path: `scripts/sentinel_lib/alerter.py`. Conceptual diff: use file lock and atomic rename writes; record send failures to JSONL; add P0 bypass budget that ignores dedup for crash-without-recovery alerts while rate-limiting repeats by incident ID. Cell/Genome reference: Cell alert sensor records Telegram send success; Genome records alert-channel failure scars.
- **Post-fix verification:** Concurrent test with 20 processes sending same alert. Before: possible double-send/corruption. After: one send, valid JSON, deterministic cooldown.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 32 - `healthcheck@balizero.com` Probe Is Referenced But Not Implemented In Repo

- **Failure mode:** The brief references a 15-minute `healthcheck@balizero.com` probe. Local `rg` found this as documentation/brief context, not a tracked implementation with tests.
- **Blast radius:** External dead-man monitoring may be assumed present when it is not reproducible from the repo.
- **Current detection:** Documentation only unless external system exists outside repo.
- **Current recovery:** Unknown.
- **Proposed fix:** File path: `docs/operations/healthcheck-probe.md` plus automation catalog entry or tracked workflow. Conceptual diff: document exact owner, schedule, endpoint, alert route, and test method; add a local check that verifies probe freshness from its public/API evidence. Cell/Genome reference: Cell tracks external probe heartbeat as an independent sensor; Genome records external-probe failures.
- **Post-fix verification:** `python scripts/validate_automation_catalog.py --id healthcheck-balizero-probe` and a heartbeat freshness check. Before: absent from repo. After: tracked and testable.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes for documentation/catalog; no if external mailbox/probe needs credentials

## Surface 33 - Langfuse Observability Is Dormant By Default

- **Failure mode:** Langfuse PR #312 is initialized best-effort in backend startup, but docs indicate it is dormant unless env keys are present. If disabled, failure spans and RAG timing can be invisible. If enabled incorrectly with payload capture, it risks data exposure.
- **Blast radius:** Debugging latency/failure across RAG, LLM calls, tools, channels. This is detection, not direct restart.
- **Current detection:** Logs only when init skipped; no Cell visibility.
- **Current recovery:** Manual env changes and deploy.
- **Proposed fix:** File paths: `apps/backend-rag/backend/core/observability.py`, docs for observability. Conceptual diff: enable metadata-only traces in production when keys are present; keep prompt/completion/body capture off by default; expose exporter health in `/health/detailed`. Cell/Genome reference: Cell reads observability exporter status; Genome records dormant-observability scar.
- **Post-fix verification:** With redacted test env, one RAG request emits metadata span and no prompt text. Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/core/test_observability_redaction.py -q`.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes for redaction tests; no for live secret activation

## Surface 34 - Twitter/X Channel Is CRC Broken And Disabled

- **Failure mode:** The brief marks Twitter/X CRC broken. `service_initializer.py` conditionally registers Twitter only when credentials exist; a broken CRC/webhook path can silently remove a channel from the active set.
- **Blast radius:** 1 of 7 channels. Lower business impact than WhatsApp/Telegram but still a channel outage.
- **Current detection:** Startup warning when credentials absent; no channel-specific live webhook canary.
- **Current recovery:** Manual fix/re-auth/provider config.
- **Proposed fix:** File paths: `apps/backend-rag/backend/channels/twitter/`, `apps/backend-rag/backend/app/setup/service_initializer.py`, channel health endpoint. Conceptual diff: expose per-channel readiness and webhook challenge canary; disabled channels must be explicit yellow in health, not invisible. Cell/Genome reference: Cell channel sensor records per-channel state; Genome records X CRC scar.
- **Post-fix verification:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_twitter_crc_health.py -q`. Before: disabled/broken channel can be log-only. After: health shows `twitter: degraded/disabled`.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes for health/canary; no for provider-side credentials

## Surface 35 - GChat And Slack Are Scaffolded But Not Recovery-Proven

- **Failure mode:** GChat and Slack are listed as channels, but scaffolding without live canary/retry verification can look supported while failing at first production webhook/send.
- **Blast radius:** 2 of 7 channels, currently likely lower traffic than WhatsApp/Telegram.
- **Current detection:** Registration logs and manual testing.
- **Current recovery:** Manual.
- **Proposed fix:** File paths: channel adapter tests under `apps/backend-rag/backend/tests/channels/`, channel health endpoint. Conceptual diff: each channel must have an adapter send/receive contract test, retry/DLQ test, and canary health state. Cell/Genome reference: Cell channel matrix tracks each channel's last canary; Genome records adapter readiness skills.
- **Post-fix verification:** `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels -q` with Slack/GChat contract tests.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes

## Surface 36 - Mata Garuda OSINT Needs Poison-Message Recovery Proof

- **Failure mode:** Mata Garuda correctly uses `packages/cell-core` concepts in its runner, but OSINT pipelines can still stall on poison items or HGT threshold mismatch. Law 2 says OSINT data never leaves Pro, so cloud retry services are not allowed.
- **Blast radius:** OSINT/intelligence ingestion and local knowledge enrichment. It should not bring backend down, but it can silently stop feeding intelligence.
- **Current detection:** Local logs and Cell/Mata runner state.
- **Current recovery:** Local retry if implemented; poison item handling needs explicit proof.
- **Proposed fix:** File paths: `apps/mata-garuda/`, `packages/cell-core/cell_core/hgt/`, Mata tests. Conceptual diff: add local-only poison DLQ with redacted metadata, retry budget, and HGT publish threshold test. Cell/Genome reference: this surface already belongs to Cell/Genome; ensure `record_scar()` on poison DLQ and `record_skill()` on recovery.
- **Post-fix verification:** Mata unit test with one poison item and one good item: good item processes, poison item moves to local DLQ, no cloud egress.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes

## Surface 37 - Postgres Backup Restore Is Tested Monthly But Not Runtime Recovery

- **Failure mode:** Restore drill workflow exists and is valuable, but a live Postgres corruption/outage still requires human promotion/repointing. This is appropriate for destructive recovery, but the manual boundary must be explicit.
- **Blast radius:** All DB-backed state: CRM, portal, channels, workflows, migrations, KG relational tables.
- **Current detection:** Fly/Postgres checks, backup logs, monthly restore drill.
- **Current recovery:** Manual restore/promotion. Automatic destructive DB restore would violate safety.
- **Proposed fix:** File paths: restore drill workflow/docs, automation catalog. Conceptual diff: keep restore manual, but automate evidence collection: latest backup age, last restore-drill row count, RPO/RTO estimate, and a one-command runbook. Cell/Genome reference: Cell reports backup freshness; Genome records successful restore drill skill.
- **Post-fix verification:** `gh workflow run restore-drill.yml` on schedule plus `python scripts/backup_status.py --json` reports latest backup age and last drill status.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes for evidence/runbook; no for live destructive restore

## Surface 38 - Redis Failure Mode Is Not Uniform Across Components

- **Failure mode:** Law 4 says Redis down means agents operate in isolation. Some components do: Organism `redis_bus.py` writes JSONL before Redis `xadd`. Backend EventBus does not use Redis Streams. Cell safety gate can fail open/closed depending path. This inconsistency can propagate faults differently by organ.
- **Blast radius:** Event-driven recovery, dedup/cooldown, Organism events, Cell STM, channel optimizations.
- **Current detection:** Component-specific logs; no single Redis degradation contract test.
- **Current recovery:** Mixed: JSONL fallback in Organism, volatile loss in backend EventBus, degraded local behavior in Cell.
- **Proposed fix:** File paths: `apps/organism/organism/redis_bus.py`, `apps/backend-rag/backend/services/events/event_bus.py`, `apps/cell/cell/core/safety.py`, shared tests. Conceptual diff: define a shared Redis-down contract: local JSONL fallback, bounded replay, degraded health, no crash, no central orchestrator. Cell/Genome reference: Cell owns Redis-down state; Genome records per-organ isolation skills.
- **Post-fix verification:** Integration suite starts components with Redis unavailable and asserts: no crash, local JSONL written, Cell yellow, replay works after Redis returns.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

## Surface 39 - LLM CLI Automation Can Crash On Optional MCP Coupling

- **Failure mode:** Dispatch log shows noninteractive Codex execution hit MCP `TokenRefreshFailed` before continuing. Law 1 requires CLI-only LLMs (DeepSeek API exception), but CLI sessions that auto-load stale MCP connectors can fail before doing useful work.
- **Blast radius:** Autonomous audit/repair workflows, not direct customer traffic. It can block Claude L2/Codex L2 from executing recovery work.
- **Current detection:** stderr in batch job only.
- **Current recovery:** Retry with different profile or refresh token manually.
- **Proposed fix:** File paths: docs/automation for LLM dispatch, Codex/Claude wrapper scripts. Conceptual diff: create a "rescue" CLI profile with MCP disabled and only filesystem/shell; use it for emergency jobs. Optional MCP profile remains interactive only. Cell/Genome reference: Cell records LLM dispatch failures; Genome records `mcp_profile_isolation` skill.
- **Post-fix verification:** Run `codex exec`/`claude` wrapper in rescue mode with expired MCP token present; command still starts and reads repo.
- **Severity:** P2
- **Auto-implementable by Claude L2:** yes for wrappers/docs; no for vendor token refresh

## Surface 40 - Architecture Atlas Count Drift Can Hide Missing Coverage

- **Failure mode:** Sacred docs, user brief, and local filesystem counts disagree: apps 27 vs local 26, routers 139 vs local 140, services 512 vs local 607. A resilience gate based on stale counts can miss new surfaces.
- **Blast radius:** Audit coverage, System Doctor coverage, router manifest coverage, automation catalog coverage.
- **Current detection:** Manual count during audit.
- **Current recovery:** Manual doc update.
- **Proposed fix:** File paths: `INDEX.md`, `docs/AI_ONBOARDING.md`, `scripts/count_surface_inventory.py`, CI docs check. Conceptual diff: generate counts from filesystem/manifest and publish a machine-readable `docs/generated/surface_inventory.json`; docs import or reference that generated artifact. Cell/Genome reference: Cell reads inventory drift; Genome records inventory-update skill.
- **Post-fix verification:** `python scripts/count_surface_inventory.py --write docs/generated/surface_inventory.json && python scripts/count_surface_inventory.py --check-docs`. Before: drift. After: docs and generated inventory match.
- **Severity:** P1
- **Auto-implementable by Claude L2:** yes

---

## Recommended P0 Implementation Bundle

These can be implemented without touching off-limits files:

1. Backend health startup failure 503: `health.py` plus test.
2. Channel optimization stale import fixes: `service_initializer.py`, `channels/router.py`, tests.
3. SQL v2 post-deploy migration rerun: `.github/workflows/fly-deploy.yml`.
4. Cell semantic health and targeted Fly restart tests: `apps/cell`.
5. Organism safe dispatch and LaunchAgent strict audit: `apps/organism`, `scripts/audit_launchagents.py`, automation catalog.

## Verification Commands For The Bundle

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest \
  backend/tests/app/routers/test_health_startup_failed.py \
  backend/tests/channels/test_delivery_retry_loop.py \
  backend/tests/channels/test_router_dedup.py \
  backend/tests/setup/test_router_registration_matches_manifest.py \
  -q

cd ../../apps/cell && pytest tests/test_pulse.py tests/test_fly_effector.py -q

cd ../organism && pytest tests/supervisor/test_dispatch.py tests/supervisor/test_daemon.py -q

cd ../..
python scripts/audit_launchagents.py --strict
python scripts/validate_automation_catalog.py --require-wrapper --strict
```

Expected before/after numbers:

- Backend startup-failed health: before can be HTTP 200; after HTTP 503.
- Channel DLQ retry task: before absent due stale import; after started when DB pool exists.
- Duplicate webhook drop: before dedup object can remain `None`; after second identical message is dropped.
- Router drift: before manifest and registration can diverge; after actual app routes match manifest.
- LaunchAgents: before 53 live project-ish plists, only 7 with `KeepAlive=true`, 11 absent; after 0 critical daemons missing KeepAlive/restart command.
- Sentinel: before 58 jobs, 10 healthy, 16 open circuits, 54 DLQ entries; after bundle should reduce DLQ backlog and expose any remaining red state through Cell/Organism rather than silent logs.
