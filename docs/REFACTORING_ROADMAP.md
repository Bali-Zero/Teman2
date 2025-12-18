# 🏗️ REFACTORING ROADMAP - Tutti i Refactoring Identificati

**Data**: 2025-12-07
**Stato**: Identificati e Prioritizzati
**Aree Analizzate**: 8 (Core, Services, Migrations, Routers, Agents, LLM, Plugins, Config)

---

## 📊 EXECUTIVE SUMMARY

**Totale Refactoring Identificati**: 47+
**Priorità Critica (P0)**: 8
**Priorità Alta (P1)**: 15
**Priorità Media (P2)**: 18
**Priorità Bassa (P3)**: 6+

**Estimated Total Effort**: 200-300 hours
**Breaking Changes**: Sì (alcuni richiedono API changes)

---

## 🔴 P0 - CRITICAL REFACTORING (Blocca o Impatta Criticamente)

### 1. **Split SearchService (God Object)** 🔴

**Location**: `services/search_service.py` (1017 lines)

**Problema**:
- Single class fa troppe cose:
  - Collection management (17 collections)
  - Search logic
  - Conflict resolution
  - Health monitoring
  - Cultural insights
  - Query routing
  - Warmup logic

**Refactoring**:
```python
# Split in:
- SearchService (core search only, ~200 LOC)
- CollectionManager (collection lifecycle, ~150 LOC)
- ConflictResolver (conflict detection/resolution, ~100 LOC)
- CollectionHealthMonitor (già esiste, integrare meglio)
- CulturalInsightsService (extract cultural logic, ~150 LOC)
- QueryRouterIntegration (extract routing logic, ~100 LOC)
```

**Effort**: 16-20 hours
**Risk**: Medium (core service, needs careful testing)
**Impact**: High (maintainability, testability, performance)

---

### 2. **Standardize Database Access (psycopg2 → asyncpg)** 🔴

**Location**:
- `services/auto_crm_service.py` (uses `psycopg2`)
- `services/context/context_builder.py` (uses `psycopg2`)
- Altri servizi già migrati a `asyncpg` ✅

**Problema**:
- Mixed sync/async database access
- No connection pooling in alcuni servizi
- Connection leaks potential
- Not compatible with async FastAPI

**Refactoring**:
```python
# Migrate to:
1. asyncpg with connection pooling
2. SQLModel for ORM (opzionale ma consigliato)
3. Shared database session manager
4. Remove all psycopg2 usage
```

**Effort**: 12-16 hours
**Risk**: High (CRM is critical path)
**Impact**: High (performance, reliability)

---

### 3. **Global State → Dependency Injection (Cache)** 🔴

**Location**: `core/cache.py:148`, `core/cache.py:22`

**Problema**:
```python
cache = CacheService()  # Global singleton
_memory_cache = {}  # Module-level mutable state
```

**Refactoring**:
```python
# Replace with:
def get_cache_service() -> CacheService:
    return CacheService()

# In FastAPI dependencies
def get_cache() -> CacheService:
    return get_cache_service()
```

**Effort**: 2-3 hours
**Risk**: Medium (breaking change per codice che usa `cache` direttamente)
**Impact**: Medium (testability, no race conditions)

---

### 4. **Migration System Centralizzato** 🔴

**Location**: `backend/migrations/` e `backend/db/migrations/`

**Problema**:
- Nessun sistema di tracking migrations applicate
- Rischio di applicare migrations multiple volte
- Nessuna gestione dipendenze tra migrations
- Impossibile rollback automatico

**Refactoring**:
```python
# Creare: backend/db/migration_manager.py
class MigrationManager:
    async def ensure_migration_log(self)
    async def get_applied_migrations(self) -> List[str]
    async def apply_migration(self, migration_name: str, sql_file: Path)
    async def rollback_migration(self, migration_name: str)
```

**Effort**: 8 hours
**Risk**: Low (backward compatible)
**Impact**: High (reliability, maintainability)

---

### 5. **QdrantClient: Sync → Async** 🔴

**Location**: `core/qdrant_db.py`

**Problema**:
- Usa `requests` (sync) in contesto async FastAPI
- Blocca event loop
- Performance degradation

**Refactoring**:
```python
# Replace requests with:
- httpx (async HTTP client)
- aiohttp (alternativa)
- Tutti i metodi devono essere async
```

