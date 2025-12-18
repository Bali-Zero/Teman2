"""
ZANTARA RAG - Memory Vector Router
Semantic memory storage and search using Qdrant
Complements Firestore-based memory system with vector search capabilities
"""

import logging
import time
from typing import Any

from core.embeddings import create_embeddings_generator
from core.qdrant_db import QdrantClient
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])

# Initialize services
embedder = create_embeddings_generator()
memory_vector_db: QdrantClient | None = None


async def initialize_memory_vector_db(qdrant_url: str | None = None) -> QdrantClient:
    """Create or refresh the Qdrant collection used for semantic memories."""
    global memory_vector_db
    # Use Qdrant URL from centralized config or override
    target_url = qdrant_url or settings.qdrant_url

    try:
        memory_vector_db = QdrantClient(qdrant_url=target_url, collection_name="zantara_memories")
        stats = await memory_vector_db.get_collection_stats()
        logger.info(
            "✅ Memory vector DB ready (collection='zantara_memories', url='{}', total={})".format(
                target_url, stats.get("total_documents", 0)
            )
        )
    except Exception as exc:
        logger.error(f"Memory vector DB initialization failed: {exc}")
        raise

    return memory_vector_db


async def get_memory_vector_db() -> QdrantClient:
    """Return an initialized memory vector database instance."""
    global memory_vector_db
    if memory_vector_db is None:
        logger.warning("Memory vector DB not initialized; creating with default Qdrant URL")
        return await initialize_memory_vector_db()
    return memory_vector_db


# Request/Response Models
class EmbedRequest(BaseModel):
    text: str
    model: str = "sentence-transformers"


class EmbedResponse(BaseModel):
    embedding: list[float]
    dimensions: int
    model: str


class StoreMemoryRequest(BaseModel):
    id: str
    document: str
    embedding: list[float]
    metadata: dict[str, Any]


class SearchMemoryRequest(BaseModel):
    query_embedding: list[float]
    limit: int = 10
    metadata_filter: dict[str, Any] | None = None


class SimilarMemoryRequest(BaseModel):
    memory_id: str
    limit: int = 5


class MemorySearchResponse(BaseModel):
    results: list[dict[str, Any]]
    ids: list[str]
    distances: list[float]
    total_found: int
    execution_time_ms: float


class InitRequest(BaseModel):
    qdrant_url: str | None = None


class InitResponse(BaseModel):
    status: str
    collection: str
    qdrant_url: str
    total_memories: int


# Endpoints


@router.post("/init", response_model=InitResponse)
async def init_memory_collection(request: InitRequest) -> InitResponse:
    """Reinitialize the semantic memory collection after deployments or resets."""
    try:
        db = await initialize_memory_vector_db(request.qdrant_url)
        stats = await db.get_collection_stats()
        return InitResponse(
            status="initialized",
            collection=stats.get("collection_name", "zantara_memories"),
            qdrant_url=db.qdrant_url,
            total_memories=stats.get("total_documents", 0),
        )
    except Exception as exc:
        logger.error(f"Memory vector init failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(exc)}") from exc


@router.post("/embed", response_model=EmbedResponse)
async def generate_embedding(request: EmbedRequest):
    """
    Generate embedding for text.
    Uses sentence-transformers (FREE, local) by default.
    """
    try:
        embedding = embedder.generate_single_embedding(request.text)

        return EmbedResponse(embedding=embedding, dimensions=len(embedding), model=embedder.model)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}") from e


@router.post("/store")
async def store_memory_vector(request: StoreMemoryRequest):
    """
    Store memory in Qdrant for semantic search.

    Metadata should include:
    - userId: User ID
    - type: Memory type (profile, expertise, event, etc)
    - timestamp: ISO timestamp
    - entities: Comma-separated entities
    """
    try:
        db = await get_memory_vector_db()
        await db.upsert_documents(
            chunks=[request.document],
            embeddings=[request.embedding],
            metadatas=[request.metadata],
            ids=[request.id],
        )

        logger.info(f"✅ Memory stored: {request.id} for user {request.metadata.get('userId')}")

        return {"success": True, "memory_id": request.id, "collection": "zantara_memories"}
    except Exception as e:
        logger.error(f"Memory storage failed: {e}")
        raise HTTPException(status_code=500, detail=f"Storage failed: {str(e)}") from e


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories_semantic(request: SearchMemoryRequest):
    """
    Semantic search across all memories using vector similarity.

    Supports metadata filtering:
    - userId: Filter by specific user
    - entities: Filter by entity (use {"entities": {"$contains": "zero"}})
    """
    try:
        start_time = time.time()

        # Prepare filter (Qdrant filter format)
        where_filter = None
        if request.metadata_filter:
            # Convert TypeScript-style filter to Qdrant format
            where_filter = {}
            for key, value in request.metadata_filter.items():
                if isinstance(value, dict) and "$contains" in value:
                    # Handle contains filter (Qdrant supports text matching)
                    where_filter[key] = value["$contains"]
                else:
                    where_filter[key] = value

        # Search Qdrant (async)
        db = await get_memory_vector_db()
        results = await db.search(
            query_embedding=request.query_embedding, filter=where_filter, limit=request.limit
        )

        execution_time = (time.time() - start_time) * 1000

        # Format results
        formatted_results = []
        for idx in range(len(results["documents"])):
            formatted_results.append(
                {
                    "document": results["documents"][idx],
                    "metadata": results["metadatas"][idx],
                    "distance": results["distances"][idx],
                }
            )

        logger.info(
            f"Memory search completed: {len(formatted_results)} results in {execution_time:.2f}ms"
        )

        return MemorySearchResponse(
            results=formatted_results,
            ids=results["ids"],
            distances=results["distances"],
            total_found=results["total_found"],
            execution_time_ms=round(execution_time, 2),
        )

    except Exception as e:
        logger.error(f"Memory search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}") from e


