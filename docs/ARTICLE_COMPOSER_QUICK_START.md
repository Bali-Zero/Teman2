# Article Composer - Quick Start Guide

**Purpose:** Quick setup guide for Article Composer monitoring and alerting  
**Last Updated:** 2026-01-24

---

## 🚀 QUICK START

### Prerequisiti

- Prometheus installato e running
- Grafana installato e running
- Alertmanager installato (opzionale ma raccomandato)
- Accesso a `nuzantara-rag.fly.dev`

---

## 📋 STEP 1: Test Manuale Endpoint

### Ottenere API Key

```bash
cd apps/backend-rag
fly secrets list -a nuzantara-rag | grep ADMIN_API_KEY
```

### Eseguire Test

```bash
cd /Users/antonellosiano/Desktop/nuzantara
export ADMIN_API_KEY=your_key_here
./scripts/test_article_composer_endpoint.sh
```

### Output Atteso

```
✅ Status endpoint OK
✅ Compose endpoint OK
✅ Rate limiting funziona!
✅ Cache funziona!
```

---

## 📊 STEP 2: Configurare Prometheus

### Opzione A: Script Automatico

```bash
cd /Users/antonellosiano/Desktop/nuzantara
./scripts/setup_prometheus_article_composer.sh
```

### Opzione B: Manuale

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

3. **Verificare:**

   ```bash
   promtool check config prometheus.yml
   promtool check rules config/prometheus/article_composer_alerts.yml
   ```

4. **Avviare Prometheus:**
   ```bash
   prometheus --config.file=prometheus.yml
   ```

### Verificare

```bash
# Verificare che Prometheus stia scraping
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="nuzantara-rag")'

# Verificare che le regole siano caricate
curl http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="article_composer")'
```

---

## 📈 STEP 3: Importare Dashboard Grafana

### Opzione A: Script Automatico

```bash
cd /Users/antonellosiano/Desktop/nuzantara
export GRAFANA_URL=http://localhost:3000
export GRAFANA_USER=admin
export GRAFANA_PASSWORD=admin
./scripts/setup_grafana_dashboard.sh
```

### Opzione B: Manuale

1. **Aprire Grafana:**

   ```
   http://localhost:3000
   ```

2. **Importare Dashboard:**
   - Vai a **Dashboards** → **Import**
   - Clicca **Upload JSON file**
   - Seleziona `config/grafana/dashboards/article-composer.json`
   - Clicca **Load**

3. **Configurare Datasource:**
   - Seleziona datasource **Prometheus**
   - URL: `http://prometheus:9090` (o il tuo endpoint)
   - Clicca **Import**

### Verificare

- Apri il dashboard
- Verifica che i panel mostrino dati
- Testa refresh automatico

---

## 🔔 STEP 4: Configurare Alertmanager

### Opzione A: Script Automatico

```bash
cd /Users/antonellosiano/Desktop/nuzantara
./scripts/setup_alertmanager.sh
```

### Opzione B: Manuale

1. **Copiare configurazione:**

   ```bash
   cp config/alertmanager/alertmanager.yml.example alertmanager.yml
   ```

2. **Configurare Slack:**

   ```yaml
   slack_configs:
     - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
       channel: '#alerts-article-composer'
   ```

3. **Configurare Email:**

   ```yaml
   global:
     smtp_smarthost: 'smtp.gmail.com:587'
     smtp_from: 'alerts@example.com'
     smtp_auth_username: 'alerts@example.com'
     smtp_auth_password: 'your_password'
   ```

4. **Verificare:**

   ```bash
   amtool check-config alertmanager.yml
   ```

5. **Avviare Alertmanager:**
   ```bash
   alertmanager --config.file=alertmanager.yml
   ```

### Testare Notifiche

```bash
curl -X POST http://localhost:9093/api/v2/alerts \
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

---

## ✅ VERIFICA COMPLETA

### Checklist

- [ ] ✅ Test manuale eseguito con successo
- [ ] ✅ Prometheus configurato e running
- [ ] ✅ Regole alert caricate
- [ ] ✅ Grafana dashboard importato
- [ ] ✅ Datasource Prometheus configurato
- [ ] ✅ Alertmanager configurato e running
- [ ] ✅ Notifiche Slack/Email configurate
- [ ] ✅ Test alert inviato con successo

### Verifica End-to-End

1. **Metriche esposte:**

   ```bash
   curl https://nuzantara-rag.fly.dev/metrics | grep article_compose
   ```

2. **Prometheus scraping:**

   ```bash
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="nuzantara-rag")'
   ```

3. **Alert attivi:**

   ```bash
   curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.component=="article_composer")'
   ```

4. **Dashboard funzionante:**
   - Apri Grafana dashboard
   - Verifica che i panel mostrino dati

---

## 🚨 TROUBLESHOOTING

### Test Manuale Fallisce

1. Verificare `ADMIN_API_KEY`:

   ```bash
   fly secrets list -a nuzantara-rag | grep ADMIN_API_KEY
   ```

2. Verificare che l'app sia raggiungibile:

   ```bash
   curl https://nuzantara-rag.fly.dev/health
   ```

3. Verificare logs:
   ```bash
   fly logs -a nuzantara-rag | grep article_composer
   ```

### Prometheus Non Scrapa

1. Verificare configurazione:

   ```bash
   promtool check config prometheus.yml
   ```

2. Verificare che l'endpoint sia accessibile:

   ```bash
   curl https://nuzantara-rag.fly.dev/metrics
   ```

3. Controllare logs Prometheus

### Dashboard Non Mostra Dati

1. Verificare datasource:
   - Configuration → Data Sources → Prometheus → Test

2. Verificare time range nel dashboard

3. Verificare che Prometheus abbia dati:
   ```bash
   curl http://localhost:9090/api/v1/query?query=article_compose_requests_total
   ```

### Alert Non Arrivano

1. Verificare configurazione Alertmanager:

   ```bash
   amtool check-config alertmanager.yml
   ```

2. Verificare che Alertmanager sia connesso a Prometheus

3. Controllare logs Alertmanager

---

## 📚 DOCUMENTAZIONE COMPLETA

- `ARTICLE_COMPOSER_OPERATIONAL_SETUP.md` - Guida operativa completa
- `ARTICLE_COMPOSER_GRAFANA_DASHBOARD_SETUP.md` - Setup dashboard dettagliato
- `ARTICLE_COMPOSER_ALERTING_SETUP.md` - Setup alerting dettagliato
- `ARTICLE_COMPOSER_MONITORING_CONTINUOUS.md` - Monitoring continuo

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
