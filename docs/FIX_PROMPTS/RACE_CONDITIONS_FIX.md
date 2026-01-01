# 🔴 FIX PROMPT: RACE CONDITIONS

**Categoria:** Concurrency & Thread Safety  
**Priorità:** 🔴 CRITICA  
**Aree Interessate:** 5 componenti core  
**Tempo Stimato:** 2-3 giorni

---

## 📋 PROMPT PER COMPOSER

```
Analizza e fixa le race conditions identificate nel sistema NUZANTARA.

CONTESTO:
Il sistema NUZANTARA gestisce operazioni concorrenti su memoria utente, database, 
e cache senza meccanismi di locking appropriati. Questo causa potenziale corruzione 
dati e perdita di informazioni.

REQUISITI:
1. Identifica tutte le operazioni di scrittura concorrenti
2. Implementa locking appropriato (asyncio.Lock per single-instance, Redis Lock per distributed)
3. Mantieni backward compatibility
4. Aggiungi test per race conditions
5. Implementa metriche per monitorare lock contention

AREE DA FIXARE:
- AgenticRAGOrchestrator: Memory save operations
- MemoryOrchestrator: Concurrent write operations
- SearchService: Collection access during ingestion
- ConversationSave: Cache-DB consistency
- CollectiveMemoryService: Fact promotion race conditions

CONSTRAINTS:
- Non modificare API pubbliche
- Mantieni performance (<10ms overhead per lock)
- Usa async/await correttamente
- Evita deadlock (timeout su lock acquisition)
```

---

## 🎯 AREA 1: AgenticRAGOrchestrator - Memory Save

### Problema
```python
# File: apps/backend-rag/backend/services/rag/agentic/orchestrator.py
# Linea ~324

# PROBLEMA: Nessun lock per operazioni concorrenti di memory save
async def _save_memory_async(self, user_id: str, query: str, response: str):
    try:
        if self.memory_orchestrator:
            await self.memory_orchestrator.process_conversation(
                user_email=user_id,
                user_message=query,
                ai_response=response,
            )
    except Exception as e:
        logger.warning(f"⚠️ [AgenticRAG] Failed to save memory: {e}", exc_info=True)
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Lock per user_id per evitare race conditions su stesso utente
# 2. Timeout su lock acquisition (max 5s)
# 3. Metriche per lock contention

import asyncio
from collections import defaultdict

class AgenticRAGOrchestrator:
    def __init__(self, ...):
        # ... existing code ...
        self._memory_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._lock_timeout = 5.0  # seconds
    
    async def _save_memory_async(self, user_id: str, query: str, response: str):
        """Save memory with lock to prevent race conditions."""
        lock = self._memory_locks[user_id]
        
        try:
            # Acquire lock with timeout
            await asyncio.wait_for(lock.acquire(), timeout=self._lock_timeout)
            try:
                if self.memory_orchestrator:
                    await self.memory_orchestrator.process_conversation(
                        user_email=user_id,
                        user_message=query,
                        ai_response=response,
                    )
            finally:
                lock.release()
        except asyncio.TimeoutError:
            logger.warning(
                f"⚠️ [AgenticRAG] Memory save lock timeout for user {user_id}"
            )
            metrics_collector.memory_lock_timeout_total.inc()
        except Exception as e:
            logger.warning(f"⚠️ [AgenticRAG] Failed to save memory: {e}", exc_info=True)
```

### Test Case
```python
# Test: apps/backend-rag/tests/services/rag/agentic/test_orchestrator_race_conditions.py

import pytest
import asyncio

@pytest.mark.asyncio
async def test_concurrent_memory_save_same_user():
    """Test that concurrent memory saves for same user don't corrupt data."""
    orchestrator = AgenticRAGOrchestrator(...)
    user_id = "test@example.com"
    
    # Simulate 10 concurrent saves
    tasks = [
        orchestrator._save_memory_async(
            user_id=user_id,
            query=f"Query {i}",
            response=f"Response {i}"
        )
        for i in range(10)
    ]
    
    # All should complete without errors
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Found exceptions: {exceptions}"
    
    # Verify all facts saved (check via memory orchestrator)
    context = await orchestrator.memory_orchestrator.get_user_context(user_id)
    assert context.has_data
    assert len(context.facts) >= 10  # All facts should be saved
```

---

## 🎯 AREA 2: MemoryOrchestrator - Concurrent Writes

