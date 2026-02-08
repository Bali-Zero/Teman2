# Intel Router Monitoring & CI/CD Setup

**Date:** 2026-01-17  
**Status:** ✅ Complete

---

## 📋 Overview

Complete monitoring, testing, and CI/CD setup for Intel Router refactoring.

---

## 🔍 Monitoring Scripts

### 1. Log Monitoring (`monitor_intel_logs.py`)

**Purpose:** Monitor Fly.io logs for Intel-related errors and warnings.

**Usage:**

```bash
python3 scripts/monitoring/monitor_intel_logs.py [limit]
```

**Features:**

- Fetches logs from Fly.io
- Analyzes for errors, warnings, Intel operations
- Tracks service call counts
- Generates JSON report

**Output:**

- Terminal report with color-coded status
- JSON report: `scripts/monitoring/intel_logs_report.json`

**Exit Codes:**

- `0`: No errors (warnings may be present)
- `1`: Errors detected

---

### 2. Metrics Monitoring (`monitor_intel_metrics.py`)

**Purpose:** Monitor Prometheus metrics for Intel services.

**Usage:**

```bash
python3 scripts/monitoring/monitor_intel_metrics.py
```

**Features:**

- Fetches metrics from `/metrics` endpoint
- Analyzes Intel-specific metrics
- Calculates duplicate rates
- Checks staging queue sizes
- Generates JSON report

**Output:**

- Terminal report with metrics summary
- JSON report: `scripts/monitoring/intel_metrics_report.json`

**Metrics Tracked:**

- Articles submitted
- Duplicates detected
- Classifications by type
- Staging queue sizes
- Service health indicators

**Exit Codes:**

- `0`: All metrics within normal range
- `1`: Staging queue size exceeds 100 items

---

### 3. Performance Monitoring (`monitor_intel_performance.py`)

**Purpose:** Measure response times and performance of Intel endpoints.

**Usage:**

```bash
python3 scripts/monitoring/monitor_intel_performance.py [iterations]
```

**Features:**

- Measures response times for key endpoints
- Calculates min, max, avg, P50, P95
- Identifies slow endpoints
- Generates performance recommendations

**Endpoints Tested:**

- `/health`
- `/metrics`
- `/api/intel/metrics`

**Output:**

- Terminal report with performance metrics
- JSON report: `scripts/monitoring/intel_performance_report.json`

**Performance Thresholds:**

- Excellent: < 200ms
- Good: < 500ms
- Acceptable: < 1000ms
- Slow: > 1000ms

**Exit Codes:**

- `0`: All endpoints performing well
- `1`: Performance degraded

---

### 4. Daily Monitoring Script (`daily_intel_monitor.sh`)

**Purpose:** Run all monitoring checks daily via cron.

**Usage:**

```bash
# Add to crontab:
0 9 * * * /path/to/scripts/monitoring/daily_intel_monitor.sh
```

**Features:**

- Runs all monitoring scripts
- Generates daily reports
- Provides summary status
- Saves reports to `scripts/monitoring/reports/`

**Reports Generated:**

- `logs_YYYYMMDD.txt`
- `metrics_YYYYMMDD.txt`
- `performance_YYYYMMDD.txt`
- `production_test_YYYYMMDD.txt`

---

## 🧪 Testing Scripts

### 1. Production Tests (`test_intel_production.py`)

**Purpose:** End-to-end tests of Intel Router endpoints in production.

**Usage:**

```bash
python3 scripts/testing/test_intel_production.py
```

**Environment Variables:**

