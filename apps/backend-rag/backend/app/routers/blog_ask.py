"""
Blog Ask Router - AskZantara widget endpoint for public blog articles
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.rag.agentic import AgenticRAGOrchestrator, create_agentic_rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/blog", tags=["blog"])

# Global orchestrator instance (lazy loaded)
_blog_orchestrator: AgenticRAGOrchestrator | None = None


async def get_blog_orchestrator(request: Request):
    """Get or create the RAG orchestrator for blog queries"""
    global _blog_orchestrator
    if _blog_orchestrator is None:
        db_pool = getattr(request.app.state, "db_pool", None)
        search_service = getattr(request.app.state, "search_service", None)
        _blog_orchestrator = create_agentic_rag(retriever=search_service, db_pool=db_pool)
    return _blog_orchestrator


class BlogAskRequest(BaseModel):
    """Request model for blog article questions"""

    question: str
    article_title: str | None = None
    article_category: str | None = None
    article_content: str | None = None  # Optional context from article


class BlogAskResponse(BaseModel):
    """Response model for blog article questions"""

    answer: str
    sources: list[dict[str, Any]] = []
    confidence: float = 0.0


@router.post("/ask", response_model=BlogAskResponse)
async def ask_zantara(request: Request, body: BlogAskRequest):
    """
    Public endpoint for AskZantara widget on blog articles.

    Allows visitors to ask questions about article topics.
    No authentication required.
    """
    try:
        orchestrator = await get_blog_orchestrator(request)

        # Build context-aware query
        query = body.question

        # Add article context to help RAG system
        context_parts = []
        if body.article_title:
            context_parts.append(f"Article: {body.article_title}")
        if body.article_category:
            context_parts.append(f"Category: {body.article_category}")

        if context_parts:
            query = f"[Context: {', '.join(context_parts)}] {query}"

        logger.info(f"📝 Blog ask: {body.question[:100]}... (category={body.article_category})")

        # Call RAG orchestrator
        result = await orchestrator.process_query(
            query=query,
            user_id="blog_visitor",
            session_id=None,
        )

        # Format sources for response
        sources = []
        if result.sources:
            for source in result.sources[:5]:  # Limit to 5 sources
                if isinstance(source, dict):
                    sources.append(
                        {
                            "title": source.get("title", "Source"),
                            "snippet": source.get("content", "")[:200]
                            if source.get("content")
                            else "",
                        }
                    )
                elif hasattr(source, "title"):
                    sources.append(
                        {
                            "title": getattr(source, "title", "Source"),
                            "snippet": getattr(source, "content", "")[:200]
                            if hasattr(source, "content")
                            else "",
                        }
                    )

        # Calculate confidence from evidence score if available
        confidence = 0.7  # Default confidence
        if hasattr(result, "evidence_score"):
            confidence = result.evidence_score
        elif hasattr(result, "debug_info") and result.debug_info:
            confidence = result.debug_info.get("evidence_score", 0.7)

        return BlogAskResponse(
            answer=result.answer,
            sources=sources,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"❌ Blog ask error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Sorry, I couldn't process your question. Please try again."
        ) from e
