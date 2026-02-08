# Article Composer - Alerting Setup Guide

**Purpose:** Configure Prometheus alerting for Article Composer  
**Last Updated:** 2026-01-24

---

## 📋 OVERVIEW

Questo documento descrive come configurare alerting per Article Composer usando Prometheus e Alertmanager.

---

## 🔔 ALERT RULES

### File di Configurazione

Le regole di alert sono definite in:

```
config/prometheus/article_composer_alerts.yml
```

### Alert Disponibili

#### 1. Critical: High Error Rate

- **Trigger:** Error rate > 10% per 5 minuti
- **Severity:** Critical
- **Action:** Verificare logs e stato API Claude

#### 2. Critical: API Key Missing

- **Trigger:** >50% errori API per 2 minuti
- **Severity:** Critical
- **Action:** Verificare `ANTHROPIC_API_KEY` in Fly.io secrets

#### 3. Warning: Low Cache Hit Rate

- **Trigger:** Cache hit rate < 20% per 15 minuti
- **Severity:** Warning
- **Action:** Verificare connessione Redis o TTL cache

#### 4. Warning: High API Costs

- **Trigger:** Costi > $10/ora per 1 ora
- **Severity:** Warning
- **Action:** Verificare utilizzo e considerare caching

#### 5. Warning: Slow Response Time

- **Trigger:** P95 response time > 10s per 10 minuti
- **Severity:** Warning
- **Action:** Verificare latenza Claude API o abilitare cache

#### 6. Warning: Rate Limit Exceeded

- **Trigger:** Rate limit hit per 1 minuto
- **Severity:** Warning
- **Action:** Considerare aumento limite o ottimizzazione

#### 7. Info: High Request Volume

- **Trigger:** Request rate > 5 req/s per 5 minuti
- **Severity:** Info
- **Action:** Monitorare performance

---

## ⚙️ CONFIGURAZIONE PROMETHEUS

### 1. Aggiungere Rules File

**Per Prometheus locale:**

```yaml
# prometheus.yml
rule_files:
  - 'config/prometheus/article_composer_alerts.yml'
```

**Per Prometheus su Fly.io/Kubernetes:**

```yaml
# ConfigMap o Secret
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-rules
data:
  article_composer_alerts.yml: |
    # Copia contenuto da config/prometheus/article_composer_alerts.yml
```

### 2. Verificare Rules

```bash
# Test syntax
promtool check rules config/prometheus/article_composer_alerts.yml

# Verificare che Prometheus carichi le rules
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[] | select(.name=="article_composer")'
```

---

## 📧 CONFIGURAZIONE ALERTMANAGER

### 1. Routing Configuration

```yaml
# alertmanager.yml
route:
  routes:
    - match:
        component: article_composer
      receiver: article-composer-team
      group_by: ['alertname', 'severity']
      group_wait: 10s
      group_interval: 5m
      repeat_interval: 12h

receivers:
  - name: article-composer-team
    email_configs:
      - to: 'devops@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@example.com'
        auth_password: 'password'
        headers:
          Subject: 'Article Composer Alert: {{ .GroupLabels.alertname }}'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts-article-composer'
        title: 'Article Composer Alert'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

### 2. Inibizioni (Inhibitions)

```yaml
# alertmanager.yml
inhibit_rules:
  # Se API key è mancante, non alertare su error rate
  - source_match:
      alertname: ArticleComposerAPIKeyMissing
    target_match:
      alertname: ArticleComposerHighErrorRate
    equal: ['component']
```

---

## 🔍 VERIFICA ALERTING

### 1. Test Alert Manuale

```bash
# Simulare alert usando Prometheus API
curl -X POST http://prometheus:9090/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "labels": {
      "alertname": "ArticleComposerHighErrorRate",
      "severity": "critical",
      "component": "article_composer"
    },
    "annotations": {
      "summary": "Test alert",
      "description": "This is a test alert"
    }
  }'
```

### 2. Verificare Alert Attivi

```bash
# Lista alert attivi
curl http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.component=="article_composer")'

