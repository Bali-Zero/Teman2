# Article Composer - Implementation Plan

**Data:** 2026-01-24  
**Status:** In Progress

---

## 📋 IMPLEMENTAZIONE COMPLETATA

### ✅ Fase 1: Servizi di Supporto Creati

1. **`claude_client.py`** ✅
   - Retry logic con exponential backoff (tenacity)
   - Circuit breaker implementation
   - Connection pooling (singleton client)
   - Structured error handling

2. **`error_handler.py`** ✅
   - Structured error responses (APIError model)
   - Error codes enum
   - Context preservation
   - Specialized handlers per tipo errore

3. **`validators.py`** ✅
   - Advanced input validation
   - Content sanitization
   - Category validation
   - Size limits enforcement

4. **`cache.py`** ✅
   - Redis-based caching
   - Cache key generation
   - TTL management
   - Cache invalidation

5. **`__init__.py`** ✅
   - Package exports
   - Clean API

---

## 🔄 PROSSIMI STEP

### Step 1: Aggiornare `article_composer.py`

Sostituire il file originale con la versione migliorata che include:

1. **Import dei nuovi servizi**

   ```python
   from backend.services.article_composer import (
       cache_service,
       call_claude_with_retry,
       handle_anthropic_error,
       handle_json_error,
       ComposeRequestValidator,
   )
   ```

2. **Rate Limiting**

   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   ```

3. **Dependency Injection**

   ```python
   def get_request_id() -> str:
       return str(uuid.uuid4())
   ```

4. **Aggiornare endpoint `/compose`**
   - Usare `ComposeRequestValidator` invece di `ComposeRequest`
   - Aggiungere `@limiter.limit("10/minute")`
   - Aggiungere `request_id: str = Depends(get_request_id)`
   - Implementare cache check/set
   - Usare `call_claude_with_retry` invece di chiamata diretta
   - Usare error handlers strutturati

5. **Background Tasks**
   ```python
   async def compose_article(
       request: ComposeRequestValidator,
       background_tasks: BackgroundTasks,
       ...
   ):
       # Cache in background
       background_tasks.add_task(cache_service.set_compose_cache, ...)
   ```

---

### Step 2: Inizializzazione Cache

Aggiungere startup event per inizializzare cache:

```python
@router.on_event("startup")
async def startup_event():
    await cache_service.initialize()

@router.on_event("shutdown")
async def shutdown_event():
    await cache_service.close()
```

---

### Step 3: Aggiornare Dipendenze

✅ Già fatto: `slowapi>=0.9.0` aggiunto a `requirements.txt`

---

### Step 4: Testing

1. Test retry logic
2. Test rate limiting
3. Test caching
4. Test error handling
5. Test validation

---

### Step 5: Documentazione

Aggiornare `ARTICLE_COMPOSER_API.md` con:

- Nuove features
- Rate limits
- Caching behavior
- Error codes

---

## 📝 NOTE IMPLEMENTAZIONE

### Rate Limiting

**Configurazione:**

- Default: 10 requests/minute per IP
- Configurabile via environment variable

**Headers di risposta:**

- `X-RateLimit-Limit`: Limite corrente
- `X-RateLimit-Remaining`: Richieste rimanenti
- `X-RateLimit-Reset`: Timestamp reset

### Caching

**TTL:**

- Compose results: 1 hour
- Status checks: 5 minutes

**Cache Keys:**

- Format: `article_composer:{operation}:{hash}`
- Hash basato su title + content preview + category

**Invalidation:**

- Automatica dopo TTL
- Manuale via endpoint (futuro)

### Error Handling

**Error Codes:**

- `API_KEY_NOT_CONFIGURED`: 500
- `RATE_LIMIT_EXCEEDED`: 429
- `API_CONNECTION_ERROR`: 503
- `API_TIMEOUT`: 504
- `JSON_PARSE_ERROR`: 400
- `VALIDATION_ERROR`: 422

**Response Format:**

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Claude API rate limit exceeded",
  "details": {...},
  "timestamp": "2026-01-24T...",
  "request_id": "uuid"
}
```

---

## 🚀 DEPLOYMENT CHECKLIST

- [ ] Testare localmente con Redis
- [ ] Verificare rate limiting funziona
- [ ] Testare retry logic con errori simulati
- [ ] Verificare cache hit/miss metrics
- [ ] Aggiornare documentazione API
- [ ] Deploy su staging
- [ ] Monitorare metrics dopo deploy
- [ ] Deploy su production

---

**Last Updated:** 2026-01-24
