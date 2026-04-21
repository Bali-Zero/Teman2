"""
Visa Oracle Router

Public API for the Visa Oracle product — anonymous visa recommendations,
contextual chat, and WhatsApp/Telegram handoff.

No authentication required (public product).
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.dependencies import get_database_pool
from backend.services.common.background import spawn
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
    family: str  # "solo" / "spouse" / "children" / "spouse_children" — parsed in endpoint


class RecommendResponse(BaseModel):
    success: bool
    visas: list[dict[str, Any]]
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    quiz_answers: dict | None = None
    conversation_history: list | None = None
    language: str | None = None  # ISO 639-1 override from client; if set, wins over auto-detect
    check_hash: str | None = None  # NEW: wizard completion hash for context augmentation


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

# Obsolete visa codes (retired by PERMENKUMHAM 22/2023 visa reform).
# When a user asks about one of these, we expand the RAG query with the
# likely current replacement so embedding/BM25 can match the docs we do
# have, then the LLM applies the REGULATORY ACCURACY rule in
# SYSTEM_PROMPT to flag the code as obsolete and redirect.
#
# Mapping intent: obsolete_code -> (primary_replacement, context_hint)
OBSOLETE_VISA_CODES: dict[str, tuple[str, str]] = {
    # B211A/B211 were the multi-purpose visit visas (tourism + light
    # business). Post-reform the tourism replacement is C1 (Visa Wisata),
    # business is C2/C10. C1 is the most common single-intent swap.
    "B211A": ("C1", "C1 Visa Wisata tourism C2 business visit"),
    "B211": ("C1", "C1 Visa Wisata tourism C2 business visit"),
}


def _detect_obsolete_code(text: str) -> tuple[str, str] | None:
    """Return (obsolete_code, expansion_hint) if the message mentions a
    retired visa code that needs query expansion + regulatory flagging.
    Matches word-boundary (B211 won't match B2115 etc.)."""
    import re
    upper = text.upper()
    for code, (_replacement, hint) in OBSOLETE_VISA_CODES.items():
        if re.search(rf"\b{re.escape(code)}\b", upper):
            return code, hint
    return None

# Telegram chat ID for Damar / team lead notifications
TELEGRAM_LEAD_CHAT_ID = 1125336968

SYSTEM_PROMPT = (
    "You are Bali Zero's Indonesian visa specialist — a concrete, practical "
    "advisor for foreigners who want to live, work, or invest in Bali. "
    "You represent Bali Zero: a licensed local team that actually processes "
    "these visas for 5000+ clients every year. You are NOT a generic wiki. "
    "\n\n"
    "STYLE:\n"
    "- Be concrete and specific. Give real numbers (stay days, extension "
    "limits, fees) only when they're in the context.\n"
    "- Skip boilerplate like 'Based on the provided context'. Just answer.\n"
    "- Never say 'you should' or 'you must'. Use 'tipicamente richiede', "
    "'il processo standard prevede', 'typically requires', 'the standard "
    "process involves'.\n"
    "- Close with a concrete next step: suggest contacting Bali Zero via "
    "WhatsApp for the actual application, OR offer to check a specific "
    "scenario the user mentioned.\n"
    "- Answer ONLY based on the context below — if the context doesn't "
    "cover the question, say so briefly and redirect to the team.\n"
    "\n"
    "REGULATORY ACCURACY (critical):\n"
    "- **B211A is an OBSOLETE visa code** — retired by PERMENKUMHAM "
    "22/2023 as part of the 2023-2024 visa reform. B211A no longer "
    "exists in the current imigrasi.go.id catalog. If a user asks about "
    "B211A, DO NOT treat it as a valid alias for B1 or any other code. "
    "Instead: clarify that B211A was retired, then redirect based on "
    "intent. For TOURISM the current replacement is **C1 Visa Wisata** "
    "first (multi-entry, longer stay, most common); B1 (VoA) is a "
    "shorter-term fallback. For BUSINESS meetings: C10. For investment "
    "prep: D12 (Pra-Investasi). For work: E23/E33G. For long stay: "
    "E33/E33F/E33G/E28 family.\n"
    "- Other obsolete codes to flag similarly if mentioned: any 'B211'-prefixed "
    "code, old pre-2023 nomenclature.\n"
    "\n"
    "LANGUAGE: ALWAYS respond in the user's language (see language "
    "instruction below). Never mix languages in the same response."
)

# Localized hedging prefix — prepended when confidence = CAUTIOUS.
HEDGING_PREFIX_BY_LANG: dict[str, str] = {
    "en": (
        "Please note: the information below is based on available sources "
        "but may not be fully up-to-date. Verify with the Bali Zero team "
        "before acting.\n\n"
    ),
    "it": (
        "Nota: le informazioni che seguono si basano sulle fonti disponibili "
        "e potrebbero non essere del tutto aggiornate. Verifica con il team "
        "Bali Zero prima di procedere.\n\n"
    ),
    "id": (
        "Catatan: informasi berikut berdasarkan sumber yang tersedia dan "
        "mungkin belum sepenuhnya terbaru. Konfirmasi dengan tim Bali Zero "
        "sebelum bertindak.\n\n"
    ),
    "fr": (
        "Note : les informations ci-dessous sont basées sur les sources "
        "disponibles et peuvent ne pas être entièrement à jour. Vérifie avec "
        "l'équipe Bali Zero avant d'agir.\n\n"
    ),
    "es": (
        "Nota: la información a continuación se basa en fuentes disponibles "
        "y puede no estar totalmente actualizada. Verifica con el equipo "
        "Bali Zero antes de actuar.\n\n"
    ),
    "de": (
        "Hinweis: Die folgenden Informationen basieren auf verfügbaren "
        "Quellen und sind möglicherweise nicht vollständig aktuell. Prüfe "
        "mit dem Bali Zero Team, bevor du handelst.\n\n"
    ),
    "ru": (
        "Обратите внимание: информация ниже основана на доступных "
        "источниках и может быть не полностью актуальна. Уточните в "
        "команде Bali Zero перед действием.\n\n"
    ),
}

# Localized ABSTAIN fallback (top_score < 0.30 or no results — handoff to team)
ABSTAIN_FALLBACK_BY_LANG: dict[str, str] = {
    "en": (
        "I don't have reliable context to answer that specifically. "
        "Contact our Bali Zero team on WhatsApp (+62 821-3107-363) — "
        "we'll give you a tailored answer in minutes."
    ),
    "it": (
        "Non ho informazioni sufficienti per rispondere con precisione "
        "a questa domanda specifica. Scrivi al nostro team Bali Zero su "
        "WhatsApp (+62 821-3107-363) — ti rispondiamo in pochi minuti "
        "con una guida su misura."
    ),
    "id": (
        "Saya belum punya informasi spesifik untuk menjawab pertanyaan ini. "
        "Hubungi tim Bali Zero di WhatsApp (+62 821-3107-363) — kami akan "
        "memberi jawaban yang disesuaikan dalam beberapa menit."
    ),
    "fr": (
        "Je n'ai pas d'informations fiables pour répondre précisément à "
        "cette question. Contacte l'équipe Bali Zero sur WhatsApp "
        "(+62 821-3107-363) — réponse sur mesure en quelques minutes."
    ),
    "es": (
        "No tengo información suficiente para responder con precisión a "
        "esta pregunta. Escribe al equipo Bali Zero por WhatsApp "
        "(+62 821-3107-363) — te respondemos a medida en pocos minutos."
    ),
    "de": (
        "Ich habe keine zuverlässigen Informationen, um diese Frage "
        "präzise zu beantworten. Schreib dem Bali Zero Team auf WhatsApp "
        "(+62 821-3107-363) — maßgeschneiderte Antwort in wenigen Minuten."
    ),
    "ru": (
        "У меня нет достоверной информации, чтобы точно ответить на "
        "этот вопрос. Напишите в команду Bali Zero в WhatsApp "
        "(+62 821-3107-363) — индивидуальный ответ за несколько минут."
    ),
}

# Localized timeout fallback when Gemini takes >30s
TIMEOUT_FALLBACK_BY_LANG: dict[str, str] = {
    "en": (
        "Our AI is taking longer than usual. Please try again or contact "
        "us on WhatsApp (+62 821-3107-363) for immediate assistance."
    ),
    "it": (
        "La nostra AI sta impiegando più tempo del solito. Riprova oppure "
        "scrivici su WhatsApp (+62 821-3107-363) per assistenza immediata."
    ),
    "id": (
        "AI kami membutuhkan waktu lebih lama. Silakan coba lagi atau "
        "hubungi WhatsApp (+62 821-3107-363) untuk bantuan langsung."
    ),
    "fr": (
        "Notre IA prend plus de temps que d'habitude. Réessaie ou "
        "contacte-nous sur WhatsApp (+62 821-3107-363)."
    ),
    "es": (
        "Nuestra IA está tardando más de lo habitual. Inténtalo de nuevo o "
        "escríbenos por WhatsApp (+62 821-3107-363)."
    ),
    "de": (
        "Unsere KI braucht länger als üblich. Versuche es erneut oder "
        "schreib uns auf WhatsApp (+62 821-3107-363)."
    ),
    "ru": (
        "Наш ИИ отвечает дольше обычного. Повторите попытку или напишите "
        "нам в WhatsApp (+62 821-3107-363)."
    ),
}


def _parse_family(family_str: str) -> bool:
    """Parse family field: 'spouse', 'children', 'spouse_children' → True; 'solo' → False."""
    return family_str.lower() in {"spouse", "children", "spouse_children", "yes", "true", "1"}


def _detect_language(text: str) -> str:
    """Detect user language from message text using Unicode script ranges.

    Returns ISO 639-1 code. Defaults to 'en'.
    Covers the top Bali visitor demographics: Russian, Chinese, Korean,
    Japanese, Indonesian, and major European languages.
    """
    # Check by Unicode script (most reliable for non-Latin)
    for char in text:
        cp = ord(char)
        if 0x0400 <= cp <= 0x04FF:  # Cyrillic
            return "ru"
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:  # CJK
            return "zh"
        if 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF:  # Hangul
            return "ko"
        if (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF):  # Hiragana/Katakana
            return "ja"

    # Latin-script languages — keyword detection
    lower = text.lower()
    # Indonesian
    id_markers = {"saya", "apa", "bagaimana", "tolong", "bisa", "mau", "untuk", "visa"}
    if sum(1 for w in id_markers if f" {w} " in f" {lower} ") >= 2:
        return "id"
    # French — function words + common visa verbs. Avoid words shared with
    # Italian/Spanish ("visa", "pour" ambiguous).
    fr_markers = {
        "je", "mon", "comment", "bonjour", "merci", "besoin", "obtenir",
        "quel", "faire", "suis", "voudrais", "veux", "aller", "mes",
        "avec", "cette", "quelle", "prendre", "étape", "demande",
    }
    if sum(1 for w in fr_markers if f" {w} " in f" {lower} ") >= 2:
        return "fr"
    # Italian — function words + visa-chat common verbs.
    it_markers = {
        "il", "come", "posso", "vorrei", "quanto", "bisogno", "voglio",
        "vorrebbe", "cosa", "mio", "mia", "sono", "serve", "fare",
        "visto", "anni", "soggiorno", "lavorare", "aprire", "vivere",
        "turismo", "famiglia", "due", "tre", "meglio", "quale",
    }
    if sum(1 for w in it_markers if f" {w} " in f" {lower} ") >= 2:
        return "it"
    # German
    de_markers = {
        "ich", "wie", "brauche", "visum", "kann", "mein", "möchte",
        "für", "arbeit", "bali", "welches", "wohnen", "nach", "eine",
        "muss", "lang", "jahr",
    }
    if sum(1 for w in de_markers if f" {w} " in f" {lower} ") >= 2:
        return "de"
    # Spanish
    es_markers = {
        "necesito", "como", "puedo", "quiero", "abrir", "trabajar",
        "vivir", "cuanto", "cuánto", "años", "meses", "tengo",
        "para", "una", "que", "qué", "mi", "tener", "tiempo",
    }
    if sum(1 for w in es_markers if f" {w} " in f" {lower} ") >= 2:
        return "es"

    return "en"


async def _persist_session_create(
    db_pool: Any,
    session_id: str,
    quiz_answers: dict[str, Any],
    recommended_visas: list[dict[str, Any]],
    ip_hash: str,
) -> None:
    """Insert a new session row. Non-fatal — failures are logged, not raised."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO visa_oracle_sessions
                    (session_id, quiz_answers, recommended_visas, ip_hash)
                VALUES ($1, $2::jsonb, $3::jsonb, $4)
                """,
                session_id,
                json.dumps(quiz_answers),
                json.dumps(recommended_visas),
                ip_hash,
            )
    except Exception as exc:
        logger.warning("visa-oracle session persist (create) failed: %s", exc)


