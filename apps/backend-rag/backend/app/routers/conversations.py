"""
ZANTARA Conversations Router
Endpoints for persistent conversation history with PostgreSQL
+ Auto-CRM population from conversations

SECURITY: All endpoints require JWT authentication (added 2025-12-03)
User identity is taken from JWT token, NOT from request parameters.

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_current_user, get_database_pool
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger, log_error, log_success, log_warning
from services.memory import MemoryOrchestrator
from services.memory_fallback import get_memory_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/api/bali-zero/conversations", tags=["conversations"])

# Constants
DEFAULT_LIMIT = 20
MAX_LIMIT = 1000
DEFAULT_CONVERSATION_MESSAGES_LIMIT = 20  # Default messages to return in history
SUMMARY_MAX_LENGTH = 200  # Max length for auto-generated summaries


# Import auto-CRM service (lazy import to avoid circular dependencies)
_auto_crm_service = None


def get_auto_crm():
    """
    Lazy import of auto-CRM service

    REFACTORED: Service now requires async initialization (connect() must be called).
    For lazy initialization, we check if pool exists and connect if needed.

    SECURITY: Fixed circular dependency by using proper import structure instead of sys.path manipulation.
    """
    global _auto_crm_service
    if _auto_crm_service is None:
        try:
            # SECURITY: Use proper import instead of sys.path.append to avoid circular dependencies
            from services.auto_crm_service import get_auto_crm_service

            _auto_crm_service = get_auto_crm_service()
            # Note: connect() should be called during app startup (main_cloud.py)
            # For lazy initialization, we could connect here, but it's better to do it at startup
            log_success(logger, "Auto-CRM service loaded")
        except ImportError as e:
            log_warning(logger, f"Auto-CRM service not available (import error): {e}")
            _auto_crm_service = False  # Mark as unavailable
        except Exception as e:
            log_warning(logger, f"Auto-CRM service not available: {e}")
            _auto_crm_service = False  # Mark as unavailable
    return _auto_crm_service if _auto_crm_service else None


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
):
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
    session_id = request.session_id or f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # ALWAYS save to memory cache first (fast & reliable)
    try:
        mem_cache = get_memory_cache()
        # We need a conversation_id for the cache. If it's a new conversation, we might not have one yet.
        # For now, we'll use session_id as a proxy key if we don't have a conversation_id
        # But wait, the cache expects conversation_id.
        # Let's use session_id as the key for the memory cache for now, or a temporary ID.
        # Actually, let's just use the session_id as the key.
        for msg in request.messages:
            mem_cache.add_message(session_id, msg.get("role", "unknown"), msg.get("content", ""))
        logger.info(
            f"✅ Saved {len(request.messages)} messages to memory cache for session {session_id}"
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to save to memory cache: {e}")

    conversation_id = 0
    db_success = False

    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                # Insert conversation
                row = await conn.fetchrow(
                    """
                    INSERT INTO conversations (user_id, session_id, messages, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    user_email,
                    session_id,
                    request.messages,
                    request.metadata or {},
                    datetime.now(),
                )

                if row:
                    conversation_id = row["id"]
                    db_success = True
                    log_success(
                        logger,
                        "Saved conversation to DB",
                        conversation_id=conversation_id,
                        user_email=user_email,
                        messages_count=len(request.messages),
                    )
        else:
            logger.warning("⚠️ DB Pool unavailable, skipping DB save")

    except Exception as e:
        logger.error(f"❌ DB Save failed: {e}")
        # Don't raise exception if we saved to memory cache, so the chat continues
        if not db_success:
            logger.info("⚠️ Continuing with memory-only persistence")

    # If both failed, then we have a problem
    # But we already tried memory cache.

    # Auto-populate CRM (don't fail if this fails)
    crm_result = {}
    if db_success:  # Only try CRM if DB save worked, as it likely depends on DB
        auto_crm = get_auto_crm()

        if auto_crm and len(request.messages) > 0:
            try:
                log_success(
                    logger,
                    "Processing conversation for CRM auto-population",
                    conversation_id=conversation_id,
                )

                crm_result = await auto_crm.process_conversation(
                    conversation_id=conversation_id,
                    messages=request.messages,
                    user_email=user_email,
                    team_member=(
                        request.metadata.get("team_member", "system")
                        if request.metadata
                        else "system"
                    ),
                    db_pool=db_pool,  # Pass centralized pool
                )

                if crm_result.get("success"):
                    log_success(
                        logger,
                        "Auto-CRM processed successfully",
                        client_id=crm_result.get("client_id"),
                        practice_id=crm_result.get("practice_id"),
                    )
                else:
                    log_warning(logger, f"Auto-CRM failed: {crm_result.get('error')}")

            except Exception as crm_error:
                log_error(logger, "Auto-CRM processing error", error=crm_error, exc_info=True)
                crm_result = {"processed": False, "error": str(crm_error)}
        else:
            crm_result = {"processed": False, "reason": "auto-crm not available"}

    return {
        "success": True,  # Always return true to keep chat alive
        "conversation_id": conversation_id,
        "messages_saved": len(request.messages),
        "user_email": user_email,
        "crm": crm_result,
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
    source = "db"

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
                    messages = row.get("messages", [])
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
                source = "memory"
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
):
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

            return {"success": True, "deleted_count": deleted_count_int}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/stats")
async def get_conversation_stats(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
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
):
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

                # Extract title from first user message
                title = "New Conversation"
                preview = ""
                for msg in messages:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        title = content[:50] + "..." if len(content) > 50 else content
                        break

                # Extract preview from last assistant message
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
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
                    )
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
):
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
):
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

            return {"success": True, "deleted_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/memory/context", response_model=UserMemoryContextResponse)
async def get_user_memory_context(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
):
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
