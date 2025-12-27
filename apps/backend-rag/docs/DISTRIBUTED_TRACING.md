# Distributed Tracing con OpenTelemetry e Grafana Cloud

## Panoramica

Il backend RAG utilizza **OpenTelemetry** per il distributed tracing, permettendo di tracciare ogni operazione del pipeline RAG dall'ingresso della query alla risposta finale.

### Architettura

```
                          +------------------+
                          | Grafana Cloud    |
                          | Tempo            |
                          +--------^---------+
                                   |
                                   | OTLP/HTTP
                                   |
+----------------------------------+----------------------------------+
|                         Backend RAG (Fly.io)                        |
|                                                                     |
|  POST /api/agentic-rag/stream                                       |
|  │                                                                  |
|  ├─ [orchestrator.process_query] ─────────────────────────────────┐|
|  │   ├─ [context.load_user] (PostgreSQL)                          ||
|  │   ├─ [cache.semantic_check] (hit/miss)                         ||
|  │   ├─ [entity.extraction]                                       ||
|  │   │                                                            ||
|  │   ├─ [react.loop] ──────────────────────────────────────┐      ||
|  │   │   ├─ [react.step.1]                                 │      ||
|  │   │   │   ├─ [llm.gemini_flash] (model, tokens, latency)│      ||
|  │   │   │   ├─ [tool.parse]                               │      ||
|  │   │   │   └─ [tool.vector_search] ──────────────┐       │      ||
|  │   │   │       ├─ [embedding.generate] (OpenAI)  │       │      ||
|  │   │   │       ├─ [qdrant.search] (collection)   │       │      ||
|  │   │   │       └─ [rerank.zeroentropy] (scores)  │       │      ||
|  │   │   │                                         │       │      ||
|  │   │   └─ [react.final_answer]                   │       │      ||
|  │   │                                             │       │      ||
|  │   └─ [pipeline.response] ───────────────────────┘       │      ||
|  │       ├─ [pipeline.verification]                        │      ||
|  │       └─ [pipeline.format]                              │      ||
|  └─────────────────────────────────────────────────────────┘      ||
+--------------------------------------------------------------------+
```

## Configurazione

### Variabili d'Ambiente

```bash
# Abilita OpenTelemetry
OTEL_ENABLED=true

# Nome del servizio (apparira in Grafana)
OTEL_SERVICE_NAME=nuzantara-backend

# Endpoint Grafana Cloud OTLP
OTEL_EXPORTER_ENDPOINT=https://otlp-gateway-prod-ap-southeast-2.grafana.net/otlp

# Header di autenticazione (Instance ID + API Token)
OTEL_EXPORTER_HEADERS=Authorization=Basic <base64(instance_id:api_token)>
```

### Secrets su Fly.io

```bash
# Impostare i secrets
fly secrets set OTEL_ENABLED=true
fly secrets set OTEL_SERVICE_NAME=nuzantara-backend
fly secrets set OTEL_EXPORTER_ENDPOINT=https://otlp-gateway-prod-ap-southeast-2.grafana.net/otlp
fly secrets set OTEL_EXPORTER_HEADERS="Authorization=Basic <token>"
```

### Dipendenze Python

```txt
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
opentelemetry-instrumentation-fastapi>=0.41b0
opentelemetry-exporter-otlp-proto-http>=1.20.0
```

## Utilizzo delle Utility di Tracing

### File: `backend/app/utils/tracing.py`

#### trace_span() - Context Manager

```python
from app.utils.tracing import trace_span, set_span_attribute, set_span_status

async def some_operation(query: str, user_id: str):
    with trace_span("operation.name", {
        "user_id": user_id,
        "query_length": len(query)
    }):
        try:
            result = await do_work()
            set_span_attribute("result_count", len(result))
            set_span_status("ok")
            return result
        except Exception as e:
            set_span_status("error", str(e))
            raise
```

#### add_span_event() - Eventi

```python
from app.utils.tracing import add_span_event

# Aggiungere un evento con attributi
add_span_event("cache_hit", {"key": cache_key, "ttl": 300})
```

#### set_span_attribute() - Attributi Dinamici

```python
from app.utils.tracing import set_span_attribute

# Durante l'esecuzione, aggiungere attributi
set_span_attribute("model_used", "gemini-2.0-flash-exp")
set_span_attribute("tokens_generated", 1250)
```

#### set_span_status() - Status OK/Error

```python
from app.utils.tracing import set_span_status

try:
    result = await call_external_api()
    set_span_status("ok")
except Exception as e:
    set_span_status("error", str(e))
    raise
```

## Spans Implementati

### Orchestrator (`orchestrator.py`)

| Span Name | Attributi |
|-----------|-----------|
| `orchestrator.process_query` | `user_id`, `query_length`, `session_id`, `has_history`, `route` |
| `context.load_user` | `user_id`, `facts_count` |
| `cache.semantic_check` | `hit`, `similarity_score` |
| `entity.extract` | `entities_count`, `entities` |

