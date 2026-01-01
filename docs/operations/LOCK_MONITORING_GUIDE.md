# Lock Monitoring Guide

**Last Updated:** 2025-12-28  
**Status:** ✅ Ready for Production

## Overview

This guide provides instructions for monitoring race condition locks and their performance in the NUZANTARA platform.

---

## Quick Start

### 1. Verify Prometheus Configuration

Check that Prometheus is loading the alert rules:

```bash
# Check Prometheus status
curl http://localhost:9090/api/v1/rules

# Verify alerts.yml is loaded
curl http://localhost:9090/api/v1/alerts
```

### 2. Import Grafana Dashboard

Import the lock contention dashboard:

1. Open Grafana: http://localhost:3001
2. Go to **Dashboards** → **Import**
3. Upload: `config/grafana/dashboards/lock-contention-dashboard.json`
4. Select Prometheus data source
5. Click **Import**

### 3. Verify Metrics Endpoint

Check that metrics are being exposed:

```bash
# Check backend metrics endpoint
curl http://localhost:8000/metrics | grep zantara_memory_lock

# Expected output should include:
# - zantara_memory_lock_timeout_total
# - zantara_memory_lock_contention_seconds
# - zantara_collection_lock_timeout_total
# - zantara_cache_db_consistency_errors_total
```

---

## Grafana Queries

### Memory Lock Timeouts

**Query:**
```promql
rate(zantara_memory_lock_timeout_total[5m])
```

**Visualization:** Time series graph  
**Alert Threshold:** > 0 timeouts/sec for 2 minutes

### Memory Lock Contention

**Query:**
```promql
rate(zantara_memory_lock_contention_seconds_sum[5m]) / 
rate(zantara_memory_lock_contention_seconds_count[5m])
```

**Visualization:** Time series graph  
**Alert Threshold:** > 0.1 seconds average wait time for 5 minutes

### Collection Lock Timeouts

**Query:**
```promql
rate(zantara_collection_lock_timeout_total[5m])
```

**Visualization:** Time series graph  
**Alert Threshold:** > 0 timeouts/sec for 2 minutes

### Cache-DB Consistency Errors

**Query:**
```promql
rate(zantara_cache_db_consistency_errors_total[5m])
```

**Visualization:** Time series graph  
**Alert Threshold:** > 0 errors/sec for 5 minutes

### Top Users by Lock Timeouts

**Query:**
```promql
topk(10, sum by (user_id) (rate(zantara_memory_lock_timeout_total[5m])))
```

**Visualization:** Table  
**Use Case:** Identify users experiencing lock contention

### Lock Contention Distribution

**Query:**
```promql
rate(zantara_memory_lock_contention_seconds_bucket[5m])
```

**Visualization:** Heatmap  
**Use Case:** Understand lock wait time distribution

---

## Prometheus Alerts

All alerts are configured in `config/prometheus/alerts.yml`:

### Warning Alerts

1. **HighMemoryLockContention**
   - Condition: Average lock wait > 0.1s for 5m
   - Severity: warning
   - Action: Investigate system load

2. **MemoryLockTimeouts**
   - Condition: Any timeout detected for 2m
   - Severity: warning
   - Action: Check for stuck operations

3. **CollectionLockTimeouts**
   - Condition: Any timeout detected for 2m
   - Severity: warning
   - Action: Review ingestion operations

4. **CacheDBConsistencyErrors**
   - Condition: Any error detected for 5m
   - Severity: warning
   - Action: Check database connectivity

### Critical Alerts

1. **CriticalMemoryLockTimeouts**
   - Condition: Timeout rate > 0.1/s for 1m
   - Severity: critical
   - Action: Immediate investigation required

2. **CriticalCollectionLockTimeouts**
   - Condition: Timeout rate > 0.05/s for 1m
   - Severity: critical
   - Action: Immediate investigation required

3. **CriticalCacheDBConsistencyErrors**
   - Condition: Error rate > 0.1/s for 2m
   - Severity: critical
   - Action: Immediate investigation required

---

## Troubleshooting

### High Lock Contention

**Symptoms:**
- `memory_lock_contention_seconds` > 0.1s
- Frequent lock timeouts

**Investigation Steps:**

1. Check system load:
   ```bash
   # CPU and memory usage
   docker stats nuzantara-backend
   ```

2. Review lock metrics:
   ```promql
   # Top users experiencing contention
   topk(10, sum by (user_id) (rate(zantara_memory_lock_contention_seconds_sum[5m])))
   ```

