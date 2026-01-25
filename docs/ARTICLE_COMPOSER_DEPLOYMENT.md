# Article Composer - Deployment Guide

**Version:** 2.0 (Best Practices 2026)  
**Last Updated:** 2026-01-24

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### 1. Code Verification ✅

**Run verification script:**

```bash
cd apps/backend-rag
./scripts/verify_article_composer_deploy.sh
```

**Manual checks:**

- [ ] Syntax check: `python3 -m py_compile backend/app/routers/article_composer.py`
- [ ] Import check: All services import correctly
- [ ] Linter: No errors
- [ ] Tests: Unit tests pass

### 2. Dependencies ✅

**Verify requirements.txt includes:**

- [ ] `slowapi>=0.1.9` (rate limiting)
- [ ] `tenacity>=8.2.3` (retry logic) - Already present
- [ ] `redis>=7.1.0` (caching) - Already present
- [ ] `anthropic>=0.75.0` (Claude API) - Already present

**Install/update dependencies:**

```bash
cd apps/backend-rag
pip install -r requirements.txt
```

### 3. Environment Variables ✅

**Required:**

- [ ] `ANTHROPIC_API_KEY` - Set in Fly.io secrets

**Optional (for caching):**

- [ ] `REDIS_URL` - Set if using Redis caching

**Set secrets:**

```bash
fly secrets set ANTHROPIC_API_KEY="sk-ant-..." -a nuzantara-rag

# Optional: Redis
fly secrets set REDIS_URL="redis://..." -a nuzantara-rag
```

### 4. Redis Configuration (Optional) ✅

**If using Redis:**

- [ ] Redis instance created/configured
- [ ] `REDIS_URL` set correctly
- [ ] Connection tested
- [ ] See `docs/REDIS_SETUP_GUIDE.md` for details

**If not using Redis:**

- [ ] Cache will be disabled (graceful degradation)
- [ ] System works without Redis
- [ ] Performance will be slower (no caching)

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Pre-Deployment Verification

```bash
cd apps/backend-rag

# Run verification script
./scripts/verify_article_composer_deploy.sh

# Should show: ✅ All checks passed!
```

### Step 2: Commit Changes

```bash
git add .
git commit -m "feat(article-composer): Implement Best Practices 2026

- Add retry logic with exponential backoff
- Add rate limiting (10 req/min)
- Add Redis caching
- Add circuit breaker
- Add structured error handling
- Add input validation
- Add background tasks
- Add dependency injection
- Improve logging

Fixes: #XXX"
```

### Step 3: Push to Repository

```bash
git push origin main
```

### Step 4: Deploy to Fly.io

**Automatic (if CI/CD configured):**

- Push triggers deployment automatically

**Manual:**

```bash
fly deploy -a nuzantara-rag
```

### Step 5: Verify Deployment

**Check health:**

```bash
curl https://nuzantara-rag.fly.dev/health
```

**Check Article Composer status:**

```bash
curl https://nuzantara-rag.fly.dev/api/articles/compose/status
```

**Expected response:**

```json
{
  "configured": true,
  "api_key_set": true,
  "model": "claude-sonnet-4-20250514",
  "estimated_cost_per_article": "$0.02-0.05",
  "cache_enabled": true, // or false if Redis not configured
  "rate_limit": "10 requests/minute per IP"
}
```

### Step 6: Test Endpoint

**Test compose endpoint:**

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/articles/compose \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Article Deployment",
    "content": "This is a test article to verify deployment is working correctly. It contains enough words to pass validation.",
    "category": "business"
  }'
```

**Expected:**

- Status: 200
- `success: true`
- `article` object present
- `request_id` present
- `cached: false` (first request)

---

## 📊 POST-DEPLOYMENT MONITORING

### 1. Check Logs

```bash
fly logs -a nuzantara-rag | grep -i "article_composer\|compose"
```

**Look for:**

- ✅ "Article composition started"
- ✅ "Cache hit" or "Cache miss"
- ✅ "Article enriched successfully"
- ❌ Any errors or warnings

### 2. Monitor Metrics

**Prometheus Metrics:**

```bash
curl https://nuzantara-rag.fly.dev/metrics | grep article_compose
```

**Key Metrics:**

- `article_compose_requests_total{status="success"}`
- `article_compose_duration_seconds`
- `article_cache_hits_total`
- `article_cache_misses_total`
- `claude_api_cost_cents`

### 3. Test Rate Limiting

**Test rate limit:**

```bash
# Make 11 requests rapidly
for i in {1..11}; do
  curl -X POST https://nuzantara-rag.fly.dev/api/articles/compose \
    -H "Content-Type: application/json" \
    -d '{"title": "Test", "content": "Test content with enough words", "category": "business"}'
  echo ""
