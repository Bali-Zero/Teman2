# Search Services API Documentation

**Last Updated:** 2025-12-07
**Version:** 2.0 (Refactored)

## Overview

The search functionality has been refactored into focused services following Single Responsibility Principle. This document describes the API for each service.

## Services

### 1. SearchService

**File:** `services/search_service.py`
**Responsibility:** Core search functionality

#### Initialization

```python
from services.search_service import SearchService
from services.collection_manager import CollectionManager
from services.conflict_resolver import ConflictResolver
from services.cultural_insights_service import CulturalInsightsService
from services.query_router_integration import QueryRouterIntegration

# With dependency injection (recommended)
collection_manager = CollectionManager()
conflict_resolver = ConflictResolver()
cultural_insights = CulturalInsightsService(...)
query_router = QueryRouterIntegration()

service = SearchService(
    collection_manager=collection_manager,
    conflict_resolver=conflict_resolver,
    cultural_insights=cultural_insights,
    query_router=query_router,
)

# Without dependencies (creates new instances)
service = SearchService()
```

#### Methods

##### `async search(query, user_level, limit=5, tier_filter=None, collection_override=None)`

Perform semantic search with tier-based access control.

**Parameters:**
- `query` (str): Search query text
- `user_level` (int): User access level (0-3)
- `limit` (int): Maximum results (default: 5)
- `tier_filter` (list[TierLevel]): Optional tier filter
- `collection_override` (str): Force specific collection (for testing)

**Returns:**
```python
{
    "query": str,
    "results": [
        {
            "id": str,
            "text": str,
            "metadata": dict,
            "score": float,
        }
    ],
    "user_level": int,
    "allowed_tiers": list[str],
    "collection_used": str,
}
```

**Example:**
```python
result = await service.search(
    query="What is KITAS visa?",
    user_level=3,
    limit=10
)
```

##### `async search_with_conflict_resolution(query, user_level, limit=5, tier_filter=None, enable_fallbacks=True)`

Enhanced search with conflict detection and resolution.

**Parameters:**
- Same as `search()` plus:
- `enable_fallbacks` (bool): Use fallback collections (default: True)

**Returns:**
```python
{
    "query": str,
    "results": list[dict],
    "user_level": int,
    "primary_collection": str,
    "collections_searched": list[str],
    "confidence": float,
    "conflicts_detected": int,
    "conflicts": list[dict],
    "fallbacks_used": bool,
}
```

##### `async search_collection(query, collection_name, limit=5, filter=None)`

Direct search on a specific collection.

**Parameters:**
- `query` (str): Search query
- `collection_name` (str): Target collection
- `limit` (int): Maximum results
- `filter` (dict): Optional metadata filter

**Returns:**
```python
{
    "query": str,
    "results": list[dict],
    "collection": str,
}
```

##### `async add_cultural_insight(text, metadata)`

Add cultural insight to Qdrant (delegates to CulturalInsightsService).

**Parameters:**
- `text` (str): Cultural insight content
- `metadata` (dict): Metadata with topic, language, when_to_use, etc.

**Returns:** `bool` - Success status

##### `async query_cultural_insights(query, when_to_use=None, limit=3)`

Query cultural insights (delegates to CulturalInsightsService).

**Parameters:**
- `query` (str): Search query
- `when_to_use` (str): Optional usage context filter
- `limit` (int): Maximum results

**Returns:** `list[dict]` - List of cultural insights

##### `get_conflict_stats()`

Get conflict resolution statistics (delegates to ConflictResolver).

**Returns:** `dict` - Conflict resolution metrics

##### `get_collection_health(collection_name)`

Get health metrics for a specific collection.

**Parameters:**
- `collection_name` (str): Collection to check

**Returns:** `dict` - Health metrics

##### `async warmup()`

Warm up Qdrant collections on startup to reduce cold-start latency.

---

### 2. CollectionManager

**File:** `services/collection_manager.py`
**Responsibility:** Collection lifecycle management

#### Initialization

```python
from services.collection_manager import CollectionManager

manager = CollectionManager(qdrant_url="http://qdrant:6333")
```

#### Methods

##### `get_collection(name)`

Get collection client with lazy initialization.

**Parameters:**
- `name` (str): Collection name

**Returns:** `QdrantClient | None` - Collection client or None if not found

**Example:**
```python
client = manager.get_collection("visa_oracle")
if client:
    results = await client.search(...)
```

##### `list_collections()`

List all available collection names.

**Returns:** `list[str]` - List of collection names

##### `get_collection_info(name)`

Get collection metadata.

**Parameters:**
- `name` (str): Collection name

**Returns:** `dict | None` - Collection info or None if not found

**Example:**
```python
info = manager.get_collection_info("visa_oracle")
# Returns: {"priority": "high", "doc_count": 1612, "actual_name": "visa_oracle"}
```

##### `get_all_collections()`

Get all collection clients (pre-initializes all collections).

**Returns:** `dict[str, QdrantClient]` - Dictionary mapping names to clients

---

### 3. ConflictResolver

**File:** `services/conflict_resolver.py`
**Responsibility:** Conflict detection and resolution

#### Initialization

```python
from services.conflict_resolver import ConflictResolver

resolver = ConflictResolver()
```

#### Methods

##### `detect_conflicts(results_by_collection)`

Detect conflicts between results from different collections.

**Parameters:**
- `results_by_collection` (dict[str, list[dict]]): Results grouped by collection

**Returns:** `list[dict]` - List of detected conflicts

