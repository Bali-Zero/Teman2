# Codex Zero-Crash Resilience Audit

Date: 2026-04-29
Machine: Pro (`nuzantara@Nuzantara`)
Branch: `main`
Scope: monorepo local filesystem, CI config, launchd inventory, backend/frontend/organi locali/MCP source.

Session limitation: Air peer was unreachable during the mandatory Pro/Air check, so every Air-side recovery claim is treated as unverified. MCP readiness also failed for project MCP/Postgres/Qdrant/Sentry in this sandbox; Playwright was reachable.

Baseline observed by Codex:

- 26 app directories found locally under `apps/`; user baseline says 27 apps.
- 5 package directories found under `packages/`.
- 139 backend router files under `apps/backend-rag/backend/app/routers`.
- 521 backend service files found locally under `backend/services` + `backend/app/services`; user baseline says 512.
- 30 SQL v2 migration files under `apps/backend-rag/backend/db/migrations_v2`.
- 79 user LaunchAgent plists under `~/Library/LaunchAgents`; user baseline says 19 Pro LaunchAgents. Treat 19 as project-critical known set, not full local blast radius.
- 2 duplicate SQL v2 migration numbers are present: `129_*` and `130_*`.
- Current structural cicatrix PR #307 is still present in CI: SQL v2 migrations run before Fly deploy, therefore against the old image.

## P0 Recovery Gaps

### P0-01 Backend health masks startup failure and DB init failure

- Failure mode: Heavy RAG startup can fail in background init, set `app.state.startup_failed`, and still expose `/health` without checking that flag. Light API DB init can fail, set `app.state.db_pool = None`, and `/health` still reports `database.connected`. Evidence: `apps/backend-rag/backend/app/setup/app_factory.py:116`, `apps/backend-rag/backend/app/routers/health.py:48`, `apps/backend-rag/backend/app/routers/health.py:147`, `apps/backend-rag/backend/app/main_api.py:34`.
- Blast radius: 2 Fly machines, 139 routers, all public API traffic, 7 channel webhook surfaces, 12 Qdrant collections. A failed boot can remain HTTP 200 instead of triggering Fly restart.
- Current detection: `/health` has `_check_startup_failed()` but does not call it. System Doctor checks `/health` only and treats some unreachable states as warning.
- Current recovery: Fly can restart only on non-2xx health responses. Today the key crash path can return 200/`healthy` or 200/`initializing`.
- Proposed fix: In `apps/backend-rag/backend/app/routers/health.py`, call `_check_startup_failed(request.app)` before process-mode branching and set HTTP 503. Add a warmup deadline for RAG process, for example `app.state.startup_started_at` plus 180 seconds, after which `initializing` becomes 503. In light process, require `db_pool` for `database.status=connected`; otherwise return 503 or explicit `degraded` only for routes that truly do not require DB. In `apps/backend-rag/backend/app/setup/app_factory.py` and `apps/backend-rag/backend/app/main_api.py`, emit `organism:events` and record a Cell/Genoma scar named `backend_startup_failed` with exception class, process group, and image SHA.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/app/test_health_startup_failure.py -q`; inject startup failure and assert before `HTTP 200`, after `HTTP 503`. Production: `curl -fsS https://nuzantara-rag.fly.dev/health/ready`; before no ready endpoint contract, after 2/2 machines must report ready.
- Severity: P0.
- Auto-implementable by Claude L2: yes for code/tests; no for production deployment without explicit approval.

### P0-02 Qdrant is a startup SPOF instead of a degraded vector organ

- Failure mode: `initialize_critical_services()` creates SearchService and then verifies Qdrant with a fresh `httpx.AsyncClient`; failure registers `search` as `UNAVAILABLE`, and critical service failure raises `RuntimeError`. Evidence: `apps/backend-rag/backend/app/setup/service_initializer.py:101`, `apps/backend-rag/backend/app/setup/service_initializer.py:138`.
- Blast radius: 12 Qdrant collections, 93K+ vector documents, 108K KG nodes, 243K KG edges, all RAG/chat endpoints. A transient Qdrant Cloud outage can prevent the backend from becoming healthy even when DB, channels, auth, CRM, and non-vector services could continue.
- Current detection: Service registry logs critical failure. Health currently masks some startup failures per P0-01.
- Current recovery: Fly restart after P0-01 fix, but restart cannot recover if Qdrant remains down. No degraded SearchService contract.
- Proposed fix: Add a vector-unavailable mode in `apps/backend-rag/backend/services/search/search_service.py` and dependency wrappers: SearchService initializes with `vector_status=unavailable`, returns `CAUTIOUS`/degraded answers using KG/BM25/static references where possible, and rejects only endpoints requiring vector writes. In `service_initializer.py`, register `search` as `DEGRADED` instead of `UNAVAILABLE` when the object exists but Qdrant ping fails. Cell/Genoma: emit `qdrant_vector_organ_down` with degraded routes count, active fallback, and recovery timestamp when Qdrant returns.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/search/test_qdrant_degraded_mode.py backend/tests/app/test_health_qdrant_degraded.py -q`; before Qdrant ping failure aborts startup, after `/health` is degraded but non-vector endpoints pass.
- Severity: P0.
- Auto-implementable by Claude L2: yes for code/tests; no for enabling production degraded policy without owner approval if UX wording changes.

### P0-03 SQL v2 migrations still run on the old Fly image

- Failure mode: Cicatrix PR #307 remains open. `fly-deploy.yml` runs SQL v2 migrations before `flyctl deploy`, so any new SQL runner code in the just-merged commit is absent. Evidence: `.github/workflows/fly-deploy.yml:134`, `.github/workflows/fly-deploy.yml:146`, `.github/workflows/fly-deploy.yml:154`.
- Blast radius: 30 SQL v2 migrations, last migration 140, all schema-dependent routers/services. One incompatible migration path can ship code/schema mismatch or require manual `gh workflow run` re-trigger.
- Current detection: Documented scar in `.claude/rules/cicatrix-scars.md`. CI has an informational migration status step only, not a blocking dry-run/new-image assertion.
- Current recovery: Manual post-merge GitHub workflow re-trigger. No automatic second-stage SQL v2 apply on the new image.
- Proposed fix: In `.github/workflows/fly-deploy.yml`, split SQL v2 into pre-deploy `dry-run` and post-deploy `apply-all` against the newly deployed image. Use a machine/image readiness sentinel tied to the current Git SHA, not fixed `apply_migration_119.py`. Add `scripts/post_deploy_sql_v2_guard.sh` that writes an `organism:events` record and a Genoma scar `migration_old_image_blocked` whenever the image SHA does not match the workflow SHA.
- Post-fix verification: `gh workflow run fly-deploy.yml -f dry_run=true` or CI dry-run; expected before: SQL apply job precedes deploy, after: dry-run before deploy and real apply after deploy. Code verification: `rg -n "run-migrations|post-deploy-sql-v2|FLY_MACHINE_VERSION" .github/workflows/fly-deploy.yml`.
- Severity: P0.
- Auto-implementable by Claude L2: yes for workflow patch; no for live deploy execution.

### P0-04 Duplicate SQL v2 migration numbers can silently skip a migration

- Failure mode: `_apply_all_pending_locked()` computes applied migrations by `migration_number`, so duplicate numbers collapse into one applied state. Local files include `129_crm_guardian.sql`, `129_legacy_user_profiles.sql`, `130_crm_guardian_summary_queue.sql`, `130_legacy_conversations.sql`. Evidence: `apps/backend-rag/backend/db/migration_manager.py:346`, `apps/backend-rag/backend/db/migration_manager.py:348`, `apps/backend-rag/backend/db/migration_manager.py:359`.
- Blast radius: 4 duplicate-number files out of 30 SQL v2 files, affecting CRM guardian, legacy user profiles, guardian summary queue, legacy conversations. If either number is marked applied, the sibling file can be skipped.
- Current detection: None found in CI. Squawk checks SQL quality, not migration-number uniqueness.
- Current recovery: Manual DB inspection and manual apply if a skipped migration is noticed.
- Proposed fix: Add `scripts/check_sql_v2_migration_contract.py` and `apps/backend-rag/backend/tests/db/test_migrations_v2_contract.py` to enforce unique numeric prefixes, monotonic ordering, rollback marker/comment policy, and `_schema_versions`/`schema_migrations` consistency. Wire it into pre-deploy gate. Cell/Genoma: on duplicate detection, emit `migration_contract_violation` and record a scar with duplicate IDs and affected filenames.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/db/test_migrations_v2_contract.py -q`; before: fails with duplicates `[129, 130]`; after: zero duplicates. Also `python scripts/check_sql_v2_migration_contract.py`.
- Severity: P0.
- Auto-implementable by Claude L2: yes for tests/checker; migration renumbering requires careful DB-state review and should be approved.

