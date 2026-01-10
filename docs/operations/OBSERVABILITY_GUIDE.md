# OBSERVABILITY GUIDE - Nuzantara Platform

**Last Updated:** 2026-01-09
**Maintainer:** AI Dev Team

> Guida completa per DevAI su come usare lo stack di observability per debugging, monitoring e quality control.

---

## Quick Reference

| Servizio | URL Locale | Credenziali | Scopo |
|----------|------------|-------------|-------|
| **Grafana** | http://localhost:3001 | admin / changeme123 | Dashboard visualizzazione |
| **Prometheus** | http://localhost:9090 | - | Metrics storage + query |
| **Alertmanager** | http://localhost:9093 | - | Alert routing |
| **Jaeger** | http://localhost:16686 | - | Distributed tracing |
| **SonarQube** | http://localhost:9000 | admin / admin | Code quality |
| **Qdrant** | http://localhost:6333/dashboard | - | Vector DB inspection |

---

## 1. Avvio Stack

```bash
# Avvia TUTTO (raccomandato per development)
docker compose up -d

# Avvia solo observability
docker compose up prometheus grafana alertmanager jaeger -d

# Verifica stato
docker compose ps
```

**Ordine di startup automatico:**
1. Alertmanager (nessuna dipendenza)
2. Prometheus (dipende da Alertmanager)
3. Grafana (dipende da Prometheus)
4. Jaeger (indipendente)

---

## 2. Grafana Dashboards

### Auto-Provisioning

I dashboard sono caricati **automaticamente** all'avvio di Grafana.
- **Datasources:** Prometheus + Jaeger (pre-configurati)
- **Dashboards:** 6 dashboard in folder "Nuzantara"

### Dashboard Disponibili

| Dashboard | File | Metriche Principali |
|-----------|------|---------------------|
| **RAG Pipeline** | `rag-dashboard.json` | Latency, cache hit rate, tool calls, fallback count |
| **System Health** | `system-health-dashboard.json` | CPU, RAM, uptime, active sessions |
| **Qdrant Health** | `qdrant-health-dashboard.json` | Vector search latency, error rate |
| **Error Tracking** | `error-tracking-dashboard.json` | 4xx/5xx per endpoint, error trends |
| **Security** | `security-dashboard.json` | Failed logins, rate limit hits |
| **Lock Contention** | `lock-contention-dashboard.json` | Memory locks, race conditions |

### Creare Nuovo Dashboard

1. Crea in Grafana UI
2. Esporta come JSON
3. Salva in `config/grafana/dashboards/`
4. Riavvia Grafana: `docker compose restart grafana`

---

## 3. Prometheus Metrics

### Metriche Backend (~50 totali)

**RAG Pipeline:**
```promql
# Latenza totale RAG
histogram_quantile(0.95, rate(zantara_rag_pipeline_duration_seconds_bucket[5m]))

# Tool calls per tipo
sum by (tool_name) (rate(zantara_rag_tool_calls_total[5m]))

# Model fallback events
sum(rate(zantara_rag_fallback_count_total[5m]))
```

**LLM Usage:**
```promql
# Token usage per modello
sum by (model) (rate(zantara_llm_prompt_tokens_total[5m]))

# Costo USD (approssimativo)
sum(rate(zantara_llm_cost_usd_total[5m]))

# Circuit breaker events
sum by (model) (rate(zantara_llm_circuit_breaker_opened_total[5m]))
```

**Lock Contention:**
```promql
# Timeout memory lock
sum by (user_id) (rate(zantara_memory_lock_timeout_total[5m]))

# Contention time
histogram_quantile(0.99, rate(zantara_memory_lock_contention_seconds_bucket[5m]))
```

**Error Handling:**
```promql
# Stream errors
sum(rate(zantara_stream_fatal_error_total[5m]))

# Search failures
sum(rate(zantara_search_failed_total[5m]))

# All models failed
sum(rate(zantara_llm_all_models_failed_total[5m]))
```

### Query Utili

