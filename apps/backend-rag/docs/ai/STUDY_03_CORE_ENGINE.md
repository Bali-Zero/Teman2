# ⚙️ PARTE 3: Core Engine (RAG Infrastructure)

> Motore vettoriale e processing pipeline

---

## Overview

**Location:** `backend/core/`

Il Core Engine gestisce l'infrastruttura RAG: vector database, embeddings, chunking, caching, e reranking.

---

## Files Structure

```
core/
├── __init__.py           # Exports
├── qdrant_db.py          # Vector DB operations (1,225 LOC) ⭐
├── embeddings.py         # Text → vectors (346 LOC) ⭐
├── chunker.py            # Text chunking (251 LOC)
├── cache.py              # Multi-level cache (415 LOC)
├── parsers.py            # Document parsing (502 LOC)
├── bm25_vectorizer.py    # Sparse vectors (366 LOC)
├── reranker.py           # Result reranking (184 LOC)
├── exceptions.py         # Custom exceptions (327 LOC)
├── legal/                # Legal document processing
│   ├── structure_parser.py
│   └── hierarchical_indexer.py
└── plugins/              # Plugin system
    ├── registry.py
    └── executor.py
```

**Totale:** ~3,617 linee di codice

---

## QdrantDB - Vector Database

**File:** `core/qdrant_db.py` (1,225 LOC)

### Architecture

```
┌─────────────────────────────────────────┐
│              QdrantDB                   │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     HTTP Client (httpx)         │    │
│  │     - Connection pooling        │    │
│  │     - Async operations          │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     Error Classifier            │    │
│  │     - Retryable detection       │    │
│  │     - Error categorization      │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     Metrics Tracking            │    │
│  │     - Search latency            │    │
│  │     - Upsert counts             │    │
│  │     - Error rates               │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Error Classification

```python
class QdrantErrorType(Enum):
    """Error types for classification."""
    RETRYABLE = "retryable"      # 500, 502, 503, 504
    NON_RETRYABLE = "non_retryable"  # 400, 401, 403, 404
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    CONNECTION = "connection"

class QdrantErrorClassifier:
    """Classify errors for retry decisions."""
    
    RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
    NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}
    
    def classify(self, error: Exception) -> tuple[QdrantErrorType, bool]:
        """Returns (error_type, should_retry)."""
        if isinstance(error, httpx.TimeoutException):
            return QdrantErrorType.TIMEOUT, True
        if isinstance(error, httpx.ConnectError):
            return QdrantErrorType.CONNECTION, True
        # ...
```

### Connection Settings

```python
# Connection pool limits
MAX_KEEPALIVE_CONNECTIONS = 10
MAX_CONNECTIONS = 20
CONNECT_TIMEOUT = 10.0  # seconds

# Retry settings
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

# Dimensions
DEFAULT_OPENAI_DIMENSIONS = 1536
DEFAULT_SENTENCE_TRANSFORMERS_DIMENSIONS = 384
```

### Main Class

```python
class QdrantDB:
    """
    Async Qdrant client wrapper.
    
    Uses httpx for async HTTP with connection pooling.
    All operations are async to avoid blocking.
    """
    
    def __init__(self, url: str = None, api_key: str = None):
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        
        # HTTP client with pooling
        self._client = httpx.AsyncClient(
            base_url=self.url,
            headers={"api-key": self.api_key} if self.api_key else {},
            limits=httpx.Limits(
                max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
                max_connections=MAX_CONNECTIONS
            ),
            timeout=httpx.Timeout(CONNECT_TIMEOUT)
        )
```

### Core Operations

```python
# Collection Management
async def create_collection(
    self,
    collection_name: str,
    vector_size: int = 768,
    distance: str = "Cosine"
) -> bool:
    """Create a new collection."""
    payload = {
        "vectors": {
            "size": vector_size,
            "distance": distance
        }
    }
    response = await self._client.put(
        f"/collections/{collection_name}",
        json=payload
    )
    return response.status_code == 200

async def delete_collection(self, collection_name: str) -> bool:
    """Delete a collection."""
    response = await self._client.delete(
        f"/collections/{collection_name}"
    )
    return response.status_code == 200

# Vector Operations
async def upsert_vectors(
    self,
    collection_name: str,
    points: list[dict]
) -> dict:
    """
    Upsert vectors to collection.
    
    Args:
        collection_name: Target collection
        points: [{"id": "...", "vector": [...], "payload": {...}}]
    
    Returns:
        {"status": "ok", "result": {...}}
    """
    response = await self._client.put(
        f"/collections/{collection_name}/points",
        json={"points": points}
    )
    return response.json()

