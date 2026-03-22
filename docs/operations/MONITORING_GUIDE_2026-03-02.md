# Monitoring Guide - Post API Fixes

**Date:** 2026-03-02  
**Version:** v2344  
**Status:** 🟡 Degraded (non-critical issues)

---

## Quick Health Check

### Backend Status

```bash
# Health endpoint
curl https://nuzantara-rag.fly.dev/health | jq .

# Detailed health with all services
curl https://nuzantara-rag.fly.dev/health/detailed | jq .

# Specific service status
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.kg_langgraph'
```

**Expected Response:**

```json
{
  "status": "healthy",
  "version": "v100-qdrant",
  "database": {
    "status": "connected",
    "type": "qdrant",
    "collections": 9,
    "total_documents": 66595
  },
  "embeddings": {
    "status": "operational",
    "provider": "openai",
    "model": "text-embedding-3-small",
    "dimensions": 1536
  }
}
```

---

## Critical Services Monitoring

### 1. Search Service (OpenAI Embeddings)

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.search'
```

**Expected:** `"status": "healthy"`

**If degraded:**

- Check OpenAI API key validity
- Verify network connectivity to OpenAI
- Check rate limits

---

### 2. AI Service (ZantaraAIClient)

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.ai'
```

**Expected:** `"status": "healthy"`

**If degraded:**

- Check LLM provider credentials
- Verify model availability
- Check request quotas

---

### 3. Router Service (IntelligentRouter)

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.router'
```

**Expected:** `"status": "healthy"`

**If degraded:**

- Check router initialization
- Verify routing rules loaded
- Check dependencies (search, ai)

---

## Database Monitoring

### Qdrant Vector Database

```bash
# Collection stats
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.database'

# Via MCP tool (if available)
# mcp0_get_collection_stats
```

**Expected Metrics:**

- Collections: 9
- Total documents: ~66,595
- Status: connected

**Collections to monitor:**

- `kbli_2025` - Business classification codes
- `lam_episodes` - LAM episodic memory
- `knowledge_base` - General knowledge
- `legal_documents` - Legal/regulatory content

---

### PostgreSQL Database

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.database'
```

**Expected:**

- Status: healthy
- Pool size: 3-5 connections (max 20)
- Min size: 5

**If degraded:**

- Check DATABASE_URL secret
- Verify PostgreSQL instance running
- Check connection pool exhaustion

---

## API Endpoint Monitoring

### Fixed Endpoints (Post v2344)

#### 1. CRM Expiry Alerts

```bash
# Correct URL (fixed in v2344)
curl https://nuzantara-rag.fly.dev/api/crm/expiry-alerts?days_ahead=30 \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Status:** ✅ Fixed (was 404, now 200)

**Monitor for:**

- Response time < 2s
- Valid JSON array response
- No 404 errors in logs

---

#### 2. LAM Memory Episodes

```bash
# List episodes (uses new scroll method)
curl https://nuzantara-rag.fly.dev/api/memory/lam/episodes?limit=5 \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Status:** ✅ Fixed (was 500, now 200)

**Monitor for:**

- Response time < 1s
- Valid episodes array
- No 500 errors in logs
- Scroll method working with filters

---

### KG LangGraph Status

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.kg_langgraph'
```

**Expected Response:**

```json
{
  "status": "pending_first_query",
  "critical": false,
  "details": {
    "enabled": true,
    "reason": "Lazy-init: orchestrator will initialize on first query"
  }
}
```

**Status:** ✅ Improved (was "initializing", now accurately reflects lazy-init)

**After first KG query, status should change to:**

```json
{
  "status": "healthy",
  "critical": false,
  "details": {
    "enabled": true,
    "initialized": true
  }
}
```

---

## Non-Critical Issues (Degraded)

### 1. FAQ Cache - DISABLED

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.registry.services.faq_cache'
```

**Current Status:** `"status": "degraded", "error": "DISABLED"`

**Impact:** Low - FAQ responses not cached, slightly slower response times

**Action:** Optional - enable if FAQ performance becomes issue

---

### 2. Channel Router - Missing Twitter Credentials

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.registry.services.channel_router'
```

**Current Status:** `"status": "degraded", "error": "consumer_key and consumer_secret required"`

**Impact:** Low - Twitter integration unavailable

**Action:** Optional - configure if Twitter channel needed

---

### 3. Health Monitor - Unavailable

```bash
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.services.health_monitor'
```

**Current Status:** `"status": "unavailable"`

**Impact:** Low - Manual monitoring still functional

**Action:** Investigate if automated health monitoring needed

---

## Fly.io Machine Monitoring

### Machine Status

```bash
# Via MCP tool
mcp0_check_fly_status

