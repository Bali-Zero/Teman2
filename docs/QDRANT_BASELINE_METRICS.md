# 📊 Qdrant Baseline Metrics

**Data**: 2025-12-07
**Scopo**: Definire baseline metrics per monitoring Qdrant operations in produzione

---

## 🎯 BASELINE METRICS

### Search Operations

| Metric | Baseline | Warning | Critical | Note |
|--------|----------|---------|----------|------|
| **Average Latency** | < 100ms | 100-500ms | > 500ms | Tempo medio per operazione search |
| **P95 Latency** | < 200ms | 200-800ms | > 800ms | 95th percentile latency |
| **P99 Latency** | < 500ms | 500-1500ms | > 1500ms | 99th percentile latency |
| **Throughput** | > 100 req/s | 50-100 req/s | < 50 req/s | Richieste per secondo |
| **Error Rate** | < 0.1% | 0.1-1% | > 1% | Percentuale errori su totale |

**Target Performance**:
- ✅ 95% delle search completate in < 200ms
- ✅ 99% delle search completate in < 500ms
- ✅ Error rate < 0.1%

---

### Upsert Operations

| Metric | Baseline | Warning | Critical | Note |
|--------|----------|---------|----------|------|
| **Average Latency** | < 200ms | 200-1000ms | > 1000ms | Tempo medio per operazione upsert |
| **P95 Latency** | < 500ms | 500-2000ms | > 2000ms | 95th percentile latency |
| **P99 Latency** | < 1000ms | 1000-5000ms | > 5000ms | 99th percentile latency |
| **Throughput** | > 50 docs/s | 20-50 docs/s | < 20 docs/s | Documenti per secondo |
| **Batch Size** | 100-500 | 50-100 | < 50 | Documenti per batch |
| **Error Rate** | < 0.1% | 0.1-1% | > 1% | Percentuale errori su totale |

**Target Performance**:
- ✅ 95% delle upsert completate in < 500ms
- ✅ 99% delle upsert completate in < 1000ms
- ✅ Throughput > 50 documenti/secondo
- ✅ Error rate < 0.1%

---

### Retry Operations

| Metric | Baseline | Warning | Critical | Note |
|--------|----------|---------|----------|------|
| **Retry Rate** | < 1% | 1-5% | > 5% | Percentuale operazioni che richiedono retry |
| **Retry Success Rate** | > 80% | 50-80% | < 50% | Percentuale retry che riescono |
| **Average Retries** | < 1.1 | 1.1-1.5 | > 1.5 | Media tentativi per operazione |

**Target Performance**:
- ✅ Retry rate < 1% delle operazioni totali
- ✅ Success rate retry > 80%
- ✅ Media tentativi < 1.1 per operazione

---

### Error Patterns

| Error Type | Baseline | Warning | Critical | Note |
|------------|----------|---------|----------|------|
| **HTTP 5xx Errors** | < 0.01% | 0.01-0.1% | > 0.1% | Server errors |
| **HTTP 4xx Errors** | < 0.1% | 0.1-1% | > 1% | Client errors |
| **Timeout Errors** | < 0.01% | 0.01-0.1% | > 0.1% | Timeout su operazioni |
| **Connection Errors** | < 0.01% | 0.01-0.1% | > 0.1% | Errori di connessione |

**Target Performance**:
- ✅ HTTP 5xx errors < 0.01%
- ✅ Timeout errors < 0.01%
- ✅ Connection errors < 0.01%

---

## 📈 METRICHE CALCOLATE

### Search Performance Score
```
score = (avg_latency_ms < 100 ? 100 : 100 - (avg_latency_ms - 100) / 10)
      * (error_rate < 0.001 ? 1 : 1 - error_rate * 100)
```
- **Target**: > 95
- **Warning**: 80-95
- **Critical**: < 80

### Upsert Efficiency
```
efficiency = (throughput_docs_per_sec / 50)
           * (avg_latency_ms < 200 ? 1 : 200 / avg_latency_ms)
           * (error_rate < 0.001 ? 1 : 1 - error_rate * 100)
```
- **Target**: > 0.9
- **Warning**: 0.7-0.9
- **Critical**: < 0.7

### System Health Score
```
health = (search_score * 0.4) + (upsert_efficiency * 0.4) + (retry_rate < 0.01 ? 20 : 20 - retry_rate * 2000)
```
- **Target**: > 90
- **Warning**: 75-90
- **Critical**: < 75

---

## 🔍 MONITORING QUERIES

### Prometheus Queries

#### Search Latency (P95)
```promql
histogram_quantile(0.95,
  rate(qdrant_search_duration_seconds_bucket[5m])
)
```

#### Search Error Rate
```promql
rate(qdrant_errors{operation="search"}[5m])
/
rate(qdrant_search_calls[5m])
```

