# 🎯 PROMPT COMPLETI PER REFACTORING

**Data**: 2025-12-07
**Uso**: Copia il prompt completo del refactoring che vuoi eseguire e assegnalo a un'AI

---

## 📋 INDICE

1. [Split SearchService (God Object)](#1-split-searchservice-god-object)
2. [Standardize Database Access](#2-standardize-database-access)
3. [Global State → Dependency Injection](#3-global-state--dependency-injection)
4. [Migration System Centralizzato](#4-migration-system-centralizzato)
5. [QdrantClient Sync → Async](#5-qdrantclient-sync--async)
6. [Extract Duplicate Routing Logic](#6-extract-duplicate-routing-logic)
7. [Implement NotificationHub Real](#7-implement-notificationhub-real)
8. [Remove Singleton Pattern](#8-remove-singleton-pattern)

---

# 1. SPLIT SEARCHSERVICE (GOD OBJECT)

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di refactorizzare SearchService.

## CONTESTO

Il file `apps/backend-rag/backend/services/search_service.py` è un "God Object" di 1017 linee che viola il Single Responsibility Principle.

**Problema Attuale:**
- Single class gestisce troppe responsabilità:
  - Collection management (17 collections)
  - Search logic (core functionality)
  - Conflict resolution
  - Health monitoring
  - Cultural insights management
  - Query routing integration
  - Warmup logic

**Problemi Causati:**
- Impossibile testare isolatamente (devi mockare tutto)
- Modifiche rischiose (cambiare una cosa può rompere altre)
- Performance issues (import lento, memory footprint alto)
- Onboarding difficile (nuovo dev impiega giorni invece di ore)
- Test coverage basso (< 50%)

## OBIETTIVO

Split SearchService in servizi focalizzati seguendo Single Responsibility Principle:

1. **SearchService** (~200 LOC)
   - Core search functionality ONLY
   - Search documents in collections
   - Return search results
   - NO collection management
   - NO conflict resolution
   - NO health monitoring

2. **CollectionManager** (~150 LOC)
   - Collection lifecycle (create, delete, list)
   - Collection metadata management
   - Collection validation
   - NO search logic

3. **ConflictResolver** (~100 LOC)
   - Conflict detection between documents
   - Conflict resolution strategies
   - Conflict reporting
   - NO search logic
   - NO collection management

4. **CollectionHealthMonitor** (già esiste in `services/collection_health_service.py`)
   - Integrare meglio con nuovo SearchService
   - Health checks per collections
   - NO search logic

5. **CulturalInsightsService** (~150 LOC)
   - Extract cultural insights logic da SearchService
   - Cultural context extraction
   - Cultural relevance scoring
   - NO search logic

6. **QueryRouterIntegration** (~100 LOC)
   - Extract query routing logic
   - Route queries to appropriate collections
   - Query preprocessing
   - NO search logic

## REGOLE DEL PROGETTO

Leggi PRIMA questi file:
- `AI_ONBOARDING.md` - Regole del progetto
- `docs/ARCHITECTURE.md` - Architettura sistema
- `apps/backend-rag/backend/services/search_service.py` - File da refactorizzare

**Regole Critiche:**
1. NO hardcoding: usa `app.core.config.settings`
2. Schema First: usa SQLModel per database
3. Dependency Discipline: aggiungi dipendenze a `requirements.txt`
4. Root Protection: codice in `apps/backend-rag/backend/services/`
5. Documentation: aggiorna `docs/ARCHITECTURE.md` se cambi architettura

## METODOLOGIA

### Fase 1: ANALISI (2-3 ore)
1. Leggi completamente `search_service.py`
2. Identifica TUTTE le responsabilità
3. Mappa dipendenze tra metodi
4. Identifica quali metodi appartengono a quale servizio
5. Crea mappa mentale della separazione

### Fase 2: CREAZIONE SERVIZI (8-10 ore)
1. Crea `services/collection_manager.py`
   - Sposta metodi collection management
   - Mantieni interfaccia pubblica compatibile
   - Aggiungi type hints completi
   - Aggiungi docstring

2. Crea `services/conflict_resolver.py`
   - Sposta logica conflict resolution
   - Estrai in classe separata
   - Mantieni compatibilità API

3. Crea `services/cultural_insights_service.py`
   - Sposta logica cultural insights
   - Estrai in servizio dedicato

4. Crea `services/query_router_integration.py`
   - Sposta logica query routing
   - Estrai integrazione con query router

5. Refactor `services/search_service.py`
   - Mantieni SOLO core search logic
   - Usa dependency injection per altri servizi
   - Mantieni interfaccia pubblica compatibile

### Fase 3: INTEGRAZIONE (3-4 ore)
1. Aggiorna `app/dependencies.py`
   - Aggiungi dependency injection per nuovi servizi
   - Mantieni backward compatibility

2. Aggiorna tutti i router che usano SearchService
   - Verifica che funzionino con nuovo SearchService
   - Aggiorna import se necessario

3. Aggiorna `app/main_cloud.py`
   - Inizializza nuovi servizi
   - Passa come dipendenze a SearchService

### Fase 4: TESTING (2-3 ore)
1. Crea test per ogni nuovo servizio
   - Test isolati per CollectionManager
   - Test isolati per ConflictResolver
   - Test isolati per CulturalInsightsService
   - Test isolati per QueryRouterIntegration

2. Aggiorna test esistenti per SearchService
   - Mock nuovi servizi come dipendenze
   - Verifica che test passino

3. Esegui test integration
   - Verifica che tutto funzioni insieme
   - Verifica performance (non deve degradare)

## STRUTTURA CODICE ATTESA

### SearchService (Dopo Refactoring)
```python
"""
SearchService - Core Search Functionality Only
Handles document search in Qdrant collections.
"""

from typing import Any, Optional
from services.collection_manager import CollectionManager
from services.conflict_resolver import ConflictResolver
from services.cultural_insights_service import CulturalInsightsService
from services.query_router_integration import QueryRouterIntegration

class SearchService:
    """
    Core search service for document retrieval.

    Responsibilities:
    - Search documents in collections
    - Return search results
    - Handle search parameters

    Does NOT handle:
    - Collection management (use CollectionManager)
    - Conflict resolution (use ConflictResolver)
    - Health monitoring (use CollectionHealthMonitor)
    """

    def __init__(
        self,
        qdrant_client: Any,
        collection_manager: CollectionManager,
        conflict_resolver: Optional[ConflictResolver] = None,
        cultural_insights: Optional[CulturalInsightsService] = None,
        query_router: Optional[QueryRouterIntegration] = None,
    ):
        self.qdrant_client = qdrant_client
        self.collection_manager = collection_manager
        self.conflict_resolver = conflict_resolver
        self.cultural_insights = cultural_insights
        self.query_router = query_router

    async def search(
        self,
        query: str,
        collection_name: str,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Search documents in specified collection.

        Args:
            query: Search query text
            collection_name: Collection to search in
            limit: Maximum results to return
            filters: Optional metadata filters

        Returns:
            Search results with documents and scores
        """
        # Core search logic ONLY
        # NO collection management
        # NO conflict resolution
        # NO health monitoring
        pass
```

### CollectionManager (Nuovo Servizio)
```python
"""
CollectionManager - Collection Lifecycle Management
Handles creation, deletion, and management of Qdrant collections.
"""

class CollectionManager:
    """
    Manages Qdrant collection lifecycle.

    Responsibilities:
    - Create collections
    - Delete collections
    - List collections
    - Validate collection metadata
    """

    async def create_collection(self, name: str, metadata: dict) -> bool:
        """Create new collection"""
        pass

    async def delete_collection(self, name: str) -> bool:
        """Delete collection"""
        pass

    async def list_collections(self) -> list[str]:
        """List all collections"""
        pass
```

## CHECKLIST COMPLETA

### Pre-Refactoring
- [ ] Leggi completamente `search_service.py`
- [ ] Leggi `AI_ONBOARDING.md` e `docs/ARCHITECTURE.md`
- [ ] Esegui tutti i test esistenti (devono passare)
- [ ] Crea branch: `refactor/split-search-service`

### Durante Refactoring
- [ ] Crea `CollectionManager` con test
- [ ] Crea `ConflictResolver` con test
- [ ] Crea `CulturalInsightsService` con test
- [ ] Crea `QueryRouterIntegration` con test
- [ ] Refactor `SearchService` (mantieni compatibilità API)
- [ ] Aggiorna `dependencies.py`
- [ ] Aggiorna `main_cloud.py`
- [ ] Aggiorna router che usano SearchService

### Post-Refactoring
- [ ] Tutti i test passano
- [ ] Test coverage >= 80% per ogni servizio
- [ ] Nessun import rotto
- [ ] Performance non degradata (verifica con benchmark)
- [ ] Aggiorna `docs/ARCHITECTURE.md`
- [ ] Code review
- [ ] Merge in main

## TEST STRATEGY

### Unit Tests
```python
# Test CollectionManager isolato
def test_collection_manager_create():
    manager = CollectionManager(qdrant_client=mock_qdrant)
    result = await manager.create_collection("test", {})
    assert result is True

# Test SearchService con mock dependencies
def test_search_service_search():
    manager = Mock(CollectionManager)
    service = SearchService(
        qdrant_client=mock_qdrant,
        collection_manager=manager
    )
    results = await service.search("test", "collection")
    assert "documents" in results
```

### Integration Tests
```python
# Test che tutti i servizi funzionano insieme
async def test_search_workflow_complete():
    # Setup tutti i servizi
    manager = CollectionManager(...)
    resolver = ConflictResolver(...)
    service = SearchService(..., manager, resolver)

    # Test workflow completo
    results = await service.search(...)
    assert results is not None
```

## ROLLBACK PLAN

Se qualcosa va storto:
1. Mantieni branch originale
2. Feature flag per nuovo SearchService
3. Possibilità di rollback immediato
4. Monitora errori in produzione

## OUTPUT ATTESO

1. **File Creati:**
   - `services/collection_manager.py`
   - `services/conflict_resolver.py`
   - `services/cultural_insights_service.py`
   - `services/query_router_integration.py`

2. **File Modificati:**
   - `services/search_service.py` (ridotto a ~200 LOC)
   - `app/dependencies.py`
   - `app/main_cloud.py`
   - Router che usano SearchService

3. **Test Creati:**
   - Test per ogni nuovo servizio
   - Test aggiornati per SearchService

4. **Documentazione:**
   - `docs/ARCHITECTURE.md` aggiornato
   - Docstring completi in ogni servizio

## CRITERI DI SUCCESSO

✅ SearchService < 250 LOC
✅ Ogni servizio ha una responsabilità chiara
✅ Test coverage >= 80% per ogni servizio
✅ Tutti i test esistenti passano
✅ Performance non degradata
✅ Nessun breaking change API
✅ Codice review approvato

## TEMPO STIMATO

- Analisi: 2-3 ore
- Creazione servizi: 8-10 ore
- Integrazione: 3-4 ore
- Testing: 2-3 ore
- **Totale: 15-20 ore**

---

INIZIA QUI:
1. Leggi `apps/backend-rag/backend/services/search_service.py` completamente
2. Crea mappa mentale delle responsabilità
3. Inizia con CollectionManager (più semplice)
4. Procedi incrementalmente
5. Testa dopo ogni step
```

---

# 2. STANDARDIZE DATABASE ACCESS

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di standardizzare l'accesso al database.

## CONTESTO

Il progetto ha accesso database inconsistente:
- Alcuni servizi usano `psycopg2` (sync) → BLOCCA event loop
- Altri usano `asyncpg` (async) → CORRETTO
- Alcuni creano nuove connessioni ogni chiamata → Connection leaks
- Altri usano connection pooling → CORRETTO

**File da Migrare:**
1. `services/auto_crm_service.py` (usa `psycopg2`, no pooling)
2. `services/context/context_builder.py` (usa `psycopg2`, no pooling)

**File Già Migrati (riferimento):**
- `services/memory_service_postgres.py` (usa `asyncpg` con pooling ✅)
- `services/golden_answer_service.py` (usa `asyncpg` con pooling ✅)
- `app/routers/crm_*.py` (già migrati a `asyncpg` ✅)

**Problemi Causati:**
- Connection leaks → Database pool esaurito → App crasha
- Performance degradation → Ogni chiamata = nuova connessione TCP (~10-50ms)
- Event loop bloccato → Concorrenza = 0 → App lenta
- Inconsistenza → Error handling diverso → Debugging difficile

## OBIETTIVO

Migrare TUTTI i servizi a:
1. `asyncpg` (async, non blocca event loop)
2. Connection pooling (riutilizzo connessioni)
3. Pattern consistente (stesso error handling)

## REGOLE DEL PROGETTO

Leggi PRIMA:
- `AI_ONBOARDING.md`
- `apps/backend-rag/backend/app/dependencies.py` (vedi `get_database_pool`)
- `apps/backend-rag/backend/services/memory_service_postgres.py` (esempio corretto)

**Pattern Standard:**
```python
from app.dependencies import get_database_pool
import asyncpg

async def my_function(db_pool: asyncpg.Pool = Depends(get_database_pool)):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM table WHERE id = $1", id)
        return dict(row)
```

## METODOLOGIA

### Fase 1: ANALISI (1-2 ore)
1. Leggi `auto_crm_service.py` completamente
2. Identifica TUTTE le query database
3. Mappa dipendenze (quali funzioni chiamano altre)
4. Identifica transaction boundaries
5. Leggi `context_builder.py` completamente
6. Stesso processo per context_builder

### Fase 2: MIGRAZIONE auto_crm_service.py (4-6 ore)

**Step 1: Sostituisci Import**
```python
# PRIMA
import psycopg2
from psycopg2.extras import RealDictCursor

# DOPO
import asyncpg
from app.dependencies import get_database_pool
```

**Step 2: Aggiorna Metodi a Async**
```python
# PRIMA
def extract_crm_data(conversation_id: str):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM ...", (conversation_id,))
    result = cursor.fetchone()
    conn.close()
    return result

# DOPO
async def extract_crm_data(
    conversation_id: str,
    db_pool: asyncpg.Pool = Depends(get_database_pool)
):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM ... WHERE id = $1",
            conversation_id
        )
        return dict(row) if row else None
```

**Step 3: Aggiorna Query Syntax**
```python
# PRIMA (psycopg2)
cursor.execute("SELECT * FROM table WHERE id = %s", (id,))
cursor.execute("INSERT INTO table (col1, col2) VALUES (%s, %s)", (val1, val2))

# DOPO (asyncpg)
row = await conn.fetchrow("SELECT * FROM table WHERE id = $1", id)
await conn.execute(
    "INSERT INTO table (col1, col2) VALUES ($1, $2)",
    val1, val2
)
```

**Step 4: Gestisci Transactions**
```python
# PRIMA
conn = psycopg2.connect(...)
try:
    cursor.execute("BEGIN")
    cursor.execute("INSERT ...")
    cursor.execute("UPDATE ...")
    conn.commit()
except:
    conn.rollback()

# DOPO
async with db_pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("INSERT ...")
        await conn.execute("UPDATE ...")
        # Auto-commit se tutto OK, auto-rollback se exception
```

**Step 5: Aggiorna Error Handling**
```python
# PRIMA
except psycopg2.IntegrityError as e:
    raise ValueError(f"Duplicate entry: {e}")

# DOPO
except asyncpg.UniqueViolationError as e:
    raise ValueError(f"Duplicate entry: {e}")
```

### Fase 3: MIGRAZIONE context_builder.py (3-4 ore)
Stesso processo di auto_crm_service.py

### Fase 4: TESTING (2-3 ore)
1. Crea test per ogni metodo migrato
2. Verifica che funzioni con connection pool
3. Verifica error handling
4. Verifica performance (non deve degradare)

## STRUTTURA CODICE ATTESA

### auto_crm_service.py (Dopo Migrazione)
```python
"""
AutoCRMService - Automatic CRM Data Extraction
Uses asyncpg with connection pooling for database access.
"""

import asyncpg
from typing import Optional
from fastapi import Depends
from app.dependencies import get_database_pool

class AutoCRMService:
    """
    Extracts CRM data from conversations automatically.
    Uses asyncpg for async database access.
    """

    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        self.db_pool = db_pool

    async def extract_crm_data(
        self,
        conversation_id: str,
        db_pool: asyncpg.Pool = Depends(get_database_pool)
    ) -> Optional[dict]:
        """
        Extract CRM data from conversation.

        Args:
            conversation_id: ID of conversation to process
            db_pool: Database connection pool (injected)

        Returns:
            Extracted CRM data or None
        """
        async with db_pool.acquire() as conn:
            # Use asyncpg syntax: $1, $2 instead of %s
            row = await conn.fetchrow(
                """
                SELECT c.*, p.*
                FROM clients c
                LEFT JOIN practices p ON p.client_id = c.id
                WHERE c.id = $1
                """,
                conversation_id
            )

            if not row:
                return None

            return dict(row)

    async def create_client(
        self,
        client_data: dict,
        db_pool: asyncpg.Pool = Depends(get_database_pool)
    ) -> dict:
        """Create new client with transaction"""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Insert client
                client_row = await conn.fetchrow(
                    """
                    INSERT INTO clients (email, full_name, client_type)
                    VALUES ($1, $2, $3)
                    RETURNING *
                    """,
                    client_data["email"],
                    client_data["full_name"],
                    client_data["client_type"]
                )

                # Insert related data in same transaction
                # ...

                return dict(client_row)
```

## CHECKLIST COMPLETA

### Pre-Migrazione
- [ ] Leggi file da migrare completamente
- [ ] Leggi esempi già migrati (memory_service_postgres.py)
- [ ] Esegui test esistenti (baseline)
- [ ] Crea branch: `refactor/migrate-db-access`

### Durante Migrazione
- [ ] Sostituisci import psycopg2 → asyncpg
- [ ] Converti metodi sync → async
- [ ] Aggiorna query syntax (%s → $1)
- [ ] Aggiorna error handling
- [ ] Usa connection pooling (get_database_pool)
- [ ] Gestisci transactions correttamente
- [ ] Aggiorna chiamate a metodi migrati (devono essere await)

### Post-Migrazione
- [ ] Tutti i test passano
- [ ] Nessun connection leak (verifica con monitoring)
- [ ] Performance migliorata (benchmark)
- [ ] Error handling consistente
- [ ] Code review
- [ ] Merge in main

## TEST STRATEGY

### Unit Tests
```python
import pytest
import asyncpg
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_extract_crm_data():
    # Mock connection pool
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock query result
    mock_row = {"id": 1, "email": "test@example.com"}
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    service = AutoCRMService()
    result = await service.extract_crm_data("conv_123", db_pool=mock_pool)

    assert result == mock_row
    mock_conn.fetchrow.assert_called_once()
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_extract_crm_data_integration(db_pool):
    """Test with real database"""
    service = AutoCRMService()
    result = await service.extract_crm_data("conv_123", db_pool=db_pool)
    assert result is not None
```

## ROLLBACK PLAN

1. Mantieni codice originale in branch
2. Feature flag per nuovo codice
3. Monitora connection pool usage
4. Possibilità rollback immediato

## OUTPUT ATTESO

1. **File Modificati:**
   - `services/auto_crm_service.py` (asyncpg + pooling)
   - `services/context/context_builder.py` (asyncpg + pooling)

2. **Test Aggiornati:**
   - Test per auto_crm_service
   - Test per context_builder

3. **Documentazione:**
   - Pattern standard documentato
   - Esempi di uso

## CRITERI DI SUCCESSO

✅ Zero psycopg2 usage rimanente
✅ Tutti i servizi usano asyncpg + pooling
✅ Zero connection leaks
✅ Performance migliorata (benchmark)
✅ Tutti i test passano
✅ Error handling consistente

## TEMPO STIMATO

- Analisi: 1-2 ore
- Migrazione auto_crm_service: 4-6 ore
- Migrazione context_builder: 3-4 ore
- Testing: 2-3 ore
- **Totale: 10-15 ore**

---

INIZIA QUI:
1. Leggi `memory_service_postgres.py` come riferimento
2. Leggi `auto_crm_service.py` completamente
3. Inizia migrazione metodo per metodo
4. Testa dopo ogni metodo migrato
5. Procedi incrementalmente
```

---

# 3. GLOBAL STATE → DEPENDENCY INJECTION

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di rimuovere global state e implementare dependency injection.

## CONTESTO

Il file `apps/backend-rag/backend/core/cache.py` usa global state:
```python
cache = CacheService()  # Global singleton (linea 148)
_memory_cache = {}  # Module-level mutable state (linea 22)
```

**Problemi Causati:**
- Test flaky (stato condiviso tra test)
- Race conditions (multi-threaded scenarios)
- Impossibile mockare (test usano cache reale)
- Impossibile avere istanze multiple (testing difficile)

**File da Modificare:**
- `core/cache.py` (rimuovere global state)
- Tutti i file che usano `from core.cache import cache` (aggiornare)

## OBIETTIVO

Sostituire global state con dependency injection:
1. Rimuovere `cache = CacheService()` globale
2. Creare factory function `get_cache_service()`
3. Usare FastAPI dependency injection
4. Mantenere backward compatibility (deprecation warning)

## REGOLE DEL PROGETTO

Leggi PRIMA:
- `AI_ONBOARDING.md`
- `apps/backend-rag/backend/app/dependencies.py` (vedi pattern DI)
- `apps/backend-rag/backend/core/cache.py` (file da refactorizzare)

**Pattern Standard FastAPI DI:**
```python
from fastapi import Depends

def get_cache_service() -> CacheService:
    return CacheService()

# In endpoint
async def my_endpoint(cache: CacheService = Depends(get_cache_service)):
    value = cache.get("key")
```

## METODOLOGIA

### Fase 1: ANALISI (1 ora)
1. Leggi `cache.py` completamente
2. Trova TUTTI i file che importano `from core.cache import cache`
3. Identifica come viene usato `cache` globale
4. Mappa dipendenze

### Fase 2: REFACTORING cache.py (1-2 ore)

**Step 1: Crea Factory Function**
```python
# PRIMA
cache = CacheService()  # Global

# DOPO
_cache_instance: Optional[CacheService] = None

def get_cache_service() -> CacheService:
    """
    Factory function for CacheService.
    Returns singleton instance (for backward compatibility).

    For new code, use FastAPI dependency injection:
    async def endpoint(cache: CacheService = Depends(get_cache_service)):
        ...
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance

# Backward compatibility (deprecated)
cache = property(lambda self: get_cache_service())
```

**Step 2: Rimuovi Module-Level State**
```python
# PRIMA
_memory_cache = {}  # Module-level

# DOPO
# Move to CacheService instance
class CacheService:
    def __init__(self):
        self._memory_cache = {}  # Instance-level
```

**Step 3: Aggiorna @cached Decorator**
```python
# PRIMA
@cached(ttl=300)
def my_function():
    pass

# DOPO (funziona ancora, ma usa DI internamente)
@cached(ttl=300)
def my_function():
    # Internally uses get_cache_service()
    pass
```

### Fase 3: AGGIORNA USAGE (1-2 ore)
1. Trova tutti i file che usano `from core.cache import cache`
2. Aggiorna a dependency injection dove possibile
3. Mantieni backward compatibility con deprecation warning

### Fase 4: TESTING (1 ora)
1. Crea test con dependency injection
2. Verifica backward compatibility
3. Verifica che test siano isolati

## STRUTTURA CODICE ATTESA

### cache.py (Dopo Refactoring)
```python
"""
Cache Service - Redis and In-Memory Caching
Uses dependency injection instead of global state.
"""

from typing import Optional
from fastapi import Depends

class CacheService:
    """
    Cache service with Redis and in-memory fallback.

    Usage with DI:
    async def endpoint(cache: CacheService = Depends(get_cache_service)):
        value = cache.get("key")
    """

    def __init__(self):
        self._memory_cache = {}  # Instance-level, not module-level
        self._redis_client = None  # Lazy initialization

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        # Check memory cache first
        if key in self._memory_cache:
            return self._memory_cache[key]

        # Check Redis
        # ...

    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache"""
        # Set in memory cache
        self._memory_cache[key] = value

        # Set in Redis
        # ...

# Factory function for dependency injection
_cache_instance: Optional[CacheService] = None

def get_cache_service() -> CacheService:
    """
    Factory function for CacheService.
    Returns singleton instance.

    For FastAPI endpoints, use dependency injection:
    async def endpoint(cache: CacheService = Depends(get_cache_service)):
        ...
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance

# Backward compatibility (deprecated)
# Use get_cache_service() or DI instead
import warnings
def _get_cache_deprecated():
    warnings.warn(
        "Direct import of 'cache' is deprecated. "
        "Use 'get_cache_service()' or dependency injection.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_cache_service()

cache = property(lambda self: _get_cache_deprecated())
```

### Usage in Router (Dopo Refactoring)
```python
# PRIMA
from core.cache import cache

@router.get("/data")
async def get_data():
    value = cache.get("key")  # Global state

# DOPO
from core.cache import get_cache_service
from fastapi import Depends

@router.get("/data")
async def get_data(cache: CacheService = Depends(get_cache_service)):
    value = await cache.get("key")  # Dependency injected
```

## CHECKLIST COMPLETA

### Pre-Refactoring
- [ ] Leggi `cache.py` completamente
- [ ] Trova tutti i file che usano `cache` globale
- [ ] Esegui test esistenti (baseline)
- [ ] Crea branch: `refactor/cache-dependency-injection`

### Durante Refactoring
- [ ] Crea `get_cache_service()` factory function
- [ ] Rimuovi `cache = CacheService()` globale
- [ ] Sposta `_memory_cache` a instance-level
- [ ] Aggiorna `@cached` decorator
- [ ] Aggiorna usage in router a DI
- [ ] Aggiungi deprecation warning per backward compatibility

### Post-Refactoring
- [ ] Tutti i test passano
- [ ] Test isolati (ogni test ha sua istanza)
- [ ] Nessuna race condition
- [ ] Backward compatibility mantenuta
- [ ] Code review
- [ ] Merge in main

## TEST STRATEGY

### Unit Tests (Isolati)
```python
@pytest.mark.asyncio
async def test_cache_service_isolated():
    """Test che ogni test ha sua istanza"""
    cache1 = get_cache_service()
    cache2 = get_cache_service()

    # Dovrebbero essere stessa istanza (singleton)
    assert cache1 is cache2

    # Ma possiamo creare istanze separate per testing
    cache3 = CacheService()  # Nuova istanza
    assert cache3 is not cache1

@pytest.mark.asyncio
async def test_cache_with_mock():
    """Test con mock cache"""
    mock_cache = MagicMock()
    mock_cache.get.return_value = "test_value"

    # Possiamo passare mock come dependency
    result = await my_function(cache=mock_cache)
    assert result == "test_value"
```

## ROLLBACK PLAN

1. Mantieni codice originale in branch
2. Backward compatibility con deprecation warning
3. Possibilità rollback immediato

## OUTPUT ATTESO

1. **File Modificati:**
   - `core/cache.py` (DI invece di global state)
   - Router che usano cache (aggiornati a DI)

2. **Test Aggiornati:**
   - Test isolati per cache
   - Test con mock

## CRITERI DI SUCCESSO

✅ Zero global state
✅ Dependency injection implementata
✅ Test isolati (ogni test ha sua istanza)
✅ Nessuna race condition
✅ Backward compatibility mantenuta
✅ Tutti i test passano

## TEMPO STIMATO

- Analisi: 1 ora
- Refactoring cache.py: 1-2 ore
- Aggiorna usage: 1-2 ore
- Testing: 1 ora
- **Totale: 4-6 ore**

---

INIZIA QUI:
1. Leggi `cache.py` completamente
2. Trova tutti gli usage di `cache` globale
3. Crea factory function
4. Aggiorna usage incrementalmente
5. Testa dopo ogni cambio
```

---

# 4. MIGRATION SYSTEM CENTRALIZZATO

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di creare un sistema di migrazione centralizzato.

## CONTESTO

Attualmente ogni migration è uno script standalone:
- `backend/migrations/apply_migration_007.py`
- `backend/migrations/apply_migration_010.py`
- `backend/migrations/apply_migration_012.py`
- ... (7 script totali)

**Problemi:**
- Nessun tracking di migrations applicate
- Rischio di applicare migrations multiple volte
- Nessuna gestione dipendenze tra migrations
- Impossibile rollback automatico
- ~400 LOC duplicate tra script

**SQL Migrations:**
- `backend/db/migrations/007_*.sql`
- `backend/db/migrations/010_*.sql`
- ... (18 file SQL totali)

## OBIETTIVO

Creare sistema centralizzato:
1. `MigrationManager` - Gestisce tracking e applicazione
2. `BaseMigration` - Classe base per eliminare duplicazione
3. Tabella `schema_migrations` - Traccia migrations applicate
4. Supporto dipendenze tra migrations
5. Rollback automatico

## REGOLE DEL PROGETTO

Leggi PRIMA:
- `AI_ONBOARDING.md`
- `apps/backend-rag/backend/migrations/apply_migration_010.py` (esempio esistente)
- `apps/backend-rag/backend/db/migrations/` (SQL files)

**Pattern Standard:**
- Usa `asyncpg` (non psycopg2)
- Usa connection pooling
- Logging strutturato
- Error handling robusto

## METODOLOGIA

### Fase 1: CREA MIGRATION MANAGER (3-4 ore)

**Crea `backend/db/migration_manager.py`:**
```python
"""
Migration Manager - Centralized Migration System
Tracks and applies database migrations safely.
"""

import asyncpg
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MigrationManager:
    """
    Centralized migration management system.

    Features:
    - Tracks applied migrations
    - Handles dependencies
    - Supports rollback
    - Prevents duplicate application
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.migration_log_table = "schema_migrations"
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool"""
        self.pool = await asyncpg.create_pool(self.db_url)

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()

    async def ensure_migration_log(self):
        """Create migration log table if not exists"""
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.migration_log_table} (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    checksum VARCHAR(64),
                    rollback_sql TEXT,
                    applied_by VARCHAR(255) DEFAULT 'system'
                );

                CREATE INDEX IF NOT EXISTS idx_migration_name
                ON {self.migration_log_table}(migration_name);
            """)

    async def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration names"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT migration_name
                FROM {self.migration_log_table}
                ORDER BY applied_at
            """)
            return [row["migration_name"] for row in rows]

    async def apply_migration(
        self,
        migration_name: str,
        sql_file: Path,
        rollback_sql: Optional[str] = None
    ) -> bool:
        """
        Apply migration if not already applied.

        Args:
            migration_name: Name of migration (e.g., "007_add_tables")
            sql_file: Path to SQL file
            rollback_sql: Optional rollback SQL

        Returns:
            True if applied, False if already applied
        """
        # Check if already applied
        applied = await self.get_applied_migrations()
        if migration_name in applied:
            logger.info(f"Migration {migration_name} already applied, skipping")
            return False

        # Read SQL file
        sql_content = sql_file.read_text()

        # Calculate checksum
        import hashlib
        checksum = hashlib.md5(sql_content.encode()).hexdigest()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Apply migration
                await conn.execute(sql_content)

                # Log migration
                await conn.execute(f"""
                    INSERT INTO {self.migration_log_table}
                    (migration_name, checksum, rollback_sql)
                    VALUES ($1, $2, $3)
                """, migration_name, checksum, rollback_sql)

        logger.info(f"✅ Applied migration: {migration_name}")
        return True

    async def rollback_migration(self, migration_name: str) -> bool:
        """Rollback a specific migration"""
        async with self.pool.acquire() as conn:
            # Get rollback SQL
            row = await conn.fetchrow(f"""
                SELECT rollback_sql
                FROM {self.migration_log_table}
                WHERE migration_name = $1
            """, migration_name)

            if not row or not row["rollback_sql"]:
                logger.warning(f"No rollback SQL for {migration_name}")
                return False

            async with conn.transaction():
                # Execute rollback
                await conn.execute(row["rollback_sql"])

                # Remove from log
                await conn.execute(f"""
                    DELETE FROM {self.migration_log_table}
                    WHERE migration_name = $1
                """, migration_name)

        logger.info(f"✅ Rolled back migration: {migration_name}")
        return True
```

### Fase 2: CREA BASE MIGRATION (2-3 ore)

**Crea `backend/db/migration_base.py`:**
```python
"""
Base Migration - Template for Migration Scripts
Eliminates code duplication.
"""

from pathlib import Path
from typing import Optional
import asyncpg
import logging
from db.migration_manager import MigrationManager

logger = logging.getLogger(__name__)

class BaseMigration:
    """
    Base class for migration scripts.
    Eliminates code duplication.
    """

    def __init__(
        self,
        migration_number: int,
        sql_file_name: str,
        rollback_sql: Optional[str] = None
    ):
        self.migration_number = migration_number
        self.migration_name = f"{migration_number:03d}_{sql_file_name}"

        # Resolve SQL file path
        migrations_dir = Path(__file__).parent.parent / "db" / "migrations"
        self.sql_file = migrations_dir / f"{migration_number:03d}_{sql_file_name}.sql"

        if not self.sql_file.exists():
            raise FileNotFoundError(f"Migration file not found: {self.sql_file}")

        self.rollback_sql = rollback_sql

    async def apply(self, manager: MigrationManager) -> bool:
        """
        Apply migration using MigrationManager.

        Args:
            manager: MigrationManager instance

        Returns:
            True if applied, False if already applied
        """
        return await manager.apply_migration(
            migration_name=self.migration_name,
            sql_file=self.sql_file,
            rollback_sql=self.rollback_sql
        )

    async def verify(self, pool: asyncpg.Pool) -> bool:
        """
        Verify migration was applied correctly.

        Override in subclasses for custom verification.
        """
        return True
```

### Fase 3: REFACTOR EXISTING SCRIPTS (2-3 ore)

**Refactor `apply_migration_010.py`:**
```python
"""
Apply Migration 010 - Fix Team Members Schema
Uses MigrationManager instead of standalone script.
"""

import asyncio
import logging
from pathlib import Path
from app.core.config import settings
from db.migration_manager import MigrationManager
from db.migration_base import BaseMigration

logger = logging.getLogger(__name__)

async def main():
    """Apply migration 010"""
    if not settings.database_url:
        logger.error("DATABASE_URL not set")
        return

    manager = MigrationManager(db_url=settings.database_url)
    await manager.connect()

    try:
        # Ensure migration log table exists
        await manager.ensure_migration_log()

        # Create migration instance
        migration = BaseMigration(
            migration_number=10,
            sql_file_name="fix_team_members_schema",
            rollback_sql="""
                -- Rollback SQL here
                ALTER TABLE team_members DROP COLUMN IF EXISTS new_column;
            """
        )

        # Apply migration
        applied = await migration.apply(manager)

        if applied:
            logger.info("✅ Migration 010 applied successfully")
        else:
            logger.info("ℹ️ Migration 010 already applied")

        # Verify
        verified = await migration.verify(manager.pool)
        if verified:
            logger.info("✅ Migration 010 verified")
        else:
            logger.warning("⚠️ Migration 010 verification failed")

    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Fase 4: CREA CLI TOOL (1-2 ore)

**Crea `backend/scripts/migrate.py`:**
```python
"""
Migration CLI Tool
Apply all pending migrations.
"""

import asyncio
import logging
from pathlib import Path
from app.core.config import settings
from db.migration_manager import MigrationManager

logger = logging.getLogger(__name__)

async def apply_all_pending():
    """Apply all pending migrations"""
    manager = MigrationManager(db_url=settings.database_url)
    await manager.connect()

    try:
        await manager.ensure_migration_log()

        # Find all migration files
        migrations_dir = Path(__file__).parent.parent / "db" / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        applied = await manager.get_applied_migrations()

        for sql_file in migration_files:
            migration_name = sql_file.stem

            if migration_name in applied:
                logger.info(f"⏭️ Skipping {migration_name} (already applied)")
                continue

            logger.info(f"🔄 Applying {migration_name}...")
            await manager.apply_migration(migration_name, sql_file)

    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(apply_all_pending())
```

## CHECKLIST COMPLETA

### Pre-Implementazione
- [ ] Leggi tutti gli script migration esistenti
- [ ] Identifica pattern comune
- [ ] Crea branch: `refactor/migration-system`

### Durante Implementazione
- [ ] Crea `MigrationManager` con test
- [ ] Crea `BaseMigration` con test
- [ ] Refactor almeno 2 script esistenti
- [ ] Crea CLI tool
- [ ] Testa con database reale

### Post-Implementazione
- [ ] Tutti i test passano
- [ ] Migrations possono essere applicate/idempotenti
- [ ] Rollback funziona
- [ ] Documentazione completa
- [ ] Code review
- [ ] Merge in main

## TEST STRATEGY

### Unit Tests
```python
@pytest.mark.asyncio
async def test_migration_manager_tracking():
    manager = MigrationManager("postgresql://test")
    await manager.connect()
    await manager.ensure_migration_log()

    # Apply migration
    applied = await manager.apply_migration("test_001", sql_file)
    assert applied is True

    # Check tracking
    applied_list = await manager.get_applied_migrations()
    assert "test_001" in applied_list

    # Try to apply again (should skip)
    applied_again = await manager.apply_migration("test_001", sql_file)
    assert applied_again is False
```

## OUTPUT ATTESO

1. **File Creati:**
   - `backend/db/migration_manager.py`
   - `backend/db/migration_base.py`
   - `backend/scripts/migrate.py`

2. **File Refactorizzati:**
   - `backend/migrations/apply_migration_*.py` (usano BaseMigration)

3. **Database:**
   - Tabella `schema_migrations` creata

## CRITERI DI SUCCESSO

✅ Migration tracking funziona
✅ Nessuna duplicazione codice
✅ Migrations idempotenti
✅ Rollback funziona
✅ CLI tool funziona
✅ Tutti i test passano

## TEMPO STIMATO

- MigrationManager: 3-4 ore
- BaseMigration: 2-3 ore
- Refactor scripts: 2-3 ore
- CLI tool: 1-2 ore
- Testing: 2-3 ore
- **Totale: 10-15 ore**

---

INIZIA QUI:
1. Leggi `apply_migration_010.py` come riferimento
2. Crea `MigrationManager`
3. Crea `BaseMigration`
4. Refactor uno script esistente
5. Testa completamente
6. Procedi con altri script
```

---

# 5. QDRANTCLIENT SYNC → ASYNC

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di migrare QdrantClient da sync a async.

## CONTESTO

Il file `apps/backend-rag/backend/core/qdrant_db.py` usa `requests` (sync) per chiamare Qdrant API:
```python
response = requests.post(url, json=payload, timeout=30)  # SYNC - blocca event loop!
```

**Problemi Causati:**
- Blocca event loop FastAPI → Concorrenza = 0
- Performance degradation → Ogni request blocca 30 secondi
- Connection overhead → Nuova connessione TCP ogni volta
- Timeout issues → Timeout fisso non gestito bene

**File da Modificare:**
- `core/qdrant_db.py` (436 LOC)

**Dipendenze:**
- Usato da SearchService, MemoryService, e molti altri
- Core service → cambiamenti impattano tutto

## OBIETTIVO

Migrare QdrantClient a:
1. `httpx` (async HTTP client) invece di `requests`
2. Connection pooling (riutilizzo connessioni)
3. Async/await pattern completo
4. Mantenere compatibilità API (se possibile)

## REGOLE DEL PROGETTO

Leggi PRIMA:
- `AI_ONBOARDING.md`
- `apps/backend-rag/backend/core/qdrant_db.py` (file completo)
- `apps/backend-rag/backend/services/search_service.py` (vedi come viene usato)

**Pattern Standard:**
- Tutti i metodi devono essere `async`
- Usa `httpx.AsyncClient` con connection pool
- Gestisci timeout con `asyncio.wait_for`
- Error handling robusto

## METODOLOGIA

### Fase 1: ANALISI (1-2 ore)
1. Leggi `qdrant_db.py` completamente
2. Identifica TUTTI i metodi che fanno HTTP calls
3. Mappa dipendenze (chi usa QdrantClient)
4. Identifica breaking changes necessari

### Fase 2: MIGRAZIONE (4-6 ore)

**Step 1: Sostituisci Import**
```python
# PRIMA
import requests

# DOPO
import httpx
import asyncio
```

**Step 2: Crea AsyncClient con Pool**
```python
# PRIMA
class QdrantClient:
    def __init__(self, qdrant_url: str):
        self.qdrant_url = qdrant_url
        self.headers = {"Content-Type": "application/json"}

# DOPO
class QdrantClient:
    def __init__(self, qdrant_url: str):
        self.qdrant_url = qdrant_url
        self.headers = {"Content-Type": "application/json"}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with connection pool"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.qdrant_url,
                timeout=30.0,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20
                )
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
```

**Step 3: Converti Metodi a Async**
```python
# PRIMA
def search(
    self,
    query_embedding: list[float],
    collection_name: str,
    limit: int = 10
) -> dict:
    url = f"{self.qdrant_url}/collections/{collection_name}/points/search"
    payload = {
        "vector": query_embedding,
        "limit": limit
    }
    response = requests.post(url, json=payload, headers=self.headers, timeout=30)
    response.raise_for_status()
    return response.json()

# DOPO
async def search(
    self,
    query_embedding: list[float],
    collection_name: str,
    limit: int = 10
) -> dict:
    client = await self._get_client()
    url = f"/collections/{collection_name}/points/search"
    payload = {
        "vector": query_embedding,
        "limit": limit
    }

    try:
        response = await client.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        raise TimeoutError(f"Qdrant request timeout after 30s")
    except httpx.HTTPStatusError as e:
        raise ValueError(f"Qdrant error: {e.response.status_code}")
```

**Step 4: Aggiorna Context Manager**
```python
# PRIMA
# Nessun context manager

# DOPO
async def __aenter__(self):
    await self._get_client()
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    await self.close()
```

### Fase 3: AGGIORNA USAGE (2-3 ore)
1. Trova tutti i file che usano QdrantClient
2. Aggiorna chiamate a `await`
3. Aggiorna context manager usage

### Fase 4: TESTING (2-3 ore)
1. Crea test async per QdrantClient
2. Verifica connection pooling
3. Verifica performance (non deve degradare)

## STRUTTURA CODICE ATTESA

### qdrant_db.py (Dopo Migrazione)
```python
"""
Qdrant Client - Async Vector Database Client
Uses httpx for async HTTP requests with connection pooling.
"""

import httpx
import asyncio
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class QdrantClient:
    """
    Async Qdrant vector database client.

    Usage:
    async with QdrantClient(url) as client:
        results = await client.search(embedding, "collection")
    """

    def __init__(self, qdrant_url: str):
        self.qdrant_url = qdrant_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with connection pool"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.qdrant_url,
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20
                ),
                http2=True  # HTTP/2 support
            )
        return self._client

    async def close(self):
        """Close HTTP client and connection pool"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def search(
        self,
        query_embedding: list[float],
        collection_name: str,
        limit: int = 10,
        filter: Optional[dict] = None
    ) -> dict[str, Any]:
        """
        Search documents in collection.

        Args:
            query_embedding: Query vector
            collection_name: Collection to search
            limit: Max results
            filter: Optional metadata filter

        Returns:
            Search results with documents and scores
        """
        client = await self._get_client()
        url = f"/collections/{collection_name}/points/search"

        payload = {
            "vector": query_embedding,
            "limit": limit
        }

        if filter:
            payload["filter"] = self._build_filter(filter)

        try:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            logger.error(f"Qdrant search timeout: {e}")
            raise TimeoutError(f"Qdrant request timeout after 30s")
        except httpx.HTTPStatusError as e:
            logger.error(f"Qdrant HTTP error: {e.response.status_code}")
            raise ValueError(f"Qdrant error: {e.response.status_code} - {e.response.text}")

    async def upsert_documents(
        self,
        collection_name: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[Any]
    ) -> dict[str, Any]:
        """Upsert documents in collection"""
        client = await self._get_client()
        url = f"/collections/{collection_name}/points"

        points = []
        for i, (chunk, embedding, metadata, id_val) in enumerate(
            zip(chunks, embeddings, metadatas, ids)
        ):
            points.append({
                "id": id_val,
                "vector": embedding,
                "payload": {
                    "text": chunk,
                    **metadata
                }
            })

        payload = {"points": points}

        try:
            response = await client.put(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise TimeoutError("Qdrant upsert timeout")
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Qdrant upsert error: {e.response.status_code}")
```

## CHECKLIST COMPLETA

### Pre-Migrazione
- [ ] Leggi `qdrant_db.py` completamente
- [ ] Trova tutti i file che usano QdrantClient
- [ ] Esegui test esistenti (baseline)
- [ ] Crea branch: `refactor/qdrant-async`

### Durante Migrazione
- [ ] Sostituisci `requests` → `httpx`
- [ ] Crea `AsyncClient` con connection pool
- [ ] Converti TUTTI i metodi a `async`
- [ ] Aggiungi context manager (`__aenter__`, `__aexit__`)
- [ ] Aggiorna error handling
- [ ] Aggiorna tutti gli usage a `await`

### Post-Migrazione
- [ ] Tutti i test passano
- [ ] Connection pooling funziona
- [ ] Performance migliorata (benchmark)
- [ ] Nessun blocking (verifica con monitoring)
- [ ] Code review
- [ ] Merge in main

## TEST STRATEGY

### Unit Tests
```python
@pytest.mark.asyncio
async def test_qdrant_search_async():
    """Test async search"""
    async with QdrantClient("http://localhost:6333") as client:
        results = await client.search([0.1] * 1536, "test_collection")
        assert "result" in results

@pytest.mark.asyncio
async def test_qdrant_connection_pool():
    """Test connection pool reuse"""
    client = QdrantClient("http://localhost:6333")

    # First request creates connection
    await client.search([0.1] * 1536, "test_collection")
    client1 = client._client

    # Second request reuses connection
    await client.search([0.1] * 1536, "test_collection")
    client2 = client._client

    assert client1 is client2  # Same client instance
```

## ROLLBACK PLAN

1. Mantieni codice originale in branch
2. Feature flag per nuovo client
3. Possibilità rollback immediato

## OUTPUT ATTESO

1. **File Modificati:**
   - `core/qdrant_db.py` (async con httpx)

2. **File Aggiornati:**
   - Tutti i file che usano QdrantClient

3. **Dependencies:**
   - Aggiungi `httpx` a `requirements.txt`

## CRITERI DI SUCCESSO

✅ Zero `requests` usage
✅ Tutti i metodi sono `async`
✅ Connection pooling funziona
✅ Performance migliorata
✅ Nessun blocking
✅ Tutti i test passano

## TEMPO STIMATO

- Analisi: 1-2 ore
- Migrazione: 4-6 ore
- Aggiorna usage: 2-3 ore
- Testing: 2-3 ore
- **Totale: 9-14 ore**

---

INIZIA QUI:
1. Leggi `qdrant_db.py` completamente
2. Installa `httpx` (aggiungi a requirements.txt)
3. Crea AsyncClient con pool
4. Migra metodo per metodo
5. Testa dopo ogni metodo
6. Aggiorna usage incrementalmente
```

---

# 6. EXTRACT DUPLICATE ROUTING LOGIC

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di eliminare duplicazione di codice.

## CONTESTO

Il file `apps/backend-rag/backend/services/query_router.py` ha duplicazione:
- `route()` e `route_with_confidence()` duplicano ~200 linee di logica
- Stesso calcolo domain scores appare due volte
- Stessa logica di determinazione collection

**Problema:**
- Bug fix deve essere applicato due volte
- Codice diverge (due implementazioni diverse)
- Manutenzione doppia

## OBIETTIVO

Estrarre logica comune in metodi helper riutilizzabili.

## METODOLOGIA

1. Identifica logica comune tra `route()` e `route_with_confidence()`
2. Estrai in metodi privati `_calculate_domain_scores()` e `_determine_collection()`
3. Refactor entrambi i metodi per usare helper comuni
4. Testa che comportamento non cambi

## OUTPUT ATTESO

- `query_router.py` con duplicazione rimossa
- Metodi helper riutilizzabili
- Test che verificano stesso comportamento

**Tempo**: 2-3 ore
```

---

# 7. IMPLEMENT NOTIFICATIONHUB REAL

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di implementare NotificationHub reale.

## CONTESTO

Il file `apps/backend-rag/backend/services/notification_hub.py` ha stub:
- `_send_email()` solo logga, non invia realmente
- `_send_whatsapp()` solo logga, non invia realmente
- `_send_sms()` solo logga, non invia realmente

**Problema:**
- Notifiche non funzionano in produzione
- Support tickets su notifiche mancanti
- Business impact (clienti non notificati)

## OBIETTIVO

Implementare integrazione reale con SendGrid (email) e Twilio (WhatsApp/SMS).

## METODOLOGIA

1. Implementa `_send_email()` con SendGrid API
2. Implementa `_send_whatsapp()` con Twilio API
3. Implementa `_send_sms()` con Twilio API
4. Aggiungi error handling e retries
5. Aggiungi integration tests

## OUTPUT ATTESO

- NotificationHub funzionante
- Integrazione SendGrid/Twilio
- Test integration
- Error handling robusto

**Tempo**: 8-12 ore
```

---

# 8. REMOVE SINGLETON PATTERN

## 🎯 PROMPT COMPLETO

```
Sei un Senior Python Architect incaricato di rimuovere singleton pattern.

## CONTESTO

Il file `apps/backend-rag/backend/core/embeddings.py` usa singleton:
```python
class EmbeddingsGenerator:
    _instance: Optional["EmbeddingsGenerator"] = None

    def __new__(cls, *_args, **_kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**Problema:**
- Difficile testare (singleton globale)
- Parametri `__init__` ignorati dopo prima inizializzazione
- Pattern inconsistente con resto codebase

## OBIETTIVO

Sostituire singleton con factory function + dependency injection.

## METODOLOGIA

1. Crea factory function `create_embeddings_generator()`
2. Rimuovi singleton pattern
3. Aggiorna usage a factory function o DI
4. Mantieni backward compatibility

## OUTPUT ATTESO

- EmbeddingsGenerator senza singleton
- Factory function
- Dependency injection support
- Test migliorati

**Tempo**: 2 ore
```

---

## 📝 NOTE FINALI

Ogni prompt è **completo e autonomo**. Puoi:
1. Copiare il prompt completo del refactoring che vuoi eseguire
2. Assegnarlo a un'AI
3. L'AI ha tutto il contesto necessario per eseguire il refactoring

**Pattern Comune di Ogni Prompt:**
- ✅ Contesto completo (problema reale)
- ✅ Obiettivo chiaro
- ✅ Metodologia step-by-step
- ✅ Esempi di codice (prima/dopo)
- ✅ Checklist completa
- ✅ Test strategy
- ✅ Rollback plan
- ✅ Criteri di successo
- ✅ Tempo stimato

**Tempo Totale Stimato**: 200-300 ore per tutti i refactoring

**Priorità Raccomandata:**
1. P0: Refactoring 1-5 (Critical)
2. P1: Refactoring 6-7 (High)
3. P2: Refactoring 8+ (Medium)
