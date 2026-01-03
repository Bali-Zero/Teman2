# 🔴 FIX PROMPT: ERROR HANDLING

**Categoria:** Error Handling & Resilience  
**Priorità:** 🔴 CRITICA  
**Aree Interessate:** 8 componenti core  
**Tempo Stimato:** 3-4 giorni

---

## 📋 PROMPT PER COMPOSER

```
Analizza e migliora la gestione degli errori nel sistema NUZANTARA.

CONTESTO:
Il sistema NUZANTARA ha gestione errori incompleta in diverse aree critiche. 
Errori vengono silenziati, classificati male, o gestiti in modo troppo permissivo,
causando degradazione silenziosa del servizio e difficoltà nel debugging.

REQUISITI:
1. Identifica tutti i punti dove errori vengono catturati ma non gestiti correttamente
2. Implementa classificazione errori completa (transient vs permanent)
3. Aggiungi retry logic appropriato per errori transienti
4. Implementa circuit breaker per prevenire cascading failures
5. Aggiungi logging strutturato con correlation IDs
6. Implementa metriche per monitorare errori
7. Crea fallback graceful per errori non critici
8. Mantieni backward compatibility

AREE DA FIXARE:
- AgenticRAGOrchestrator: Stream query error handling
- SearchService: Hybrid search error handling
- MemoryOrchestrator: Graceful degradation troppo permissiva
- LLM Gateway: Fallback cascade senza circuit breaker
- Database Pool: Error recovery incompleto
- Qdrant Client: Error classification incompleta
- Reasoning Engine: Context validation mancante
- Streaming Endpoints: Error propagation incompleta

CONSTRAINTS:
- Non modificare API pubbliche
- Mantieni performance (<5ms overhead per error handling)
- Usa structured logging (JSON format)
- Implementa alerting su errori critici
- Evita errori silenziosi (sempre log almeno)
```

---

## 🎯 AREA 1: AgenticRAGOrchestrator - Stream Query Error Handling

### Problema
```python
# File: apps/backend-rag/backend/services/rag/agentic/orchestrator.py
# Linea ~388-398

# PROBLEMA: Eventi malformati vengono skippati silenziosamente
async for event in orchestrator.stream_query(...):
    if event is None:
        continue  # Skip None events - SILENZIOSO
    if not isinstance(event, dict):
        continue  # Skip non-dict events - SILENZIOSO
    # Nessun logging, nessuna metrica, nessun alert
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Validazione completa eventi con schema
# 2. Logging strutturato per eventi malformati
# 3. Metriche per event corruption
# 4. Retry logic per errori transienti
# 5. Error events nel stream per notificare client

import json
from typing import Any
from pydantic import BaseModel, ValidationError

class StreamEvent(BaseModel):
    """Schema per eventi stream."""
    type: str
    data: dict[str, Any]
    timestamp: float | None = None
    correlation_id: str | None = None

class AgenticRAGOrchestrator:
    def __init__(self, ...):
        # ... existing code ...
        self._event_validation_enabled = True
        self._max_event_errors = 10  # Max errori prima di abortire stream
    
    async def stream_query(
        self,
        query: str,
        user_id: str,
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream query with comprehensive error handling."""
        correlation_id = str(uuid.uuid4())
        event_error_count = 0
        
        try:
            # Yield initial status
            yield {
                "type": "status",
                "data": {"status": "processing", "correlation_id": correlation_id},
                "timestamp": time.time(),
            }
            
            async for raw_event in self._stream_query_internal(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                session_id=session_id,
                correlation_id=correlation_id,
            ):
                # Validate event structure
                try:
                    if raw_event is None:
                        event_error_count += 1
                        logger.warning(
                            f"⚠️ [Stream] None event received",
                            extra={
                                "correlation_id": correlation_id,
                                "user_id": user_id,
                                "error_count": event_error_count,
                            }
                        )
                        metrics_collector.stream_event_none_total.inc()
                        
                        if event_error_count >= self._max_event_errors:
                            yield self._create_error_event(
                                "too_many_errors",
                                "Stream aborted due to too many malformed events",
                                correlation_id
                            )
                            break
                        continue
                    
                    if not isinstance(raw_event, dict):
                        event_error_count += 1
                        logger.error(
                            f"❌ [Stream] Invalid event type: {type(raw_event)}",
                            extra={
                                "correlation_id": correlation_id,
                                "user_id": user_id,
                                "event_type": str(type(raw_event)),
                                "error_count": event_error_count,
                            }
                        )
                        metrics_collector.stream_event_invalid_type_total.inc()
                        continue
                    
                    # Validate event schema
                    if self._event_validation_enabled:
                        try:
                            validated_event = StreamEvent(**raw_event)
                            yield validated_event.model_dump(exclude_none=True)
                        except ValidationError as e:
                            event_error_count += 1
                            logger.error(
                                f"❌ [Stream] Event validation failed: {e}",
                                extra={
                                    "correlation_id": correlation_id,
                                    "user_id": user_id,
                                    "validation_errors": e.errors(),
                                    "raw_event": str(raw_event)[:200],
                                }
                            )
                            metrics_collector.stream_event_validation_failed_total.inc()
                            
                            # Yield error event to client
                            yield self._create_error_event(
                                "validation_error",
                                f"Event validation failed: {e}",
                                correlation_id
                            )
                            continue
                    else:
                        # Skip validation but still yield
                        yield raw_event
                        
                except Exception as e:
                    event_error_count += 1
                    logger.exception(
                        f"❌ [Stream] Unexpected error processing event",
                        extra={
                            "correlation_id": correlation_id,
                            "user_id": user_id,
                            "error": str(e),
                        }
                    )
                    metrics_collector.stream_event_processing_error_total.inc()
                    
                    if event_error_count >= self._max_event_errors:
                        yield self._create_error_event(
                            "processing_error",
                            f"Stream aborted: {str(e)}",
                            correlation_id
                        )
                        break
                        
        except Exception as e:
            logger.exception(
                f"❌ [Stream] Fatal error in stream_query",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "query": query[:100],
                }
            )
            # Yield final error event
            yield self._create_error_event(
                "fatal_error",
                f"Stream failed: {str(e)}",
                correlation_id
            )
            metrics_collector.stream_fatal_error_total.inc()
    
    def _create_error_event(
        self,
        error_type: str,
        message: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Create standardized error event."""
        return {
            "type": "error",
            "data": {
                "error_type": error_type,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": time.time(),
            },
            "timestamp": time.time(),
        }
```

