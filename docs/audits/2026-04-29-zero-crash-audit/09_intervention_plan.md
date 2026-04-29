# Intervention plan — Zero-crash roadmap

**Goal:** From 2026-04-30, no Nuzantara crash without automatic recovery.
**Date:** 2026-04-29
**Author:** Opus 4.7 (synthesizer of 5-LLM analysis)

---

## Reading guide

For each surface with recovery gap below:
- **Severity:** P0 (crash without recovery now) | P1 (degrade without alert) | P2 (manual recovery)
- **Confidence:** High (4-5 LLM convergence) | Medium (2-3 LLM) | Low (1 LLM only)
- **Convergence:** which LLMs identified it
- **Cell/Genoma touchpoint:** yes/no — see `10_cell_genoma_alignment.md`

Order: P0 first by severity, then P1, then P2. Within each tier, ordered by ease of implementation.

---

## P0-0 — `/health` masks `startup_failed=True` → Fly never restarts

> **Highest priority. Discovered by Codex, NOT in original brief.**

**Severity:** P0 · **Confidence:** High · **Convergence:** Codex empirical (only — others missed)
**Cell/Genoma touchpoint:** yes (Cell HealthSensor must align)

### Failure mode

`apps/backend-rag/backend/app/setup/app_factory.py:114-118` catches critical service init RuntimeError, sets `app.state.startup_failed=True`, but does NOT propagate to /health endpoint. `apps/backend-rag/backend/app/routers/health.py:48-55` defines `_check_startup_failed()` helper — but `health_check()` at line 147-266 NEVER CALLS IT.

Result: backend with broken critical services keeps returning HTTP 200 from `/health`. **Fly auto-restart only fires on non-2xx**. So a deterministically-broken backend stays "healthy" forever, no Telegram alert, no rollback, no recovery.

### Blast radius

100% API down while monitoring shows green. Worse than P0-1 (SearchService fail-fast) because P0-1 at least crashes loudly. P0-0 is a SILENT crash that pretends to be alive.

This is exactly the 2026-04-29 03:11Z incident pattern — kita.balizero.com login broke, Fly didn't restart, manual intervention required (memory `discovery_2026_04_29`).

### Stato attuale

- **Detection:** Login healthcheck@balizero.com (15min lag) catches it via login flow. /health alone is BLIND.
- **Recovery:** Manual `fly machines restart`.

### Fix proposto

File: `apps/backend-rag/backend/app/routers/health.py`

```python
async def health_check(request: Request, response: Response) -> HealthResponse:
    # Check startup status FIRST
    startup_error = _check_startup_failed(request.app)
    if startup_error:
        response.status_code = 503
        return HealthResponse(
            status="unhealthy",
            version=settings.VERSION,
            message=f"startup_failed: {startup_error}",
            database={"status": "unknown", "type": "postgresql"},
            embeddings={"status": "unknown"}
        )
    # ... rest of existing health_check
```

ALSO: warmup deadline. If `app.state.startup_started_at` is set and `time.time() - app.state.startup_started_at > 180` AND state is still `initializing`, return 503. Prevents indefinite "warming up" facade.

ALSO: Light API process must require `db_pool != None` for `database.status="connected"`. Currently it returns connected even if pool init failed.

### Cell parallel fix

File: `apps/cell/cell/sensors/health_sensor.py` and `apps/cell/cell/core/pulse.py`

Cell pulse currently classifies green based on `reading.reachable and reading.status_code == 200`. Must extend:

```python
# pulse.py
def classify(reading) -> str:
    if not reading.reachable: return "red"
    if reading.status_code != 200: return "red"
    body_status = reading.body.get("status") if isinstance(reading.body, dict) else None
    if body_status in ("unhealthy", "startup_failed", "failed"):
        return "red"
    if body_status in ("degraded", "initializing"):
        return "yellow"
    return "green"
```

### Verifica post-fix

```bash
# Test 1: simulate startup_failed
cd apps/backend-rag && source .venv/bin/activate
SEARCH_FORCE_FAIL=1 PYTHONPATH=. uvicorn backend.app.main_api:app --port 8001 &
sleep 5
curl -sI http://localhost:8001/health | head -1
# Expected: HTTP/1.1 503 Service Unavailable (NOT 200)

# Test 2: warmup deadline
# Inject 200s "initializing" delay
WARMUP_FORCE_DELAY=200 PYTHONPATH=. uvicorn ... &
sleep 30
curl -sI http://localhost:8001/health | head -1
# Expected: HTTP/1.1 200 (initializing) at 30s
sleep 180
curl -sI http://localhost:8001/health | head -1
# Expected: HTTP/1.1 503 (timeout exceeded)

# Test 3: Cell sensor
# Send a body with status="startup_failed" to Cell HealthSensor
# Verify Cell pulse classifies as RED, triggers actor (Telegram alert + restart attempt)
```

Numbers before/after:
- Before: deterministic startup failure = 100% API down + monitoring green (silent crash)
- After: deterministic startup failure = 503 from /health → Fly restart attempt → Telegram alert via deploy-failure-alert OR Sentinel circuit breaker

### Owner & deadline

**Auto-implementable L2:** ✓ Yes. Three files: `health.py` (3 lines), `app_factory.py` (track startup_started_at), `pulse.py` (classify body status). Reversible via git revert.
**Estimated effort:** 1-2 hours including tests.

> **Implement this BEFORE all others.** Without it, every other fix is hidden by silent green health.

---

## P0-1 — SearchService fail-fast → restart loop

**Severity:** P0 · **Confidence:** High · **Convergence:** Opus, Gemini, DeepSeek, NB-1
**Cell/Genoma touchpoint:** yes (genome scar `searchservice_init_failure_pattern`)

