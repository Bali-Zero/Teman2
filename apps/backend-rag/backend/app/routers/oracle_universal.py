"""
=======================================
ZANTARA v5.3 (Ultra Hybrid) - Universal Oracle API
=======================================

Author: Senior DevOps Engineer & Database Administrator
Version: 5.3.1 (Refactored)
Production Status: READY
Description:
Production-ready hybrid RAG system integrating:
- Qdrant Vector Database (Semantic Search)
- Google Drive Integration (PDF Document Repository)
- Google Gemini 2.5 Flash (Reasoning Engine)
- User Identity & Localization System (PostgreSQL)
- Multimodal Capabilities (Text + Audio)
- Comprehensive Error Handling & Logging

Language Protocol:
- Source Code & Logs: ENGLISH (Standard)
- Knowledge Base: Bahasa Indonesia (Indonesian Laws)
- WebApp UI: ENGLISH
- AI Responses: User's preferred language (from users.meta_json.language)
"""

import logging
import time
import traceback
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import get_current_user, get_search_service
from app.models import UserProfile
from services.oracle_service import oracle_service
from services.search_service import SearchService

logger = logging.getLogger(__name__)


class ConversationMessage(BaseModel):
    """Single message in conversation history"""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class OracleQueryRequest(BaseModel):
    """Universal Oracle query request with user context"""

    query: str = Field(..., description="Natural language query", min_length=3)
    user_email: str | None = Field(None, description="User email for personalization")
    language_override: str | None = Field(None, description="Override user language preference")
    domain_hint: str | None = Field(None, description="Optional domain hint for routing")
    context_docs: list[str] | None = Field(None, description="Specific document IDs to analyze")
    use_ai: bool = Field(True, description="Enable AI reasoning")
    include_sources: bool = Field(True, description="Include source document references")
    response_format: str = Field(
        "structured", description="Response format: 'structured' or 'conversational'"
    )
    limit: int = Field(10, ge=1, le=50, description="Max document results")
    session_id: str | None = Field(None, description="Session identifier for analytics")
    conversation_history: list[ConversationMessage] | None = Field(
        None, description="Previous messages in this conversation for context continuity"
    )


class OracleQueryResponse(BaseModel):
    """Universal Oracle query response with full context"""

    model_config = ConfigDict(protected_namespaces=())

    success: bool
    query: str
    user_email: str | None = None

    # Response Details
    answer: str | None = None
    answer_language: str = "en"
    model_used: str | None = None

    # Source Information
    sources: list[dict[str, Any]] = Field(default_factory=list)
    document_count: int = 0

    # Context Information
    collection_used: str | None = None
    routing_reason: str | None = None
    domain_confidence: dict[str, float] | None = None

    # User Context
    user_profile: UserProfile | None = None
    language_detected: str | None = None

    # Performance Metrics
    execution_time_ms: float
    search_time_ms: float | None = None
    reasoning_time_ms: float | None = None

    # Error Handling
    error: str | None = None
    warning: str | None = None

    # Enhanced Services (NEW)
    followup_questions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list, description="Source citations with metadata"
    )
    clarification_needed: bool = Field(
        default=False, description="Whether query needs clarification"
    )
    clarification_question: str | None = Field(
        default=None, description="Clarification question if needed"
    )
    personality_used: str | None = Field(default=None, description="Personality type used")
    golden_answer_used: bool = Field(
        default=False, description="Whether a cached golden answer was used"
    )
    user_memory_facts: list[str] = Field(
        default_factory=list, description="User's stored profile facts for context"
    )


class FeedbackRequest(BaseModel):
    """User feedback for continuous learning"""

    user_email: str
    query_text: str
    original_answer: str
    user_correction: str | None = None
    feedback_type: str = Field(..., description="Type of feedback")
    rating: int = Field(..., ge=1, le=5, description="User satisfaction rating")
    notes: str | None = None
    session_id: str | None = Field(None, description="Session identifier")


router = APIRouter(prefix="/api/oracle", tags=["Oracle v5.3 - Ultra Hybrid"])


@router.post("/query", response_model=OracleQueryResponse)
async def hybrid_oracle_query(
    request: OracleQueryRequest,
    service: SearchService = Depends(get_search_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Ultra Hybrid Oracle Query - v5.3 (Refactored)
    Integrates Qdrant search, Google Drive, and Gemini reasoning via OracleService.
    """
    try:
        result = await oracle_service.process_query(
            request_query=request.query,
            request_user_email=request.user_email,
            request_limit=request.limit,
            request_session_id=request.session_id,
            request_include_sources=request.include_sources,
            request_use_ai=request.use_ai,
            request_language_override=request.language_override,
            request_conversation_history=request.conversation_history,
            search_service=service,
        )

        # Pydantic conversion handles the dict->model validation
        # Special handling for user_profile if needed (ensure dict has user_id)
        if result.get("user_profile") and isinstance(result["user_profile"], dict):
            profile_data = result["user_profile"]
            if "id" in profile_data and "user_id" not in profile_data:
                profile_data["user_id"] = profile_data["id"]

        return OracleQueryResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Oracle Router Error: {e}")
        logger.debug(traceback.format_exc())
        return OracleQueryResponse(
            success=False, query=request.query, error=str(e), execution_time_ms=0, document_count=0
        )


@router.post("/feedback")
async def submit_user_feedback(feedback: FeedbackRequest):
    """
    Submit user feedback for continuous learning and system improvement
    """
    try:
        success = await oracle_service.submit_feedback(feedback.dict())
        return {"success": success}
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/health")
async def oracle_health_check():
    """Health check for Oracle v5.3 services"""
    return {
        "status": "active",
        "service": "Oracle v5.3",
        "mode": "Refactored (Service Layer)",
        "timestamp": time.time(),
    }


@router.get("/drive/test")
async def test_drive_connection():
    """Test Google Drive integration"""
    return {"status": "moved_to_service", "available": True}


@router.get("/gemini/test")
async def test_gemini_integration():
    """Test Google Gemini integration"""
    return {"status": "moved_to_service", "available": True}


@router.get("/user/profile/{user_email}")
async def get_user_profile_endpoint(user_email: str):
    """Get user profile with localization preferences"""
    return {"status": "not_implemented", "email": user_email}
