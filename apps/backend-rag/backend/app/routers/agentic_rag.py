"""
Agentic RAG API Router

Integrates A/B testing for retrieval strategy comparison.
Experiments:
- hybrid_vs_dense: Hybrid search vs dense-only
- reranking_on_off: Cross-encoder reranking enabled/disabled
- query_expansion: Query expansion enabled/disabled
"""

import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.dependencies import (
    get_current_user,
    get_current_user_optional,
    get_optional_database_pool,
    get_orchestrator,
)
from backend.app.utils.tracing import add_span_event, set_span_status, trace_span
from backend.db.repositories.conversation_repository import ConversationRepository
from backend.services.rag.agentic import AgenticRAGOrchestrator
from backend.services.rag.evaluation import ABTestManager, MetricsTracker

logger = logging.getLogger(__name__)

# Global A/B testing components (lazy initialization)
_ab_test_manager: ABTestManager | None = None
_metrics_tracker: MetricsTracker | None = None


def get_ab_test_manager() -> ABTestManager:
    """Get or create global ABTestManager instance."""
    global _ab_test_manager
    if _ab_test_manager is None:
        _metrics_tracker_instance = get_metrics_tracker()
        _ab_test_manager = ABTestManager(metrics_tracker=_metrics_tracker_instance)
    return _ab_test_manager