### Test Case
```python
# Test: apps/backend-rag/tests/services/rag/agentic/test_orchestrator_error_handling.py

@pytest.mark.asyncio
async def test_stream_handles_none_events():
    """Test that None events are handled gracefully."""
    orchestrator = AgenticRAGOrchestrator(...)
    
    # Mock stream to yield None events
    async def mock_stream():
        yield None
        yield {"type": "token", "data": {"text": "test"}}
        yield None
        yield None
    
    events = []
    async for event in orchestrator._validate_stream_events(mock_stream(), "test-id"):
        events.append(event)
    
    # Should have error events for None, but continue processing
    assert len(events) > 0
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) == 2  # Two None events

@pytest.mark.asyncio
async def test_stream_aborts_after_max_errors():
    """Test that stream aborts after too many errors."""
    orchestrator = AgenticRAGOrchestrator(...)
    orchestrator._max_event_errors = 3
    
    # Mock stream with many None events
    async def mock_stream():
        for _ in range(10):
            yield None
    
    events = []
    async for event in orchestrator._validate_stream_events(mock_stream(), "test-id"):
        events.append(event)
        if event.get("type") == "error" and "aborted" in event.get("data", {}).get("message", ""):
            break
    
    # Should abort after 3 errors
    assert len(events) <= 5  # Initial + 3 errors + abort
```

---

## 🎯 AREA 2: SearchService - Hybrid Search Error Handling

### Problema
```python
# File: apps/backend-rag/backend/services/search/search_service.py
# Linea ~142

# PROBLEMA: BM25 initialization fallisce silenziosamente
try:
    self._bm25_vectorizer = BM25Vectorizer(...)
except Exception as e:
    logger.warning(f"⚠️ Failed to initialize BM25Vectorizer: {e}")
    # Continua senza BM25 - nessun fallback, nessuna metrica
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Fallback a dense-only search quando BM25 fallisce
# 2. Metriche per BM25 failures
# 3. Retry logic per initialization
# 4. Health check per BM25 availability
# 5. Alerting su BM25 failures

class SearchService:
    def __init__(self, ...):
        # ... existing code ...
        self._bm25_enabled = False
        self._bm25_initialization_attempts = 0
        self._max_bm25_init_attempts = 3
    
    def _init_bm25_with_retry(self) -> bool:
        """Initialize BM25 with retry and fallback."""
        if not settings.enable_bm25:
            logger.info("BM25 disabled via settings")
            return False
        
        for attempt in range(self._max_bm25_init_attempts):
            try:
                from core.bm25_vectorizer import BM25Vectorizer
                
                self._bm25_vectorizer = BM25Vectorizer(
                    vocab_size=settings.bm25_vocab_size,
                    k1=settings.bm25_k1,
                    b=settings.bm25_b,
                )
                
                self._bm25_enabled = True
                logger.info("✅ BM25Vectorizer initialized successfully")
                metrics_collector.bm25_initialization_success_total.inc()
                return True
                
            except ImportError as e:
                logger.error(
                    f"❌ BM25Vectorizer import failed: {e}",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": self._max_bm25_init_attempts,
                        "error_type": "import_error",
                    }
                )
                metrics_collector.bm25_initialization_failed_total.labels(
                    error_type="import_error"
                ).inc()
                # Import errors are permanent - don't retry
                return False
                
            except Exception as e:
                self._bm25_initialization_attempts = attempt + 1
                logger.warning(
                    f"⚠️ BM25Vectorizer initialization failed (attempt {attempt + 1}/{self._max_bm25_init_attempts}): {e}",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": self._max_bm25_init_attempts,
                        "error_type": type(e).__name__,
                    }
                )
                metrics_collector.bm25_initialization_failed_total.labels(
                    error_type=type(e).__name__
                ).inc()
                
                if attempt < self._max_bm25_init_attempts - 1:
                    # Exponential backoff
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(
                        f"❌ BM25Vectorizer initialization failed after {self._max_bm25_init_attempts} attempts. "
                        f"Falling back to dense-only search.",
                        extra={
                            "final_error": str(e),
                            "error_type": type(e).__name__,
                        }
                    )
                    # Alert on persistent failure
                    await self._alert_bm25_failure(e)
                    return False
        
        return False
    
    async def search(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        collection_override: str | None = None,
    ) -> dict[str, Any]:
        """Search with fallback to dense-only if BM25 unavailable."""
        try:
            # Prepare search context
            query_embedding, collection_name, filter_dict, tier_values = (
                await self._prepare_search_context(...)
            )
            
            # Try hybrid search if BM25 available
            if self._bm25_enabled and self._bm25_vectorizer:
                try:
                    # Generate sparse vector
                    sparse_vector = self._bm25_vectorizer.vectorize(query)
                    
                    # Hybrid search
                    results = await self.collection_manager.hybrid_search(
                        collection_name=collection_name,
                        dense_vector=query_embedding,
                        sparse_vector=sparse_vector,
                        limit=limit,
                        filter=filter_dict,
                    )
                    
                    metrics_collector.search_hybrid_total.inc()
                    return format_search_results(results, query, user_level, tier_values)
                    
                except Exception as e:
                    logger.warning(
                        f"⚠️ Hybrid search failed, falling back to dense-only: {e}",
                        extra={
                            "query": query[:100],
                            "collection": collection_name,
                            "error": str(e),
                        }
                    )
                    metrics_collector.search_hybrid_failed_total.inc()
                    # Fall through to dense-only search
            
            # Fallback: Dense-only search
            results = await self.collection_manager.search(
                collection_name=collection_name,
                query_embedding=query_embedding,
                limit=limit,
                filter=filter_dict,
            )
            
            metrics_collector.search_dense_only_total.inc()
            return format_search_results(results, query, user_level, tier_values)
            
        except Exception as e:
            logger.exception(
                f"❌ Search failed completely",
                extra={
                    "query": query[:100],
                    "user_level": user_level,
                    "collection_override": collection_override,
                }
            )
            metrics_collector.search_failed_total.inc()
            
            # Return empty results instead of raising
            return {
                "query": query,
                "results": [],
                "user_level": user_level,
                "allowed_tiers": [],
                "collection_used": collection_override or "unknown",
                "error": "Search service temporarily unavailable",
            }
    
    async def _alert_bm25_failure(self, error: Exception):
        """Alert on BM25 persistent failure."""
        # Send alert to monitoring system
        try:
            from services.monitoring.alert_service import AlertService
            alert_service = AlertService()
            await alert_service.send_alert(
                severity="warning",
                title="BM25 Initialization Failed",
                message=f"BM25Vectorizer failed to initialize after {self._max_bm25_init_attempts} attempts. "
                       f"System falling back to dense-only search.",
                metadata={
                    "error": str(error),
                    "error_type": type(error).__name__,
                }
            )
        except Exception as alert_error:
            logger.error(f"Failed to send BM25 failure alert: {alert_error}")
```

