# RAG Retrieval Quality Monitoring Dashboard

## Overview

This monitoring dashboard provides comprehensive visibility into the Nuzantara RAG system's retrieval quality metrics, helping identify performance issues, track optimization efforts, and ensure high-quality responses.

## Files Created

### 1. Backend Service (`apps/backend-rag/backend/services/rag/evaluation/monitoring.py`)

**Class: `RetrievalQualityMonitor`**

Core monitoring service with the following capabilities:

#### Metrics Tracked

| Metric                        | Description                              | Prometheus Type |
| ----------------------------- | ---------------------------------------- | --------------- |
| `retrieval_scores_avg`        | Average retrieval score over time        | Gauge           |
| `retrieval_scores_p95`        | 95th percentile score                    | Gauge           |
| `retrieval_scores_p99`        | 99th percentile score                    | Gauge           |
| `abstain_rate_percent`        | % of queries that ABSTAIN                | Gauge           |
| `abstain_total`               | Total ABSTAIN responses by domain/reason | Counter         |
| `evidence_score_distribution` | Histogram of scores                      | Histogram       |
| `query_latency_ms`            | Response time distribution               | Histogram       |
| `cache_hit_rate_percent`      | Redis cache effectiveness                | Gauge           |
| `hybrid_search_usage_percent` | % using hybrid vs dense                  | Gauge           |
| `reranker_usage_percent`      | % using reranking                        | Gauge           |
| `reranker_improvement`        | Score improvement from reranking         | Histogram       |

#### Methods

- `record_query_metrics(query, results, latency_ms, ...)` - Record metrics for a query
- `record_retrieval_score(score)` - Record standalone score
- `record_abstain(domain, reason)` - Record ABSTAIN response
- `record_cache_access(hit)` - Record cache hit/miss
- `record_reranker_effectiveness(before, after)` - Track reranker improvement
- `get_dashboard_data(time_range)` - Get aggregated metrics
- `get_scores_trend(days)` - Get historical score trends
- `get_abstain_statistics(days)` - Get abstain analytics
- `get_latency_percentiles(days)` - Get latency statistics
- `set_alert_thresholds(thresholds)` - Configure alert thresholds

---

### 2. API Router (`apps/backend-rag/backend/app/routers/monitoring_rag.py`)

**Base Path: `/api/monitoring`**

#### Endpoints

| Method | Path                 | Description              | Access |
| ------ | -------------------- | ------------------------ | ------ |
| GET    | `/retrieval-quality` | Current metrics snapshot | Admin  |
| GET    | `/scores-trend`      | Historical score trends  | Admin  |
| GET    | `/abstain-rate`      | Abstain statistics       | Admin  |
| GET    | `/latency`           | Latency percentiles      | Admin  |
| POST   | `/alert-threshold`   | Set alert thresholds     | Admin  |
| GET    | `/alert-threshold`   | Get current thresholds   | Admin  |
| GET    | `/health`            | Service health check     | Public |

#### Example Usage

```bash
# Get current metrics
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/monitoring/retrieval-quality?time_range=24h

# Get score trends
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/monitoring/scores-trend?days=7

# Set alert thresholds
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"min_score": 0.4, "max_abstain_rate": 0.15}' \
  http://localhost:8000/api/monitoring/alert-threshold
```

---

### 3. Grafana Dashboard (`monitoring/grafana/dashboards/rag_quality.json`)

**Dashboard ID: `rag-quality-monitoring`**

#### Panels

| Panel                       | Type              | Description                     |
| --------------------------- | ----------------- | ------------------------------- |
| Avg Score (24h)             | Gauge             | Current average retrieval score |
| Abstain Rate %              | Gauge             | Current abstain percentage      |
| Cache Hit Rate %            | Gauge             | Redis cache effectiveness       |
| P95 Latency                 | Stat              | 95th percentile response time   |
| Retrieval Score Trend       | Time Series       | Score trends over time          |
| Query Latency Heatmap       | Heatmap           | Latency distribution            |
| Evidence Score Distribution | Histogram         | Score bucket distribution       |
| Usage Patterns              | Bar Chart         | Hybrid vs Dense, Reranker usage |
| Top Low-Score Queries       | Table             | Queries needing attention       |
| Alert Threshold Breaches    | Table             | Recent threshold violations     |
| Abstain Trends              | Time Series       | Abstains by domain              |
| A/B Test Results            | Time Series + Bar | Hybrid vs Dense comparison      |

#### Alerts Configured

