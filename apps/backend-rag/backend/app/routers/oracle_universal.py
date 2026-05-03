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
- Google Gemini 3 Flash Preview (Reasoning Engine)
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

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.dependencies import get_current_user, get_search_service
from backend.app.models import UserProfile
from backend.services.oracle.oracle_service import oracle_service
from backend.services.search.search_service import SearchService

logger = logging.getLogger(__name__)

# Dedicated logger for the Q1 drop-field WARN so ops can route, mute or
# aggregate it independently of the router's other output. Sentry tag key
# is `oracle.dropped_fields` (field names only — Sentry PII redaction is
# handled globally in backend/app/setup/sentry_config.py).
_DROPPED_FIELDS_LOGGER = logging.getLogger("oracle.query.dropped_fields")


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
        "structured", description="Response format: 'structured' or 'conversational'",
    )
    limit: int = Field(10, ge=1, le=50, description="Max document results")
    session_id: str | None = Field(None, description="Session identifier for analytics")
    conversation_history: list[ConversationMessage] | None = Field(
        None, description="Previous messages in this conversation for context continuity",
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
        default_factory=list, description="Suggested follow-up questions",
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list, description="Source citations with metadata",
    )
    clarification_needed: bool = Field(
        default=False, description="Whether query needs clarification",
    )
    clarification_question: str | None = Field(
        default=None, description="Clarification question if needed",
    )
    personality_used: str | None = Field(default=None, description="Personality type used")
    golden_answer_used: bool = Field(
        default=False, description="Whether a cached golden answer was used",
    )
    user_memory_facts: list[str] = Field(
        default_factory=list, description="User's stored profile facts for context",
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
) -> OracleQueryResponse:
    """
    Ultra Hybrid Oracle Query - v5.3 (Refactored)
    Integrates Qdrant search, Google Drive, and Gemini reasoning via OracleService.
    """
    # Known-unwired request fields (Q1 from wave 1 audit). Logged so that
    # clients sending them know the hint is silently dropped until the service
    # layer consumes it. Contract is kept so the OpenAPI schema stays stable.
    _unwired = [
        k
        for k in ("domain_hint", "context_docs", "response_format")
        if getattr(request, k) not in (None, "structured")
    ]
    if _unwired:
        _DROPPED_FIELDS_LOGGER.warning(
            "oracle_universal: request fields %s provided but not forwarded "
            "to OracleService (see WAVE2_NOTES.md Q1)",
            _unwired,
        )
        # Sentry aggregation tag. No user data — only the field names we
        # already expose in the OpenAPI schema. `set_tag` is a no-op when
        # Sentry is not initialised (SENTRY_DSN unset or SKIP_SENTRY_INIT=1),
        # so it is safe to call unconditionally.
        sentry_sdk.set_tag("oracle.dropped_fields", ",".join(_unwired))

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
    except ValidationError as e:
        # Q2 (wave 2): a ValidationError here means the upstream service
        # returned a dict that does not match OracleQueryResponse. Without
        # this branch it was swallowed by the generic handler and looked
        # identical to a runtime error, hiding real service-schema drift.
        # Semantics are unchanged (still 200 + success=False) — only the
        # log line is elevated to WARN with an explicit tag so Sentry can
        # separate schema drift from transient service failures.
        logger.warning(
            "oracle_universal: OracleQueryResponse validation failed — "
            "upstream OracleService returned a dict that does not match "
            "the router contract. error=%s",
            e,
        )
        return OracleQueryResponse(
            success=False,
            query=request.query,
            error=f"response_validation_error: {e}",
            execution_time_ms=0,
            document_count=0,
        )
    except Exception as e:
        logger.error(f"❌ Oracle Router Error: {e}")
        logger.debug(traceback.format_exc())
        return OracleQueryResponse(
            success=False, query=request.query, error=str(e), execution_time_ms=0, document_count=0,
        )


@router.post("/feedback")
async def submit_user_feedback(feedback: FeedbackRequest) -> dict[str, Any]:
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
async def oracle_health_check() -> dict[str, Any]:
    """Health check for Oracle v5.3 services"""
    return {
        "status": "active",
        "service": "Oracle v5.3",
        "mode": "Refactored (Service Layer)",
        "timestamp": time.time(),
    }
