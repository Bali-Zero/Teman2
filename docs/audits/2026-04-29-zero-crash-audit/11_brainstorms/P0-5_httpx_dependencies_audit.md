# P0-5 Brainstorm — httpx async client + dependencies.py audit

**Goal:** Eliminate Golden Rule #10 violations and convert dependencies.py fail-fast to log-and-degrade pattern.
**Effort:** 1-2 days
**Dependencies:** P0-0 (visibility), P0-1 (degraded pattern reference)

---

## Strategy options

### Option A: Mass automated rewrite + CI grep-test

Audit + rewrite each `httpx.AsyncClient(` instantiation outside `_http.py` files to lazy-singleton pattern. Add CI grep-test as guardrail.

**Pros:**
- Comprehensive — eliminates the class of bug
- Self-policing via CI test
- Reference pattern already exists (`email_http.py`)

**Cons:**
- Volume: ~50-200 callsites estimated. Each needs careful conversion to ensure `aclose()` registered in lifespan
- Some callsites are in 3rd-party patterns (e.g., `with httpx.AsyncClient() as c:` is OK and shouldn't be flagged)

**Effort:** 1-2 days for full audit + tests.

### Option B: Add lifespan-managed pool, refactor incrementally

Single global `httpx.AsyncClient` pool, all services Depends() on `get_http_client()`. Refactor highest-traffic services first.

**Pros:**
- Single pool minimizes connection overhead
- Faster to ship initial benefit
- Less mechanical, more architectural

**Cons:**
- Requires per-service decision on shared pool vs dedicated
- Doesn't immediately fix all leaks

**Effort:** 1 week for incremental refactor.

### Option C: Use httpx Connection Pool with shared limits

Keep current pattern but configure pool limits explicitly to prevent unbounded FD growth.

**Pros:**
- Minimal code change
- Bounds the leak to `max_connections`

**Cons:**
- Doesn't fix the root cause (still creates clients in loops)
- Just bounds the damage

**Effort:** 2 hours.

**Recommendation:** **Option A**. The leak is a class of bug that needs eliminating. Option C is bandaid; Option B is high-effort refactor. Option A is the right balance.

---

## Implementation plan (Option A)

### Step 1: Audit (find all violators)

```bash
# All instantiations
rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend > /tmp/httpx_all.txt
wc -l /tmp/httpx_all.txt
# Expected: ~50-200

# Filter to violators (not in _http.py and not in `with` block)
rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend \
  | grep -v "_http\.py" \
  | grep -v "async with" \
  | grep -v "context manager" > /tmp/httpx_violations.txt
wc -l /tmp/httpx_violations.txt
```

### Step 2: Reference pattern from `email_http.py`

```python
# apps/backend-rag/backend/services/notifications/email_http.py
"""Shared persistent httpx.AsyncClient for outbound email delivery.

CLAUDE.md Golden Rule #10 forbids httpx.AsyncClient() instantiation in method bodies and loops —
a persistent client avoids TCP handshake and TLS resume cost on every call.
Pattern: lazy-singleton global, re-created if closed. close_email_client is registered in
the FastAPI lifespan shutdown hook (app_factory.lifespan) so connections are released cleanly.
"""

_email_client: httpx.AsyncClient | None = None

def get_email_client() -> httpx.AsyncClient:
    global _email_client
    if _email_client is None or _email_client.is_closed:
        _email_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
        )
    return _email_client

async def close_email_client() -> None:
    global _email_client
    if _email_client and not _email_client.is_closed:
        await _email_client.aclose()
        _email_client = None
```

### Step 3: Per-violator conversion

For each violator, identify:
- Module-scope instantiation (rare) → keep as singleton
- Function-body instantiation (common) → convert to lazy-singleton in module
- Loop-body instantiation (worst) → URGENT, lazy-singleton

Example:

```python
# BEFORE (violator)
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
    return resp.json()
```

```python
# AFTER (fixed)
_data_client: httpx.AsyncClient | None = None

def _get_data_client() -> httpx.AsyncClient:
    global _data_client
    if _data_client is None or _data_client.is_closed:
        _data_client = httpx.AsyncClient(timeout=30)
    return _data_client

async def close_data_client():
    global _data_client
    if _data_client:
        await _data_client.aclose()
        _data_client = None

async def fetch_data(url: str) -> dict:
    resp = await _get_data_client().get(url)
    return resp.json()
```

Register `close_data_client` in `app_factory.lifespan()` shutdown.

### Step 4: dependencies.py log-and-degrade

```python
# apps/backend-rag/backend/app/dependencies.py

def get_search_service(request: Request) -> SearchService:
    svc = getattr(request.app.state, 'search_service', None)
    if svc is None:
        # Was: raise HTTPException(503, "service unavailable")
        # Now: structured response with degraded set
        raise HTTPException(
            status_code=503,
            detail={
                "error": "search_unavailable",
                "retry_after_seconds": 60,
                "degraded_services": list(getattr(request.app.state, 'degraded_services', set())),
                "fallback": "Try /api/query again in 60 seconds"
            }
        )
    return svc

# Same pattern for get_ai_client, get_kg_agent, etc.
```

### Step 5: CI guardrail

```yaml
# .github/workflows/lint-golden-rule-10.yml
name: Golden Rule #10 — httpx pattern lint
on: [pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect violations
        run: |
          # Find AsyncClient instantiations outside *_http.py
          VIOLATIONS=$(rg --type py "httpx\.AsyncClient\(" apps/backend-rag/backend \
            | grep -v "_http\.py" \
            | grep -v "async with httpx" \
            | grep -v "# golden-rule-10-exempt" \
            || true)

          if [ -n "$VIOLATIONS" ]; then
            echo "::error::Golden Rule #10 violations:"
            echo "$VIOLATIONS"
            echo ""
            echo "Solution: convert to lazy-singleton pattern (see services/notifications/email_http.py)"
            echo "Or add # golden-rule-10-exempt: <reason> on offending line"
            exit 1
          fi
```

### Step 6: ResourceSensor for Cell

```python
# packages/cell-core/cell_core/sensors/resource.py
import os, psutil
from .base import Sensor, SensorResult

class ResourceSensor(Sensor):
    name = "backend_resources"

    def sense(self) -> SensorResult:
        proc = psutil.Process(os.getpid())
        try:
            fd_count = proc.num_fds()  # Linux/Darwin
        except (AttributeError, psutil.AccessDenied):
            fd_count = -1

        memory_mb = proc.memory_info().rss / (1024 * 1024)

        # Classify
        if fd_count > 1000 or memory_mb > 1500:
            status = "red"
        elif fd_count > 500 or memory_mb > 1000:
            status = "yellow"
        else:
            status = "green"

        return SensorResult(
            name=self.name,
            status=status,
            value={"fd_count": fd_count, "memory_mb": memory_mb}
        )
```

---

## Dependencies

- **Before:** P0-0 (degraded state visible), P0-1 (degraded pattern reference)
- **After:** httpx leaks eliminated → reduces P0-1 frequency

## Rollback plan

Per-file rollback via git revert. CI guardrail can be disabled via `GOLDEN_RULE_10_BYPASS=1` env in workflow if needed.

## L2 autonomy decision

**Auto-implementable: PARTIAL.**

- Step 1 (audit) and Step 5 (CI guardrail): YES
- Step 2-4 (per-violator conversion): YES but mechanical — review each diff
- Step 6 (sensor): YES

Per-violator conversion is mechanical but ~50-200 callsites → split into batches.

## Verification

```bash
# 1. Local: count FDs before and after load
PID=$(pgrep -f "uvicorn.*main_api" | head -1)
LSOF_BEFORE=$(lsof -p $PID 2>/dev/null | wc -l)
ab -n 10000 -c 50 http://localhost:8001/api/query
LSOF_AFTER=$(lsof -p $PID 2>/dev/null | wc -l)
echo "FDs before: $LSOF_BEFORE, after: $LSOF_AFTER"
# Expected: < 5% growth (was: monotonic climb)

# 2. CI guardrail
echo "import httpx; httpx.AsyncClient()" >> apps/backend-rag/backend/services/test_violation.py
git add . && git commit -m "test: GR10 violation" && git push
gh pr create
gh pr checks
# Expected: lint-golden-rule-10 fails

# 3. Cell sensor
python -c "
from cell_core.sensors.resource import ResourceSensor
s = ResourceSensor()
print(s.sense())
"
# Expected: SensorResult(name='backend_resources', status='green', value={'fd_count': X, 'memory_mb': Y})
```

Numbers:
- Before: monotonic FD climb under load → eventual exhaustion → crash → restart loop
- After: stable FD plateau under load (httpx connection pool reuses)
- Before: dependencies.py raise HTTPException = thin error
- After: structured 503 with retry_after_seconds + degraded set