**Effort**: 6-8 hours
**Risk**: Medium (breaking change API)
**Impact**: High (performance, scalability)

---

### 6. **Connection Pooling per Qdrant** 🔴

**Location**: `core/qdrant_db.py`

**Problema**:
- Crea nuova connessione HTTP per ogni operazione
- Nessun connection pooling
- Overhead significativo

**Refactoring**:
```python
# Implementare:
- HTTP connection pool (httpx.AsyncClient con pool)
- Reuse connections
- Connection lifecycle management
```

**Effort**: 4-6 hours
**Risk**: Low
**Impact**: High (performance)

---

### 7. **Remove Singleton Pattern (EmbeddingsGenerator)** 🔴

**Location**: `core/embeddings.py:36-42`

**Problema**:
- Singleton globale difficile da testare
- Parametri `__init__` ignorati dopo prima inizializzazione
- Pattern inconsistente

**Refactoring**:
```python
# Replace with factory function:
def create_embeddings_generator(settings=None) -> EmbeddingsGenerator:
    return EmbeddingsGenerator(settings=settings)

# Use dependency injection in FastAPI
```

**Effort**: 2 hours
**Risk**: Medium (breaking change)
**Impact**: Medium (testability)

---

### 8. **Extract Filter Builder (Qdrant)** 🔴

**Location**: `core/qdrant_db.py:57-111`

**Problema**:
- Logica filter conversion complessa e non riutilizzabile
- Embedded in QdrantClient
- Difficile testare isolatamente

**Refactoring**:
```python
# Extract to:
class QdrantFilterBuilder:
    def build_filter(self, filter_dict: dict) -> dict
    def validate_filter(self, filter_dict: dict) -> bool
```

**Effort**: 1 hour
**Risk**: Low
**Impact**: Medium (maintainability)

---

## 🟠 P1 - HIGH PRIORITY REFACTORING

### 9. **Extract Duplicate Routing Logic** 🟠

**Location**: `services/query_router.py`

**Problema**:
- `route()` e `route_with_confidence()` duplicano logica
- ~200 lines duplicate

**Refactoring**:
```python
# Extract common logic:
def _calculate_domain_scores(self, query: str) -> dict
def _determine_collection(self, domain_scores: dict, query: str) -> CollectionName
```

**Effort**: 2-3 hours
**Risk**: Low
**Impact**: Medium (maintainability)

---

### 10. **Implement NotificationHub (Stub → Real)** 🟠

**Location**: `services/notification_hub.py`

**Problema**:
- `_send_email()`, `_send_whatsapp()`, `_send_sms()` solo loggano
- Nessuna integrazione reale con SendGrid/Twilio

**Refactoring**:
```python
# Implement actual:
- SendGrid email sending
- Twilio WhatsApp/SMS sending
- Error handling e retries
- Integration tests
```

**Effort**: 8-12 hours
**Risk**: Medium (external API integration)
**Impact**: High (production bug fix)

---

### 11. **Dependency Injection Pattern** 🟠

**Location**: Multiple services

