# 🚀 Monitoring Deploy Guide

**Data**: 2025-12-07
**Scopo**: Guida completa per deploy di Prometheus e Alertmanager

---

## 📋 PREREQUISITI

- Docker e Docker Compose installati
- Backend FastAPI in esecuzione (per test endpoint)
- Porte disponibili: 9090 (Prometheus), 9093 (Alertmanager), 7979 (JSON Exporter)

---

## 🚀 DEPLOY RAPIDO

### 1. Deploy Monitoring Stack

```bash
# Deploy completo
./scripts/deploy_monitoring.sh local

# Oppure manualmente
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Verifica Deploy

```bash
# Verifica che tutto funzioni
./scripts/verify_monitoring.sh

# Oppure manualmente
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:9093/-/healthy  # Alertmanager
curl http://localhost:7979/            # JSON Exporter
```

### 3. Test Endpoint Metrics

```bash
# Test endpoint backend
./scripts/test_qdrant_metrics_endpoint.sh http://localhost:8000
```

---

## 📊 ACCESSO SERVIZI

### Prometheus
- **URL**: http://localhost:9090
- **API**: http://localhost:9090/api/v1
- **Targets**: http://localhost:9090/targets
- **Alerts**: http://localhost:9090/alerts

### Alertmanager
- **URL**: http://localhost:9093
- **API**: http://localhost:9093/api/v2
- **Alerts**: http://localhost:9093/#/alerts
- **Silences**: http://localhost:9093/#/silences

### JSON Exporter
- **URL**: http://localhost:7979
- **Probe**: http://localhost:7979/probe?module=qdrant_metrics&target=http://host.docker.internal:8000

---

## 🔧 CONFIGURAZIONE

### Prometheus

**File**: `config/prometheus/prometheus.yml`

**Scraping Configurato**:
- Backend FastAPI (`/metrics`)
- Qdrant metrics endpoint (`/health/metrics/qdrant`)
- Qdrant server nativo

**Alerting Rules**: `config/prometheus/alerts.yml`

### Alertmanager

**File**: `config/alertmanager/alertmanager.yml`

**Configurazione**:
- Routing per severità (critical, warning, info)
- Webhook receivers configurati
- Inhibition rules per evitare alert duplicati

**Customizzazione**:
1. Modifica `config/alertmanager/alertmanager.yml`
2. Aggiungi webhook URL o email config
3. Riavvia: `docker-compose -f docker-compose.monitoring.yml restart alertmanager`

---

## 🧪 VERIFICA FUNZIONAMENTO

### 1. Verifica Prometheus Scraping

```bash
# Lista targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Verifica metrics disponibili
curl 'http://localhost:9090/api/v1/label/__name__/values' | jq '.[] | select(startswith("qdrant"))'
```

### 2. Verifica Alerting Rules

```bash
# Lista regole caricate
curl http://localhost:9090/api/v1/rules | jq '.data.groups[] | {name: .name, rules: .rules | length}'

# Verifica alert attivi
curl http://localhost:9093/api/v2/alerts | jq 'length'
```

### 3. Test Alert

```bash
# Trigger test alert (se hai alertmanager configurato)
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning",
      "component": "qdrant"
    },
    "annotations": {
      "summary": "Test alert",
      "description": "This is a test alert"
    }
  }]'
```

---

## 🔔 CONFIGURAZIONE NOTIFICHE

### Webhook

Modifica `config/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'critical-alerts'
    webhook_configs:
      - url: 'https://your-webhook-url/critical'
        send_resolved: true
```

### Email

```yaml
receivers:
  - name: 'critical-alerts'
    email_configs:
      - to: 'team@nuzantara.com'
        from: 'alerts@nuzantara.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@nuzantara.com'
        auth_password: 'your-password'
```

### Slack

```yaml
receivers:
  - name: 'critical-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts-critical'
        title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
```

---

## 🐛 TROUBLESHOOTING

### Prometheus non scrapa

1. Verifica targets:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

2. Verifica logs:
   ```bash
   docker logs nuzantara-prometheus
   ```

3. Verifica configurazione:
   ```bash
   docker exec nuzantara-prometheus promtool check config /etc/prometheus/prometheus.yml
   ```

### Alertmanager non riceve alert

1. Verifica connessione Prometheus → Alertmanager:
   ```bash
   curl http://localhost:9090/api/v1/alertmanagers
   ```

2. Verifica configurazione Alertmanager:
   ```bash
   docker exec nuzantara-alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
   ```

3. Verifica logs:
   ```bash
   docker logs nuzantara-alertmanager
   ```

### JSON Exporter non funziona

1. Verifica configurazione:
   ```bash
   docker logs nuzantara-json-exporter
   ```

2. Test probe manualmente:
   ```bash
   curl "http://localhost:7979/probe?module=qdrant_metrics&target=http://host.docker.internal:8000"
   ```

3. Verifica che backend sia raggiungibile dal container:
   ```bash
   docker exec nuzantara-json-exporter ping -c 1 host.docker.internal
   ```

---

## 📈 PRODUZIONE

### Deploy in Produzione

1. **Aggiorna configurazione**:
   - Modifica `docker-compose.monitoring.yml` per produzione
   - Aggiorna URL backend in `prometheus.yml`
   - Configura notifiche in `alertmanager.yml`

2. **Deploy**:
   ```bash
   ./scripts/deploy_monitoring.sh production
   ```

3. **Verifica**:
   ```bash
   ./scripts/verify_monitoring.sh
   ```

### Security

- Usa HTTPS per Prometheus/Alertmanager in produzione
- Configura autenticazione
- Limita accesso alle porte
- Usa secrets per password/token

### Scaling

- Prometheus può gestire milioni di metrics
- Per alta disponibilità, usa Prometheus HA setup
- Considera Thanos per long-term storage

---

## 📝 MAINTENANCE

### Backup

```bash
# Backup Prometheus data
docker exec nuzantara-prometheus tar czf /tmp/prometheus-backup.tar.gz /prometheus

# Backup Alertmanager data
docker exec nuzantara-alertmanager tar czf /tmp/alertmanager-backup.tar.gz /alertmanager
```

### Update

```bash
# Pull nuove immagini
docker-compose -f docker-compose.monitoring.yml pull

# Restart con nuove immagini
docker-compose -f docker-compose.monitoring.yml up -d
```

### Logs

```bash
# Prometheus logs
docker logs -f nuzantara-prometheus

# Alertmanager logs
docker logs -f nuzantara-alertmanager

# JSON Exporter logs
docker logs -f nuzantara-json-exporter
```

---

## 🔗 RIFERIMENTI

- **Docker Compose**: `docker-compose.monitoring.yml`
- **Prometheus Config**: `config/prometheus/prometheus.yml`
- **Alerting Rules**: `config/prometheus/alerts.yml`
- **Alertmanager Config**: `config/alertmanager/alertmanager.yml`
- **Deploy Script**: `scripts/deploy_monitoring.sh`
- **Verify Script**: `scripts/verify_monitoring.sh`

---

**Status**: ✅ Ready for Deploy
**Next Steps**: Deploy in produzione e configurare notifiche


















