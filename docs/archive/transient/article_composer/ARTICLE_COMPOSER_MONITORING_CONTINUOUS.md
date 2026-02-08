# Article Composer - Continuous Monitoring Guide

**Purpose:** Setup continuous monitoring for Article Composer  
**Last Updated:** 2026-01-24

---

## 📊 OVERVIEW

Questa guida descrive come monitorare continuamente Article Composer usando Prometheus, Grafana e alerting.

---

## 🔍 METRICHE DA MONITORARE

### 1. Request Metrics

#### Success Rate

```promql
# Success rate (last 5 minutes)
rate(article_compose_requests_total{status="success"}[5m]) /
rate(article_compose_requests_total[5m])
```

**Target:** > 95%

#### Request Rate by Category

```promql
# Requests per second by category
rate(article_compose_requests_total[5m]) by (category)
```

**Target:** Monitorare picchi e pattern

#### Error Rate

```promql
# Error rate
rate(article_compose_requests_total{status=~"error|api_error|json_error"}[5m]) /
rate(article_compose_requests_total[5m])
```

**Target:** < 5%

### 2. Performance Metrics

#### Response Time (P50, P95, P99)

```promql
# P50
histogram_quantile(0.50, article_compose_duration_seconds)

# P95
histogram_quantile(0.95, article_compose_duration_seconds)

# P99
histogram_quantile(0.99, article_compose_duration_seconds)
```

**Target:** P95 < 5s

#### Average Response Time

```promql
# Average duration
rate(article_compose_duration_seconds_sum[5m]) /
rate(article_compose_duration_seconds_count[5m])
```

**Target:** < 3s

### 3. Cache Metrics

#### Cache Hit Rate

```promql
# Cache hit rate
rate(article_cache_hits_total[5m]) /
(rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))
```

**Target:** > 30% (dopo warmup)

#### Cache Effectiveness

```promql
# Cache hits vs misses
sum(rate(article_cache_hits_total[5m])) by (operation)
sum(rate(article_cache_misses_total[5m])) by (operation)
```

**Target:** Hit rate > Miss rate

### 4. Cost Metrics

#### Daily Cost

```promql
# Total cost per day
sum(increase(claude_api_cost_cents[24h])) / 100
```

**Target:** Monitorare trend

#### Cost per Article

```promql
# Average cost per article
avg(claude_api_cost_cents)
```

**Target:** $0.02-0.05 per article

#### Cost by Category

```promql
# Cost breakdown by category
sum by (category) (claude_api_cost_cents)
```

**Target:** Identificare categorie costose

### 5. Quality Metrics

#### Word Count by Priority

```promql
# Average word count by priority
avg(article_enrichment_word_count) by (priority)
```

**Target:** Monitorare qualità output

---

## 📈 GRAFANA DASHBOARD

### Panel 1: Overview

**Query:**

```promql
# Success Rate
rate(article_compose_requests_total{status="success"}[5m]) /
rate(article_compose_requests_total[5m])

# Request Rate
sum(rate(article_compose_requests_total[5m]))

# Error Rate
rate(article_compose_requests_total{status=~"error|api_error|json_error"}[5m]) /
rate(article_compose_requests_total[5m])
```

**Visualization:** Stat panels

### Panel 2: Performance

**Query:**

```promql
# Response Time Percentiles
histogram_quantile(0.50, article_compose_duration_seconds)
histogram_quantile(0.95, article_compose_duration_seconds)
histogram_quantile(0.99, article_compose_duration_seconds)
```

**Visualization:** Time series graph

### Panel 3: Cache Performance

**Query:**

```promql
# Cache Hit Rate
rate(article_cache_hits_total[5m]) /
(rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))

# Cache Hits/Misses
sum(rate(article_cache_hits_total[5m]))
sum(rate(article_cache_misses_total[5m]))
```

**Visualization:** Time series + Stat panels

### Panel 4: Costs

**Query:**

```promql
# Daily Cost
sum(increase(claude_api_cost_cents[24h])) / 100

# Cost Trend (7 days)
sum(increase(claude_api_cost_cents[7d])) / 100
```

**Visualization:** Time series graph

### Panel 5: Request Breakdown

**Query:**

```promql
# Requests by Category
sum(rate(article_compose_requests_total[5m])) by (category)

# Requests by Status
sum(rate(article_compose_requests_total[5m])) by (status)
```

**Visualization:** Pie chart / Bar chart

---