### Failure mode

`backend.app.setup.service_initializer._init_critical_services` raises uncaught `RuntimeError` if SearchService or ZantaraAIClient fail to init. Fly auto-restart loops because the failure is deterministic (e.g., bad embedding model load).

### Blast radius (numeri prima)

- 100% API down
- 88 registered routers offline
- 7 channels stop processing
- /api/query 502
- kita.balizero.com login fails
- Estimated 5000+ clients affected
- Fly billing keeps charging on restart loops (~$0.0001/restart but cumulative)

### Stato attuale

- **Detection:** GH Action `cron-fly-restart-detector.yml` every 15 min + healthcheck@balizero.com login probe every 15 min. Lag = up to 14 min before notification.
- **Recovery:** None automatic. Fly restarts but the deterministic crash repeats. Manual `fly releases rollback` required.

### Fix proposto

File: `apps/backend-rag/backend/app/setup/service_initializer.py`

Convert `_init_critical_services` to log-and-degrade:

```python
async def _init_critical_services(app: FastAPI) -> tuple[Any, Any]:
    """Initialize critical services with degraded-mode fallback.

    Previously fail-fast (raised RuntimeError → Fly restart loop on deterministic crash).
    Now: log error, register `degraded` flag in app.state, allow uvicorn to bind 8080.
    Health endpoint reports degraded; /api/query returns 503 with structured error.
    """
    try:
        search_service = await _init_search_service(app)
    except Exception as e:
        logger.exception("SearchService init failed; entering degraded mode")
        search_service = None
        app.state.degraded_services = (app.state.__dict__.get('degraded_services') or set()) | {'search'}

    try:
        ai_client = await _init_ai_client(app)
    except Exception as e:
        logger.exception("ZantaraAIClient init failed; entering degraded mode")
        ai_client = None
        app.state.degraded_services |= {'ai_client'}

    return search_service, ai_client
```

Also update `/health` to report `degraded` array, and `dependencies.get_search_service` to return 503 with structured `{error: "search_unavailable", retry_after: 60}` when degraded.

### Verifica post-fix

```bash
# Test 1: induce SearchService import failure
cd apps/backend-rag && source .venv/bin/activate
SEARCH_FORCE_FAIL=1 PYTHONPATH=. uvicorn backend.app.main_api:app --port 8001 &
sleep 5
curl -s http://localhost:8001/health | jq '.degraded_services'
# Expected: ["search"]
curl -s http://localhost:8001/api/query -X POST -d '{"q":"test"}' -H "X-API-Key: $API_KEY" | jq '.error'
# Expected: "search_unavailable"

# Test 2: verify uvicorn stays bound
curl -sI http://localhost:8001/health | head -1
# Expected: 200 OK (NOT exit code from uvicorn)
```

Numbers before/after:
- Before: deterministic init failure = Fly restart loop = 100% API down
- After: deterministic init failure = uvicorn bound, /health reports degraded, /api/query 503 — backend serves OTHER routes (channels, /static, etc.)

### Owner & deadline

**Auto-implementable L2:** ✓ Yes. Single file change, additive, reversible.
**Estimated effort:** 30-60 min.

---

## P0-2 — EventBus PG LISTEN/NOTIFY without Outbox = silent event loss

**Severity:** P0 · **Confidence:** High · **Convergence:** NB-1 (authoritative), Opus (after correction), DeepSeek, Gemini
**Cell/Genoma touchpoint:** yes (genome skill `outbox_pattern_for_pg_eventbus`)

### Failure mode

EventBus `services/events/` uses `pg_notify` over PostgreSQL channels. When the listener disconnects (`_RECONNECT_DELAY_S = 5`), every NOTIFY published during the window is lost — pg_notify is volatile, no queue.

NB-1 cited the actual code in `backend/services/events/handlers/__init__.py` confirming the architecture. Symbiosis.md Law 4 documentation says "Redis Streams" — drift.

### Blast radius

Per NB-1, affected channels:
- `practice.status_changed` (CRM practice updates)
- `client.changed`
- `compliance.alert`
- `lkpm.ingest_completed` (tax reporting)
- `war_room.event` → review_handler Telegram, publisher_worker, measurer_worker, dashboard_sse
- `intel.event` → 4 cognitive layer tables (cross_dossier_theses, wr_anomaly_alerts, weekly_strategic_briefs, ultra_moves)
- `cognitive.event`

Lost events per minute of PG outage = 10-50 (estimate based on regular workload).

### Stato attuale

- **Detection:** None. `_RECONNECT_DELAY_S` reconnects but doesn't replay.
- **Recovery:** None. Lost events vanish.

### Fix proposto

Two-step.

**Step A: Outbox table migration (new SQL v2)**

File: `apps/backend-rag/backend/db/migrations_v2/141_events_outbox.sql`

```sql
CREATE TABLE events_outbox (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_at TIMESTAMPTZ NULL,
    last_consumer TEXT NULL,
    CONSTRAINT events_outbox_pk_id PRIMARY KEY (id)
);
CREATE INDEX events_outbox_pending ON events_outbox (channel, published_at)
    WHERE consumed_at IS NULL;
CREATE INDEX events_outbox_published_at ON events_outbox (published_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS events_outbox_pending;
DROP INDEX IF EXISTS events_outbox_published_at;
DROP TABLE IF EXISTS events_outbox;
```

**Step B: Outbox helper + EventBus integration**

File: `apps/backend-rag/backend/services/events/outbox.py` (model on existing `services/bridge/outbox.py`)

