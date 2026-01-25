# Article Composer - Monitoring & Alerting Guide

**Purpose:** Monitor Article Composer performance, costs, and health  
**Last Updated:** 2026-01-24

---

## 📊 PROMETHEUS METRICS

### Available Metrics

#### Request Metrics

```promql
# Total compose requests by status and category
article_compose_requests_total{status="success", category="business"}

# Compose duration histogram
article_compose_duration_seconds

# Total publish requests
article_publish_requests_total{status="success", has_cover_image="true"}
```

#### Cache Metrics

```promql
# Cache hits
article_cache_hits_total{operation="compose"}

# Cache misses
article_cache_misses_total{operation="compose"}

# Cache hit rate
rate(article_cache_hits_total[5m]) /
(rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))
```

#### Cost Metrics

```promql
# Claude API cost per article (cents)
claude_api_cost_cents

# Total cost (daily)
sum(increase(claude_api_cost_cents[24h])) / 100

# Average cost per article
avg(claude_api_cost_cents)
```

#### Quality Metrics

```promql
# Word count by priority
article_enrichment_word_count{priority="high"}
article_enrichment_word_count{priority="medium"}
article_enrichment_word_count{priority="low"}
```

---

## 📈 GRAFANA DASHBOARDS

### Recommended Panels

#### 1. Request Rate & Success Rate

```promql
# Success rate (last 5min)
rate(article_compose_requests_total{status="success"}[5m]) /
rate(article_compose_requests_total[5m])

# Request rate by category
rate(article_compose_requests_total[5m]) by (category)
```

#### 2. Performance

```promql
# 95th percentile duration
histogram_quantile(0.95, article_compose_duration_seconds)

# Average duration
avg(article_compose_duration_seconds)

# Cache hit rate
rate(article_cache_hits_total[5m]) /
(rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))
```

#### 3. Costs

```promql
# Daily cost
sum(increase(claude_api_cost_cents[24h])) / 100

# Cost per article (average)
avg(claude_api_cost_cents)

# Cost trend (7 days)
sum(increase(claude_api_cost_cents[7d])) / 100
```

#### 4. Error Rate

```promql
# Error rate
rate(article_compose_requests_total{status=~"error|api_error|json_error"}[5m]) /
rate(article_compose_requests_total[5m])

# Errors by type
rate(article_compose_requests_total{status="api_error"}[5m])
rate(article_compose_requests_total{status="json_error"}[5m])
rate(article_compose_requests_total{status="error"}[5m])
```

---

## 🔔 ALERTING RULES

### Critical Alerts

#### 1. High Error Rate

```yaml
alert: ArticleComposerHighErrorRate
expr: |
  rate(article_compose_requests_total{status=~"error|api_error|json_error"}[5m]) / 
  rate(article_compose_requests_total[5m]) > 0.1
for: 5m
labels:
  severity: critical
annotations:
  summary: 'Article Composer error rate > 10%'
  description: 'Error rate is {{ $value | humanizePercentage }}'
```

#### 2. API Key Missing

```yaml
alert: ArticleComposerAPIKeyMissing
expr: |
  up{job="nuzantara-rag"} == 1 AND
  article_compose_requests_total{status="error"} > 0
for: 1m
labels:
  severity: critical
annotations:
  summary: 'Article Composer API key may be missing'
```

#### 3. Circuit Breaker Open

```yaml
# If circuit breaker metric exists
alert: ArticleComposerCircuitBreakerOpen
expr: |
  claude_circuit_breaker_state == 1  # OPEN state
for: 2m
labels:
  severity: warning
annotations:
  summary: 'Claude API circuit breaker is OPEN'
```

### Warning Alerts

#### 4. Low Cache Hit Rate

```yaml
alert: ArticleComposerLowCacheHitRate
expr: |
  rate(article_cache_hits_total[5m]) / 
  (rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m])) < 0.2
for: 15m
labels:
  severity: warning
annotations:
  summary: 'Cache hit rate < 20%'
```