async def _persist_session_append_message(
    db_pool: Any,
    session_id: str,
    role: str,
    content: str,
) -> None:
    """Append a chat message to an existing session. Non-fatal."""
    try:
        msg = json.dumps({"role": role, "content": content[:500]})
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE visa_oracle_sessions
                SET messages = messages || $2::jsonb
                WHERE session_id = $1
                """,
                session_id,
                f"[{msg}]",
            )
    except Exception as exc:
        logger.warning("visa-oracle session persist (message) failed: %s", exc)


async def _persist_session_handoff(db_pool: Any, session_id: str) -> None:
    """Mark handoff_triggered = TRUE. Non-fatal."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE visa_oracle_sessions
                SET handoff_triggered = TRUE
                WHERE session_id = $1
                """,
                session_id,
            )
    except Exception as exc:
        logger.warning("visa-oracle session persist (handoff) failed: %s", exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(
    request: Request, body: RecommendRequest, db_pool=Depends(get_database_pool),
) -> RecommendResponse:
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
        # Persist session non-blocking
        ip_hash = service.hash_ip(request.client.host if request.client else "unknown")
        spawn(
            _persist_session_create(
                db_pool, session_id, body.model_dump(), visas, ip_hash,
            )
        )

        return RecommendResponse(success=True, visas=visas, session_id=session_id)

    except Exception as exc:
        logger.error("visa-oracle /recommend error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Recommendation failed") from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request, body: ChatRequest, db_pool=Depends(get_database_pool),
) -> ChatResponse:
    """
    Answer a visa question using the hybrid search pipeline.

    Confidence thresholds (vector similarity scores, no cross-encoder on Fly):
      < 0.30  → ABSTAIN  (no answer generated, WhatsApp handoff)
      0.30-0.55 → CAUTIOUS (hedged answer via Gemini Flash)
      > 0.55  → NORMAL   (standard answer via Gemini Flash)
    """
    # Lazy imports — avoid loading heavy ML deps at startup
    from backend.llm.genai_client import get_genai_client
    from backend.services.rag.hybrid_search import HybridSearchService

    # Resolve response language early so every fallback branch (no results,
    # ABSTAIN, timeout, CAUTIOUS hedging) uses the user's language, not the
    # wrong default.
    #
    # Priority: message auto-detect > body.language (browser) > English default.
    #
    # Rationale: "message wins" — if a user deliberately writes in Spanish on
    # a browser configured in English (or any other), the act of writing is a
    # stronger language signal than navigator.language. Browser locale is the
    # fallback when detection is inconclusive. Default is English because Bali
    # Zero serves a foreign / international audience; the site is in English.
    _lang_names = {
        "ru": "Russian", "zh": "Chinese", "ko": "Korean", "ja": "Japanese",
        "id": "Indonesian", "fr": "French", "it": "Italian", "de": "German",
        "es": "Spanish", "en": "English",
    }
    _detected = _detect_language(body.message)
    _browser_lang = (body.language or "").strip().lower()[:2]
    if _detected in _lang_names and _detected != "en":
        # Detector is confident about a non-English language (script or
        # keyword-rich). Trust it.
        response_lang = _detected
    elif _browser_lang in _lang_names:
        # Detector returned "en" (its default when no strong markers found)
        # or an unknown code. Use browser locale as the more reliable hint.
        response_lang = _browser_lang
    else:
        # No signal at all — English default (international audience).
        response_lang = "en"

    # --- Wizard-context branch (Task 3, spec 2026-04-21-visa-funnel-fusion) ---
    # When the caller posts a check_hash (completed wizard), we require an
    # Authorization: Bearer <jwt> header signed by settings.jwt_secret_key with
    # sub=check_hash and type="visa_funnel". On success, we load the wizard
    # context from visa_checks and prepend a ground-truth preamble to the
    # system prompt so the LLM cannot contradict the wizard or invent prices.
    # Backwards compatible: when check_hash is absent, validation is skipped.
    system_prompt_prefix = ""
    if body.check_hash:
        from jose import JWTError, jwt as _jose_jwt
        from backend.app.core.config import settings as _settings
        from backend.services.visa_unified.bridge import (
            augment_chat_system_prompt as _augment,
            get_funnel_context as _get_ctx,
        )

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = auth.split(" ", 1)[1].strip()
        try:
            claims = _jose_jwt.decode(
                token, _settings.jwt_secret_key,
                algorithms=[_settings.jwt_algorithm],
                options={"verify_exp": True},
            )
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        if claims.get("type") != "visa_funnel":
            raise HTTPException(status_code=401, detail="Wrong token type")
        if claims.get("sub") != body.check_hash:
            raise HTTPException(status_code=403, detail="Token does not match check_hash")

        ctx = await _get_ctx(body.check_hash, db_pool)
        if ctx is None:
            raise HTTPException(status_code=410, detail="Wizard context expired")

        # Build the prefix. augment_chat_system_prompt prepends its text to a
        # base prompt; we pass empty "" so we get only the preamble, which we
        # then stitch to SYSTEM_PROMPT at the usual line.
        system_prompt_prefix = _augment(ctx, "")

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

        # Include recent conversation history for context
        history_ctx = ""
        if body.conversation_history:
            recent = body.conversation_history[-4:]  # Last 2 exchanges
            history_lines = []
            for msg in recent:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    history_lines.append(f"{role}: {content[:200]}")
            if history_lines:
                history_ctx = "[Previous conversation:\n" + "\n".join(history_lines) + "]\n\n"

        # Detect obsolete visa codes (B211A etc). If present, expand the
        # RAG query with hints toward the current replacement so we match
        # something relevant in the KB. Also force CAUTIOUS min-confidence
        # downstream: we have enough pretraining knowledge + SYSTEM_PROMPT
        # guidance to correct the code mention, even if the KB top_score
        # is weak (KB is thin on ex-codes precisely because they no longer
        # exist).
        obsolete_hit = _detect_obsolete_code(body.message)
        if obsolete_hit:
            code, hint = obsolete_hit
            enriched_query = f"{quiz_ctx}{body.message} {hint}"
            logger.info(
                "visa-oracle /chat: obsolete code %s detected, expanded query session=%s",
                code,
                body.session_id[:12],
            )
        else:
            enriched_query = f"{quiz_ctx}{body.message}"

        # --- Hybrid search ---
        search_service = HybridSearchService()
        raw = await search_service.search_hybrid(
            query=enriched_query,
            collection="visa_oracle",
            limit=5,
            alpha=0.5,
        )
        search_results: list[dict[str, Any]] = raw.get("results", [])

        if not search_results:
            logger.info("visa-oracle /chat: no results for session=%s", body.session_id[:12])
            return ChatResponse(
                success=True,
                answer=ABSTAIN_FALLBACK_BY_LANG.get(
                    response_lang, ABSTAIN_FALLBACK_BY_LANG["en"]
                ),
                confidence=CONFIDENCE_ABSTAIN,
                sources=[],
                session_id=body.session_id,
            )

        # --- Use vector similarity scores directly (cross-encoder not available on Fly) ---
        # Vector scores from Qdrant hybrid search are typically 0.3-0.9 for good matches.
        # Thresholds adjusted accordingly: <0.30 ABSTAIN, 0.30-0.55 CAUTIOUS, >0.55 NORMAL.
        top_docs = search_results[:5]
        scores = [r.get("score", r.get("vector_score", 0.0)) for r in top_docs]
        top_score = max(scores, default=0.0)

        if top_score < 0.30:
            confidence = CONFIDENCE_ABSTAIN
        elif top_score <= 0.55:
            confidence = CONFIDENCE_CAUTIOUS
        else:
            confidence = CONFIDENCE_NORMAL

        # If the user mentioned an obsolete code, DON'T ABSTAIN even with weak
        # scores. We have enough pretraining context + SYSTEM_PROMPT rules to
        # correctly flag the code as obsolete and redirect. Promote to CAUTIOUS
        # so the hedging prefix is emitted too.
        if obsolete_hit and confidence == CONFIDENCE_ABSTAIN:
            confidence = CONFIDENCE_CAUTIOUS
            logger.info(
                "visa-oracle /chat: promoted ABSTAIN→CAUTIOUS due to obsolete "
                "code %s (top_score=%.3f) session=%s",
                obsolete_hit[0],
                top_score,
                body.session_id[:12],
            )

        if confidence == CONFIDENCE_ABSTAIN:
            logger.info(
                "visa-oracle /chat: ABSTAIN (top_score=%.3f) session=%s",
                top_score,
                body.session_id[:12],
            )
            return ChatResponse(
                success=True,
                answer=ABSTAIN_FALLBACK_BY_LANG.get(
                    response_lang, ABSTAIN_FALLBACK_BY_LANG["en"]
                ),
                confidence=CONFIDENCE_ABSTAIN,
                sources=[],
                session_id=body.session_id,
            )

        # --- Build context for LLM ---
        context_chunks = [r.get("content", r.get("text", "")) for r in top_docs[:3]]
        context_str = "\n\n---\n\n".join(filter(None, context_chunks))
        sources = [
            r.get("source", r.get("metadata", {}).get("source", ""))
            for r in top_docs[:3]
            if r.get("source") or r.get("metadata", {}).get("source")
        ]

        system = system_prompt_prefix + SYSTEM_PROMPT
        if confidence == CONFIDENCE_CAUTIOUS:
            system += (
                "\n\nIMPORTANT: Add a brief disclaimer that the user should verify "
                "the information with the Bali Zero team, as regulations may change."
            )

        # response_lang already resolved at handler entry. Inject lang instruction.
        lang_name = _lang_names[response_lang]
        system += (
            f"\n\nIMPORTANT: Respond in {lang_name}. The entire answer, "
            f"including section headings and labels, must be in {lang_name}. "
            "Never respond in English when the user's language is different."
        )

        prompt = (
            f"{system}\n\n"
            f"=== CONTEXT ===\n{context_str}\n\n"
            f"{history_ctx}"
            f"=== QUESTION ===\n{body.message}"
        )

        # --- Generate answer via Gemini Flash (30s timeout) ---
        gemini = get_genai_client()
        try:
            result = await asyncio.wait_for(
                gemini.generate_content(
                    contents=prompt,
                    max_output_tokens=1024,
                    temperature=0.3,
                ),
                timeout=30.0,
            )
            answer_text = result.get("text", "") if isinstance(result, dict) else str(result)
        except asyncio.TimeoutError:
            logger.warning(
                "visa-oracle /chat: Gemini timeout (30s) session=%s",
                body.session_id[:12],
            )
            return ChatResponse(
                success=True,
                answer=TIMEOUT_FALLBACK_BY_LANG.get(
                    response_lang, TIMEOUT_FALLBACK_BY_LANG["en"]
                ),
                confidence=CONFIDENCE_CAUTIOUS,
                sources=sources,
                session_id=body.session_id,
            )

        if confidence == CONFIDENCE_CAUTIOUS:
            answer_text = (
                HEDGING_PREFIX_BY_LANG.get(
                    response_lang, HEDGING_PREFIX_BY_LANG["en"]
                )
                + answer_text
            )

        logger.info(
            "visa-oracle /chat: confidence=%s session=%s",
            confidence,
            body.session_id[:12],
        )

        # Persist Q&A non-blocking
        spawn(
            _persist_session_append_message(db_pool, body.session_id, "user", body.message)
        )
        spawn(
            _persist_session_append_message(db_pool, body.session_id, "assistant", answer_text)
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
async def handoff(
    request: Request, body: HandoffRequest, db_pool=Depends(get_database_pool),
) -> HandoffResponse:
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

        # Send Telegram notification — skip empty/unknown leads
        telegram_sent = False
        qa = body.quiz_answers or {}
        has_real_data = any(
            qa.get(k) and qa.get(k) != "Unknown"
            for k in ("nationality", "purpose", "duration")
        ) or bool(body.recommended_visas)
        try:
            if not has_real_data:
                logger.info(
                    "visa-oracle /handoff: skipping Telegram — no real quiz data, session=%s",
                    body.session_id[:12],
                )
            else:
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

        # Mark handoff in session non-blocking
        spawn(_persist_session_handoff(db_pool, body.session_id))

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