### Test Case
```python
@pytest.mark.asyncio
async def test_search_fallback_to_dense_on_bm25_failure():
    """Test that search falls back to dense-only when BM25 fails."""
    search_service = SearchService()
    search_service._bm25_enabled = False  # Simulate BM25 failure
    
    results = await search_service.search(
        query="test query",
        user_level=3,
        limit=5
    )
    
    # Should return results using dense-only
    assert "results" in results
    assert results["error"] is None  # No error, just fallback
    # Verify dense-only metric was incremented
```

---

## 🎯 AREA 3: MemoryOrchestrator - Graceful Degradation Troppo Permissiva

### Problema
```python
# File: apps/backend-rag/backend/services/memory/orchestrator.py
# Linea ~127-132

# PROBLEMA: Degraded mode viene attivato troppo facilmente
except Exception as e:
    logger.error(f"❌ MemoryOrchestrator initialization failed: {e}")
    # Allow graceful degradation - still mark as initialized
    self._is_initialized = True
    logger.warning("⚠️ MemoryOrchestrator running in degraded mode")
    # Nessuna validazione se degraded mode è accettabile
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Circuit breaker per degraded mode
# 2. Validazione rigorosa prima di degraded mode
# 3. Metriche per degraded mode activations
# 4. Alerting su degraded mode
# 5. Health check per recovery

from enum import Enum

class MemoryServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

class MemoryOrchestrator:
    def __init__(self, ...):
        # ... existing code ...
        self._status = MemoryServiceStatus.UNAVAILABLE
        self._degraded_mode_allowed = False
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
    
    async def initialize(self) -> None:
        """Initialize with strict validation."""
        if self._is_initialized:
            return
        
        critical_failures = []
        non_critical_failures = []
        
        try:
            # CRITICAL: Memory service must initialize
            self._memory_service = MemoryServicePostgres(database_url=self._database_url)
            
            if self._db_pool:
                self._memory_service.pool = self._db_pool
                self._memory_service.use_postgres = True
            else:
                await self._memory_service.connect()
                self._db_pool = self._memory_service.pool
            
            # Verify connection works
            test_memory = await self._memory_service.get_memory("__test__", force_refresh=False)
            if test_memory is None:
                raise RuntimeError("Memory service connection test failed")
            
            logger.info("✅ Memory service initialized and verified")
            
        except Exception as e:
            critical_failures.append(("memory_service", str(e)))
            logger.error(
                f"❌ CRITICAL: Memory service initialization failed: {e}",
                extra={"error_type": type(e).__name__}
            )
        
        try:
            # NON-CRITICAL: Fact extractor
            self._fact_extractor = MemoryFactExtractor()
        except Exception as e:
            non_critical_failures.append(("fact_extractor", str(e)))
            logger.warning(f"⚠️ Fact extractor initialization failed: {e}")
        
        try:
            # NON-CRITICAL: Collective memory
            self._collective_memory = CollectiveMemoryService(pool=self._db_pool)
        except Exception as e:
            non_critical_failures.append(("collective_memory", str(e)))
            logger.warning(f"⚠️ Collective memory initialization failed: {e}")
        
        # Determine status
        if critical_failures:
            self._status = MemoryServiceStatus.UNAVAILABLE
            self._is_initialized = False
            metrics_collector.memory_orchestrator_unavailable_total.inc()
            
            # Alert on critical failure
            await self._alert_critical_failure(critical_failures)
            
            raise RuntimeError(
                f"MemoryOrchestrator initialization failed: {critical_failures}"
            )
        elif non_critical_failures:
            self._status = MemoryServiceStatus.DEGRADED
            self._is_initialized = True
            self._degraded_mode_allowed = True
            
            logger.warning(
                f"⚠️ MemoryOrchestrator running in DEGRADED mode",
                extra={
                    "non_critical_failures": non_critical_failures,
                    "degraded_features": [f[0] for f in non_critical_failures],
                }
            )
            metrics_collector.memory_orchestrator_degraded_total.inc()
            
            # Alert on degraded mode
            await self._alert_degraded_mode(non_critical_failures)
        else:
            self._status = MemoryServiceStatus.HEALTHY
            self._is_initialized = True
            logger.info("✅ MemoryOrchestrator initialized successfully (HEALTHY)")
            metrics_collector.memory_orchestrator_healthy_total.inc()
    
    def _ensure_initialized(self) -> None:
        """Raise error if not initialized or unavailable."""
        if not self._is_initialized:
            raise RuntimeError("MemoryOrchestrator not initialized. Call initialize() first.")
        
        if self._status == MemoryServiceStatus.UNAVAILABLE:
            raise RuntimeError("MemoryOrchestrator is unavailable. Check initialization errors.")
    
    async def get_user_context(self, user_email: str, query: str | None = None) -> MemoryContext:
        """Get user context with status awareness."""
        self._ensure_initialized()
        
        if self._status == MemoryServiceStatus.DEGRADED:
            # In degraded mode, return limited context
            logger.debug(f"Returning degraded context for {user_email}")
            metrics_collector.memory_context_degraded_total.inc()
        
        try:
            if not self._memory_service or not self._memory_service.pool:
                return MemoryContext(user_id=user_email, has_data=False)
            
            memory = await self._memory_service.get_memory(user_email, force_refresh=True)
            
            # Get collective memory only if available
            collective_facts = []
            if self._collective_memory and self._status != MemoryServiceStatus.DEGRADED:
                try:
                    if query:
                        collective_facts = await self._collective_memory.get_relevant_context(
                            query=query, limit=10
                        )
                    else:
                        collective_facts = await self._collective_memory.get_promoted_facts(limit=10)
                except Exception as e:
                    logger.warning(f"Collective memory retrieval failed: {e}")
                    # Don't fail entire operation
            
            return MemoryContext(
                user_id=user_email,
                has_data=memory.has_data,
                facts=memory.facts,
                summary=memory.summary,
                counters=memory.counters,
                collective_facts=collective_facts,
            )
            
        except Exception as e:
            logger.exception(
                f"Failed to get user context",
                extra={"user_email": user_email}
            )
            metrics_collector.memory_context_failed_total.inc()
            
            # Return empty context instead of raising
            return MemoryContext(user_id=user_email, has_data=False)
    
    async def _alert_critical_failure(self, failures: list[tuple[str, str]]):
        """Alert on critical initialization failure."""
        # Implementation for alerting
        pass
    
    async def _alert_degraded_mode(self, failures: list[tuple[str, str]]):
        """Alert on degraded mode activation."""
        # Implementation for alerting
        pass
```