#### Upsert Throughput
```promql
rate(qdrant_upsert_documents_total[5m])
```

#### Retry Rate
```promql
rate(qdrant_retry_count[5m])
/
(rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m]))
```

#### System Health Score
```promql
(
  (qdrant_search_avg_time_ms < 100 ? 100 : 100 - (qdrant_search_avg_time_ms - 100) / 10)
  * (rate(qdrant_errors{operation="search"}[5m]) / rate(qdrant_search_calls[5m]) < 0.001 ? 1 : 1 - (rate(qdrant_errors{operation="search"}[5m]) / rate(qdrant_search_calls[5m])) * 100)
  * 0.4
) +
(
  ((rate(qdrant_upsert_documents_total[5m]) / 50) * (qdrant_upsert_avg_time_ms < 200 ? 1 : 200 / qdrant_upsert_avg_time_ms) * (rate(qdrant_errors{operation="upsert"}[5m]) / rate(qdrant_upsert_calls[5m]) < 0.001 ? 1 : 1 - (rate(qdrant_errors{operation="upsert"}[5m]) / rate(qdrant_upsert_calls[5m])) * 100))
  * 0.4
) +
(
  rate(qdrant_retry_count[5m]) / (rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m])) < 0.01 ? 20 : 20 - (rate(qdrant_retry_count[5m]) / (rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m]))) * 2000
)
```

---

## 📊 DASHBOARD PANELS

### Recommended Grafana Panels

1. **Search Latency Over Time**
   - Query: `qdrant_search_avg_time_ms`
   - Visualization: Time series
   - Thresholds: Green (< 100ms), Yellow (100-500ms), Red (> 500ms)

2. **Search Throughput**
   - Query: `rate(qdrant_search_calls[5m])`
   - Visualization: Time series
   - Unit: req/s

3. **Upsert Latency Over Time**
   - Query: `qdrant_upsert_avg_time_ms`
   - Visualization: Time series
   - Thresholds: Green (< 200ms), Yellow (200-1000ms), Red (> 1000ms)

4. **Upsert Throughput**
   - Query: `rate(qdrant_upsert_documents_total[5m])`
   - Visualization: Time series
   - Unit: docs/s

5. **Error Rate**
   - Query: `rate(qdrant_errors[5m]) / (rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m]))`
   - Visualization: Time series
   - Unit: percentage

6. **Retry Rate**
   - Query: `rate(qdrant_retry_count[5m]) / (rate(qdrant_search_calls[5m]) + rate(qdrant_upsert_calls[5m]))`
   - Visualization: Time series
   - Unit: percentage

7. **System Health Score**
   - Query: (vedi sopra)
   - Visualization: Gauge
   - Thresholds: Green (> 90), Yellow (75-90), Red (< 75)

---

## 🎯 ESTABLISHING BASELINE

### Processo

1. **Raccolta Dati (Settimana 1-2)**
   - Monitorare metrics per 1-2 settimane senza alerting
   - Raccogliere dati durante carichi normali e picchi
   - Identificare pattern giornalieri/settimanali

2. **Analisi Dati (Settimana 2-3)**
   - Calcolare percentili (P50, P95, P99)
   - Identificare outliers
   - Stabilire range normali

3. **Definizione Baseline (Settimana 3)**
   - Baseline = P50 durante carico normale
   - Warning = P95 durante carico normale
   - Critical = P99 durante carico normale + 20%

4. **Validazione (Settimana 4)**
   - Applicare baseline con alerting soft
   - Verificare che alerting non sia troppo sensibile
   - Aggiustare threshold se necessario

5. **Produzione (Settimana 5+)**
   - Alerting attivo con baseline stabilita
   - Review settimanale delle metrics
   - Aggiustamento trimestrale dei threshold

---

## 📝 NOTE

### Fattori che Influenzano Baseline

- **Carico Applicazione**: Più richieste = più latenza
- **Dimensione Collection**: Collection più grandi = search più lente
- **Network Latency**: Distanza geografica tra app e Qdrant
- **Qdrant Server Resources**: CPU/Memory disponibili
- **Batch Size**: Batch più grandi = upsert più lente ma più efficienti

### Aggiornamento Baseline

- **Review Trimestrale**: Verificare se baseline è ancora valida
- **Dopo Major Changes**: Ricalcolare dopo upgrade Qdrant o refactoring
- **Scalabilità**: Aggiustare quando si scala orizzontalmente

---

## 🔗 RIFERIMENTI

- **Metrics Endpoint**: `/health/metrics/qdrant`
- **Prometheus Config**: `config/prometheus/prometheus.yml`
- **Alerting Rules**: `config/prometheus/alerts.yml`
- **Testing Results**: `docs/QDRANT_TESTING_RESULTS.md`

---

**Status**: 📊 Baseline da stabilire in produzione
**Next Review**: Dopo 2 settimane di monitoring


















