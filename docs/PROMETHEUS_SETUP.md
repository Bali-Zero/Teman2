# 🔧 Prometheus Setup per Qdrant Metrics

**Data**: 2025-12-07
**Scopo**: Guida completa per configurare Prometheus per monitoring Qdrant operations

---

## 📋 PREREQUISITI

- Prometheus installato e configurato
- Accesso al backend endpoint `/health/metrics/qdrant`
- (Opzionale) JSON Exporter per convertire JSON in formato Prometheus

---

## 🚀 SETUP RAPIDO

### 1. Configurazione Prometheus Base

Il file `config/prometheus/prometheus.yml` è già configurato con:
- Scraping del backend FastAPI
- Scraping delle Qdrant metrics (JSON endpoint)
- Scraping del Qdrant server nativo

### 2. Setup JSON Exporter (Raccomandato)

Il JSON endpoint restituisce JSON, non formato Prometheus nativo. Per convertirlo:

#### Opzione A: JSON Exporter (Raccomandato)

```bash
# Docker
docker run -d \
  --name json-exporter \
  -p 7979:7979 \
  -v $(pwd)/config/prometheus/json_exporter_config.yml:/config.yml \
  quay.io/prometheuscommunity/json-exporter:latest \
  --config.file=/config.yml

# Verifica
curl http://localhost:7979/probe?module=qdrant_metrics&target=http://host.docker.internal:8000
```

#### Opzione B: Custom Exporter Script

Crea uno script Python che converte JSON in Prometheus format:

```python
# scripts/prometheus_qdrant_exporter.py
from prometheus_client import Gauge, Counter, start_http_server
import requests
import time

# Metrics
search_calls = Gauge('qdrant_search_calls', 'Total search calls')
search_avg_time = Gauge('qdrant_search_avg_time_ms', 'Average search latency ms')
# ... altre metrics

def collect_metrics():
    response = requests.get('http://localhost:8000/health/metrics/qdrant')
    data = response.json()['metrics']

    search_calls.set(data['search_calls'])
    search_avg_time.set(data['search_avg_time_ms'])
    # ... aggiorna altre metrics

if __name__ == '__main__':
    start_http_server(7979)
    while True:
        collect_metrics()
        time.sleep(30)
```

### 3. Aggiorna Prometheus Config

Se usi JSON Exporter, aggiungi al `prometheus.yml`:

```yaml
scrape_configs:
  # ... altre configs ...

  - job_name: 'json-exporter-qdrant'
    scrape_interval: 30s
    metrics_path: '/probe'
    params:
      module: ['qdrant_metrics']
      target: ['http://host.docker.internal:8000']
    static_configs:
      - targets: ['json-exporter:7979']
```

### 4. Configura Alerting

Il file `config/prometheus/alerts.yml` contiene tutte le regole di alerting.

Aggiungi al `prometheus.yml`:

```yaml
rule_files:
  - 'alerts.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

---

## 🧪 VERIFICA SETUP

### 1. Test Endpoint Metrics

```bash
# Test locale
./scripts/test_qdrant_metrics_endpoint.sh http://localhost:8000

# Test produzione
./scripts/test_qdrant_metrics_endpoint.sh https://your-domain.com
```

### 2. Verifica Prometheus Scraping

```bash
# Query Prometheus per verificare che le metrics siano disponibili
curl 'http://localhost:9090/api/v1/query?query=qdrant_search_calls'
```

### 3. Verifica Alerting Rules

```bash
# Verifica che le regole siano caricate
curl 'http://localhost:9090/api/v1/rules'
```

---

## 📊 QUERIES UTILI

### Verifica Metrics Disponibili

```promql
# Lista tutte le metrics Qdrant
{__name__=~"qdrant_.*"}

# Search calls total
qdrant_search_calls

# Search average latency
qdrant_search_avg_time_ms

# Upsert throughput
rate(qdrant_upsert_documents_total[5m])

# Error rate
rate(qdrant_errors[5m]) / (rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m]))
```

---

## 🔔 ALERTING SETUP

### Alertmanager Configuration

Crea `config/alertmanager/alertmanager.yml`:

```yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://your-webhook-url/alert'
        send_resolved: true
    # Oppure email
    # email_configs:
    #   - to: 'team@example.com'
    #     from: 'alerts@example.com'
    #     smarthost: 'smtp.example.com:587'
```

### Test Alert

```bash
# Trigger test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning"
    }
  }]'
```

---

## 📈 GRAFANA DASHBOARD

### Import Dashboard

1. Crea dashboard in Grafana
2. Importa queries da `docs/QDRANT_BASELINE_METRICS.md`
3. Configura panels come descritto nella sezione "Dashboard Panels"

### Dashboard JSON (Esempio)

```json
{
  "dashboard": {
    "title": "Qdrant Operations",
    "panels": [
      {
        "title": "Search Latency",
        "targets": [{
          "expr": "qdrant_search_avg_time_ms"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(qdrant_errors[5m]) / (rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m]))"
        }]
      }
    ]
  }
}
```

---

## 🐛 TROUBLESHOOTING

### Metrics Non Appaiono

1. Verifica endpoint risponde:
   ```bash
   curl http://localhost:8000/health/metrics/qdrant
   ```

2. Verifica Prometheus sta scraping:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

3. Verifica JSON Exporter (se usato):
   ```bash
   curl http://localhost:7979/probe?module=qdrant_metrics&target=http://host.docker.internal:8000
   ```

### Alerting Non Funziona

1. Verifica regole caricate:
   ```bash
   curl http://localhost:9090/api/v1/rules
   ```

2. Verifica Alertmanager connesso:
   ```bash
   curl http://localhost:9090/api/v1/alertmanagers
   ```

3. Verifica log Prometheus per errori

---

## 📝 NOTE

- **Scrape Interval**: 30s è raccomandato per Qdrant metrics (non troppo frequente)
- **Retention**: Configura retention policy appropriata (es. 30 giorni)
- **Storage**: Assicurati storage sufficiente per metrics
- **Network**: Verifica che Prometheus possa raggiungere il backend

---

## 🔗 RIFERIMENTI

- **Prometheus Docs**: https://prometheus.io/docs/
- **JSON Exporter**: Prometheus Community JSON Exporter (search online for latest version)
- **Alerting Rules**: `config/prometheus/alerts.yml`
- **Baseline Metrics**: `docs/QDRANT_BASELINE_METRICS.md`

---

**Status**: ✅ Configurazione completa
**Next Steps**: Deploy in produzione e verificare scraping


