### P0-05 Inbound webhooks ACK before durable inbox persistence

- Failure mode: WhatsApp schedules processing via `BackgroundTasks` and returns 200. Telegram returns 200 even on exceptions to prevent retries. Instagram returns OK/error JSON without durable pre-ACK persistence. A process crash after provider ACK loses the inbound message. Evidence: `apps/backend-rag/backend/app/routers/whatsapp_chat.py:617`, `apps/backend-rag/backend/app/routers/whatsapp_chat.py:685`, `apps/backend-rag/backend/app/routers/telegram_webhook.py:299`, `apps/backend-rag/backend/app/routers/telegram_webhook.py:322`, `apps/backend-rag/backend/app/routers/instagram_chat.py:163`, `apps/backend-rag/backend/app/routers/instagram_chat.py:219`.
- Blast radius: 3 high-value inbound channels directly observed; user baseline says 7 channels total. Every user/client message can disappear if the worker crashes after ACK and before DB/conversation write.
- Current detection: Channel metrics are in-memory counters only. Outbound DLQ exists, but inbound DLQ/inbox does not appear to be a universal contract.
- Current recovery: Provider retries are intentionally suppressed for Telegram errors; WhatsApp background task death has no durable replay; Instagram returns OK for invalid bodies.
- Proposed fix: Add `channel_inbox` SQL v2 table and `backend/channels/inbox.py`. Each webhook verifies signature, inserts raw provider payload with idempotency key `(channel, provider_message_id/update_id)`, commits, then ACKs. A supervised worker drains inbox to `ChannelRouter`; failures move to `channel_inbox_dlq`. Use Redis Stream `channel:inbox` as fast path and Postgres as durable source. Cell/Genoma: Cell watches inbox backlog and writes scars for `inbound_ack_loss_prevented`, including channel and count.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_inbound_inbox_ack_contract.py -q`; before no durable row exists before ACK, after every ACKed payload has an inbox row and replay succeeds after simulated crash.
- Severity: P0.
- Auto-implementable by Claude L2: yes for code/tests/migration; no for production channel cutover without staged deploy.

### P0-06 Background workers are spawned without restart supervision

- Failure mode: Workflow worker, legal ingestion worker, EventBus listener, DLQ retry loop, and notification scheduler are started as raw `asyncio.create_task()` or internal background loops. If a task exits after startup, the process may keep serving HTTP while recovery work is dead. Evidence: `apps/backend-rag/backend/app/setup/app_factory.py:170`, `apps/backend-rag/backend/app/setup/app_factory.py:182`, `apps/backend-rag/backend/app/setup/app_factory.py:216`, `apps/backend-rag/backend/channels/optimizations.py:558`.
- Blast radius: 4+ backend background systems, workflow queue, legal ingestion, event propagation, outbound retry, notifications. Failures affect all channels and ops automations without killing the process.
- Current detection: Logs only. `/health` does not expose supervised task liveness. System Doctor does not inspect backend task registry.
- Current recovery: None after task death, except manual restart or deploy.
- Proposed fix: Add `apps/backend-rag/backend/app/setup/background_supervisor.py` with `supervise_task(name, factory, restart_budget, backoff, criticality)`. Store task state under `app.state.background_supervisor`, expose it in `/health/detailed` and `/api/cell/metrics`, restart non-critical tasks automatically, and return 503 for critical tasks that exceed restart budget. Cell/Genoma: every restart and budget exhaustion becomes a Genoma scar and `organism:events` event.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/setup/test_background_supervisor.py -q`; before a killed worker remains dead, after restart count increments and health reports `recovered`.
- Severity: P0.
- Auto-implementable by Claude L2: yes.

### P0-07 Organism is documented as Level 2 active but dispatch is still shadow/placeholder