### Test Case
```python
@pytest.mark.asyncio
async def test_memory_orchestrator_rejects_degraded_on_critical_failure():
    """Test that orchestrator fails if critical component fails."""
    # Mock memory service to fail
    with patch('services.memory.memory_service_postgres.MemoryServicePostgres') as mock:
        mock.side_effect = Exception("Critical failure")
        
        orchestrator = MemoryOrchestrator()
        
        with pytest.raises(RuntimeError, match="initialization failed"):
            await orchestrator.initialize()
        
        assert orchestrator._status == MemoryServiceStatus.UNAVAILABLE
        assert not orchestrator._is_initialized
```

---

## 🎯 AREA 4: LLM Gateway - Fallback Cascade senza Circuit Breaker

### Problema
```python
# File: apps/backend-rag/backend/services/rag/agentic/llm_gateway.py
# Linea ~225

# PROBLEMA: Fallback cascade può continuare indefinitamente
async def _send_with_fallback(...):
    # Try Flash -> Lite -> OpenRouter
    # Nessun circuit breaker, nessun limite costo
    # Può causare costi esplosivi
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Circuit breaker per ogni modello
# 2. Cost tracking e limiti
# 3. Timeout globale per fallback cascade
# 4. Metriche per fallback depth
# 5. Alerting su costi elevati

import time
from collections import defaultdict
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, don't try
    HALF_OPEN = "half_open"  # Testing recovery

class LLMGateway:
    def __init__(self, gemini_tools: list = None):
        # ... existing code ...
        self._circuit_breakers: dict[str, dict] = defaultdict(
            lambda: {
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "last_failure_time": None,
                "success_count": 0,
            }
        )
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60  # seconds
        self._max_fallback_depth = 3
        self._max_fallback_cost_usd = 0.10  # Max $0.10 per query
        self._total_cost_tracker: dict[str, float] = defaultdict(float)
    
    async def send_message(
        self,
        chat: Any,
        message: str,
        system_prompt: str = "",
        tier: int = TIER_FLASH,
        enable_function_calling: bool = True,
        conversation_messages: list[dict] | None = None,
    ) -> tuple[str, str, Any, TokenUsage]:
        """Send message with circuit breaker and cost limits."""
        start_time = time.time()
        query_cost = 0.0
        fallback_depth = 0
        
        try:
            return await self._send_with_fallback(
                chat=chat,
                message=message,
                system_prompt=system_prompt,
                model_tier=tier,
                enable_function_calling=enable_function_calling,
                conversation_messages=conversation_messages or [],
                query_cost_tracker={"cost": 0.0, "depth": 0},
            )
        except Exception as e:
            logger.exception(
                f"All LLM models failed",
                extra={
                    "tier": tier,
                    "fallback_depth": fallback_depth,
                    "total_cost": query_cost,
                }
            )
            metrics_collector.llm_all_models_failed_total.inc()
            raise RuntimeError(f"All LLM models failed: {e}")
    
    async def _send_with_fallback(
        self,
        chat: Any,
        message: str,
        system_prompt: str,
        model_tier: int,
        enable_function_calling: bool,
        conversation_messages: list[dict],
        query_cost_tracker: dict,
    ) -> tuple[str, str, Any, TokenUsage]:
        """Send with fallback cascade and circuit breakers."""
        models_to_try = self._get_fallback_chain(model_tier)
        
        for model_name in models_to_try:
            # Check circuit breaker
            if self._is_circuit_open(model_name):
                logger.debug(f"Circuit breaker OPEN for {model_name}, skipping")
                metrics_collector.llm_circuit_breaker_open_total.labels(
                    model=model_name
                ).inc()
                continue
            
            # Check cost limit
            if query_cost_tracker["cost"] >= self._max_fallback_cost_usd:
                logger.warning(
                    f"Cost limit reached ({query_cost_tracker['cost']:.4f} USD), "
                    f"stopping fallback cascade"
                )
                metrics_collector.llm_cost_limit_reached_total.inc()
                break
            
            # Check fallback depth
            if query_cost_tracker["depth"] >= self._max_fallback_depth:
                logger.warning(
                    f"Max fallback depth reached ({query_cost_tracker['depth']}), "
                    f"stopping cascade"
                )
                metrics_collector.llm_max_depth_reached_total.inc()
                break
            
            try:
                # Try model
                response, model_used, obj, usage = await self._try_model(
                    model_name=model_name,
                    chat=chat,
                    message=message,
                    system_prompt=system_prompt,
                    enable_function_calling=enable_function_calling,
                    conversation_messages=conversation_messages,
                )
                
                # Success - reset circuit breaker
                self._record_success(model_name)
                query_cost_tracker["cost"] += usage.cost_usd
                query_cost_tracker["depth"] += 1
                
                metrics_collector.llm_fallback_depth.observe(query_cost_tracker["depth"])
                metrics_collector.llm_query_cost_usd.observe(query_cost_tracker["cost"])
                
                return response, model_used, obj, usage
                
            except ResourceExhausted as e:
                # Quota exceeded - open circuit breaker
                self._record_failure(model_name, "quota_exhausted")
                logger.warning(f"Quota exhausted for {model_name}: {e}")
                metrics_collector.llm_quota_exhausted_total.labels(
                    model=model_name
                ).inc()
                continue
                
            except ServiceUnavailable as e:
                # Service unavailable - record failure but don't open circuit immediately
                self._record_failure(model_name, "service_unavailable")
                logger.warning(f"Service unavailable for {model_name}: {e}")
                metrics_collector.llm_service_unavailable_total.labels(
                    model=model_name
                ).inc()
                continue
                
            except Exception as e:
                # Other errors - record failure
                self._record_failure(model_name, type(e).__name__)
                logger.warning(f"Error with {model_name}: {e}")
                metrics_collector.llm_model_error_total.labels(
                    model=model_name,
                    error_type=type(e).__name__
                ).inc()
                continue
        
        # All models failed
        raise RuntimeError("All models in fallback chain failed")
    
    def _is_circuit_open(self, model_name: str) -> bool:
        """Check if circuit breaker is open."""
        circuit = self._circuit_breakers[model_name]
        
        if circuit["state"] == CircuitState.OPEN:
            # Check if timeout expired
            if circuit["last_failure_time"]:
                elapsed = time.time() - circuit["last_failure_time"]
                if elapsed > self._circuit_breaker_timeout:
                    # Move to half-open for testing
                    circuit["state"] = CircuitState.HALF_OPEN
                    circuit["success_count"] = 0
                    logger.info(f"Circuit breaker HALF_OPEN for {model_name}")
                    return False
            return True
        
        return False
    
    def _record_success(self, model_name: str):
        """Record successful call."""
        circuit = self._circuit_breakers[model_name]
        circuit["failure_count"] = 0
        
        if circuit["state"] == CircuitState.HALF_OPEN:
            circuit["success_count"] += 1
            if circuit["success_count"] >= 2:
                circuit["state"] = CircuitState.CLOSED
                logger.info(f"Circuit breaker CLOSED for {model_name}")
    
    def _record_failure(self, model_name: str, error_type: str):
        """Record failed call."""
        circuit = self._circuit_breakers[model_name]
        circuit["failure_count"] += 1
        circuit["last_failure_time"] = time.time()
        
        if circuit["failure_count"] >= self._circuit_breaker_threshold:
            circuit["state"] = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPENED for {model_name} "
                f"({circuit['failure_count']} failures)"
            )
            metrics_collector.llm_circuit_breaker_opened_total.labels(
                model=model_name,
                error_type=error_type
            ).inc()
```