### Problema
```python
# File: apps/backend-rag/backend/services/memory/orchestrator.py
# Linea ~184

# PROBLEMA: get_memory e process_conversation possono essere chiamati concorrentemente
async def get_user_context(self, user_email: str, query: str | None = None) -> MemoryContext:
    # ... nessun lock ...
    memory = await self._memory_service.get_memory(user_email, force_refresh=True)
    # ...
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Read-write lock per permettere letture concorrenti ma scritture esclusive
# 2. Redis Lock per distributed systems (se necessario)
# 3. Lock per operazioni di scrittura (process_conversation)

import asyncio
from collections import defaultdict

class MemoryOrchestrator:
    def __init__(self, db_pool: asyncpg.Pool | None = None, ...):
        # ... existing code ...
        self._write_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._read_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(10)  # Allow 10 concurrent reads
        )
    
    async def get_user_context(self, user_email: str, query: str | None = None) -> MemoryContext:
        """Get user context with read lock."""
        semaphore = self._read_semaphores[user_email]
        
        async with semaphore:
            # Read operations can proceed concurrently
            if not self._memory_service or not self._memory_service.pool:
                return MemoryContext(user_id=user_email, has_data=False)
            
            memory = await self._memory_service.get_memory(user_email, force_refresh=True)
            # ... rest of implementation ...
    
    async def process_conversation(
        self,
        user_email: str,
        user_message: str,
        ai_response: str,
    ) -> MemoryProcessResult:
        """Process conversation with write lock."""
        lock = self._write_locks[user_email]
        
        try:
            await asyncio.wait_for(lock.acquire(), timeout=5.0)
            try:
                # Write operations are exclusive
                result = await self._fact_extractor.extract_facts(
                    user_message, ai_response
                )
                # ... save facts ...
                return result
            finally:
                lock.release()
        except asyncio.TimeoutError:
            logger.warning(f"Write lock timeout for user {user_email}")
            # Return empty result instead of failing
            return MemoryProcessResult(facts=[], summary="")
```

### Test Case
```python
@pytest.mark.asyncio
async def test_concurrent_read_write_memory():
    """Test that reads can proceed during writes."""
    orchestrator = MemoryOrchestrator(db_pool=test_pool)
    await orchestrator.initialize()
    
    user_email = "test@example.com"
    
    # Start write operation
    write_task = asyncio.create_task(
        orchestrator.process_conversation(
            user_email=user_email,
            user_message="Test message",
            ai_response="Test response"
        )
    )
    
    # Multiple reads should be able to proceed
    read_tasks = [
        orchestrator.get_user_context(user_email)
        for _ in range(5)
    ]
    
    # All should complete
    reads, write_result = await asyncio.gather(
        *read_tasks, write_task, return_exceptions=True
    )
    
    # Verify no exceptions
    assert not any(isinstance(r, Exception) for r in reads)
    assert not isinstance(write_result, Exception)
```

---

## 🎯 AREA 3: SearchService - Collection Access

### Problema
```python
# File: apps/backend-rag/backend/services/search/search_service.py
# PROBLEMA: Accesso concorrente a collezioni durante ingestion può causare corruzione

async def search(
    self,
    query: str,
    user_level: int,
    limit: int = 5,
    collection_override: str | None = None,
) -> dict[str, Any]:
    # Nessun lock durante search mentre ingestion può essere in corso
    collection_name = await self.query_router.route(query, user_level)
    results = await self.collection_manager.search(collection_name, ...)
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Read-write lock per collezioni
# 2. Lock durante ingestion (write)
# 3. Lock durante search (read) - può essere concorrente

from collections import defaultdict
import asyncio

class CollectionManager:
    def __init__(self, qdrant_url: str):
        # ... existing code ...
        self._collection_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._collection_read_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(20)  # Allow 20 concurrent reads
        )
    
    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search with read lock."""
        semaphore = self._collection_read_semaphores[collection_name]
        
        async with semaphore:
            # Multiple searches can proceed concurrently
            return await self._do_search(collection_name, query_embedding, limit)
    
    async def ingest_documents(
        self,
        collection_name: str,
        documents: list[dict],
    ) -> dict[str, Any]:
        """Ingest with write lock."""
        lock = self._collection_locks[collection_name]
        
        try:
            await asyncio.wait_for(lock.acquire(), timeout=30.0)
            try:
                # Exclusive write access
                return await self._do_ingest(collection_name, documents)
            finally:
                lock.release()
        except asyncio.TimeoutError:
            raise RuntimeError(f"Ingestion lock timeout for {collection_name}")
```

### Test Case
```python
@pytest.mark.asyncio
async def test_concurrent_search_during_ingestion():
    """Test that searches can proceed during ingestion."""
    collection_manager = CollectionManager(qdrant_url=test_qdrant_url)
    collection_name = "test_collection"
    
    # Start ingestion
    ingest_task = asyncio.create_task(
        collection_manager.ingest_documents(
            collection_name=collection_name,
            documents=[{"id": i, "text": f"doc {i}"} for i in range(100)]
        )
    )
    
    # Multiple searches should be able to proceed
    search_tasks = [
        collection_manager.search(
            collection_name=collection_name,
            query_embedding=[0.1] * 1536,
            limit=5
        )
        for _ in range(10)
    ]
    
    # All should complete
    searches, ingest_result = await asyncio.gather(
        *search_tasks, ingest_task, return_exceptions=True
    )
    
    # Verify no exceptions
    assert not any(isinstance(s, Exception) for s in searches)
    assert not isinstance(ingest_result, Exception)
```

