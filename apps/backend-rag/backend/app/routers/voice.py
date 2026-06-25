"""
Voice-Optimized RAG Endpoint

Fast, simple endpoint for voice assistants.
Skips complex agentic reasoning for speed.

Pipeline: Query → Vector Search → Fast LLM → Response (~5-8s instead of 40s)
"""

import asyncio
import logging
import socket
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.datastructures import UploadFile

from backend.app.core.config import settings
from backend.app.services.local_audio import (
    LOCAL_ONLY_PROVIDER_POLICY,
    LocalSTTProvider,
    LocalTTSProvider,
    ProviderStatus,
)
from backend.app.services.local_audio.chatterbox import ChatterboxTTSProvider
from backend.app.services.local_audio.runtime_checks import is_approved_voice_runtime_host
from backend.app.services.local_audio.silero_vad import SileroVADProvider
from backend.app.services.local_audio.whisper_cpp import WhisperCppSTTProvider

logger = logging.getLogger(__name__)

_ALLOWED_LOCAL_AUDIO_CONTENT_TYPES = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}
_REQUIRED_LOCAL_AUDIO_PROVIDER_KEYS = ("stt", "vad", "tts")
_REQUIRED_LOCAL_AUDIO_ROUNDTRIP_PROVIDER_KEYS = ("stt", "tts")
_TTS_PROFILE_HIGH_QUALITY = "high_quality_offline"
_TTS_PROFILE_BROWSER_REALTIME = "browser_realtime"
_TTS_PROFILE_ALIASES = {
    "high-quality": _TTS_PROFILE_HIGH_QUALITY,
    "high-quality-offline": _TTS_PROFILE_HIGH_QUALITY,
    "high_quality": _TTS_PROFILE_HIGH_QUALITY,
    "high_quality_offline": _TTS_PROFILE_HIGH_QUALITY,
    "offline": _TTS_PROFILE_HIGH_QUALITY,
    "browser-realtime": _TTS_PROFILE_BROWSER_REALTIME,
    "browser_realtime": _TTS_PROFILE_BROWSER_REALTIME,
    "realtime": _TTS_PROFILE_BROWSER_REALTIME,
}


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


class LocalAudioPolicyResponse(BaseModel):
    """Policy exposed for local audio providers."""

    requires_network: bool
    allows_cloud_fallback: bool
    pii_boundary: str


class LocalAudioProviderResponse(BaseModel):
    """Sanitized local audio provider status."""

    name: str
    available: bool
    detail: str
    policy: LocalAudioPolicyResponse


class LocalAudioTTSProfileEntry(BaseModel):
    """Operational metadata for one TTS profile."""

    profile: str
    provider: str
    quality: str
    latency_class: str
    available: bool
    detail: str
    policy: LocalAudioPolicyResponse


class LocalAudioTTSProfileResponse(BaseModel):
    """Active TTS profile and fallback policy for local audio."""

    active_profile: str
    active_provider: str
    quality: str
    latency_class: str
    fallback_policy: str
    profiles: dict[str, LocalAudioTTSProfileEntry]


class LocalAudioStatusResponse(BaseModel):
    """Local audio stack readiness for the voice concierge lab."""

    enabled: bool
    ready: bool
    roundtrip_ready: bool
    turn_detection_ready: bool
    providers: dict[str, LocalAudioProviderResponse]
    tts_profile: LocalAudioTTSProfileResponse
    constraints: list[str]


class LocalAudioTranscribeResponse(BaseModel):
    """Sanitized local STT response for the voice concierge lab."""

    text: str
    language: str | None
    duration_seconds: float | None
    provider: str
    constraints: list[str]


class LocalAudioSynthesizeRequest(BaseModel):
    """Local TTS request for the voice concierge lab."""

    text: str
    voice: str | None = None
    language: str | None = None


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


def _disabled_provider_status(name: str) -> ProviderStatus:
    return ProviderStatus(
        name=name,
        available=False,
        detail="local audio disabled",
        policy=LOCAL_ONLY_PROVIDER_POLICY,
    )


def _local_audio_enabled() -> bool:
    return settings.voice_concierge_local_audio_enabled or settings.voice_concierge_local_audio


