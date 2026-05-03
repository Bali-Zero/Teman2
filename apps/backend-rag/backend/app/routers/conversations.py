"""
ZANTARA Conversations Router
Endpoints for persistent conversation history with PostgreSQL
+ Auto-CRM population from conversations
+ Async LLM-generated conversation titles

SECURITY: All endpoints require JWT authentication (added 2025-12-03)
User identity is taken from JWT token, NOT from request parameters.

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.metrics import metrics_collector
from backend.core.cache import invalidate_cache
from backend.app.utils.error_handlers import handle_database_error
from backend.app.utils.json_utils import to_jsonb
from backend.app.utils.logging_utils import get_logger, log_error, log_success, log_warning
from backend.services.common.background import spawn
from backend.services.crm.conversation_title_generator import generate_conversation_title
from backend.services.memory import MemoryOrchestrator, get_memory_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/api/bali-zero/conversations", tags=["conversations"])

# Constants
DEFAULT_LIMIT = 20
MAX_LIMIT = 1000
DEFAULT_CONVERSATION_MESSAGES_LIMIT = 20  # Default messages to return in history
SUMMARY_MAX_LENGTH = 200  # Max length for auto-generated summaries


async def _generate_and_update_title(
    conversation_id: int, first_user_message: str, db_pool: asyncpg.Pool,
) -> None:
    """
    Background task to generate and store conversation title.

    Runs async (fire-and-forget) to avoid blocking conversation save.
    Stores generated title in metadata.generated_title JSONB field.

    Args:
        conversation_id: ID of conversation to update
        first_user_message: First message content for title generation
        db_pool: Database connection pool

    Cost: ~$0.000006 per title (Claude Haiku)
    Latency: Non-blocking (runs in background)
    """
    try:
        # Generate title using LLM
        title = await generate_conversation_title(
            conversation_id=str(conversation_id), first_user_message=first_user_message,
        )

        if title:
            # Update metadata.generated_title in database
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE conversations
                    SET metadata = COALESCE(metadata, '{}'::jsonb) ||
                                   jsonb_build_object('generated_title', $1::text)
                    WHERE id = $2
                    """,
                    title,
                    conversation_id,
                )

            log_success(
                logger,
                "Generated conversation title",
                conversation_id=conversation_id,
                title=title[:50],
            )
        else:
            logger.info(
                f"Title generation returned None for conversation {conversation_id}, using fallback",
            )

    except Exception as e:
        # Don't fail conversation save if title generation fails
        log_warning(
            logger, "Title generation failed", conversation_id=conversation_id, error=str(e),
        )


# Pydantic models
class SaveConversationRequest(BaseModel):
    # NOTE: user_email is no longer accepted from request body for security reasons.
    # The authenticated user's email is extracted from the JWT token.
    messages: list[
        dict
    ]  # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    session_id: str | None = None
    metadata: dict | None = None


class ConversationHistoryResponse(BaseModel):
    success: bool
    messages: list[dict] = []
    total_messages: int = 0
    session_id: str | None = None
    error: str | None = None


class ConversationListItem(BaseModel):
    """Single conversation item for list view"""

    id: int
    title: str
    preview: str
    message_count: int
    created_at: str
    updated_at: str | None = None
    session_id: str | None = None


class ConversationListResponse(BaseModel):
    """List of conversations"""

    success: bool
    conversations: list[ConversationListItem] = []
    total: int = 0
    error: str | None = None


class SingleConversationResponse(BaseModel):
    """Single conversation with full messages"""

    success: bool
    id: int | None = None
    messages: list[dict] = []
    message_count: int = 0
    created_at: str | None = None
    session_id: str | None = None
    metadata: dict | None = None
    error: str | None = None


class UserMemoryContextResponse(BaseModel):
    """User memory context with profile facts"""

    success: bool
    user_id: str
    profile_facts: list[str] = []
    summary: str | None = None
    counters: dict[str, int] = {}
    has_data: bool = False
    error: str | None = None


# Global memory orchestrator instance (lazy initialized)
_memory_orchestrator: MemoryOrchestrator | None = None


async def get_memory_orchestrator(db_pool: asyncpg.Pool | None = None) -> MemoryOrchestrator | None:
    """Get or initialize the global memory orchestrator"""
    global _memory_orchestrator
    if _memory_orchestrator is None:
        try:
            _memory_orchestrator = MemoryOrchestrator(db_pool=db_pool)
            await _memory_orchestrator.initialize()
            log_success(logger, "MemoryOrchestrator initialized for conversations router")
        except Exception as e:
            log_warning(logger, f"Failed to initialize MemoryOrchestrator: {e}")
            return None
    return _memory_orchestrator


