# P0-0 Brainstorm — `/health` masks `startup_failed=True`

**Goal:** Make `/health` return 503 when backend startup failed, AND make Cell pulse classify body status semantically.
**Effort:** 1-2h
**Dependencies:** None — foundational fix that unblocks all others' visibility.

---

## Strategy options

### Option A: Minimal — call `_check_startup_failed()` at top of `health_check()`

**Pros:**
- Single file change (`backend/app/routers/health.py`)
- Backward-compatible (existing healthy boots return same 200 + body)
- Reversible via git revert
- Existing helper function already present, just unused

**Cons:**
- Doesn't address Cell pulse blind spot (need second change)
- Doesn't add warmup deadline (initializing forever still 200)

**Effort:** 30 min for the change + 30 min for tests.

### Option B: Comprehensive — Option A + warmup deadline + Cell sensor classification

**Pros:**
- Fixes all three layers: backend health, Cell pulse, warmup timeout
- Aligns with Codex finding ("3 surface" approach)
- Permanent fix — no follow-up needed

**Cons:**
- 3 files touched: `health.py`, `app_factory.py`, `pulse.py`
- Slightly higher test surface

**Effort:** 1-2h for changes + tests.

### Option C: Refactor — separate `/health` endpoint into `/livez` and `/readyz` (k8s-style)

**Pros:**
- Industry-standard pattern (Kubernetes liveness vs readiness probes)
- `/livez` = process alive (always 200 if uvicorn bound)
- `/readyz` = ready to serve (503 if startup_failed, dependencies down, etc.)
- Future-proof if we move to k8s

**Cons:**
- Breaking change for current health monitoring (Fly health check, GH Actions, healthcheck@balizero.com)
- Requires updating fly.toml (off-limits!), `cron-fly-restart-detector.yml`, healthcheck script
- Higher coordination cost

**Effort:** 1 day including all consumers updated.

**Recommendation:** **Option B**. Comprehensive enough to be permanent, scoped enough to be L2-autonomous. Option C is a future architectural improvement (L3, Zero handoff).

---

## Implementation plan (Option B)

### File 1: `apps/backend-rag/backend/app/routers/health.py`

**Current state (lines 147-266):** `health_check()` returns based on process group (light/api/rag) + DB ping. Never checks `app.state.startup_failed`.

**Change:**

```python
async def health_check(request: Request, response: Response) -> HealthResponse:
    """Health endpoint with startup_failed propagation."""

    # P0-0: surface startup_failed as 503 (not silently 200)
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

    # P0-0b: warmup deadline (180s) — after that, "initializing" becomes 503
    started_at = getattr(request.app.state, "startup_started_at", None)
    if started_at and (time.time() - started_at) > 180:
        if getattr(request.app.state, "startup_complete", False) is False:
            response.status_code = 503
            return HealthResponse(
                status="unhealthy",
                message=f"startup_timeout: started {int(time.time() - started_at)}s ago",
                ...
            )

    # Continue with existing logic
    ...
```

### File 2: `apps/backend-rag/backend/app/setup/app_factory.py`

**Current state (lines 114-118):** sets `app.state.startup_failed=True` on RuntimeError but doesn't track timing.

**Change:**

```python
async def lifespan(app: FastAPI) -> AsyncGenerator:
    app.state.startup_started_at = time.time()
    app.state.startup_failed = None
    app.state.startup_complete = False

    try:
        await initialize_services(app)
        app.state.startup_complete = True
    except Exception as e:
        logger.exception("Startup failed")
        app.state.startup_failed = e
        # Do NOT raise — let uvicorn keep serving /health (which will now 503)

    yield

    # shutdown
    await close_services(app)
```

**Note:** Removing `raise` means uvicorn no longer crashes on init failure. The /health 503 + Fly auto-restart handles recovery. This is the GRACEFUL DEGRADATION pattern (Symbiosis Law 4).

### File 3: `apps/cell/cell/core/pulse.py`

**Current state:** classify green based on `reading.reachable and reading.status_code == 200`.

**Change:**

```python
def classify_health(reading: HealthReading) -> str:
    """Classify health reading. Examines BODY status, not just HTTP code."""
    if not reading.reachable:
        return "red"
    if reading.status_code >= 500:
        return "red"
    if reading.status_code != 200:
        return "yellow"  # 3xx/4xx might be intermediate

    # Examine body if structured
    body = reading.body if isinstance(reading.body, dict) else {}
    body_status = body.get("status", "").lower()

    if body_status in ("unhealthy", "startup_failed", "failed", "down"):
        return "red"
    if body_status in ("degraded", "initializing", "warming"):
        return "yellow"
    if body_status in ("healthy", "ok", "ready"):
        return "green"

    # No body status — fall back to HTTP-only (existing behavior)
    return "green"
```