def _local_audio_runtime_host_allowed() -> bool:
    return is_approved_voice_runtime_host(socket.gethostname())


def _ensure_local_audio_runtime_host() -> None:
    if not _local_audio_runtime_host_allowed():
        raise HTTPException(
            status_code=503,
            detail="local audio runtime host not approved",
        )


def _whisper_status() -> ProviderStatus:
    binary = settings.voice_concierge_whisper_binary
    model = settings.voice_concierge_whisper_model
    if not binary or not model:
        return ProviderStatus(
            name=WhisperCppSTTProvider.name,
            available=False,
            detail="binary or model not configured",
            policy=LOCAL_ONLY_PROVIDER_POLICY,
        )

    return WhisperCppSTTProvider(
        binary_path=Path(binary),
        model_path=Path(model),
        timeout_seconds=settings.voice_concierge_whisper_timeout_seconds,
    ).status()


def get_local_stt_provider() -> LocalSTTProvider:
    """Build the configured local STT provider."""
    binary = settings.voice_concierge_whisper_binary
    model = settings.voice_concierge_whisper_model
    if not binary or not model:
        raise HTTPException(status_code=503, detail="local STT provider unavailable")
    return WhisperCppSTTProvider(
        binary_path=Path(binary),
        model_path=Path(model),
        timeout_seconds=settings.voice_concierge_whisper_timeout_seconds,
    )


def get_local_stt_provider_factory() -> Callable[[], LocalSTTProvider]:
    """Return a provider factory so route guards run before provider construction."""
    return get_local_stt_provider


def get_local_tts_provider() -> LocalTTSProvider:
    """Build the configured local TTS provider."""
    model_path = settings.voice_concierge_chatterbox_model_path
    return ChatterboxTTSProvider(
        module_name=settings.voice_concierge_chatterbox_module,
        model_path=Path(model_path) if model_path else None,
        t3_model=settings.voice_concierge_chatterbox_t3_model,
        language_id=settings.voice_concierge_chatterbox_language,
        timeout_seconds=settings.voice_concierge_chatterbox_timeout_seconds,
    )


def get_local_tts_provider_factory() -> Callable[[], LocalTTSProvider]:
    """Return a provider factory so route guards run before provider construction."""
    return get_local_tts_provider


def _normalize_tts_profile(raw_value: str | None) -> str:
    value = (raw_value or "").strip().lower().replace(" ", "_")
    return _TTS_PROFILE_ALIASES.get(value, _TTS_PROFILE_HIGH_QUALITY)


def _active_tts_profile() -> str:
    return _normalize_tts_profile(settings.voice_concierge_tts_profile)


def _policy_response() -> LocalAudioPolicyResponse:
    policy = LOCAL_ONLY_PROVIDER_POLICY
    return LocalAudioPolicyResponse(
        requires_network=policy.requires_network,
        allows_cloud_fallback=policy.allows_cloud_fallback,
        pii_boundary=policy.pii_boundary,
    )


def _sanitize_provider_status(status: ProviderStatus) -> LocalAudioProviderResponse:
    detail = status.detail
    if status.name == WhisperCppSTTProvider.name and ":" in detail:
        detail = detail.split(":", 1)[0]
    return LocalAudioProviderResponse(
        name=status.name,
        available=status.available,
        detail=detail,
        policy=LocalAudioPolicyResponse(
            requires_network=status.policy.requires_network,
            allows_cloud_fallback=status.policy.allows_cloud_fallback,
            pii_boundary=status.policy.pii_boundary,
        ),
    )


def _tts_profile_response(
    *,
    active_profile: str,
    chatterbox_status: LocalAudioProviderResponse,
) -> LocalAudioTTSProfileResponse:
    realtime_provider = settings.voice_concierge_realtime_tts_provider or "browser-web-speech-local"
    profiles = {
        _TTS_PROFILE_HIGH_QUALITY: LocalAudioTTSProfileEntry(
            profile=_TTS_PROFILE_HIGH_QUALITY,
            provider=chatterbox_status.name,
            quality="high_quality",
            latency_class="offline",
            available=chatterbox_status.available,
            detail=chatterbox_status.detail,
            policy=chatterbox_status.policy,
        ),
        _TTS_PROFILE_BROWSER_REALTIME: LocalAudioTTSProfileEntry(
            profile=_TTS_PROFILE_BROWSER_REALTIME,
            provider=realtime_provider,
            quality="realtime",
            latency_class="interactive",
            available=False,
            detail="client must confirm a browser localService voice",
            policy=_policy_response(),
        ),
    }
    active = profiles[active_profile]
    return LocalAudioTTSProfileResponse(
        active_profile=active.profile,
        active_provider=active.provider,
        quality=active.quality,
        latency_class=active.latency_class,
        fallback_policy="fail_closed",
        profiles=profiles,
    )


