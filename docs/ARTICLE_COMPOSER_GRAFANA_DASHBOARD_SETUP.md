# Article Composer - Grafana Dashboard Setup

**Purpose:** Import and configure Grafana dashboard for Article Composer  
**Last Updated:** 2026-01-24

---

## 📊 OVERVIEW

Questa guida descrive come importare e configurare il dashboard Grafana per Article Composer.

---

## 🚀 QUICK START

### 1. Import Dashboard

**Metodo 1: Via UI**

1. Apri Grafana
2. Vai a **Dashboards** → **Import**
3. Clicca **Upload JSON file**
4. Seleziona `config/grafana/dashboards/article-composer.json`
5. Clicca **Load**
6. Seleziona il datasource Prometheus
7. Clicca **Import**

**Metodo 2: Via API**

```bash
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d @config/grafana/dashboards/article-composer.json
```

**Metodo 3: Via Provisioning**

```yaml
# grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1

providers:
  - name: "Article Composer"
    orgId: 1
    folder: "Monitoring"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/dashboards/article-composer.json
```

---

## 📋 DASHBOARD PANELS

### Panel 1: Success Rate

- **Type:** Stat
- **Query:** Success rate (last 5min)
- **Thresholds:**
  - Red: < 95%
  - Yellow: 95-98%
  - Green: > 98%

### Panel 2: Request Rate

- **Type:** Stat
- **Query:** Requests per second
- **Unit:** reqps

### Panel 3: Error Rate

- **Type:** Stat
- **Query:** Error rate (last 5min)
- **Thresholds:**
  - Green: < 5%
  - Yellow: 5-10%
  - Red: > 10%

### Panel 4: Cache Hit Rate

- **Type:** Stat
- **Query:** Cache hit rate
- **Thresholds:**
  - Red: < 20%
  - Yellow: 20-30%
  - Green: > 30%

### Panel 5: Response Time

- **Type:** Time Series
- **Query:** P50, P95, P99 percentiles
- **Unit:** seconds

### Panel 6: Daily Cost

- **Type:** Time Series
- **Query:** Daily API costs
- **Unit:** USD

### Panel 7: Requests by Category

- **Type:** Pie Chart
- **Query:** Requests grouped by category

### Panel 8: Requests by Status

- **Type:** Bar Gauge
- **Query:** Requests grouped by status

### Panel 9: Cache Hits vs Misses

- **Type:** Time Series
- **Query:** Cache hits and misses over time

---

## ⚙️ CONFIGURAZIONE

### Datasource Prometheus

Assicurati che il datasource Prometheus sia configurato:

1. Vai a **Configuration** → **Data Sources**
2. Aggiungi **Prometheus**
3. URL: `http://prometheus:9090` (o il tuo endpoint)
4. Clicca **Save & Test**

### Variables (Optional)

Aggiungi variabili per filtrare:

```json
{
  "templating": {
    "list": [
      {
        "name": "category",
        "type": "query",
        "query": "label_values(article_compose_requests_total, category)",
        "current": {
          "value": "All",
          "text": "All"
        },
        "includeAll": true
      }
    ]
  }
}
```

---

## 🔧 CUSTOMIZZAZIONE

### Modificare Refresh Interval

Nel JSON del dashboard:

```json
{
  "refresh": "30s" // Cambia questo valore
}
```

### Aggiungere Nuovi Panel

1. Apri il dashboard in Grafana
2. Clicca **Edit**
3. Clicca **Add Panel**
4. Configura query e visualizzazione
5. Salva il dashboard

### Esportare Dashboard Modificato

1. Vai al dashboard
2. Clicca **Share** → **Export**
3. Scarica JSON
4. Sostituisci `config/grafana/dashboards/article-composer.json`

---

## 📊 QUERY EXAMPLES

### Success Rate by Category

```promql
rate(article_compose_requests_total{status="success", category="$category"}[5m]) /
rate(article_compose_requests_total{category="$category"}[5m])
```

### Cost Trend (7 days)

```promql
sum(increase(claude_api_cost_cents[7d])) / 100
```

### Average Response Time by Category

```promql
rate(article_compose_duration_seconds_sum{category="$category"}[5m]) /
rate(article_compose_duration_seconds_count{category="$category"}[5m])
```

---

## 🚨 ALERTING IN GRAFANA

### Creare Alert dal Dashboard

1. Apri il panel (es. Success Rate)
2. Clicca **Edit**
3. Vai a **Alert**
4. Clicca **Create Alert**
5. Configura:
   - Condition: `WHEN last() OF query(A, 5m, now) IS BELOW 0.95`
   - Evaluation: Every 5m, For 5m
   - Notifications: Seleziona canale

### Alert Rules

Vedi `docs/ARTICLE_COMPOSER_ALERTING_SETUP.md` per configurare alert via Prometheus.

---

## 🔍 TROUBLESHOOTING

### Dashboard Non Mostra Dati

1. Verificare che Prometheus stia raccogliendo metriche:

   ```bash
   curl http://prometheus:9090/api/v1/query?query=article_compose_requests_total
   ```

2. Verificare che il datasource sia configurato correttamente

3. Verificare time range nel dashboard

4. Verificare che le query siano corrette

### Panel Mostra "No Data"

1. Verificare che le metriche esistano:

   ```bash
   curl https://nuzantara-rag.fly.dev/metrics | grep article_compose
   ```

2. Verificare che il time range includa dati

3. Verificare che le label nelle query corrispondano

---

## 📚 RISORSE

- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