3. Check for long-running operations:
   ```bash
   # Database slow queries
   curl http://localhost:8000/api/debug/postgres/slow-queries
   ```

**Solutions:**
- Increase semaphore limits (if reads are blocked)
- Review timeout values
- Scale horizontally
- Optimize slow operations

### Lock Timeouts

**Symptoms:**
- `memory_lock_timeout_total` increasing
- Operations failing silently

**Investigation Steps:**

1. Check timeout rate:
   ```promql
   rate(zantara_memory_lock_timeout_total[5m])
   ```

2. Identify affected users:
   ```promql
   sum by (user_id) (rate(zantara_memory_lock_timeout_total[5m]))
   ```

3. Review application logs:
   ```bash
   # Check for timeout warnings
   docker logs nuzantara-backend | grep "lock timeout"
   ```

**Solutions:**
- Increase lock timeout (if operations are legitimately slow)
- Investigate deadlock scenarios
- Check for stuck operations
- Review system resources

### Cache-DB Consistency Errors

**Symptoms:**
- `cache_db_consistency_errors_total` increasing
- Conversations not persisting

**Investigation Steps:**

1. Check error rate:
   ```promql
   rate(zantara_cache_db_consistency_errors_total[5m])
   ```

2. Verify database connectivity:
   ```bash
   curl http://localhost:8000/health/ready
   ```

3. Check retry mechanism:
   ```bash
   # Review conversation save logs
   docker logs nuzantara-backend | grep "DB Save failed"
   ```

**Solutions:**
- Check database connectivity
- Review retry mechanism logs
- Verify cache and DB are in sync
- Check for network issues

---

## Performance Benchmarks

### Expected Values

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Lock Contention | < 0.01s | 0.01-0.1s | > 0.1s |
| Lock Timeouts | 0/s | > 0/s | > 0.1/s |
| Collection Timeouts | 0/s | > 0/s | > 0.05/s |
| Consistency Errors | 0/s | > 0/s | > 0.1/s |

### Lock Overhead

- **Memory locks**: < 1ms per operation (when not contended)
- **Collection locks**: < 1ms per operation (when not contended)
- **Database locks**: Managed by PostgreSQL (negligible)

---

## Monitoring Checklist

### Daily Checks

- [ ] Review lock contention dashboard
- [ ] Check for active alerts
- [ ] Review top users by lock timeouts
- [ ] Verify metrics are being collected

### Weekly Reviews

- [ ] Analyze lock contention trends
- [ ] Review timeout patterns
- [ ] Check for optimization opportunities
- [ ] Update alert thresholds if needed

### Monthly Analysis

- [ ] Review lock performance trends
- [ ] Analyze user patterns
- [ ] Optimize lock configuration
- [ ] Update documentation

---

## Grafana Dashboard Panels

The lock contention dashboard includes:

1. **Memory Lock Timeouts** - Time series of timeout rates
2. **Memory Lock Contention** - Average wait time per operation
3. **Collection Lock Timeouts** - Ingestion operation timeouts
4. **Cache-DB Consistency Errors** - Consistency error rates
5. **Lock Contention Distribution** - Heatmap of wait times
6. **Top Users by Lock Timeouts** - Table of affected users
7. **Lock Operations Summary** - Summary statistics
8. **Avg Lock Wait Time** - Current average wait time

---

## Alerting Integration

### Alertmanager Configuration

Ensure Alertmanager is configured to receive alerts:

```yaml
# config/alertmanager/alertmanager.yml
route:
  group_by: ['alertname', 'severity']
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'default'
    # Configure notification channels
  - name: 'critical-alerts'
    # Configure critical notification channels
  - name: 'warning-alerts'
    # Configure warning notification channels
```

### Notification Channels

Configure notification channels for:
- **Critical alerts**: Immediate notification (Slack, PagerDuty, etc.)
- **Warning alerts**: Daily summary (Email, Slack, etc.)

---

## References

- [Race Conditions & Locking Documentation](../RACE_CONDITIONS_LOCKING.md)
- [Prometheus Alerts Configuration](../../config/prometheus/alerts.yml)
- [Grafana Dashboard](../../config/grafana/dashboards/lock-contention-dashboard.json)
- [Test Suite](../../apps/backend-rag/tests/unit/services/)

---

*Guide created: 2025-12-28*