```python
async def write(conn: asyncpg.Connection, channel: str, payload: dict) -> int:
    row = await conn.fetchrow(
        """INSERT INTO events_outbox (channel, payload)
           VALUES ($1, $2::jsonb)
           RETURNING id""",
        channel, json.dumps(payload)
    )
    await conn.execute(f"NOTIFY {pg_quote_ident(channel)}, $1", json.dumps({**payload, '_outbox_id': row['id']}))
    return row['id']
```

EventBus publishers must call `outbox.write()` instead of `conn.execute("NOTIFY ...")`.

Add a recovery daemon in `services/events/recovery.py`:

```python
async def replay_unconsumed_events(conn: asyncpg.Connection, max_age_minutes: int = 60):
    """Replay unconsumed events from outbox. Called on listener reconnect."""
    rows = await conn.fetch(
        """SELECT id, channel, payload FROM events_outbox
           WHERE consumed_at IS NULL
             AND published_at > NOW() - INTERVAL '%s minutes'
           ORDER BY published_at""",
        max_age_minutes
    )
    for r in rows:
        await conn.execute(f"NOTIFY {r['channel']}, $1", json.dumps({**json.loads(r['payload']), '_replay': True, '_outbox_id': r['id']}))
    return len(rows)
```

Consumers acknowledge by `UPDATE events_outbox SET consumed_at = NOW(), last_consumer = $1 WHERE id = $2`.

### Verifica post-fix

```bash
# Test: drop PG connection during war_room event
fly proxy 5432:5432 -a nuzantara-postgres &
PGPID=$!
# Trigger 100 war_room events
for i in {1..100}; do
  curl -X POST .../api/war_room/post -d '...'
done
# Kill PG proxy
kill $PGPID
sleep 30
# Resume
fly proxy 5432:5432 -a nuzantara-postgres &
sleep 60
# Verify
psql ... -c "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
# Expected: 0 (all consumed via replay)
```

Before/after:
- Before: 100 events, 30s outage = ~30 events lost (depending on disconnect timing)
- After: 0 lost — all replayed on reconnect

### Owner & deadline

**Auto-implementable L2:** ✓ partial. Migration + outbox helper auto. Refactor of all `pg_notify` callsites is mechanical but extensive (search: `rg "pg_notify|NOTIFY " apps/backend-rag/backend/services`).
**Estimated effort:** 1 day for migration+helper, 2-3 days for refactor of all callsites + tests.

> **Note:** This also requires updating SYMBIOSIS.md Law 4 to clarify the EventBus uses PG, OR migrating to Redis Streams (the larger architectural decision). The fix above keeps PG and adds the missing durability layer.

---

## P0-3 — Cell/Organism processes have no auto-restart (LaunchAgents audit)

**Severity:** P0 · **Confidence:** High · **Convergence:** Opus, Gemini, DeepSeek, NB-1, Codex (empirical)
**Cell/Genoma touchpoint:** META — fixes the cell substrate itself.

### Failure mode

53 project LaunchAgents (Codex empirical):
- Only **7 (13%)** have `KeepAlive=true`
- **11 (21%)** have NO `KeepAlive` directive at all
- **5 (9%)** missing `EnvironmentVariables` (VADEMECUM §11 violation, scar documented)
- **6 (11%)** logging to `/tmp/` (lost on reboot, breaks Sentinel)

### Blast radius

Each unmonitored daemon is a single-process SPOF. Critical examples:
- `com.balizero.nlm-bridge` — NLM bridge between Pro and Fly (without it, NB-1..NB-10 pipelines fail silently)
- `com.balizero.intel.nightly` — daily intel scraper
- `com.balizero.post-publish-poller` — feeds publisher_worker
- `com.cell.organism.plist` — the actual organism

### Stato attuale

- **Detection:** Sentinel reads `~/.agent/decisions/sentinel_status.json` — but only sees jobs registered in `~/.agent/decisions/job_registry.json`. Many plist NOT in registry.
- **Recovery:** Manual SSH + `launchctl kickstart`.

### Fix proposto

**Step A: Launchd lint script**

File: `scripts/lint_launchagents.sh`

```bash
#!/usr/bin/env bash
# Validate all project plist against VADEMECUM §11
set -e
PLIST_DIR=~/Library/LaunchAgents
VIOLATIONS=0
for plist in "$PLIST_DIR"/com.{nuzantara,balizero,cell}.*.plist; do
    [ -f "$plist" ] || continue
    label=$(plutil -extract Label raw "$plist")

    # Daemon must have KeepAlive=true
    if ! plutil -extract KeepAlive json "$plist" >/dev/null 2>&1; then
        echo "VIOLATION: $label missing KeepAlive (set true if daemon, false if cron-style)"
        ((VIOLATIONS++))
    fi

    # All must have EnvironmentVariables
    if ! plutil -extract EnvironmentVariables json "$plist" >/dev/null 2>&1; then
        echo "VIOLATION: $label missing EnvironmentVariables (PATH+HOME mandatory)"
        ((VIOLATIONS++))
    fi

    # Logs must NOT be in /tmp/
    out=$(plutil -extract StandardOutPath raw "$plist" 2>/dev/null || echo "")
    err=$(plutil -extract StandardErrorPath raw "$plist" 2>/dev/null || echo "")
    if [[ "$out" == /tmp/* ]] || [[ "$err" == /tmp/* ]]; then
        echo "VIOLATION: $label logs to /tmp/ (lost on reboot)"
        ((VIOLATIONS++))
    fi
done
echo "Total violations: $VIOLATIONS"
exit $VIOLATIONS
```

**Step B: PreToolUse hook**