**Problema**:
- Services creano dipendenze internamente
- Difficile testare (can't mock)
- Tight coupling

**Refactoring**:
```python
# Before:
class AutoCRMService:
    def __init__(self, ai_client=None):
        self.extractor = get_extractor(ai_client=ai_client)  # Creates dependency

# After:
class AutoCRMService:
    def __init__(self, extractor: AIExtractor):
        self.extractor = extractor  # Dependency injected
```

**Effort**: 4-6 hours
**Risk**: Medium (breaking changes)
**Impact**: High (testability)

---

### 12. **Extract BaseMigration Class** 🟠

**Location**: `backend/migrations/apply_migration_*.py`

**Problema**:
- ~400 LOC duplicate tra migrations
- Stesso pattern ripetuto 7 volte

**Refactoring**:
```python
# Create: backend/db/migration_base.py
class BaseMigration:
    async def apply(self) -> bool
    def verify(self) -> bool
    def rollback(self) -> bool
```

**Effort**: 4 hours
**Risk**: Low
**Impact**: High (maintainability)

---

### 13. **Standardize Migration Libraries** 🟠

**Location**: `backend/migrations/`

**Problema**:
- Mix di `psycopg2` (sync) e `asyncpg` (async)
- Inconsistenza

**Refactoring**:
- Standardizzare su `asyncpg` per tutte le migrations

**Effort**: 3 hours
**Risk**: Medium (testare tutte le migrations)
**Impact**: Medium (consistency)

---

### 14. **Remove Settings Dependency (Core Modules)** 🟠

**Location**: `core/chunker.py`, `core/embeddings.py`, `core/qdrant_db.py`

**Problema**:
- Accoppiamento forte a `app.core.config`
- Difficile testare senza mock complessi

**Refactoring**:
```python
# Before:
from app.core.config import settings
chunk_size = settings.chunk_size or 1000

# After:
class TextChunker:
    def __init__(self, chunk_size: int = 1000, ...):
        self.chunk_size = chunk_size  # Explicit parameter
```

**Effort**: 3-4 hours
**Risk**: Low
**Impact**: Medium (testability)

---

### 15. **Split QdrantClient (God Object)** 🟠

**Location**: `core/qdrant_db.py:19` (436 LOC)

**Problema**:
- Troppe responsabilità:
  - Search
  - Upsert
  - Delete
  - Collection management
  - Filter conversion
  - Stats retrieval

**Refactoring**:
```python
# Split into:
- QdrantSearchClient (search operations)
- QdrantCollectionManager (collection CRUD)
- QdrantFilterBuilder (filter conversion utility)
```

**Effort**: 6-8 hours
**Risk**: Medium (breaking change API)
**Impact**: Medium (maintainability)

---

## 🟡 P2 - MEDIUM PRIORITY REFACTORING

### 16. **Extract Magic Numbers to Constants** 🟡

**Location**: Multiple files

**Problema**:
- Magic numbers sparsi nel codice
- Difficile capire significato

**Refactoring**:
```python
# Extract to constants:
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
CACHE_TTL = 300
```

**Effort**: 2-3 hours
**Risk**: Low
**Impact**: Low (code clarity)

---

### 17. **Extract Helper Methods (Long Functions)** 🟡

**Location**: Multiple services

**Problema**:
- Funzioni troppo lunghe (>50 righe)
- Complessità ciclomatica elevata

**Refactoring**:
- Estrarre logica in helper methods
- Ridurre complessità

**Effort**: 4-6 hours
**Risk**: Low
**Impact**: Medium (maintainability)

---

### 18. **String Concatenation Optimization** 🟡

**Location**: `core/chunker.py:300`

**Problema**:
```python
current_chunk += split_with_sep  # String concatenation in loop
```

**Refactoring**:
```python
# Use list + join:
chunk_parts = []
for split in splits:
    chunk_parts.append(split_with_sep)
current_chunk = "".join(chunk_parts)
```

**Effort**: 1 hour
**Risk**: Low
**Impact**: Low (performance)

---

### 19. **Add Type Hints Completeness** 🟡

**Location**: Multiple files

**Problema**:
- Type hints mancanti o incompleti
- Difficile debugging

**Refactoring**:
- Aggiungere type hints completi
- Usare `mypy` per validazione

**Effort**: 8-12 hours
**Risk**: Low
**Impact**: Medium (code quality)

---

### 20. **Extract Common Error Handling** 🟡

**Location**: Multiple routers

**Problema**:
- Error handling duplicato
- Messaggi inconsistenti

**Refactoring**:
```python
# Create: app/utils/error_handlers.py
def handle_database_error(e: Exception) -> HTTPException
def handle_validation_error(e: ValidationError) -> HTTPException
```

**Effort**: 2-3 hours
**Risk**: Low
**Impact**: Medium (consistency)

---

## 📋 REFACTORING BY AREA

### Core Module (`core/*`)
1. ✅ Global State → DI (cache.py)
2. ✅ Singleton → Factory (embeddings.py)
3. ✅ Settings Dependency → Explicit params
4. ✅ Split QdrantClient
5. ✅ Sync → Async (QdrantClient)
6. ✅ Connection Pooling (Qdrant)
7. ✅ Extract Filter Builder

### Services Module (`services/*`)
1. ✅ Split SearchService (God Object)
2. ✅ Standardize DB Access (psycopg2 → asyncpg)
3. ✅ Extract Duplicate Routing Logic
4. ✅ Implement NotificationHub
5. ✅ Dependency Injection Pattern
6. ✅ Extract Helper Methods

### Migrations (`migrations/`, `db/migrations/`)
1. ✅ Migration System Centralizzato
2. ✅ Extract BaseMigration Class
3. ✅ Standardize Migration Libraries
4. ✅ Connection Pooling per Migrations

### Routers (`app/routers/*`)
1. ✅ Extract Common Error Handling
2. ✅ Standardize Input Validation
3. ✅ Add Rate Limiting Consistency

### Agents (`agents/*`)
1. ✅ Extract Common Agent Patterns
2. ✅ Standardize Agent Lifecycle

### LLM (`llm/*`)
1. ✅ Extract Client Factory
2. ✅ Standardize Error Handling

### Plugins (`plugins/*`, `core/plugins/*`)
1. ✅ Extract Plugin Base Class
2. ✅ Standardize Plugin Interface

---

## 🎯 PRIORITIZZAZIONE RACCOMANDATA

### Sprint 1 (Questa Settimana) - Critical Fixes
1. ✅ Fix Syntax Error (COMPLETATO)
2. 🔴 Split SearchService (16-20h)
3. 🔴 Standardize DB Access (12-16h)
4. 🔴 Global State → DI (2-3h)

**Total**: ~30-40 hours

### Sprint 2 (Prossima Settimana) - High Priority
5. 🔴 Migration System (8h)
6. 🔴 QdrantClient Async (6-8h)
7. 🟠 Extract Duplicate Logic (2-3h)
8. 🟠 Implement NotificationHub (8-12h)

**Total**: ~24-31 hours

### Sprint 3 (Settimana 3) - Medium Priority
9. 🟠 Dependency Injection Pattern (4-6h)
10. 🟠 Extract BaseMigration (4h)
11. 🟡 Extract Magic Numbers (2-3h)
12. 🟡 Extract Helper Methods (4-6h)

**Total**: ~14-19 hours

### Sprint 4+ (Settimane 4+) - Code Quality
13. 🟡 Type Hints Completeness (8-12h)
14. 🟡 Extract Common Error Handling (2-3h)
15. 🟡 String Optimization (1h)
16. Altri refactoring P2/P3

**Total**: ~11-16 hours

---

## 📊 METRICHE ATTESE DOPO REFACTORING

### Code Quality
- **Cyclomatic Complexity**: -30% (function extraction)
- **Code Duplication**: -40% (extract common logic)
- **Test Coverage**: +20% (better testability)
- **Maintainability Index**: +25%

### Performance
- **Database Queries**: -50% (connection pooling)
- **API Response Time**: -30% (async operations)
- **Memory Usage**: -20% (remove global state)
- **Concurrency**: +500% (async/await)

### Reliability
- **Connection Leaks**: 0 (pooling + proper cleanup)
- **Race Conditions**: 0 (remove global state)
- **Error Handling**: +100% consistency

---

## ⚠️ RISCHI E MITIGAZIONI

### Rischio Alto
- **SearchService Split**: Core service, molti dipendenti
  - **Mitigazione**: Test completo prima di deploy, feature flag per rollback

- **DB Access Standardization**: CRM è critical path
  - **Mitigazione**: Migrazione graduale, test paralleli

### Rischio Medio
- **Breaking Changes API**: Alcuni refactoring cambiano API
  - **Mitigazione**: Versioning API, deprecation warnings

- **Test Coverage**: Alcuni servizi hanno pochi test
  - **Mitigazione**: Aggiungere test prima di refactoring

---

## 📝 NOTE IMPLEMENTAZIONE

### Best Practices
1. **Test First**: Aggiungere test prima di refactoring
2. **Incremental**: Un refactoring alla volta
3. **Feature Flags**: Usare feature flags per rollback
4. **Documentation**: Documentare cambiamenti API
5. **Monitoring**: Monitorare metriche dopo ogni refactoring

### Tools Consigliati
- **mypy**: Type checking
- **pytest**: Testing framework
- **pytest-cov**: Coverage analysis
- **ruff**: Linting e auto-fix
- **black**: Code formatting

---

**Ultimo Aggiornamento**: 2025-12-07
**Prossimo Review**: Dopo Sprint 1
