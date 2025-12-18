# RAG Dedup Baseline - Comportamento Attuale

## Endpoint `/api/search` (KnowledgeService)

### Input
- `query`: string (min_length=1)
- `level`: int (0-3, default=0)
- `limit`: int (1-50, default=5)
- `tier_filter`: list[TierLevel] | None
- `collection`: string | None

### Output (SearchResponse)
- `query`: string
- `results`: SearchResult[]
  - `text`: string
  - `metadata`: ChunkMetadata
    - `book_title`: string (default: "Unknown")
    - `book_author`: string (default: "Unknown")
    - `tier`: TierLevel (default: "C")
    - `min_level`: int (default: 0)
    - `chunk_index`: int (default: 0)
    - `page_number`: int | None
    - `language`: string (default: "en")
    - `topics`: list[str] (default: [])
    - `file_path`: string (default: "")
    - `total_chunks`: int (default: 0)
  - `similarity_score`: float (0.0-1.0)
- `total_found`: int
- `user_level`: int
- `execution_time_ms`: float

### Comportamento KnowledgeService.search()
- Routing: pricing detection → `bali_zero_pricing`, altrimenti `QueryRouter.route()`
- Filtri: applicati solo per `zantara_books` collection (tier-based)
- Cache: `@cached(ttl=300, prefix="rag_search")`
- Score: `1 / (1 + distance)` con boost +0.15 per pricing

## Chat Agentic (SearchService)

### Input (via VectorSearchTool)
- `query`: string
- `collection`: string | None (enum: legal_unified, visa_oracle, tax_genius, kbli_unified, litigation_oracle)
- `top_k`: int (default: 5)

### Output (dict)
- `query`: string
- `results`: list[dict]
  - `id`: string | None
  - `text`: string
  - `metadata`: dict (raw Qdrant metadata)
  - `score`: float
- `user_level`: int
- `allowed_tiers`: list[str]
- `collection_used`: string

### Comportamento SearchService.search()
- Routing: `QueryRouterIntegration.route_query()` con pricing detection
- Filtri: **DISABILITATI** (NUCLEAR DEBUG override)
- Cache: `@cached(ttl=300, prefix="rag_search")` - **STESSA CHIAVE** di KnowledgeService!
- Score: `1 / (1 + distance)` con boost da SearchConstants per pricing

## Differenze Critiche

1. **Filtri**: KnowledgeService applica filtri tier per `zantara_books`, SearchService li disabilita sempre
2. **Cache collision**: Entrambi usano `prefix="rag_search"` → risultati cross-contaminated
3. **Metadata mapping**: KnowledgeService mappa a `ChunkMetadata` con fallback, SearchService ritorna raw dict
4. **Routing**: KnowledgeService usa `QueryRouter.route()` diretto, SearchService usa `QueryRouterIntegration.route_query()`

## Note per Dedup

- `/api/search` si aspetta `ChunkMetadata` con campi specifici; i metadati Qdrant potrebbero non averli tutti
- Il router deve mappare `metadata` dict → `ChunkMetadata` con fallback sensati
- Mantenere comportamento filtri invariato: `/api/search` deve continuare ad applicare filtri tier per `zantara_books`
- SearchService deve esporre parametro per controllare applicazione filtri senza cambiare default chat