def _is_local_only_provider_ready(provider: LocalAudioProviderResponse) -> bool:
    return (
        provider.available
        and not provider.policy.requires_network
        and not provider.policy.allows_cloud_fallback
        and provider.policy.pii_boundary == "local_only"
    )


def get_local_audio_status() -> LocalAudioStatusResponse:
    """Return sanitized local-only audio stack readiness."""
    enabled = _local_audio_enabled()
    constraints = [
        "local_only",
        "no_cloud_audio_fallback",
        "no_raw_audio_persistence",
        "no_pii",
        "ready_requires_stt_vad_tts",
    ]
    if not enabled:
        statuses = {
            "stt": _disabled_provider_status(WhisperCppSTTProvider.name),
            "vad": _disabled_provider_status(SileroVADProvider.name),
            "tts": _disabled_provider_status(ChatterboxTTSProvider.name),
        }
    else:
        statuses = {
            "stt": _whisper_status(),
            "vad": SileroVADProvider(
                module_name=settings.voice_concierge_silero_module,
                sampling_rate=settings.voice_concierge_silero_sampling_rate,
                threshold=settings.voice_concierge_silero_threshold,
                timeout_seconds=settings.voice_concierge_silero_timeout_seconds,
            ).status(),
            "tts": ChatterboxTTSProvider(
                module_name=settings.voice_concierge_chatterbox_module,
                model_path=Path(settings.voice_concierge_chatterbox_model_path)
                if settings.voice_concierge_chatterbox_model_path
                else None,
                t3_model=settings.voice_concierge_chatterbox_t3_model,
                language_id=settings.voice_concierge_chatterbox_language,
                timeout_seconds=settings.voice_concierge_chatterbox_timeout_seconds,
            ).status(),
        }

    providers = {key: _sanitize_provider_status(value) for key, value in statuses.items()}
    active_tts_profile = _active_tts_profile()
    tts_profile = _tts_profile_response(
        active_profile=active_tts_profile,
        chatterbox_status=providers["tts"],
    )
    roundtrip_ready = enabled and all(
        _is_local_only_provider_ready(providers[key])
        for key in _REQUIRED_LOCAL_AUDIO_ROUNDTRIP_PROVIDER_KEYS
    )
    turn_detection_ready = enabled and _is_local_only_provider_ready(providers["vad"])
    ready = enabled and all(
        _is_local_only_provider_ready(providers[key]) for key in _REQUIRED_LOCAL_AUDIO_PROVIDER_KEYS
    )
    return LocalAudioStatusResponse(
        enabled=enabled,
        ready=ready,
        roundtrip_ready=roundtrip_ready,
        turn_detection_ready=turn_detection_ready,
        providers=providers,
        tts_profile=tts_profile,
        constraints=constraints,
    )


def _validate_local_stt_provider(provider: LocalSTTProvider) -> None:
    status = provider.status()
    if not status.available:
        raise HTTPException(status_code=503, detail="local STT provider unavailable")
    policy = status.policy
    if (
        policy.requires_network
        or policy.allows_cloud_fallback
        or policy.pii_boundary != "local_only"
    ):
        raise HTTPException(
            status_code=503,
            detail="local STT provider violates local-only policy",
        )


def _validate_local_tts_provider(provider: LocalTTSProvider) -> None:
    status = provider.status()
    if not status.available:
        raise HTTPException(status_code=503, detail="local TTS provider unavailable")
    policy = status.policy
    if (
        policy.requires_network
        or policy.allows_cloud_fallback
        or policy.pii_boundary != "local_only"
    ):
        raise HTTPException(
            status_code=503,
            detail="local TTS provider violates local-only policy",
        )


