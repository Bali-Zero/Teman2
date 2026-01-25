# Redis Setup Guide for Article Composer

**Purpose:** Configure Redis for caching in Article Composer  
**Status:** Optional but recommended for production

---

## 🎯 OVERVIEW

Redis caching improves Article Composer performance by:

- ✅ Reducing API costs (30-50% reduction)
- ✅ Improving response times (30-50% faster)
- ✅ Reducing load on Claude API

**Note:** Article Composer works without Redis (graceful degradation), but caching is disabled.

---

## 🏠 LOCAL DEVELOPMENT

### Option 1: Docker (Recommended)

**Quick Start:**

```bash
cd apps/backend-rag
./scripts/setup_redis_local.sh
```

**Manual Docker Setup:**

```bash
# Start Redis container
docker run -d \
  --name redis-article-composer \
  -p 6379:6379 \
  redis:7-alpine

# Verify it's running
docker ps | grep redis

# Test connection
redis-cli ping
# Should return: PONG
```

**Stop Redis:**

```bash
docker stop redis-article-composer
docker rm redis-article-composer
```

### Option 2: Local Installation

**macOS:**

```bash
brew install redis
redis-server
```

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**Windows:**

- Download from: https://github.com/microsoftarchive/redis/releases
- Or use WSL with Ubuntu setup

### Option 3: Cloud Redis (Development)

**Upstash (Free Tier):**

1. Sign up at https://upstash.com
2. Create Redis database
3. Copy connection URL
4. Set `REDIS_URL` environment variable

---

## 🌐 PRODUCTION (Fly.io)

### Option 1: Fly.io Redis (Recommended)

**Create Redis Instance:**

```bash
# Create Redis app
fly redis create

# Or attach existing Redis
fly redis attach <redis-app-name>
```

**Set Redis URL:**

```bash
# Get Redis URL from Fly.io dashboard
# Or from: fly redis status

fly secrets set REDIS_URL="redis://<host>:<port>/0" -a nuzantara-rag
```

### Option 2: External Redis Service

**Upstash:**

1. Create Redis database
2. Copy connection URL
3. Set as secret:
   ```bash
   fly secrets set REDIS_URL="rediss://..." -a nuzantara-rag
   ```

**Redis Cloud:**

1. Sign up at https://redis.com/cloud
2. Create database
3. Copy connection URL
4. Set as secret

**Other Providers:**

- AWS ElastiCache
- Google Cloud Memorystore
- Azure Cache for Redis

---

## ⚙️ CONFIGURATION

### Environment Variable

**Variable:** `REDIS_URL`

**Format:**

```
redis://[username]:[password]@[host]:[port]/[database]
```

**Examples:**

```bash
# Local
REDIS_URL=redis://localhost:6379/0

# With password
REDIS_URL=redis://:password@localhost:6379/0

# Upstash
REDIS_URL=rediss://default:password@host.upstash.io:6379/0

# Fly.io
REDIS_URL=redis://redis-app-name.internal:6379/0
```

### Default Values

If `REDIS_URL` is not set:

- Default: `redis://localhost:6379/0`
- Cache service will attempt connection
- If connection fails, cache is disabled (graceful degradation)

---

## ✅ VERIFICATION

### Check Cache Status

**Via API:**

```bash
curl https://nuzantara-rag.fly.dev/api/articles/compose/status
```

**Response:**

```json
{
  "configured": true,
  "api_key_set": true,
  "model": "claude-sonnet-4-20250514",
  "estimated_cost_per_article": "$0.02-0.05",
  "cache_enabled": true, // ← Should be true if Redis is working
  "rate_limit": "10 requests/minute per IP"
}
```

### Test Cache Functionality

1. **First Request (Cache Miss):**

   ```bash
   curl -X POST https://nuzantara-rag.fly.dev/api/articles/compose \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Test Article",
       "content": "Test content...",
       "category": "business"
     }'
   ```

   Response: `"cached": false`

2. **Second Request (Cache Hit):**
   ```bash
   # Same request
   ```
   Response: `"cached": true` (should be instant)

### Check Redis Connection

**Local:**

```bash
redis-cli ping
# Should return: PONG
```

**Via Python:**

```python
import redis.asyncio as redis

client = await redis.from_url("redis://localhost:6379/0")
result = await client.ping()
print(result)  # Should be True
```

---

## 📊 MONITORING

### Prometheus Metrics

**Cache Metrics:**

```promql
# Cache hit rate
rate(article_cache_hits_total[5m]) /
(rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))

# Cache hits per operation
article_cache_hits_total{operation="compose"}

# Cache misses per operation
article_cache_misses_total{operation="compose"}
```

### Redis Monitoring

**Key Metrics:**

- Memory usage
- Connection count
- Hit rate
- Evictions

**Tools:**

- Redis CLI: `redis-cli INFO stats`
- RedisInsight (GUI)
- Grafana dashboards

---

## 🔧 TROUBLESHOOTING

### Cache Not Working

**Symptoms:**

- `cache_enabled: false` in status endpoint
- All requests show `cached: false`

**Solutions:**

1. Check Redis is running:

   ```bash
   redis-cli ping
   ```

2. Check `REDIS_URL` environment variable:

   ```bash
   echo $REDIS_URL
   ```

3. Check logs for connection errors:

   ```bash
   fly logs -a nuzantara-rag | grep -i redis
   ```

4. Verify Redis URL format:
   - Must start with `redis://` or `rediss://`
   - Port must be specified
   - Database number must be specified (`/0`)

### Connection Timeout

**Symptoms:**

- Cache initialization fails
- Timeout errors in logs

**Solutions:**

1. Check Redis is accessible from application
2. Verify firewall rules allow connection
3. Check Redis is listening on correct interface
4. For Fly.io: Use internal hostname (`*.internal`)

### Memory Issues

**Symptoms:**

- Redis evicting keys
- High memory usage

**Solutions:**

1. Monitor memory usage:

   ```bash
   redis-cli INFO memory
   ```

2. Adjust cache TTL (reduce if needed):
   - Edit `CACHE_TTL_COMPOSE` in `cache.py`
   - Default: 3600s (1 hour)

3. Increase Redis memory limit:
   - Fly.io: Scale Redis instance
   - External: Upgrade plan

---

## 📋 CHECKLIST

### Local Development

- [ ] Redis installed/running
- [ ] `REDIS_URL` set (or using default)
- [ ] Cache status shows `cache_enabled: true`
- [ ] Cache hit/miss working correctly

### Production

- [ ] Redis instance created
- [ ] `REDIS_URL` set in Fly.io secrets
- [ ] Connection tested
- [ ] Monitoring configured
- [ ] Alerting set up for cache failures

---

## 💡 BEST PRACTICES

1. **TTL Configuration:**
   - Compose results: 1 hour (good balance)
   - Status checks: 5 minutes (frequent updates)

2. **Memory Management:**
   - Monitor memory usage
   - Set appropriate maxmemory policy
   - Use eviction policy: `allkeys-lru`

3. **Security:**
   - Use password authentication in production
   - Use TLS (`rediss://`) for external connections
   - Restrict network access

4. **High Availability:**
   - Use Redis Sentinel for failover
   - Or managed Redis service with HA

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
