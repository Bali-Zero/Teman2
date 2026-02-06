# Portal Monitoring & Operations Guide

## 📋 Table of Contents

1. [Cron Job Configuration](#cron-job-configuration)
2. [Manual Testing](#manual-testing)
3. [Grafana Dashboard](#grafana-dashboard)
4. [Troubleshooting](#troubleshooting)

---

## 1. Cron Job Configuration

### GitHub Actions (Recommended)

**File:** `.github/workflows/deadline-checker-daily.yml`

**Schedule:** Daily at 6:00 AM Singapore time (22:00 UTC previous day)

**Setup:**

1. Add `DATABASE_URL` secret to GitHub repository:

   ```
   Settings → Secrets and variables → Actions → New repository secret
   Name: DATABASE_URL
   Value: postgresql://user:pass@host:port/dbname
   ```

2. Enable workflow:

   ```bash
   # Workflow is automatically enabled when pushed to main
   # Verify at: https://github.com/YOUR_ORG/YOUR_REPO/actions
   ```

3. Manual trigger (optional):
   ```bash
   # Via GitHub UI: Actions → Deadline Checker → Run workflow
   # Or via gh CLI:
   gh workflow run deadline-checker-daily.yml
   ```

**Monitoring:**

- Workflow runs: `https://github.com/YOUR_ORG/YOUR_REPO/actions`
- Failures create automatic GitHub issues with label `cron-job`

---

### Alternative: Fly.io Machines

If you prefer running on Fly.io infrastructure:

```bash
# Create scheduled machine
fly machines run \
  --app nuzantara-rag \
  --schedule daily \
  --entrypoint "python -m backend.jobs.deadline_checker" \
  registry.fly.io/nuzantara-rag:latest

# View scheduled machines
fly machines list -a nuzantara-rag --scheduled
```

---

## 2. Manual Testing

### Test Script

**File:** `apps/backend-rag/scripts/test_portal_endpoints.py`

**Prerequisites:**

```bash
pip install requests
```

**Get JWT Token:**

1. **Option A: Browser DevTools**

   ```
   1. Login to Portal: https://portal.balizero.com
   2. Open DevTools (F12) → Application → Storage → Cookies
   3. Copy value of 'auth_token' or 'jwt_token' cookie
   ```

2. **Option B: Portal Login API** (if available)
   ```bash
   curl -X POST https://portal.balizero.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"client@example.com","password":"xxx"}' \
     | jq -r '.token'
   ```

**Run Tests:**

```bash
cd apps/backend-rag

# Basic test
python scripts/test_portal_endpoints.py "eyJhbGciOiJIUzI1NiIs..."

# With verbose output
python scripts/test_portal_endpoints.py "eyJhbGciOiJIUzI1NiIs..." 2>&1 | tee test-results.log
```

**Expected Output:**

```
================================================================================
NUZANTARA Portal Endpoints - Manual Test Suite
================================================================================

Base URL: https://nuzantara-rag.fly.dev
Token: eyJhbGciOiJIUzI1NiIs...
Time: 2026-02-02T18:30:00+08:00

================================================================================
Testing: tax_full - /api/portal/taxes
================================================================================
Status: ✅ 200 OK
Response Time: 245ms

Response Data:
{
  "summary": {
    "total_due": 5000000,
    "next_deadline": "2026-03-15",
    "days_until_deadline": 41,
    "pending_count": 2,
    "overdue_count": 0,
    "status": "ok"
  },
  "obligations": [...]
}

✅ Found 2 tax obligations
✅ Summary status: ok

================================================================================
TEST SUMMARY
================================================================================

✅ PASS - tax_full
✅ PASS - tax_summary
✅ PASS - visa_full
✅ PASS - visa_summary

Total: 4/4 passed

🎉 All tests passed!
```

---

## 3. Grafana Dashboard

### Import Dashboard

**File:** `apps/backend-rag/grafana-dashboard-portal.json`

**Steps:**

1. **Open Grafana**

   ```
   https://grafana.your-domain.com
   ```

2. **Import Dashboard**

   ```
   Dashboards → Import → Upload JSON file
   → Select grafana-dashboard-portal.json
   → Select Prometheus data source
   → Import
   ```

3. **Configure Data Source**
   ```
   Ensure Prometheus data source is configured:
   - Name: Prometheus
   - URL: http://prometheus:9090 (or your Prometheus URL)
   - Access: Server (default)
   ```

### Dashboard Panels

The dashboard includes:

1. **Request Rate** (2 panels)
   - Tax endpoint requests/sec (success vs error)
   - Visa endpoint requests/sec (success vs error)

2. **Success Rate** (2 panels)
   - Tax endpoint success rate (%)
   - Visa endpoint success rate (%)

3. **Deadline Checker** (2 panels)
   - Total execution count
   - Time since last run (seconds)

4. **Latency** (2 panels)
   - Tax endpoint p50/p95/p99 latency
   - Visa endpoint p50/p95/p99 latency

5. **Reminders** (1 panel)
   - Reminders created by type (tax/visa) and urgency (critical/warning/info)

6. **Request Tables** (2 panels)
   - Tax requests by endpoint
   - Visa requests by endpoint

### Dashboard URL

After import: `https://grafana.your-domain.com/d/portal-monitoring`

---

## 4. Troubleshooting

### Cron Job Issues

**Problem:** Deadline checker not running

**Solution:**

```bash
# Check GitHub Actions logs
gh run list --workflow=deadline-checker-daily.yml --limit 5

# View specific run logs
gh run view <RUN_ID> --log

# Manual trigger
gh workflow run deadline-checker-daily.yml
```

**Problem:** Database connection failed

**Solution:**

```bash
# Verify DATABASE_URL secret is set
gh secret list

# Test database connection
fly ssh console -a nuzantara-rag
python -c "import asyncio; import asyncpg; asyncio.run(asyncpg.connect('postgresql://...'))"
```

---

### Endpoint Testing Issues

**Problem:** 401 Unauthorized

**Cause:** JWT token expired or invalid

**Solution:**

```bash
# Get fresh token from Portal login
# Tokens typically expire after 24 hours
```

**Problem:** 403 Forbidden

**Cause:** Token doesn't have `client` role

**Solution:**

```bash
# Verify token payload
echo "eyJhbGciOi..." | cut -d. -f2 | base64 -d | jq

# Check "role" field should be "client"
```

**Problem:** 404 Not Found

**Cause:** Endpoints not registered

**Solution:**

```bash
# Verify deployment
fly status -a nuzantara-rag

# Check logs
fly logs -a nuzantara-rag | grep portal_taxes

# Verify router registration
fly ssh console -a nuzantara-rag
python -c "from backend.app.main import app; print([r.path for r in app.routes])"
```

---

### Grafana Dashboard Issues

**Problem:** No data showing

**Cause:** Prometheus not scraping metrics or no requests yet

**Solution:**

```bash
# Verify metrics endpoint
curl https://nuzantara-rag.fly.dev/metrics | grep portal_

# Check Prometheus targets
# Prometheus UI → Status → Targets
# Ensure nuzantara-rag target is UP

# Generate test requests
python scripts/test_portal_endpoints.py <JWT_TOKEN>
```

**Problem:** Queries returning errors

**Cause:** PromQL syntax errors or missing metrics

**Solution:**

```bash
# Test queries directly in Prometheus
# Prometheus UI → Graph → Execute query

# Example queries:
rate(portal_tax_requests_total[5m])
histogram_quantile(0.95, portal_tax_latency_seconds_bucket)
```

---

## 5. Monitoring Best Practices

### Alerting Rules

Add to Prometheus `alert.rules.yml`:

```yaml
groups:
  - name: portal
    interval: 1m
    rules:
      # High error rate
      - alert: PortalHighErrorRate
        expr: |
          sum(rate(portal_tax_requests_total{status="error"}[5m])) 
          / sum(rate(portal_tax_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: 'Portal tax endpoint error rate > 5%'

      # High latency
      - alert: PortalHighLatency
        expr: |
          histogram_quantile(0.95, 
            sum(rate(portal_tax_latency_seconds_bucket[5m])) by (le)
          ) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: 'Portal tax endpoint p95 latency > 2s'

      # Deadline checker not running
      - alert: DeadlineCheckerStale
        expr: |
          time() - deadline_checker_last_run_timestamp > 86400
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Deadline checker hasn't run in 24+ hours"
```

### Logging Best Practices

**Structured Logging Example:**

```python
logger.info(
    "Tax obligations fetched",
    client_id=client_id,
    count=len(obligations),
    include_completed=include_completed,
    response_time_ms=elapsed_ms
)
```

**Query Logs:**

```bash
# Fly.io logs
fly logs -a nuzantara-rag | grep "Tax obligations fetched"

# Filter by client_id
fly logs -a nuzantara-rag | jq 'select(.client_id == 123)'

# Error logs only
fly logs -a nuzantara-rag | grep "ERROR"
```

---

## 6. Performance Optimization

### Database Indexes

```sql
-- Tax obligations indexes
CREATE INDEX idx_tax_client_status ON tax_obligations(client_id, status);
CREATE INDEX idx_tax_due_date ON tax_obligations(due_date) WHERE status IN ('upcoming', 'pending');

-- Visa records indexes
CREATE INDEX idx_visa_client_status ON visa_records(client_id, status);
CREATE INDEX idx_visa_expiry_date ON visa_records(expiry_date) WHERE status IN ('active', 'expiring_soon');

-- Timeline events indexes
CREATE INDEX idx_timeline_client_visible ON timeline_events(client_id, client_visible, event_date DESC);
```

### Caching Strategy

```python
# Add Redis caching for summary endpoints
from redis import Redis

redis_client = Redis(host='localhost', port=6379, decode_responses=True)

async def get_tax_summary(client_id: int) -> TaxSummary:
    # Try cache first
    cache_key = f"tax_summary:{client_id}"
    cached = redis_client.get(cache_key)

    if cached:
        return TaxSummary.parse_raw(cached)

    # Query database
    summary = await _compute_tax_summary(client_id)

    # Cache for 5 minutes
    redis_client.setex(cache_key, 300, summary.json())

    return summary
```

---

## 7. Next Steps

### Short-term (This Month)

- [ ] **Email Notifications** - Send T-7 day reminders
- [ ] **Telegram Alerts** - Send urgent reminders
- [ ] **Database Indexes** - Add performance indexes

### Long-term (Future)

- [ ] **Auto-Practice Creation** - T-60 visa renewal practices
- [ ] **Client Portal UI** - React dashboard components
- [ ] **Historical Analytics** - Completion rate tracking

---

**Last Updated:** 2026-02-02  
**Maintained by:** DevOps Team