| Alert              | Condition          | Severity |
| ------------------ | ------------------ | -------- |
| Low Score          | Score < 0.3        | Warning  |
| High Abstain Rate  | Abstain rate > 20% | Critical |
| High Latency       | Latency > 5s       | Warning  |
| Low Cache Hit Rate | Cache hit < 50%    | Warning  |

---

### 4. Tests (`apps/backend-rag/backend/tests/services/rag/evaluation/test_monitoring.py`)

**52 Tests** covering:

- Metric recording functionality
- Dashboard data aggregation
- Alert threshold management
- Prometheus metrics integration
- Edge cases and error handling
- Time range parsing
- Percentile calculations
- Score distributions
- Integration workflows

Run tests:

```bash
cd apps/backend-rag
source .venv/bin/activate
pytest backend/tests/services/rag/evaluation/test_monitoring.py -v
```

---

## Integration Guide

### 1. Add to RAG Pipeline

```python
from backend.services.rag.evaluation.monitoring import retrieval_quality_monitor

async def process_query(query: str, ...):
    start_time = time.time()

    # Your RAG pipeline
    results = await search(query)
    reranked = await rerank(results)

    # Record metrics
    latency_ms = (time.time() - start_time) * 1000
    await retrieval_quality_monitor.record_query_metrics(
        query=query,
        results=reranked,
        latency_ms=latency_ms,
        search_type="hybrid",
        use_reranker=True,
        cache_hit=cache_hit,
    )

    return reranked
```

### 2. Record Abstains

```python
if confidence < threshold:
    retrieval_quality_monitor.record_abstain(
        domain="visa",
        reason="low_confidence"
    )
    return {"response": "ABSTAIN", "reason": "low_confidence"}
```

### 3. Track Reranker Effectiveness

```python
before_scores = [r.score for r in results]
after_scores = [r.score for r in reranked]

retrieval_quality_monitor.record_reranker_effectiveness(
    before_scores=before_scores,
    after_scores=after_scores
)
```

---

## Grafana Setup

### Auto-Provisioning

The dashboard is automatically provisioned via:

- **Dashboard Config:** `monitoring/grafana/dashboards/dashboard.yml`
- **Dashboard JSON:** `monitoring/grafana/dashboards/rag_quality.json`

### Manual Import

1. Open Grafana UI (`http://localhost:3000`)
2. Go to Dashboards → Import
3. Upload `rag_quality.json`
4. Select Prometheus datasource

---

## Alertmanager Configuration

Add to `monitoring/prometheus/prometheus.yml`:

```yaml
rule_files:
  - "rag_alerts.yml"
```

Create `monitoring/prometheus/rag_alerts.yml`:

```yaml
groups:
  - name: rag_quality
    rules:
      - alert: LowRetrievalScore
        expr: rag_retrieval_scores_avg{time_window="24h"} < 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low RAG retrieval score detected"

      - alert: HighAbstainRate
        expr: rag_abstain_rate_percent > 20
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High ABSTAIN rate detected"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(rag_query_latency_milliseconds_bucket[5m])) > 5000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High RAG query latency"

      - alert: LowCacheHitRate
        expr: rag_cache_hit_rate_percent < 50
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
```

---

## Metrics Retention

- **In-Memory:** 50,000 records (configurable via `MAX_RECORDS`)
- **Prometheus:** 30 days (configurable in `prometheus.yml`)
- **Grafana:** Dashboards persist until deleted

---

## Dashboard Access

| Environment | URL                                                    |
| ----------- | ------------------------------------------------------ |
| Local       | http://localhost:3000/d/rag-quality-monitoring         |
| Production  | https://grafana.nuzantara.com/d/rag-quality-monitoring |

---

## Troubleshooting

### Metrics not appearing

1. Check Prometheus is scraping: `http://localhost:9090/targets`
2. Verify metrics endpoint: `http://localhost:8000/metrics`
3. Look for `rag_*` metrics in Prometheus

### Dashboard empty

1. Ensure queries are being processed
2. Check time range selector in Grafana
3. Verify datasource is selected

### High memory usage

- Reduce `MAX_RECORDS` in `monitoring.py`
- Lower Prometheus retention
- Enable metric aggregation

---

## Future Enhancements

- [ ] Persistent storage (PostgreSQL/TimescaleDB)
- [ ] Real-time WebSocket updates
- [ ] A/B testing framework integration
- [ ] Automated anomaly detection
- [ ] Custom alert channels (Slack, PagerDuty)
- [ ] Query drill-down capabilities
