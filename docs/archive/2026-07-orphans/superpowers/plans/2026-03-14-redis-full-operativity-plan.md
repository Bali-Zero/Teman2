# Redis Full Operativity — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-03-14-redis-full-operativity-design.md`
**Date:** 2026-03-14

---

## Step 1: Create RedisManager singleton

**File:** `backend/core/redis_manager.py` (NEW)

- Singleton with async pool + sync client
- TTL_CONFIG map
- `get_async_client()`, `get_sync_client()`, `health_check()`, `get_stats()`, `register_component()`
- Graceful degradation: if REDIS_URL missing or connection fails, set `available=False`
- **Test:** Import and verify singleton behavior

## Step 2: Migrate CacheService

**File:** `backend/core/cache.py`

- Replace `redis.asyncio.from_url()` with `RedisManager.get_async_client()`
- Use `RedisManager.get_ttl(prefix)` in `set()` method
- Register component: `RedisManager.register_component("cache_service", "active")`
- **Test:** `redis-cli keys 'zantara:*'` still works

## Step 3: Migrate RateLimiter

**File:** `backend/middleware/rate_limiter.py`

- Replace `redis.from_url()` + `ping()` with `RedisManager.get_sync_client()`
- Register component
- **Test:** Make API requests, verify `rate_limit:*` keys appear

## Step 4: Migrate SessionService

**File:** `backend/services/misc/session_service.py`

- Change constructor to accept optional Redis client instead of requiring URL
- Fall back to `RedisManager.get_async_client()` if no client passed
- Register component
- **Test:** Verify session creation/retrieval works

## Step 5: Migrate WebSocket Pub/Sub

**File:** `backend/app/routers/websocket.py`

- Replace `redis.from_url()` with `RedisManager.get_async_client()`
- Register component
- **Test:** Verify `redis_listener()` starts without error in logs

## Step 6: Migrate AutonomousScheduler

**File:** `backend/services/misc/autonomous_scheduler.py`

- Replace `_get_redis()` function with `RedisManager.get_async_client()`
- Register component
- **Test:** Verify scheduler lock keys appear

## Step 7: Migrate NotebookLM Cache

**File:** `backend/services/caching/notebooklm_cache_service.py`

- Replace `redis.from_url()` with `RedisManager.get_async_client()`
- Register component
- **Test:** Verify cache operations work

## Step 8: Migrate HealthService

**File:** `backend/services/monitoring/unified_health_service.py`

- Replace `redis.from_url()` with `RedisManager.get_sync_client()`
- Register component
- **Test:** Verify health check includes Redis status

## Step 9: Wire RedisManager into startup

**File:** `backend/app/setup/service_initializer.py`

- Initialize `RedisManager` early in background init (before other services)
- Pass RedisManager client to services that need it
- **Test:** Backend starts clean, logs show all components connected

## Step 10: Add Redis to /health endpoint

**File:** Health router (find exact file)

- Add `RedisManager.get_stats()` to health response
- Include component registry, cache stats, latency, key count
- **Test:** `curl localhost:8000/health | jq '.redis'` shows full dashboard

## Step 11: Integration test

- Start Redis locally
- Run backend with `PYTHONPATH=. python -m uvicorn backend.main:app --port 8000`
- Verify: all components registered, keys from multiple prefixes exist
- Stop Redis, restart backend, verify graceful fallback
- Run core tests: `PYTHONPATH=. pytest backend/tests/services/rag/ -q`
