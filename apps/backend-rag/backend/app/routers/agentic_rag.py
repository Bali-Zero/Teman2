"""
Agentic RAG API Router
"""

import hashlib
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.dependencies import get_database_pool
from services.rag.agentic import AgenticRAGOrchestrator, create_agentic_rag

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/agentic-rag",
    tags=["agentic-rag"],
    responses={404: {"description": "Not found"}},
)

# Global orchestrator instance (lazy loaded)
_orchestrator: AgenticRAGOrchestrator | None = None


async def get_orchestrator(request: Request):
    global _orchestrator
    if _orchestrator is None:
        db_pool = getattr(request.app.state, "db_pool", None)
        search_service = getattr(request.app.state, "search_service", None)
        _orchestrator = create_agentic_rag(retriever=search_service, db_pool=db_pool)
    return _orchestrator


def get_optional_database_pool(request: Request) -> Any | None:
    try:
        return get_database_pool(request)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise


class ConversationMessageInput(BaseModel):
    """Single message in conversation history from frontend"""

    role: str
    content: str


class AgenticQueryRequest(BaseModel):
    query: str
    user_id: str | None = "anonymous"
    enable_vision: bool | None = False
    session_id: str | None = None
    conversation_id: int | None = None
    conversation_history: list[ConversationMessageInput] | None = (
        None  # Direct history from frontend
    )


class AgenticQueryResponse(BaseModel):
    answer: str
    sources: list[Any]
    context_length: int
    execution_time: float
    route_used: str | None
    tools_called: int = 0
    total_steps: int = 0
    debug_info: dict | None = None


@router.post("/query", response_model=AgenticQueryResponse)
async def query_agentic_rag(
    request: AgenticQueryRequest,
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
):
    """
    Esegue una query usando il sistema Agentic RAG completo.
    """
    try:
        # Priority 1: Use conversation_history from frontend if provided
        conversation_history: list[dict] = []

        if request.conversation_history and len(request.conversation_history) > 0:
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in request.conversation_history
            ]
            logger.info(
                f"💬 Using {len(conversation_history)} messages from frontend conversation_history (DB-independent)"
            )

        # Priority 2: Try to retrieve from database if no frontend history
        elif request.user_id and (request.conversation_id or request.session_id):
            logger.info(
                f"🔍 Retrieving conversation history from DB: conversation_id={request.conversation_id}, session_id={request.session_id}, user_id={request.user_id}"
            )
            conversation_history = await get_conversation_history_for_agentic(
                conversation_id=request.conversation_id,
                session_id=request.session_id,
                user_id=request.user_id,
                db_pool=db_pool,
            )
            logger.info(f"💬 Retrieved {len(conversation_history)} messages from database")

        query_kwargs = {
            "query": request.query,
            "user_id": request.user_id,
            "session_id": request.session_id,
        }
        if conversation_history:
            query_kwargs["conversation_history"] = conversation_history

        result = await orchestrator.process_query(**query_kwargs)

        return AgenticQueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            context_length=result["context_used"],
            execution_time=result["execution_time"],
            route_used=result["route_used"],
            tools_called=result.get("tools_called", 0),
            total_steps=result.get("total_steps", 0),
            debug_info=result.get("debug_info"),
        )
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.error(f"❌ Error in query_agentic_rag: {str(e)}\n{tb}")
        # Temporarily include traceback in response for debugging
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nTRACEBACK:\n{tb}") from e


