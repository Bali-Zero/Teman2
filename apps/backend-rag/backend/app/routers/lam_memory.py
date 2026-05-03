"""
LAM Episodic Memory Router
Provides save/recall/list/delete endpoints for the LAM agent's episodic memory.
Uses Qdrant collection 'lam_episodes' with text-embedding-3-small (FROZEN, 1536 dims).
"""

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.core.cache import invalidate_cache
from backend.core.qdrant_db import QdrantClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory/lam", tags=["lam-memory"])

COLLECTION = "lam_episodes"

_qdrant: QdrantClient | None = None
_embedder = None


async def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(qdrant_url=settings.qdrant_url, collection_name=COLLECTION)
        try:
            await _qdrant.get_stats()
            logger.info(f"✅ LAM memory: connected to '{COLLECTION}'")
        except Exception:
            # Collection may not exist yet — create it on first save
            logger.info(
                f"LAM memory: collection '{COLLECTION}' not found, will create on first write",
            )
    return _qdrant


def _get_embedder() -> Any:
    global _embedder
    if _embedder is None:
        from backend.core.embeddings import create_embeddings_generator

        _embedder = create_embeddings_generator()
    return _embedder


# --- Models ---


class SaveEpisodeRequest(BaseModel):
    content: str
    agent: str = "main"
    tags: list[str] = []
    outcome: str = ""
    metadata: dict[str, Any] = {}


class SaveEpisodeResponse(BaseModel):
    id: str
    status: str


class RecallRequest(BaseModel):
    query: str
    limit: int = 5
    agent: str | None = None


class EpisodeResult(BaseModel):
    id: str
    content: str
    agent: str
    tags: list[str]
    outcome: str
    timestamp: str
    score: float
    metadata: dict[str, Any]


class RecallResponse(BaseModel):
    results: list[EpisodeResult]
    query: str
    execution_time_ms: float


class ListEpisodesResponse(BaseModel):
    episodes: list[EpisodeResult]
    total: int


# --- Endpoints ---


@router.post("/episodes", response_model=SaveEpisodeResponse)
async def save_episode(request: SaveEpisodeRequest) -> SaveEpisodeResponse:
    """Save an episodic memory for the LAM agent."""
    try:
        embedder = _get_embedder()
        embedding = await embedder.generate_single_embedding(request.content)

        episode_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        payload = {
            "content": request.content,
            "agent": request.agent,
            "tags": request.tags,
            "outcome": request.outcome,
            "timestamp": timestamp,
            **request.metadata,
        }

        db = await _get_qdrant()
        await db.upsert_documents(
            chunks=[request.content],
            embeddings=[embedding],
            metadatas=[payload],
            ids=[episode_id],
        )

        logger.info(f"LAM episode saved: {episode_id} (agent={request.agent})")
        await invalidate_cache("zantara:lam_memory:*")
        return SaveEpisodeResponse(id=episode_id, status="saved")

    except Exception as e:
        logger.error(f"LAM save_episode failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/recall", response_model=RecallResponse)
async def recall_similar(request: RecallRequest) -> RecallResponse:
    """Recall semantically similar episodes by query text."""
    start = time.time()
    try:
        embedder = _get_embedder()
        embedding = await embedder.generate_single_embedding(request.query)

        db = await _get_qdrant()
        filter_conditions = None
        if request.agent:
            filter_conditions = {"agent": request.agent}

        raw = await db.search(
            query_embedding=embedding,
            limit=request.limit,
            filter=filter_conditions,
        )

        # db.search() returns a dict with parallel arrays:
        # {"ids": [...], "documents": [...], "metadatas": [...], "scores": [...], "total_found": N}
        results = []
        ids = raw.get("ids", []) if isinstance(raw, dict) else []
        documents = raw.get("documents", []) if isinstance(raw, dict) else []
        metadatas = raw.get("metadatas", []) if isinstance(raw, dict) else []
        scores = raw.get("scores", []) if isinstance(raw, dict) else []

        for i, doc_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            if not isinstance(meta, dict):
                meta = {}
            doc = documents[i] if i < len(documents) else ""
            score = scores[i] if i < len(scores) else 0.0

            results.append(
                EpisodeResult(
                    id=str(doc_id),
                    content=meta.get("content", doc),
                    agent=meta.get("agent", ""),
                    tags=meta.get("tags", []),
                    outcome=meta.get("outcome", ""),
                    timestamp=meta.get("timestamp", ""),
                    score=score,
                    metadata={
                        k: v
                        for k, v in meta.items()
                        if k not in ("content", "agent", "tags", "outcome", "timestamp")
                    },
                ),
            )

        elapsed_ms = (time.time() - start) * 1000
        return RecallResponse(results=results, query=request.query, execution_time_ms=elapsed_ms)

    except Exception as e:
        err_str = str(e)
        # Collection not found = expected when no episodes have been saved yet
        if "not found" in err_str.lower() or "doesn't exist" in err_str.lower() or "404" in err_str:
            logger.info(f"LAM recall: collection '{COLLECTION}' not yet created — returning empty")
            elapsed_ms = (time.time() - start) * 1000
            return RecallResponse(results=[], query=request.query, execution_time_ms=elapsed_ms)
        logger.error(f"LAM recall failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/episodes", response_model=ListEpisodesResponse)
async def list_recent_episodes(limit: int = 10, agent: str | None = None) -> ListEpisodesResponse:
    """List the most recent LAM episodes, optionally filtered by agent."""
    try:
        db = await _get_qdrant()
        filter_conditions = {"agent": agent} if agent else None

        # Use scroll to get recent episodes (no vector needed)
        raw = await db.scroll(limit=limit, metadata_filter=filter_conditions)

        episodes = []
        for item in raw:
            payload = item.get("payload", {})
            episodes.append(
                EpisodeResult(
                    id=item.get("id", ""),
                    content=payload.get("content", ""),
                    agent=payload.get("agent", ""),
                    tags=payload.get("tags", []),
                    outcome=payload.get("outcome", ""),
                    timestamp=payload.get("timestamp", ""),
                    score=1.0,
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ("content", "agent", "tags", "outcome", "timestamp")
                    },
                ),
            )

        return ListEpisodesResponse(episodes=episodes, total=len(episodes))

    except Exception as e:
        err_str = str(e)
        if "not found" in err_str.lower() or "doesn't exist" in err_str.lower() or "404" in err_str:
            logger.info(
                f"LAM list_episodes: collection '{COLLECTION}' not yet created — returning empty",
            )
            return ListEpisodesResponse(episodes=[], total=0)
        logger.error(f"LAM list_episodes failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/episodes/{episode_id}")
async def delete_episode(episode_id: str) -> dict[str, str]:
    """Delete a specific episode by ID."""
    try:
        db = await _get_qdrant()
        await db.delete([episode_id])
        logger.info(f"LAM episode deleted: {episode_id}")
        await invalidate_cache("zantara:lam_memory:*")
        return {"status": "deleted", "id": episode_id}
    except Exception as e:
        logger.error(f"LAM delete_episode failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
