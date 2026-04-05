"""
Visa Oracle Router

Public API for the Visa Oracle product — anonymous visa recommendations,
contextual chat, and WhatsApp/Telegram handoff.

No authentication required (public product).
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.services.visa_oracle.visa_oracle_service import get_visa_oracle_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visa-oracle", tags=["visa-oracle"])

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RecommendRequest(BaseModel):
    nationality: str
    purpose: str
    duration: str
    family: str  # "yes" / "no" / "true" / "false" — parsed in endpoint


class RecommendResponse(BaseModel):
    success: bool
    visas: list[dict[str, Any]]
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    quiz_answers: dict | None = None
    conversation_history: list | None = None


class ChatResponse(BaseModel):
    success: bool
    answer: str
    confidence: str
    sources: list[str]
    session_id: str


class HandoffRequest(BaseModel):
    session_id: str
    quiz_answers: dict
    recommended_visas: list
    messages: list
    language: str | None = None


class HandoffResponse(BaseModel):
    success: bool
    whatsapp_url: str
    telegram_sent: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIDENCE_ABSTAIN = "ABSTAIN"
CONFIDENCE_CAUTIOUS = "CAUTIOUS"
CONFIDENCE_NORMAL = "NORMAL"

# Telegram chat ID for Damar / team lead notifications
TELEGRAM_LEAD_CHAT_ID = 1125336968

SYSTEM_PROMPT = (
    "You are an Indonesian visa specialist. "
    "Answer ONLY based on the context below. "
    "Never say 'you should' or 'you must'. "
    "Use 'typically requires', 'the standard process involves'."
)

HEDGING_PREFIX = (
    "Please note: the following information is based on available sources but "
    "may not be fully up-to-date. Verify with a qualified immigration specialist. "
    "\n\n"
)


def _compute_confidence(scores: list[float]) -> str:
    """Map reranker scores to a confidence label."""
    if not scores:
        return CONFIDENCE_ABSTAIN
    top = max(scores)
    if top < 0.15:
        return CONFIDENCE_ABSTAIN
    if top <= 0.60:
        return CONFIDENCE_CAUTIOUS
    return CONFIDENCE_NORMAL


def _parse_family(family_str: str) -> bool:
    return family_str.lower() in {"yes", "true", "1"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(request: Request, body: RecommendRequest) -> RecommendResponse:
    """
    Score and rank visa types for the given quiz answers.
    No LLM — pure scoring logic from VisaOracleService.
    """
    try:
        service = get_visa_oracle_service()
        family_bool = _parse_family(body.family)
        visas = service.recommend_visas(
            nationality=body.nationality,
            purpose=body.purpose,
            duration=body.duration,
            family=family_bool,
        )
        session_id = service.generate_session_id()

        logger.info(
            "visa-oracle /recommend: purpose=%s duration=%s family=%s → %d visas",
            body.purpose,
            body.duration,
            family_bool,
            len(visas),
        )
        return RecommendResponse(success=True, visas=visas, session_id=session_id)

    except Exception as exc:
        logger.error("visa-oracle /recommend error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Recommendation failed") from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Answer a visa question using the hybrid search pipeline + cross-encoder reranker.

    Confidence thresholds (from reranker scores):
      < 0.15  → ABSTAIN  (no answer generated)
      0.15-0.60 → CAUTIOUS (hedged answer via Gemini Flash)
      > 0.60  → NORMAL   (standard answer via Gemini Flash)
    """
    # Lazy imports — avoid loading heavy ML deps at startup
    from backend.llm.gemini_client import GeminiClient
    from backend.services.rag.hybrid_search import HybridSearchService
    from backend.services.rag.reranker import CrossEncoderReranker

    try:
        # Build an enriched query that includes quiz context
        quiz_ctx = ""
        if body.quiz_answers:
            nationality = body.quiz_answers.get("nationality", "")
            purpose = body.quiz_answers.get("purpose", "")
            duration = body.quiz_answers.get("duration", "")
            if any([nationality, purpose, duration]):
                quiz_ctx = (
                    f"[User context: nationality={nationality}, "
                    f"purpose={purpose}, duration={duration}] "
                )

        enriched_query = f"{quiz_ctx}{body.message}"

        # --- Hybrid search ---
        search_service = HybridSearchService()
        search_results = await search_service.search(
            query=enriched_query,
            collection="visa_oracle",
            limit=5,
        )

        if not search_results:
            logger.info("visa-oracle /chat: no results for session=%s", body.session_id[:12])
            return ChatResponse(
                success=True,
                answer=(
                    "I don't have specific information about that. "
                    "Please contact our team directly via WhatsApp for personalised advice."
                ),
                confidence=CONFIDENCE_ABSTAIN,
                sources=[],
                session_id=body.session_id,
            )

        # --- Cross-encoder reranking ---
        reranker = CrossEncoderReranker()
        reranked = await reranker.rerank(
            query=enriched_query,
            documents=search_results,
        )

        scores = [r.get("score", 0.0) for r in reranked]
        confidence = _compute_confidence(scores)

        if confidence == CONFIDENCE_ABSTAIN:
            logger.info(
                "visa-oracle /chat: ABSTAIN (top_score=%.3f) session=%s",
                max(scores, default=0.0),
                body.session_id[:12],
            )
            return ChatResponse(
                success=True,
                answer=(
                    "I couldn't find reliable information to answer that question. "
                    "Please contact our specialists directly via WhatsApp."
                ),
                confidence=CONFIDENCE_ABSTAIN,
                sources=[],
                session_id=body.session_id,
            )

        # --- Build context for LLM ---
        context_chunks = [r.get("content", r.get("text", "")) for r in reranked[:3]]
        context_str = "\n\n---\n\n".join(filter(None, context_chunks))
        sources = [
            r.get("source", r.get("metadata", {}).get("source", ""))
            for r in reranked[:3]
            if r.get("source") or r.get("metadata", {}).get("source")
        ]

        system = SYSTEM_PROMPT
        if confidence == CONFIDENCE_CAUTIOUS:
            system += (
                "\n\nIMPORTANT: Add a brief disclaimer that the user should verify "
                "the information with the Bali Zero team, as regulations may change."
            )

        prompt = (
            f"{system}\n\n"
            f"=== CONTEXT ===\n{context_str}\n\n"
            f"=== QUESTION ===\n{body.message}"
        )

        # --- Generate answer via Gemini Flash (30s timeout) ---
        gemini = GeminiClient()
        try:
            answer_text = await asyncio.wait_for(
                gemini.generate(prompt=prompt),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "visa-oracle /chat: Gemini timeout (30s) session=%s",
                body.session_id[:12],
            )
            return ChatResponse(
                success=True,
                answer=(
                    "Our AI is taking longer than usual to respond. "
                    "Please try again or contact us on WhatsApp for immediate assistance."
                ),
                confidence=CONFIDENCE_CAUTIOUS,
                sources=sources,
                session_id=body.session_id,
            )

        if confidence == CONFIDENCE_CAUTIOUS:
            answer_text = HEDGING_PREFIX + answer_text

        logger.info(
            "visa-oracle /chat: confidence=%s session=%s",
            confidence,
            body.session_id[:12],
        )

        return ChatResponse(
            success=True,
            answer=answer_text,
            confidence=confidence,
            sources=sources,
            session_id=body.session_id,
        )

    except Exception as exc:
        logger.error("visa-oracle /chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Chat failed") from exc