Add to `~/.claude/settings.json`:

```json
{
  "hooks": [{
    "matcher": "Edit|Write",
    "matcher_args": ["**/Library/LaunchAgents/*.plist"],
    "type": "command",
    "command": "bash ~/Desktop/nuzantara/scripts/lint_launchagents.sh"
  }]
}
```

**Step C: Mass plist patch**

For each violator, add proper directives. Example template patch:
- `com.balizero.intel.nightly`: this is daily-cron — KeepAlive=false, has EnvironmentVariables, logs to ~/logs/
- `com.balizero.nlm-bridge`: this IS daemon — KeepAlive=true, EnvironmentVariables present, logs to ~/logs/

Auto-classify by inspecting `<key>StartInterval</key>` (cron-like = false) vs `<key>RunAtLoad</key>` and absence of timing keys (daemon = true).

**Step D: Job registry sync**

For each daemon plist, ensure entry exists in `~/.agent/decisions/job_registry.json` so Sentinel monitors it.

### Verifica post-fix

```bash
bash scripts/lint_launchagents.sh
# Expected: Total violations: 0

# Kill Cell process; verify launchd respawns within 10s
PID=$(launchctl list com.cell.organism | jq -r .PID)
kill -9 $PID
sleep 15
NEW_PID=$(launchctl list com.cell.organism | jq -r .PID)
[ -n "$NEW_PID" ] && [ "$NEW_PID" != "$PID" ] && echo "PASS: respawned"
```

Numbers:
- Before: 7/53 KeepAlive=true (13%)
- After audit: ~25-30/53 KeepAlive=true (proper daemon classification, the rest are cron-style with KeepAlive=false explicit)
- Before: 5/53 missing EnvironmentVariables
- After: 0 missing

### Owner & deadline

**Auto-implementable L2:** ✓ partial. Lint script + hook auto. Mass plist patch is mechanical but each one needs a daemon-vs-cron classification call (some plist may be ambiguous). Estimated 30-60 min per ambiguous plist + 5 min per clear case. Total ~3 hours.

---

## P0-4 — SQL v2 migration deploy ordering bug (PR #307 STRUCTURAL)

**Severity:** P0 · **Confidence:** High · **Convergence:** Opus (cicatrix), Gemini, DeepSeek
**Cell/Genoma touchpoint:** no (CI/build-time, not organ runtime)

### Failure mode

Already documented in `.claude/rules/cicatrix-scars.md` 2026-04-26. `flyctl ssh console --command "python -m backend.db.migrate apply-all"` runs against OLD container image (pre-deploy), so new SQL v2 files in same PR aren't applied.

### Blast radius

Per PR with new SQL v2 + code expecting new schema → 500 errors on routes touching new column. Window 5-30min before manual `gh workflow run` re-trigger.

### Stato attuale

- **Detection:** Production 500s observed by users / monitoring.
- **Recovery:** Manual `gh workflow run "Deploy Backend to Fly.io" --ref main`.

### Fix proposto

File: `.github/workflows/fly-deploy.yml`

Add new job after `deploy`:

```yaml
run-sql-v2-migrations-post-deploy:
  needs: [deploy, run-python-migrations]
  if: always() && needs.deploy.result == 'success'
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Wait for new image to be live
      run: |
        # Use the same sentinel approach as run-python-migrations
        for i in {1..30}; do
          STATUS=$(flyctl status -a nuzantara-rag --json 2>/dev/null | jq -r '.Allocations[0].Image')
          if [[ "$STATUS" == *"$DEPLOY_SHA"* ]]; then break; fi
          sleep 10
        done
    - name: Re-run SQL v2 migrations on fresh image
      env:
        FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
      run: |
        flyctl ssh console --app nuzantara-rag \
          --command "/bin/sh -c 'cd /app && PYTHONPATH=. python -m backend.db.migrate apply-all'" \
          | tee migration_log.txt
        # Idempotent: runner skips applied via _schema_versions table
        # Verify: count "Applying migration" lines == count of new SQL files in PR
```

### Verifica post-fix

```bash
# Plant a test migration
echo "
CREATE TABLE audit_canary_$(date +%s) (id BIGSERIAL PRIMARY KEY);
-- === ROLLBACK ===
DROP TABLE IF EXISTS audit_canary_$(date +%s);
" > apps/backend-rag/backend/db/migrations_v2/141_audit_canary.sql

# Open PR, merge
# Verify both:
# 1. run-migrations (pre-deploy): does NOT apply 141 (old image)
# 2. run-sql-v2-migrations-post-deploy: applies 141
gh run view <run-id> --log | grep "Applying migration 141"
# Expected: 1 occurrence in post-deploy job
```

### Owner & deadline

**Auto-implementable L2:** ✓ Yes. Single workflow YAML edit. Reversible.
**Estimated effort:** 30 min including verification.

---

## P0-5 — dependencies.py SPOF + Golden Rule #10 violations

**Severity:** P0 · **Confidence:** High · **Convergence:** Opus, Gemini, DeepSeek, NB-1
**Cell/Genoma touchpoint:** yes (genome scar `golden_rule_10_violations_fixed_2026_04_29`)

### Failure mode

Two compounding issues:
1. `dependencies.py` raises `HTTPException` if service missing from `app.state` → fail-fast at request time
2. Scattered `httpx.AsyncClient(` instantiations leak sockets → eventual FD exhaustion → process crash

### Blast radius

Slow degradation (latency spikes) culminating in deterministic OOM/FD-exhaustion crash → restart loop.

### Stato attuale

