# 📊 Monitoring Guide: LLM Module

**Data**: 2025-12-07
**Versione**: Refactored v2.0

---

## 🎯 Metriche da Monitorare

### 1. Performance Metrics

#### Latency
- **Metrica**: Tempo di risposta per `chat_async` e `stream`
- **Target**: < 2s per chat_async, < 100ms first token per stream
- **Alert**: Se > 5s per chat_async o > 500ms first token

**Come Monitorare**:
```python
import time
start = time.time()
result = await client.chat_async(messages)
latency = time.time() - start
logger.info(f"chat_async latency: {latency:.2f}s")
```

#### Connection Pooling Effectiveness
- **Metrica**: Cache hit rate per `_get_cached_model()`
- **Target**: > 80% cache hits per richieste ripetute
- **Alert**: Se cache hit rate < 50%

**Come Monitorare**:
```python
# Aggiungere logging in _get_cached_model
cache_hits = len(ZantaraAIClient._model_cache)
logger.debug(f"Model cache size: {cache_hits}")
```

#### Token Estimation Accuracy
- **Metrica**: Differenza tra token stimati e token reali (quando disponibile)
- **Target**: < 10% errore
- **Alert**: Se errore > 20%

**Come Monitorare**:
```python
estimated = token_estimator.estimate_tokens(text)
# Confrontare con token reali quando disponibili da API response
```

---

### 2. Error Metrics

#### Retry Rate
- **Metrica**: Percentuale di richieste che richiedono retry
- **Target**: < 5% delle richieste
- **Alert**: Se retry rate > 15%

**Come Monitorare**:
```python
# RetryHandler già logga i retry
# Cercare nei log: "Retrying in"
```

#### Error Types
- **Metrica**: Distribuzione errori per tipo
- **Monitorare**:
  - `ConnectionError`: Problemi di rete
  - `TimeoutError`: Timeout API
  - `ValueError`: Input validation errors
  - Altri: Unexpected errors

**Come Monitorare**:
```python
# Errori già loggati con exc_info=True
# Cercare nei log: "❌ Native Gemini Error"
```

#### Safety Block Rate
- **Metrica**: Percentuale di risposte bloccate da safety filters
- **Target**: < 1%
- **Alert**: Se > 5%

**Come Monitorare**:
```python
# Cercare nei log: "Response blocked by safety filters"
```

---

### 3. Cost Metrics

#### Token Usage
- **Metrica**: Token input/output per richiesta
- **Target**: Monitorare trend per identificare anomalie
- **Alert**: Se token usage aumenta > 50% rispetto a baseline

**Come Monitorare**:
```python
tokens = result["tokens"]
logger.info(f"Tokens - Input: {tokens['input']}, Output: {tokens['output']}")
```

#### Cost per Request
- **Metrica**: Costo stimato per richiesta (quando disponibile)
- **Target**: Monitorare trend
- **Alert**: Se costo aumenta > 30% rispetto a baseline

---

### 4. Availability Metrics

#### Service Availability
- **Metrica**: Uptime del servizio LLM
- **Target**: > 99.9%
- **Alert**: Se downtime > 1 minuto

**Come Monitorare**:
```python
is_available = client.is_available()
if not is_available:
    logger.critical("LLM service unavailable")
```

#### Mock Mode Usage
- **Metrica**: Percentuale di richieste in mock mode
- **Target**: 0% in produzione
- **Alert**: Se > 0% in produzione

**Come Monitorare**:
```python
if client.mock_mode:
    logger.warning("⚠️ Running in MOCK MODE - check API key")
```

---

## 🔍 Logging Structure

### Log Levels

#### DEBUG
- Prompt assembly details
- Token estimation details
- Cache operations
- Retry attempts

#### INFO
- Service initialization
- Request start/completion
- Performance metrics

#### WARNING
- Retry attempts
- Fallback usage
- Mock mode activation