- Failure mode: `AUTONOMOUS_OPS.md` says Level 2 active, but the Organism Supervisor launchd plist sets `ORGANISM_SHADOW_MODE=true`, daemon logs decisions only, and dispatcher returns `DISPATCHED` without invoking actuators in active mode. Evidence: `apps/organism/organism/launchd/com.nuzantara.organism.supervisor.plist:13`, `apps/organism/organism/supervisor/daemon.py:129`, `apps/organism/organism/supervisor/dispatch.py:140`.
- Blast radius: All self-healing events that depend on Organism: 79 local LaunchAgents, backend deploy failure events, cron-agent failures, circuit breakers, DLQs. Decisions can be logged but not executed.
- Current detection: Decisions JSONL exists. No production check fails when shadow mode remains true.
- Current recovery: Manual human/Claude intervention. Actuator code exists, but daemon does not invoke it.
- Proposed fix: Wire `organism.supervisor.dispatch.Dispatcher` into `daemon.py` using the existing actuator registry for a safe L0 allowlist: `restart_agent`, `cleanup_log`, `notify_telegram`. Keep irreversible actions such as deploy rollback/manual migrations gated to Zero. Add a runtime `organism:mode` status endpoint and System Doctor check that fails if Level 2 docs say active while launchd is shadow. Cell/Genoma: Cell must consume decisions/outcomes and record `organism_shadow_drift` until dispatch is truly active.
- Post-fix verification: `cd apps/organism && pytest tests/supervisor/test_daemon.py tests/supervisor/test_dispatch.py tests/gauntlet/test_gauntlet_01_break_guardian.py -q`; before decision logged only, after `restart_agent` actuator mock is invoked exactly once and guarded by circuit breaker/mutex.
- Severity: P0.
- Auto-implementable by Claude L2: yes for wiring/tests; no for flipping production launchd to active without Zero approval.

### P0-08 Cell can crash-loop before Genoma records the wound

- Failure mode: `apps/cell/cell/main.py` bootstraps DB tables before entering the pulse-loop exception boundary. Missing `.env` in `launch_cell.sh` exits immediately. LaunchAgent `KeepAlive=true` restarts, but logs go to `/tmp` and Cell does not instantiate the central `packages/cell-core.Genome`. Evidence: `apps/cell/cell/main.py:61`, `apps/cell/cell/main.py:65`, `apps/cell/scripts/launch_cell.sh:9`, `apps/cell/com.cell.organism.plist:16`, `apps/cell/com.cell.organism.plist:18`.
- Blast radius: 1 central nervous-system process, plus every proposal required by Law 8. If Cell is down, scars/proposals/pulse monitoring degrade silently into launchd restarts.
- Current detection: launchd bad-exit/zombie-hunter may detect loops if state bridge is healthy. `/tmp` logs are not durable operational logs.
- Current recovery: launchd restarts only. No structured Genoma scar before early boot failures.
- Proposed fix: Add a minimal bootstrap guard in `apps/cell/cell/main.py` before DB table creation: instantiate `packages/cell-core.Genome` using a local SQLite path, record `cell_boot_start`, `cell_boot_failed`, and `cell_halted`. Move plist logs to `~/logs/cell/`, add `ThrottleInterval`, and add a health heartbeat file in `~/.agent/decisions/state/cell_heartbeat.json`. Cell/Genoma: this fix directly centralizes recovery scars in Genome.
- Post-fix verification: `cd apps/cell && source .venv/bin/activate && PYTHONPATH=.:../../packages/cell-core pytest tests/test_cell_boot_genome.py -q`; before missing `.env` exits with only stderr, after a Genoma scar and launchd state heartbeat exist.
- Severity: P0.
- Auto-implementable by Claude L2: yes for code/plist template; no for installing/reloading launchd without approval.

## P1 Recovery Gaps

### P1-01 Router manifest is not the actual registration source

- Failure mode: `router_manifest.py` claims it prevents PR #54/#55/#60 scars, but `router_registration.py` still manually imports/includes routers instead of driving from `ROUTER_MANIFEST`. Evidence: `apps/backend-rag/backend/app/setup/router_manifest.py:1`, `apps/backend-rag/backend/app/setup/router_registration.py:12`, `apps/backend-rag/backend/app/setup/router_registration.py:23`.
- Blast radius: 139 router files. A router can exist in manifest/tests but be absent in light or heavy process, yielding production 404s without process crash.
- Current detection: Manifest tests verify manifest structure and file existence, not actual `include_routers()` output equality.
- Current recovery: Manual route registration patch after a 404 is noticed.
- Proposed fix: Replace manual registration with a manifest loader in `router_registration.py`. Add a test that builds light/heavy FastAPI apps and compares route prefixes against `routers_for_group("api")` and `routers_for_group("rag")`. Cell/Genoma: daily route-drift guard emits `router_manifest_drift` with missing/extra counts.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py backend/tests/setup/test_router_registration_contract.py -q`; before manual registration can drift, after route set equals manifest.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-02 EventBus is not Law-3 Redis Streams durable eventing

- Failure mode: Backend EventBus is PG LISTEN/NOTIFY plus in-process pub/sub, while Symbiosis Law 3 requires Redis Streams and consumer groups. Handler failures are not durable DLQ by default. Evidence: `apps/backend-rag/backend/app/setup/app_factory.py:206`, `apps/backend-rag/backend/services/events/event_bus.py` source comments/implementation.
- Blast radius: Event propagation across 512+ services and local organs. One handler/process restart can drop transient NOTIFY events.
- Current detection: EventBus monitoring router/log traces only. No stream lag/DLQ metric for every event kind.
- Current recovery: Reconnect loop exists for PG EventBus, but not durable replay of already emitted events.
- Proposed fix: Add `backend/services/events/redis_stream_bridge.py`. On publish, write to Redis Stream `nuzantara:events` with consumer groups per organ and mirror to PG/in-process for compatibility. On handler failure, XACK only after success; failed payloads go to `event_bus_dlq`. Cell/Genoma: Cell consumes event lag metrics and records `event_bus_lag`/`event_bus_dlq_growth`.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/events/test_redis_stream_bridge.py -q`; before process crash loses transient event, after event is replayed from stream.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-03 Outbound channel DLQ can still lose messages when PG and Redis are down

- Failure mode: DeliveryManager writes failed outbound messages to Postgres, falls back to Redis list, then logs `message LOST` when both are unavailable. Evidence: `apps/backend-rag/backend/channels/optimizations.py:385`, `apps/backend-rag/backend/channels/optimizations.py:389`, `apps/backend-rag/backend/channels/optimizations.py:397`.
- Blast radius: 7 channels, all outbound replies/alerts. A dual DB+Redis outage loses failed sends permanently.
- Current detection: Log line only. Telegram alert exists for exhausted messages after PG persistence, not for both-stores-down loss.
- Current recovery: None for dual-store-down loss.
- Proposed fix: Add a local JSONL spool under Fly volume `/data/channel_dlq/` as third fallback, with a drain task that replays to PG when DB returns. For Pro/Air local jobs, use `~/logs/channel_dlq_spool/`. Cell/Genoma: Cell watches spool length and records `channel_dlq_spool_growth`.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_delivery_spool_fallback.py -q`; before persist returns lost, after a JSONL record exists and drains.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-04 Channel health metrics are in-memory and not enough for restart/degrade decisions

- Failure mode: `ChannelMetrics` stores counters/latency in process memory only. Process restart clears evidence; no durable per-channel status or rolling SLO state. Evidence: `apps/backend-rag/backend/channels/optimizations.py:220`, `apps/backend-rag/backend/channels/optimizations.py:227`.
- Blast radius: 7 channels. A channel can be failing but restart clears the symptom counters before escalation.
- Current detection: In-process stats and logs.
- Current recovery: None automatic by channel health state.
- Proposed fix: Persist channel rolling metrics to Redis Stream/Hash and Postgres hourly rollup. Define per-channel states `UP`, `DEGRADED`, `DOWN` from sent/received/error rates. ChannelRouter should stop only the failing adapter, not the whole backend. Cell/Genoma: Cell consumes channel state and records scars when a channel remains degraded for more than N pulses.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/channels/test_channel_health_persistence.py -q`; before restart resets metrics to 0, after Redis/PG state survives restart.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-05 Drive polling has alerting but no automatic local fallback or OAuth expiry recovery