- **Detection:** Prometheus `zantara_ai_latency_seconds` histogram observable but no alert rule.
- **Recovery:** `self_healing/backend_agent.py` daemon restarts container on health check failure — but the leak is deterministic, so loop.

### Fix proposto

**Step A: Audit + convert all httpx.AsyncClient instantiations**

```bash
# Find all violators
rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend > /tmp/httpx_audit.txt
# Expected: hundreds of hits.
# Filter for non-_http.py files (the legitimate pattern lives in *_http.py)
rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend | grep -v "_http\.py" > /tmp/httpx_violations.txt
```

For each violator, convert to lazy-singleton pattern (template from `services/notifications/email_http.py`):

```python
_client: httpx.AsyncClient | None = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client

async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None

# Register in app_factory.lifespan() shutdown hook
```

**Step B: Convert dependencies.py fail-fast → log-and-degrade**

File: `apps/backend-rag/backend/app/dependencies.py`

```python
def get_search_service(request: Request) -> SearchService:
    svc = getattr(request.app.state, 'search_service', None)
    if svc is None:
        # Was: raise HTTPException(503, ...)
        # Now: structured response with retry hint
        raise HTTPException(
            status_code=503,
            detail={
                "error": "search_unavailable",
                "retry_after_seconds": 60,
                "degraded_services": list(getattr(request.app.state, 'degraded_services', set()))
            }
        )
    return svc
```

**Step C: CI lint to prevent regression**

File: `.github/workflows/lint-golden-rule-10.yml`

```yaml
name: Golden Rule #10 lint
on: [pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          VIOLATIONS=$(rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend | grep -v "_http\.py" | wc -l)
          if [ "$VIOLATIONS" -gt 0 ]; then
            echo "::error::Found $VIOLATIONS Golden Rule #10 violations"
            rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend | grep -v "_http\.py"
            exit 1
          fi
```

### Verifica post-fix

```bash
# Test 1: monitored FD count
PID=$(pgrep -f "uvicorn.*main_api")
lsof -p $PID | wc -l
# Run synthetic load
ab -n 10000 -c 50 http://localhost:8001/api/query
lsof -p $PID | wc -l
# Expected: stable FD count (was: monotonic climb)

# Test 2: degrade response
SEARCH_FORCE_FAIL=1 PYTHONPATH=. uvicorn ... &
sleep 5
curl -s http://localhost:8001/api/query -d '{"q":"x"}' | jq
# Expected: {"error": "search_unavailable", "retry_after_seconds": 60, "degraded_services": ["search"]}
```

### Owner & deadline

**Auto-implementable L2:** ✓ partial. Step A is mechanical (rewrite each callsite), Step B+C auto. Step A volume = ~50-200 callsites estimated. Tests must pass per callsite.
**Estimated effort:** 1-2 days for full audit + convert + tests.

---

## P0-6 — Channels webhook resilience (sync processing + Twitter CRC)

**Severity:** P0 · **Confidence:** Medium-High · **Convergence:** Opus, Gemini, NB-1, Codex
**Cell/Genoma touchpoint:** yes (genome skill `webhook_ack_first_pattern`)

### Failure mode

Two issues:
1. Webhook routers process synchronously. If processing >3s, Meta/Twitter auto-disable webhook after 3 failures in 5 min.
2. Twitter X CRC handshake broken since 2026-04-03 (already disabled in `logging_config.py`).

### Blast radius

- WhatsApp: 100% missed messages during processing slowdown.
- Instagram: same as WhatsApp.
- Twitter: 100% missed (disabled).
- Telegram: less affected (bot polling).

### Stato attuale

- **Detection:** Twitter dev portal shows webhook deactivated (no auto-alert). Meta has dashboard but no integration.
- **Recovery:** Manual webhook re-registration. For Twitter, fix CRC + re-register.
- **Outbound DLQ exists** (table `failed_messages`, migration 086) — inbound has no equivalent.

### Fix proposto

**Step A: Inbound webhook ack-first pattern**

For each webhook router:

```python
# Was: process synchronously, return after
@router.post("/webhook/whatsapp")
async def whatsapp_webhook(payload: dict, db_pool=Depends(get_database_pool)):
    # ack first
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO inbound_webhooks (channel, payload, received_at) VALUES ($1, $2, NOW())",
            "whatsapp", json.dumps(payload)
        )
    # Process async via worker (read inbound_webhooks, process, mark consumed)
    return {"status": "ok"}  # < 200ms guaranteed
```

New table:

```sql
CREATE TABLE inbound_webhooks (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL,
    error_message TEXT NULL
);
CREATE INDEX inbound_webhooks_pending ON inbound_webhooks (channel, received_at)
    WHERE processed_at IS NULL;
```

Background worker: read pending, process, mark consumed.

**Step B: Twitter CRC restoration**

File: `apps/backend-rag/backend/channels/twitter/webhook_router.py`

```python
# Restore CRC handshake per Twitter spec
import hmac, hashlib, base64, os

@router.get("/webhook/twitter")
async def twitter_crc(crc_token: str):
    # Twitter sends GET with crc_token query param
    secret = os.getenv("TWITTER_CONSUMER_SECRET").encode()
    signature = hmac.new(secret, crc_token.encode(), hashlib.sha256).digest()
    return {"response_token": "sha256=" + base64.b64encode(signature).decode()}
```

Re-register webhook with Twitter API after deploy.

### Verifica post-fix

```bash
# Test: 100 concurrent webhook hits
ab -n 100 -c 10 -p whatsapp_payload.json -T application/json \
   http://localhost:8001/webhook/whatsapp
# Expected: 100/100 200 OK, all under 200ms

# Twitter CRC test
TOKEN=$(openssl rand -hex 16)
curl -sI "http://localhost:8001/webhook/twitter?crc_token=$TOKEN"
# Expected: 200 with response_token signed
```

