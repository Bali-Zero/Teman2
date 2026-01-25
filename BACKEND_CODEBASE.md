# 🐍 NUZANTARA BACKEND CODEBASE (Snapshot)

**Generated:** 2026-01-23 (Snapshot)
**Update (Jan 25 2026):** Database Architecture Refactored to V2. See `docs/DATABASE_ARCHITECTURE_V2.md`.
**Focus:** Core Intelligence & Architecture

## 1. Entrypoint (`apps/backend-rag/backend/app/main_cloud.py`)

```python
"""
FastAPI entrypoint for the ZANTARA RAG backend.

This module serves as the minimal entry point for uvicorn.
All application setup is delegated to app.setup.app_factory.create_app().

Run via: uvicorn app.main_cloud:app --host 0.0.0.0 --port 8080

BACKWARD COMPATIBILITY:
- Exports app, initialize_services, initialize_plugins, on_startup, on_shutdown
- Exports utility functions: _parse_history, _allowed_origins, _safe_endpoint_label
- All exports maintain backward compatibility with existing tests and code
"""

import json
import logging
from typing import Any
from urllib.parse import urlparse

from backend.app.setup.app_factory import create_app
from backend.app.setup.cors_config import get_allowed_origins
from backend.app.setup.plugin_initializer import initialize_plugins
from backend.app.setup.sentry_config import init_sentry
from backend.app.setup.service_initializer import initialize_services
from backend.services.monitoring.alert_service import AlertService

logger = logging.getLogger("zantara.backend")

# Initialize Sentry before creating app (must be first)
init_sentry()

# Create FastAPI application instance
app = create_app()

# Backward compatibility: Export functions for tests and other modules
# These are used by tests and some agent code that imports directly from main_cloud

# Re-export initialization functions
__all__ = [
    "app",
    "initialize_services",
    "initialize_plugins",
    "on_startup",
    "on_shutdown",
    "_parse_history",
    "_allowed_origins",
    "_safe_endpoint_label",
]


# Backward compatibility: Export startup/shutdown handlers
# These functions can be called directly by tests and maintain the same interface
async def on_startup() -> None:
    """
    Startup handler - backward compatibility export.

    This function replicates the original startup behavior for tests.
    It initializes AlertService and calls initialize_services/initialize_plugins.
    """
    # Initialize AlertService at startup (avoid import-time instantiation)
    app.state.alert_service = AlertService()
    await initialize_services(app)
    await initialize_plugins(app)


async def on_shutdown() -> None:
    """
    Shutdown handler - backward compatibility export.

    This function replicates the original shutdown behavior for tests.
    Note: Actual shutdown handlers are registered via register_shutdown_handlers()
    in app_factory.py, but this function exists for backward compatibility.
    """
    logger.info("🛑 Shutting down ZANTARA services...")

    import asyncio
    import inspect
    from contextlib import suppress

    from backend.services.misc.proactive_compliance_monitor import ProactiveComplianceMonitor
    from backend.services.monitoring.health_monitor import HealthMonitor

    # Shutdown WebSocket Redis Listener
    redis_task = getattr(app.state, "redis_listener_task", None)
    if redis_task:
        cancel = getattr(redis_task, "cancel", None)
        if callable(cancel):
            cancel()

        if inspect.isawaitable(redis_task):
            with suppress(asyncio.CancelledError):
                await redis_task
        logger.info("✅ WebSocket Redis Listener stopped")

    # Shutdown Health Monitor
    health_monitor: HealthMonitor | None = getattr(app.state, "health_monitor", None)
    if health_monitor:
        await health_monitor.stop()
        logger.info("✅ Health Monitor stopped")

    # Shutdown Compliance Monitor
    compliance_monitor: ProactiveComplianceMonitor | None = getattr(
        app.state, "compliance_monitor", None
    )
    if compliance_monitor:
        await compliance_monitor.stop()
        logger.info("✅ Compliance Monitor stopped")

    # Shutdown Autonomous Scheduler (all agents)
    autonomous_scheduler = getattr(app.state, "autonomous_scheduler", None)
    if autonomous_scheduler:
        await autonomous_scheduler.stop()
        logger.info("✅ Autonomous Scheduler stopped (all agents terminated)")

    logger.info("✅ HTTP clients closed")
    logger.info("✅ ZANTARA shutdown complete")


# Backward compatibility: Export utility functions
def _parse_history(history_raw: str | None) -> list[dict[str, Any]]:
    """
    Parse conversation history from raw string.

    Args:
        history_raw: JSON string containing conversation history

    Returns:
        List of conversation dictionaries, empty list if invalid/empty
    """
    if not history_raw:
        return []
    try:
        parsed = json.loads(history_raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        import logging

        logger = logging.getLogger("zantara.backend")
        logger.warning("Invalid conversation_history payload received")
    return []


def _allowed_origins() -> list[str]:
    """Get allowed CORS origins - backward compatibility wrapper."""
    return get_allowed_origins()


def _safe_endpoint_label(url: str | None) -> str:
    """Return a minimal identifier for logging without leaking credentials."""
    if not url:
        return "unknown"
    parsed = urlparse(url)
    return parsed.netloc or parsed.path or "unknown"
```

