"""API routes — query, stream, and health endpoints.

POST /api/query                — synchronous graph invocation, returns full result
POST /api/query/stream         — start query + stream events via SSE
GET  /api/query/{run_id}/events — subscribe to events for a running query (Redis Pub/Sub)
DELETE /api/session/{id}       — clear conversation history
GET  /health                   — basic liveness probe
GET  /health/ready             — deep readiness probe (checks all services)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nuzantara_graph.api.middleware import get_current_user, rate_limit
from nuzantara_graph.config import settings
from nuzantara_graph.dependencies import get_services
from nuzantara_graph.services import Services
from nuzantara_schemas.events import SSEMessage, StreamEventType, StreamNodeEvent
from nuzantara_schemas.state import ChannelType, GraphState

logger = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Incoming query from any channel."""

    query: str = Field(..., min_length=1, max_length=5000)
    user_id: str = "anonymous"
    channel: ChannelType = ChannelType.WEB
    session_id: str | None = None


class QueryResponse(BaseModel):
    """Synchronous query result."""

    run_id: str
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: dict[str, Any] = Field(default_factory=dict)
    intent: str = ""
    domain: str | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    _rl: None = Depends(rate_limit),
) -> QueryResponse:
    """Execute a full graph query synchronously.

    Returns the complete answer after all nodes + grading finish.
    """
    run_id = str(uuid.uuid4())
    services: Services = request.app.state.services
    graph = request.app.state.compiled_graph

    logger.info(
        "query_start",
        run_id=run_id,
        query=req.query[:100],
        user_id=req.user_id,
        channel=req.channel,
    )

    try:
        # Semantic cache lookup — skip graph invocation if we have a match
        cached = await services.cache.get_semantic(
            req.query,
            embeddings_service=services.embeddings,
            qdrant_client=services.vector_store.client,
        )
        if cached:
            logger.info("query_cache_hit", run_id=run_id, query=req.query[:60])
            return QueryResponse(
                run_id=run_id,
                answer=cached.get("answer", ""),
                sources=cached.get("sources", []),
                confidence=cached.get("confidence", {}),
                intent=cached.get("intent", ""),
                domain=cached.get("domain"),
                token_usage={"total_tokens": 0, "cached": True},
            )

        # Load conversation history for multi-turn context
        conversation_history = []
        if req.session_id:
            conversation_history = await services.conversation_memory.load(req.session_id)
            logger.debug(
                "session_history_loaded",
                session_id=req.session_id,
                turns=len(conversation_history),
            )

        initial_state = GraphState(
            run_id=run_id,
            query=req.query,
            user_id=req.user_id,
            channel=req.channel,
            session_id=req.session_id,
            conversation_history=conversation_history,
        )

        result = await graph.ainvoke(initial_state)

        confidence_raw = result.get("confidence", {})
        if hasattr(confidence_raw, "model_dump"):
            confidence_raw = confidence_raw.model_dump()

        token_usage_raw = result.get("token_usage", [])
        total_tokens = 0
        for u in token_usage_raw:
            if hasattr(u, "input_tokens"):
                total_tokens += u.input_tokens + u.output_tokens
            elif isinstance(u, dict):
                total_tokens += u.get("input_tokens", 0) + u.get("output_tokens", 0)

        response = QueryResponse(
            run_id=run_id,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            confidence=confidence_raw,
            intent=str(result.get("intent", "")),
            domain=result.get("domain"),
            token_usage={"total_tokens": total_tokens},
            error=result.get("error"),
        )

        # Store in semantic cache if answer is clean (no error)
        if not response.error and response.answer:
            await services.cache.set_semantic(
                req.query,
                response.model_dump(),
                embeddings_service=services.embeddings,
                qdrant_client=services.vector_store.client,
            )

        # Persist conversation turns for multi-turn continuity
        if req.session_id and response.answer and not response.error:
            await services.conversation_memory.append(
                req.session_id, role="user", content=req.query
            )
            await services.conversation_memory.append(
                req.session_id, role="assistant", content=response.answer
            )

        return response

    except Exception as e:
        logger.error("query_failed", run_id=run_id, error=str(e), exc_info=True)
        detail = str(e) if settings.debug else "Internal server error"
        raise HTTPException(status_code=500, detail=detail)