### Owner & deadline

**Auto-implementable L2:** ✓ Yes for Step A (mechanical pattern). Step B requires verifying TWITTER_CONSUMER_SECRET in Fly secrets and re-registering webhook on Twitter dashboard — credential check needed.
**Estimated effort:** 2-3 days.

---

## P0-7 — Duplicate SQL v2 migration numbers (`129_*` and `130_*` collide)

**Severity:** P0 · **Confidence:** High · **Convergence:** Codex empirical
**Cell/Genoma touchpoint:** no (CI/build-time)

### Failure mode

Per Codex empirical scan, `apps/backend-rag/backend/db/migrations_v2/` has TWO migrations sharing number `129` and TWO sharing `130`. The runner (`migration_manager.py`) tracks via `migration_number` in `_schema_versions` table — duplicates cause undefined apply order and silent corruption risk.

### Blast radius

Schema state may diverge from expected. Specific blast depends on what each duplicate does. Worst case: one duplicate marked applied, the other never applied → schema inconsistent.

### Stato attuale

- **Detection:** None. Squawk lints SQL syntax but not numbering uniqueness.
- **Recovery:** Manual.

### Fix proposto

**Step A: Identify duplicates**

```bash
ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort | uniq -c | awk '$1>1{print $2}'
# Expected output: 129, 130
ls apps/backend-rag/backend/db/migrations_v2/ | grep -E "^(129|130)_"
```

**Step B: Audit `_schema_versions`**

```bash
fly ssh console -a nuzantara-rag -C "psql ... -c \"SELECT migration_number, applied_at FROM _schema_versions WHERE migration_number IN (129, 130) ORDER BY migration_number, applied_at\""
```

**Step C: Rename non-applied duplicate to next-available number**

For each duplicate pair, the file with NO entry in `_schema_versions` gets renamed to next available (`141_*` or higher). The applied one stays.

**Step D: Add CI check**

```yaml
# .github/workflows/lint-migration-numbers.yml
- run: |
    DUPS=$(ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort | uniq -d)
    if [ -n "$DUPS" ]; then
      echo "::error::Duplicate migration numbers: $DUPS"
      exit 1
    fi
```

### Verifica post-fix

```bash
ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort | uniq -c | awk '$1>1'
# Expected: empty
```

### Owner & deadline

**Auto-implementable L2:** Partial. Step A+B mechanical. Step C requires verification of which duplicate is which (need PG query against prod). Step D auto.
**Estimated effort:** 2-4 hours (depends on what the duplicates do).

---

## P1-7 — NLM pipelines DLQ stuck (54 entries, 7 terminal)

**Severity:** P1 · **Confidence:** High · **Convergence:** Opus, NB-1, Codex (empirical)
**Cell/Genoma touchpoint:** yes (genome scar `nlm_pipeline_silent_failures`)

### Failure mode

NB-1, NB-6, NB-7, NB-8, weekly_report jobs in persistent escalation state. Memory `discovery_2026_04_24` documents 8/9 NB pipelines exit in 3-5ms (openclaw dispatcher bug) and `claim_extractor.py:216` blocks NB-2 on CB_NLM=OPEN.

### Blast radius

Daily NLM ground-truth refresh stops. Bali Zero clients receive stale answers. CRM team workflows depending on NB-10 stop.

### Stato attuale

- **Detection:** `dlq_autopilot_escalation` writes to escalations.jsonl. File has 7404 lines pending — no consumer.
- **Recovery:** None.

### Fix proposto

File: `~/scripts/system_doctor.py` extension

```python
def check_nlm_pipelines_stuck(state_dir: Path = Path.home() / ".agent/decisions/state") -> list[dict]:
    """Detect NLM pipelines stuck >24h and attempt rerun."""
    nlm_pipelines = ["nlm_nb1_daily_refresh", "nlm_nb6_ops_compliance", "nlm_nb7_editorial",
                     "nlm_nb8_expat_life", "weekly_report"]
    stuck = []
    for pipeline in nlm_pipelines:
        state_file = state_dir / f"{pipeline}.json"
        if not state_file.exists():
            continue
        state = json.loads(state_file.read_text())
        last_success = state.get("last_success_ts", 0)
        age_hours = (time.time() - last_success) / 3600
        if age_hours > 24:
            # Attempt rerun
            result = subprocess.run(
                ["python", "-m", f"apps.evaluator.nlm_deep_research.{pipeline}", "--retry"],
                timeout=300, capture_output=True
            )
            stuck.append({
                "pipeline": pipeline,
                "age_hours": age_hours,
                "rerun_status": result.returncode,
                "rerun_stderr": result.stderr.decode()[:500]
            })
    return stuck
```

Telegram alert if rerun fails after 1 attempt.

### Verifica post-fix

```bash
# Plant a stuck pipeline
echo '{"last_success_ts": 0}' > ~/.agent/decisions/state/nlm_nb1_daily_refresh.json
python ~/scripts/system_doctor.py --notify-telegram --check-nlm
# Expected: detection + rerun attempt + Telegram if rerun fails
```

### Owner & deadline

**Auto-implementable L2:** ✓ Yes. Single Python file extension. Existing system_doctor.py infra reused.
**Estimated effort:** 4 hours.

---

## P1-8 — escalations.jsonl unbounded growth (7404 lines)

**Severity:** P1 · **Confidence:** High · **Convergence:** Codex (empirical)
**Cell/Genoma touchpoint:** no (infrastructure plumbing)

