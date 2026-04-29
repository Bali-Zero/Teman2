# Zero-Crash System Resilience Audit
**Date:** 2026-04-29
**Target:** Nuzantara Monorepo (Production AI Platform)
**Goal:** Map every surface where a fault propagates without recovery and propose concrete, auto-implementable fixes. Zero crashes without automatic restart.

---

## 1. BACKEND SURFACES

### 1.1 Fly.io App (OOM & Restart Loops)
- **Failure mode:** Fly.io `nuzantara-rag` container crashes on OOM (exceeding 2GB RAM due to ML loads or `--workers 2+`) or gets stuck in a restart loop from bad secret rotation.
- **Blast radius:** 100% of API traffic, 139 routers, 512 services unreachable.
- **Current detection:** 15-minute `healthcheck@balizero.com` probe or manual discovery.
- **Current recovery:** Manual `flyctl restart` or rollback.
- **Proposed fix:**
  1. Enforce `min_machines = 2` and `auto_rollback = true` in `fly.toml`.
  2. Implement an explicit Docker `HEALTHCHECK` directive.
  3. Enforce `--workers 1` in the Dockerfile `CMD` (Golden Rule #10).
  *Ref: `AUTONOMOUS_OPS.md` (Graceful Degradation)*
- **Post-fix verification:** `fly status --app nuzantara-rag` (expect 2 running, auto-rollback enabled).
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 1.2 Routers & Services (`dependencies.py` SPOF & Async Leaks)
- **Failure mode:** `apps/backend-rag/backend/app/dependencies.py` eagerly loads heavy ML/RAG models (torch, sentence-transformers). If one fails, the entire FastAPI app crashes on startup. `httpx.AsyncClient` isn't closed properly in services, exhausting DB/network pools.
- **Blast radius:** 139 routers fail to register; API offline.
- **Current detection:** Uvicorn startup crash logs, 502 Bad Gateway timeouts.
- **Current recovery:** Process restart via supervisor (if any) or Fly.
- **Proposed fix:**
  1. Refactor `dependencies.py` to lazy-load `get_search_service` and `get_kg_agent`.
  2. Implement global `httpx.AsyncClient` pooling with explicit `yield` cleanup in FastAPI `lifespan` manager in `main.py`.
  *Ref: `SYMBIOSIS.md` (Law 4: Graceful degradation — one organ down != system down)*
- **Post-fix verification:** Induce an import error in a heavy ML module; verify `curl -s http://localhost:8001/health` still returns 200 OK for core routes.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 1.3 SQL v2 Migration Runner (PR #307 Scar)
- **Failure mode:** In `.github/workflows/fly-deploy.yml`, `run-migrations` via `flyctl ssh console` runs against the *old* container filesystem. New SQL v2 files in the same PR are invisible until step 3, so migrations don't apply.
- **Blast radius:** 100% of routes querying the new schema throw 500 errors.
- **Current detection:** Production 500s (`column does not exist`).
- **Current recovery:** Manual `gh workflow run` after merge.
- **Proposed fix:** Add a `run-sql-v2-migrations-post-deploy` job in `fly-deploy.yml` that runs *after* the `deploy` step. It must wait for the new image to become healthy, then run `python -m backend.db.migrate apply-all`.
- **Post-fix verification:** Deploy a test `.sql` migration; `fly logs` show applying migration *post-deploy*.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 1.4 Drive Polling (Air OAuth 90gg)
- **Failure mode:** Google Drive polling script on Air machine stops silently when OAuth token expires after 90 days.
- **Blast radius:** CRM document ingestion blocked for all clients.
- **Current detection:** None (silent failure).
- **Current recovery:** Manual `gemini auth login` on Air.
- **Proposed fix:** Add a cron job in `infra/cron_drive_poll.sh` checking token expiry date in `~/.gemini/oauth_creds.json` and sending a Telegram alert via EventBus at 80 days. (Or migrate to Service Account).
  *Ref: `cell_core.genome` (Record OAuth expiry as stressor).*
- **Post-fix verification:** Run token check script; output shows valid days remaining.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 1.5 Background Cron Jobs (12+ on Air)
- **Failure mode:** Air cron jobs fail silently due to environment path issues (not sourcing virtualenv) or overlaps.
- **Blast radius:** Background tasks (billing, backups, daily reports) fail.
- **Current detection:** No built-in cron observability.
- **Current recovery:** Manual execution.
- **Proposed fix:** Wrap all cron commands with a generic wrapper (`infra/cron_wrapper.sh`) that sources `.venv`, uses file locks (`flock`) to prevent overlap, and logs failures to Redis EventBus.
- **Post-fix verification:** `crontab -l` (verify wrappers); trigger a fake failure and check Redis Stream.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 1.6 Channels Webhook Resilience (Twitter CRC broken)
- **Failure mode:** Webhooks for channels (WhatsApp, Telegram, Twitter) drop messages if backend processing >3s. Twitter CRC fails randomly, disabling the webhook.
- **Blast radius:** Dropped messages from clients.
- **Current detection:** Twitter developer portal shows webhook deactivated.
- **Current recovery:** Manual reactivation.
- **Proposed fix:** Offload all webhook processing to Redis Streams immediately in the FastAPI router (return 200 OK instantly). For Twitter CRC, cache the expected hash and respond <1s.
  *Ref: `SYMBIOSIS.md` (Law 3: Event-driven Redis Streams).*
- **Post-fix verification:** Send 10 concurrent webhook requests; observe 100% 200 OK within 50ms.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 1.7 EventBus Redis
- **Failure mode:** Redis crashes or reaches max memory. Event-driven `redis.xadd()` fails synchronously, crashing the main API thread.
- **Blast radius:** 100% of async processing stops, API 500s.
- **Current detection:** Redis ping failure.
- **Current recovery:** Restart Redis.
- **Proposed fix:** Wrap `redis.xadd()` calls in try/except blocks. If Redis is down, log locally to SQLite (fallback buffer) or discard non-critical events. Respect Graceful Degradation.
  *Ref: `SYMBIOSIS.md` (Law 4: Graceful Degradation).*
- **Post-fix verification:** Stop local Redis, trigger an event; API must return 200 OK (buffered).
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 1.8 KG Subgraph Generation
- **Failure mode:** LangGraph node generation fails mid-way due to timeout or LLM parse error, leaving an orphaned or partial subgraph in Qdrant/Postgres.
- **Blast radius:** Incomplete/hallucinated answers for KBLI/Visa queries relying on that subgraph.
- **Current detection:** LangSmith run shows error, but no system alert.
- **Current recovery:** Manual deletion of partial nodes.
- **Proposed fix:** Wrap subgraph generation in DB transactions (for Postgres) and use a temporary staging payload for Qdrant. Only commit/upsert if the entire LangGraph execution completes successfully.
- **Post-fix verification:** Induce an LLM error mid-generation; assert graph edge/node count remains exactly unchanged.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

---

## 2. FRONTEND SURFACES

### 2.1 Mouth Next.js (i18n Provider per route group PR #273)
- **Failure mode:** Missing translations or context errors during SSR because i18n provider is instantiated multiple times per route group, leading to hydration mismatches.
- **Blast radius:** Non-Italian/English users see blank pages or broken UI.
- **Current detection:** Vercel build warnings, Sentry hydration errors.
- **Current recovery:** Rebuild.
- **Proposed fix:** Move i18n provider to the root `layout.tsx` (App Router) or use server-side dictionary loading correctly as per PR #273 to avoid client-side context leakage.
- **Post-fix verification:** Run Next.js build; check Vercel bundle sizes and hydration logs.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 2.2 Service Worker Cache Poisoning
- **Failure mode:** Next.js Service Worker caches bad JS chunks or old API responses indefinitely.
- **Blast radius:** Returning users stuck on a broken version ("white screen of death").
- **Current detection:** User reports.
- **Current recovery:** User has to manually clear browser cache.
- **Proposed fix:** Update `next-pwa` config to bypass cache for `/api/` routes and add proper version hashing. Auto-unregister old service workers on major version changes in `_app.tsx` / `layout.tsx`.
- **Post-fix verification:** Deploy new version; verify SW automatically updates within 1 minute.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 2.3 Vercel Build Env Vars
- **Failure mode:** Vercel deploy fails because a new env var was added to the backend but forgotten in Vercel project settings.
- **Blast radius:** Frontend deploy fails, or deploys but crashes client-side.
- **Current detection:** Vercel deploy logs.
- **Current recovery:** Add variable in Vercel UI and redeploy.
- **Proposed fix:** Add a `"prebuild": "node scripts/check-env.js"` script in `package.json` that asserts required public environment variables exist before starting the Next.js build.
- **Post-fix verification:** Remove an env var locally; `npm run build` must fail immediately with a clear error.
- **Severity:** P2
- **Auto-implementable by Claude L2:** Yes

---

## 3. LOCALS (ORGANI LOCALI)

### 3.1 apps/cell & apps/organism (Nervous System)
- **Failure mode:** The core nervous system (`apps/cell`) crashes due to a SQLite locking error (`database is locked`), taking down all autonomous ops.
- **Blast radius:** All background autonomous agents stop. No new skills recorded, no self-healing.
- **Current detection:** `system_doctor` misses it if it only checks HTTP ports.
- **Current recovery:** Manual restart of the python process.
- **Proposed fix:**
  1. Implement SQLite WAL mode (`PRAGMA journal_mode=WAL;`) in `cell_core.memory`.
  2. Wrap the main `PulseLoop` in a supervisor daemon (`supervisord` or macOS LaunchAgent with `KeepAlive=true`) that auto-restarts on crash.
  *Ref: `SYMBIOSIS.md` (Cell + Genoma central).*
- **Post-fix verification:** `kill -9` the cell process; verify it restarts within 5s via LaunchAgent.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 3.2 Mata Garuda OSINT
- **Failure mode:** OSINT scraper hits rate limits (429) or IP bans, crashing the pipeline instead of pausing.
- **Blast radius:** Fresh intel gathering stops. (Zero impact on core API).
- **Current detection:** Empty intel staging queue.
- **Current recovery:** Rotate IP/VPN manually.
- **Proposed fix:** Catch 429 errors. Implement an exponential backoff circuit breaker in the scraper. If banned, sleep for 24h and record a scar in `cell_core.genome`.
  *Ref: `CLAUDE.md` (OSINT data never leaves Pro).*
- **Post-fix verification:** Mock a 429 response; ensure scraper pauses, logs, and sleeps.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 3.3 MCP Servers (nuzantara-mcp, advanced, browser)
- **Failure mode:** MCP servers crash/hang when the host (Claude/Gemini) sends a malformed JSON payload.
- **Blast radius:** CLI tooling and LLM workflows become unresponsive.
- **Current detection:** Connection refused in LLM logs.
- **Current recovery:** Restart MCP servers.
- **Proposed fix:** Add broad `try/except` around the MCP message handlers. Use PM2 or LaunchAgents configuration to ensure `KeepAlive=true` for all 3 MCP servers.
- **Post-fix verification:** Send malformed JSON via socket; ensure server rejects but stays alive.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

---

## 4. DEPLOY/CI

### 4.1 `fly-deploy.yml` Pipeline Status Blindspot
- **Failure mode:** Deploy crashes *before* the health check (Scar: Air A3, 2026-04-18). Telegram alert only triggers on `post-deploy-health`. If `pre-deploy-gate` or `run-migrations` fails, the workflow skips health check and fails silently.
- **Blast radius:** Zero visibility on failed deploys.
- **Current detection:** Dev notices PR merged but not live.
- **Current recovery:** Manual checking of Actions.
- **Proposed fix:** Add an `always()` status notification step at the very end of `fly-deploy.yml` that summarizes the pipeline status (Success/Failed/Skipped) to Telegram, regardless of where it failed.
- **Post-fix verification:** Intentionally fail `pre-deploy-gate`; confirm Telegram alert received.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 4.2 Squawk Migration Lint Bypass Tracking
- **Failure mode:** Developer bypasses Squawk via `-- squawk-ignore: ban-drop-column` but forgets to add it to a tracking issue.
- **Blast radius:** Accidental data loss (dropped columns/tables).
- **Current detection:** Squawk allows it.
- **Current recovery:** Restore from backup (Nightmare).
- **Proposed fix:** Add a GitHub Action that `grep`s for `squawk-ignore` in changed SQL files and automatically posts a PR comment requiring Admin approval, or blocks the merge unless the `risk-accepted` label is present.
- **Post-fix verification:** Add `squawk-ignore` to a test PR; verify Action blocks merge.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

---

## 5. OBSERVABILITY

### 5.1 Langfuse Tracing (PR #312 Dormant)
- **Failure mode:** Langfuse tracing is dormant by default. If the RAG chain hallucinates, debugging the intermediate steps takes hours.
- **Blast radius:** RAG debugging is blind.
- **Current detection:** Client complains about wrong KBLI response.
- **Current recovery:** Enable Langfuse manually and ask client to repeat.
- **Proposed fix:** Activate Langfuse tracing natively. Configure dynamic sampling rate: 10% for NORMAL confidence, 100% for CAUTIOUS/ABSTAIN responses (Evidence Scoring).
  *Ref: `GEMINI.md` (Evidence Scoring).*
- **Post-fix verification:** Trigger a CAUTIOUS response; verify trace appears in Langfuse.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes

### 5.2 `system_doctor` 08:00 Blindspots
- **Failure mode:** `system_doctor` runs daily but only checks HTTP ports. It misses Qdrant Cloud health (`nuzantara-qdrant` is SUSPENDED), Fly.io volume usage, and Air cron execution statuses.
- **Blast radius:** Disk full or Vector DB offline goes unnoticed until production failure.
- **Current detection:** 500 errors in production.
- **Current recovery:** Manual cleanup.
- **Proposed fix:** Add Qdrant connection test (`QDRANT_URL`), Fly.io volume metrics check (via flyctl API), and Air cron heartbeat verification to `system_doctor.py`.
- **Post-fix verification:** Run `system_doctor`; ensure Qdrant and Disks sections are explicitly verified.
- **Severity:** P0
- **Auto-implementable by Claude L2:** Yes

### 5.3 Telegram Chat Rate-Limit / Dedup
- **Failure mode:** An error loop generates 10,000 Telegram messages, getting the bot rate-limited and banned by Telegram.
- **Blast radius:** All monitoring alerts stop working.
- **Current detection:** Bot stops sending messages.
- **Current recovery:** Wait 24h for Telegram unban.
- **Proposed fix:** Implement a Redis-based token bucket rate limiter/deduplicator for the Telegram webhook/notifier service. If identical error > 5 times in 1 min, send "Muting further alerts for this error" and suppress.
- **Post-fix verification:** Trigger 50 identical errors; verify only 5 messages sent + 1 mute notification.
- **Severity:** P1
- **Auto-implementable by Claude L2:** Yes