# Alert via Alertmanager
curl http://alertmanager:9093/api/v2/alerts | jq '.[] | select(.labels.component=="article_composer")'
```

### 3. Verificare Notifiche

- Controllare email/Slack per notifiche
- Verificare che Alertmanager stia inviando notifiche
- Controllare logs di Alertmanager per errori

---

## 📊 DASHBOARD GRAFANA

### Query per Alert Status

```promql
# Alert status per Article Composer
ALERTS{alertname=~"ArticleComposer.*"}
```

### Panel per Alert History

```promql
# Alert frequency
count_over_time(ALERTS{alertname=~"ArticleComposer.*"}[1h])
```

---

## 🚨 RUNBOOKS

### High Error Rate

1. **Verificare logs:**

   ```bash
   fly logs -a nuzantara-rag | grep -i "article_composer\|error"
   ```

2. **Verificare Claude API status:**
   - https://status.anthropic.com

3. **Verificare rate limiting:**

   ```bash
   curl https://nuzantara-rag.fly.dev/metrics | grep article_compose_requests_total
   ```

4. **Rollback se necessario:**
   ```bash
   fly releases rollback <previous-release> -a nuzantara-rag
   ```

### Low Cache Hit Rate

1. **Verificare Redis:**

   ```bash
   fly redis status
   # o
   redis-cli ping
   ```

2. **Verificare REDIS_URL:**

   ```bash
   fly secrets list -a nuzantara-rag | grep REDIS
   ```

3. **Verificare cache metrics:**
   ```bash
   curl https://nuzantara-rag.fly.dev/metrics | grep article_cache
   ```

### High API Costs

1. **Analizzare utilizzo:**

   ```promql
   sum by (category) (increase(claude_api_cost_cents[24h]))
   ```

2. **Verificare cache hit rate:**

   ```promql
   rate(article_cache_hits_total[5m]) /
   (rate(article_cache_hits_total[5m]) + rate(article_cache_misses_total[5m]))
   ```

3. **Considerare:**
   - Aumentare cache TTL
   - Abilitare Redis se non configurato
   - Ottimizzare prompt per ridurre token

---

## 📝 BEST PRACTICES

1. **Alert Thresholds:**
   - Iniziare con threshold conservativi
   - Aggiustare basandosi su dati reali
   - Evitare alert fatigue

2. **Grouping:**
   - Raggruppare alert simili
   - Usare `group_by` appropriato
   - Evitare troppi alert separati

3. **Notification Channels:**
   - Usare canali diversi per severità diverse
   - Critical → PagerDuty/SMS
   - Warning → Email/Slack
   - Info → Dashboard only

4. **Runbooks:**
   - Mantenere runbooks aggiornati
   - Includere link nei runbook_url
   - Testare runbooks regolarmente

---

## 🔧 TROUBLESHOOTING

### Alert Non Si Attivano

1. Verificare che Prometheus stia raccogliendo metriche:

   ```bash
   curl http://prometheus:9090/api/v1/query?query=article_compose_requests_total
   ```

2. Verificare syntax rules:

   ```bash
   promtool check rules config/prometheus/article_composer_alerts.yml
   ```

3. Verificare che Prometheus carichi le rules:
   ```bash
   curl http://prometheus:9090/api/v1/rules
   ```

### Alert Non Si Risolvono

1. Verificare `for` duration nelle rules
2. Verificare che le condizioni non siano più vere
3. Verificare che Alertmanager stia processando le risoluzioni

### Notifiche Non Arrivano

1. Verificare configurazione Alertmanager:

   ```bash
   curl http://alertmanager:9093/api/v2/receivers
   ```

2. Verificare logs Alertmanager:

   ```bash
   # Docker
   docker logs alertmanager

   # Kubernetes
   kubectl logs -n monitoring alertmanager-0
   ```

3. Testare configurazione:
   ```bash
   amtool check-config alertmanager.yml
   ```

---

## 📚 RISORSE

- [Prometheus Alerting Documentation](https://prometheus.io/docs/alerting/latest/overview/)
- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)

---

**Last Updated:** 2026-01-24  
**Maintained by:** Backend Team