## 🔄 MONITORING SCHEDULE

### Real-time (Every Minute)

- Success rate
- Error rate
- Active alerts

### Short-term (Every 5 Minutes)

- Response time percentiles
- Cache hit rate
- Request rate

### Medium-term (Every Hour)

- Cost trends
- Performance trends
- Error patterns

### Long-term (Daily)

- Daily cost summary
- Performance summary
- Cache effectiveness report

---

## 📊 REPORTING

### Daily Report

**Metrics:**

- Total requests
- Success rate
- Average response time
- Cache hit rate
- Total cost
- Error breakdown

**Format:** Email/Slack summary

### Weekly Report

**Metrics:**

- Weekly trends
- Cost analysis
- Performance improvements
- Cache effectiveness
- Error patterns

**Format:** Detailed report with charts

### Monthly Report

**Metrics:**

- Monthly trends
- Cost optimization opportunities
- Performance benchmarks
- Recommendations

**Format:** Comprehensive report

---

## 🔧 AUTOMATED MONITORING

### Script di Monitoraggio

```bash
#!/bin/bash
# monitor_article_composer.sh

API_URL="https://nuzantara-rag.fly.dev"
PROMETHEUS_URL="http://prometheus:9090"

# Check success rate
SUCCESS_RATE=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=rate(article_compose_requests_total{status=\"success\"}[5m])/rate(article_compose_requests_total[5m])" | jq -r '.data.result[0].value[1]')

if (( $(echo "$SUCCESS_RATE < 0.95" | bc -l) )); then
    echo "ALERT: Success rate below 95%: $SUCCESS_RATE"
    # Send notification
fi

# Check error rate
ERROR_RATE=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=rate(article_compose_requests_total{status=~\"error|api_error|json_error\"}[5m])/rate(article_compose_requests_total[5m])" | jq -r '.data.result[0].value[1]')

if (( $(echo "$ERROR_RATE > 0.05" | bc -l) )); then
    echo "ALERT: Error rate above 5%: $ERROR_RATE"
    # Send notification
fi

# Check cache hit rate
CACHE_HIT_RATE=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=rate(article_cache_hits_total[5m])/(rate(article_cache_hits_total[5m])+rate(article_cache_misses_total[5m]))" | jq -r '.data.result[0].value[1]')

if (( $(echo "$CACHE_HIT_RATE < 0.2" | bc -l) )); then
    echo "WARNING: Cache hit rate below 20%: $CACHE_HIT_RATE"
fi
```

### Cron Job

```bash
# /etc/cron.d/article-composer-monitoring
*/5 * * * * /path/to/monitor_article_composer.sh >> /var/log/article-composer-monitoring.log 2>&1
```

---

## 📱 NOTIFICATIONS

### Channels

1. **Critical Alerts:**
   - PagerDuty / SMS
   - Slack #critical-alerts
   - Email to on-call

2. **Warning Alerts:**
   - Slack #alerts
   - Email to team

3. **Info Alerts:**
   - Dashboard only
   - Weekly summary

### Notification Templates

**Critical Alert:**

```
🚨 CRITICAL: Article Composer {{ .GroupLabels.alertname }}

{{ .CommonAnnotations.description }}

Current Value: {{ .CommonLabels.value }}
Threshold: {{ .CommonLabels.threshold }}

Runbook: {{ .CommonAnnotations.runbook_url }}
```

**Warning Alert:**

```
⚠️ WARNING: Article Composer {{ .GroupLabels.alertname }}

{{ .CommonAnnotations.description }}

View Dashboard: https://grafana.example.com/d/article-composer
```

---

## 🔍 TROUBLESHOOTING

### Metriche Non Appaiono

1. Verificare che Prometheus stia scraping:

   ```bash
   curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="nuzantara-rag")'
   ```

2. Verificare che le metriche siano esposte:

   ```bash
   curl https://nuzantara-rag.fly.dev/metrics | grep article_compose
   ```

3. Verificare configurazione Prometheus:
   ```yaml
   scrape_configs:
     - job_name: 'nuzantara-rag'
       static_configs:
         - targets: ['nuzantara-rag.fly.dev:443']
       scheme: https
   ```

### Dashboard Non Aggiorna

1. Verificare query Prometheus direttamente
2. Verificare time range nel dashboard
3. Verificare che Grafana possa raggiungere Prometheus

---

## 📚 RISORSE

- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Alerting Best Practices](https://prometheus.io/docs/practices/alerting/)

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