### Test Case
```python
@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold():
    """Test that circuit breaker opens after threshold failures."""
    gateway = LLMGateway()
    gateway._circuit_breaker_threshold = 3
    
    model_name = "gemini-3-flash-preview"
    
    # Simulate failures
    for i in range(3):
        gateway._record_failure(model_name, "test_error")
    
    assert gateway._is_circuit_open(model_name) == True
    assert gateway._circuit_breakers[model_name]["state"] == CircuitState.OPEN
```

---

## 🎯 AREA 5: Database Pool - Error Recovery Incompleto

### Problema
```python
# File: apps/backend-rag/backend/app/setup/service_initializer.py
# Linea ~326

# PROBLEMA: Errori transitori causano failure immediata
except (asyncpg.PostgresError, ValueError, ...) as e:
    logger.error(f"Database initialization failed: {e}")
    # Nessun retry, nessun recovery
    return None
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Retry con exponential backoff
# 2. Health check periodico
# 3. Auto-recovery su errori transitori
# 4. Connection pool validation
# 5. Graceful degradation

import asyncio
from datetime import datetime, timedelta

async def _init_database_services(app: FastAPI) -> asyncpg.Pool | None:
    """Initialize database with retry and health checks."""
    if not settings.database_url:
        service_registry.register(
            "database",
            ServiceStatus.UNAVAILABLE,
            error="DATABASE_URL not configured",
            critical=False,
        )
        return None
    
    max_retries = 5
    base_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Database initialization attempt {attempt + 1}/{max_retries}")
            
            # Create pool with validation
            async def init_db_connection(conn):
                await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
                await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
                
                # Validate connection
                await conn.execute("SELECT 1")
            
            db_pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=settings.db_pool_min_size or 5,
                max_size=settings.db_pool_max_size or 20,
                command_timeout=settings.db_command_timeout or 60,
                init=init_db_connection,
            )
            
            # Verify pool works
            async with db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    raise ValueError("Pool validation failed")
            
            # Initialize services
            from services.analytics.team_timesheet_service import init_timesheet_service
            ts_service = init_timesheet_service(db_pool)
            app.state.ts_service = ts_service
            app.state.db_pool = db_pool
            
            # Start background tasks
            await ts_service.start_auto_logout_monitor()
            
            # Start health check task
            app.state.db_health_check_task = asyncio.create_task(
                _database_health_check_loop(db_pool)
            )
            
            service_registry.register("database", ServiceStatus.HEALTHY, critical=False)
            logger.info("✅ Database services initialized successfully")
            metrics_collector.database_init_success_total.inc()
            
            return db_pool
            
        except (asyncpg.PostgresError, ValueError, ConnectionError) as e:
            error_type = type(e).__name__
            is_transient = _is_transient_error(e)
            
            logger.warning(
                f"⚠️ Database initialization failed (attempt {attempt + 1}/{max_retries}): {e}",
                extra={
                    "attempt": attempt + 1,
                    "error_type": error_type,
                    "is_transient": is_transient,
                }
            )
            
            metrics_collector.database_init_failed_total.labels(
                error_type=error_type,
                is_transient=is_transient
            ).inc()
            
            if attempt < max_retries - 1 and is_transient:
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + (random.random() * 0.5)
                logger.info(f"Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
            else:
                # Permanent error or max retries reached
                service_registry.register(
                    "database",
                    ServiceStatus.UNAVAILABLE,
                    error=str(e),
                    critical=False,
                )
                logger.error(f"❌ Database initialization failed permanently: {e}")
                metrics_collector.database_init_permanent_failure_total.inc()
                return None
    
    return None

def _is_transient_error(error: Exception) -> bool:
    """Determine if error is transient and retryable."""
    error_msg = str(error).lower()
    
    transient_patterns = [
        "connection",
        "timeout",
        "temporarily unavailable",
        "too many connections",
        "server closed",
        "network",
    ]
    
    return any(pattern in error_msg for pattern in transient_patterns)

async def _database_health_check_loop(db_pool: asyncpg.Pool):
    """Periodic health check for database pool."""
    check_interval = 30  # seconds
    
    while True:
        try:
            await asyncio.sleep(check_interval)
            
            # Check pool health
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                
                # Pool is healthy
                service_registry.register("database", ServiceStatus.HEALTHY)
                metrics_collector.database_health_check_success_total.inc()
                
            except Exception as e:
                logger.warning(f"Database health check failed: {e}")
                service_registry.register(
                    "database",
                    ServiceStatus.DEGRADED,
                    error=str(e),
                )
                metrics_collector.database_health_check_failed_total.inc()
                
                # Try to recover
                if _is_transient_error(e):
                    logger.info("Attempting database recovery...")
                    # Recovery logic here
                    
        except asyncio.CancelledError:
            logger.info("Database health check loop cancelled")
            break
        except Exception as e:
            logger.exception(f"Error in database health check loop: {e}")
```

