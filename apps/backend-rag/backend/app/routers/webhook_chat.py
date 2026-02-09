"""
Webhook Chat Router
Provides /webhook/chat endpoint with automatic conversation persistence
Integrates with RAG orchestrator for context-aware responses
"""

import logging
from datetime import datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool, get_orchestrator
from backend.app.utils.logging_utils import get_logger, log_error, log_success
from backend.db.repositories.conversation_repository import ConversationRepository
from backend.services.rag.agentic import AgenticRAGOrchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook-chat"])


class ChatRequest(BaseModel):
    """Chat request with session support"""

    query: str
    session_id: str
    user_id: str | None = None  # Optional, will use authenticated user if not provided
    metadata: dict | None = None


class ChatResponse(BaseModel):
    """Chat response with persistence confirmation"""

    answer: str
    session_id: str
    conversation_id: int | None = None
    sources: list[dict] = []
    execution_time: float = 0.0
    persisted: bool = False
    error: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def webhook_chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
):
    """
    Chat endpoint with automatic conversation persistence

    Features:
    - Retrieves conversation history from DB before processing query
    - Injects history into RAG context for continuity
    - Saves user query + assistant response after processing
    - Returns conversation_id for tracking

    Request body:
    {
        "query": "What is the capital of France?",
        "session_id": "session-123",
        "metadata": {"source": "webapp", "query_type": "general"}
    }

    Response:
    {
        "answer": "The capital of France is Paris.",
        "session_id": "session-123",
        "conversation_id": 42,
        "sources": [...],
        "execution_time": 1.23,
        "persisted": true
    }
    """
    # SECURITY: Use authenticated user's email
    user_email = current_user.get("email") or current_user.get("user_id")

    if not user_email:
        raise HTTPException(status_code=401, detail="User email not found in token")

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Initialize repository
    repo = ConversationRepository(db_pool)

    # Step 1: Retrieve conversation history from DB
    conversation_history = await repo.get_messages(
        session_id=request.session_id,
        limit=20,  # Last 20 messages for context
    )

    logger.info(
        f"📚 Retrieved {len(conversation_history)} messages for session {request.session_id}"
    )

    # Step 2: Process query with RAG orchestrator (with history context)
    try:
        import time

        start_time = time.time()

        result = await orchestrator.process_query(
            query=request.query,
            user_id=user_email,
            session_id=request.session_id,
            conversation_history=conversation_history,
        )

        execution_time = time.time() - start_time

        log_success(
            logger,
            "RAG query processed",
            session_id=request.session_id,
            execution_time=execution_time,
        )

    except Exception as e:
        log_error(logger, "RAG processing failed", error=e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

    # Step 3: Save conversation (user query + assistant response)
    new_messages = [
        {"role": "user", "content": request.query, "timestamp": datetime.now().isoformat()},
        {
            "role": "assistant",
            "content": result.answer,
            "timestamp": datetime.now().isoformat(),
        },
    ]

    # Merge metadata
    conversation_metadata = {
        **(request.metadata or {}),
        "query_type": result.route_used or "unknown",
        "collections_used": [src.get("collection") for src in result.sources if src.get("collection")],
        "tools_called": len(result.tools_called),
        "model_used": result.model_used,
        "execution_time": execution_time,
    }

    conversation_id = await repo.save_messages(
        session_id=request.session_id,
        user_id=user_email,
        messages=new_messages,
        metadata=conversation_metadata,
    )

    persisted = conversation_id is not None

    if persisted:
        log_success(
            logger,
            "Conversation persisted",
            conversation_id=conversation_id,
            session_id=request.session_id,
        )
    else:
        logger.warning(f"⚠️ Failed to persist conversation for session {request.session_id}")

    # Step 4: Return response
    return ChatResponse(
        answer=result.answer,
        session_id=request.session_id,
        conversation_id=conversation_id,
        sources=result.sources,
        execution_time=execution_time,
        persisted=persisted,
    )


@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
):
    """
    Retrieve conversation history for a session

    Query params:
    - limit: Max number of messages to return (default: 20, 0 = all)
    """
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    repo = ConversationRepository(db_pool)

    messages = await repo.get_messages(session_id=session_id, limit=limit)

    return {
        "success": True,
        "session_id": session_id,
        "messages": messages,
        "total_messages": len(messages),
    }


@router.delete("/chat/cleanup")
async def cleanup_old_conversations(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool | None = Depends(get_database_pool),
):
    """
    Admin endpoint: Cleanup conversations older than specified days

    Requires authentication. Only for admin/system use.

    Query params:
    - days: Number of days to keep (default: 30)
    """
    # Check if user has admin role (optional - add role check if needed)
    user_role = current_user.get("role", "user")
    if user_role not in ["admin", "system"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    repo = ConversationRepository(db_pool)

    deleted_count = await repo.cleanup_old_conversations(days=days)

    return {
        "success": True,
        "deleted_count": deleted_count,
        "cutoff_days": days,
    }
