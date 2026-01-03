"""
Voice-Optimized RAG Endpoint

Fast, simple endpoint for voice assistants.
Skips complex agentic reasoning for speed.

Pipeline: Query → Vector Search → Fast LLM → Response (~5-8s instead of 40s)
"""

import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


async def verify_api_key(x_api_key: str | None = Header(None)) -> dict:
    """Verify API key for voice endpoint (service-to-service auth)."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    # Check against configured API keys
    valid_keys = [k.strip() for k in settings.api_keys.split(",") if k.strip()]
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return {"user_id": "voice-service", "role": "service"}

router = APIRouter(
    prefix="/api/voice",
    tags=["voice"],
    responses={404: {"description": "Not found"}},
)


class VoiceQueryRequest(BaseModel):
    """Simple voice query request."""
    query: str
    user_id: str | None = "voice-user"
    session_id: str | None = None
    conversation_history: list[dict] | None = None


class VoiceQueryResponse(BaseModel):
    """Fast voice response."""
    answer: str
    sources: list[str] = []
    execution_time: float


# Voice-optimized system prompt (short responses)
VOICE_SYSTEM_PROMPT = """You are Zantara, a friendly voice assistant for Indonesia immigration and business.

CRITICAL LANGUAGE RULE - ALWAYS FOLLOW:
- Italian query → respond ONLY in Italian
- English query → respond ONLY in English
- Indonesian query → respond ONLY in Indonesian
- NEVER mix languages. Match the user's language exactly.

Examples:
- "Ciao, come stai?" → "Ciao! Sto bene, grazie! Come posso aiutarti?"
- "Hello, how are you?" → "Hello! I'm doing great, thanks! How can I help you?"
- "Halo, apa kabar?" → "Halo! Baik, terima kasih! Ada yang bisa saya bantu?"

STYLE:
- Keep responses SHORT (2-3 sentences max)
- Be conversational and warm, like chatting with a friend
- If you don't know something, say so briefly in the user's language

Use the context below to answer. If no relevant context, say you don't have that information."""


async def get_search_service(request: Request):
    """Get search service from app state."""
    search_service = getattr(request.app.state, "search_service", None)
    if not search_service:
        raise HTTPException(status_code=503, detail="Search service not available")
    return search_service


async def generate_fast_response(
    query: str,
    context: str,
    conversation_history: list[dict] | None = None,
) -> str:
    """Generate response using fast LLM (GPT-4o-mini)."""
    import openai

    from app.core.config import settings

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    messages = [{"role": "system", "content": VOICE_SYSTEM_PROMPT}]

    # Add conversation history (last 6 messages max)
    if conversation_history:
        for msg in conversation_history[-6:]:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"][:500]  # Truncate long messages
                })

    # Add current query with context
    user_message = f"""Context from knowledge base:
{context[:2000]}

User question: {query}

Answer briefly (2-3 sentences):"""

    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast model
            messages=messages,
            max_tokens=200,  # Short responses
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return "Mi dispiace, non riesco a rispondere in questo momento."


@router.post("/query", response_model=VoiceQueryResponse)
async def voice_query(
    request: VoiceQueryRequest,
    http_request: Request,
    api_user: dict = Depends(verify_api_key),
    search_service = Depends(get_search_service),
):
    """
    Fast voice query endpoint.

    Optimized for speed:
    - Direct vector search (no agentic reasoning)
    - Fast LLM (GPT-4o-mini)
    - Short responses (2-3 sentences)

    Expected latency: 5-8 seconds (vs 40s for agentic)
    """
    start_time = time.time()

    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    logger.info(f"🎤 Voice query: '{request.query[:50]}...'")

    try:
        # Step 1: Fast vector search (no reranking, no conflict resolution)
        search_results = await search_service.search(
            query=request.query,
            user_level=2,  # Standard access
            limit=3,  # Fewer results for speed
            apply_filters=False,
        )

        # Step 2: Build context from results
        # Note: format_search_results() returns 'text' not 'content'
        context_parts = []
        sources = []
        for result in search_results.get("results", [])[:3]:
            text = result.get("text", "")
            if text:
                context_parts.append(text[:500])
                source = result.get("metadata", {}).get("source", "")
                if source and source not in sources:
                    sources.append(source)

        context = "\n\n".join(context_parts) if context_parts else "No relevant information found."

        # Step 3: Generate fast response
        answer = await generate_fast_response(
            query=request.query,
            context=context,
            conversation_history=request.conversation_history,
        )

        execution_time = time.time() - start_time
        logger.info(f"🎤 Voice response in {execution_time:.2f}s")

        return VoiceQueryResponse(
            answer=answer,
            sources=sources[:3],
            execution_time=execution_time,
        )

    except Exception as e:
        logger.error(f"Voice query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Voice query failed")


class ElevenLabsRequest(BaseModel):
    """ElevenLabs webhook request - flexible field names."""
    query: str | None = None
    question: str | None = None  # Alternative field name
    text: str | None = None  # Another alternative
    message: str | None = None  # Yet another

    def get_query(self) -> str:
        """Get query from any field."""
        return self.query or self.question or self.text or self.message or ""


from fastapi.responses import JSONResponse


@router.options("/elevenlabs")
async def elevenlabs_options():
    """CORS preflight for ElevenLabs webhook."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


@router.post("/elevenlabs")
async def elevenlabs_webhook(
    request: ElevenLabsRequest,
    http_request: Request,
    search_service = Depends(get_search_service),
):
    """
    ElevenLabs Conversational AI webhook.

    PUBLIC endpoint - no auth required for ElevenLabs to call.
    Returns: {"result": "text response"}
    """
    start_time = time.time()

    # Log raw request for debugging
    logger.info(f"🎤 ElevenLabs RAW request: {request.model_dump()}")

    query = request.get_query()
    if not query or not query.strip():
        return {"result": "Non ho capito la domanda. Puoi ripetere?"}

    logger.info(f"🎤 ElevenLabs query: '{query[:50]}...'")

    try:
        # Fast vector search
        search_results = await search_service.search(
            query=query,
            user_level=2,
            limit=3,
            apply_filters=False,
        )

        # Build context
        context_parts = []
        for result in search_results.get("results", [])[:3]:
            text = result.get("text", "")
            if text:
                context_parts.append(text[:500])

        context = "\n\n".join(context_parts) if context_parts else "No relevant information found."

        # Generate response
        answer = await generate_fast_response(
            query=query,
            context=context,
        )

        execution_time = time.time() - start_time
        logger.info(f"🎤 ElevenLabs response in {execution_time:.2f}s: {answer[:100]}...")

        # Return format that ElevenLabs can use as context
        return JSONResponse(
            content={"result": answer},
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logger.error(f"ElevenLabs query failed: {e}", exc_info=True)
        return JSONResponse(
            content={"result": "Mi dispiace, c'è stato un errore. Riprova tra poco."},
            headers={"Access-Control-Allow-Origin": "*"}
        )
