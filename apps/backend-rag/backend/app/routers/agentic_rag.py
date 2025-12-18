"""
Agentic RAG API Router
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
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
    conversation_history: list[
        ConversationMessageInput
    ] | None = None  # Direct history from frontend


class AgenticQueryResponse(BaseModel):
    answer: str
    sources: list[Any]
    context_length: int
    execution_time: float
    route_used: str | None
    debug_info: dict | None = None


import json

from fastapi.responses import StreamingResponse


@router.post("/query", response_model=AgenticQueryResponse)
async def query_agentic_rag(
    request: AgenticQueryRequest,
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_database_pool),
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

        result = await orchestrator.process_query(
            query=request.query,
            user_id=request.user_id,
            conversation_history=conversation_history,
        )

        return AgenticQueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            context_length=result["context_used"],
            execution_time=result["execution_time"],
            route_used=result["route_used"],
            debug_info=result.get("debug_info"),
        )
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"❌ Error in query_agentic_rag: {str(e)}\n{tb}")
        # Temporarily include traceback in response for debugging
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nTRACEBACK:\n{tb}")


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
        import json

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
                    SELECT email FROM team_members
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
    request: AgenticQueryRequest,
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: Any | None = Depends(get_database_pool),
):
    """
    Stream the Agentic RAG process (SSE).
    Supports conversation history via:
    1. Direct conversation_history from frontend (preferred - works even if DB is down)
    2. conversation_id or session_id lookup from database (fallback)
    """
    # Validate query is not empty
    if not request.query or not request.query.strip():
        logger.warning("⚠️ Empty query received - rejecting")
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    async def event_generator():
        # Priority 1: Use conversation_history from frontend if provided
        conversation_history: list[dict] = []

        if request.conversation_history and len(request.conversation_history) > 0:
            # Frontend sent conversation history directly - use it (DB-independent!)
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

        try:
            async for event in orchestrator.stream_query(
                query=request.query,
                user_id=request.user_id,
                conversation_history=conversation_history if conversation_history else None,
            ):
                # Format as SSE
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_data = {"type": "error", "message": str(e)}
            if "429" in str(e) or "ResourceExhausted" in str(e):
                error_data["code"] = "QUOTA_EXCEEDED"
                error_data["message"] = "Usage limit reached. Please try again later."
            elif "503" in str(e) or "ServiceUnavailable" in str(e):
                error_data["code"] = "SERVICE_UNAVAILABLE"
                error_data["message"] = "Service temporarily unavailable. Please try again."

            yield f"data: {json.dumps({'type': 'error', 'data': error_data})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