def _validate_tts_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    if len(text) > settings.voice_concierge_tts_max_chars:
        raise HTTPException(status_code=413, detail="text payload too large")
    return text


def _validate_tts_audio_size(size_bytes: int) -> None:
    if size_bytes > settings.voice_concierge_tts_audio_max_bytes:
        raise HTTPException(status_code=413, detail="audio payload too large")


async def _read_bounded_audio(file: UploadFile) -> bytes:
    max_bytes = settings.voice_concierge_audio_max_bytes
    payload = await file.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise HTTPException(status_code=413, detail="audio payload too large")
    if not payload:
        raise HTTPException(status_code=422, detail="audio payload is empty")
    return payload


def _content_type_media_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _audio_suffix_for_content_type(content_type: str | None) -> str | None:
    return _ALLOWED_LOCAL_AUDIO_CONTENT_TYPES.get(
        _content_type_media_type(content_type),
    )


def _reject_declared_oversized_request(request: Request) -> None:
    raw_content_length = request.headers.get("content-length")
    if not raw_content_length:
        raise HTTPException(status_code=411, detail="content length required")
    try:
        content_length = int(raw_content_length)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid content length") from None
    if content_length < 0:
        raise HTTPException(status_code=400, detail="invalid content length")

    multipart_overhead_allowance = 64 * 1024
    if content_length > settings.voice_concierge_audio_max_bytes + multipart_overhead_allowance:
        raise HTTPException(status_code=413, detail="audio payload too large")


async def _extract_single_audio_payload(
    request: Request,
) -> tuple[bytes, str | None, str]:
    if not _content_type_media_type(request.headers.get("content-type")).startswith(
        "multipart/form-data",
    ):
        raise HTTPException(status_code=400, detail="multipart audio upload required")

    try:
        form = await request.form(
            max_files=1,
            max_fields=1,
            max_part_size=settings.voice_concierge_audio_max_bytes,
        )
    except Exception as exc:
        logger.warning("Rejected malformed local audio multipart: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="exactly one audio file is required",
        ) from exc

    try:
        uploads = [
            (key, value) for key, value in form.multi_items() if isinstance(value, UploadFile)
        ]
        if len(uploads) != 1 or uploads[0][0] != "file":
            raise HTTPException(
                status_code=400,
                detail="exactly one audio file is required",
            )

        file = uploads[0][1]
        suffix = _audio_suffix_for_content_type(file.content_type)
        if suffix is None:
            raise HTTPException(status_code=415, detail="unsupported audio content type")

        language_value = form.get("language")
        language = language_value.strip() if isinstance(language_value, str) else None
        return await _read_bounded_audio(file), language or None, suffix
    finally:
        await form.close()


async def get_search_service(request: Request) -> Any:
    """Get search service from app state."""
    search_service = getattr(request.app.state, "search_service", None)
    if not search_service:
        raise HTTPException(status_code=503, detail="Search service not available")
    return search_service


@router.get("/local-audio/status", response_model=LocalAudioStatusResponse)
async def local_audio_status(
    _auth: dict = Depends(verify_api_key),
) -> LocalAudioStatusResponse:
    """Return sanitized local audio stack readiness."""
    if _local_audio_enabled():
        _ensure_local_audio_runtime_host()
    return get_local_audio_status()


@router.post(
    "/local-audio/transcribe",
    response_model=LocalAudioTranscribeResponse,
)
async def local_audio_transcribe(
    request: Request,
    _auth: dict = Depends(verify_api_key),
    provider_factory: Callable[[], LocalSTTProvider] = Depends(
        get_local_stt_provider_factory,
    ),
) -> LocalAudioTranscribeResponse:
    """Transcribe one local audio upload without persisting raw audio."""
    if not _local_audio_enabled():
        raise HTTPException(status_code=503, detail="local audio disabled")
    _ensure_local_audio_runtime_host()

    _reject_declared_oversized_request(request)
    provider = provider_factory()
    _validate_local_stt_provider(provider)

    payload, language, suffix = await _extract_single_audio_payload(request)

    try:
        with tempfile.TemporaryDirectory(prefix="voice-concierge-") as tmpdir:
            audio_path = Path(tmpdir) / f"voice-concierge-upload{suffix}"
            await asyncio.to_thread(audio_path.write_bytes, payload)
            result = await provider.transcribe(audio_path, language=language)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Local STT transcription failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="local STT transcription failed",
        ) from exc

    return LocalAudioTranscribeResponse(
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
        provider=result.provider,
        constraints=[
            "local_only",
            "no_cloud_audio_fallback",
            "no_raw_audio_persistence",
        ],
    )