---

## 🎯 AREA 4: ConversationSave - Cache-DB Consistency

### Problema
```python
# File: apps/backend-rag/backend/app/routers/conversations.py
# Linea ~191-206

# PROBLEMA: Race condition tra memory cache e DB save
mem_cache = get_memory_cache()
for msg in request.messages:
    mem_cache.add_message(session_id, msg.get("role"), msg.get("content"))

# Poi save to DB - nessuna transazione atomica
async with db_pool.acquire() as conn:
    await conn.execute("INSERT INTO conversations ...")
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Two-phase commit pattern o eventual consistency
# 2. Transaction log per recovery
# 3. Retry mechanism per consistency

import asyncio
from datetime import datetime

async def save_conversation(
    request: SaveConversationRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
):
    """Save conversation with atomic cache-DB consistency."""
    user_email = current_user["email"]
    session_id = request.session_id or str(uuid.uuid4())
    
    # Phase 1: Save to cache (fast, always succeeds)
    mem_cache = get_memory_cache()
    try:
        for msg in request.messages:
            mem_cache.add_message(
                session_id, msg.get("role", "unknown"), msg.get("content", "")
            )
    except Exception as e:
        logger.warning(f"Cache save failed: {e}")
        # Continue - DB save is more important
    
    # Phase 2: Save to DB with retry
    conversation_id = None
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    async with conn.transaction():
                        row = await conn.fetchrow(
                            """
                            INSERT INTO conversations (user_id, session_id, messages, metadata, created_at)
                            VALUES ($1, $2, $3, $4, $5)
                            RETURNING id
                            """,
                            user_email,
                            session_id,
                            request.messages,
                            request.metadata or {},
                            datetime.now(),
                        )
                        conversation_id = row["id"]
                        
                        # Mark cache as synced
                        mem_cache.mark_synced(session_id, conversation_id)
                        
                break  # Success
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"DB save failed after {max_retries} attempts: {e}")
                # Queue for async retry
                await queue_retry_save(user_email, session_id, request.messages)
            else:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    return {
        "success": conversation_id is not None,
        "conversation_id": conversation_id,
        "messages_saved": len(request.messages),
    }
```

### Test Case
```python
@pytest.mark.asyncio
async def test_cache_db_consistency_race():
    """Test that cache and DB stay consistent under concurrent saves."""
    # Simulate concurrent saves for same session
    session_id = "test_session"
    tasks = [
        save_conversation(
            request=SaveConversationRequest(
                messages=[{"role": "user", "content": f"Message {i}"}],
                session_id=session_id
            ),
            current_user={"email": "test@example.com"},
            db_pool=test_pool
        )
        for i in range(5)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verify consistency
    # Check cache
    cache_messages = mem_cache.get_messages(session_id)
    
    # Check DB
    async with test_pool.acquire() as conn:
        db_row = await conn.fetchrow(
            "SELECT messages FROM conversations WHERE session_id = $1",
            session_id
        )
        db_messages = db_row["messages"] if db_row else []
    
    # Should be consistent (all messages in both)
    assert len(cache_messages) == len(db_messages)
```

---

## 🎯 AREA 5: CollectiveMemoryService - Fact Promotion

### Problema
```python
# File: apps/backend-rag/backend/services/memory/collective_memory_service.py
# PROBLEMA: Race condition quando multiple utenti confermano stesso fatto simultaneamente

async def contribute_fact(
    self,
    user_email: str,
    content: str,
    category: str = "general",
) -> dict[str, Any]:
    # Nessun lock - multiple contributes possono causare duplicate promotions
    fact = await self._find_or_create_fact(content)
    await self._add_source(fact.id, user_email)
    
    if fact.source_count >= 3 and not fact.is_promoted:
        fact.is_promoted = True  # RACE CONDITION QUI
        await self._promote_fact(fact.id)
```

