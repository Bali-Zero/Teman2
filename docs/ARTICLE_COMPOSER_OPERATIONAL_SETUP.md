# Article Composer - Operational Setup Guide

**Purpose:** Complete operational setup for Article Composer monitoring and alerting  
**Last Updated:** 2026-01-24

---

## 🎯 OVERVIEW

Questa guida completa descrive come configurare tutti i componenti operativi per Article Composer:

1. Test manuale
2. Prometheus alerting
3. Grafana dashboard
4. Alertmanager notifications

---

## ✅ STEP 1: Test Manuale Endpoint

### Prerequisiti

```bash
# Ottenere ADMIN_API_KEY
fly secrets list -a nuzantara-rag | grep ADMIN_API_KEY

# Esportare variabile
export ADMIN_API_KEY=your_key_here
```

### Eseguire Test

```bash
cd /Users/antonellosiano/Projects/nuzantara
./scripts/test_article_composer_endpoint.sh
```

### Output Atteso

```
🧪 Test Manuale Article Composer Endpoint
==========================================

✅ API Key fornita: sk-ant-api...
1️⃣ Test Status Endpoint...
✅ Status endpoint OK
{
  "configured": true,
  "api_key_set": true,
  "model": "claude-sonnet-4-20250514",
  ...
}

2️⃣ Test Compose Endpoint...
✅ Compose endpoint OK
{
  "success": true,
  "article": {...},
  "cached": false,
  ...
}

3️⃣ Test Rate Limiting...
✅ Richiesta 1: OK
...
⚠️  Richiesta 11: Rate limited (429)
✅ Rate limiting funziona!

4️⃣ Test Caching...
✅ Cache funziona! Seconda richiesta è cached
```

### Troubleshooting

**Se il test fallisce:**

1. Verificare che `ADMIN_API_KEY` sia corretto
2. Verificare che l'app sia raggiungibile: `curl https://nuzantara-rag.fly.dev/health`
3. Verificare logs: `fly logs -a nuzantara-rag | grep article_composer`

---

## ✅ STEP 2: Configurare Prometheus con Regole Alert

### File di Configurazione

**File:** `config/prometheus/article_composer_alerts.yml`

### Setup Prometheus

#### Opzione 1: Prometheus Standalone

1. **Copiare configurazione:**

   ```bash
   cp config/prometheus/prometheus.yml.example prometheus.yml
   ```

2. **Modificare `prometheus.yml`:**

   ```yaml
   rule_files:
     - 'config/prometheus/article_composer_alerts.yml'

   scrape_configs:
     - job_name: 'nuzantara-rag'
       scheme: https
       static_configs:
         - targets: ['nuzantara-rag.fly.dev']
       metrics_path: '/metrics'
   ```

3. **Verificare syntax:**

   ```bash
   promtool check rules config/prometheus/article_composer_alerts.yml
   promtool check config prometheus.yml
   ```

4. **Avviare Prometheus:**
   ```bash
   prometheus --config.file=prometheus.yml
   ```

#### Opzione 2: Prometheus su Kubernetes

1. **Creare ConfigMap:**

   ```bash
   kubectl create configmap prometheus-rules \
     --from-file=article_composer_alerts.yml=config/prometheus/article_composer_alerts.yml
   ```

2. **Aggiungere a Prometheus deployment:**

   ```yaml
   volumes:
     - name: prometheus-rules
       configMap:
         name: prometheus-rules
   volumeMounts:
     - name: prometheus-rules
       mountPath: /etc/prometheus/rules
   ```

3. **Aggiornare prometheus.yml:**
   ```yaml
   rule_files:
     - '/etc/prometheus/rules/article_composer_alerts.yml'
   ```

#### Opzione 3: Prometheus su Docker Compose

```yaml
# docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./config/prometheus/article_composer_alerts.yml:/etc/prometheus/rules/article_composer_alerts.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
```

### Verificare Regole

```bash
# Verificare che Prometheus carichi le regole
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[] | select(.name=="article_composer")'

# Verificare alert attivi
curl http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.component=="article_composer")'
```

---

## ✅ STEP 3: Creare Dashboard Grafana

### Import Dashboard

**File:** `config/grafana/dashboards/article-composer.json`

#### Metodo 1: Via UI (Consigliato)

1. Apri Grafana: `http://grafana:3000`
2. Login con credenziali admin
3. Vai a **Dashboards** → **Import**
4. Clicca **Upload JSON file**
5. Seleziona `config/grafana/dashboards/article-composer.json`
6. Clicca **Load**
7. Seleziona datasource **Prometheus**
8. Clicca **Import**

#### Metodo 2: Via API

```bash
# Ottenere API key da Grafana
# Settings → API Keys → New API Key

curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d @config/grafana/dashboards/article-composer.json
```

#### Metodo 3: Via Provisioning

```yaml
# grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1

providers:
  - name: 'Article Composer'
    orgId: 1
    folder: 'Monitoring'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/dashboards/article-composer.json
```

### Configurare Datasource

1. Vai a **Configuration** → **Data Sources**
2. Clicca **Add data source**
3. Seleziona **Prometheus**
4. URL: `http://prometheus:9090` (o il tuo endpoint)
5. Clicca **Save & Test**