@router.post("/save")
async def save_conversation(
    request: SaveConversationRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Save conversation messages to PostgreSQL
    + Auto-populate CRM with client/practice data

    SECURITY: User identity is extracted from JWT token, not request body.

    Body:
    {
        "messages": [{"role": "user", "content": "..."}, ...],
        "session_id": "optional-session-id",
        "metadata": {"key": "value"}
    }

    Returns:
    {
        "success": true,
        "conversation_id": 123,
        "messages_saved": 10,
        "user_email": "authenticated-user@example.com",
        "crm": {
            "processed": true,
            "client_id": 42,
            "client_created": false,
            "client_updated": true,
            "practice_id": 15,
            "practice_created": true,
            "interaction_id": 88
        }
    }
    """
    # Get user email from JWT token (prevents spoofing)
    user_email = current_user["email"]

    # Generate session_id if not provided
    session_id = request.session_id or f"session-{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # RACE CONDITION PROTECTION: Two-phase commit pattern
    # Phase 1: Save to cache (fast, always succeeds)
    mem_cache = get_memory_cache()
    try:
        for msg in request.messages:
            mem_cache.add_message(session_id, msg.get("role", "unknown"), msg.get("content", ""))
        logger.info(
            f"✅ Saved {len(request.messages)} messages to memory cache for session {session_id}",
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to save to memory cache: {e}")
        # Continue - DB save is more important

    # Phase 2: Save to DB with retry mechanism
    conversation_id = 0
    db_success = False
    max_retries = 3

    for attempt in range(max_retries):
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    async with conn.transaction():
                        # Insert conversation atomically
                        row = await conn.fetchrow(
                            """
                            INSERT INTO conversations (user_id, session_id, messages, metadata, created_at)
                            VALUES ($1, $2, $3, $4, $5)
                            RETURNING id
                            """,
                            user_email,
                            session_id,
                            # Use to_jsonb for asyncpg JSONB compatibility (handles Decimal, datetime, UUID)
                            to_jsonb(request.messages),
                            to_jsonb(request.metadata or {}),
                            datetime.now(tz=timezone.utc),
                        )

                        if row:
                            conversation_id = row["id"]
                            db_success = True

                            # Mark cache as synced (if cache supports it)
                            try:
                                if hasattr(mem_cache, "mark_synced"):
                                    mem_cache.mark_synced(session_id, conversation_id)
                            except Exception as e:
                                logger.debug(f"Cache sync marker not available: {e}")

                            log_success(
                                logger,
                                "Saved conversation to DB",
                                conversation_id=conversation_id,
                                user_email=user_email,
                                messages_count=len(request.messages),
                                attempt=attempt + 1,
                            )

                            # Trigger async title generation for new conversations
                            # (fire-and-forget, non-blocking)
                            if conversation_id and request.messages:
                                # Find first user message for title generation
                                first_user_msg = next(
                                    (
                                        msg.get("content", "")
                                        for msg in request.messages
                                        if isinstance(msg, dict) and msg.get("role") == "user"
                                    ),
                                    None,
                                )

                                if first_user_msg:
                                    spawn(
                                        _generate_and_update_title(
                                            conversation_id=conversation_id,
                                            first_user_message=first_user_msg,
                                            db_pool=db_pool,
                                        ),
                                        name=f"conv_title:{conversation_id}",
                                    )
                                    logger.info(
                                        f"🎯 Triggered async title generation for conversation {conversation_id}",
                                    )

                            break  # Success - exit retry loop
            else:
                logger.warning("⚠️ DB Pool unavailable, skipping DB save")
                break

        except Exception as e:
            if attempt == max_retries - 1:
                # Final attempt failed - log error and queue for async retry
                logger.error(f"❌ DB Save failed after {max_retries} attempts: {e}")
                # Note: In production, you might want to queue this for async retry
                # For now, we continue with cache-only persistence
                metrics_collector.record_cache_db_consistency_error(session_id=session_id)
            else:
                # Exponential backoff before retry
                import asyncio

                wait_time = 2**attempt
                logger.warning(
                    f"⚠️ DB Save attempt {attempt + 1} failed, retrying in {wait_time}s: {e}",
                )
                await asyncio.sleep(wait_time)

    # If both failed, then we have a problem
    # But we already tried memory cache.

    await invalidate_cache("zantara:conversations:*")
    return {
        "success": True,  # Always return true to keep chat alive
        "conversation_id": conversation_id,
        "messages_saved": len(request.messages),
        "user_email": user_email,
        "persistence_mode": "db" if db_success else "memory_fallback",
    }


@router.get("/history")
async def get_conversation_history(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    session_id: str | None = Query(None, description="Optional session filter"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
) -> ConversationHistoryResponse:
    """
    Get conversation history for the authenticated user

    SECURITY: User identity is extracted from JWT token.

    Query params:
    - limit: Max number of messages to return (default: 20)
    - session_id: Optional session filter
    """
    # Get user email from JWT token (prevents spoofing)
    user_email = current_user["email"]

    messages = []
    session_id_result = session_id
    total_messages = 0

    # Try DB first
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                # Get most recent conversation for user
                if session_id:
                    row = await conn.fetchrow(
                        """
                        SELECT messages, created_at, session_id
                        FROM conversations
                        WHERE user_id = $1 AND session_id = $2
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        user_email,
                        session_id,
                    )
                else:
                    row = await conn.fetchrow(
                        """
                        SELECT messages, created_at, session_id
                        FROM conversations
                        WHERE user_id = $1
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        user_email,
                    )

                if row:
                    raw_messages = row.get("messages", [])
                    if isinstance(raw_messages, str):
                        try:
                            messages = json.loads(raw_messages)
                        except json.JSONDecodeError:
                            messages = []
                    elif isinstance(raw_messages, list):
                        messages = raw_messages
                    else:
                        messages = []
                    session_id_result = row.get("session_id")
                    log_success(
                        logger,
                        "Retrieved conversation history from DB",
                        user_email=user_email,
                        messages_count=len(messages),
                    )
        except Exception as e:
            log_error(logger, "Failed to retrieve conversation history from DB", error=e)
            # Fallback to memory cache below

    # Fallback to memory cache if DB failed or returned nothing (and we have a session_id)
    if not messages and session_id:
        try:
            mem_cache = get_memory_cache()
            messages = mem_cache.get_messages(session_id, limit=limit)
            if messages:
                log_success(
                    logger,
                    "Retrieved conversation history from Memory Cache",
                    user_email=user_email,
                    messages_count=len(messages),
                )
        except Exception as e:
            logger.warning(f"⚠️ Memory cache retrieval failed: {e}")

    # Limit messages if needed
    total_messages = len(messages)
    if len(messages) > limit:
        messages = messages[-limit:]

    return ConversationHistoryResponse(
        success=True,
        messages=messages,
        total_messages=total_messages,
        session_id=session_id_result,
    )


@router.delete("/clear")
async def clear_conversation_history(
    session_id: str | None = Query(None, description="Optional session filter"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Clear conversation history for the authenticated user

    SECURITY: User identity is extracted from JWT token.

    Query params:
    - session_id: Optional session filter (if omitted, clears ALL conversations for user)
    """
    # Get user email from JWT token (prevents spoofing)
    user_email = current_user["email"]

    try:
        async with db_pool.acquire() as conn:
            if session_id:
                deleted_count = await conn.execute(
                    """
                    DELETE FROM conversations
                    WHERE user_id = $1 AND session_id = $2
                    """,
                    user_email,
                    session_id,
                )
            else:
                deleted_count = await conn.execute(
                    """
                    DELETE FROM conversations
                    WHERE user_id = $1
                    """,
                    user_email,
                )

            # asyncpg execute returns "DELETE N", extract number
            deleted_count_int = int(deleted_count.split()[-1]) if deleted_count else 0

            log_success(
                logger,
                "Cleared conversations",
                user_email=user_email,
                deleted_count=deleted_count_int,
            )

            await invalidate_cache("zantara:conversations:*")
            return {"success": True, "deleted_count": deleted_count_int}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/stats")
async def get_conversation_stats(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Get conversation statistics for the authenticated user

    SECURITY: User identity is extracted from JWT token.
    """
    # Get user email from JWT token (prevents spoofing)
    user_email = current_user["email"]

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_conversations,
                    SUM(jsonb_array_length(messages)) as total_messages,
                    MAX(created_at) as last_conversation
                FROM conversations
                WHERE user_id = $1
                """,
                user_email,
            )

            if not row:
                return {
                    "success": True,
                    "user_email": user_email,
                    "total_conversations": 0,
                    "total_messages": 0,
                    "last_conversation": None,
                }

            return {
                "success": True,
                "user_email": user_email,
                "total_conversations": row["total_conversations"] or 0,
                "total_messages": row["total_messages"] or 0,
                "last_conversation": (
                    row["last_conversation"].isoformat() if row["last_conversation"] else None
                ),
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/list", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConversationListResponse:
    """
    List all conversations for the authenticated user

    SECURITY: User identity is extracted from JWT token.

    Query params:
    - limit: Max number of conversations to return (default: 20)
    - offset: Offset for pagination (default: 0)

    Returns list with title (first user message), preview, and message count.
    """
    user_email = current_user["email"]

    try:
        async with db_pool.acquire() as conn:
            # Get total count
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM conversations WHERE user_id = $1",
                user_email,
            )
            total = count_row["total"] if count_row else 0

            # Get conversations ordered by most recent
            rows = await conn.fetch(
                """
                SELECT id, session_id, messages, metadata, created_at
                FROM conversations
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_email,
                limit,
                offset,
            )

            conversations = []
            for row in rows:
                messages = row["messages"] or []
                metadata = row["metadata"] or {}

                # Fallback chain: generated_title → first_message → default
                # Priority 1: Use LLM-generated title (best quality)
                title = None
                if metadata and isinstance(metadata, dict) and "generated_title" in metadata:
                    title = metadata["generated_title"]

                # Priority 2: Fallback to first message excerpt
                if not title:
                    for msg in messages:
                        if isinstance(msg, dict) and msg.get("role") == "user":
                            content = msg.get("content", "")
                            title = content[:50] + "..." if len(content) > 50 else content
                            break

                # Priority 3: Final fallback to default
                if not title:
                    title = "New Conversation"

                # Extract preview from last assistant message
                preview = ""

                # Extract preview from last assistant message
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        preview = content[:100] + "..." if len(content) > 100 else content
                        break

                conversations.append(
                    ConversationListItem(
                        id=row["id"],
                        title=title or "New Conversation",
                        preview=preview,
                        message_count=len(messages),
                        created_at=row["created_at"].isoformat(),
                        session_id=row["session_id"],
                    ),
                )

            log_success(
                logger,
                "Listed conversations",
                user_email=user_email,
                count=len(conversations),
                total=total,
            )

            return ConversationListResponse(
                success=True,
                conversations=conversations,
                total=total,
            )

    except Exception as e:
        log_error(logger, "Failed to list conversations", error=e, exc_info=True)
        return ConversationListResponse(success=False, error=str(e))


@router.get("/{conversation_id}", response_model=SingleConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> SingleConversationResponse:
    """
    Get a single conversation by ID

    SECURITY: Only returns conversation if it belongs to authenticated user.
    """
    user_email = current_user["email"]

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, session_id, messages, metadata, created_at
                FROM conversations
                WHERE id = $1 AND user_id = $2
                """,
                conversation_id,
                user_email,
            )

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation {conversation_id} not found",
                )

            messages = row["messages"] or []

            log_success(
                logger,
                "Retrieved conversation",
                conversation_id=conversation_id,
                user_email=user_email,
                message_count=len(messages),
            )

            return SingleConversationResponse(
                success=True,
                id=row["id"],
                messages=messages,
                message_count=len(messages),
                created_at=row["created_at"].isoformat(),
                session_id=row["session_id"],
                metadata=row["metadata"],
            )

    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "Failed to get conversation", error=e, exc_info=True)
        return SingleConversationResponse(success=False, error=str(e))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Delete a single conversation by ID

    SECURITY: Only deletes conversation if it belongs to authenticated user.
    """
    user_email = current_user["email"]

    try:
        async with db_pool.acquire() as conn:
            # Check if conversation exists and belongs to user
            existing = await conn.fetchrow(
                "SELECT id FROM conversations WHERE id = $1 AND user_id = $2",
                conversation_id,
                user_email,
            )

            if not existing:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation {conversation_id} not found",
                )

            # Delete the conversation
            await conn.execute(
                "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
                conversation_id,
                user_email,
            )

            log_success(
                logger,
                "Deleted conversation",
                conversation_id=conversation_id,
                user_email=user_email,
            )

            await invalidate_cache("zantara:conversations:*")
            return {"success": True, "deleted_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/memory/context", response_model=UserMemoryContextResponse)
async def get_user_memory_context(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
) -> UserMemoryContextResponse:
    """
    Get user memory context (profile facts, summary, counters)

    SECURITY: User identity is extracted from JWT token.

    Returns the user's stored memory facts and context that the AI uses
    to personalize responses.
    """
    user_email = current_user["email"]

    try:
        orchestrator = await get_memory_orchestrator(db_pool)
        if not orchestrator:
            return UserMemoryContextResponse(
                success=True,
                user_id=user_email,
                has_data=False,
                error="Memory service not available",
            )

        context = await orchestrator.get_user_context(user_email)

        log_success(
            logger,
            "Retrieved user memory context",
            user_email=user_email,
            facts_count=len(context.profile_facts),
            has_data=context.has_data,
        )

        return UserMemoryContextResponse(
            success=True,
            user_id=context.user_id,
            profile_facts=context.profile_facts,
            summary=context.summary,
            counters=context.counters,
            has_data=context.has_data,
        )

    except Exception as e:
        log_error(logger, "Failed to get user memory context", error=e, exc_info=True)
        return UserMemoryContextResponse(
            success=False,
            user_id=user_email,
            error=str(e),
        )