- Failure mode: `.github/workflows/cron-drive-poll.yml` runs every 5 minutes and POSTs `/api/admin/drive/poll`. Failure sends Telegram, but there is no automatic fallback to Pro/Air local poller, no token-expiry preflight in workflow, and no durable queue for missed polls in the workflow itself. Evidence: `.github/workflows/cron-drive-poll.yml:1`, `.github/workflows/cron-drive-poll.yml:21`, `.github/workflows/cron-drive-poll.yml:47`.
- Blast radius: Drive ingestion pipeline, client documents, CRM document updates, OAuth 90-day expiry risk, 12+ Air cron jobs mentioned by user.
- Current detection: GitHub Actions failure and Telegram if secrets exist. Air unreachable in this session means local fallback could not be verified.
- Current recovery: Manual token refresh or backend fix. GitHub workflow retries only on next schedule.
- Proposed fix: Add `scripts/drive_poll_failsafe.py` run by Pro/Air LaunchAgent and System Doctor. It checks last successful poll timestamp, token expiry/refreshability, workflow status, and enqueues a local recovery poll only if GitHub has missed 2 intervals. Write status to `organism:events` and Genome scar `drive_poll_gap` with missed interval count. Keep OSINT/local documents on Pro per Law 2.
- Post-fix verification: `python scripts/drive_poll_failsafe.py --dry-run --max-age-minutes 10`; before only GitHub alert, after local dry-run reports `would_recover=true` and emits an organism event in test Redis.
- Severity: P1.
- Auto-implementable by Claude L2: yes for scripts/tests; no for OAuth/token rotation.

### P1-06 RedisManager does not mark mid-life Redis ping failure unavailable