- `INTEL_API_URL`: Base URL (default: https://nuzantara-rag.fly.dev)
- `INTEL_API_KEY`: API key for authenticated endpoints

**Tests Performed:**

1. Health check (`/health`)
2. System metrics (`/api/intel/metrics`)
3. Staging pending (`/api/intel/staging/pending`)
4. Prometheus metrics (`/metrics`)

**Output:**

- Terminal report with test results
- JSON report: `scripts/monitoring/intel_production_test_report.json`

**Exit Codes:**

- `0`: All tests passed
- `1`: Tests failed or errors occurred

---

### 2. Approval Workflow Tests (`test_intel_approval_workflow.py`)

**Purpose:** Verify approval workflow functionality.

**Usage:**

```bash
python3 scripts/testing/test_intel_approval_workflow.py
```

**Features:**

- Checks pending items in staging
- Verifies staging item access
- Checks Telegram notification status (requires file system access)

**Output:**

- Terminal report with workflow status
- JSON report: `scripts/monitoring/intel_approval_workflow_test.json`

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow (`intel-router-tests.yml`)

**Location:** `.github/workflows/intel-router-tests.yml`

**Triggers:**

- Push to `main` branch (Intel Router files)
- Pull requests to `main` branch
- Manual workflow dispatch

**Jobs:**

#### 1. Test Job

- Runs unit tests for all Intel services
- Checks code syntax
- Uploads test results as artifacts

**Test Files:**

- `test_intel_classification_service.py`
- `test_intel_staging_service.py`
- `test_intel_approval_service.py`
- `test_intel_analytics_service.py`

#### 2. Lint Job

- Checks code formatting (black)
- Checks import ordering (isort)
- Validates code style

#### 3. Post-Deploy Test Job

- **Note:** Deploy is done manually from local machine using `fly deploy`
- Post-deploy tests should be run manually after deployment
- Use `scripts/deployment/deploy_intel_router.sh` for automated deploy + test flow

**Artifacts:**

- Test results (7 days retention)
- Production test reports (7 days retention)

---

## 📊 Monitoring Dashboard

### Key Metrics to Monitor

1. **Error Rate**
   - Target: < 0.1%
   - Alert: > 1%

2. **Response Time**
   - Target: < 500ms (P95)
   - Alert: > 1000ms (P95)

3. **Staging Queue Size**
   - Target: < 50 items
   - Warning: 50-100 items
   - Alert: > 100 items

4. **Duplicate Rate**
   - Target: < 10%
   - Alert: > 20%

5. **Classification Accuracy**
   - Monitor visa vs news classification distribution

---

## 🚨 Alerting

### Recommended Alerts

1. **High Error Rate**
   - Condition: > 5 errors in 5 minutes
   - Action: Notify team via Slack/Email

2. **Slow Response Times**
   - Condition: P95 > 1000ms for 10 minutes
   - Action: Investigate performance issues

3. **Staging Queue Backlog**
   - Condition: Queue size > 100 items
   - Action: Review approval workflow

4. **Service Unavailable**
   - Condition: Health check fails
   - Action: Immediate investigation

---

## 📝 Usage Examples

### Daily Monitoring

```bash
# Run all monitoring checks
./scripts/monitoring/daily_intel_monitor.sh

# Check logs only
python3 scripts/monitoring/monitor_intel_logs.py 200

# Check metrics only
python3 scripts/monitoring/monitor_intel_metrics.py

# Check performance only
python3 scripts/monitoring/monitor_intel_performance.py 10
```

### Production Testing

```bash
# Run production tests
python3 scripts/testing/test_intel_production.py

# Test approval workflow
python3 scripts/testing/test_intel_approval_workflow.py
```

### Deployment

**Deploy is done manually from local machine:**

```bash
# Option 1: Manual deploy
cd apps/backend-rag
fly deploy -a nuzantara-rag --remote-only

# Option 2: Automated deploy with verification
./scripts/deployment/deploy_intel_router.sh
```

**Post-deploy verification:**

```bash
# Run production tests after deployment
python3 scripts/testing/test_intel_production.py

# Check metrics
python3 scripts/monitoring/monitor_intel_metrics.py

# Check performance
python3 scripts/monitoring/monitor_intel_performance.py
```

### CI/CD

```bash
# Trigger workflow manually (tests only, no deploy)
gh workflow run intel-router-tests.yml

# View workflow runs
gh run list --workflow=intel-router-tests.yml
```

---

## ✅ Verification Checklist

- [x] Monitoring scripts created
- [x] Testing scripts created
- [x] CI/CD workflow configured
- [x] Daily monitoring script ready
- [x] Production tests verified
- [x] Documentation complete

---

## 🎯 Next Steps

1. **Set up cron job** for daily monitoring
2. **Configure alerts** in monitoring system
3. **Review test results** from CI/CD runs
4. **Monitor metrics** in Prometheus dashboard
5. **Adjust thresholds** based on production data

---

**Monitoring and CI/CD setup complete!** ✅
