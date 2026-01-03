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

import json
import logging
from typing import Any

import asyncpg

from services.memory import MemoryOrchestrator, get_memory_cache

logger = logging.getLogger(__name__)


async def get_user_context(
    db_pool: Any,
    user_id: str,
    memory_orchestrator: MemoryOrchestrator | None = None,
    query: str | None = None,
    deep_think_mode: bool = False,
    session_id: str | None = None,
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
        deep_think_mode: Whether deep thinking mode is enabled
        session_id: Optional session ID to filter conversation history by specific session

    Returns:
        Dictionary containing:
        - profile: User profile data
        - history: Recent conversation messages (filtered by session_id if provided)
        - facts: Personal memory facts
        - collective_facts: Shared knowledge
        - entities: Extracted entities from cache
        - summary: Memory summary
        - counters: Memory statistics
    """
    logger.warning(
        f"🔍 [ContextManager] get_user_context called with user_id='{user_id}', session_id='{session_id}', query={query[:50] if query else None}..."
    )
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
            logger.warning("Memory cache lookup skipped - user_id not found in cache")
            pass
        except (KeyError, ValueError, RuntimeError) as e:
            logger.warning(f"⚠️ Memory cache lookup failed: {e}", exc_info=True)

    # Keep original user_id (email) for memory queries
    original_user_id = user_id

    if not db_pool or not user_id or user_id == "anonymous":
        logger.debug(
            "🧠 [ContextManager] DB Pool missing or user anonymous, returning empty context"
        )
        return context

    try:
        async with db_pool.acquire() as conn:
            # OPTIMIZED: Single combined query for profile + recent conversations
            # Uses user_profiles + team_access tables
            # FIX: Filter by session_id if provided to avoid cross-session contamination
            if session_id:
                query_combined = """
                    SELECT
                        up.id, up.full_name as name, ta.role, tm.department,
                        up.language_pref as preferred_language, tm.notes,
                        up.email,
                        COALESCE(
                            (
                                SELECT json_build_object(
                                    'id', c.id,
                                    'messages', c.messages
                                )
                                FROM conversations c
                                WHERE (c.user_id = CAST(up.id AS TEXT) OR c.user_id = up.email)
                                  AND c.session_id = $2
                                ORDER BY c.created_at DESC
                                LIMIT 1
                            ),
                            NULL
                        ) as latest_conversation
                    FROM user_profiles up
                    LEFT JOIN team_access ta ON ta.user_id = up.id
                    LEFT JOIN team_members tm ON tm.email = up.email
                    WHERE CAST(up.id AS TEXT) = $1 OR up.email = $1
                """
                logger.info(
                    f"🧠 [ContextManager] Executing profile query for user_id: {user_id}, session_id: {session_id}"
                )
                row = await conn.fetchrow(query_combined, user_id, session_id)
            else:
                query_combined = """
                    SELECT
                        up.id, up.full_name as name, ta.role, tm.department,
                        up.language_pref as preferred_language, tm.notes,
                        up.email,
                        COALESCE(
                            (
                                SELECT json_build_object(
                                    'id', c.id,
                                    'messages', c.messages
                                )
                                FROM conversations c
                                WHERE c.user_id = CAST(up.id AS TEXT) OR c.user_id = up.email
                                ORDER BY c.created_at DESC
                                LIMIT 1
                            ),
                            NULL
                        ) as latest_conversation
                    FROM user_profiles up
                    LEFT JOIN team_access ta ON ta.user_id = up.id
                    LEFT JOIN team_members tm ON tm.email = up.email
                    WHERE CAST(up.id AS TEXT) = $1 OR up.email = $1
                """
                logger.info(
                    f"🧠 [ContextManager] Executing profile query for user_id: {user_id} (no session_id)"
                )
                row = await conn.fetchrow(query_combined, user_id)

            if row:
                logger.info(f"✅ [ContextManager] Found profile: {row['name']} ({row['role']})")
                # Extract profile (including email and notes from team_members table)
                context["profile"] = {
                    "id": row["id"],
                    "name": row["name"],
                    "role": row["role"],
                    "department": row["department"],
                    "preferred_language": row["preferred_language"],
                    "notes": row["notes"],
                    "email": row.get("email"),
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
                        # Take last 20 messages (10 turns) for better context retention
                        context["history"] = msgs[-20:] if len(msgs) > 0 else []

                        # Also try to get entities from this conversation ID from cache
                        conversation_id = str(conv["id"])
                        mem_cache = get_memory_cache()
                        context["entities"] = mem_cache.get_entities(conversation_id)

    except (asyncpg.PostgresError, asyncpg.InterfaceError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to fetch profile/history for {user_id}: {e}", exc_info=True)

    # Get Memory Facts via MemoryOrchestrator (single source of truth)
    # FIX USER RECOGNITION BUG: ALWAYS load memory facts, even on first query
    # The previous logic skipped facts on first query to "avoid hallucination",
    # but this prevented user recognition completely!
    if memory_orchestrator:
        try:
            logger.warning(f"🧠 [ContextManager] Loading memory facts for user: {original_user_id}")

            # Pass query for query-aware collective memory retrieval
            memory_context = await memory_orchestrator.get_user_context(
                original_user_id, query=query
            )
            context["facts"] = memory_context.profile_facts
            context["collective_facts"] = memory_context.collective_facts
            context["timeline_summary"] = memory_context.timeline_summary
            context["kg_entities"] = memory_context.kg_entities
            context["summary"] = memory_context.summary
            context["counters"] = memory_context.counters
            context["memory_context"] = memory_context  # Full context for system prompt

            logger.warning(
                f"✅ [ContextManager] Memory loaded: {len(memory_context.profile_facts)} personal facts, "
                f"{len(memory_context.collective_facts)} collective facts, "
                f"{len(memory_context.kg_entities)} KG entities for {original_user_id}"
            )

            # DIAGNOSTIC: Log first 3 facts for debugging
            if memory_context.profile_facts:
                logger.warning(f"📋 [ContextManager] Sample facts: {memory_context.profile_facts[:3]}")
            else:
                logger.warning(f"⚠️  [ContextManager] NO profile facts found for {original_user_id} - user recognition will fail!")

        except (asyncpg.PostgresError, ValueError, RuntimeError, KeyError) as e:
            logger.error(
                f"❌ [ContextManager] Failed to fetch memory context for {original_user_id}: {e}",
                exc_info=True,
            )
            # Fallback: empty facts (graceful degradation)
            context["facts"] = []
            context["collective_facts"] = []
    else:
        logger.warning("⚠️  [ContextManager] NO memory_orchestrator provided - memory facts will be empty!")

    return context