- Failure mode: RedisManager starts reconnect loop when initial connection fails, but `health_check()` ping exceptions return an error without setting `_available=False` or starting reconnect for mid-life failure. Evidence: `apps/backend-rag/backend/core/redis_manager.py:162`, `apps/backend-rag/backend/core/redis_manager.py:181`, `apps/backend-rag/backend/core/redis_manager.py:200`, `apps/backend-rag/backend/core/redis_manager.py:259`.
- Blast radius: distributed rate limiting, cache invalidation, channel DLQ fallback, future Redis Streams. Components may keep a stale client and repeatedly fail instead of downgrading cleanly.
- Current detection: Redis health check returns `connected=false` with error.
- Current recovery: Initial-start reconnect loop only; mid-life failure recovery is incomplete.
- Proposed fix: On ping failure, close stale clients, set `_available=False`, set `_reconnect_pending=True`, and call `_ensure_reconnect_loop()`. Emit `redis_midlife_disconnect` to Organism and Genoma with affected components count.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/core/test_redis_manager_reconnect.py -q`; before `_available` remains stale, after reconnect task starts and fallback mode activates.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-07 Service Worker can cache private/stale API responses

- Failure mode: `apps/mouth/public/sw.js` intercepts every same-origin GET `/api/*` and caches any `networkResponse.ok`, ignoring `Cache-Control: no-store`, cookies, and authorization. Evidence: `apps/mouth/public/sw.js:19`, `apps/mouth/public/sw.js:23`, `apps/mouth/public/sw.js:29`, `apps/mouth/public/sw.js:70`.
- Blast radius: 8 frontend subdomains and all GET API routes proxied through `apps/mouth`. Stale auth/profile/portal/CRM data can be served after backend recovery or user switch.
- Current detection: None in System Doctor. Browser QA is manual and not cache-state aware.
- Current recovery: User hard refresh/cache clear; deploy increments SW version but does not prevent poisoning within the version.
- Proposed fix: Change SW to an explicit public allowlist only, for example `/api/public/*` and static unauthenticated lookups. Skip any request with `Cookie`/`Authorization` and any response with `Cache-Control: no-store|private`. Add cache purge message and Playwright SW test. Cell/Genoma: frontend canary emits `service_worker_private_cache_blocked` with blocked count.
- Post-fix verification: `cd apps/mouth && npm run test -- service-worker && npx playwright test tests/e2e/service-worker-auth-cache.spec.ts`; before `/api/auth/profile` can be cached, after it is never stored.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-08 Next.js i18n provider can regress per route group

- Failure mode: `useTranslation()` throws outside `I18nProvider`; root layout wraps `QueryProvider`, `ThemeProvider`, and `ErrorBoundary`, but not `I18nProvider`. Some route groups provide their own provider, preserving PR #273-style regression risk. Evidence: `apps/mouth/src/i18n/index.tsx:90`, `apps/mouth/src/app/layout.tsx:235`.
- Blast radius: Next.js 16/React 19 frontend, 8 subdomains, all route groups using `useTranslation`.
- Current detection: Build may pass if routes are not rendered in tests. System Doctor only checks HTTP body length.
- Current recovery: ErrorBoundary fallback or white-screen/route crash until code fix.
- Proposed fix: Move `I18nProvider` into root layout or add a route-contract test that renders every route group using translation hooks with provider. If root wrap is too broad, add a `scripts/check_i18n_provider_routes.ts` static guard. Cell/Genoma: browser canary logs `frontend_i18n_provider_missing` when console contains the provider error.
- Post-fix verification: `cd apps/mouth && npm run test -- i18n && npx playwright test tests/e2e/i18n-provider.spec.ts`; before a missing-provider fixture crashes, after every route renders.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-09 Vercel build gate omits typecheck/tests/env contract/browser QA

- Failure mode: `vercel.json` build command is only `npm run build -w apps/mouth`. It does not require typecheck, unit tests, e2e, env-var contract, or post-deploy browser QA. Evidence: `vercel.json:3`, `apps/mouth/package.json` scripts.
- Blast radius: 8 subdomains, SSO flows, SW, route groups, API proxy. A runtime frontend crash can deploy if `next build` passes.
- Current detection: GitHub CI may run some checks, but Vercel deployment itself is not guarded by full frontend resilience suite. System Doctor only performs HTTP GET.
- Current recovery: Manual rollback/redeploy in Vercel.
- Proposed fix: Add `apps/mouth/scripts/verify-build-env.ts`, `npm run verify:deploy`, and update Vercel build command to run build plus env/typecheck/test smoke. Add post-deploy Playwright QA using Vercel preview URL. Cell/Genoma: frontend canary emits browser console/network errors into `organism:events`.
- Post-fix verification: `cd apps/mouth && npm run verify:deploy`; before missing env/browser crash can pass, after deploy gate fails with counted errors.
- Severity: P1.
- Auto-implementable by Claude L2: yes for scripts; no for Vercel project settings if dashboard-only.

### P1-10 SSO/subdomain auth has no synthetic recovery canary

- Failure mode: Middleware handles multiple subdomain groups and cookie flows, while one Air HIGH escalation `air-a1-auth-surface` has been unresolved for 11 days. No canary proves `nz_access_token`/SSO across all 8 subdomains after deploy. Evidence: user-provided open escalation plus `apps/mouth/src/middleware.ts` subdomain auth logic.
- Blast radius: 8 subdomains and all client/team portal access. Auth crash is user-visible and may not affect generic HTTP health.
- Current detection: Manual reports/escalations; System Doctor HTTP-only checks do not authenticate.
- Current recovery: Manual patch/redeploy; cookie clearing by user.
- Proposed fix: Add Playwright authenticated SSO canary with a synthetic non-client account and no sensitive data. It visits each subdomain, verifies cookie domain/path/HttpOnly/SameSite behavior, and records `sso_surface_ok` per subdomain. Cell/Genoma: unresolved auth canary writes `sso_surface_degraded` scar and blocks deploy promotion if new.
- Post-fix verification: `cd apps/mouth && npx playwright test tests/e2e/sso-subdomains.spec.ts`; before no automated coverage, after 8/8 subdomains checked with exact pass count.
- Severity: P1.
- Auto-implementable by Claude L2: yes for test skeleton; no for synthetic credentials/secrets.

### P1-11 LaunchAgent registry is incomplete relative to actual host

- Failure mode: User baseline says 19 Pro LaunchAgents, but local host has 79 user plists. System Doctor and zombie-hunter cannot guarantee coverage if the registry only models the known project subset. Evidence: `find ~/Library/LaunchAgents -maxdepth 1 -name '*.plist' | wc -l` returned 79; `apps/cell/com.cell.organism.plist` and Organism plist are only two examples.
- Blast radius: 79 local launchd surfaces, including Cell, Organism, Mata Garuda, WR2, nuz-sync, Redis/Postgres/Ollama homebrew services, cost advisors, sentinels, and third-party updaters.
- Current detection: zombie-hunter state file, System Doctor launchd scan, manual catalog. Coverage drift is not a failing contract.
- Current recovery: launchd `KeepAlive` for some jobs; many plists may have missing `ThrottleInterval`, logs, restart command, or catalog entry.
- Proposed fix: Add `scripts/launchagent_contract.py` that parses actual `~/Library/LaunchAgents`, `scripts/automation_catalog.*`, and `~/.agent/decisions/job_registry.json`. Enforce RunAtLoad/KeepAlive policy for project-critical labels, log path under `~/logs`, restart command, owner, SLA, and Cell/Genoma touchpoint. Emit `launchagent_registry_drift` with total/known/unknown counts.
- Post-fix verification: `python scripts/launchagent_contract.py --dry-run`; before actual=79 and known likely lower, after known project-critical=100% and unknown explicitly ignored/allowed.
- Severity: P1.
- Auto-implementable by Claude L2: yes for scanner/docs; no for unloading/reloading launchd.

### P1-12 System Doctor misses key zero-crash surfaces and `--notify-telegram` does not send

- Failure mode: `--notify-telegram` is parsed, `telegram_summary` is built, but no Telegram send is performed in `system_doctor.py`. It also treats backend unreachable as warning, performs frontend HTTP body checks only, and emits Organism events only for cron-agent findings. Evidence: `scripts/system_doctor.py:1368`, `scripts/system_doctor.py:1458`, `scripts/system_doctor.py:1522`, `scripts/system_doctor.py:323`, `scripts/system_doctor.py:638`.
- Blast radius: Daily 08:00 health layer, all systems the user relies on for non-developer guardrails.
- Current detection: JSON output and logs only. Telegram may be absent despite flag.
- Current recovery: Auto-fixers exist, but one auto-fixer resets OpenClaw error counters, which can hide failure rather than recover it. Evidence: `scripts/system_doctor.py:1240`.
- Proposed fix: Implement `scripts/sentinel_lib/alert_bus.py` and use it from System Doctor. Convert backend unreachable to critical for Fly min>=1, add `/health/ready`, migration-contract, browser Playwright, SW cache, Organism active-mode, launchagent-contract, MCP readiness, and Pro/Air sync collectors. Emit every critical finding to `organism:events` and Genome, not just cron-agent logs.
- Post-fix verification: `python scripts/system_doctor.py --dry-run --notify-telegram --verbose`; before no Telegram send side effect and limited collectors, after `alert_bus` dry-run shows one deduped alert and collector count includes the new surfaces.
- Severity: P1.
- Auto-implementable by Claude L2: yes for code/tests; no for live Telegram send verification without secrets.

### P1-13 Telegram alert plane lacks a global dedup/rate-limit/DLQ

- Failure mode: Multiple scripts/services send directly to Telegram chat `1125336968` or env chat IDs. There is no single token-bucket, dedup key, local spool, or DLQ across backend, Cell, Organism, GitHub workflows, and scripts. Evidence: direct senders in `.github/workflows/fly-deploy.yml`, `.github/workflows/cron-drive-poll.yml`, `apps/backend-rag/backend/channels/optimizations.py:523`, `scripts/system_doctor.py`.
- Blast radius: All critical alerts. During cascading failure, Telegram can flood, rate-limit, or fail silently.
- Current detection: Sender-local logs, if any.
- Current recovery: None universal. Some senders `|| true` on failure.
- Proposed fix: Centralize to `scripts/sentinel_lib/alert_bus.py` plus backend equivalent `backend/services/alerts/alert_bus.py`: dedup key, 30-minute cooldown, token bucket, JSONL spool, optional Redis Stream `alerts:outbound`, Telegram worker, and dry-run mode. Cell/Genoma: alert suppression and DLQ growth become scars/proposals, not hidden drops.
- Post-fix verification: `python scripts/tests/test_alert_bus.py` or `pytest scripts/tests/test_alert_bus.py -q`; before 10 identical alerts call Telegram 10 times, after 1 send and 9 deduped with counters.
- Severity: P1.
- Auto-implementable by Claude L2: yes; live Telegram credentials require owner.

### P1-14 Langfuse/OpenLLMetry is dormant by default

- Failure mode: Observability is disabled unless Langfuse keys exist; docs confirm dormant behavior. Evidence: `apps/backend-rag/backend/core/observability.py:42`, `apps/backend-rag/backend/core/observability.py:52`, `docs/oss-injections-2026-04-26.md:150`.
- Blast radius: LLM/RAG/council traces across complex failure paths. Crash recovery can happen, but root cause/quality degradation is blind.
- Current detection: Logs say disabled/missing keys.
- Current recovery: Manual enable and ask user to reproduce.
- Proposed fix: Activate metadata-only Langfuse for production with `LANGFUSE_TRACE_LLM_MESSAGES=false`, 100% tracing for CAUTIOUS/ABSTAIN/errors, sampled normal traffic, and local/self-hosted target if Law 2/PII constraints require. Keep Anthropic SDK banned: do not add Anthropic client usage; instrument only CLI/OAuth spans and current Gemini/OpenAI-compatible clients. Cell/Genoma: Cell consumes trace error-rate summaries and records `rag_trace_gap` if traces are absent for active traffic.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/core/test_observability.py -q`; production verification requires one CAUTIOUS query and checking trace count increments without message text.
- Severity: P1.
- Auto-implementable by Claude L2: partial. Code guardrails yes; keys/host activation require Zero.

### P1-15 MCP config contains inline secrets and MCP readiness has no recovery contract

- Failure mode: `.mcp.json` contains inline API key material in env fields and starts MCP servers via client-managed stdio without an external readiness/deadman. Current `mcp_readiness_check.py` could not reach project MCPs in this session. Evidence: `.mcp.json:7`, `.mcp.json:8`, `.mcp.json:9`, `.mcp.json:10`.
- Blast radius: 3 Nuzantara MCP servers plus fetch/GA/GSC/OCR/browser MCPs. Tooling can silently be unavailable to agents; inline secret rotation is brittle.
- Current detection: Manual `python3 ~/.codex/mcp_readiness_check.py`.
- Current recovery: Restart Codex/MCP client or manually edit config. No Cell/Genoma scar for MCP unavailable.
- Proposed fix: Replace inline secrets with env-file or secret-provider references, add `scripts/mcp_contract_check.py` that validates no literal secret patterns, venv paths exist, health tool responds, and project MCPs report tool counts. Emit `mcp_unavailable` to Organism and Genome with server name and tool count delta.
- Post-fix verification: `python scripts/mcp_contract_check.py --no-network`; before inline secret findings >0, after 0 inline secrets and all configured paths valid. Live: `python3 ~/.codex/mcp_readiness_check.py` returns project MCP reachable.
- Severity: P1.
- Auto-implementable by Claude L2: yes for checker/config template; no for rotating exposed secrets.

### P1-16 nuzantara-mcp-advanced blocks the async MCP loop and exposes recovery actions outside Organism gates

- Failure mode: Async tools call `subprocess.run()` directly, blocking the MCP server event loop. The recovery tool can run Fly restart/redeploy without going through Organism circuit breakers, mutexes, blackout windows, or Zero approval gates. Evidence: `apps/nuzantara-mcp-advanced/nuzantara_mcp_advanced/server.py:65`, `apps/nuzantara-mcp-advanced/nuzantara_mcp_advanced/server.py:302`.
- Blast radius: 14 advanced MCP tools, Fly app recovery commands, agent operator workflows.
- Current detection: Tool timeout/error response only.
- Current recovery: MCP client restart/manual retry.
- Proposed fix: Wrap CLI calls with `asyncio.to_thread` or `asyncio.create_subprocess_exec` and route recovery actions through an Organism proposal endpoint: safe restart can be L2, redeploy/rollback stays Zero-gated. Cell/Genoma: every MCP recovery request writes `mcp_recovery_action_requested` and outcome.
- Post-fix verification: `cd apps/nuzantara-mcp-advanced && source .venv/bin/activate && pytest tests/test_server_async_cli.py -q`; before concurrent tool calls serialize/block, after event loop remains responsive and gated actions are enforced.
- Severity: P1.
- Auto-implementable by Claude L2: yes for async refactor/tests; no for enabling live recovery operations.

### P1-17 Browser MCP can crash on Playwright init/navigation edge cases

- Failure mode: BrowserManager raises on Playwright initialization failure and assumes `page.goto()` returns a response object; `response.status` can crash if navigation returns `None`. Evidence: `packages/browser-core/browser_core/manager.py:72`, `packages/browser-core/browser_core/manager.py:100`, `packages/browser-core/browser_core/manager.py:208`, `packages/browser-core/browser_core/manager.py:214`.
- Blast radius: `apps/nuzantara-mcp-browser` 6 tools and browser QA exception path.
- Current detection: MCP tool failure or readiness check failure.
- Current recovery: Manual Playwright reinstall/restart.
- Proposed fix: Add browser health states: `unavailable`, `initializing`, `ready`; return structured degraded errors instead of raising during server startup; handle `response is None`; add auto-reinit with bounded backoff. Cell/Genoma: browser health emits `browser_mcp_unavailable` with installed browser/version.
- Post-fix verification: `cd packages/browser-core && pytest tests/test_manager_navigation_none.py tests/test_manager_init_failure.py -q`; before None response crashes, after structured error and reinit attempt.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-18 HTTP client lifecycle guard is not enforced repo-wide

- Failure mode: Many services/routers instantiate `httpx.AsyncClient()` per call or lazy without a shared lifecycle. `requests`/Anthropic SDK imports still exist outside the approved production Claude CLI path. Evidence: `rg -n "httpx.AsyncClient\\(" apps/backend-rag/backend/app/routers apps/backend-rag/backend/services`, `rg -n "from anthropic|import anthropic|Anthropic\\(" apps packages`.
- Blast radius: 512+ services, external API integrations, channel senders, publishers, ingestion workers. Under load this can exhaust sockets/DB-like pools or leak clients.
- Current detection: Manual review. No CI guard for Golden Rule #10 or Anthropic SDK ban across all apps.
- Current recovery: Process restart after resource exhaustion, if health catches it.
- Proposed fix: Add `scripts/check_http_client_lifecycle.py` that allows known factories/singletons and flags per-request clients in routers/services. Add `scripts/check_banned_anthropic_sdk.py` with allowlist for tests/docs only and enforce Claude CLI/OAuth client usage. Cell/Genoma: daily guard records `http_client_lifecycle_violations` count.
- Post-fix verification: `python scripts/check_http_client_lifecycle.py --fail-on-new && python scripts/check_banned_anthropic_sdk.py`; before violations >0, after count decreases to accepted baseline and CI blocks new ones.
- Severity: P1.
- Auto-implementable by Claude L2: yes for guard; fixing all call sites should be batched.

### P1-19 KG subgraph generation is request-coupled and can exhaust resources

- Failure mode: KG/RAG subgraph generation touches 108K nodes and 243K edges; request-time generation can hit memory/timeouts and crash or stall a worker if not bounded by queue/circuit breaker. Evidence: user-verified KG numbers and KG orchestrator/service files under `apps/backend-rag/backend/services/rag/`.
- Blast radius: RAG heavy process, chat endpoints, all knowledge workflows, potentially 1 of 2 Fly machines at a time.
- Current detection: Prometheus counters/logs for some KG paths, not a hard per-request budget contract.
- Current recovery: Fly restart if process dies; no automatic downgrade to cached subgraph/static answer when generator is unhealthy.
- Proposed fix: Add `kg_subgraph_budget` with max nodes/edges/time per request, queue large builds to Workflow Queue, cache last-known-good subgraphs, and trip a circuit breaker to degraded KG answers when failure rate exceeds threshold. Cell/Genoma: record `kg_subgraph_budget_exceeded` with node/edge counts and fallback used.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/rag/test_kg_subgraph_budget.py -q`; before unbounded fixture can exceed budget, after bounded response returns degraded/cached result.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-20 Squawk migration lint has no bypass/exception ledger

- Failure mode: Migration lint uses Squawk but no bypass tracking was found for ignored/waived findings. Cicatrix says Atlas migrate-lint was paywalled and Squawk replaced it; the new guard needs an exception ledger or it can rot into `continue-on-error`/ignore drift.
- Blast radius: All future SQL migrations, production schema safety.
- Current detection: PR workflow only when migration files change.
- Current recovery: Human review.
- Proposed fix: Pin Squawk version, add `.security/squawk_exceptions.yaml` with incident ID, owner, expiry, and migration file. Add `scripts/check_squawk_exceptions.py` to fail expired/unused exceptions. Cell/Genoma: expired exceptions emit `migration_lint_exception_expired`.
- Post-fix verification: `python scripts/check_squawk_exceptions.py`; before no ledger, after every ignore has an owner/expiry.
- Severity: P1.
- Auto-implementable by Claude L2: yes.

### P1-21 Branch protection does not require all resilience gates

- Failure mode: AUTONOMOUS_OPS notes branch protection requires E2E Tests and MCP Server Tests, not necessarily Backend/Frontend/pre-deploy resilience checks. A green merge can still bypass backend import, migration, SW, SSO, and health-ready guards.
- Blast radius: Entire production monorepo, 27-app user baseline.
- Current detection: GitHub branch protection settings, not fully represented in repo.
- Current recovery: Post-merge deploy checks/manual rollback.
- Proposed fix: Add a single required `resilience-gate` workflow that depends on backend import/tests, SQL v2 contract, frontend verify, MCP contract, launchagent contract in dry-run, and browser smoke. Keep it fast and non-network by default. Cell/Genoma: failed required gate writes `resilience_gate_failed` only from CI artifacts when available.
- Post-fix verification: `gh api repos/:owner/:repo/branches/main/protection/required_status_checks` plus CI run; before required checks omit resilience gate, after required gate listed.
- Severity: P1.
- Auto-implementable by Claude L2: code workflow yes; branch protection setting no if GitHub admin required.

### P1-22 Air/Pro network partition has no verified auto-recovery in this session

- Failure mode: Mandatory machine check returned `Peer: UNREACHABLE`, so git sync and Air H24 health could not be verified. User also reports 1 Air HIGH escalation unresolved for 11 days.
- Blast radius: 2-machine sovereignty model, Air H24 server responsibilities, nuz-sync, Air cron jobs, apps/web SSO surface.
- Current detection: Session start check and likely nuz-sync watchdog, but current peer state is unreachable.
- Current recovery: Unknown from this session. Git sync cannot be trusted when peer is unreachable.
- Proposed fix: Make Pro/Air sync a first-class Organism event: `nuz_sync_partition` after 2 failed SSH probes, `air_h24_unverified` after 15 minutes, and `git_sync_out_of_sync` with local/remote SHAs. Cell/Genoma records the partition scar and blocks deploy-from-Air/push-to-origin from Air. Add local queue for sync actions until peer returns.
- Post-fix verification: `python scripts/check_pro_air_sync.py --json`; before peer unreachable is only a printed warning, after structured event with severity and recovery command.
- Severity: P1.
- Auto-implementable by Claude L2: yes for checker/events; network recovery no.

### P1-23 Fly image pull/restart loop/secret rotation is not tied to Cell scars

- Failure mode: Deploy-failure alert covers pre-health failures for migration/deploy, and health rollback covers failed post-deploy health, but image pull failure, restart loop after successful health, and bad secret rotation need structured Cell/Genoma memory to avoid repeating. Evidence: `.github/workflows/fly-deploy.yml:346`, user baseline says Fly app deployed 3h ago with 2 machines.
- Blast radius: 2 Fly backend machines, secrets `QDRANT_URL`, DB, Redis, API keys.
- Current detection: Fly logs/metrics, GitHub deploy alerts, optional fly restart loop detector LaunchAgent.
- Current recovery: Fly restarts on crash; rollback on health failure; manual secret correction.
- Proposed fix: Add post-deploy `fly machines list --json`, per-machine image SHA/readiness check, restart count delta check, and secret contract smoke that validates presence only, never values. Emit `fly_restart_loop` and `fly_secret_contract_failed` to Organism and Genome. Do not edit `fly.toml`.
- Post-fix verification: `scripts/post-deploy-verify.sh --sha "$GITHUB_SHA"` after refactor; before latest-run/health-only, after exact SHA and 2/2 machines ready with restart delta <= threshold.
- Severity: P1.
- Auto-implementable by Claude L2: yes for scripts/workflow; no for changing secrets.

## P2 Manual-Recovery or Detection-Only Gaps

### P2-01 Post-deploy verifier is not SHA-bound and checks only shallow health

- Failure mode: `scripts/post-deploy-verify.sh` identifies the latest in-progress deploy on main, not necessarily the current SHA, and checks `/health` plus a database field. It does not verify `/health/ready`, both Fly machines, frontend browser, SW, or auth canary.
- Blast radius: backend deploy confidence and frontend smoke coverage.
- Current detection: Script output.
- Current recovery: Manual rerun/rollback.
- Proposed fix: Add `--sha` required arg, assert workflow run SHA, query Fly machines for image version, run `/health/ready`, RAG smoke, and frontend Playwright smoke. Cell/Genoma: post-deploy outcome becomes `deploy_verify_passed/failed`.
- Post-fix verification: `scripts/post-deploy-verify.sh --sha "$(git rev-parse HEAD)"`; before can attach wrong run, after mismatch exits non-zero.
- Severity: P2.
- Auto-implementable by Claude L2: yes.

### P2-02 Restore drills are documented but not automated

- Failure mode: AUTONOMOUS_OPS references restore drill, but recovery from DB/Qdrant backup is not part of automated monthly verification in the code paths inspected.
- Blast radius: PostgreSQL, Qdrant Cloud collections, CRM/client data, RAG documents.
- Current detection: Manual checklist.
- Current recovery: Manual restore.
- Proposed fix: Add non-production monthly restore drill workflow using sanitized backup/sample, validate schema version, document counts, and one query per critical collection. Cell/Genoma: record `restore_drill_passed` or `restore_drill_failed` with RTO/RPO numbers.
- Post-fix verification: `gh workflow run restore-drill.yml -f dry_run=true`; before no current automated RTO/RPO artifact, after artifact has restore duration/counts.
- Severity: P2.
- Auto-implementable by Claude L2: workflow skeleton yes; credentials/data policy no.

### P2-03 Circuit breaker and escalation state is visible but not structurally self-healing

- Failure mode: User baseline says 58 circuit breakers, 16 open (28%), 40 escalation cooldowns, 5 Pro pending escalations, 1 Air HIGH unresolved 11 days. Open breakers/cooldowns can become accepted background noise if not tied to recovery proposals and expiry.
- Blast radius: At least 16 active degraded surfaces and 46 total escalation/cooldown items.
- Current detection: Existing circuit breaker/escalation records.
- Current recovery: Manual or Organism shadow-only decisions.
- Proposed fix: Add a Cell pulse that ranks open breakers by age/blast radius, auto-closes only after verification, and proposes one concrete repair PR/task per persistent breaker. Genoma records each breaker as scar or healed scar.
- Post-fix verification: `python scripts/circuit_breaker_report.py --json`; before reports state only, after includes `recovery_action`, `owner`, `next_probe_at`, and `genoma_scar_id`.
- Severity: P2.
- Auto-implementable by Claude L2: yes for reporting/proposals; no for acting on all repairs.

### P2-04 OSINT/Mata Garuda local sovereignty needs recovery checks, not cloud fallback

- Failure mode: Mata Garuda and OSINT LaunchAgents must keep data on Pro. Cloud fallback would violate Law 2, but local crash recovery currently depends on launchd/log scans rather than domain-specific data freshness and no-exfil checks.
- Blast radius: Multiple `com.matagaruda.*` LaunchAgents in the 79-plist local set, OSINT intelligence pipeline, Bali Zero competitive/regulatory monitoring.
- Current detection: LaunchAgent state/logs and daily briefs.
- Current recovery: launchd restart/manual repair.
- Proposed fix: Add `scripts/mata_garuda_local_guard.py`: verify recent output timestamps, no non-local upload targets, Redis/JSONL event emission, and local queue backlog. Cell/Genoma: record `mata_garuda_stale` or `osint_exfil_blocked`. Exception rationale: proposals touch Cell/Genoma, but no cloud recovery is proposed because Law 2 forbids OSINT data leaving Pro.
- Post-fix verification: `python scripts/mata_garuda_local_guard.py --dry-run`; before no single freshness/exfil contract, after outputs counts and event payload.
- Severity: P2.
- Auto-implementable by Claude L2: yes.

### P2-05 Pricing/visa volatile data recovery is detection-only unless source tools are checked

- Failure mode: Rules say never hardcode prices/visa data, but zero-crash resilience also needs recovery when PricingTool/source references are unavailable. Otherwise endpoints may either crash or answer stale facts.
- Blast radius: Pricing/visa routes, client-facing business services, compliance trust.
- Current detection: Source-of-truth docs and code review.
- Current recovery: Manual correction if hardcoded/stale data appears.
- Proposed fix: Add `scripts/check_volatile_fact_sources.py` to verify pricing/visa references route through `PricingTool`, `PRICING_REFERENCE.md`, and `VISA_TYPES_REFERENCE.md`, and that unavailable tool responses produce `ABSTAIN`/`CAUTIOUS` not crashes. Cell/Genoma: record `volatile_fact_source_unavailable`.
- Post-fix verification: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/pricing/test_pricing_tool_failure_modes.py -q`; before unsupported paths may be untested, after unavailable source degrades safely.
- Severity: P2.
- Auto-implementable by Claude L2: yes.

## Highest-Impact Implementation Order

1. P0-01 health/startup truthfulness and P0-06 background supervisor. Without these, crash/recovery state is invisible.
2. P0-03/P0-04 SQL v2 deploy/migration contract. This closes the open structural cicatrix.
3. P0-05 inbound durable inbox. This prevents silent loss after provider ACK.
4. P0-07/P0-08 Cell + Organism reality alignment. This makes Law 8 operational instead of documentary.
5. P1-12/P1-13 System Doctor + AlertBus. This makes non-developer guardrails reliable for Zero.
6. P1-07/P1-08/P1-10 frontend SW/i18n/SSO canaries. These catch user-visible crashes that HTTP health misses.

## Minimum Zero-Crash Acceptance Gate for 2026-04-30

The system should not be considered zero-crash-ready until these before/after numbers are true:

- Backend startup failure paths returning HTTP 503: before unknown/masked, after 100% of injected startup failures.
- SQL v2 duplicate migration numbers: before 2 duplicate numbers, after 0.
- Durable inbound ACK contract: before 0 universal inbox tables, after 7/7 channel adapters ACK only after durable write or explicit non-message ignore.
- Background task supervision: before raw tasks untracked, after 100% critical backend background tasks registered with restart counts.
- Organism active safe dispatch: before shadow/placeholder, after at least 3 safe actuators wired and tested, irreversible actions still Zero-gated.
- Cell boot scars: before early boot failures can miss Genoma, after 100% boot failure tests write a Genome scar.
- LaunchAgent registry coverage: before 79 actual plists vs 19 baseline known, after 100% project-critical plists cataloged and unknown plists explicitly allowed/ignored.
- System Doctor Telegram: before flag builds summary only, after one deduped dry-run alert record per critical report.