def get_metrics_tracker() -> MetricsTracker:
    """Get or create global MetricsTracker instance."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = MetricsTracker()
    return _metrics_tracker


def clean_image_generation_response(text: str) -> str:
    """
    Post-process AI response to remove ugly URLs from image generation.
    Uses line-by-line filtering for robustness.

    This is the SINGLE SOURCE OF TRUTH for image response cleaning.
    Removes pollinations URLs, markdown images, version numbers, and other artifacts
    from AI-generated image responses.

    Features:
    - Removes pollinations.ai URLs and subdomains
    - Filters markdown image syntax
    - Removes version numbers and intro/outro lines
    - Handles URL-encoded content
    - Provides fallback message if too much content is removed

    Note: Processes text only if it contains "pollinations" OR has image-related patterns
    to avoid unnecessary processing of normal text.
    """
    if not text:
        return text

    # Early exit: if no pollinations and no image-related patterns, return unchanged
    text_lower = text.lower()
    has_pollinations = "pollinations" in text_lower
    has_image_patterns = (
        "![[" in text
        or "](" in text
        or "[visualizza" in text_lower
        or re.search(r"versione\s*\d", text_lower)
        or re.search(r"^\s*\d+\.\s*\*{0,2}(versione|prima|seconda|opzione)", text_lower)
    )

    if not has_pollinations and not has_image_patterns:
        return text

    # Process line by line for better control
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line_lower = line.lower()
        should_skip = False

        # Skip lines with pollinations URLs (any subdomain)
        if (
            "pollinations" in line_lower
            or "image" in line_lower
            and "http" in line_lower
            or re.search(r"!\[.*?\]\(.*?\)", line, re.IGNORECASE)
            or "![" in line
            or "](" in line
            and "http" in line
            or line.strip().startswith("[Visualizza")
            or re.search(
                r"^\s*\d+\.\s*\*{0,2}(Versione|Prima|Seconda|Opzione)", line, re.IGNORECASE,
            )
            or re.search(
                r"^\s*[\*\-]\s*\*{0,2}(Versione|Prima|Seconda|Opzione)", line, re.IGNORECASE,
            )
            or re.search(r"^\s*\*{0,2}Versione\s*\d", line, re.IGNORECASE)
            or re.search(
                r"ecco le (opzioni|immagini)|ho (elaborato|generato|creato) (due|le)|ti propongo|due varianti|ecco i risultati|queste versioni",
                line_lower,
            )
            or re.search(
                r"spero che queste|se hai bisogno di|vadano bene per|sembra che queste",
                line_lower,
            )
            or line.strip().startswith("(http")
            or re.search(r"^https?://", line.strip(), re.IGNORECASE)
            or re.search(r"%20.*%20.*%20", line)
            or re.search(r"alta risoluzione|atmosfera tradizionale|luce dorata", line_lower)
        ):
            should_skip = True

        if not should_skip:
            cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Clean up multiple newlines and spaces
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"  +", " ", text)
    text = text.strip()

    # If almost everything was removed, provide a default response
    # Using threshold of 30 (aligned with frontend) for consistency
    if len(text) < 30:
        text = "Ecco l'immagine che hai richiesto! 🎨"

    return text


router = APIRouter(
    prefix="/api/agentic-rag",
    tags=["agentic-rag"],
    responses={404: {"description": "Not found"}},
)


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
    conversation_history: list[ConversationMessageInput] | None = (
        None  # Direct history from frontend
    )
    channel: str | None = None  # Channel overlay: "website", "webapp", "whatsapp", etc.


class AgenticQueryResponse(BaseModel):
    answer: str
    sources: list[Any]
    context_length: int
    execution_time: float
    route_used: str | None
    tools_called: int = 0
    total_steps: int = 0
    debug_info: dict | None = None
    ab_test: dict | None = None  # A/B test variant info
    # ABSTAIN handling
    abstain: bool = False  # True when system refused to answer
    abstain_reason: str | None = None  # Reason for abstaining
    evidence_score: float = 0.0  # Evidence confidence score
    # KG LangGraph outputs (Phase 3)
    workflow: dict | None = None  # Synthesized workflow from KG LangGraph
    reasoning: str | None = None  # Reasoning chain from KG exploration
    detected_entities: list[dict] | None = None  # Entities detected from query


@router.post("/query", response_model=AgenticQueryResponse)
async def query_agentic_rag(
    request: AgenticQueryRequest,
    current_user: dict | None = Depends(get_current_user_optional),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
) -> AgenticQueryResponse:
    """
    Esegue una query usando il sistema Agentic RAG completo.

    **AUTHENTICATION OPTIONAL**: Supports both logged-in and anonymous users.
    For anonymous users, uses session_id for tracking.

    **A/B TESTING**: Automatically assigns users to retrieval strategy variants
    and records performance metrics for comparison.
    """
    # SECURITY: Use authenticated user if available, otherwise session-based
    if current_user:
        authenticated_user_id = current_user.get("email") or current_user.get("user_id")
    else:
        authenticated_user_id = (
            f"anonymous_{request.session_id[:12] if request.session_id else 'guest'}"
        )

    # DIAGNOSTIC: Log identity info
    logger.info(
        f"🔍 Sync query: user={authenticated_user_id} (authenticated: {current_user is not None})",
    )

    # A/B TESTING: Assign variants and get configurations
    ab_manager = get_ab_test_manager()
    query_id = str(uuid.uuid4())

    # Assign variants for each experiment
    ab_variants = {
        "hybrid_vs_dense": ab_manager.assign_variant(authenticated_user_id, "hybrid_vs_dense"),
        "reranking_on_off": ab_manager.assign_variant(authenticated_user_id, "reranking_on_off"),
        "query_expansion": ab_manager.assign_variant(authenticated_user_id, "query_expansion"),
    }

    # Get variant configurations
    hybrid_config = ab_manager.get_variant_config("hybrid_vs_dense", ab_variants["hybrid_vs_dense"])
    rerank_config = ab_manager.get_variant_config(
        "reranking_on_off", ab_variants["reranking_on_off"],
    )
    expansion_config = ab_manager.get_variant_config(
        "query_expansion", ab_variants["query_expansion"],
    )

    logger.info(
        f"🧪 A/B Test variants for {authenticated_user_id}: "
        f"hybrid={ab_variants['hybrid_vs_dense']}, "
        f"rerank={ab_variants['reranking_on_off']}, "
        f"expansion={ab_variants['query_expansion']}",
    )

    try:
        query_start_time = time.time()

        # Priority 1: Use conversation_history from frontend if provided
        conversation_history: list[dict] = []

        if request.conversation_history and len(request.conversation_history) > 0:
            conversation_history = [
                {"role": msg.role, "content": msg.content} for msg in request.conversation_history
            ]
            logger.info(
                f"💬 Using {len(conversation_history)} messages from frontend conversation_history (DB-independent)",
            )

        # Priority 2: Try to retrieve from database if no frontend history
        elif authenticated_user_id and (request.conversation_id or request.session_id):
            logger.info(
                f"🔍 Retrieving conversation history from DB: conversation_id={request.conversation_id}, session_id={request.session_id}, user_id={authenticated_user_id}",
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

        # Calculate response time
        response_time = time.time() - query_start_time

        # A/B TESTING: Record metrics
        metrics_to_record = {
            "response_time": response_time,
            "evidence_score": result.confidence_score
            if hasattr(result, "confidence_score")
            else 0.0,
        }

        # Record metrics for each experiment
        await ab_manager.metrics_tracker.record_query_metrics(
            query_id=query_id,
            user_id=authenticated_user_id,
            experiment="hybrid_vs_dense",
            variant=ab_variants["hybrid_vs_dense"],
            metrics=metrics_to_record,
            metadata={
                "query": request.query[:100],
                "route_used": result.route_used,
                "document_count": result.document_count,
            },
        )

        # CoreResult is a Pydantic model, access via attributes
        # Prepare detected entities for response
        detected_entities_list = []
        if result.entities:
            for entity_type, entities in result.entities.items():
                if isinstance(entities, list):
                    for entity in entities:
                        detected_entities_list.append({"type": entity_type, "value": entity})

        return AgenticQueryResponse(
            answer=result.answer,
            sources=result.sources,
            context_length=result.document_count,  # context_used -> document_count
            execution_time=result.timings.get("total", 0.0),
            route_used=result.route_used,
            tools_called=len(result.tools_called),
            total_steps=len(result.tools_called),
            debug_info={
                "model": result.model_used,
                "cache_hit": result.cache_hit,
                "ab_config": {
                    "hybrid": hybrid_config,
                    "rerank": rerank_config,
                    "expansion": expansion_config,
                },
            },
            ab_test={
                "query_id": query_id,
                "variants": ab_variants,
            },
            # ABSTAIN fields
            abstain=result.abstain,
            abstain_reason=result.abstain_reason,
            evidence_score=result.evidence_score,
            # KG LangGraph outputs (Phase 3)
            workflow=result.workflow,
            reasoning=result.reasoning,
            detected_entities=detected_entities_list if detected_entities_list else None,
        )
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        logger.error(f"❌ Error in query_agentic_rag: {str(e)}\n{tb}")
        # Temporarily include traceback in response for debugging
        # Generic error message for production
        raise HTTPException(
            status_code=500, detail="Internal Server Error: The request could not be processed.",
        ) from e


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
            f"⚠️ Cannot retrieve conversation history: db_pool={db_pool is not None}, user_id={user_id}",
        )
        return []

    try:
        async with db_pool.acquire() as conn:
            # Convert user_id to email if needed
            user_email = str(user_id)

            # If user_id doesn't look like an email, try to get email from team_members
            if "@" not in user_email:
                logger.debug(
                    f"🔍 user_id '{user_id}' doesn't look like email, trying to find email...",
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
            logger.debug("📚 No conversation history found")
            return []

    except Exception as e:
        logger.warning(f"⚠️ Failed to retrieve conversation history: {e}")
        return []


@router.post("/stream")
async def stream_agentic_rag(
    request_body: AgenticQueryRequest,
    http_request: Request,
    current_user: dict | None = Depends(get_current_user_optional),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_optional_database_pool),
) -> Any:
    """
    Stream the Agentic RAG process (SSE).

    **AUTHENTICATION OPTIONAL**: Supports both logged-in and anonymous users.
    For anonymous users, uses session_id for tracking.

    Supports conversation history via:
    1. Direct conversation_history from frontend (preferred - works even if DB is down)
    2. conversation_id or session_id lookup from database (fallback)
    """
    # SECURITY: Use authenticated user if available, otherwise fallback to session-based identity
    if current_user:
        authenticated_user_id = current_user.get("email") or current_user.get("user_id")
    else:
        # For anonymous users, we use a session-based virtual ID
        # This allows context awareness within the same session
        authenticated_user_id = (
            f"anonymous_{request_body.session_id[:12] if request_body.session_id else 'guest'}"
        )

    logger.info(
        f"📡 Chat Stream: user={authenticated_user_id} (authenticated: {current_user is not None})",
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
        request_body.query.encode() if request_body.query else b"",
    ).hexdigest()[:8]

    # Log request start
    start_time = time.time()
    logger.info(
        f"📥 SSE stream request started: correlation_id={correlation_id}, "
        f"query_preview='{query_preview}...', query_hash={query_hash}, "
        f"query_length={len(request_body.query) if request_body.query else 0}, "
        f"user_id={authenticated_user_id[:8] + '...' if authenticated_user_id and len(authenticated_user_id) > 8 else authenticated_user_id}, "
        f"session_id={request_body.session_id}",
    )

    # TRACING: Record span for streaming request (completes before response streams)
    # This ensures traces are sent even for long-running SSE connections
    with trace_span(
        "agentic_rag.stream",
        {
            "user_id": authenticated_user_id or "anonymous",
            "query_length": len(request_body.query) if request_body.query else 0,
            "query_hash": query_hash,
            "session_id": request_body.session_id or "none",
            "correlation_id": correlation_id,
            "has_conversation_history": bool(request_body.conversation_history),
            "endpoint": "/api/agentic-rag/stream",
        },
    ):
        add_span_event(
            "stream_request_received",
            {
                "query_preview": query_preview[:30] if query_preview else "",
            },
        )

        # Validate query is not empty
        if not request_body.query or not request_body.query.strip():
            logger.warning(f"⚠️ Empty query received - rejecting (correlation_id={correlation_id})")
            set_span_status("error", "Empty query")
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        set_span_status("ok", "Stream initiated")

    async def event_generator() -> Any:
        events_yielded = 0
        tokens_sent = 0
        events_by_type: dict[str, int] = {}
        final_answer_received = False
        error_count = 0
        max_errors = 5

        full_answer = ""
        conversation_id: int | None = None
        persisted = False

        try:
            # Yield initial status
            initial_status = {
                "type": "status",
                "data": {
                    "status": "processing",
                    "correlation_id": correlation_id,
                },
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
                    f"(correlation_id={correlation_id})",
                )

            # Priority 2: Try to retrieve from database if no frontend history
            elif authenticated_user_id and (
                request_body.conversation_id or request_body.session_id
            ):
                logger.info(
                    f"🔍 Retrieving conversation history from DB: conversation_id={request_body.conversation_id}, "
                    f"session_id={request_body.session_id}, user_id={authenticated_user_id} "
                    f"(correlation_id={correlation_id})",
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
                        f"(correlation_id={correlation_id})",
                    )
                except Exception as e:
                    logger.warning(f"Failed to load history: {e}")
                    # Yield error but continue
                    error_event = {
                        "type": "error",
                        "data": {
                            "error_type": "history_load_failed",
                            "message": "Could not load conversation history",
                            "non_fatal": True,
                            "correlation_id": correlation_id,
                        },
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    events_yielded += 1

            # Check for client disconnect before starting stream
            if await http_request.is_disconnected():
                logger.warning(
                    f"⚠️ Client disconnected before stream start (correlation_id={correlation_id})",
                )
                return

            # Stream query with disconnect detection
            # SECURITY: Use authenticated_user_id from JWT, not from request body
            # Prepare images for vision if provided
            images_for_vision = None
            if request_body.images and request_body.enable_vision:
                images_for_vision = [
                    {"base64": img.base64, "name": img.name} for img in request_body.images
                ]
                logger.info(
                    f"🖼️ Vision enabled with {len(images_for_vision)} images (correlation_id={correlation_id})",
                )

            async for event in orchestrator.stream_query(
                query=request_body.query,
                user_id=authenticated_user_id,
                conversation_history=conversation_history if conversation_history else None,
                session_id=request_body.session_id,
                images=images_for_vision,
                channel=request_body.channel,
            ):
                try:
                    # Validate event
                    if event is None:
                        error_count += 1
                        if error_count >= max_errors:
                            error_event = {
                                "type": "error",
                                "data": {
                                    "error_type": "too_many_errors",
                                    "message": "Stream aborted due to too many errors",
                                    "fatal": True,
                                    "correlation_id": correlation_id,
                                },
                            }
                            yield f"data: {json.dumps(error_event)}\n\n"
                            break
                        continue

                    if not isinstance(event, dict):
                        error_count += 1
                        if error_count >= max_errors:
                            error_event = {
                                "type": "error",
                                "data": {
                                    "error_type": "too_many_errors",
                                    "message": "Stream aborted due to too many errors",
                                    "fatal": True,
                                    "correlation_id": correlation_id,
                                },
                            }
                            yield f"data: {json.dumps(error_event)}\n\n"
                            break
                        continue

                    # Post-process token events to clean image generation URLs
                    if event.get("type") == "token" and isinstance(event.get("data"), str):
                        event["data"] = clean_image_generation_response(event["data"])

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

                    # Count tokens from token events and collect full answer
                    if event_type == "token":
                        token_content = event.get("data", "")
                        # Fix: Handle None explicitly (event.get("data") can return None)
                        if token_content is None:
                            token_content = ""
                        if isinstance(token_content, str):
                            full_answer += token_content
                            # Approximate token count (rough estimate: 1 token ≈ 4 chars)
                            tokens_sent += max(1, len(token_content) // 4)
                        else:
                            tokens_sent += 1

                    # Collect sources (logged for diagnostics)
                    elif event_type == "sources":
                        pass

                    # Check if final answer was received
                    if event_type == "done" or (
                        event_type == "status" and event.get("data") == "[DONE]"
                    ):
                        final_answer_received = True

                except json.JSONEncodeError as e:
                    error_count += 1
                    logger.error(f"JSON serialization failed: {e}")
                    error_event = {
                        "type": "error",
                        "data": {
                            "error_type": "serialization_error",
                            "message": "Failed to serialize event",
                            "non_fatal": True,
                            "correlation_id": correlation_id,
                        },
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    events_yielded += 1

                except Exception as e:
                    error_count += 1
                    logger.exception(f"Error processing stream event: {e}")
                    error_event = {
                        "type": "error",
                        "data": {
                            "error_type": "processing_error",
                            "message": str(e),
                            "non_fatal": error_count < max_errors,
                            "correlation_id": correlation_id,
                        },
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    events_yielded += 1

                    if error_count >= max_errors:
                        break

            # Yield final status
            final_status = {
                "type": "status",
                "data": {
                    "status": "completed",
                    "correlation_id": correlation_id,
                },
            }
            yield f"data: {json.dumps(final_status)}\n\n"
            events_yielded += 1

        except Exception as e:
            logger.exception(f"Fatal error in stream: {e}")
            fatal_error_event = {
                "type": "error",
                "data": {
                    "error_type": "fatal_error",
                    "message": f"Stream failed: {str(e)}",
                    "fatal": True,
                    "correlation_id": correlation_id,
                },
            }
            yield f"data: {json.dumps(fatal_error_event)}\n\n"
            events_yielded += 1
        finally:
            # Log final statistics regardless of success or error
            end_time = time.time()
            duration = end_time - start_time

            # Persist conversation to database if we have a complete answer
            if db_pool and full_answer and request_body.session_id:
                try:
                    repo = ConversationRepository(db_pool)
                    new_messages = [
                        {
                            "role": "user",
                            "content": request_body.query,
                            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                        },
                        {
                            "role": "assistant",
                            "content": full_answer,
                            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                        },
                    ]
                    conversation_metadata = {
                        "source": "agentic_rag_stream",
                        "correlation_id": correlation_id,
                        "execution_time": duration,
                        "tokens_sent": tokens_sent,
                        "events_by_type": events_by_type,
                        "streamed": True,
                    }
                    conversation_id = await repo.save_messages(
                        session_id=request_body.session_id,
                        user_id=authenticated_user_id,
                        messages=new_messages,
                        metadata=conversation_metadata,
                    )
                    persisted = conversation_id is not None
                    if persisted:
                        logger.info(
                            f"💾 Conversation persisted: conversation_id={conversation_id}, "
                            f"session_id={request_body.session_id}",
                        )
                except Exception as persist_error:
                    logger.warning(f"⚠️ Failed to persist conversation: {persist_error}")
                    persisted = False

            # Yield final metadata with persistence info
            if request_body.session_id:
                persistence_event = {
                    "type": "metadata",
                    "data": {
                        "conversation_id": conversation_id,
                        "persisted": persisted,
                        "execution_time": duration,
                        "session_id": request_body.session_id,
                    },
                }
                yield f"data: {json.dumps(persistence_event)}\n\n"
                events_yielded += 1

            # Log completion statistics
            logger.info(
                f"✅ SSE stream completed: correlation_id={correlation_id}, "
                f"duration={duration:.2f}s, events_yielded={events_yielded}, "
                f"tokens_sent={tokens_sent}, final_answer_received={final_answer_received}, "
                f"events_by_type={events_by_type}, persisted={persisted}",
            )

            # Warning if stream was interrupted prematurely
            if not final_answer_received and events_yielded > 0:
                logger.warning(
                    f"⚠️ SSE stream interrupted: correlation_id={correlation_id}, "
                    f"events_yielded={events_yielded}, tokens_sent={tokens_sent}, "
                    f"duration={duration:.2f}s, events_by_type={events_by_type}",
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


class ProactiveTriggerRequest(BaseModel):
    """Request to trigger proactive AI behavior based on system events"""

    event_type: str  # e.g. "USER_LOGIN", "PAGE_VISIT", "IDLE"
    user_id: str | None = None  # Optional override, defaults to Auth User
    context_data: dict[str, Any] | None = None


@router.post("/proactive-trigger")
async def trigger_proactivity(
    request_body: ProactiveTriggerRequest,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    """
    Trigger a proactive AI event (Zero-Shot Proactivity).
    The AI will analyze the user's context/memory and decide whether to speak.
    """
    # Security: Use Auth User unless Admin (simplified: just use Auth User for now)
    authenticated_user_id = current_user.get("email") or current_user.get("user_id")
    target_user_id = authenticated_user_id

    # Allow override only if needed (future: RBAC)
    if request_body.user_id and request_body.user_id != authenticated_user_id:
        # Check permissions? For now, strictly verify it matches or is system call.
        # Let's enforce authenticated user for safety unless it's a specific system token (not impl yet).
        logger.warning(
            f"⚠️ Proactive trigger mismatch: Auth={authenticated_user_id}, Req={request_body.user_id}. Forcing Auth ID.",
        )
        target_user_id = authenticated_user_id

    correlation_id = getattr(
        http_request.state, "correlation_id", None,
    ) or http_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    logger.info(f"⚡ [Proactive] Trigger received: {request_body.event_type} for {target_user_id}")

    async def event_generator() -> None:
        # Yield initial status
        yield f"data: {json.dumps({'type': 'status', 'data': {'status': 'analyzing_context', 'correlation_id': correlation_id}})}\n\n"

        try:
            async for event in orchestrator.stream_proactive_event(
                user_id=target_user_id,
                event_type=request_body.event_type,
                context_data=request_body.context_data or {},
            ):
                event_json = json.dumps(event)
                yield f"data: {event_json}\n\n"
        except Exception as e:
            logger.error(f"❌ [Proactive] Stream Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'data': None})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Correlation-ID": correlation_id,
        },
    )


# =============================================================================
# A/B TESTING ENDPOINTS
# =============================================================================


class ABTestFeedbackRequest(BaseModel):
    """Request to record user feedback for A/B testing."""

    query_id: str
    experiment: str
    variant: str
    feedback_type: str  # "thumbs_up", "thumbs_down", "click", "dismiss"
    metadata: dict[str, Any] | None = None


@router.post("/ab-test/feedback")
async def record_ab_test_feedback(
    request: ABTestFeedbackRequest,
    current_user: dict | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    """
    Record user feedback for A/B testing metrics.

    This endpoint allows the frontend to report user interactions
    (thumbs up/down, clicks) for measuring experiment success.
    """
    user_id = (
        current_user.get("email") or current_user.get("user_id") if current_user else "anonymous"
    )

    ab_manager = get_ab_test_manager()

    # Map feedback type to metric value
    metric_values = {
        "thumbs_up": 1.0,
        "thumbs_down": 0.0,
        "click": 1.0,
        "dismiss": 0.0,
    }

    metric_name = "satisfaction" if request.feedback_type in ["thumbs_up", "thumbs_down"] else "ctr"
    value = metric_values.get(request.feedback_type, 0.0)

    await ab_manager.record_metric(
        experiment=request.experiment,
        variant=request.variant,
        metric=metric_name,
        value=value,
        user_id=user_id,
        query_id=request.query_id,
        metadata=request.metadata,
    )

    return {
        "status": "recorded",
        "query_id": request.query_id,
        "experiment": request.experiment,
        "variant": request.variant,
        "metric": metric_name,
        "value": value,
    }


@router.get("/ab-test/results/{experiment}")
async def get_ab_test_results(
    experiment: str,
    _current_user: dict = Depends(get_current_user),
) -> Any:
    """
    Get A/B test results for a specific experiment.

    Requires authentication. Returns aggregated metrics and
    statistical significance analysis.
    """
    ab_manager = get_ab_test_manager()

    results = await ab_manager.get_experiment_results(experiment)

    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])

    return results


@router.get("/ab-test/dashboard")
async def get_ab_test_dashboard(
    _current_user: dict = Depends(get_current_user),
) -> Any:
    """
    Get A/B testing dashboard data.

    Returns overview of all experiments with current status,
    sample sizes, and significance results.
    """
    ab_manager = get_ab_test_manager()

    return await ab_manager.get_dashboard_data()



@router.get("/ab-test/experiments")
async def list_ab_test_experiments(
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    List all available A/B test experiments.

    Returns experiment configurations without detailed results.
    """
    ab_manager = get_ab_test_manager()

    return {
        "experiments": ab_manager.list_experiments(),
    }