#### ERROR
- API errors
- Connection failures
- Validation errors

#### CRITICAL
- Service unavailable
- Missing API key in production

---

## 📈 Dashboard Metrics

### Key Metrics da Tracciare

1. **Request Rate**: Richieste per minuto/ora
2. **Success Rate**: Percentuale richieste riuscite
3. **Average Latency**: Latency media (p50, p95, p99)
4. **Error Rate**: Percentuale errori per tipo
5. **Token Usage**: Token totali per ora/giorno
6. **Cache Hit Rate**: Percentuale cache hits
7. **Retry Rate**: Percentuale richieste con retry

---

## 🚨 Alerting Rules

### Critical Alerts
- Service unavailable in produzione
- Mock mode attivato in produzione
- Error rate > 10% per 5 minuti
- Latency p95 > 10s per 5 minuti

### Warning Alerts
- Retry rate > 15% per 10 minuti
- Cache hit rate < 50% per 30 minuti
- Token usage aumenta > 50% rispetto a baseline

---

## 🔧 Troubleshooting Guide

### Problema: High Latency

**Possibili Cause**:
1. Network issues
2. API rate limiting
3. Model cache non efficace
4. Token estimation lenta

**Azioni**:
1. Verificare log per retry attempts
2. Controllare cache hit rate
3. Verificare network connectivity
4. Considerare aumentare cache size

### Problema: High Error Rate

**Possibili Cause**:
1. API key invalida o scaduta
2. Rate limiting
3. Network issues
4. Input validation errors

**Azioni**:
1. Verificare API key validity
2. Controllare rate limits
3. Verificare error logs per dettagli
4. Controllare input validation errors

### Problema: High Token Usage

**Possibili Cause**:
1. Prompt troppo lunghi
2. Context injection eccessivo
3. Token estimation imprecisa

**Azioni**:
1. Verificare prompt length
2. Controllare context injection
3. Verificare token estimation accuracy

---

## 📝 Log Examples

### Successful Request
```
INFO: ✅ ZantaraAIClient initialized
INFO: 🌊 [ZantaraAI] Starting stream for user user123
DEBUG: ✅ Created new cached model: gemini-2.5-pro:1234567890...
INFO: ✅ [ZantaraAI] Stream completed successfully for user user123
INFO: Tokens - Input: 150, Output: 200
```

### Retry Scenario
```
WARNING: ⚠️ Stream for user user123 failed (attempt 1/3): Connection timeout. Retrying in 2s...
WARNING: ⚠️ Stream for user user123 failed (attempt 2/3): Connection timeout. Retrying in 4s...
INFO: ✅ [ZantaraAI] Stream completed successfully for user user123
```

### Error Scenario
```
ERROR: ❌ Native Gemini Error: 400 API key not valid
CRITICAL: ❌ CRITICAL: No Gemini API key found in PRODUCTION environment
```

---

## 🎯 Performance Targets

### Latency Targets
- **chat_async**: p50 < 1s, p95 < 2s, p99 < 5s
- **stream**: First token < 100ms, p95 < 500ms

### Availability Targets
- **Uptime**: > 99.9%
- **Error Rate**: < 1%
- **Retry Rate**: < 5%

### Cost Targets
- **Token Efficiency**: Monitorare trend, alert se aumenta > 30%

---

## 📊 Monitoring Tools Integration

### Prometheus Metrics (Future)
```python
# Esempio metriche Prometheus da aggiungere
from prometheus_client import Counter, Histogram

llm_requests_total = Counter('llm_requests_total', 'Total LLM requests')
llm_request_duration = Histogram('llm_request_duration_seconds', 'LLM request duration')
llm_errors_total = Counter('llm_errors_total', 'Total LLM errors', ['error_type'])
```

### Grafana Dashboard (Future)
- Request rate over time
- Latency percentiles
- Error rate by type
- Token usage trends
- Cache hit rate

---

**Status**: ✅ **MONITORING READY**


















