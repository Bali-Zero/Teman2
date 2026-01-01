# ALERTS RUNBOOK - Nuzantara Observability

Guida operativa per la gestione degli alert Prometheus/Alertmanager.

---

## Quick Reference

| Alert | Severity | Threshold | Action |
|-------|----------|-----------|--------|
| `CriticalQdrantErrorRate` | CRITICAL | >5% errors/5m | [Jump](#criticalqdranterrorrate) |
| `CriticalQdrantSearchLatency` | CRITICAL | >1000ms/2m | [Jump](#criticalqdrantsearchlatency) |
| `CriticalQdrantUpsertLatency` | CRITICAL | >2000ms/2m | [Jump](#criticalqdrantupsertlatency) |
| `CriticalQdrantRetryRate` | CRITICAL | >0.2 retries/s | [Jump](#criticalqdrantretryrate) |
| `QdrantMetricsEndpointDown` | CRITICAL | up==0 per 1m | [Jump](#qdrantmetricsendpointdown) |
| `HighQdrantErrorRate` | WARNING | >1% errors/5m | [Jump](#highqdranterrorrate) |
| `SlowQdrantSearch` | WARNING | >500ms/5m | [Jump](#slowqdrantsearch) |
| `SlowQdrantUpsert` | WARNING | >1000ms/5m | [Jump](#slowqdrantupsert) |
| `HighQdrantRetryRate` | WARNING | >0.05 retries/s | [Jump](#highqdrantretryrate) |
| `NoQdrantSearchActivity` | WARNING | 0 searches/15m | [Jump](#noqdrantsearchactivity) |
| `QdrantMetricsEndpointSlow` | WARNING | >1s response | [Jump](#qdrantmetricsendpointslow) |
| `LowQdrantUpsertThroughput` | INFO | <0.1 docs/s | [Jump](#lowqdrantupsertthroughput) |

---

## CRITICAL ALERTS

### CriticalQdrantErrorRate

**Condizione:** `rate(qdrant_errors[5m]) > 0.05` per 2 minuti

**Impatto:** Sistema RAG potenzialmente non funzionante. Query utenti falliscono.

**Diagnosi:**
```bash
# 1. Verifica logs backend
./scripts/fly-backend.sh logs | grep -i "qdrant\|error"

# 2. Verifica stato Qdrant Cloud
curl -s https://cloud.qdrant.io/status

# 3. Verifica connettività
./scripts/fly-backend.sh ssh -C "curl -s http://localhost:8080/health/metrics/qdrant"
```

**Azioni:**
1. Verifica Qdrant Cloud dashboard per outages
2. Controlla rate limits API Qdrant
3. Se problema persistente, riavvia backend: `./scripts/fly-backend.sh restart`
4. Escalation: contatta Qdrant support se outage loro

---

### CriticalQdrantSearchLatency

**Condizione:** `qdrant_search_avg_time_ms > 1000` per 2 minuti

**Impatto:** Risposte lente, timeout utenti, UX degradata.

**Diagnosi:**
```bash
# 1. Verifica carico sistema
./scripts/fly-backend.sh ssh -C "top -l 1 | head -10"

# 2. Verifica collection stats
curl -s "$QDRANT_URL/collections" | jq '.result.collections[].name'

# 3. Controlla query patterns in Jaeger
open http://localhost:16686  # cerca traces con latency > 1s
```

**Azioni:**
1. Verifica se c'è un picco di traffico (Grafana → RAG dashboard)
2. Controlla dimensione collezioni Qdrant (potrebbero necessitare ottimizzazione)
3. Verifica se reranker (ZeroEntropy) è lento
4. Considera scaling backend: `./scripts/fly-backend.sh scale count=2`

---

### CriticalQdrantUpsertLatency

**Condizione:** `qdrant_upsert_avg_time_ms > 2000` per 2 minuti

**Impatto:** Ingestion rallentata, nuovi documenti non indicizzati.

**Diagnosi:**
```bash
# 1. Verifica batch size negli upsert
grep -r "upsert" apps/backend-rag/backend/services/ | head -20

# 2. Verifica dimensione payload
./scripts/fly-backend.sh logs | grep -i "upsert\|batch"
```

**Azioni:**
1. Riduci batch size negli upsert (default 100 → 50)
2. Verifica se collection necessita compaction
3. Contatta Qdrant se problema persistente

---

### CriticalQdrantRetryRate

**Condizione:** `rate(qdrant_retry_count[5m]) > 0.2` per 2 minuti

**Impatto:** Network instabile verso Qdrant, possibile outage imminente.

**Diagnosi:**
```bash
# 1. Test connettività
./scripts/fly-backend.sh ssh -C "curl -w '%{time_total}s' -o /dev/null $QDRANT_URL/health"

# 2. Verifica DNS
./scripts/fly-backend.sh ssh -C "nslookup $(echo $QDRANT_URL | sed 's|https://||' | cut -d/ -f1)"
```

**Azioni:**
1. Verifica status page Qdrant Cloud
2. Verifica status page Fly.io (networking Singapore)
3. Se entrambi OK, potrebbe essere rate limiting → contatta Qdrant support

---

### QdrantMetricsEndpointDown

**Condizione:** `up{job="nuzantara-backend"} == 0` per 1 minuto

**Impatto:** Backend completamente down. Nessuna funzionalità disponibile.

**Diagnosi:**
```bash
# 1. Verifica stato macchine
./scripts/fly-backend.sh status

# 2. Verifica logs recenti
./scripts/fly-backend.sh logs --limit 100

# 3. Verifica health
curl -s https://nuzantara-rag.fly.dev/health
```

**Azioni:**
1. Se crashed: `./scripts/fly-backend.sh machines restart`
2. Se OOM: verifica memory usage, considera scale up
3. Se deploy fallito: `./scripts/fly-backend.sh releases` e rollback se necessario
4. Escalation immediata se non risolto in 5 minuti

---

## WARNING ALERTS

### HighQdrantErrorRate

**Condizione:** `rate(qdrant_errors[5m]) > 0.01` per 5 minuti

**Azioni:**
1. Monitora trend in Grafana
2. Verifica logs per pattern errori
3. Se aumenta → prepara escalation a CRITICAL

---

### SlowQdrantSearch

**Condizione:** `qdrant_search_avg_time_ms > 500` per 5 minuti

**Azioni:**
1. Verifica carico sistema
2. Controlla se specifiche collezioni sono lente
3. Considera ottimizzazione query (HNSW parameters)

---

### SlowQdrantUpsert

**Condizione:** `qdrant_upsert_avg_time_ms > 1000` per 5 minuti

**Azioni:**
1. Riduci batch size se > 100
2. Verifica payload size documenti
3. Monitora per escalation

---

### HighQdrantRetryRate

**Condizione:** `rate(qdrant_retry_count[5m]) > 0.05` per 5 minuti

**Azioni:**
1. Monitora stabilità network
2. Verifica timeout configuration
3. Prepara escalation se aumenta

---

### NoQdrantSearchActivity

**Condizione:** `increase(qdrant_search_calls[15m]) == 0` per 15 minuti

**Azioni:**
1. Verifica se frontend è up
2. Verifica se auth funziona
3. Potrebbe essere normale in orari notturni (Asia timezone)

---

### QdrantMetricsEndpointSlow

**Condizione:** `http_request_duration_seconds{endpoint="/health/metrics/qdrant"} > 1` per 2 minuti

**Azioni:**
1. Verifica carico backend
2. Metrics endpoint potrebbe necessitare caching
3. Monitora per pattern

---

## INFO ALERTS

### LowQdrantUpsertThroughput

**Condizione:** `rate(qdrant_upsert_documents_total[10m]) < 0.1` per 10 minuti

**Azioni:**
1. Normale se non c'è ingestion attiva
2. Verifica se pipeline ingestion è bloccata
3. Non richiede azione immediata

---

## Accesso Strumenti

| Tool | URL Locale | Credenziali |
|------|------------|-------------|
| Grafana | http://localhost:3001 | admin / changeme123 |
| Prometheus | http://localhost:9090 | - |
| Alertmanager | http://localhost:9093 | - |
| Jaeger | http://localhost:16686 | - |

## Comandi Utili

```bash
# Avvia stack monitoring
docker compose up -d prometheus grafana alertmanager jaeger

# Verifica alert attivi
curl -s http://localhost:9093/api/v2/alerts | jq '.[] | {alertname: .labels.alertname, state: .status.state}'

# Silenzia alert (1 ora)
curl -X POST http://localhost:9093/api/v2/silences -H "Content-Type: application/json" -d '{
  "matchers": [{"name": "alertname", "value": "SlowQdrantSearch", "isRegex": false}],
  "startsAt": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
  "endsAt": "'"$(date -u -v+1H +%Y-%m-%dT%H:%M:%SZ)"'",
  "createdBy": "operator",
  "comment": "Investigating"
}'

# Query Prometheus per debug
curl -s 'http://localhost:9090/api/v1/query?query=qdrant_search_avg_time_ms' | jq '.data.result'
```

---

## Escalation Path

1. **L1 (Self-service):** Segui runbook sopra
2. **L2 (DevOps):** Se non risolto in 15 min, contatta team
3. **L3 (Vendor):** Qdrant support per issues infrastruttura

---

*Ultimo aggiornamento: 2025-12-29*
*Config files: `config/prometheus/alerts.yml`, `config/alertmanager/alertmanager.yml`*