class ABTestControlRequest(BaseModel):
    """Request to enable/disable an experiment."""

    enabled: bool


@router.post("/ab-test/experiments/{experiment}/control")
async def control_ab_test_experiment(
    experiment: str,
    request: ABTestControlRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Enable or disable an A/B test experiment.

    Requires team member access. Allows starting/stopping experiments.
    """
    # Check if user is team member (not client)
    if current_user.get("role") == "client":
        raise HTTPException(
            status_code=403,
            detail="Only team members can control experiments",
        )

    ab_manager = get_ab_test_manager()

    if request.enabled:
        success = ab_manager.enable_experiment(experiment)
    else:
        success = ab_manager.disable_experiment(experiment)

    if not success:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment}' not found")

    return {
        "experiment": experiment,
        "enabled": request.enabled,
        "status": "updated",
    }


@router.get("/ab-test/user/{user_id}/exposure")
async def get_user_exposure(
    user_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get experiment exposure history for a specific user.

    Useful for debugging and support.
    """
    # Only allow team members to check other users' exposure
    if current_user.get("role") == "client" and user_id != current_user.get("email"):
        raise HTTPException(
            status_code=403,
            detail="Can only view your own exposure history",
        )

    tracker = get_metrics_tracker()
    exposure = await tracker.get_user_exposure(user_id)

    return {
        "user_id": user_id,
        "exposure": exposure,
    }