### Failure mode

`shared/escalations_pro.jsonl` and `shared/escalations_air.jsonl` are append-only since inception. No retention. No deduplication. No reader consumes.

### Blast radius

Disk grows slowly. Performance walls when any tool tries to parse. Sentinel ignores.

### Stato attuale

- **Detection:** None.
- **Recovery:** None.

### Fix proposto

**Step A: Migrate to SQLite tables**

```python
# scripts/migrate_escalations_to_sqlite.py
import sqlite3, json
from pathlib import Path

DB = Path.home() / ".agent/decisions/escalations.sqlite"
JSONL = Path("/Users/nuzantara/Desktop/nuzantara/shared/escalations_pro.jsonl")

con = sqlite3.connect(DB)
con.execute("""
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id TEXT,
    job TEXT,
    type TEXT,
    severity TEXT,
    machine TEXT,
    created_at INTEGER,
    resolved_at INTEGER NULL,
    resolved_by TEXT NULL,
    raw_json TEXT,
    UNIQUE(audit_id, machine)
)
""")
con.execute("CREATE INDEX IF NOT EXISTS idx_active ON escalations (resolved_at) WHERE resolved_at IS NULL")
con.execute("CREATE INDEX IF NOT EXISTS idx_job_created ON escalations (job, created_at)")

with open(JSONL) as f:
    for line in f:
        try:
            row = json.loads(line)
            con.execute("INSERT OR IGNORE INTO escalations (audit_id, job, type, severity, machine, created_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row.get("audit_id"), row.get("job"), row.get("type"), row.get("severity"), row.get("machine"), row.get("ts", 0), line.strip()))
        except: pass
con.commit()
```

**Step B: Pruning cron**

LaunchAgent `com.nuzantara.escalations-prune.plist`, daily 03:00:

```python
# Mark escalations as resolved if their job's circuit_breaker is CLOSED for >24h
# Delete resolved older than 30 days
# Archive non-resolved older than 90 days
```

**Step C: Update writers**

All current `dlq_autopilot.py` and similar writers should `INSERT OR REPLACE INTO escalations` rather than append to jsonl.

### Verifica post-fix

```bash
sqlite3 ~/.agent/decisions/escalations.sqlite "SELECT COUNT(*) FROM escalations WHERE resolved_at IS NULL"
# Expected: <100 active (vs current 7404 file lines)
```

### Owner & deadline

**Auto-implementable L2:** ✓ Yes.
**Estimated effort:** 1 day (migration + cron + writer updates).

---

## P1-9 — nuzantara-mcp 115-tool monolite blast radius

**Severity:** P1 · **Confidence:** Medium · **Convergence:** NB-1, Opus
**Cell/Genoma touchpoint:** no

### Failure mode

Single FastMCP process serving 115 tools. Crash = 115 tools offline simultaneously.

### Blast radius

Claude Code, Cowork, OpenClaw all lose 115 tools. Federation launcher restarts (good) but window of 30s+ tool-blackout.

### Stato attuale

- **Detection:** Federation launcher heartbeat 30s.
- **Recovery:** Auto-restart after 3x miss.

### Fix proposto

Partition into 3 specialized FastMCP processes:
- `nuzantara-mcp-crm` (CRM, clients, conversations, ~50 tools)
- `nuzantara-mcp-ingestion` (Drive, OCR, ingestion, ~30 tools)
- `nuzantara-mcp-intel` (Mata Garuda, OSINT, ~35 tools)

Each registered separately in claude_code config. Crash isolation per namespace.

### Verifica post-fix

Kill `nuzantara-mcp-crm` → verify Intel + Ingestion tools still respond.

### Owner & deadline

**Auto-implementable L2:** Partial. Architectural change touching FastMCP server file split + claude_code config + cowork integration. Best as L2-with-Zero-handoff.
**Estimated effort:** 2-3 days.

---

## P1-10 — Frontend i18n provider per route group lint

**Severity:** P1 · **Confidence:** High · **Convergence:** Opus, Gemini
**Cell/Genoma touchpoint:** no (frontend-specific)

### Failure mode

Adding `useTranslation()` to component without ancestor `<I18nProvider>` → throw → unmount → white screen. PR #273 was the manifest.

### Blast radius

White screen for users on affected route group until manual fix.

### Stato attuale

- **Detection:** None preemptive. Production users hit it.
- **Recovery:** Manual fix + redeploy.

### Fix proposto

File: `scripts/lint_i18n_providers.sh` + GH Action workflow

```bash
#!/usr/bin/env bash
# For each route group, check if descendants use useTranslation
for group_dir in apps/mouth/src/app/\(*\)/; do
    layout="$group_dir/layout.tsx"
    [ -f "$layout" ] || continue
    has_provider=$(grep -l "I18nProvider" "$layout" || true)
    descendants_use=$(rg -l "useTranslation\(\)" "$group_dir" || true)
    if [ -n "$descendants_use" ] && [ -z "$has_provider" ]; then
        echo "::error::Route group $group_dir uses useTranslation but layout lacks <I18nProvider>"
        echo "  Files: $descendants_use"
        exit 1
    fi
done
```

### Verifica post-fix

Plant a `useTranslation()` in `(workspace)/some-component.tsx` without `<I18nProvider>` in `(workspace)/layout.tsx`. CI fails before deploy.

### Owner & deadline

**Auto-implementable L2:** ✓ Yes.
**Estimated effort:** 4 hours.

---

## P1-11 — Drive polling Air OAuth 90gg monitoring