# Or via flyctl
flyctl status -a nuzantara-rag
```

**Expected:**

- Machine: `7849e2efe00148`
- State: `started`
- Region: `sin` (Singapore)
- Health checks: `passing`

---

### Resource Usage

```bash
flyctl metrics -a nuzantara-rag
```

**Monitor:**

- CPU: Should be < 80% average
- Memory: Should be < 1.5GB (2GB total)
- Disk: Should be < 800MB (1GB total)

**Alert if:**

- Memory > 1.8GB (risk of OOM)
- CPU sustained > 90%
- Disk > 950MB

---

## Logs Monitoring

### Real-time Logs

```bash
# All logs
flyctl logs -a nuzantara-rag --follow

# Error logs only
flyctl logs -a nuzantara-rag | grep -i "error\|exception\|failed"

# Specific endpoint
flyctl logs -a nuzantara-rag | grep "/api/crm/expiry-alerts"
```

---

### Via MCP Tool

```bash
# Last 50 lines
mcp0_get_fly_logs(lines=50)

# Filter for errors
mcp0_get_fly_logs(lines=100, filter_str="ERROR")

# Filter for KG
mcp0_get_fly_logs(lines=50, filter_str="KG")
```

---

## MCP Server Status

### Action Required: Restart MCP Server

**Issue:** MCP caller still using old URL `/api/crm/enhanced/expiry-alerts` (cached)

**Fix Applied:** URL corrected in `chains.py` to `/api/crm/expiry-alerts`

**Status:** ✅ Code deployed, ⚠️ MCP restart pending

**To Apply Fix:**

```bash
# Restart MCP server process
# (exact command depends on MCP deployment method)
```

**Verify Fix:**

```bash
# Check MCP grounding snapshot
mcp1_lam_grounding_snapshot

# Should no longer show 404 error on expiry-alerts
```

---

## Alert Thresholds

### Critical Alerts

Trigger immediate action if:

- ❌ Backend health check fails (status != "healthy")
- ❌ Critical service degraded (search, ai, router)
- ❌ Qdrant connection lost
- ❌ PostgreSQL connection lost
- ❌ Memory usage > 1.8GB
- ❌ Fly.io machine not started

---

### Warning Alerts

Monitor closely if:

- ⚠️ Response time > 5s on any endpoint
- ⚠️ Error rate > 1% on any endpoint
- ⚠️ Memory usage > 1.5GB
- ⚠️ CPU usage sustained > 80%
- ⚠️ Qdrant documents not increasing (ingestion stopped)

---

### Info Alerts

Track for trends:

- ℹ️ Non-critical service degraded
- ℹ️ KG LangGraph pending_first_query (normal)
- ℹ️ FAQ cache disabled (intentional)
- ℹ️ Channel router missing credentials (optional feature)

---

## Monitoring Schedule

### Every 5 Minutes (Automated)

- Health check endpoint
- Critical services status
- Fly.io machine status

### Every Hour (Automated)

- Database connection pool
- Qdrant collection stats
- Error rate analysis

### Daily (Manual)

- Review logs for patterns
- Check resource trends
- Verify backup status
- Review MCP activity

### Weekly (Manual)

- Performance analysis
- Capacity planning
- Update monitoring thresholds
- Review and update documentation

---

## Troubleshooting Quick Reference

### Backend Not Responding

```bash
# Check machine status
flyctl status -a nuzantara-rag

# Check logs for crash
flyctl logs -a nuzantara-rag | tail -100

# Restart if needed
flyctl restart -a nuzantara-rag
```

---

### Database Connection Issues

```bash
# Check PostgreSQL status
flyctl postgres status -a nuzantara-postgres

# Check DATABASE_URL secret
flyctl secrets list -a nuzantara-rag | grep DATABASE_URL

# Verify connection from machine
flyctl ssh console -a nuzantara-rag
# Then: psql $DATABASE_URL
```

---

### Qdrant Issues

```bash
# Check Qdrant health
curl https://nuzantara-rag.fly.dev/health/detailed | jq '.database'

# Check collection stats via MCP
mcp0_get_collection_stats

# Verify QDRANT_URL secret
flyctl secrets list -a nuzantara-rag | grep QDRANT_URL
```

---

### High Memory Usage

```bash
# Check current usage
flyctl metrics -a nuzantara-rag

# Check for memory leaks in logs
flyctl logs -a nuzantara-rag | grep -i "memory\|oom"

# Restart to clear
flyctl restart -a nuzantara-rag
```

---

## Success Metrics (Post v2344)

### API Endpoints

- ✅ `/api/crm/expiry-alerts` - 200 OK (was 404)
- ✅ `/api/memory/lam/episodes` - 200 OK (was 500)
- ✅ `/health/detailed` - KG status accurate (was ambiguous)

### System Health

- ✅ Critical services: All healthy
- ✅ Database: Connected, 66K+ documents
- ✅ Embeddings: Operational
- 🟡 Non-critical: Degraded (expected, non-blocking)

### Performance

- ✅ Response time < 2s average
- ✅ Error rate < 0.1%
- ✅ Uptime > 99.9%

---

**Last Updated:** 2026-03-22
**Next Review:** 2026-03-29