done
```

**Expected:**

- First 10 requests: 200 OK
- 11th request: 429 Too Many Requests

### 4. Test Caching

**First request (cache miss):**

```bash
time curl -X POST https://nuzantara-rag.fly.dev/api/articles/compose \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Cache Test Article",
    "content": "This article tests caching functionality with enough content.",
    "category": "business"
  }'
```

**Second request (cache hit - should be faster):**

```bash
time curl -X POST https://nuzantara-rag.fly.dev/api/articles/compose \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Cache Test Article",
    "content": "This article tests caching functionality with enough content.",
    "category": "business"
  }'
```

**Expected:**

- First: `cached: false`, slower response
- Second: `cached: true`, faster response (<100ms)

### 5. Test Error Handling

**Test with invalid input:**

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/articles/compose \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Short",  # Too short
    "content": "Test",
    "category": "business"
  }'
```

**Expected:**

- Status: 422
- Structured error response

---

## 🔔 ALERTING SETUP

### Recommended Alerts

**1. High Error Rate**

```promql
rate(article_compose_requests_total{status=~"error|api_error|json_error"}[5m]) > 0.1
```

**2. Circuit Breaker Open**

```promql
# If circuit breaker metric exists
claude_circuit_breaker_state == 1  # OPEN state
```

**3. Cache Hit Rate Low**

```promql
rate(article_cache_hits_total[5m]) /
(rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m])) < 0.3
```

**4. High API Costs**

```promql
sum(increase(claude_api_cost_cents[1h])) > 1000  # $10/hour
```

**5. Rate Limit Exceeded**

```promql
rate(article_compose_requests_total{status="rate_limit"}[5m]) > 0
```

---

## 🐛 TROUBLESHOOTING

### Issue: Rate Limiting Not Working

**Symptoms:**

- No 429 errors even with many requests
- Rate limit not enforced

**Solutions:**

1. Verify `slowapi` is installed
2. Check limiter is configured:
   ```python
   router.state.limiter = limiter
   ```
3. Check middleware order in FastAPI app

### Issue: Cache Not Working

**Symptoms:**

- `cache_enabled: false` in status
- All requests show `cached: false`

**Solutions:**

1. Check Redis connection (see `REDIS_SETUP_GUIDE.md`)
2. Verify `REDIS_URL` is set correctly
3. Check logs for Redis connection errors
4. Test Redis connection manually

### Issue: Retry Logic Not Working

**Symptoms:**

- Immediate failures on transient errors
- No retry attempts

**Solutions:**

1. Verify `tenacity` is installed
2. Check error types are retryable:
   - `RateLimitError` ✅
   - `APIConnectionError` ✅
   - `APITimeoutError` ✅
   - `AuthenticationError` ❌ (not retryable)

### Issue: Circuit Breaker Always Open

**Symptoms:**

- All requests fail immediately
- Circuit breaker state: OPEN

**Solutions:**

1. Check failure threshold (default: 5)
2. Check recovery timeout (default: 60s)
3. Verify underlying service is healthy
4. Manually reset circuit breaker (restart app)

---

## 📈 PERFORMANCE BENCHMARKS

### Expected Performance

**Without Cache:**

- Average response time: 3-8 seconds
- Cost per article: $0.02-0.05

**With Cache:**

- Cache hit response time: <100ms
- Cache miss response time: 3-8 seconds
- Cost reduction: 30-50% (for cached requests)

### Monitoring Targets

- **Success Rate:** >95%
- **Cache Hit Rate:** >30% (after warmup)
- **Average Response Time:** <5s (p95)
- **Error Rate:** <5%

---

## 🔄 ROLLBACK PROCEDURE

If deployment causes issues:

**1. Quick Rollback:**

```bash
fly releases -a nuzantara-rag
fly releases rollback <previous-release-id> -a nuzantara-rag
```

**2. Code Rollback:**

```bash
git revert <commit-hash>
git push origin main
fly deploy -a nuzantara-rag
```

**3. Disable Features:**

- Remove rate limiting decorator
- Disable cache (set `REDIS_URL` to empty)
- Use old error handling (temporary)

---

## 📝 POST-DEPLOYMENT TASKS

- [ ] Monitor metrics for 24 hours
- [ ] Verify cache hit rate improves
- [ ] Check error rates are acceptable
- [ ] Review cost savings
- [ ] Update documentation with learnings
- [ ] Set up alerting rules
- [ ] Schedule follow-up review

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