## 2. Agentic RAG Router (`apps/backend-rag/backend/app/routers/agentic_rag.py`)

```python
"""
Agentic RAG API Router
"""

import hashlib
import json
import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.dependencies import (
    get_current_user,
    get_optional_database_pool,
    get_orchestrator,
)
from backend.app.utils.tracing import add_span_event, set_span_status, trace_span
from backend.services.rag.agentic import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)


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
            or re.search(r"!\\[.*?\\]\(.*?\".*?\")", line, re.IGNORECASE)
            or "![[" in line
            or "](" in line
            and "http" in line
            or line.strip().startswith("[Visualizza")
            or re.search(
                r"^\s*\d+\.\s*\*{0,2}(Versione|Prima|Seconda|Opzione)", line, re.IGNORECASE
            )
            or re.search(
                r"^\s*[\*\-]\s*\*{0,2}(Versione|Prima|Seconda|Opzione)", line, re.IGNORECASE
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
        text = "Ecco l\'immagine che hai richiesto! 🎨"

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
        raise HTTPException(
            status_code=500, detail="Internal Server Error: The request could not be processed."
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
        f"🔐 Authenticated user: {authenticated_user_id} (role: {current_user.get('role', 'user')})"
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
                    f"(correlation_id={correlation_id})"
                )

            # Priority 2: Try to retrieve from database if no frontend history
            elif authenticated_user_id and (
                request_body.conversation_id or request_body.session_id
            ):
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
                    f"⚠️ Client disconnected before stream start (correlation_id={correlation_id})"
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
                    f"🖼️ Vision enabled with {len(images_for_vision)} images (correlation_id={correlation_id})"
                )

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
):
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
            f"⚠️ Proactive trigger mismatch: Auth={authenticated_user_id}, Req={request_body.user_id}. Forcing Auth ID."
        )
        target_user_id = authenticated_user_id

    correlation_id = getattr(
        http_request.state, "correlation_id", None
    ) or http_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    logger.info(f"⚡ [Proactive] Trigger received: {request_body.event_type} for {target_user_id}")

    async def event_generator():
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
```

## 3. Orchestrator Core (`apps/backend-rag/backend/services/rag/agentic/orchestrator.py`)

