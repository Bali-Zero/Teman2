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

import asyncio
import json
import logging
import time
from typing import Any

import asyncpg

from backend.services.memory import MemoryOrchestrator, get_memory_cache

logger = logging.getLogger(__name__)


async def fetch_profile_and_history(
    db_pool: Any,
    user_id: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Fetch user profile and conversation history from database.

    This is extracted as a separate function to enable parallel execution
    with memory facts loading.

    Args:
        db_pool: Database connection pool
        user_id: User identifier (email or UUID)
        session_id: Optional session ID to filter conversation history

    Returns:
        Dict with 'profile', 'history', 'entities' keys
    """
    context = {"profile": None, "history": [], "entities": {}}

    if not db_pool or not user_id or user_id == "anonymous":
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
                    f"🧠 [ContextManager] Executing profile query for user_id: {user_id}, session_id: {session_id}",
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
                    f"🧠 [ContextManager] Executing profile query for user_id: {user_id} (no session_id)",
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

    return context


async def fetch_memory_facts(
    memory_orchestrator: MemoryOrchestrator | None,
    user_id: str,
    query: str | None = None,
) -> dict[str, Any]:
    """
    Fetch memory facts from MemoryOrchestrator.

    This is extracted as a separate function to enable parallel execution
    with profile/history loading.

    Args:
        memory_orchestrator: Optional pre-initialized memory orchestrator
        user_id: User identifier (email or UUID)
        query: Optional query for query-aware collective memory retrieval

    Returns:
        Dict with 'facts', 'collective_facts', and other memory data
    """
    memory_data = {
        "facts": [],
        "collective_facts": [],
        "timeline_summary": None,
        "kg_entities": [],
        "summary": None,
        "counters": None,
        "memory_context": None,
    }

    if not memory_orchestrator:
        logger.warning("⚠️  [ContextManager] NO memory_orchestrator provided")
        return memory_data

    try:
        logger.warning(f"🧠 [ContextManager] Loading memory facts for user: {user_id}")

        # Pass query for query-aware collective memory retrieval
        memory_context = await memory_orchestrator.get_user_context(user_id, query=query)

        memory_data["facts"] = memory_context.profile_facts
        memory_data["collective_facts"] = memory_context.collective_facts
        memory_data["timeline_summary"] = memory_context.timeline_summary
        memory_data["kg_entities"] = memory_context.kg_entities
        memory_data["summary"] = memory_context.summary
        memory_data["counters"] = memory_context.counters
        memory_data["memory_context"] = memory_context  # Full context for system prompt

        logger.warning(
            f"✅ [ContextManager] Memory loaded: {len(memory_context.profile_facts)} personal facts, "
            f"{len(memory_context.collective_facts)} collective facts, "
            f"{len(memory_context.kg_entities)} KG entities for {user_id}",
        )

        # DIAGNOSTIC: Log first 3 facts for debugging
        if memory_context.profile_facts:
            logger.warning(f"📋 [ContextManager] Sample facts: {memory_context.profile_facts[:3]}")
        else:
            logger.warning(
                f"⚠️  [ContextManager] NO profile facts found for {user_id} - user recognition will fail!",
            )

    except (asyncpg.PostgresError, ValueError, RuntimeError, KeyError) as e:
        logger.error(
            f"❌ [ContextManager] Failed to fetch memory context for {user_id}: {e}",
            exc_info=True,
        )

    return memory_data


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
    start_time = time.time()

    logger.warning(
        f"🔍 [ContextManager] get_user_context called with user_id='{user_id}', session_id='{session_id}', query={query[:50] if query else None}...",
    )
    context = {"profile": None, "history": [], "facts": [], "collective_facts": [], "entities": {}}

    # Always check in-memory cache for entities first (most recent)
    if user_id and user_id != "anonymous":
        try:
            get_memory_cache()
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
            "🧠 [ContextManager] DB Pool missing or user anonymous, returning empty context",
        )
        return context

    # 🚀 PARALLEL EXECUTION: Profile + Memory (Phase 1.1 Optimization)
    # These two operations are completely independent and can run concurrently
    # We measure individual timings by wrapping each task with timing logic
    async def _timed_profile_fetch() -> Any:
        task_start = time.time()
        result = await fetch_profile_and_history(db_pool, user_id, session_id)
        task_time = time.time() - task_start
        return result, task_time

    async def _timed_memory_fetch() -> Any:
        task_start = time.time()
        result = await fetch_memory_facts(memory_orchestrator, original_user_id, query)
        task_time = time.time() - task_start
        return result, task_time

    # Execute both tasks in parallel
    results = await asyncio.gather(
        _timed_profile_fetch(),
        _timed_memory_fetch(),
        return_exceptions=True,  # Don't fail if one task fails
    )

    profile_data, memory_data = results

    # Handle profile result
    if isinstance(profile_data, Exception):
        logger.error(f"❌ Profile fetch failed: {profile_data}", exc_info=True)
        profile_time = 0.0
    else:
        profile_result, profile_time = profile_data
        context.update(profile_result)
        logger.info(f"⏱️  [ContextManager] Profile fetch: {profile_time:.3f}s")

    # Handle memory result
    if isinstance(memory_data, Exception):
        logger.error(f"❌ Memory fetch failed: {memory_data}", exc_info=True)
        # Fallback: empty facts (graceful degradation)
        context["facts"] = []
        context["collective_facts"] = []
        memory_time = 0.0
    else:
        memory_result, memory_time = memory_data
        context.update(memory_result)
        logger.info(f"⏱️  [ContextManager] Memory fetch: {memory_time:.3f}s")

    total_time = time.time() - start_time

    # Calculate speedup (estimated sequential time vs actual parallel time)
    if not isinstance(profile_data, Exception) and not isinstance(memory_data, Exception):
        estimated_sequential_time = profile_time + memory_time
        speedup = max(0, estimated_sequential_time - total_time)
        logger.warning(
            f"⚡ [ContextManager] PARALLEL LOADING completed in {total_time:.3f}s "
            f"(DB: {profile_time:.3f}s, Memory: {memory_time:.3f}s, "
            f"speedup: ~{speedup:.3f}s vs sequential ~{estimated_sequential_time:.3f}s)",
        )
    else:
        logger.warning(
            f"⚡ [ContextManager] PARALLEL LOADING completed in {total_time:.3f}s "
            f"(one or more tasks failed)",
        )

    return context