#### 5. High API Costs

```yaml
alert: ArticleComposerHighCosts
expr: |
  sum(increase(claude_api_cost_cents[1h])) / 100 > 10
for: 1h
labels:
  severity: warning
annotations:
  summary: 'API costs > $10/hour'
  description: 'Current cost: ${{ $value }}'
```

#### 6. Slow Response Time

```yaml
alert: ArticleComposerSlowResponse
expr: |
  histogram_quantile(0.95, article_compose_duration_seconds) > 10
for: 10m
labels:
  severity: warning
annotations:
  summary: '95th percentile response time > 10s'
```

---

## 📋 MONITORING CHECKLIST

### Daily Checks

- [ ] Review error rate (should be < 5%)
- [ ] Check cache hit rate (should be > 30% after warmup)
- [ ] Monitor API costs (should be < $50/day)
- [ ] Review slow requests (> 10s)

### Weekly Reviews

- [ ] Analyze cost trends
- [ ] Review error patterns
- [ ] Check cache effectiveness
- [ ] Review performance metrics
- [ ] Update alerting thresholds if needed

### Monthly Reviews

- [ ] Cost optimization opportunities
- [ ] Performance improvements
- [ ] Cache TTL adjustments
- [ ] Rate limit adjustments
- [ ] Circuit breaker tuning

---

## 🔍 DEBUGGING QUERIES

### Find Failed Requests

```promql
# Recent errors
increase(article_compose_requests_total{status=~"error|api_error|json_error"}[1h])

# Errors by category
sum by (category) (article_compose_requests_total{status="error"})
```

### Analyze Cache Performance

```promql
# Cache hit/miss ratio
sum(rate(article_cache_hits_total[5m])) /
sum(rate(article_cache_misses_total[5m]))

# Cache effectiveness by operation
rate(article_cache_hits_total[5m]) by (operation)
```

### Cost Analysis

```promql
# Cost per category
sum by (category) (claude_api_cost_cents)

# Cost trend
sum(increase(claude_api_cost_cents[7d])) / 100

# Average cost per article
avg(claude_api_cost_cents)
```

### Performance Analysis

```promql
# P50, P95, P99 durations
histogram_quantile(0.50, article_compose_duration_seconds)
histogram_quantile(0.95, article_compose_duration_seconds)
histogram_quantile(0.99, article_compose_duration_seconds)

# Duration by category
histogram_quantile(0.95, article_compose_duration_seconds) by (category)
```

---

## 📊 DASHBOARD JSON

### Example Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Article Composer",
    "panels": [
      {
        "title": "Success Rate",
        "targets": [
          {
            "expr": "rate(article_compose_requests_total{status=\"success\"}[5m]) / rate(article_compose_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "rate(article_cache_hits_total[5m]) / (rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))"
          }
        ]
      },
      {
        "title": "Daily Cost",
        "targets": [
          {
            "expr": "sum(increase(claude_api_cost_cents[24h])) / 100"
          }
        ]
      },
      {
        "title": "Response Time (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, article_compose_duration_seconds)"
          }
        ]
      }
    ]
  }
}
```

---

## 🚨 INCIDENT RESPONSE

### High Error Rate

1. Check logs: `fly logs -a nuzantara-rag | grep -i error`
2. Verify API key: `fly secrets list -a nuzantara-rag | grep ANTHROPIC`
3. Check Claude API status: https://status.anthropic.com
4. Review recent changes
5. Check circuit breaker state

### High Costs

1. Check cache hit rate (should be > 30%)
2. Review request volume
3. Check for duplicate requests
4. Verify cache is working
5. Consider increasing cache TTL

### Slow Performance

1. Check response time percentiles
2. Review cache hit rate
3. Check Claude API latency
4. Review recent code changes
5. Check system resources

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