### ReAct Loop (`reasoning.py`)

| Span Name | Attributi |
|-----------|-----------|
| `react.loop` | `max_steps`, `tools_available` |
| `react.step.N` | `step_number`, `thought`, `action`, `has_observation` |
| `react.final_answer` | `answer_length` |

### LLM Gateway (`llm_gateway.py`)

| Span Name | Attributi |
|-----------|-----------|
| `llm.send_message` | `model`, `tier`, `prompt_tokens`, `completion_tokens`, `has_tools` |
| `llm.fallback` | `from_model`, `to_model`, `reason` |

### Tools (`tools.py`)

| Span Name | Attributi |
|-----------|-----------|
| `tool.vector_search` | `collection`, `query_length`, `limit`, `results_count`, `top_score` |
| `tool.vision` | `image_size`, `analysis_type` |
| `tool.pricing` | `category`, `item_count` |
| `tool.team` | `query`, `results_count` |

### Qdrant (`qdrant_db.py`)

| Span Name | Attributi |
|-----------|-----------|
| `qdrant.search` | `collection`, `vector_size`, `limit`, `results_count`, `search_type` |
| `qdrant.hybrid_search` | `collection`, `dense_weight`, `sparse_weight` |

### Reranker (`reranker.py`)

| Span Name | Attributi |
|-----------|-----------|
| `rerank.zeroentropy` | `documents_count`, `top_k`, `model`, `top_score`, `latency_ms` |

### Embeddings (`embeddings.py`)

| Span Name | Attributi |
|-----------|-----------|
| `embedding.generate` | `provider`, `model`, `text_length`, `dimensions` |

## Visualizzazione in Grafana Cloud Tempo

### Accesso

1. Vai a [Grafana Cloud](https://grafana.com) → Login
2. Seleziona la tua organizzazione
3. Vai a **Explore** → Seleziona **Tempo** come data source

### Query TraceQL

```traceql
# Tutti i traces del servizio
{ resource.service.name = "nuzantara-backend" }

# Solo errori
{ resource.service.name = "nuzantara-backend" && status = error }

# Traces lenti (>2 secondi)
{ resource.service.name = "nuzantara-backend" } | duration > 2s

# Traces con specifico span
{ resource.service.name = "nuzantara-backend" && name = "react.loop" }
```

### Interpretare il Waterfall

```
nuzantara-backend GET /api/agentic-rag/stream (1.2s)
├── orchestrator.process_query (1.15s)
│   ├── context.load_user (45ms) [user_id=xyz, facts=12]
│   ├── cache.semantic_check (5ms) [hit=false]
│   ├── react.loop (980ms)
│   │   ├── react.step.1 (450ms)
│   │   │   ├── llm.gemini_flash (380ms) [tokens=1250]
│   │   │   └── tool.vector_search (65ms)
│   │   │       ├── embedding.generate (20ms)
│   │   │       ├── qdrant.search (25ms) [hits=5]
│   │   │       └── rerank.zeroentropy (18ms)
│   │   └── react.final_answer (520ms)
│   │       └── llm.gemini_flash (515ms)
│   └── pipeline.response (95ms)
```

## Troubleshooting

### Traces non appaiono in Grafana

1. **Verifica OTEL enabled**:
   ```bash
   fly ssh console -a nuzantara-rag
   python -c "from app.core.config import settings; print(settings.otel_enabled)"
   ```

2. **Verifica endpoint e headers**:
   ```bash
   fly secrets list -a nuzantara-rag | grep OTEL
   ```

3. **Controlla logs di startup**:
   ```bash
   fly logs -a nuzantara-rag | grep -i "opentelemetry\|otel\|tracing"
   ```

### Span mancanti

- Verifica che la funzione abbia il decorator/context manager `trace_span()`
- Controlla che non ci siano eccezioni silenziate nei try/except
- Assicurati che `OTEL_AVAILABLE = True` nel modulo

### Performance Impact

Il tracing ha un overhead minimo (~1-2ms per span). Per disabilitarlo in produzione se necessario:

```bash
fly secrets set OTEL_ENABLED=false
fly deploy --now
```

## Best Practices

1. **Nomi span consistenti**: Usa notazione dot-separated (`service.operation`)
2. **Attributi utili**: Includi sempre `user_id`, `query_length`, result counts
3. **Errori espliciti**: Usa `set_span_status("error", description)` per errori
4. **Evita PII**: Non includere dati sensibili negli attributi
5. **Span granulari**: Crea span per ogni operazione I/O (DB, API, cache)

## Riferimenti

- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Grafana Cloud Tempo](https://grafana.com/docs/tempo/latest/)
- [TraceQL Query Language](https://grafana.com/docs/tempo/latest/traceql/)