async def search(
    self,
    collection_name: str,
    query_vector: list[float],
    limit: int = 10,
    filter: dict = None,
    with_payload: bool = True,
    score_threshold: float = None
) -> list[dict]:
    """
    Search for similar vectors.
    
    Args:
        collection_name: Collection to search
        query_vector: Query embedding
        limit: Max results
        filter: Qdrant filter conditions
        with_payload: Include metadata
        score_threshold: Minimum similarity score
    
    Returns:
        [{"id": "...", "score": 0.95, "payload": {...}}, ...]
    """
    payload = {
        "vector": query_vector,
        "limit": limit,
        "with_payload": with_payload
    }
    
    if filter:
        payload["filter"] = filter
    if score_threshold:
        payload["score_threshold"] = score_threshold
    
    response = await self._client.post(
        f"/collections/{collection_name}/points/search",
        json=payload
    )
    return response.json().get("result", [])
```

### Hybrid Search (Dense + Sparse)

```python
async def hybrid_search(
    self,
    collection_name: str,
    dense_vector: list[float],
    sparse_vector: dict,  # {"indices": [...], "values": [...]}
    limit: int = 10,
    alpha: float = 0.5  # Balance: 0=sparse, 1=dense
) -> list[dict]:
    """
    Hybrid search combining dense and sparse vectors.
    
    Uses Reciprocal Rank Fusion (RRF) for result merging.
    """
    # Dense search
    dense_results = await self.search(
        collection_name, dense_vector, limit=limit*2
    )
    
    # Sparse search (BM25)
    sparse_results = await self._sparse_search(
        collection_name, sparse_vector, limit=limit*2
    )
    
    # RRF fusion
    return self._rrf_fusion(dense_results, sparse_results, alpha, limit)
```

### Collections Used

| Collection | Purpose | Vector Size |
|------------|---------|-------------|
| `visa_knowledge` | Visa/immigration info | 768 |
| `business_knowledge` | Business setup, PT/CV | 768 |
| `legal_knowledge` | Indonesian laws | 768 |
| `politics_knowledge` | Political news | 768 |
| `pricing_knowledge` | Service pricing | 768 |
| `team_knowledge` | Internal team info | 768 |
| `client_memory` | Per-client memory | 768 |

---

## Embeddings

**File:** `core/embeddings.py` (346 LOC)

```python
class EmbeddingService:
    """
    Text embedding generation.
    
    Providers:
    - Google text-embedding-004 (default)
    - OpenAI text-embedding-3-large
    - Local via Ollama
    
    Features:
    - Batch processing
    - Caching (optional)
    - Fallback chain
    """
    
    def __init__(self, provider: str = "google"):
        self.provider = provider
        self.dimension = 768  # Default for Google
        
        if provider == "google":
            self._client = self._init_google()
        elif provider == "openai":
            self._client = self._init_openai()
            self.dimension = 1536
        elif provider == "ollama":
            self._client = self._init_ollama()
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for single text."""
        return await self.embed_batch([text])[0]
    
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Processes in batches to respect API limits.
        """
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = await self._embed_batch_internal(batch)
            embeddings.extend(batch_embeddings)
        return embeddings
    
    async def _embed_batch_internal(self, texts: list[str]) -> list[list[float]]:
        """Provider-specific batch embedding."""
        if self.provider == "google":
            from google import genai
            result = await self._google_client.aio.models.embed_content(
                model="text-embedding-004",
                content=texts
            )
            return [e.values for e in result.embeddings]
        # ... other providers
```

---

## Chunker

**File:** `core/chunker.py` (251 LOC)

```python
class ChunkerStrategy(Enum):
    """Chunking strategies."""
    FIXED = "fixed"           # Fixed size chunks
    SENTENCE = "sentence"     # Sentence boundaries
    PARAGRAPH = "paragraph"   # Paragraph boundaries
    SEMANTIC = "semantic"     # Semantic similarity
    RECURSIVE = "recursive"   # LangChain-style