### Test Case
```python
@pytest.mark.asyncio
async def test_database_init_retries_on_transient_error():
    """Test that database init retries on transient errors."""
    # Mock transient error
    with patch('asyncpg.create_pool') as mock_pool:
        mock_pool.side_effect = [
            ConnectionError("Connection timeout"),
            ConnectionError("Connection timeout"),
            MagicMock()  # Success on third attempt
        ]
        
        pool = await _init_database_services(app)
        
        assert pool is not None
        assert mock_pool.call_count == 3
```

---

## 🎯 AREA 6: Qdrant Client - Error Classification Incompleta

### Problema
```python
# File: apps/backend-rag/backend/core/qdrant_db.py
# Linea ~376

# PROBLEMA: Classificazione errori troppo semplice
if 500 <= e.response.status_code < 600:
    raise Exception(f"Qdrant server error {e.response.status_code}")
# Non distingue retryable da non-retryable
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Classificazione completa errori Qdrant
# 2. Retry solo per errori retryable
# 3. Metriche per tipo errore
# 4. Alerting su errori critici

from enum import Enum

class QdrantErrorType(Enum):
    RETRYABLE = "retryable"  # Can retry
    NON_RETRYABLE = "non_retryable"  # Don't retry
    CLIENT_ERROR = "client_error"  # Bad request
    SERVER_ERROR = "server_error"  # Server issue
    TIMEOUT = "timeout"  # Timeout
    CONNECTION = "connection"  # Connection issue

class QdrantClient:
    def __init__(self, ...):
        # ... existing code ...
        self._error_classifier = QdrantErrorClassifier()
    
    def _classify_error(self, error: Exception) -> tuple[QdrantErrorType, bool]:
        """Classify error and determine if retryable."""
        return self._error_classifier.classify(error)
    
    async def search(
        self,
        query_embedding: list[float],
        filter: dict[str, Any] | None = None,
        limit: int = 5,
        vector_name: str | None = None,
    ) -> dict[str, Any]:
        """Search with proper error classification."""
        async def _do_search():
            # ... search implementation ...
            pass
        
        try:
            return await _retry_with_backoff(
                _do_search,
                max_retries=self._max_retries,
                base_delay=self._retry_base_delay,
                error_classifier=self._classify_error,
            )
        except httpx.TimeoutException as e:
            error_type, retryable = self._classify_error(e)
            logger.error(
                f"Qdrant search timeout",
                extra={
                    "error_type": error_type.value,
                    "retryable": retryable,
                    "timeout": self.timeout,
                }
            )
            metrics_collector.qdrant_timeout_total.labels(
                error_type=error_type.value
            ).inc()
            raise TimeoutError(f"Qdrant request timeout after {self.timeout}s")
            
        except httpx.HTTPStatusError as e:
            error_type, retryable = self._classify_error(e)
            
            logger.error(
                f"Qdrant HTTP error: {e.response.status_code}",
                extra={
                    "status_code": e.response.status_code,
                    "error_type": error_type.value,
                    "retryable": retryable,
                    "response_text": e.response.text[:200] if hasattr(e.response, "text") else None,
                }
            )
            
            metrics_collector.qdrant_http_error_total.labels(
                status_code=e.response.status_code,
                error_type=error_type.value
            ).inc()
            
            if error_type == QdrantErrorType.CLIENT_ERROR:
                # Don't retry client errors
                raise ValueError(f"Qdrant client error {e.response.status_code}: {e.response.text}")
            elif error_type == QdrantErrorType.SERVER_ERROR and retryable:
                # Retry server errors
                raise Exception(f"Qdrant server error {e.response.status_code}: {e.response.text}")
            else:
                raise

class QdrantErrorClassifier:
    """Classify Qdrant errors."""
    
    RETRYABLE_STATUS_CODES = {500, 502, 503, 504}  # Server errors
    NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}  # Client errors
    
    def classify(self, error: Exception) -> tuple[QdrantErrorType, bool]:
        """Classify error and return (error_type, retryable)."""
        if isinstance(error, httpx.TimeoutException):
            return QdrantErrorType.TIMEOUT, True
        
        if isinstance(error, httpx.ConnectError):
            return QdrantErrorType.CONNECTION, True
        
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            
            if status_code in self.RETRYABLE_STATUS_CODES:
                return QdrantErrorType.SERVER_ERROR, True
            elif status_code in self.NON_RETRYABLE_STATUS_CODES:
                return QdrantErrorType.CLIENT_ERROR, False
            else:
                # Unknown status code - be conservative
                return QdrantErrorType.SERVER_ERROR, False
        
        # Unknown error - don't retry by default
        return QdrantErrorType.NON_RETRYABLE, False

async def _retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    error_classifier=None,
):
    """Retry with backoff and error classification."""
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries:
                raise
            
            # Classify error
            if error_classifier:
                error_type, retryable = error_classifier(e)
                if not retryable:
                    raise  # Don't retry non-retryable errors
            
            # Calculate delay with jitter
            delay = base_delay * (2 ** attempt) + (random.random() * 0.5)
            logger.warning(
                f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s: {e}"
            )
            await asyncio.sleep(delay)
    
    raise RuntimeError(f"Function failed after {max_retries} retries")
```