### Fix Richiesto
```python
# IMPLEMENTARE:
# 1. Database-level lock (SELECT FOR UPDATE)
# 2. Atomic increment con check
# 3. Idempotent promotion

async def contribute_fact(
    self,
    user_email: str,
    content: str,
    category: str = "general",
) -> dict[str, Any]:
    """Contribute fact with atomic promotion check."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            # Use SELECT FOR UPDATE to lock row
            fact = await conn.fetchrow(
                """
                SELECT id, source_count, is_promoted
                FROM collective_memories
                WHERE content_hash = $1
                FOR UPDATE
                """,
                content_hash
            )
            
            if fact:
                fact_id = fact["id"]
                # Check if user already contributed
                existing_source = await conn.fetchrow(
                    """
                    SELECT id FROM collective_memory_sources
                    WHERE memory_id = $1 AND user_email = $2
                    """,
                    fact_id, user_email
                )
                
                if not existing_source:
                    # Add source atomically
                    await conn.execute(
                        """
                        INSERT INTO collective_memory_sources (memory_id, user_email)
                        VALUES ($1, $2)
                        """,
                        fact_id, user_email
                    )
                    
                    # Atomic increment with promotion check
                    updated = await conn.fetchrow(
                        """
                        UPDATE collective_memories
                        SET source_count = source_count + 1,
                            last_confirmed_at = NOW(),
                            is_promoted = CASE
                                WHEN source_count + 1 >= 3 THEN TRUE
                                ELSE is_promoted
                            END
                        WHERE id = $1
                        RETURNING id, source_count, is_promoted
                        """,
                        fact_id
                    )
                    
                    # Only promote if just crossed threshold
                    if updated["is_promoted"] and not fact["is_promoted"]:
                        await self._trigger_promotion_event(updated["id"])
            else:
                # Create new fact
                fact_id = await conn.fetchval(
                    """
                    INSERT INTO collective_memories (content, content_hash, category, source_count)
                    VALUES ($1, $2, $3, 1)
                    RETURNING id
                    """,
                    content, content_hash, category
                )
                
                await conn.execute(
                    """
                    INSERT INTO collective_memory_sources (memory_id, user_email)
                    VALUES ($1, $2)
                    """,
                    fact_id, user_email
                )
    
    return {"fact_id": fact_id, "promoted": updated.get("is_promoted", False)}
```

### Test Case
```python
@pytest.mark.asyncio
async def test_concurrent_fact_promotion():
    """Test that fact promotion is atomic."""
    service = CollectiveMemoryService(pool=test_pool)
    content = "Test fact"
    
    # 5 users contribute simultaneously
    tasks = [
        service.contribute_fact(
            user_email=f"user{i}@example.com",
            content=content,
            category="test"
        )
        for i in range(5)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verify only one promotion happened
    async with test_pool.acquire() as conn:
        fact = await conn.fetchrow(
            "SELECT source_count, is_promoted FROM collective_memories WHERE content = $1",
            content
        )
        
        assert fact["source_count"] == 5
        assert fact["is_promoted"] == True  # Should be promoted after 3+
    
    # Verify no duplicate sources
    sources = await conn.fetch(
        "SELECT user_email FROM collective_memory_sources WHERE memory_id = $1",
        fact["id"]
    )
    assert len(sources) == 5  # No duplicates
```

---

## 📊 METRICHE DA IMPLEMENTARE

```python
# File: apps/backend-rag/backend/app/metrics.py

# Race condition metrics
memory_lock_timeout_total = Counter(
    "zantara_memory_lock_timeout_total",
    "Number of memory lock timeouts",
    ["user_id"]
)

memory_lock_contention_seconds = Histogram(
    "zantara_memory_lock_contention_seconds",
    "Time spent waiting for memory locks",
    ["operation"]
)

collection_lock_timeout_total = Counter(
    "zantara_collection_lock_timeout_total",
    "Number of collection lock timeouts",
    ["collection_name"]
)

cache_db_consistency_errors_total = Counter(
    "zantara_cache_db_consistency_errors_total",
    "Number of cache-DB consistency errors",
    ["session_id"]
)
```

---

## ✅ CHECKLIST DI COMPLETAMENTO

- [ ] Implementato asyncio.Lock per AgenticRAGOrchestrator
- [ ] Implementato read-write lock per MemoryOrchestrator
- [ ] Implementato collection locks per SearchService
- [ ] Implementato two-phase commit per ConversationSave
- [ ] Implementato SELECT FOR UPDATE per CollectiveMemoryService
- [ ] Aggiunti test per ogni race condition
- [ ] Implementate metriche di monitoring
- [ ] Documentato comportamento locking
- [ ] Verificato performance (<10ms overhead)
- [ ] Aggiunto alerting su lock timeouts

---

## 🚨 ALERTING RULES

```yaml
# File: config/prometheus/alerts.yml

- alert: HighMemoryLockContention
  expr: rate(zantara_memory_lock_contention_seconds_sum[5m]) > 0.1
  for: 5m
  annotations:
    summary: "High memory lock contention detected"
    description: "Memory operations are waiting too long for locks"

- alert: CollectionLockTimeouts
  expr: rate(zantara_collection_lock_timeout_total[5m]) > 0
  for: 2m
  annotations:
    summary: "Collection lock timeouts detected"
    description: "Ingestion operations are timing out on lock acquisition"
```

---

*Prompt creato: 2025-12-28*  
*Prossimo step: Implementazione fix*