async def get_conversation_history_for_agentic(
    conversation_id: int | None,
    session_id: str | None,
    user_id: str | None,
    db_pool: Any | None = None,
) -> list[dict]:
    """
    Retrieve conversation history for agentic RAG context awareness

    Args:
        conversation_id: Optional conversation ID
        session_id: Optional session ID
        user_id: User ID (can be email or ID) - will be used to find user email
        db_pool: Database connection pool

    Returns:
        List of conversation messages (role, content)
    """
    if not db_pool or not user_id:
        logger.debug(
            f"⚠️ Cannot retrieve conversation history: db_pool={db_pool is not None}, user_id={user_id}"
        )
        return []

    try:
        async with db_pool.acquire() as conn:
            # Convert user_id to email if needed
            user_email = str(user_id)

            # If user_id doesn't look like an email, try to get email from team_members
            if "@" not in user_email:
                logger.debug(
                    f"🔍 user_id '{user_id}' doesn't look like email, trying to find email..."
                )
                email_row = await conn.fetchrow(
                    """
                    SELECT email FROM user_profiles
                    WHERE id::text = $1 OR email = $1
                    LIMIT 1
                    """,
                    user_email,
                )
                if email_row and email_row.get("email"):
                    user_email = email_row["email"]
                    logger.info(f"✅ Found email for user_id '{user_id}': {user_email}")
                else:
                    logger.warning(f"⚠️ Could not find email for user_id '{user_id}', using as-is")

            # Try conversation_id first, then session_id, then most recent
            if conversation_id:
                row = await conn.fetchrow(
                    """
                    SELECT messages
                    FROM conversations
                    WHERE id = $1 AND user_id = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    conversation_id,
                    user_email,
                )
            elif session_id:
                row = await conn.fetchrow(
                    """
                    SELECT messages
                    FROM conversations
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    session_id,
                )
            else:
                # Get most recent conversation
                row = await conn.fetchrow(
                    """
                    SELECT messages
                    FROM conversations
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    user_email,
                )

            if row and row.get("messages"):
                messages = row["messages"]
                if isinstance(messages, str):
                    messages = json.loads(messages)
                logger.info(f"📚 Retrieved {len(messages)} messages from conversation history")
                return messages
            else:
                logger.debug("📚 No conversation history found")
                return []

    except Exception as e:
        logger.warning(f"⚠️ Failed to retrieve conversation history: {e}")
        return []


@router.post("/stream")
async def stream_agentic_rag(
    request_body: AgenticQueryRequest,
    http_request: Request,
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
):
    """
    Stream the Agentic RAG process (SSE).
    Supports conversation history via:
    1. Direct conversation_history from frontend (preferred - works even if DB is down)
    2. conversation_id or session_id lookup from database (fallback)
    """
    # Get correlation ID from request state (set by RequestTracingMiddleware)
    correlation_id = getattr(http_request.state, "correlation_id", None) or getattr(
        http_request.state, "request_id", None
    ) or http_request.headers.get("X-Correlation-ID", "unknown")
    
    # Safe query hash for logging (first 50 chars + hash)
    query_preview = request_body.query[:50] if request_body.query else ""
    query_hash = hashlib.sha256(request_body.query.encode() if request_body.query else b"").hexdigest()[:8]
    
    # Log request start
    start_time = time.time()
    logger.info(
        f"📥 SSE stream request started: correlation_id={correlation_id}, "
        f"query_preview='{query_preview}...', query_hash={query_hash}, "
        f"query_length={len(request_body.query) if request_body.query else 0}, "
        f"user_id={request_body.user_id[:8] + '...' if request_body.user_id and len(request_body.user_id) > 8 else request_body.user_id}, "
        f"session_id={request_body.session_id}"
    )
    
    # Validate query is not empty
    if not request_body.query or not request_body.query.strip():
        logger.warning(f"⚠️ Empty query received - rejecting (correlation_id={correlation_id})")
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    async def event_generator():
        events_yielded = 0
        tokens_sent = 0
        events_by_type: dict[str, int] = {}
        final_answer_received = False
        try:
            # Priority 1: Use conversation_history from frontend if provided
            conversation_history: list[dict] = []

            if request_body.conversation_history and len(request_body.conversation_history) > 0:
                # Frontend sent conversation history directly - use it (DB-independent!)
                conversation_history = [
                    {"role": msg.role, "content": msg.content} for msg in request_body.conversation_history
                ]
                logger.info(
                    f"💬 Using {len(conversation_history)} messages from frontend conversation_history (DB-independent) "
                    f"(correlation_id={correlation_id})"
                )

            # Priority 2: Try to retrieve from database if no frontend history
            elif request_body.user_id and (request_body.conversation_id or request_body.session_id):
                logger.info(
                    f"🔍 Retrieving conversation history from DB: conversation_id={request_body.conversation_id}, "
                    f"session_id={request_body.session_id}, user_id={request_body.user_id} "
                    f"(correlation_id={correlation_id})"
                )
                conversation_history = await get_conversation_history_for_agentic(
                    conversation_id=request_body.conversation_id,
                    session_id=request_body.session_id,
                    user_id=request_body.user_id,
                    db_pool=db_pool,
                )
                logger.info(
                    f"💬 Retrieved {len(conversation_history)} messages from database "
                    f"(correlation_id={correlation_id})"
                )

            # Check for client disconnect before starting stream
            if await http_request.is_disconnected():
                logger.warning(
                    f"⚠️ Client disconnected before stream start (correlation_id={correlation_id})"
                )
                return

            # Emit initial status event (heartbeat)
            initial_status = {"type": "status", "data": "Processing your request..."}
            yield f"data: {json.dumps(initial_status)}\n\n"
            events_yielded += 1

            # Stream query with disconnect detection
            async for event in orchestrator.stream_query(
                query=request_body.query,
                user_id=request_body.user_id,
                conversation_history=conversation_history if conversation_history else None,
                session_id=request_body.session_id,
            ):
                # Fix: Handle None or non-dict events
                if event is None:
                    continue  # Skip None events
                
                if not isinstance(event, dict):
                    continue  # Skip non-dict events
                
                # Check for client disconnect periodically
                if events_yielded % 10 == 0:  # Check every 10 events
                    if await http_request.is_disconnected():
                        logger.warning(
                            f"⚠️ Client disconnected during stream (correlation_id={correlation_id}, "
                            f"events_yielded={events_yielded}, tokens_sent={tokens_sent})"
                        )
                        return
                
                # Track event type and tokens
                event_type = event.get("type", "unknown")
                events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
                
                # Count tokens from token events
                if event_type == "token":
                    token_content = event.get("data", "")
                    # Fix: Handle None explicitly (event.get("data") can return None)
                    if token_content is None:
                        token_content = ""
                    if isinstance(token_content, str):
                        # Approximate token count (rough estimate: 1 token ≈ 4 chars)
                        tokens_sent += max(1, len(token_content) // 4)
                    else:
                        tokens_sent += 1
                
                # Check if final answer was received
                if event_type == "done" or (event_type == "status" and event.get("data") == "[DONE]"):
                    final_answer_received = True
                
                # Format as SSE
                yield f"data: {json.dumps(event)}\n\n"
                events_yielded += 1
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_data = {"type": "error", "message": str(e)}
            if "429" in str(e) or "ResourceExhausted" in str(e):
                error_data["code"] = "QUOTA_EXCEEDED"
                error_data["message"] = "Usage limit reached. Please try again later."
            elif "503" in str(e) or "ServiceUnavailable" in str(e):
                error_data["code"] = "SERVICE_UNAVAILABLE"
                error_data["message"] = "Service temporarily unavailable. Please try again."

            logger.error(
                f"❌ SSE stream error: correlation_id={correlation_id}, "
                f"error={type(e).__name__}: {str(e)[:100]}, "
                f"duration_ms={duration_ms:.1f}, events_yielded={events_yielded}, "
                f"tokens_sent={tokens_sent}, final_answer_received={final_answer_received}, "
                f"events_by_type={events_by_type}"
            )
            yield f"data: {json.dumps({'type': 'error', 'data': error_data})}\n\n"
        finally:
            # Log final statistics regardless of success or error
            end_time = time.time()
            duration = end_time - start_time
            
            # Log completion statistics
            logger.info(
                f"✅ SSE stream completed: correlation_id={correlation_id}, "
                f"duration={duration:.2f}s, events_yielded={events_yielded}, "
                f"tokens_sent={tokens_sent}, final_answer_received={final_answer_received}, "
                f"events_by_type={events_by_type}"
            )
            
            # Warning if stream was interrupted prematurely
            if not final_answer_received and events_yielded > 0:
                logger.warning(
                    f"⚠️ SSE stream interrupted: correlation_id={correlation_id}, "
                    f"events_yielded={events_yielded}, tokens_sent={tokens_sent}, "
                    f"duration={duration:.2f}s, events_by_type={events_by_type}"
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