**Example:**
```python
results = {
    "tax_knowledge": [...],
    "tax_updates": [...],
}
conflicts = resolver.detect_conflicts(results)
```

##### `resolve_conflicts(results_by_collection, conflicts)`

Resolve conflicts using timestamp and relevance-based priority.

**Parameters:**
- `results_by_collection` (dict): Results grouped by collection
- `conflicts` (list[dict]): Detected conflicts

**Returns:** `tuple[list[dict], list[dict]]` - (resolved_results, conflict_reports)

**Resolution Strategy:**
1. Temporal priority: `*_updates` collections win over base collections
2. Relevance: Higher scores win if timestamps equal
3. Transparency: Losing results flagged as "outdated" or "alternate"

##### `get_stats()`

Get conflict resolution statistics.

**Returns:** `dict` - Statistics with conflicts_detected, conflicts_resolved, etc.

---

### 4. CulturalInsightsService

**File:** `services/cultural_insights_service.py`
**Responsibility:** Cultural insights storage and retrieval

#### Initialization

```python
from services.cultural_insights_service import CulturalInsightsService
from services.collection_manager import CollectionManager
from core.embeddings import EmbeddingsGenerator

collection_manager = CollectionManager()
embedder = EmbeddingsGenerator()

service = CulturalInsightsService(
    collection_manager=collection_manager,
    embedder=embedder,
)
```

#### Methods

##### `async add_insight(text, metadata)`

Add cultural insight to Qdrant.

**Parameters:**
- `text` (str): Cultural insight content
- `metadata` (dict): Metadata with topic, language, when_to_use, tone, etc.

**Returns:** `bool` - Success status

**Example:**
```python
success = await service.add_insight(
    text="Indonesians value indirect communication",
    metadata={
        "topic": "communication",
        "language": "id",
        "when_to_use": ["first_contact", "greeting"],
        "tone": "respectful",
    }
)
```

##### `async query_insights(query, when_to_use=None, limit=3)`

Query cultural insights using semantic search.

**Parameters:**
- `query` (str): Search query (user message)
- `when_to_use` (str): Optional usage context filter
- `limit` (int): Maximum results

**Returns:** `list[dict]` - List of cultural insights

**Example:**
```python
insights = await service.query_insights(
    query="Hello, how are you?",
    when_to_use="first_contact",
    limit=3
)
# Returns: [
#     {
#         "content": "...",
#         "metadata": {"topic": "greeting", ...},
#         "score": 0.92
#     }
# ]
```

##### `async get_topics_coverage()`

Get coverage statistics for cultural topics (not yet implemented).

**Returns:** `dict` - Topic coverage statistics

---

### 5. QueryRouterIntegration

**File:** `services/query_router_integration.py`
**Responsibility:** Query routing and collection selection

#### Initialization

```python
from services.query_router_integration import QueryRouterIntegration
from services.query_router import QueryRouter

router = QueryRouter()
integration = QueryRouterIntegration(query_router=router)
```

#### Methods

##### `is_pricing_query(query)`

Detect if query is about pricing.

**Parameters:**
- `query` (str): User query text

**Returns:** `bool` - True if pricing query detected

**Example:**
```python
if integration.is_pricing_query("What is the price?"):
    # Route to pricing collection
```

##### `route_query(query, collection_override=None, enable_fallbacks=False)`

Route query to appropriate collection(s).

**Parameters:**
- `query` (str): User query text
- `collection_override` (str): Force specific collection
- `enable_fallbacks` (bool): Return fallback collections

**Returns:** `dict` - Routing information

**Example:**
```python
routing = integration.route_query(
    query="Tell me about visas",
    enable_fallbacks=True
)
# Returns: {
#     "collection_name": "visa_oracle",
#     "collections": ["visa_oracle", "legal_architect"],
#     "confidence": 0.85,
#     "is_pricing": False,
# }
```

---

## Dependency Injection Pattern

All services support dependency injection for testability:

```python
# In tests - inject mocks
mock_manager = Mock(CollectionManager)
mock_resolver = Mock(ConflictResolver)

service = SearchService(
    collection_manager=mock_manager,
    conflict_resolver=mock_resolver,
)

# In production - use defaults
service = SearchService()  # Creates dependencies automatically
```

## Migration Guide

### Before (Old API)

```python
# Old way - still works
service = SearchService()
results = await service.search("query", user_level=3)
insights = await service.query_cultural_insights("hello")
```

### After (New API)

```python
# New way - with dependency injection
collection_manager = CollectionManager()
cultural_insights = CulturalInsightsService(...)
service = SearchService(
    collection_manager=collection_manager,
    cultural_insights=cultural_insights,
)

# Or use services directly
insights = await cultural_insights.query_insights("hello")
```

## Performance Considerations

- **Lazy Loading:** Collections are loaded on-demand
- **Caching:** Collection clients are cached after first access
- **Connection Pooling:** Uses asyncpg pool for database operations
- **Parallel Search:** Multiple collections searched in parallel

## Error Handling

All services raise exceptions on critical errors:
- `ValueError`: Invalid parameters
- `RuntimeError`: Service initialization failures
- `ConnectionError`: Database/Qdrant connection failures

Services return `None` or empty lists for non-critical failures (e.g., collection not found).

## Testing

See test files:
- `tests/unit/test_collection_manager.py`
- `tests/unit/test_conflict_resolver.py`
- `tests/unit/test_cultural_insights_service.py`
- `tests/unit/test_query_router_integration.py`
- `tests/unit/test_search_service_refactored.py`
- `tests/performance/test_search_service_benchmark.py`


