### File 4: `apps/backend-rag/backend/tests/app/routers/test_health_startup_failed.py` (NEW)

```python
"""Verify /health returns 503 when startup_failed."""
from fastapi.testclient import TestClient

def test_health_503_on_startup_failed(monkeypatch):
    from backend.app.app_factory import create_app
    app = create_app()
    app.state.startup_failed = RuntimeError("Test failure")
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    assert "startup_failed" in response.json()["message"]

def test_health_503_on_warmup_timeout(monkeypatch):
    import time
    app = create_app()
    app.state.startup_started_at = time.time() - 200  # 200s ago > 180s deadline
    app.state.startup_complete = False
    app.state.startup_failed = None
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    assert "startup_timeout" in response.json()["message"]

def test_health_200_on_normal_startup(monkeypatch):
    app = create_app()
    app.state.startup_complete = True
    app.state.startup_failed = None
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
```

### File 5: `apps/cell/cell/tests/test_pulse_classify.py` (NEW)

```python
def test_pulse_classifies_red_on_startup_failed_body():
    reading = HealthReading(reachable=True, status_code=200, body={"status": "startup_failed"})
    assert classify_health(reading) == "red"

def test_pulse_classifies_yellow_on_initializing_body():
    reading = HealthReading(reachable=True, status_code=200, body={"status": "initializing"})
    assert classify_health(reading) == "yellow"

def test_pulse_classifies_green_on_healthy_body():
    reading = HealthReading(reachable=True, status_code=200, body={"status": "healthy"})
    assert classify_health(reading) == "green"
```

---

## Dependencies & ordering

- **Before this:** Nothing (this is foundational).
- **After this:** Every other P0 fix becomes verifiable. Without this, you can't tell if SearchService degraded mode (P0-1) actually surfaces correctly to monitoring.

---

## Rollback plan

If something breaks after deploy:

1. `git revert <commit-sha>` reverts the `health.py` + `app_factory.py` + `pulse.py` changes
2. Squawk migration lint won't trigger (no SQL)
3. Tests revert with the same commit
4. Old behavior (silent 200 on startup_failed) restores within next deploy cycle (~10 min)

**Risk:** None significant. Worst case: existing /health consumers (15min healthcheck probe, GH Actions cron) start seeing 503 for legitimate startup transitions during deploy roll-out. Mitigation: warmup deadline 180s gives enough buffer for normal RAG warmup.

---

## L2 autonomy decision

**Auto-implementable: YES.**

Reasoning:
- All files in scope are NOT off-limits (zantara_core.py, fly.toml, .env.production excluded)
- Changes are additive (no deletion of existing behavior except removing an unused branch)
- Tests are added (new TDD)
- Reversible
- No external service contract change (Fly health check still hits /health, just gets correct status now)

**No Zero handoff required.** Proceed L2 autonomously after audit acceptance.

---

## Verification protocol

```bash
# 1. Local test
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/app/routers/test_health_startup_failed.py -v
# Expected: 3 tests pass

# 2. Cell test
cd apps/cell && source .venv/bin/activate  # if separate venv
PYTHONPATH=. pytest cell/tests/test_pulse_classify.py -v
# Expected: 3 tests pass

# 3. Local backend boot with simulated failure
cd apps/backend-rag && source .venv/bin/activate
SEARCH_FORCE_FAIL=1 PYTHONPATH=. uvicorn backend.app.main_api:app --port 8001 &
sleep 5
RESP=$(curl -sI http://localhost:8001/health | head -1)
echo "$RESP"
# Expected: HTTP/1.1 503 Service Unavailable

# 4. Fly deploy + verify
fly deploy --strategy rolling -a nuzantara-rag
sleep 60
curl -sI https://nuzantara-rag.fly.dev/health | head -1
# Expected: HTTP/1.1 200 OK (production should be healthy)
```

Numbers:
- Before: silent 200 on startup_failed = silent crash for up to 15 min until login probe catches downstream
- After: 503 on startup_failed = Fly auto-restart attempt within 30s + deploy-failure-alert Telegram

---

## Open questions for Zero

None. This is straightforward technical correction.

If questions arise during implementation:
1. Should warmup deadline be 180s (current proposal) or longer? RAG cold start can take 90-120s in some cases per memory `feedback_oauth_only_cron`. **Decision:** keep 180s as default, expose `STARTUP_DEADLINE_S` env for override.
2. Should we also add `/livez` separate from `/health`? **Decision:** defer (Option C above), L3 work.
