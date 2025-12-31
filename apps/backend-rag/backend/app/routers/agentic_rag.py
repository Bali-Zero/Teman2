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

from app.dependencies import get_current_user, get_database_pool
from app.utils.tracing import trace_span, set_span_attribute, set_span_status, add_span_event
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


class ImageInput(BaseModel):
    """Image attachment from frontend"""

    base64: str  # Base64 encoded image data (with data:image/... prefix)
    name: str  # Original filename


class AgenticQueryRequest(BaseModel):
    query: str
    user_id: str | None = "anonymous"
    enable_vision: bool | None = False
    images: list[ImageInput] | None = None  # Attached images for vision
    session_id: str | None = None
    conversation_id: int | None = None
    conversation_history: list[
        ConversationMessageInput
    ] | None = None  # Direct history from frontend


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
    current_user: dict = Depends(get_current_user),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
):
    """
    Esegue una query usando il sistema Agentic RAG completo.

    **AUTHENTICATION REQUIRED**: This endpoint requires a valid JWT token.
    The user_id is extracted from the authenticated user, not from the request body.
    """
    # SECURITY FIX: Use authenticated user's email/id instead of trusting request body
    authenticated_user_id = current_user.get("email") or current_user.get("user_id")

    # DIAGNOSTIC: Log current_user structure and authenticated_user_id
    logger.warning(
        f"🔍 [USER_ID_DEBUG] current_user keys: {list(current_user.keys())}, "
        f"email={current_user.get('email')}, id={current_user.get('id')}, "
        f"authenticated_user_id={authenticated_user_id}"
    )

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
        elif authenticated_user_id and (request.conversation_id or request.session_id):
            logger.info(
                f"🔍 Retrieving conversation history from DB: conversation_id={request.conversation_id}, session_id={request.session_id}, user_id={authenticated_user_id}"
            )
            conversation_history = await get_conversation_history_for_agentic(
                conversation_id=request.conversation_id,
                session_id=request.session_id,
                user_id=authenticated_user_id,
                db_pool=db_pool,
            )
            logger.info(f"💬 Retrieved {len(conversation_history)} messages from database")

        query_kwargs = {
            "query": request.query,
            "user_id": authenticated_user_id,  # SECURITY: Use authenticated user_id
            "session_id": request.session_id,
        }
        if conversation_history:
            query_kwargs["conversation_history"] = conversation_history

        result = await orchestrator.process_query(**query_kwargs)

        # CoreResult is a Pydantic model, access via attributes
        return AgenticQueryResponse(
            answer=result.answer,
            sources=result.sources,
            context_length=result.document_count,  # context_used -> document_count
            execution_time=result.timings.get("total", 0.0),
            route_used=result.route_used,
            tools_called=len(result.tools_called),
            total_steps=len(result.tools_called),
            debug_info={"model": result.model_used, "cache_hit": result.cache_hit},
        )
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.error(f"❌ Error in query_agentic_rag: {str(e)}\n{tb}")
        # Temporarily include traceback in response for debugging
        # Generic error message for production
        raise HTTPException(status_code=500, detail="Internal Server Error: The request could not be processed.") from e


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
    current_user: dict = Depends(get_current_user),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
):
    """
    Stream the Agentic RAG process (SSE).

    **AUTHENTICATION REQUIRED**: This endpoint requires a valid JWT token.
    The user_id is extracted from the authenticated user, not from the request body.

    Supports conversation history via:
    1. Direct conversation_history from frontend (preferred - works even if DB is down)
    2. conversation_id or session_id lookup from database (fallback)
    """
    # SECURITY FIX: Use authenticated user's email/id instead of trusting request body
    # This prevents user_id spoofing and unauthorized access to other users' data
    authenticated_user_id = current_user.get("email") or current_user.get("user_id")

    logger.info(
        f"🔐 Authenticated user: {authenticated_user_id} "
        f"(role: {current_user.get('role', 'user')})"
    )
    # Get correlation ID from request state (set by RequestTracingMiddleware)
    correlation_id = (
        getattr(http_request.state, "correlation_id", None)
        or getattr(http_request.state, "request_id", None)
        or http_request.headers.get("X-Correlation-ID", "unknown")
    )

    # Safe query hash for logging (first 50 chars + hash)
    query_preview = request_body.query[:50] if request_body.query else ""
    query_hash = hashlib.sha256(
        request_body.query.encode() if request_body.query else b""
    ).hexdigest()[:8]

    # Log request start
    start_time = time.time()
    logger.info(
        f"📥 SSE stream request started: correlation_id={correlation_id}, "
        f"query_preview='{query_preview}...', query_hash={query_hash}, "
        f"query_length={len(request_body.query) if request_body.query else 0}, "
        f"user_id={authenticated_user_id[:8] + '...' if authenticated_user_id and len(authenticated_user_id) > 8 else authenticated_user_id}, "
        f"session_id={request_body.session_id}"
    )

    # TRACING: Record span for streaming request (completes before response streams)
    # This ensures traces are sent even for long-running SSE connections
    with trace_span("agentic_rag.stream", {
        "user_id": authenticated_user_id or "anonymous",
        "query_length": len(request_body.query) if request_body.query else 0,
        "query_hash": query_hash,
        "session_id": request_body.session_id or "none",
        "correlation_id": correlation_id,
        "has_conversation_history": bool(request_body.conversation_history),
        "endpoint": "/api/agentic-rag/stream",
    }):
        add_span_event("stream_request_received", {
            "query_preview": query_preview[:30] if query_preview else "",
        })

        # Validate query is not empty
        if not request_body.query or not request_body.query.strip():
            logger.warning(f"⚠️ Empty query received - rejecting (correlation_id={correlation_id})")
            set_span_status("error", "Empty query")
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        set_span_status("ok", "Stream initiated")

    async def event_generator():
        events_yielded = 0
        tokens_sent = 0
        events_by_type: dict[str, int] = {}
        final_answer_received = False
        error_count = 0
        max_errors = 5
        
        try:
            # Yield initial status
            initial_status = {
                'type': 'status',
                'data': {
                    'status': 'processing',
                    'correlation_id': correlation_id,
                }
            }
            yield f"data: {json.dumps(initial_status)}\n\n"
            events_yielded += 1
            
            # Priority 1: Use conversation_history from frontend if provided
            conversation_history: list[dict] = []

            if request_body.conversation_history and len(request_body.conversation_history) > 0:
                # Frontend sent conversation history directly - use it (DB-independent!)
                conversation_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request_body.conversation_history
                ]
                logger.info(
                    f"💬 Using {len(conversation_history)} messages from frontend conversation_history (DB-independent) "
                    f"(correlation_id={correlation_id})"
                )

            # Priority 2: Try to retrieve from database if no frontend history
            elif authenticated_user_id and (request_body.conversation_id or request_body.session_id):
                logger.info(
                    f"🔍 Retrieving conversation history from DB: conversation_id={request_body.conversation_id}, "
                    f"session_id={request_body.session_id}, user_id={authenticated_user_id} "
                    f"(correlation_id={correlation_id})"
                )
                try:
                    conversation_history = await get_conversation_history_for_agentic(
                        conversation_id=request_body.conversation_id,
                        session_id=request_body.session_id,
                        user_id=authenticated_user_id,
                        db_pool=db_pool,
                    )
                    logger.info(
                        f"💬 Retrieved {len(conversation_history)} messages from database "
                        f"(correlation_id={correlation_id})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to load history: {e}")
                    # Yield error but continue
                    error_event = {
                        'type': 'error',
                        'data': {
                            'error_type': 'history_load_failed',
                            'message': 'Could not load conversation history',
                            'non_fatal': True,
                            'correlation_id': correlation_id,
                        }
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    events_yielded += 1

            # Check for client disconnect before starting stream
            if await http_request.is_disconnected():
                logger.warning(
                    f"⚠️ Client disconnected before stream start (correlation_id={correlation_id})"
                )
                return

            # Stream query with disconnect detection
            # SECURITY: Use authenticated_user_id from JWT, not from request body
            # Prepare images for vision if provided
            images_for_vision = None
            if request_body.images and request_body.enable_vision:
                images_for_vision = [
                    {"base64": img.base64, "name": img.name}
                    for img in request_body.images
                ]
                logger.info(f"🖼️ Vision enabled with {len(images_for_vision)} images (correlation_id={correlation_id})")

            async for event in orchestrator.stream_query(
                query=request_body.query,
                user_id=authenticated_user_id,
                conversation_history=conversation_history if conversation_history else None,
                session_id=request_body.session_id,
                images=images_for_vision,
            ):
                try:
                    # Validate event
                    if event is None:
                        error_count += 1
                        if error_count >= max_errors:
                            error_event = {
                                'type': 'error',
                                'data': {
                                    'error_type': 'too_many_errors',
                                    'message': 'Stream aborted due to too many errors',
                                    'fatal': True,
                                    'correlation_id': correlation_id,
                                }
                            }
                            yield f"data: {json.dumps(error_event)}\n\n"
                            break
                        continue

                    if not isinstance(event, dict):
                        error_count += 1
                        if error_count >= max_errors:
                            error_event = {
                                'type': 'error',
                                'data': {
                                    'error_type': 'too_many_errors',
                                    'message': 'Stream aborted due to too many errors',
                                    'fatal': True,
                                    'correlation_id': correlation_id,
                                }
                            }
                            yield f"data: {json.dumps(error_event)}\n\n"
                            break
                        continue
                    
                    # Serialize and yield
                    event_json = json.dumps(event)
                    yield f"data: {event_json}\n\n"
                    events_yielded += 1
                    
                    # Reset error count on success
                    error_count = 0
                    
                    # Check for client disconnect
                    if await http_request.is_disconnected():
                        logger.info(f"Client disconnected: {correlation_id}")
                        break
                    
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
                    if event_type == "done" or (
                        event_type == "status" and event.get("data") == "[DONE]"
                    ):
                        final_answer_received = True
                        
                except json.JSONEncodeError as e:
                    error_count += 1
                    logger.error(f"JSON serialization failed: {e}")
                    error_event = {
                        'type': 'error',
                        'data': {
                            'error_type': 'serialization_error',
                            'message': 'Failed to serialize event',
                            'non_fatal': True,
                            'correlation_id': correlation_id,
                        }
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    events_yielded += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.exception(f"Error processing stream event: {e}")
                    error_event = {
                        'type': 'error',
                        'data': {
                            'error_type': 'processing_error',
                            'message': str(e),
                            'non_fatal': error_count < max_errors,
                            'correlation_id': correlation_id,
                        }
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    events_yielded += 1
                    
                    if error_count >= max_errors:
                        break
            
            # Yield final status
            final_status = {
                'type': 'status',
                'data': {
                    'status': 'completed',
                    'correlation_id': correlation_id,
                }
            }
            yield f"data: {json.dumps(final_status)}\n\n"
            events_yielded += 1

        except Exception as e:
            logger.exception(f"Fatal error in stream: {e}")
            fatal_error_event = {
                'type': 'error',
                'data': {
                    'error_type': 'fatal_error',
                    'message': f'Stream failed: {str(e)}',
                    'fatal': True,
                    'correlation_id': correlation_id,
                }
            }
            yield f"data: {json.dumps(fatal_error_event)}\n\n"
            events_yielded += 1
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
            "X-Correlation-ID": correlation_id,
        },
    )