_STREAM_HEARTBEAT_SECONDS = 2.0
_STREAM_TOTAL_TIMEOUT_SECONDS = 600.0  # 10 min hard cap


@router.post("/api/query/stream")
async def query_stream(
    req: QueryRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    _rl: None = Depends(rate_limit),
) -> StreamingResponse:
    """Start a query and stream node-level events via SSE.

    Each node emits START/END events. The final event is DONE with the answer.
    Sends heartbeat comments every 2s to keep the connection alive.
    Hard timeout of 600s prevents zombie connections.
    """
    run_id = str(uuid.uuid4())
    services: Services = request.app.state.services
    graph = request.app.state.compiled_graph

    logger.info(
        "stream_start",
        run_id=run_id,
        query=req.query[:100],
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        import time as _time

        sequence = 0
        last_answer: str = ""
        stream_start_monotonic = _time.monotonic()

        # Emit initial event
        start_event = StreamNodeEvent(
            run_id=run_id,
            event_type=StreamEventType.NODE_START,
            node="pipeline",
            data={"query": req.query[:100]},
            sequence=sequence,
        )
        yield _format_sse(start_event)
        sequence += 1

        try:
            # --- Semantic cache check (same as sync endpoint) ---
            cached = await services.cache.get_semantic(
                req.query,
                embeddings_service=services.embeddings,
                qdrant_client=services.vector_store.client,
            )
            if cached:
                logger.info("stream_cache_hit", run_id=run_id, query=req.query[:60])
                cache_event = StreamNodeEvent(
                    run_id=run_id,
                    event_type=StreamEventType.NODE_END,
                    node="cache",
                    data={
                        "answer": cached.get("answer", ""),
                        "intent": cached.get("intent", ""),
                        "cached": True,
                    },
                    sequence=sequence,
                )
                yield _format_sse(cache_event)
                sequence += 1
                last_answer = cached.get("answer", "")

                done_event = StreamNodeEvent(
                    run_id=run_id,
                    event_type=StreamEventType.DONE,
                    node="pipeline",
                    sequence=sequence,
                )
                yield _format_sse(done_event)
                return

            # --- Load conversation history ---
            conversation_history = []
            if req.session_id:
                conversation_history = await services.conversation_memory.load(req.session_id)

            initial_state = GraphState(
                run_id=run_id,
                query=req.query,
                user_id=req.user_id,
                channel=req.channel,
                session_id=req.session_id,
                conversation_history=conversation_history,
            )

            # --- Stream graph nodes (single invocation) ---
            stream_iter = graph.astream(initial_state, stream_mode="updates").__aiter__()

            while True:
                # Global timeout guard
                elapsed = _time.monotonic() - stream_start_monotonic
                if elapsed > _STREAM_TOTAL_TIMEOUT_SECONDS:
                    logger.warning("stream_timeout", run_id=run_id, elapsed_s=round(elapsed))
                    timeout_event = StreamNodeEvent(
                        run_id=run_id,
                        event_type=StreamEventType.ERROR,
                        data={"error": "Stream timeout exceeded"},
                        sequence=sequence,
                    )
                    yield _format_sse(timeout_event)
                    return

                try:
                    event = await asyncio.wait_for(
                        stream_iter.__anext__(),
                        timeout=_STREAM_HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                except StopAsyncIteration:
                    break

                for node_name, node_output in event.items():
                    node_start = StreamNodeEvent(
                        run_id=run_id,
                        event_type=StreamEventType.NODE_START,
                        node=node_name,
                        sequence=sequence,
                    )
                    yield _format_sse(node_start)
                    sequence += 1

                    event_data: dict[str, Any] = {}
                    if isinstance(node_output, dict):
                        if "current_node" in node_output:
                            event_data["current_node"] = node_output["current_node"]
                        if "intent" in node_output:
                            event_data["intent"] = str(node_output["intent"])
                        if "answer" in node_output:
                            event_data["answer"] = node_output["answer"]
                            last_answer = node_output["answer"]
                        if "grades" in node_output:
                            grades = node_output["grades"]
                            if grades:
                                last = grades[-1] if isinstance(grades, list) else grades
                                if hasattr(last, "model_dump"):
                                    event_data["grade"] = last.model_dump()
                                elif isinstance(last, dict):
                                    event_data["grade"] = last
                        if "error" in node_output and node_output["error"]:
                            event_data["error"] = node_output["error"]

                    node_end = StreamNodeEvent(
                        run_id=run_id,
                        event_type=StreamEventType.NODE_END,
                        node=node_name,
                        data=event_data,
                        sequence=sequence,
                    )
                    yield _format_sse(node_end)
                    sequence += 1

                    try:
                        await services.cache.publish_node_event(
                            run_id, node_end.model_dump()
                        )
                    except Exception:
                        pass  # Non-critical

            # Final DONE event
            done_event = StreamNodeEvent(
                run_id=run_id,
                event_type=StreamEventType.DONE,
                node="pipeline",
                sequence=sequence,
            )
            yield _format_sse(done_event)

            # Cache the result for future queries
            if last_answer:
                await services.cache.set_semantic(
                    req.query,
                    {"answer": last_answer, "run_id": run_id},
                    embeddings_service=services.embeddings,
                    qdrant_client=services.vector_store.client,
                )

            # Persist conversation turns
            if req.session_id and last_answer:
                await services.conversation_memory.append(
                    req.session_id, role="user", content=req.query
                )
                await services.conversation_memory.append(
                    req.session_id, role="assistant", content=last_answer
                )

        except Exception as e:
            logger.error("stream_failed", run_id=run_id, error=str(e), exc_info=True)
            error_msg = str(e) if settings.debug else "Stream processing failed"
            error_event = StreamNodeEvent(
                run_id=run_id,
                event_type=StreamEventType.ERROR,
                data={"error": error_msg},
                sequence=sequence,
            )
            yield _format_sse(error_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/api/session/{session_id}")
async def clear_session(
    session_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    """Clear conversation history for a session (new chat button)."""
    services: Services = request.app.state.services
    await services.conversation_memory.clear(session_id)
    logger.info("session_cleared", session_id=session_id, user_id=user.get("user_id"))
    return {"session_id": session_id, "cleared": True}


@router.get("/api/query/{run_id}/events")
async def query_events(
    run_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    _rl: None = Depends(rate_limit),
) -> StreamingResponse:
    """Subscribe to events for an already-running query via Redis Pub/Sub.

    Useful for reconnecting to an in-progress stream or WebSocket fallback.
    """
    services: Services = request.app.state.services

    async def pubsub_generator() -> AsyncGenerator[str, None]:
        client = await services.cache._get_client()
        pubsub = client.pubsub()
        channel = f"v6:stream:{run_id}"

        try:
            await pubsub.subscribe(channel)
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=30.0,
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    event = StreamNodeEvent.model_validate_json(data)
                    yield _format_sse(event)

                    # Stop on DONE or ERROR
                    if event.event_type in (
                        StreamEventType.DONE,
                        StreamEventType.ERROR,
                    ):
                        break
                else:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        pubsub_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

health_router = APIRouter()


@health_router.get("/health")
async def health() -> dict:
    """Basic liveness probe — returns immediately."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
        "embeddings": {"model": settings.embedding_model},
    }


@health_router.get("/health/ready")
async def readiness(request: Request) -> dict:
    """Deep readiness probe — checks all service connections."""
    try:
        services: Services = request.app.state.services
        checks = await services.health_check()
        all_ok = checks.get("all_ok", False)

        return {
            "ready": all_ok,
            "services": checks,
            "version": settings.app_version,
        }
    except Exception as e:
        return {
            "ready": False,
            "error": str(e),
            "version": settings.app_version,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_sse(event: StreamNodeEvent) -> str:
    """Format a StreamNodeEvent as an SSE string."""
    msg = SSEMessage(
        event=event.event_type,
        data=event.model_dump_json(),
        id=f"{event.run_id}-{event.sequence}",
    )
    return msg.to_sse()
