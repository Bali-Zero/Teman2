"""
Intel News API - Search and manage Bali intelligence news
"""

import logging
from datetime import datetime, timedelta

from core.embeddings import create_embeddings_generator
from core.qdrant_db import QdrantClient
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

embedder = create_embeddings_generator()

# Qdrant collections for intel
INTEL_COLLECTIONS = {
    "immigration": "bali_intel_immigration",
    "bkpm_tax": "bali_intel_bkpm_tax",
    "realestate": "bali_intel_realestate",
    "events": "bali_intel_events",
    "social": "bali_intel_social",
    "competitors": "bali_intel_competitors",
    "bali_news": "bali_intel_bali_news",
    "roundup": "bali_intel_roundup",
}


class IntelSearchRequest(BaseModel):
    query: str
    category: str | None = None
    date_range: str = "last_7_days"
    tier: list[str] = ["T1", "T2", "T3"]  # Fixed: Changed from "1","2","3" to match Qdrant storage
    impact_level: str | None = None
    limit: int = 20


class IntelStoreRequest(BaseModel):
    collection: str
    id: str
    document: str
    embedding: list[float]
    metadata: dict
    full_data: dict


@router.post("/api/intel/search")
async def search_intel(request: IntelSearchRequest):
    """Search intel news with semantic search"""
    try:
        # Generate query embedding
        query_embedding = embedder.generate_single_embedding(request.query)

        # Determine collections to search
        if request.category:
            collection_names = [INTEL_COLLECTIONS.get(request.category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        all_results = []

        for collection_name in collection_names:
            if not collection_name:
                continue

            try:
                client = QdrantClient(collection_name=collection_name)

                # Build metadata filter
                where_filter = {"tier": {"$in": request.tier}}

                # Add date range filter
                if request.date_range != "all":
                    days_map = {
                        "today": 1,
                        "last_7_days": 7,
                        "last_30_days": 30,
                        "last_90_days": 90,
                    }
                    days = days_map.get(request.date_range, 7)
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    where_filter["published_date"] = {"$gte": cutoff_date}

                # Add impact level filter
                if request.impact_level:
                    where_filter["impact_level"] = request.impact_level

                # Search (async)
                results = await client.search(
                    query_embedding=query_embedding, filter=where_filter, limit=request.limit
                )

                # Parse results
                for doc, metadata, distance in zip(
                    results.get("documents", []),
                    results.get("metadatas", []),
                    results.get("distances", []),
                    strict=True,
                ):
                    similarity_score = 1 / (1 + distance)  # Convert distance to similarity

                    all_results.append(
                        {
                            "id": metadata.get("id"),
                            "title": metadata.get("title"),
                            "summary_english": doc[:300],  # First 300 chars
                            "summary_italian": metadata.get("summary_italian", ""),
                            "source": metadata.get("source"),
                            "tier": metadata.get("tier"),
                            "published_date": metadata.get("published_date"),
                            "category": collection_name.replace("bali_intel_", ""),
                            "impact_level": metadata.get("impact_level"),
                            "url": metadata.get("url"),
                            "key_changes": metadata.get("key_changes"),
                            "action_required": metadata.get("action_required") == "True",
                            "deadline_date": metadata.get("deadline_date"),
                            "similarity_score": similarity_score,
                        }
                    )

            except Exception as e:
                logger.warning(f"Error searching collection {collection_name}: {e}")
                continue

        # Sort by similarity score
        all_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Limit total results
        all_results = all_results[: request.limit]

        return {"results": all_results, "total": len(all_results)}

    except Exception as e:
        logger.error(f"Intel search error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/intel/store")
async def store_intel(request: IntelStoreRequest):
    """Store intel news item in Qdrant"""
    try:
        collection_name = INTEL_COLLECTIONS.get(request.collection)
        if not collection_name:
            raise HTTPException(status_code=400, detail=f"Invalid collection: {request.collection}")

        client = QdrantClient(collection_name=collection_name)

        await client.upsert_documents(
            chunks=[request.document],
            embeddings=[request.embedding],
            metadatas=[request.metadata],
            ids=[request.id],
        )

        return {"success": True, "collection": collection_name, "id": request.id}

    except Exception as e:
        logger.error(f"Store intel error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/critical")
async def get_critical_items(category: str | None = None, days: int = 7):
    """Get critical impact items"""
    try:
        if category:
            collection_names = [INTEL_COLLECTIONS.get(category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        critical_items = []
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        for collection_name in collection_names:
            if not collection_name:
                continue

            try:
                client = QdrantClient(collection_name=collection_name)

                # Qdrant: Use peek to get documents, then filter in Python
                # TODO: Implement Qdrant filter support for better performance
                results = client.peek(limit=100)

                # Filter in Python for now
                filtered_metadatas = []
                for metadata in results.get("metadatas", []):
                    if (
                        metadata.get("impact_level") == "critical"
                        and metadata.get("published_date", "") >= cutoff_date
                    ):
                        filtered_metadatas.append(metadata)

                for metadata in filtered_metadatas[:50]:
                    critical_items.append(
                        {
                            "id": metadata.get("id"),
                            "title": metadata.get("title"),
                            "source": metadata.get("source"),
                            "tier": metadata.get("tier"),
                            "published_date": metadata.get("published_date"),
                            "category": collection_name.replace("bali_intel_", ""),
                            "url": metadata.get("url"),
                            "action_required": metadata.get("action_required") == "True",
                            "deadline_date": metadata.get("deadline_date"),
                        }
                    )

            except Exception:
                continue

        # Sort by date (newest first)
        critical_items.sort(key=lambda x: x.get("published_date", ""), reverse=True)

        return {"items": critical_items, "count": len(critical_items)}

    except Exception as e:
        logger.error(f"Get critical items error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/trends")
async def get_trends(category: str | None = None, _days: int = 30):
    """Get trending topics and keywords"""
    try:
        # This would require more sophisticated analysis
        # For now, return basic stats

        if category:
            collection_names = [INTEL_COLLECTIONS.get(category)]
        else:
            collection_names = list(INTEL_COLLECTIONS.values())

        all_keywords = []

        for collection_name in collection_names:
            if not collection_name:
                continue

            try:
                client = QdrantClient(collection_name=collection_name)
                stats = client.get_collection_stats()

                # Extract keywords from metadata (simplified)
                # In production, you'd want NLP-based topic modeling

                all_keywords.append(
                    {
                        "collection": collection_name.replace("bali_intel_", ""),
                        "total_items": stats.get("total_documents", 0),
                    }
                )

            except Exception:
                continue

        return {
            "trends": all_keywords,
            "top_topics": [],  # Would require NLP analysis
        }

    except Exception as e:
        logger.error(f"Get trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/intel/stats/{collection}")
async def get_collection_stats(collection: str):
    """Get statistics for a specific intel collection"""
    try:
        collection_name = INTEL_COLLECTIONS.get(collection)
        if not collection_name:
            raise HTTPException(status_code=404, detail=f"Collection not found: {collection}")

        client = QdrantClient(collection_name=collection_name)
        stats = client.get_collection_stats()

        return {
            "collection_name": collection_name,
            "total_documents": stats.get("total_documents", 0),
            "last_updated": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