```python
"""
Agentic RAG Orchestrator - Main Query Processing Logic

This is the core orchestrator that coordinates all agentic RAG operations:
- Query routing (Fast/Pro/DeepThink)
- Tool-based reasoning (ReAct pattern)
- Streaming and non-streaming query processing
- Model fallback cascade (Gemini Pro -> Flash -> Flash-Lite -> OpenRouter)
- Memory persistence
- Semantic caching
- Response verification

Architecture:
- Uses modular components for context, prompts, tools, and processing
- Implements quality routing based on intent classification
- Supports conversation history with context window management
- Provides backward compatibility with legacy interfaces
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.metrics import metrics_collector
from backend.app.utils.tracing import (
    add_span_event,
    trace_span,
)
from backend.services.classification.intent_classifier import IntentClassifier
from backend.services.misc.clarification_service import ClarificationService
from backend.services.misc.context_window_manager import ContextWindowManager
from backend.services.misc.emotional_attunement import EmotionalAttunementService
from backend.services.misc.followup_service import FollowupService
from backend.services.misc.golden_answer_service import GoldenAnswerService
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval
from backend.services.response.cleaner import OUT_OF_DOMAIN_RESPONSES, is_out_of_domain
from backend.services.search.semantic_cache import SemanticCache
from backend.services.tools.definitions import BaseTool

from .llm_gateway import LLMGateway
from .memory_handler import MemoryHandler
from .pipeline import create_default_pipeline
from .prompt_builder import SystemPromptBuilder
from .query_gates import QueryGates
from .query_helpers import (
    TIER_FLASH,
    is_conversation_recall_query,
    wrap_query_with_language_instruction,
)
from .reasoning import ReasoningEngine, detect_team_query
from .schema import CoreResult
from .tool_executor import execute_tool

logger = logging.getLogger(__name__)


class StreamEvent(BaseModel):
    """Schema per eventi stream."""

    type: str
    data: Any
    timestamp: float | None = None
    correlation_id: str | None = None

    class Config:
        arbitrary_types_allowed = True


# Alias for backward compatibility (used internally)
_wrap_query_with_language_instruction = wrap_query_with_language_instruction
_is_conversation_recall_query = is_conversation_recall_query


class AgenticRAGOrchestrator:
    """
    Orchestrator for Agentic RAG with Tool Use.
    Implements ReAct: Thought → Action → Observation → Repeat

    Supports:
    - Quality Routing: Fast (Flash) vs Pro (Pro) vs DeepThink (Reasoning)
    - Automatic fallback: Flash -> Flash-Lite -> OpenRouter
    - Memory persistence and context management
    - Streaming and non-streaming modes
    """

    def __init__(
        self,
        tools: list[BaseTool],
        db_pool: Any = None,
        model_name: str = "gemini-3-flash-preview",  # Zantara AI
        semantic_cache: SemanticCache = None,
        retriever: Any = None,
        clarification_service: ClarificationService = None,
        entity_extractor: EntityExtractionService = None,
        llm_gateway: LLMGateway = None,
    ):
        """Initialize the AgenticRAGOrchestrator.

        Sets up model clients, dependencies, and configuration for multi-tier
        agentic reasoning with automatic fallback handling.

        Args:
            tools: List of tool definitions available for agent reasoning
            db_pool: Optional asyncpg connection pool for database operations
            model_name: Base model name (legacy, not actively used)
            semantic_cache: Optional semantic cache instance for query deduplication
            retriever: SearchService or KnowledgeService instance for embeddings
            clarification_service: Optional service for resolving ambiguous queries
            entity_extractor: Optional EntityExtractionService instance
            llm_gateway: Optional LLMGateway instance
        Note:
            - Initializes Gemini models (Pro, Flash, Flash-Lite) for cascade fallback
            - Lazy loads OpenRouter client and MemoryOrchestrator on first use
            - Configures intent classifier and emotional attunement services
            - Converts tools to Gemini function declarations for native calling
        """
        logger.debug(f"AgenticRAGOrchestrator.__init__ started. Model: {model_name}")
        self.tools = {tool.name: tool for tool in tools}  # Changed to dict for direct access
        self.db_pool = db_pool
        self.model_name = model_name
        self.semantic_cache = semantic_cache
        self.retriever = retriever
        self.clarification_service = clarification_service
        self.llm_gateway = llm_gateway or LLMGateway()  # Initialize LLMGateway here

        # Convert tools to Gemini function declarations for native calling
        self.gemini_tools = [tool.to_gemini_function_declaration() for tool in tools]
        logger.debug(f"Converted {len(self.gemini_tools)} tools to Gemini function declarations")

        # Initialize IntentClassifier
        logger.debug("AgenticRAGOrchestrator: Initializing IntentClassifier...")
        self.intent_classifier = IntentClassifier()
        logger.debug("AgenticRAGOrchestrator: IntentClassifier initialized")

        # Initialize Emotional Attunement
        logger.debug("AgenticRAGOrchestrator: Initializing EmotionalAttunementService...")
        self.emotional_service = EmotionalAttunementService()
        logger.debug("AgenticRAGOrchestrator: EmotionalAttunementService initialized")

        # Initialize Prompt Builder
        self.prompt_builder = SystemPromptBuilder()

        # Initialize Response Processing Pipeline
        logger.debug("AgenticRAGOrchestrator: Initializing ResponsePipeline...")
        self.response_pipeline = create_default_pipeline()
        logger.debug("AgenticRAGOrchestrator: ResponsePipeline initialized")

        # Initialize LLM Gateway (manages all model interactions and fallbacks)
        logger.debug("AgenticRAGOrchestrator: Initializing LLMGateway...")
        # self.llm_gateway = LLMGateway(gemini_tools=self.gemini_tools) # Moved above
        self.llm_gateway.set_gemini_tools(
            self.gemini_tools
        )  # Set tools after LLMGateway is initialized
        logger.debug("AgenticRAGOrchestrator: LLMGateway initialized")

        # BRIDGE: Inject LLM Gateway into tools that need semantic intelligence
        # This enables Knowledge Graph Builder to use LLM-based extraction instead of regex-only
        if "knowledge_graph_search" in self.tools:
            kg_tool = self.tools["knowledge_graph_search"]
            if hasattr(kg_tool, "kg_builder") and kg_tool.kg_builder:
                kg_tool.kg_builder.llm_gateway = self.llm_gateway
                logger.info("✅ LLM Gateway injected into KnowledgeGraphBuilder")

        # Initialize Reasoning Engine (manages ReAct loop)
        logger.debug("AgenticRAGOrchestrator: Initializing ReasoningEngine...")
        self.reasoning_engine = ReasoningEngine(
            tool_map=self.tools,
            response_pipeline=self.response_pipeline,
        )
        logger.debug("AgenticRAGOrchestrator: ReasoningEngine initialized")

        # Initialize Entity Extraction Service
        logger.debug("AgenticRAGOrchestrator: Initializing EntityExtractionService...")
        self.entity_extractor = entity_extractor or EntityExtractionService(
            llm_gateway=self.llm_gateway
        )
        logger.debug("AgenticRAGOrchestrator: EntityExtractionService initialized")

        # Initialize KG-Enhanced Retrieval Service
        self.kg_retrieval = KGEnhancedRetrieval(db_pool) if db_pool else None
        if self.kg_retrieval:
            logger.info("✅ KG-Enhanced Retrieval initialized")

        # Initialize Follow-up & Golden Answer services
        self.followup_service = FollowupService()
        self.golden_answer_service = GoldenAnswerService(database_url=settings.database_url)

        # Memory Handler - manages memory persistence with race condition protection
        self.memory_handler = MemoryHandler(db_pool=db_pool)

        # Query Gates - pre-processing gates that can bypass RAG pipeline
        self.query_gates = QueryGates(
            prompt_builder=self.prompt_builder,
            clarification_service=clarification_service,
        )

        # Stream event validation configuration
        self._event_validation_enabled = True
        self._max_event_errors = 10  # Max errori prima di abortire stream

        # Context Window Manager for conversation history summarization
        # Summarizes older messages to preserve key facts while managing token budget
        self.context_window_manager = ContextWindowManager(
            max_messages=20,  # Keep last 20 messages in full
            summary_threshold=30,  # Start summarizing when >30 messages
        )
        logger.debug("AgenticRAGOrchestrator: ContextWindowManager initialized")

        logger.debug("AgenticRAGOrchestrator.__init__ completed")

        # Initialize OrchestratorCore (delegates main logic)
        from .orchestrator_core import OrchestratorCore
        from .orchestrator_streaming import OrchestratorStreamingManager
        from .orchestrator_streaming_core import OrchestratorStreamingCore

        self.core = OrchestratorCore(
            llm_gateway=self.llm_gateway,
            reasoning_engine=self.reasoning_engine,
            prompt_builder=self.prompt_builder,
            query_gates=self.query_gates,
            memory_handler=self.memory_handler,
            context_window_manager=self.context_window_manager,
            entity_extractor=self.entity_extractor,
            kg_retrieval=self.kg_retrieval,
            semantic_cache=self.semantic_cache,
            db_pool=db_pool,
        )

        # Initialize streaming components
        streaming_manager = OrchestratorStreamingManager(
            max_event_errors=self._max_event_errors,
            event_validation_enabled=self._event_validation_enabled,
        )
        self.streaming_core = OrchestratorStreamingCore(
            core=self.core,
            streaming_manager=streaming_manager,
        )
        logger.info(
            "✅ OrchestratorCore and OrchestratorStreamingCore initialized (Refactored Architecture)"
        )

    async def process_query(
        self,
        query: str,
        user_id: str | None = None,
        conversation_history: list[dict] | None = None,
        start_time: float | None = None,
        session_id: str | None = None,
    ) -> CoreResult:
        """
        Process query with full RAG pipeline - Delegates to OrchestratorCore.

        Args:
            query: Query string
            user_id: Optional user ID
            conversation_history: Optional conversation history
            start_time: Optional start time (defaults to now)
            session_id: Optional session ID

        Returns:
            CoreResult with answer, sources, and metadata
        """
        start_time = start_time or time.time()

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 🔍 TRACING: Parent span for entire query processing
        with trace_span(
            "orchestrator.process_query",
            {
                "user_id": user_id or "anonymous",
                "query_length": len(query),
                "session_id": session_id or "none",
                "has_history": bool(conversation_history),
            },
        ):
            # Delegate to OrchestratorCore
            logger.debug("Delegating process_query to OrchestratorCore")
            return await self.core.process_query_core(
                query=query,
                user_id=user_id,
                conversation_history=conversation_history,
                start_time=start_time,
                session_id=session_id,
                tool_execution_counter=tool_execution_counter,
            )

    def _create_error_event(
        self,
        error_type: str,
        message: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Create standardized error event."""
        return {
            "type": "error",
            "data": {
                "error_type": error_type,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": time.time(),
            },
            "timestamp": time.time(),
        }

    async def stream_query(
        self,
        query: str,
        user_id: str = "anonymous",
        conversation_history: list[dict] | None = None,
        session_id: str | None = None,
        images: list[dict] | None = None,  # Vision images: [{"base64": ..., "name": ...}]
    ) -> AsyncGenerator[dict, None]:
        """Stream query with comprehensive error handling. Supports vision with images."""
        correlation_id = str(uuid.uuid4())

        # Security: Validate user_id format
        if user_id and user_id != "anonymous":
            if not isinstance(user_id, str) or len(user_id) < 1:
                raise ValueError("Invalid user_id format")

        # Initialize tool execution counter for rate limiting
        tool_execution_counter = {"count": 0}

        # 🔍 TRACING: Add span event for stream query start
        add_span_event(
            "stream_query.start",
            {
                "user_id": user_id,
                "query_length": len(query),
                "session_id": session_id or "none",
                "images_count": len(images) if images else 0,
            },
        )

        # Log vision mode if images are attached
        if images:
            logger.info(f"🖼️ Vision mode: {len(images)} images attached to query")

        # -1. SECURITY GATE: Prompt Injection Detection (MUST BE FIRST! NO CONTEXT NEEDED)
        is_injection, injection_response = self.prompt_builder.detect_prompt_injection(query)
        if is_injection:
            logger.warning("🛡️ [Security Stream] Blocked prompt injection/off-topic request")
            yield {"type": "metadata", "data": {"status": "blocked", "route": "security-gate"}}
            for token in injection_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # 0. FAST CONTEXT LOADING (Basic Profile + History ONLY)
        # Avoids heavy Memory/Entity extraction unless needed
        user_context, history_to_use = await self.core.context_manager.get_basic_context(
            user_id=user_id, session_id=session_id
        )

        # If conversation_history passed explicitly, prefer it or merge?
        # get_basic_context logic usually respects conversation_history if passed to prepare_conversation_history.
        # But here we called it without passing history.
        # Ideally, we should respect the explicit history if provided.
        if conversation_history:
            # Overwrite history_to_use if explicit history provided
            history_to_use = conversation_history

        logger.info(
            f"🧠 [Stream Context] Loaded BASIC context for {user_id or 'anonymous'} (History: {len(history_to_use)} msgs)"
        )

        # Check Greetings first (skip RAG for simple greetings)
        # INJECT CONTEXT
        greeting_response = self.prompt_builder.check_greetings(query, context=user_context)
        if greeting_response:
            logger.info("👋 [Greeting Stream] Returning direct greeting response (skipping RAG)")
            yield {"type": "metadata", "data": {"status": "greeting", "route": "greeting-pattern"}}
            for token in greeting_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # 0.05 Check Casual Conversation (skip RAG for "come stai", "how are you", etc.)
        casual_response = self.prompt_builder.get_casual_response(query, context=user_context)
        if casual_response:
            logger.info("💬 [Casual Stream] Returning direct casual response (skipping RAG)")
            yield {"type": "metadata", "data": {"status": "casual", "route": "casual-pattern"}}
            for token in casual_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.02)  # Slightly slower for natural feel
            yield {"type": "done", "data": None}
            return

        # 0.5 Check Identity / Hardcoded Patterns
        identity_response = self.prompt_builder.check_identity_questions(
            query, context=user_context
        )
        if identity_response:
            logger.info("🤖 [Identity Stream] Returning hardcoded identity response")
            yield {"type": "metadata", "data": {"status": "identity", "route": "identity-pattern"}}
            for token in identity_response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # 0.1 CLARIFICATION GATE (Ambiguity Detection - Stream)
        if self.clarification_service:
            ambiguity_info = self.clarification_service.detect_ambiguity(
                query, conversation_history or history_to_use
            )
            if (
                ambiguity_info["is_ambiguous"]
                and ambiguity_info["confidence"] > 0.6
                and ambiguity_info["clarification_needed"]
            ):
                logger.info(
                    f"🛑 [Clarification Gate Stream] Stopped ambiguous query: {ambiguity_info['reasons']}"
                )
                clarification_msg = self.clarification_service.generate_clarification_request(
                    query, ambiguity_info
                )

                yield {
                    "type": "metadata",
                    "data": {
                        "status": "clarification_needed",
                        "confidence": ambiguity_info["confidence"],
                        "reasons": ambiguity_info["reasons"],
                    },
                }

                # Stream the clarification question
                tokens = clarification_msg.split()
                for token in tokens:
                    yield {"type": "token", "data": token + " "}
                    await asyncio.sleep(0.01)

                yield {"type": "done", "data": None}
                return

        # EARLY TEAM QUERY CHECK - handle team questions immediately
        is_team_query, team_query_type, team_search_term = detect_team_query(query)
        if is_team_query and "team_knowledge" in self.tools:  # Changed self.tool_map to self.tools
            logger.info(
                f"🎯 [Early Team Route] Forcing team_knowledge for: {team_query_type}={team_search_term}"
            )
            yield {"type": "metadata", "data": {"status": "team-query", "route": "team-knowledge"}}
            yield {"type": "status", "data": "Fetching team data..."}
            try:
                team_result_str, _ = await execute_tool(
                    self.tools,  # Changed self.tool_map to self.tools
                    "team_knowledge",
                    {"query_type": team_query_type, "search_term": team_search_term},
                    user_id,
                    tool_execution_counter,
                )
                if team_result_str:
                    logger.info(f"Team Knowledge Result Length: {len(team_result_str)}")

                if team_result_str and len(team_result_str) > 20:
                    # Build simple prompt with team context
                    # Language handling: model will match user's language automatically
                    team_prompt = f"""You are ZANTARA. Answer this question using the team data below.
Be direct and factual. IMPORTANT: Respond in the SAME language the user is writing in.

TEAM DATA:
{team_result_str}

USER QUESTION: {query}

Answer directly. Example: "Zainal Abidin è il CEO di {settings.COMPANY_NAME}."
"""
                    team_chat = self.llm_gateway.create_chat_with_history(
                        history_to_use=history_to_use,
                        model_tier=TIER_FLASH
                    )
                    team_response, model_used, _ = await self.llm_gateway.send_message(
                        team_chat,
                        team_prompt,
                        system_prompt="",
                        tier=TIER_FLASH,
                        enable_function_calling=False,
                    )
                    import re

                    tokens = re.findall(r"\S+|\s+", team_response)
                    for token in tokens:
                        yield {"type": "token", "data": token}
                        await asyncio.sleep(0.01)
                    yield {"type": "done", "data": None}
                    return
            except Exception as e:
                logger.warning(f"⚠️ [Early Team Route] Failed: {e}, falling back to RAG")

        # 🧠 CONVERSATION RECALL GATE - bypass RAG for recall questions
        # This fixes the "lost in the middle" problem where LLM searches Qdrant
        # for information that's actually in the conversation history
        if _is_conversation_recall_query(query) and len(history_to_use) > 0:
            logger.info("🧠 [Recall Gate] Detected conversation recall query - bypassing RAG")
            yield {
                "type": "metadata",
                "data": {"status": "recall", "route": "conversation-history"},
            }
            yield {"type": "status", "data": "Ricordando la conversazione..."}

            # Format conversation history for the prompt
            history_text = "\n".join(
                [
                    f"{('USER' if msg.get('role') == 'user' else 'ASSISTANT')}: {msg.get('content', '')}"
                    for msg in history_to_use[-20:]  # Last 20 messages
                ]
            )

            recall_prompt = f"""You are ZANTARA. The user is asking you to recall something from THIS conversation.

CRITICAL: The answer is in the CONVERSATION HISTORY below. Do NOT say you don't have information - read the history!

CONVERSATION HISTORY:
{history_text}

USER QUESTION: {query}

Answer directly using information from the conversation above. Be specific with names, details, and facts the user mentioned.
Respond in the SAME language the user is using."""

            try:
                recall_chat = self.llm_gateway.create_chat_with_history(
                    history_to_use=[],  # Empty history - we put it in prompt
                )
                recall_response, model_used, _, _ = await self.llm_gateway.send_message(
                    recall_chat,
                    recall_prompt,
                    system_prompt="",
                    tier=TIER_FLASH,
                    enable_function_calling=False,
                )
                import re

                tokens = re.findall(r"\S+|\s+", recall_response)
                for token in tokens:
                    yield {"type": "token", "data": token}
                    await asyncio.sleep(0.01)
                yield {"type": "done", "data": {"route": "recall-gate"}}
                return
            except Exception as e:
                logger.warning(f"⚠️ [Recall Gate] Failed: {e}, falling back to RAG")

        # NOTE: Casual conversation detection removed (Dec 2025)
        # The ReAct loop + system prompt now handles this via QUERY CLASSIFICATION - STEP 0
        # The LLM decides when to use tools vs respond directly based on query type

        # Check Out-of-Domain Questions
        out_of_domain, reason = is_out_of_domain(query)
        if out_of_domain and reason:
            logger.info(f"🚫 [Out-of-Domain Stream] Query rejected: {reason}")
            response = OUT_OF_DOMAIN_RESPONSES.get(reason, OUT_OF_DOMAIN_RESPONSES["unknown"])
            yield {"type": "metadata", "data": {"status": "out-of-domain", "reason": reason}}
            for token in response.split():
                yield {"type": "token", "data": token + " "}
                await asyncio.sleep(0.01)
            yield {"type": "done", "data": None}
            return

        # After all early gates, delegate to OrchestratorStreamingCore
        logger.debug(f"Entering stream_query core. Query: {query}")

        full_answer = ""

        # 🎯 PROACTIVITY: Start Speculative Follow-up Generation (Background Task)
        # We start this BEFORE the heavy RAG processing so it runs in parallel with the stream.
        # Using response=None tells the service to predict based on Query + Context,
        # effectively masking the 2-3s generation latency.
        followup_task = asyncio.create_task(
            self.followup_service.get_followups(
                query=query,
                response=None,  # SPECULATIVE MODE
                use_ai=True,
                conversation_context=None,
            )
        )

        try:
            # Delegate to OrchestratorStreamingCore for main processing
            # PASS THE LOADED BASIC CONTEXT FOR ENRICHMENT
            async for event in self.streaming_core.stream_query_core(
                query=query,
                user_id=user_id,
                conversation_history=history_to_use,  # Pass optimized history
                session_id=session_id,
                images=images,
                tool_execution_counter=tool_execution_counter,
                correlation_id=correlation_id,
                initial_user_context=user_context,  # NEW: Pass basic context for late binding
            ):
                # Accumulate tokens for memory saving
                if event.get("type") == "token":
                    full_answer += event.get("data", "")

                yield event

            # 🎯 PROACTIVITY: Retrieve results from background task
            # By now, generation should be complete or nearly complete.
            try:
                # Wait for the task to finish (should be instant if stream took > 3s)
                followup_questions = await followup_task

                if followup_questions:
                    logger.info(
                        f"📝 [Proactive] Retrieved {len(followup_questions)} speculative follow-up questions"
                    )
                    # Emit metadata event with follow-up questions
                    yield {
                        "type": "metadata",
                        "data": {"followup_questions": followup_questions},
                    }
            except Exception as followup_err:
                logger.warning(f"⚠️ [Proactive] Failed to retrieve follow-ups: {followup_err}")

        except Exception as e:
            # Use error classification for better error handling
            from backend.app.core.error_classification import ErrorClassifier, get_error_context

            error_category, error_severity = ErrorClassifier.classify_error(e)
            error_context = get_error_context(
                e,
                correlation_id=correlation_id,
                user_id=user_id,
                query=query[:100],
            )

            logger.exception("❌ [Stream] Fatal error in stream_query", extra=error_context)
            add_span_event("react.stream.error", {"error": str(e)})
            # Yield final error event
            yield self._create_error_event(
                "fatal_error", f"Stream failed: {str(e)}", correlation_id
            )
            metrics_collector.stream_fatal_error_total.inc()
            return

        # 🧠 MEMORY PERSISTENCE: Save facts in background after stream completes
        # Uses MemoryHandler which provides race condition protection via per-user locks
        self.memory_handler.create_save_task(
            user_id=user_id,
            query=query,
            answer=full_answer,
            metrics_collector=metrics_collector,
        )

        return

    async def stream_proactive_event(
        self,
        user_id: str,
        event_type: str,
        context_data: dict[str, Any],
    ) -> AsyncGenerator[dict, None]:
        """
        Stream a proactive message triggered by a system event (e.g. Login).

        Logic:
        1. Load FULL User Context (Memory, Tasks, Unread items).
        2. Prompt LLM to decide IF and WHAT to say based on context + event.
        3. Stream response if proactive message is generated.

        Args:
            user_id: User triggering the event.
            event_type: Type of event (e.g. "USER_LOGIN", "PAGE_VISIT", "IDLE").
            context_data: Additional context (e.g. page_url, time_of_day).

        Yields:
            Stream events.
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        if not user_id or user_id == "anonymous":
            logger.warning("⚠️ [Proactive] Cannot trigger for anonymous user")
            return

        yield self.streaming_manager.create_initial_status_event(correlation_id)

        # 1. Load FULL Context immediately (we need to know what to be proactive about)
        # Using Parallel Load (Fast)
        user_context = await self.core.context_manager.get_user_context(
            self.db_pool, user_id, self.memory_handler.memory_orchestrator
        )

        # 2. Build Proactive Prompt
        # We need a specialized prompt that takes the Event + Memory and decides output.
        proactive_prompt = self.prompt_builder.build_proactive_prompt(
            user_id=user_id,
            context=user_context,
            event_type=event_type,
            event_context=context_data,
        )

        # 3. Generate content via LLM Gateway (Single Turn, Fast Model)
        # We use Flash because proactivity should be quick and doesn't need deep reasoning usually.
        # But we enable tool use? No, usually proactive message is just text.
        # IF we want it to "check calendar", it should have been done in context loading phase or via specialized tools.
        # For "Zero-Shot Proactivity", we rely on the context we just loaded.

        chat = self.llm_gateway.create_chat_with_history(
            history_to_use=[],  # No conversation history for the strict prompt, but maybe valuable context?
            # Actually, we should probably include recent history so it doesn't repeat itself.
            model_tier=TIER_FLASH,
        )

        # Add history to context for the prompt, but maybe not as chat messages to keep prompt clean?
        # Let's rely on the system prompt having the history summary if needed.

        # Stream the response
        try:
            logger.info(f"🤖 [Proactive] Triggering event {event_type} for {user_id}")

            # Streaming standard generation
            async for token in self.llm_gateway.stream_message(
                chat,
                user_message=f"SYSTEM EVENT: {event_type} occurred. Context: {context_data}. Generate proactive message or [SILENCE].",
                system_prompt=proactive_prompt,
                tier=TIER_FLASH,
            ):
                # Check for "silence" token or empty response if model decides not to speak?
                # The prompt determines this.
                yield {"type": "token", "data": token}

            yield {"type": "done", "data": {"route": "proactive"}}

        except Exception as e:
            logger.error(f"❌ [Proactive] Failed: {e}", exc_info=True)
            yield self._create_error_event("proactive_error", str(e), correlation_id)
```