@router.post("/local-audio/synthesize")
async def local_audio_synthesize(
    request: LocalAudioSynthesizeRequest,
    _auth: dict = Depends(verify_api_key),
    provider_factory: Callable[[], LocalTTSProvider] = Depends(
        get_local_tts_provider_factory,
    ),
) -> Response:
    """Synthesize local speech without persisting generated audio."""
    if not _local_audio_enabled():
        raise HTTPException(status_code=503, detail="local audio disabled")
    if _active_tts_profile() == _TTS_PROFILE_BROWSER_REALTIME:
        raise HTTPException(
            status_code=503,
            detail="backend TTS disabled for realtime browser profile",
        )
    _ensure_local_audio_runtime_host()

    text = _validate_tts_text(request.text)
    provider = provider_factory()
    _validate_local_tts_provider(provider)

    try:
        with tempfile.TemporaryDirectory(prefix="voice-concierge-tts-") as tmpdir:
            output_path = Path(tmpdir) / "voice-concierge-output.wav"
            result = await provider.synthesize(
                text,
                voice=request.voice or request.language,
                output_path=output_path,
            )
            if not result.mime_type.startswith("audio/"):
                raise RuntimeError("local TTS provider returned non-audio content")
            if result.audio_bytes is not None:
                _validate_tts_audio_size(len(result.audio_bytes))
                payload = result.audio_bytes
            elif result.audio_path is not None:
                output_size = await asyncio.to_thread(lambda: result.audio_path.stat().st_size)
                _validate_tts_audio_size(output_size)
                payload = await asyncio.to_thread(result.audio_path.read_bytes)
                _validate_tts_audio_size(len(payload))
            else:
                raise RuntimeError("local TTS provider returned no audio")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Local TTS synthesis failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="local TTS synthesis failed",
        ) from exc

    return Response(
        content=payload,
        media_type=result.mime_type,
        headers={
            "X-Voice-Provider": result.provider,
            "X-Voice-Constraints": ("local_only,no_cloud_audio_fallback,no_raw_audio_persistence"),
        },
    )


async def generate_fast_response(
    query: str,
    context: str,
    conversation_history: list[dict] | None = None,
) -> str:
    """Generate response using fast LLM (GPT-4o-mini)."""
    import openai

    from backend.app.core.config import settings

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    messages = [{"role": "system", "content": VOICE_SYSTEM_PROMPT}]

    # Add conversation history (last 6 messages max)
    if conversation_history:
        for msg in conversation_history[-6:]:
            if msg.get("role") in ["user", "assistant"]:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"][:500],  # Truncate long messages
                    },
                )

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
        logger.error("LLM generation failed: %s", e)
        return "Mi dispiace, non riesco a rispondere in questo momento."


@router.post("/query", response_model=VoiceQueryResponse)
async def voice_query(
    request: VoiceQueryRequest,
    search_service=Depends(get_search_service),
    _auth: dict = Depends(verify_api_key),
) -> VoiceQueryResponse:
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
        logger.error("Voice query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Voice query failed") from e


class ElevenLabsRequest(BaseModel):
    """Legacy ElevenLabs Conversational AI request."""

    query: str | None = None
    conversation: list[dict] | None = None


@router.post("/elevenlabs/kbli-audit", deprecated=True)
async def elevenlabs_kbli_audit(
    _request: ElevenLabsRequest,
) -> dict[str, Any]:
    """
    Retired legacy ElevenLabs tool endpoint.

    The production voice concierge is local-first and must not route through
    external voice platforms. Keep the route as an explicit 410 so old webhook
    callers fail closed with a clear migration signal.
    """
    raise HTTPException(
        status_code=410,
        detail="ElevenLabs KBLI audit webhook retired; use local voice concierge.",
    )