### Verificare Dashboard

1. Apri il dashboard
2. Verifica che i panel mostrino dati
3. Verifica che il time range sia corretto
4. Testa refresh automatico

Vedi `docs/ARTICLE_COMPOSER_GRAFANA_DASHBOARD_SETUP.md` per dettagli.

---

## ✅ STEP 4: Configurare Notifiche Alertmanager

### File di Configurazione

**File:** `config/alertmanager/alertmanager.yml.example`

### Setup Alertmanager

#### Opzione 1: Alertmanager Standalone

1. **Copiare configurazione:**

   ```bash
   cp config/alertmanager/alertmanager.yml.example alertmanager.yml
   ```

2. **Modificare `alertmanager.yml`:**
   - Configurare SMTP per email
   - Configurare Slack webhook
   - Configurare PagerDuty (opzionale)

3. **Verificare configurazione:**

   ```bash
   amtool check-config alertmanager.yml
   ```

4. **Avviare Alertmanager:**
   ```bash
   alertmanager --config.file=alertmanager.yml
   ```

#### Opzione 2: Alertmanager su Kubernetes

```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
data:
  alertmanager.yml: |
    # Copia contenuto da config/alertmanager/alertmanager.yml.example
```

#### Opzione 3: Alertmanager su Docker Compose

```yaml
# docker-compose.yml
services:
  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./config/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
```

### Configurare Slack

1. **Creare Slack App:**
   - Vai a https://api.slack.com/apps
   - Crea nuova app
   - Abilita **Incoming Webhooks**
   - Crea webhook per canale `#alerts-article-composer`

2. **Aggiornare alertmanager.yml:**
   ```yaml
   slack_configs:
     - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
       channel: '#alerts-article-composer'
   ```

### Configurare Email

1. **Configurare SMTP:**

   ```yaml
   global:
     smtp_smarthost: 'smtp.gmail.com:587'
     smtp_from: 'alerts@example.com'
     smtp_auth_username: 'alerts@example.com'
     smtp_auth_password: 'your_password'
   ```

2. **Per Gmail:**
   - Usa "App Password" invece della password normale
   - Abilita "Less secure app access" o usa OAuth2

### Testare Notifiche

```bash
# Simulare alert
curl -X POST http://alertmanager:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[
    {
      "labels": {
        "alertname": "ArticleComposerHighErrorRate",
        "severity": "critical",
        "component": "article_composer"
      },
      "annotations": {
        "summary": "Test alert",
        "description": "This is a test alert"
      }
    }
  ]'
```

### Verificare Notifiche

1. Controllare email/Slack per notifiche
2. Verificare logs Alertmanager:
   ```bash
   docker logs alertmanager
   # o
   kubectl logs alertmanager-0
   ```

---

## 🔍 VERIFICA COMPLETA

### Checklist Finale

- [ ] ✅ Test manuale eseguito con successo
- [ ] ✅ Prometheus configurato e running
- [ ] ✅ Regole alert caricate in Prometheus
- [ ] ✅ Grafana dashboard importato
- [ ] ✅ Datasource Prometheus configurato
- [ ] ✅ Alertmanager configurato e running
- [ ] ✅ Notifiche Slack/Email configurate
- [ ] ✅ Test alert inviato con successo

### Verifica End-to-End

1. **Verificare metriche:**

   ```bash
   curl https://nuzantara-rag.fly.dev/metrics | grep article_compose
   ```

2. **Verificare Prometheus scraping:**

   ```bash
   curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="nuzantara-rag")'
   ```

3. **Verificare alert attivi:**

   ```bash
   curl http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.component=="article_composer")'
   ```

4. **Verificare dashboard:**
   - Apri Grafana dashboard
   - Verifica che i panel mostrino dati
   - Testa refresh

5. **Testare alert:**
   - Simula condizione di alert (es. alto error rate)
   - Verifica che alert si attivi
   - Verifica che notifica arrivi

---

## 📚 DOCUMENTAZIONE COMPLETA

- `ARTICLE_COMPOSER_MONITORING.md` - Monitoring base
- `ARTICLE_COMPOSER_MONITORING_CONTINUOUS.md` - Monitoring continuo
- `ARTICLE_COMPOSER_ALERTING_SETUP.md` - Setup alerting dettagliato
- `ARTICLE_COMPOSER_GRAFANA_DASHBOARD_SETUP.md` - Setup dashboard Grafana

---

## 🚨 TROUBLESHOOTING

### Prometheus Non Scrapa Metriche

1. Verificare che l'endpoint `/metrics` sia accessibile
2. Verificare configurazione scrape in prometheus.yml
3. Verificare che Prometheus possa raggiungere l'app
4. Controllare logs Prometheus

### Alert Non Si Attivano

1. Verificare che le regole siano caricate
2. Verificare che le condizioni siano soddisfatte
3. Verificare che `for` duration sia passata
4. Controllare logs Prometheus

### Notifiche Non Arrivano

1. Verificare configurazione Alertmanager
2. Verificare che Alertmanager possa raggiungere Slack/Email
3. Controllare logs Alertmanager
4. Testare configurazione con amtool

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