### Test Case
```python
@pytest.mark.asyncio
async def test_qdrant_classifies_errors_correctly():
    """Test error classification."""
    classifier = QdrantErrorClassifier()
    
    # Test timeout
    timeout_error = httpx.TimeoutException("Timeout")
    error_type, retryable = classifier.classify(timeout_error)
    assert error_type == QdrantErrorType.TIMEOUT
    assert retryable == True
    
    # Test client error
    client_error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=MagicMock(status_code=400))
    error_type, retryable = classifier.classify(client_error)
    assert error_type == QdrantErrorType.CLIENT_ERROR
    assert retryable == False
```

---

## 🎯 AREA 7: Reasoning Engine - Context Validation Mancante

### Problema
```python
# File: apps/backend-rag/backend/services/rag/agentic/reasoning.py
# PROBLEMA: Context gathering non valida qualità risultati
# Nessun check su relevance, nessun threshold
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Validazione qualità context
# 2. Threshold per relevance score
# 3. Fallback se context insufficiente
# 4. Metriche per context quality

class ReasoningEngine:
    def __init__(self, ...):
        # ... existing code ...
        self._min_context_quality_score = 0.3
        self._min_context_items = 1
    
    async def execute_reasoning_loop(
        self,
        query: str,
        tools: dict[str, BaseTool],
        max_steps: int = 10,
    ) -> AgentState:
        """Execute reasoning with context validation."""
        state = AgentState(query=query, current_step=0)
        context_gathered = []
        
        for step in range(max_steps):
            # ... reasoning logic ...
            
            # Validate context quality before using
            if context_gathered:
                quality_score = self._validate_context_quality(
                    query=query,
                    context_items=context_gathered,
                )
                
                if quality_score < self._min_context_quality_score:
                    logger.warning(
                        f"⚠️ Context quality too low ({quality_score:.2f} < {self._min_context_quality_score})",
                        extra={
                            "quality_score": quality_score,
                            "context_items": len(context_gathered),
                            "step": step,
                        }
                    )
                    metrics_collector.reasoning_low_context_quality_total.inc()
                    
                    # Try to gather more context
                    if step < max_steps - 1:
                        continue  # Try another tool
                    else:
                        # Last step - use what we have but warn
                        logger.warning("Using low-quality context due to max steps")
            
            # Use validated context
            # ... continue reasoning ...
        
        return state
    
    def _validate_context_quality(
        self,
        query: str,
        context_items: list[str],
    ) -> float:
        """Validate context quality and return score (0.0-1.0)."""
        if not context_items:
            return 0.0
        
        # Check minimum items
        if len(context_items) < self._min_context_items:
            return 0.0
        
        # Simple heuristic: check if context contains query keywords
        query_keywords = set(query.lower().split())
        quality_scores = []
        
        for item in context_items:
            item_lower = item.lower()
            matching_keywords = sum(1 for kw in query_keywords if kw in item_lower)
            relevance = matching_keywords / max(len(query_keywords), 1)
            quality_scores.append(relevance)
        
        # Average quality
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        # Penalize if too few items
        item_count_penalty = min(len(context_items) / 5.0, 1.0)  # Prefer 5+ items
        
        final_score = avg_quality * 0.7 + item_count_penalty * 0.3
        
        return min(final_score, 1.0)
```

### Test Case
```python
@pytest.mark.asyncio
async def test_reasoning_validates_context_quality():
    """Test that reasoning validates context quality."""
    engine = ReasoningEngine(...)
    engine._min_context_quality_score = 0.5
    
    # Low quality context
    low_quality_context = ["unrelated text", "another unrelated"]
    score = engine._validate_context_quality("test query", low_quality_context)
    assert score < 0.5
    
    # High quality context
    high_quality_context = ["test query result", "query test answer"]
    score = engine._validate_context_quality("test query", high_quality_context)
    assert score >= 0.5
```

---

## 🎯 AREA 8: Streaming Endpoints - Error Propagation Incompleta