```promql
# Top 10 endpoint più lenti
topk(10, histogram_quantile(0.95, rate(zantara_request_duration_seconds_bucket[5m])))

# Error rate globale
sum(rate(zantara_http_requests_total{status=~"5.."}[5m])) /
sum(rate(zantara_http_requests_total[5m])) * 100

# Cache hit rate
sum(rate(zantara_cache_hits_total[5m])) /
(sum(rate(zantara_cache_hits_total[5m])) + sum(rate(zantara_cache_misses_total[5m]))) * 100
```

---

## 4. Alertmanager

### Alert Attivi

Configurati in `config/prometheus/alerts.yml`:

| Alert | Condizione | Severity |
|-------|------------|----------|
| `CriticalQdrantErrorRate` | Error rate > 5% per 2m | critical |
| `CriticalQdrantSearchLatency` | P95 > 1000ms per 2m | critical |
| `QdrantMetricsEndpointDown` | Endpoint unreachable | critical |
| `HighMemoryLockContention` | Contention > 500ms | warning |
| `LLMAllModelsFailed` | Tutti i modelli falliti | critical |

### Verificare Alert

```bash
# UI
open http://localhost:9093

# CLI - alert attivi
curl -s http://localhost:9093/api/v2/alerts | jq

# CLI - silences attivi
curl -s http://localhost:9093/api/v2/silences | jq
```

### Aggiungere Alert

1. Modifica `config/prometheus/alerts.yml`
2. Reload Prometheus: `curl -X POST http://localhost:9090/-/reload`

---

## 5. Jaeger Tracing

### Cercare Trace

1. Apri http://localhost:16686
2. Seleziona Service: `nuzantara-backend`
3. Cerca per:
   - **Operation:** nome endpoint (es. `/api/agentic-rag/stream`)
   - **Tags:** `user.id`, `error=true`, `http.status_code`
   - **Duration:** min/max latency

### Trace ID nei Log

I trace ID sono inclusi nei log backend:
```
2025-12-31 10:00:00 INFO [trace_id=abc123] Processing query...
```

Per cercare un trace specifico:
```
http://localhost:16686/trace/abc123
```

---

## 6. SonarQube

### Setup Iniziale

1. Avvia: `docker compose up sonarqube -d`
2. Attendi ~2 minuti per startup
3. Accedi: http://localhost:9000 (admin/admin)
4. Cambia password al primo accesso

### Analisi Codice

```bash
# Installa sonar-scanner (una volta)
brew install sonar-scanner

# Esegui analisi
cd apps/backend-rag
sonar-scanner \
  -Dsonar.projectKey=nuzantara-backend \
  -Dsonar.sources=backend \
  -Dsonar.host.url=http://localhost:9000 \
  -Dsonar.token=YOUR_TOKEN
```

### Metriche SonarQube

- **Bugs:** Potenziali errori runtime
- **Vulnerabilities:** Problemi sicurezza
- **Code Smells:** Manutenibilità
- **Coverage:** Test coverage (richiede report pytest)
- **Duplications:** Codice duplicato

---

## 7. Sentinel (Quality Control)

### Esecuzione

```bash
# Dalla root del progetto
./sentinel

# Output salvato in:
# sentinel-results/sentinel-run-YYYYMMDD-HHMMSS.log
```

### Fasi Sentinel

1. **Auto-Healing**
   - Ruff check + fix automatico
   - Ruff format

2. **Testing**
   - Pytest con coverage
   - Report HTML in `htmlcov/`

3. **Health Checks**
   - Qdrant connectivity
   - Database connection

### Enhanced Mode

Richiede setup aggiuntivo:

```bash
# Installa strumenti avanzati
./scripts/setup-deep-analysis.sh

# Include:
# - Semgrep (SAST security scanning)
# - CodeQL (GitHub security analysis)
```

---

## 8. Debugging Workflow

### Scenario: Query RAG lenta

1. **Grafana** - Controlla `RAG Pipeline` dashboard
   - Quale fase è lenta? (embedding, search, reranking, LLM)

2. **Prometheus** - Query specifica
   ```promql
   histogram_quantile(0.95, rate(zantara_rag_vector_search_duration_seconds_bucket[5m]))
   ```

3. **Jaeger** - Trova trace lento
   - Filter: `minDuration > 5s`
   - Analizza waterfall