class Chunker:
    """
    Text chunking for RAG.
    
    Strategies:
    - Fixed: Simple fixed-size chunks
    - Sentence: Respect sentence boundaries
    - Paragraph: Respect paragraph boundaries
    - Semantic: Group by semantic similarity
    - Recursive: Try largest then smaller splits
    """
    
    def __init__(
        self,
        strategy: ChunkerStrategy = ChunkerStrategy.RECURSIVE,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk(self, text: str) -> list[str]:
        """Split text into chunks."""
        if self.strategy == ChunkerStrategy.FIXED:
            return self._fixed_chunk(text)
        elif self.strategy == ChunkerStrategy.SENTENCE:
            return self._sentence_chunk(text)
        elif self.strategy == ChunkerStrategy.RECURSIVE:
            return self._recursive_chunk(text)
        # ...
    
    def _recursive_chunk(self, text: str) -> list[str]:
        """
        Recursive chunking (LangChain style).
        
        Try splits in order: \n\n, \n, . , " "
        Fall back to smaller if chunks too large.
        """
        separators = ["\n\n", "\n", ". ", " "]
        return self._split_recursive(text, separators)
```

---

## Cache

**File:** `core/cache.py` (415 LOC)

```python
class CacheLevel(Enum):
    """Cache hierarchy levels."""
    MEMORY = "memory"    # In-process (fastest)
    REDIS = "redis"      # Distributed (shared)
    DISK = "disk"        # Persistent (cheapest)

class MultiLevelCache:
    """
    Multi-level caching system.
    
    Hierarchy:
    1. Memory (LRU, ~1000 items)
    2. Redis (distributed, TTL-based)
    3. Disk (persistent, for large items)
    
    Features:
    - Automatic promotion/demotion
    - TTL per level
    - Compression for large values
    """
    
    def __init__(self):
        self._memory = LRUCache(maxsize=1000)
        self._redis = None  # Lazy init
        self._disk = None   # Lazy init
    
    async def get(self, key: str) -> Any | None:
        """Get from cache (tries all levels)."""
        # Try memory first
        if key in self._memory:
            return self._memory[key]
        
        # Try Redis
        if self._redis:
            value = await self._redis.get(key)
            if value:
                # Promote to memory
                self._memory[key] = value
                return value
        
        # Try disk
        if self._disk:
            value = self._disk.get(key)
            if value:
                # Promote to memory
                self._memory[key] = value
                return value
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        levels: list[CacheLevel] = None
    ):
        """Set in cache (specified levels)."""
        levels = levels or [CacheLevel.MEMORY, CacheLevel.REDIS]
        
        if CacheLevel.MEMORY in levels:
            self._memory[key] = value
        
        if CacheLevel.REDIS in levels and self._redis:
            await self._redis.setex(key, ttl, value)
        
        if CacheLevel.DISK in levels and self._disk:
            self._disk.set(key, value)
```

### Semantic Cache

```python
class SemanticCache:
    """
    Cache based on semantic similarity.
    
    For queries like:
    - "What is KITAS?" → cached
    - "Can you explain KITAS?" → cache HIT (similar meaning)
    
    Uses embedding similarity for cache lookup.
    """
    
    def __init__(self, similarity_threshold: float = 0.92):
        self.threshold = similarity_threshold
        self.embedding_service = EmbeddingService()
        self._cache = {}  # {embedding_key: (query, response)}
    
    async def get(self, query: str) -> str | None:
        """Find similar cached query."""
        query_embedding = await self.embedding_service.embed(query)
        
        for cached_embedding, (cached_query, response) in self._cache.items():
            similarity = self._cosine_similarity(
                query_embedding, cached_embedding
            )
            if similarity >= self.threshold:
                logger.info(f"Semantic cache hit: {query} ≈ {cached_query}")
                return response
        
        return None
```

---

## Parsers

**File:** `core/parsers.py` (502 LOC)

```python
class DocumentParser:
    """
    Parse various document formats.
    
    Supported:
    - PDF (PyPDF2, pdfplumber)
    - DOCX (python-docx)
    - TXT (plain text)
    - HTML (BeautifulSoup)
    - Markdown
    """
    
    def parse(self, file_path: str) -> ParsedDocument:
        """Auto-detect and parse document."""
        ext = Path(file_path).suffix.lower()
        
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".docx":
            return self._parse_docx(file_path)
        elif ext == ".txt":
            return self._parse_txt(file_path)
        elif ext in [".html", ".htm"]:
            return self._parse_html(file_path)
        elif ext == ".md":
            return self._parse_markdown(file_path)
        else:
            raise UnsupportedFormatError(ext)
    
    def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """
        Parse PDF with fallback strategies.
        
        1. Try pdfplumber (better for tables)
        2. Fallback to PyPDF2 (more robust)
        3. OCR if needed (pytesseract)
        """
        pass