### Problema
```python
# File: apps/backend-rag/backend/app/routers/agentic_rag.py
# Linea ~398

# PROBLEMA: Errori durante streaming non propagati correttamente
# Client non sa che stream è fallito
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Error events nel stream
# 2. Retry logic per errori transienti
# 3. Final status event
# 4. Client notification su errori

@router.post("/stream")
async def stream_agentic_rag(
    request_body: AgenticQueryRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
):
    """Stream with comprehensive error handling."""
    correlation_id = str(uuid.uuid4())
    authenticated_user_id = current_user.get("user_id") or current_user.get("email")
    
    async def event_generator():
        try:
            # Yield initial status
            yield f"data: {json.dumps({
                'type': 'status',
                'data': {
                    'status': 'processing',
                    'correlation_id': correlation_id,
                }
            })}\n\n"
            
            # Get conversation history
            conversation_history = None
            if request_body.conversation_id or request_body.session_id:
                try:
                    conversation_history = await get_conversation_history_for_agentic(
                        conversation_id=request_body.conversation_id,
                        session_id=request_body.session_id,
                        user_id=authenticated_user_id,
                        db_pool=db_pool,
                    )
                except Exception as e:
                    logger.warning(f"Failed to load history: {e}")
                    # Yield error but continue
                    yield f"data: {json.dumps({
                        'type': 'error',
                        'data': {
                            'error_type': 'history_load_failed',
                            'message': 'Could not load conversation history',
                            'non_fatal': True,
                        }
                    })}\n\n"
            
            # Stream query
            error_count = 0
            max_errors = 5
            
            async for event in orchestrator.stream_query(
                query=request_body.query,
                user_id=authenticated_user_id,
                conversation_history=conversation_history,
                session_id=request_body.session_id,
            ):
                try:
                    # Validate event
                    if event is None:
                        error_count += 1
                        if error_count >= max_errors:
                            yield f"data: {json.dumps({
                                'type': 'error',
                                'data': {
                                    'error_type': 'too_many_errors',
                                    'message': 'Stream aborted due to too many errors',
                                    'fatal': True,
                                }
                            })}\n\n"
                            break
                        continue
                    
                    # Serialize and yield
                    event_json = json.dumps(event)
                    yield f"data: {event_json}\n\n"
                    
                    # Reset error count on success
                    error_count = 0
                    
                    # Check for client disconnect
                    if await http_request.is_disconnected():
                        logger.info(f"Client disconnected: {correlation_id}")
                        break
                        
                except json.JSONEncodeError as e:
                    error_count += 1
                    logger.error(f"JSON serialization failed: {e}")
                    yield f"data: {json.dumps({
                        'type': 'error',
                        'data': {
                            'error_type': 'serialization_error',
                            'message': 'Failed to serialize event',
                            'non_fatal': True,
                        }
                    })}\n\n"
                    
                except Exception as e:
                    error_count += 1
                    logger.exception(f"Error processing stream event: {e}")
                    yield f"data: {json.dumps({
                        'type': 'error',
                        'data': {
                            'error_type': 'processing_error',
                            'message': str(e),
                            'non_fatal': error_count < max_errors,
                        }
                    })}\n\n"
                    
                    if error_count >= max_errors:
                        break
            
            # Yield final status
            yield f"data: {json.dumps({
                'type': 'status',
                'data': {
                    'status': 'completed',
                    'correlation_id': correlation_id,
                }
            })}\n\n"
            
        except Exception as e:
            logger.exception(f"Fatal error in stream: {e}")
            yield f"data: {json.dumps({
                'type': 'error',
                'data': {
                    'error_type': 'fatal_error',
                    'message': f'Stream failed: {str(e)}',
                    'fatal': True,
                    'correlation_id': correlation_id,
                }
            })}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Correlation-ID": correlation_id,
        }
    )
```

### Test Case
```python
@pytest.mark.asyncio
async def test_stream_propagates_errors():
    """Test that stream propagates errors to client."""
    # Mock orchestrator to raise error
    async def mock_stream():
        yield {"type": "token", "data": {"text": "test"}}
        raise Exception("Test error")
        yield {"type": "token", "data": {"text": "after error"}}
    
    events = []
    async for event in mock_stream():
        events.append(event)
    
    # Should have error event
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) > 0
```

---

## 📊 METRICHE DA IMPLEMENTARE

```python
# File: apps/backend-rag/backend/app/metrics.py

# Error handling metrics
stream_event_none_total = Counter(
    "zantara_stream_event_none_total",
    "Number of None events in stream",
)

stream_event_validation_failed_total = Counter(
    "zantara_stream_event_validation_failed_total",
    "Number of stream events that failed validation",
)

search_hybrid_failed_total = Counter(
    "zantara_search_hybrid_failed_total",
    "Number of hybrid search failures",
)

memory_orchestrator_degraded_total = Counter(
    "zantara_memory_orchestrator_degraded_total",
    "Number of times memory orchestrator entered degraded mode",
)

llm_circuit_breaker_opened_total = Counter(
    "zantara_llm_circuit_breaker_opened_total",
    "Number of times circuit breaker opened",
    ["model", "error_type"]
)

database_init_failed_total = Counter(
    "zantara_database_init_failed_total",
    "Number of database initialization failures",
    ["error_type", "is_transient"]
)

qdrant_http_error_total = Counter(
    "zantara_qdrant_http_error_total",
    "Number of Qdrant HTTP errors",
    ["status_code", "error_type"]
)

reasoning_low_context_quality_total = Counter(
    "zantara_reasoning_low_context_quality_total",
    "Number of times context quality was too low",
)
```

---

## ✅ CHECKLIST DI COMPLETAMENTO

- [ ] Implementato validazione eventi stream con schema
- [ ] Implementato fallback BM25 → dense-only
- [ ] Implementato circuit breaker per degraded mode
- [ ] Implementato circuit breaker per LLM Gateway
- [ ] Implementato retry logic per database init
- [ ] Implementato classificazione errori Qdrant
- [ ] Implementato validazione qualità context
- [ ] Implementato error propagation in stream
- [ ] Aggiunti test per ogni area
- [ ] Implementate metriche di monitoring
- [ ] Documentato comportamento error handling
- [ ] Aggiunto alerting su errori critici

---

*Prompt creato: 2025-12-28*  
*Prossimo step: Implementazione fix*








