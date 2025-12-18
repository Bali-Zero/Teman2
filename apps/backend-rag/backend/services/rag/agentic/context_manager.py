"""
User Context Management for Agentic RAG

This module handles retrieval and management of user context including:
- User profile data from team_members table
- Conversation history
- Memory facts (via MemoryOrchestrator)
- Collective knowledge facts
- Memory vector search for recall assist

Key Features:
- Optimized single-query profile + history fetch (eliminates N+1 pattern)
- Integration with MemoryOrchestrator as single source of truth
- Memory cache fallback for entity extraction
- Graceful degradation on failures
"""

import asyncpg
import httpx
import json
import logging
from typing import Any

from qdrant_client.http import exceptions as qdrant_exceptions

from services.memory import MemoryOrchestrator
from services.memory_fallback import get_memory_cache

logger = logging.getLogger(__name__)


async def get_user_context(
    db_pool: Any,
    user_id: str,
    memory_orchestrator: MemoryOrchestrator | None = None,
    query: str | None = None,
    deep_think_mode: bool = False,
) -> dict[str, Any]:
    """
    Retrieve user profile, history, and memory facts.

    Uses MemoryOrchestrator as single source of truth for memory facts/summary/counters.
    Profile and history are still fetched directly (not part of memory orchestrator scope).

    Args:
        db_pool: Database connection pool
        user_id: User identifier (email or UUID)
        memory_orchestrator: Optional pre-initialized memory orchestrator
        query: Optional query for query-aware collective memory retrieval

    Returns:
        Dictionary containing:
        - profile: User profile data
        - history: Recent conversation messages
        - facts: Personal memory facts
        - collective_facts: Shared knowledge
        - entities: Extracted entities from cache
        - summary: Memory summary
        - counters: Memory statistics
    """
    logger.debug(f"🧠 [ContextManager] get_user_context called with user_id='{user_id}', query={query[:50] if query else None}...")
    context = {"profile": None, "history": [], "facts": [], "collective_facts": [], "entities": {}}

    # Always check in-memory cache for entities first (most recent)
    if user_id and user_id != "anonymous":
        try:
            mem_cache = get_memory_cache()
            # Get entities from cache
            # We don't have conversation_id here easily, so we might need to rely on what we have
            # For now, let's try to get entities if we can find a recent conversation for this user
            # This is a limitation of the current cache design (keyed by conversation_id)
            # But we can iterate to find the user's latest conversation
            pass
        except (KeyError, ValueError, RuntimeError) as e:
            logger.warning(f"⚠️ Memory cache lookup failed: {e}", exc_info=True)

    # Keep original user_id (email) for memory queries
    original_user_id = user_id

    if not db_pool or not user_id or user_id == "anonymous":
        logger.debug("🧠 [ContextManager] DB Pool missing or user anonymous, returning empty context")
        return context

    try:
        async with db_pool.acquire() as conn:
            # OPTIMIZED: Single combined query for profile + recent conversations
            # This eliminates N+1 query pattern (was 2 separate queries)
            query_combined = """
                SELECT
                    tm.id, tm.full_name as name, tm.role, tm.department,
                    tm.language as preferred_language, tm.notes,
                    COALESCE(
                        (
                            SELECT json_build_object(
                                'id', c.id,
                                'messages', c.messages
                            )
                            FROM conversations c
                            WHERE c.user_id = CAST(tm.id AS TEXT) OR c.user_id = tm.email
                            ORDER BY c.created_at DESC
                            LIMIT 1
                        ),
                        NULL
                    ) as latest_conversation
                FROM team_members tm
                WHERE CAST(tm.id AS TEXT) = $1 OR tm.email = $1
            """
            logger.info(f"🧠 [ContextManager] Executing profile query for user_id: {user_id}")
            row = await conn.fetchrow(query_combined, user_id)
            
            if row:
                logger.info(f"✅ [ContextManager] Found profile: {row['name']} ({row['role']})")
                # Extract profile
                context["profile"] = {
                    "id": row["id"],
                    "name": row["name"],
                    "role": row["role"],
                    "department": row["department"],
                    "preferred_language": row["preferred_language"],
                    "notes": row["notes"],
                }

                # Use actual ID for further queries (stored by UUID)
                if context["profile"].get("id"):
                    user_id = context["profile"]["id"]

                # Extract conversation history
                if row["latest_conversation"]:
                    conv = row["latest_conversation"]
                    # Parse JSON string to dict if needed (asyncpg returns JSONB as string)
                    if isinstance(conv, str):
                        conv = json.loads(conv)
                    if conv.get("messages"):
                        msgs = conv["messages"]
                        if isinstance(msgs, str):
                            msgs = json.loads(msgs)
                        # Take last 6 messages (3 turns)
                        context["history"] = msgs[-6:] if len(msgs) > 0 else []

                        # Also try to get entities from this conversation ID from cache
                        conversation_id = str(conv["id"])
                        mem_cache = get_memory_cache()
                        context["entities"] = mem_cache.get_entities(conversation_id)

    except (asyncpg.PostgresError, asyncpg.InterfaceError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to fetch profile/history for {user_id}: {e}", exc_info=True)

    # Get Memory Facts via MemoryOrchestrator (single source of truth)
    if memory_orchestrator:
        try:
            # Pass query for query-aware collective memory retrieval
            memory_context = await memory_orchestrator.get_user_context(original_user_id, query=query)
            context["facts"] = memory_context.profile_facts
            context["collective_facts"] = memory_context.collective_facts
            context["timeline_summary"] = memory_context.timeline_summary
            context["kg_entities"] = memory_context.kg_entities
            context["summary"] = memory_context.summary
            context["counters"] = memory_context.counters
            context["memory_context"] = memory_context  # Full context for system prompt

            logger.debug(
                f"🧠 [ContextManager] Memory via orchestrator: {len(memory_context.profile_facts)} personal facts, "
                f"{len(memory_context.collective_facts)} collective facts, {len(memory_context.kg_entities)} KG entities for {original_user_id}"
            )
        except (asyncpg.PostgresError, ValueError, RuntimeError, KeyError) as e:
            logger.error(f"Failed to fetch memory context via orchestrator for {original_user_id}: {e}", exc_info=True)
            # Fallback: empty facts (graceful degradation)

    return context


async def search_memory_vector(
    query: str, user_id: str, limit: int = 5
) -> list[dict[str, Any]]:
    """
    Search zantara_memories collection for personal/team context (Recall Assist).
    Only used for identity/team_query intents, not for business/legal queries.

    Args:
        query: Search query
        user_id: User identifier (email)
        limit: Max results

    Returns:
        List of memory candidates with text and metadata
    """
    try:
        from core.qdrant_db import QdrantClient
        from core.embeddings import create_embeddings_generator
        from app.core.config import settings

        # Initialize memory vector DB client
        memory_db = QdrantClient(
            qdrant_url=settings.qdrant_url, collection_name="zantara_memories"
        )

        # Generate query embedding
        embedder = create_embeddings_generator()
        query_embedding = embedder.generate_query_embedding(query)

        # Build filter: only memories for this user or team
        where_filter = None
        if user_id and user_id != "anonymous":
            # Filter by userId if available in metadata
            where_filter = {"userId": {"$eq": user_id}}

        # Search Qdrant
        results = await memory_db.search(
            query_embedding=query_embedding, filter=where_filter, limit=limit
        )

        # Format results
        candidates = []
        for i in range(len(results.get("documents", []))):
            candidates.append(
                {
                    "text": results["documents"][i],
                    "metadata": results["metadatas"][i] if i < len(results.get("metadatas", [])) else {},
                    "score": 1 / (1 + results["distances"][i]) if i < len(results.get("distances", [])) else 0.0,
                }
            )

        return candidates

    except (qdrant_exceptions.UnexpectedResponse, httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning(f"⚠️ Memory vector search failed: {e}", exc_info=True)
        return []
