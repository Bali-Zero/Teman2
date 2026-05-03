# P0-1 Brainstorm — SearchService fail-fast → degraded mode

**Goal:** Convert SearchService critical-init failure from RuntimeError-raising fail-fast to log-and-degrade pattern. Allow uvicorn to bind 8080 even when SearchService can't init.
**Effort:** 1h
**Dependencies:** P0-0 (visibility) — without P0-0, the degraded state isn't visible to monitoring.

---

## Strategy options

### Option A: Wrap `_init_critical_services` calls in try/except per service

**Pros:**
- Fine-grained: SearchService can fail without crashing ZantaraAIClient init
- Each service has its own degraded flag in `app.state.degraded_services` set
- Mirrors existing pattern for non-critical services

**Cons:**
- Repetitive boilerplate per service
- Easy to forget one service in the wrap

**Effort:** 30 min.

### Option B: Decorator pattern

```python
def degraded_safe(service_name: str):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(app: FastAPI):
            try:
                return await fn(app)
            except Exception as e:
                logger.exception(f"{service_name} init failed; degraded")
                app.state.degraded_services = (app.state.__dict__.get('degraded_services') or set()) | {service_name}
                return None
        return wrapper
    return decorator

@degraded_safe("search")
async def _init_search_service(app): ...
```

**Pros:**
- DRY — one decorator covers all services
- Self-documenting
- Easy to extend: add `@degraded_safe` to new service inits

**Cons:**
- Slightly more abstraction (decorator)
- Can hide errors in tests if not careful (override decorator in test mode)

**Effort:** 45 min.

### Option C: Service registry refactor — initialize services lazily

**Pros:**
- Most architecturally clean
- Services init on first use, not at startup
- No degraded state — request-time fallback

**Cons:**
- Major refactor: changes service contract
- Breaks 100+ Depends() callsites
- High risk for an audit fix

**Effort:** 5+ days.

**Recommendation:** **Option B** — decorator pattern. Best DRY/correctness tradeoff. Reviewable in ~50 lines of diff.

---

## Implementation plan (Option B)

### File 1: `apps/backend-rag/backend/app/setup/service_initializer.py`

Add at top:

```python
import functools

def degraded_safe(service_name: str):
    """Decorator: catches init failure and registers as degraded.

    Use for services that can run in degraded mode. The app keeps booting,
    binds 8080, and /health surfaces the degraded set.

    Note: P0-0 fix in /health endpoint required for degraded state to be visible
    to monitoring.
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(app: FastAPI, *args, **kwargs):
            try:
                return await fn(app, *args, **kwargs)
            except Exception as e:
                logger.exception(f"Critical service '{service_name}' init failed; entering degraded mode")
                if not hasattr(app.state, 'degraded_services'):
                    app.state.degraded_services = set()
                app.state.degraded_services.add(service_name)
                # Genome scar (Symbiosis Pillar 2)
                _record_genome_scar(service_name, e)
                return None
        return wrapper
    return decorator


def _record_genome_scar(service_name: str, exc: Exception) -> None:
    """Record scar in genome KB for accumulated learning."""
    try:
        from backend.services.genome.client import get_genome_client
        get_genome_client().record_scar(
            cell="apps/backend-rag",
            scar_id=f"{service_name}_init_failure_{type(exc).__name__}",
            procedure=f"_init_critical_services raised {type(exc).__name__}",
            rationale=str(exc)[:500]
        )
    except Exception:
        pass  # genome unavailable shouldn't break startup
```

Apply decorator to existing service inits:

```python
@degraded_safe("search")
async def _init_search_service(app: FastAPI):
    # ... existing logic
    return search_service

@degraded_safe("ai_client")
async def _init_ai_client(app: FastAPI):
    # ... existing logic
    return ai_client
```

Modify `_init_critical_services` to NOT raise:

```python
async def _init_critical_services(app: FastAPI) -> tuple[Any, Any]:
    # Was: raises RuntimeError on failure
    # Now: each component may return None; degraded state recorded
    search_service = await _init_search_service(app)
    ai_client = await _init_ai_client(app)
    # No raise. App keeps booting.
    return search_service, ai_client
```

### File 2: `apps/backend-rag/backend/app/dependencies.py`

Modify `get_search_service`:

```python
def get_search_service(request: Request) -> SearchService:
    svc = getattr(request.app.state, 'search_service', None)
    if svc is None:
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

Same pattern for `get_ai_client`.

### File 3: tests

```python
# backend/tests/app/setup/test_degraded_safe.py

@pytest.mark.asyncio
async def test_degraded_safe_catches_runtime_error(monkeypatch, app_fixture):
    app = app_fixture
    monkeypatch.setattr("backend.services.search._init", lambda: (_ for _ in ()).throw(RuntimeError("test")))
    await _init_critical_services(app)
    assert "search" in app.state.degraded_services
    assert app.state.search_service is None  # default
```

---

## Dependencies

- **Requires P0-0** for the degraded state to be visible at /health.

## Rollback plan

`git revert` reverses 1 file change + tests. SearchService failure reverts to RuntimeError + Fly restart loop.

## L2 autonomy decision

**Auto-implementable: YES.**

## Verification

```bash
# Inject SearchService failure
SEARCH_FORCE_FAIL=1 PYTHONPATH=. uvicorn backend.app.main_api:app --port 8001 &
sleep 5
curl -s http://localhost:8001/health | jq '.degraded_services'
# Expected: ["search"]
curl -s http://localhost:8001/api/query -d '{"q":"test"}' -H "X-API-Key: $K"
# Expected: 503 with structured error
```
