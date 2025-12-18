"""
NUZANTARA PRIME - Knowledge Router
HTTP interface for RAG/Search operations

REFACTORED: Now uses SearchService (canonical retriever) instead of KnowledgeService singleton.
This eliminates duplicate RAG pipelines and cache collisions.
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.models import ChunkMetadata, SearchQuery, SearchResponse, SearchResult, TierLevel
from app.modules.knowledge.service import KnowledgeService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["knowledge"])

# Fallback service instance (only used if SearchService not available in app.state)
_knowledge_service_fallback: KnowledgeService | None = None


def get_search_service(request: Request):
    """
    Get SearchService from app.state (canonical retriever).
    Falls back to KnowledgeService singleton only if SearchService not initialized (test/local boot).
    """
    # Try to get SearchService from app.state (preferred - canonical retriever)
    search_service = getattr(request.app.state, "search_service", None)
    if search_service:
        logger.debug("Using SearchService from app.state (canonical retriever)")
        return search_service

    # Fallback to KnowledgeService singleton (for test/local boot scenarios)
    logger.warning(
        "SearchService not found in app.state, falling back to KnowledgeService singleton. "
        "This should only happen in test/local boot scenarios."
    )
    global _knowledge_service_fallback
    if _knowledge_service_fallback is None:
        _knowledge_service_fallback = KnowledgeService()
    return _knowledge_service_fallback


@router.post("/", response_model=SearchResponse)
async def semantic_search(query: SearchQuery, request: Request) -> SearchResponse:
    """
    Semantic search with tier-based access control.

    - **query**: Search query text
    - **level**: User access level (0-3)
    - **limit**: Maximum results (1-50, default 5)
    - **tier_filter**: Optional specific tier filter

    Returns relevant book chunks filtered by user's access level.

    REFACTORED: Now uses SearchService (canonical retriever) instead of KnowledgeService singleton.
    This ensures consistent RAG pipeline across chat agentic and /api/search endpoints.
    """
    try:
        start_time = time.time()

        logger.info(
            f"Received query: '{query.query}', collection={query.collection}, level={query.level}, limit={query.limit}"
        )

        # Validate level
        if query.level < 0 or query.level > 3:
            raise HTTPException(status_code=400, detail="Invalid access level. Must be 0-3.")

        # Get service instance (SearchService preferred, KnowledgeService fallback)
        search_service = get_search_service(request)

        # Perform search using canonical SearchService
        # apply_filters=True ensures tier/exclude_repealed filters are applied (required for /api/search)
        raw_results = await search_service.search(
            query=query.query,
            user_level=query.level,
            limit=query.limit,
            tier_filter=query.tier_filter,
            collection_override=query.collection,
            apply_filters=True,  # Enable filters for /api/search endpoint
        )

        # Format results
        search_results: list[SearchResult] = []

        if raw_results.get("results"):
            for result_dict in raw_results["results"]:
                # Extract data
                text = result_dict.get("text", "")
                metadata_dict = result_dict.get("metadata", {})
                score = result_dict.get("score", 0.0)

                # Convert score to similarity (already normalized)
                similarity_score = score

                # Create metadata model
                # Convert tier string to TierLevel enum (with fallback to TierLevel.C)
                tier_str = metadata_dict.get("tier", "C")
                try:
                    tier = TierLevel(tier_str) if isinstance(tier_str, str) else TierLevel.C
                except (ValueError, TypeError):
                    tier = TierLevel.C

                metadata = ChunkMetadata(
                    book_title=metadata_dict.get("book_title", "Unknown"),
                    book_author=metadata_dict.get("book_author", "Unknown"),
                    tier=tier,
                    min_level=metadata_dict.get("min_level", 0),
                    chunk_index=metadata_dict.get("chunk_index", 0),
                    page_number=metadata_dict.get("page_number"),
                    language=metadata_dict.get("language", "en"),
                    topics=metadata_dict.get("topics", []),
                    file_path=metadata_dict.get("file_path", ""),
                    total_chunks=metadata_dict.get("total_chunks", 0),
                )

                # Create search result
                result = SearchResult(
                    text=text, metadata=metadata, similarity_score=round(similarity_score, 4)
                )

                search_results.append(result)

        execution_time = (time.time() - start_time) * 1000

        logger.info(
            f"Search completed: '{query.query}' (level {query.level}) -> "
            f"{len(search_results)} results in {execution_time:.2f}ms"
        )

        return SearchResponse(
            query=query.query,
            results=search_results,
            total_found=len(search_results),
            user_level=query.level,
            execution_time_ms=round(execution_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}") from e


@router.get("/health")
async def search_health(request: Request) -> dict[str, Any]:
    """Quick health check for search service"""
    try:
        # Verify SearchService is available (or fallback to KnowledgeService)
        get_search_service(request)  # Verify service is available
        service_name = (
            "SearchService" if hasattr(request.app.state, "search_service") else "KnowledgeService"
        )
        return {
            "status": "operational",
            "service": service_name,
            "embeddings": "ready",
            "vector_db": "connected",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Knowledge service unhealthy: {str(e)}") from e


@router.get("/debug/parent-documents/{document_id}")
async def get_parent_documents_debug(document_id: str) -> dict[str, Any]:
    """DEBUG endpoint: Get parent documents (BAB) from PostgreSQL for a document"""
    import asyncpg
    from app.core.config import settings

    try:
        conn = await asyncpg.connect(settings.database_url)

        records = await conn.fetch("""
            SELECT id, document_id, type, title, pasal_count, char_count,
                   LEFT(full_text, 2000) as text_preview,
                   LENGTH(full_text) as full_text_length
            FROM parent_documents
            WHERE document_id = $1
            ORDER BY id
        """, document_id)

        await conn.close()

        bab_list = []
        for r in records:
            bab_list.append({
                "id": r["id"],
                "document_id": r["document_id"],
                "type": r["type"],
                "title": r["title"],
                "pasal_count": r["pasal_count"],
                "char_count": r["char_count"],
                "full_text_length": r["full_text_length"],
                "text_preview": r["text_preview"]
            })

        return {
            "document_id": document_id,
            "total_bab": len(bab_list),
            "bab": bab_list
        }

    except Exception as e:
        logger.error(f"Error fetching parent documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch parent documents: {str(e)}") from e


# TEMPORARY PUBLIC ENDPOINT - NO AUTH
router_public = APIRouter(prefix="/api/public", tags=["public"])

@router_public.get("/bab/{document_id}")
async def get_bab_public(document_id: str) -> dict[str, Any]:
    """TEMPORARY PUBLIC - Get BAB without authentication"""
    import asyncpg
    from app.core.config import settings

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=30)

        records = await conn.fetch("""
            SELECT id, title, pasal_count, char_count,
                   LEFT(full_text, 2000) as text_preview,
                   LENGTH(full_text) as full_text_length
            FROM parent_documents
            WHERE document_id = $1
            ORDER BY id
        """, document_id)

        await conn.close()

        bab_list = [dict(r) for r in records]

        return {
            "document_id": document_id,
            "total_bab": len(bab_list),
            "bab": bab_list
        }

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
