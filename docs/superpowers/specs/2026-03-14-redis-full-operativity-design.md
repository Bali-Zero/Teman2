# Redis Full Operativity — Design Spec

**Date:** 2026-03-14
**Status:** Approved
**Effort:** 4-5h
**Scope:** Centralize Redis client, fix 6 broken integrations, add TTL strategy, add health visibility

---

## Problem

Redis is wired into 7 backend components but only 1 (CacheService) actually produces keys. The other 6 either fail silently or never receive traffic. Each component creates its own Redis connection independently — no pooling, no shared health, no visibility.

## Solution

### 1. RedisManager Singleton

**New file:** `backend/core/redis_manager.py`

Single source of Redis connections for the entire backend.

```python
class RedisManager:
    _instance = None

    async_pool: ConnectionPool      # For CacheService, SessionService, WebSocket, Scheduler
    sync_client: Redis              # For RateLimiter (sync middleware)

    def get_async_client() -> Redis
    def get_sync_client() -> Redis
    async def health_check() -> dict
    def get_stats() -> dict
    def register_component(name: str, status: str)
```

**Connection config:**

- `socket_connect_timeout=5`
- `socket_timeout=5`
- `max_connections=10` (enough for 7 components + headroom)
- `decode_responses=True`
- `retry_on_timeout=True`

**Graceful degradation:** If Redis is unavailable at startup, all components fall back to their existing fallbacks (in-memory LRU, in-memory dict, disabled). No crash.

### 2. Component Migration

Each component stops doing `redis.from_url()` and imports from RedisManager.

| Component           | File                                                    | Change                                                               |
| ------------------- | ------------------------------------------------------- | -------------------------------------------------------------------- |
| CacheService        | `backend/core/cache.py`                                 | Replace `aioredis.from_url()` with `RedisManager.get_async_client()` |
| RateLimiter         | `backend/middleware/rate_limiter.py`                    | Replace `redis.from_url()` with `RedisManager.get_sync_client()`     |
| SessionService      | `backend/services/misc/session_service.py`              | Accept Redis client via constructor instead of URL                   |
| WebSocket           | `backend/app/routers/websocket.py`                      | Replace `redis.from_url()` with `RedisManager.get_async_client()`    |
| AutonomousScheduler | `backend/services/misc/autonomous_scheduler.py`         | Replace `aioredis.from_url()` with `RedisManager.get_async_client()` |
| FAQ Cache           | via `service_initializer.py`                            | Pass RedisManager client to CacheService                             |
| NotebookLM Cache    | `backend/services/caching/notebooklm_cache_service.py`  | Replace `redis.from_url()` with `RedisManager.get_async_client()`    |
| HealthService       | `backend/services/monitoring/unified_health_service.py` | Replace `redis.from_url()` with `RedisManager.get_sync_client()`     |

**No behavioral changes.** Same logic, same fallbacks, different connection source.

### 3. TTL Strategy

**New constant map** in `redis_manager.py`:

```python
TTL_CONFIG = {
    "hybrid_search": 3600,      # 1h — RAG responses
    "kg:entity": 21600,         # 6h — KG entities
    "kg:traverse": 21600,       # 6h — KG traversals
    "query_expand": 7200,       # 2h — query expansion
    "kbli_translate": 86400,    # 24h — KBLI translations (static)
    "kbli_inspect": 86400,      # 24h — KBLI inspections (static)
    "faq": 14400,               # 4h — FAQ cache
    "notebooklm": 14400,        # 4h — NotebookLM cache
    "session": 86400,           # 24h — conversation sessions
    "default": 1800,            # 30min — fallback
}

def get_ttl(prefix: str) -> int:
    return TTL_CONFIG.get(prefix, TTL_CONFIG["default"])
```

CacheService's `_generate_key()` already prefixes keys with `zantara:{prefix}:`. The TTL lookup extracts the prefix and applies the right TTL.

### 4. Health Dashboard

**Extend `/health` response** with Redis section:

```json
{
  "redis": {
    "connected": true,
    "latency_ms": 12,
    "keys": 19,
    "memory_used": "1.54MB",
    "cache_stats": {
      "hits": 847,
      "misses": 123,
      "hit_rate": "87.3%",
      "errors": 0
    },
    "components": {
      "cache_service": "active",
      "session_service": "active",
      "rate_limiter": "active",
      "websocket_pubsub": "active",
      "scheduler_locks": "active",
      "faq_cache": "active",
      "notebooklm_cache": "active"
    }
  }
}
```

Component status is registered during `service_initializer.py` startup. Each component calls `RedisManager.register_component(name, status)` after init.

## Files Changed

| Action   | File                                                    |
| -------- | ------------------------------------------------------- |
| **NEW**  | `backend/core/redis_manager.py`                         |
| **EDIT** | `backend/core/cache.py`                                 |
| **EDIT** | `backend/middleware/rate_limiter.py`                    |
| **EDIT** | `backend/services/misc/session_service.py`              |
| **EDIT** | `backend/app/routers/websocket.py`                      |
| **EDIT** | `backend/services/misc/autonomous_scheduler.py`         |
| **EDIT** | `backend/services/caching/notebooklm_cache_service.py`  |
| **EDIT** | `backend/services/monitoring/unified_health_service.py` |
| **EDIT** | `backend/app/setup/service_initializer.py`              |
| **EDIT** | `backend/app/routers/health.py` (or equivalent)         |

## What This Does NOT Do

- No new features or abstractions
- No refactoring beyond connection source swap
- No changes to business logic
- No new dependencies (uses existing `redis` package)
- No frontend changes

## Testing Strategy

1. **Local:** Start Redis, run backend, verify all 7 components produce keys
2. **Health endpoint:** `curl localhost:8000/health | jq '.redis'` shows all components active
3. **Fallback:** Stop Redis, restart backend, verify graceful degradation (all fallbacks work)
4. **Existing tests:** Run core test suite to verify no regressions

## Verification Commands

```bash
# After implementation, verify Redis is fully operational:
redis-cli keys '*' | wc -l                    # Should show keys from all components
redis-cli keys 'session:*' | wc -l            # Session keys present
redis-cli keys 'rate_limit:*' | wc -l         # Rate limit keys present
redis-cli keys 'zantara:*' | wc -l            # Cache keys present
curl localhost:8000/health | jq '.redis'       # All components "active"
```