```

---

## Reranker

**File:** `core/reranker.py` (184 LOC)

```python
class Reranker:
    """
    Rerank search results for relevance.
    
    Methods:
    - Cross-encoder (most accurate, slow)
    - BM25 (fast, keyword-based)
    - Reciprocal Rank Fusion (combine rankings)
    """
    
    def __init__(self, method: str = "cross_encoder"):
        self.method = method
        
        if method == "cross_encoder":
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 10
    ) -> list[dict]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: Original query
            documents: [{"content": "...", "score": 0.8, ...}]
            top_k: Number of results to return
        
        Returns:
            Reranked documents with updated scores
        """
        if self.method == "cross_encoder":
            return self._rerank_cross_encoder(query, documents, top_k)
        elif self.method == "bm25":
            return self._rerank_bm25(query, documents, top_k)
        elif self.method == "rrf":
            return self._rerank_rrf(query, documents, top_k)
    
    def _rerank_cross_encoder(
        self,
        query: str,
        documents: list[dict],
        top_k: int
    ) -> list[dict]:
        """Rerank using cross-encoder model."""
        pairs = [(query, doc["content"]) for doc in documents]
        scores = self.model.predict(pairs)
        
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)
        
        return sorted(
            documents,
            key=lambda x: x["rerank_score"],
            reverse=True
        )[:top_k]
```

---

## BM25 Vectorizer

**File:** `core/bm25_vectorizer.py` (366 LOC)

```python
class BM25Vectorizer:
    """
    BM25 sparse vector generation.
    
    Used for:
    - Hybrid search (dense + sparse)
    - Keyword matching
    - Fast initial filtering
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # Term frequency saturation
        self.b = b    # Length normalization
        self._vocabulary = {}
        self._idf = {}
    
    def fit(self, documents: list[str]):
        """Build vocabulary and IDF from documents."""
        from collections import Counter
        
        # Build vocabulary
        all_terms = set()
        doc_freqs = Counter()
        
        for doc in documents:
            terms = set(self._tokenize(doc))
            all_terms.update(terms)
            for term in terms:
                doc_freqs[term] += 1
        
        # Calculate IDF
        n_docs = len(documents)
        for term, df in doc_freqs.items():
            self._idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5))
        
        self._vocabulary = {term: i for i, term in enumerate(all_terms)}
    
    def vectorize(self, text: str) -> dict:
        """
        Convert text to sparse BM25 vector.
        
        Returns:
            {"indices": [...], "values": [...]}
        """
        terms = self._tokenize(text)
        term_freqs = Counter(terms)
        doc_len = len(terms)
        avg_len = self._avg_doc_length
        
        indices = []
        values = []
        
        for term, tf in term_freqs.items():
            if term in self._vocabulary:
                idx = self._vocabulary[term]
                idf = self._idf.get(term, 0)
                
                # BM25 score
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_len)
                score = idf * numerator / denominator
                
                indices.append(idx)
                values.append(score)
        
        return {"indices": indices, "values": values}
```

---

## Metrics

```python
# Global metrics tracking
_qdrant_metrics = {
    "search_calls": 0,
    "search_total_time": 0.0,
    "upsert_calls": 0,
    "upsert_total_time": 0.0,
    "upsert_documents_total": 0,
    "retry_count": 0,
    "errors": 0,
}

def get_qdrant_metrics() -> dict:
    """Get operation metrics for monitoring."""
    metrics = _qdrant_metrics.copy()
    
    if metrics["search_calls"] > 0:
        metrics["search_avg_time_ms"] = (
            metrics["search_total_time"] / metrics["search_calls"]
        ) * 1000
    
    return metrics
```

---

## Usage Examples

### Search
```python
from backend.core.qdrant_db import QdrantDB
from backend.core.embeddings import EmbeddingService

db = QdrantDB()
embeddings = EmbeddingService()

# Generate query embedding
query_embedding = await embeddings.embed("What is KITAS?")

# Search
results = await db.search(
    collection_name="visa_knowledge",
    query_vector=query_embedding,
    limit=5,
    filter={"must": [{"key": "category", "match": {"value": "visa"}}]}
)

for r in results:
    print(f"Score: {r['score']:.2f} - {r['payload']['title']}")
```

### Ingest
```python
from backend.core.chunker import Chunker

chunker = Chunker(chunk_size=1000, chunk_overlap=200)
chunks = chunker.chunk(document_text)

# Embed chunks
embeddings = await embedding_service.embed_batch(chunks)

# Upsert to Qdrant
points = [
    {"id": str(uuid4()), "vector": emb, "payload": {"text": chunk}}
    for chunk, emb in zip(chunks, embeddings)
]
await db.upsert_vectors("visa_knowledge", points)
```

---

*"Vectors speak louder than words" 📐*