@router.post("/similar", response_model=MemorySearchResponse)
async def find_similar_memories(request: SimilarMemoryRequest):
    """
    Find memories similar to a given memory.
    Uses the stored memory's embedding to find neighbors.
    """
    try:
        start_time = time.time()

        db = await get_memory_vector_db()

        # Get the memory's embedding from Qdrant
        memory = await db.get(ids=[request.memory_id], include=["embeddings"])

        embeddings_raw = memory.get("embeddings") if isinstance(memory, dict) else None
        if embeddings_raw is None or len(embeddings_raw) == 0:
            raise HTTPException(status_code=404, detail=f"Memory not found: {request.memory_id}")

        # Normalize embedding payloads returned by Qdrant
        first_embedding = embeddings_raw[0]
        if isinstance(first_embedding, list | tuple):
            query_embedding = list(first_embedding)
        elif isinstance(first_embedding, int | float):
            # Handle flat vectors returned directly as a single list of floats
            query_embedding = list(embeddings_raw)
        else:
            raise HTTPException(
                status_code=500, detail="Invalid embedding format returned by vector store"
            )

        results = await db.search(
            query_embedding=query_embedding,
            limit=request.limit + 1,  # +1 because it will include itself
        )

        logger.debug(f"Similar search raw results: {results}")

        # Remove the original memory from results
        filtered_results = {"ids": [], "documents": [], "metadatas": [], "distances": []}

        for idx in range(len(results["ids"])):
            if results["ids"][idx] != request.memory_id:
                filtered_results["ids"].append(results["ids"][idx])
                filtered_results["documents"].append(results["documents"][idx])
                filtered_results["metadatas"].append(results["metadatas"][idx])
                filtered_results["distances"].append(results["distances"][idx])

        # Limit to requested number
        for key in filtered_results:
            filtered_results[key] = filtered_results[key][: request.limit]

        execution_time = (time.time() - start_time) * 1000

        formatted_results = []
        for idx in range(len(filtered_results["documents"])):
            formatted_results.append(
                {
                    "document": filtered_results["documents"][idx],
                    "metadata": filtered_results["metadatas"][idx],
                    "distance": filtered_results["distances"][idx],
                }
            )

        logger.info(
            f"Similar memories found: {len(formatted_results)} results in {execution_time:.2f}ms"
        )

        return MemorySearchResponse(
            results=formatted_results,
            ids=filtered_results["ids"],
            distances=filtered_results["distances"],
            total_found=len(formatted_results),
            execution_time_ms=round(execution_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similar memory search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Similar search failed: {str(e)}") from e


@router.delete("/{memory_id}")
async def delete_memory_vector(memory_id: str):
    """Delete memory from vector store"""
    try:
        db = await get_memory_vector_db()
        await db.delete(ids=[memory_id])

        logger.info(f"✅ Memory deleted: {memory_id}")

        return {"success": True, "deleted_id": memory_id}
    except Exception as e:
        logger.error(f"Memory deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}") from e


@router.get("/stats")
async def get_memory_stats():
    """Get memory collection statistics"""
    try:
        db = await get_memory_vector_db()
        stats = await db.get_collection_stats()

        peek_data = await db.peek(limit=1000)
        return {
            "total_memories": stats.get("total_documents", 0),
            "collection_name": stats.get("collection_name", "zantara_memories"),
            "qdrant_url": db.qdrant_url,
            "users": len({m.get("userId", "") for m in peek_data.get("metadatas", [])}),
            "collection_size_mb": stats.get("total_documents", 0) * 0.001,  # Rough estimate
        }
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        return {"total_memories": 0, "users": 0, "collection_size_mb": 0, "error": str(e)}


@router.get("/health")
async def memory_vector_health():
    """Health check for memory vector service"""
    try:
        db = await get_memory_vector_db()
        stats = await db.get_collection_stats()

        return {
            "status": "operational",
            "service": "memory_vector",
            "collection": "zantara_memories",
            "total_memories": stats.get("total_documents", 0),
            "embedder_model": embedder.model,
            "embedder_provider": embedder.provider,
            "dimensions": embedder.dimensions,
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Memory vector service unhealthy: {str(e)}"
        ) from e
