"""
Streaming endpoints extracted from main_cloud to keep entrypoint slim.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.validation import validate_auth_mixed
from app.utils.state_helpers import get_app_state, get_request_state
from services.intelligent_router import IntelligentRouter
from services.auto_crm_service import get_auto_crm_service
from utils.response_sanitizer import sanitize_zantara_response

logger = logging.getLogger(__name__)

router = APIRouter()

# Streaming timeout configuration (seconds)
STREAM_TIMEOUT_SECONDS = 120  # 2 minutes max for entire stream
CHUNK_TIMEOUT_SECONDS = 30  # 30 seconds max between chunks


def _parse_history(history_raw: str | None) -> list[dict[str, Any]]:
    """Parse conversation history from raw string."""
    if not history_raw:
        return []
    try:
        parsed = json.loads(history_raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        logger.warning("Invalid conversation_history payload received")
    return []


class ChatStreamRequest(BaseModel):
    """Request model for POST /api/chat/stream"""

    message: str
    user_id: str | None = None
    conversation_history: list[dict] | None = None
    metadata: dict | None = None
    zantara_context: dict | None = None
    session_id: str | None = None  # Support root-level session_id (frontend compatibility)


@router.get("/api/v2/bali-zero/chat-stream")
@router.get("/bali-zero/chat-stream")
async def bali_zero_chat_stream(
    request: Request,
    query: str,
    background_tasks: BackgroundTasks,
    user_email: str | None = None,
    user_role: str = "member",
    conversation_history: str | None = None,
    authorization: str | None = Header(None),
    auth_token: str | None = None,
) -> StreamingResponse:
    """
    Streaming chat endpoint using IntelligentRouter for RAG-based responses.
    """

    if not query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    # Use middleware auth result first (already validated by HybridAuthMiddleware)
    user_profile = get_request_state(request.state, "user", expected_type=dict)

    # Fallback: validate manually if middleware didn't set user (shouldn't happen)
    if not user_profile:
        user_profile = await validate_auth_mixed(
            authorization=authorization,
            auth_token=auth_token,
            x_api_key=request.headers.get("X-API-Key"),  # Note: Capital letters for header name
        )

    if not user_profile:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide either JWT token (Bearer <token>) or API key (X-API-Key header)",
        )

    if not get_app_state(request.app.state, "services_initialized", default=False):
        raise HTTPException(status_code=503, detail="Services are still initializing")

    intelligent_router: IntelligentRouter = request.app.state.intelligent_router

    if not user_email:
        user_email = user_profile.get("email") or user_profile.get("name")
    user_role = user_profile.get("role", user_role or "member")

    conversation_history_list = _parse_history(conversation_history)
    user_id = user_email or user_role or user_profile.get("id") or "anonymous"

    # Collaborator lookup
    collaborator = None
    collaborator_service = get_app_state(request.app.state, "collaborator_service")
    if collaborator_service and user_email:
        try:
            collaborator = await collaborator_service.identify(user_email)
            if collaborator and collaborator.id != "anonymous":
                logger.info(f"✅ Identified user: {collaborator.name} ({collaborator.role})")
            else:
                logger.info(f"👤 User not in team database: {user_email}")
        except Exception as e:
            logger.warning(f"⚠️ Collaborator lookup failed: {e}")

    # Load user memory from persistent storage
    memory_service = request.app.state.memory_service
    user_memory = None
    if memory_service:
        try:
            memory_obj = await memory_service.get_memory(user_id)
            if memory_obj:
                user_memory = {
                    "facts": memory_obj.profile_facts,
                    "summary": memory_obj.summary,
                    "counters": memory_obj.counters,
                }
                logger.info(f"✅ Loaded memory for {user_id}: {len(memory_obj.profile_facts)} facts")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load memory for {user_id}: {e}")

    async def event_stream() -> AsyncIterator[str]:
        # Send connection metadata
        metadata = {
            "type": "metadata",
            "data": {
                "status": "connected",
                "user": user_id,
                "identified": (
                    collaborator.name if collaborator and collaborator.id != "anonymous" else None
                ),
            },
        }
        yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"

        try:
            # Wrap entire stream with timeout to prevent infinite hangs
            async with asyncio.timeout(STREAM_TIMEOUT_SECONDS):
                last_chunk_time = asyncio.get_event_loop().time()

                async for chunk in intelligent_router.stream_chat(
                    message=query,
                    user_id=user_id,
                    conversation_history=conversation_history_list,
                    memory=user_memory,
                    collaborator=collaborator,
                ):
                    # Check chunk timeout (time since last chunk)
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_chunk_time > CHUNK_TIMEOUT_SECONDS:
                        logger.warning(f"Chunk timeout exceeded ({CHUNK_TIMEOUT_SECONDS}s)")
                        yield f"data: {json.dumps({'type': 'error', 'data': 'Response timeout - please try again'}, ensure_ascii=False)}\n\n"
                        return
                    last_chunk_time = current_time

                    if isinstance(chunk, dict):
                        chunk_type = chunk.get("type", "token")
                        chunk_data = chunk.get("data", "")

                        if chunk_type == "metadata":
                            yield f"data: {json.dumps({'type': 'metadata', 'data': chunk_data}, ensure_ascii=False)}\n\n"
                        elif chunk_type == "token":
                            yield f"data: {json.dumps({'type': 'token', 'data': chunk_data}, ensure_ascii=False)}\n\n"
                        elif chunk_type == "done":
                            yield f"data: {json.dumps({'type': 'done', 'data': chunk_data}, ensure_ascii=False)}\n\n"
                        else:
                            logger.warning(f"Unknown chunk type: {chunk_type}")
                    elif isinstance(chunk, str):
                        if chunk.startswith("[METADATA]"):
                            try:
                                json_str = chunk.replace("[METADATA]", "").strip()
                                metadata_data = json.loads(json_str)
                                yield f"data: {json.dumps({'type': 'metadata', 'data': metadata_data}, ensure_ascii=False)}\n\n"
                            except Exception as e:
                                logger.warning(f"Failed to parse legacy metadata chunk: {e}")
                        else:
                            yield f"data: {json.dumps({'type': 'token', 'data': chunk}, ensure_ascii=False)}\n\n"
                    else:
                        logger.warning(f"Unexpected chunk type: {type(chunk)}")

            # Background: Auto-CRM Processing
            try:
                crm_messages = [{"role": "user", "content": query}]
                background_tasks.add_task(
                    get_auto_crm_service().process_conversation,
                    conversation_id=0,
                    messages=crm_messages,
                    user_email=user_email,
                    team_member="system",
                )
            except Exception as e:
                logger.error(f"⚠️ Auto-CRM background task failed: {e}")

            # Background: Collective Memory Processing
            try:
                collective_workflow = get_app_state(request.app.state, "collective_memory_workflow")
                if collective_workflow:
                    state = {
                        "query": query,
                        "user_id": user_id,
                        "session_id": "session_0",
                        "participants": [user_id],
                        "existing_memories": [],
                        "relationships_to_update": [],
                        "profile_updates": [],
                        "consolidation_actions": [],
                        "memory_to_store": None,
                    }

                    async def run_collective_memory(workflow, input_state):
                        try:
                            await workflow.ainvoke(input_state)
                            logger.info(f"🧠 Collective Memory processed for {input_state['user_id']}")
                        except Exception as e:
                            logger.error(f"❌ Collective Memory failed: {e}")

                    background_tasks.add_task(run_collective_memory, collective_workflow, state)
            except Exception as e:
                logger.error(f"⚠️ Collective Memory background task failed: {e}")

        except asyncio.TimeoutError:
            logger.error(f"Stream timeout after {STREAM_TIMEOUT_SECONDS}s for user {user_id}")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Response timeout - the request took too long. Please try again.'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("Streaming error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/chat/stream")
async def chat_stream_post(
    request: Request,
    body: ChatStreamRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    """
    Modern POST endpoint for chat streaming (JSON body).
    Compatible with frontend Next.js client.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty")

    user_profile = getattr(request.state, "user", None)

    if not user_profile:
        user_profile = await validate_auth_mixed(
            authorization=authorization,
            auth_token=None,
            x_api_key=request.headers.get("X-API-Key"),
        )

    if not user_profile:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide either JWT token (Bearer <token>) or API key (X-API-Key header)",
        )

    if not get_app_state(request.app.state, "services_initialized", default=False):
        raise HTTPException(status_code=503, detail="Services are still initializing")

    intelligent_router: IntelligentRouter = request.app.state.intelligent_router

    user_email = body.user_id or user_profile.get("email") or user_profile.get("name")
    user_role = user_profile.get("role", "member")

    conversation_history_list = body.conversation_history or []
    user_id = user_email or user_role or user_profile.get("id") or "anonymous"

    session_id = body.session_id
    if not session_id and body.zantara_context:
        session_id = body.zantara_context.get("session_id")

    if not session_id:
        import uuid
        from datetime import datetime

        session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        logger.info(f"🆕 Generated new session_id: {session_id}")

    if not conversation_history_list and session_id and hasattr(request.app.state, "conversation_service"):
        try:
            history_data = await request.app.state.conversation_service.get_history(
                user_email=user_email, session_id=session_id, limit=20
            )
            if history_data and history_data.get("messages"):
                conversation_history_list = history_data["messages"]
                logger.info(
                    f"📜 Loaded {len(conversation_history_list)} messages from {history_data.get('source')} for session {session_id}"
                )
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch history for session {session_id}: {e}")

    collaborator = None
    collaborator_service = get_app_state(request.app.state, "collaborator_service")
    if collaborator_service and user_email:
        try:
            collaborator = await collaborator_service.identify(user_email)
            if collaborator and collaborator.id != "anonymous":
                logger.info(f"✅ Identified user: {collaborator.name} ({collaborator.role})")
            else:
                logger.info(f"👤 User not in team database: {user_email}")
        except Exception as e:
            logger.warning(f"⚠️ Collaborator lookup failed: {e}")

    memory_service = request.app.state.memory_service
    user_memory = None
    if memory_service:
        try:
            memory_obj = await memory_service.get_memory(user_id)
            if memory_obj:
                user_memory = {
                    "facts": memory_obj.profile_facts,
                    "summary": memory_obj.summary,
                    "counters": memory_obj.counters,
                }
                logger.info(f"✅ Loaded memory for {user_id}: {len(memory_obj.profile_facts)} facts")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load memory for {user_id}: {e}")

    async def event_stream() -> AsyncIterator[str]:
        metadata = {
            "type": "metadata",
            "data": {
                "status": "connected",
                "user": user_id,
                "identified": (
                    collaborator.name if collaborator and collaborator.id != "anonymous" else None
                ),
            },
        }
        yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"

        try:
            ai_full_response = ""

            # Wrap entire stream with timeout to prevent infinite hangs
            async with asyncio.timeout(STREAM_TIMEOUT_SECONDS):
                last_chunk_time = asyncio.get_event_loop().time()

                async for chunk in intelligent_router.stream_chat(
                    message=body.message,
                    user_id=user_id,
                    conversation_history=conversation_history_list,
                    memory=user_memory,
                    collaborator=collaborator,
                ):
                    # Check chunk timeout (time since last chunk)
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_chunk_time > CHUNK_TIMEOUT_SECONDS:
                        logger.warning(f"Chunk timeout exceeded ({CHUNK_TIMEOUT_SECONDS}s)")
                        yield f"data: {json.dumps({'type': 'error', 'data': 'Response timeout - please try again'}, ensure_ascii=False)}\n\n"
                        return
                    last_chunk_time = current_time

                    if isinstance(chunk, dict):
                        chunk_type = chunk.get("type", "token")
                        chunk_data = chunk.get("data", "")

                        if chunk_type == "metadata":
                            yield f"data: {json.dumps({'type': 'metadata', 'data': chunk_data}, ensure_ascii=False)}\n\n"
                        elif chunk_type == "token":
                            ai_full_response += str(chunk_data) if chunk_data else ""
                            yield f"data: {json.dumps({'type': 'token', 'data': chunk_data}, ensure_ascii=False)}\n\n"
                        elif chunk_type == "done":
                            yield f"data: {json.dumps({'type': 'done', 'data': chunk_data}, ensure_ascii=False)}\n\n"
                        else:
                            logger.warning(f"Unknown chunk type: {chunk_type}")
                    elif isinstance(chunk, str):
                        if chunk.startswith("[METADATA]"):
                            try:
                                json_str = chunk.replace("[METADATA]", "").replace("[METADATA]", "")
                                metadata_data = json.loads(json_str)
                                yield f"data: {json.dumps({'type': 'metadata', 'data': metadata_data}, ensure_ascii=False)}\n\n"
                            except Exception as e:
                                logger.warning(f"Failed to parse legacy metadata chunk: {e}")
                        else:
                            ai_full_response += chunk
                            yield f"data: {json.dumps({'type': 'token', 'data': chunk}, ensure_ascii=False)}\n\n"
                    else:
                        logger.warning(f"Unexpected chunk type: {type(chunk)}")

            if ai_full_response:
                try:
                    new_messages = conversation_history_list + [
                        {"role": "user", "content": body.message},
                        {"role": "assistant", "content": ai_full_response},
                    ]

                    session_id_to_save = session_id

                    await request.app.state.conversation_service.save_conversation(
                        user_email=user_email,
                        messages=new_messages,
                        session_id=session_id_to_save,
                        metadata=body.metadata,
                    )
                    logger.info(f"💾 Saved conversation for {user_email}")
                except Exception as e:
                    logger.error(f"❌ Failed to save conversation: {e}")

            try:
                collective_workflow = get_app_state(request.app.state, "collective_memory_workflow")
                if collective_workflow:
                    state = {
                        "query": body.message,
                        "user_id": user_id,
                        "session_id": (
                            body.zantara_context.get("session_id", "session_0")
                            if body.zantara_context
                            else "session_0"
                        ),
                        "participants": [user_id],
                        "existing_memories": [],
                        "relationships_to_update": [],
                        "profile_updates": [],
                        "consolidation_actions": [],
                        "memory_to_store": None,
                    }

                    async def run_collective_memory(workflow, input_state):
                        try:
                            await workflow.ainvoke(input_state)
                            logger.info(
                                f"🧠 Collective Memory processed for {input_state['user_id']}"
                            )
                        except Exception as e:
                            logger.error(f"❌ Collective Memory failed: {e}")

                    background_tasks.add_task(run_collective_memory, collective_workflow, state)
            except Exception as e:
                logger.error(f"⚠️ Collective Memory background task failed: {e}")

        except asyncio.TimeoutError:
            logger.error(f"Stream timeout after {STREAM_TIMEOUT_SECONDS}s for user {user_id}")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Response timeout - the request took too long. Please try again.'}, ensure_ascii=False)}\n\n"
        except ValueError as ve:
            error_msg = str(ve).lower()
            if "leaked" in error_msg or "api key" in error_msg:
                logger.critical(f"🚨 API key error in stream: {ve}")
                error_data = {
                    "type": "error",
                    "data": "API key was reported as leaked. Please use another API key. The technical team has been notified.",
                }
            else:
                error_data = {"type": "error", "data": str(ve)}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("Streaming error: %s", exc)
            error_msg = str(exc).lower()
            if "403" in error_msg or "leaked" in error_msg or "api key" in error_msg:
                error_data = {
                    "type": "error",
                    "data": "API key configuration error. The technical team has been notified.",
                }
            else:
                error_data = {"type": "error", "data": str(exc)}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