4. **Logs** - Correlation ID
   ```bash
   fly logs -a nuzantara-rag | grep "trace_id=abc123"
   ```

### Scenario: Alert "CriticalQdrantErrorRate"

1. **Alertmanager** - Verifica dettagli alert
2. **Prometheus** - Query errori
   ```promql
   sum by (error_type) (rate(zantara_qdrant_http_error_total[5m]))
   ```
3. **Qdrant Dashboard** - http://localhost:6333/dashboard
   - Controlla collection health
4. **Fix** - Riavvia se necessario
   ```bash
   docker compose restart qdrant
   ```

---

## 9. File Configuration

| File | Scopo |
|------|-------|
| `docker-compose.yml` | Service definitions |
| `config/prometheus/prometheus.yml` | Prometheus config |
| `config/prometheus/alerts.yml` | Alert rules |
| `config/alertmanager/alertmanager.yml` | Alert routing |
| `config/grafana/provisioning/datasources/` | Auto-configure datasources |
| `config/grafana/provisioning/dashboards/` | Auto-load dashboards |
| `config/grafana/dashboards/*.json` | Dashboard definitions |
| `backend/app/metrics.py` | Prometheus metrics export |

---

## 10. Troubleshooting

### Grafana non mostra dati

```bash
# Verifica Prometheus scraping
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Se target down, verifica backend
curl http://localhost:8080/metrics
```

### Alertmanager non invia notifiche

```bash
# Verifica config
docker exec nuzantara-alertmanager amtool check-config /etc/alertmanager/alertmanager.yml

# Test webhook
curl -X POST http://localhost:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert"}}]'
```

### Jaeger trace incompleti

```bash
# Verifica OTEL collector
docker logs nuzantara-jaeger | grep -i error

# Verifica backend env
docker exec nuzantara-backend env | grep OTEL
```

---

---

## 11. Structured Logging (NEW - Jan 2026)

### Configuration

Logging è configurato automaticamente in `app/setup/logging_config.py`:

```python
from app.setup.logging_config import configure_logging, get_logger

# Automatic at startup in app_factory.py
configure_logging()

# In your module
logger = get_logger(__name__)
```

### Output Formats

**Development** (colored, human-readable):
```
21:37:05 [INFO    ] zantara.backend: Logging configured
    context: {"level": "INFO", "environment": "development"}
```

**Production** (JSON for log aggregation):
```json
{
  "timestamp": "2026-01-09T21:37:05.123Z",
  "level": "INFO",
  "logger": "zantara.backend",
  "message": "Logging configured",
  "service": "nuzantara-backend",
  "environment": "production",
  "source": {"file": "/app/backend/app/setup/logging_config.py", "line": 150},
  "context": {"level": "INFO"}
}
```

### Structured Context

```python
from app.utils.logging_utils import log_success, log_error, log_operation

# With duration and context
log_success(logger, "Query processed", duration_ms=245.5, user="zero@balizero.com")

# With error details
log_error(logger, "Query failed", error=e, query_id="abc123")

# Context manager with automatic timing
with log_operation(logger, "process_query", user_id=123) as ctx:
    result = process_query()
    ctx["result_count"] = len(result)  # Add more context
```

### Log Rotation

- **File:** `./data/zantara_rag.log`
- **Max Size:** 50MB per file
- **Backups:** 5 rotating files
- **Format:** Always JSON in file (for parsing)

### Key Files

| File | Purpose |
|------|---------|
| `app/setup/logging_config.py` | Configure formatters, handlers, rotation |
| `app/utils/logging_utils.py` | Utility functions (log_success, log_error, etc.) |
| `app/setup/app_factory.py` | Calls `configure_logging()` at startup |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `ENVIRONMENT` | development | production = JSON output |

---

**Documentazione correlata:**
- [ALERTS_RUNBOOK.md](ALERTS_RUNBOOK.md) - Runbook per gestire alert
- [LOCK_MONITORING_GUIDE.md](LOCK_MONITORING_GUIDE.md) - Guida race conditions
- [DEBUG_GUIDE.md](DEBUG_GUIDE.md) - Debug endpoints API