@router.post("/handoff", response_model=HandoffResponse)
async def handoff(request: Request, body: HandoffRequest) -> HandoffResponse:
    """
    Build WhatsApp deep-link URL and send Telegram lead notification.
    """
    from backend.services.integrations.telegram_bot_service import telegram_bot

    try:
        service = get_visa_oracle_service()

        # Build WhatsApp URL
        nationality = body.quiz_answers.get("nationality", "Unknown")
        purpose = body.quiz_answers.get("purpose", "Unknown")
        duration = body.quiz_answers.get("duration", "Unknown")

        top_visa = body.recommended_visas[0] if body.recommended_visas else {}
        visa_name = top_visa.get("visa_name", "Indonesian Visa")
        price = top_visa.get("price", "contact for pricing")

        whatsapp_url = service.build_whatsapp_message(
            nationality=nationality,
            purpose=purpose,
            duration=duration,
            visa_name=visa_name,
            price=price,
        )

        # Send Telegram notification
        telegram_sent = False
        try:
            language = body.language or "en"
            summary = service.build_telegram_summary(
                session_id=body.session_id,
                quiz_answers=body.quiz_answers,
                recommended_visas=body.recommended_visas,
                messages=body.messages,
                language=language,
            )
            await telegram_bot.send_message(
                chat_id=TELEGRAM_LEAD_CHAT_ID,
                text=summary,
                parse_mode="Markdown",
            )
            telegram_sent = True
            logger.info(
                "visa-oracle /handoff: Telegram notification sent, session=%s",
                body.session_id[:12],
            )
        except Exception as tg_exc:
            # Non-fatal — still return WhatsApp URL
            logger.warning(
                "visa-oracle /handoff: Telegram notification failed: %s", tg_exc
            )

        return HandoffResponse(
            success=True,
            whatsapp_url=whatsapp_url,
            telegram_sent=telegram_sent,
        )

    except Exception as exc:
        logger.error("visa-oracle /handoff error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Handoff failed") from exc


@router.get("/visa-types")
async def get_visa_types() -> dict[str, Any]:
    """
    Return all visa types — used by Next.js SSG at build time.
    """
    try:
        service = get_visa_oracle_service()
        visa_types = service.get_all_visa_types()
        return {"success": True, "visa_types": visa_types, "count": len(visa_types)}
    except Exception as exc:
        logger.error("visa-oracle /visa-types error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch visa types") from exc


@router.get("/visa-types/{code}")
async def get_visa_type_detail(code: str) -> dict[str, Any]:
    """
    Return detail for a single visa type by code (slug).
    """
    try:
        service = get_visa_oracle_service()
        all_types = service.get_all_visa_types()

        # Match by slug: lowercase, spaces → dashes
        code_lower = code.lower().strip()
        for vt in all_types:
            slug = vt["name"].lower().replace(" ", "-").replace("/", "-")
            if slug == code_lower or vt["name"].lower() == code_lower:
                return {"success": True, "visa_type": vt}

        raise HTTPException(status_code=404, detail=f"Visa type '{code}' not found")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("visa-oracle /visa-types/%s error: %s", code, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch visa type") from exc