**Severity:** P1 · **Confidence:** High · **Convergence:** Opus, Gemini, NB-1 (cited cell_core.genome stressor pattern)
**Cell/Genoma touchpoint:** yes (Cell sensor for `oauth_expiry_pressure`)

### Failure mode

Drive token expires every ~90 days. `drive_token_watchdog.py` alerts 7 days before. But: Drive-poll cron Pro DISABLED since 2026-04-29 due to broken-pipe (memory `unresolved_2026_04_29`), watchdog also degraded.

### Blast radius

Drive ingestion stops. CRM document processing freezes.

### Stato attuale

- **Detection:** Watchdog 7-day warning IF cron runs.
- **Recovery:** Manual re-auth at kita settings.

### Fix proposto

**Step A: Restore drive-poll cron Pro after fixing broken-pipe** (separate task — not autonomous).

**Step B: Watchdog escalation tiers**

```python
# scripts/drive_token_watchdog.py
def check_token_expiry():
    days_until_expiry = compute_days()
    if days_until_expiry <= 1:
        send_telegram_urgent("Drive OAuth expires in 1 day! Reauth NOW.")
    elif days_until_expiry <= 7:
        send_telegram_warning(f"Drive OAuth expires in {days_until_expiry} days.")
    elif days_until_expiry <= 14:
        send_telegram_info(f"Drive OAuth: {days_until_expiry} days left.")
    elif days_until_expiry <= 30:
        send_telegram_info(f"Drive OAuth heads-up: {days_until_expiry} days.")
```

**Step C: Cell sensor**

Add to Cell PulseLoop `Sensor`:
```python
# packages/cell-core/cell_core/sensors/oauth_health.py
class OAuthExpirySensor(Sensor):
    def sense(self) -> SensorResult:
        days = check_oauth_expiry()
        status = "green" if days > 14 else ("yellow" if days > 7 else "red")
        return SensorResult(name="oauth_drive", status=status, value=days, unit="days_until_expiry")
```

### Verifica post-fix

Mock token expiry at 1, 7, 14, 30 days; verify each Telegram tier fires. Verify Cell sensor reports correct state.

### Owner & deadline

**Auto-implementable L2:** ✓ Yes for Step B+C.
**Estimated effort:** 4 hours.

---

## P2-12..P2-15 — Lower urgency

Brief summary (full detail above in Opus analysis):

- **P2-12: KG subgraph BFS timeout** — fallback to vector exists. Confidence threshold + early termination at 2nd hop. L2 yes. ~1 day.
- **P2-13: nuzantara-qdrant Fly suspended zombie** — decide: re-enable or destroy. Document migration to Qdrant Cloud. L2 yes. 1 hour.
- **P2-14: Vercel build env vars NEXT_PUBLIC_** — pre-commit hook warning when `vercel --prod` in monorepo CWD. L2 yes. 2 hours.
- **P2-15: Healthcheck probe coverage gaps** — synthetic probes per channel + KG end-to-end. L2 yes. 1 day.

---

## Surfaces NOT in brief but found

### NB-A. Sentinel itself recursive watchdog

`nuzantara-sentinel.py` needs its own KeepAlive plist + Air-side dead-man monitor. L2 yes.

### NB-B. Federation launcher restart

`apps/federation/launcher.py` restarts agents but who restarts launcher? L2 yes, similar pattern as NB-A.

### NB-C. system_doctor.py vs OpsIntelligence naming clash

Two daemons, different roles, similar names confuse audits. Documentation fix in INDEX.md + AUTONOMOUS_OPS.md.

### NB-D. Vercel monorepo cross-import not lint-checked

If satellite app imports broken workspace package, monorepo deploy breaks. Pre-deploy gate addition. L2 yes. ~6 hours.

### NB-E. Brevo email SPOF

Single API key, no fallback. Add Resend or SES fallback. L2 yes, with Zero handoff for second-provider account creation. ~1 day.

### NB-F. Tigris backup never restore-tested

Monthly restore-into-staging-PG drill. L2 yes. ~1 day for cron + alert wiring.

### NB-G. Tailscale OFF during AI work single-link risk

Heartbeat schedule. L2 yes. ~2 hours.

---

## Implementation order recommendation

Given autonomy L2 + Antonello not reviewing code, I recommend the following order, optimizing for risk reduction per hour invested:

**Week 1 (highest impact P0 — start TODAY):**
1. **P0-0 (/health + Cell pulse classify, 1-2h)** — implement BEFORE all others. Without it, every other fix is masked by silent green health.
2. P0-7 (migration duplicates, 2-4h) — schema integrity, blocks new migrations safely
3. P0-4 (deploy ordering bug, 30min) — quickest, eliminates a chronic recurring pain
4. P0-1 (SearchService degraded mode, 1h) — eliminates the most common restart loop
5. P0-3 (LaunchAgents audit, 3h) — makes ALL local daemons resilient
6. P0-6 (channels ack-first, 2-3 days) — protects client-facing messages

**Week 2 (foundational):**
5. P0-2 (EventBus Outbox, 1-3 days) — fixes Symbiosis Law 4 docs-vs-code drift
6. P0-5 (httpx + dependencies.py, 1-2 days) — eliminates resource leak class

**Week 3 (P1 cleanup):**
7. P1-7 (NLM auto-recovery, 4h)
8. P1-8 (escalations SQLite, 1 day)
9. P1-10 (i18n lint, 4h)
10. P1-11 (OAuth tiers, 4h)

**Week 4+ (P1 architectural + P2):**
11. P1-9 (MCP partition) — Zero handoff first
12. P2-12..15 + NB-A..G (cleanup wave)

**Total estimated effort:** ~20-30 working days. Spread over 4-6 weeks at autonomy L2.
