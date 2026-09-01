"""
Google GenAI Client Wrapper

Unified client for Google's new GenAI SDK (google-genai).
Replaces the deprecated google-generativeai package.

This module provides:
- Centralized client management with connection pooling
- Async support via client.aio
- Streaming support
- Chat session management
- Backward-compatible interface for migration

Usage:
    from backend.llm.genai_client import get_genai_client, GenAIClient

    client = get_genai_client()
    response = await client.generate_content("Hello!")

    # Or streaming:
    async for chunk in client.generate_content_stream("Hello!"):
        # Process chunk
        pass

Author: Nuzantara Team
Date: 2025-12-23
"""

import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

from backend.app.core.config import settings
from backend.llm.metrics_emitter import emit_llm_metric

# NOTE: `backend.services.llm_clients.pricing` is imported LOCALLY inside the
# methods below, never at module level: `backend.services.llm_clients.__init__`
# pulls in `gemini_service`, which imports THIS module — a module-level import
# here is a circular import (verified 2026-08-09). Same reason the cost-recorder
# imports in the `finally:` blocks are function-local.

logger = logging.getLogger(__name__)


class LLMStructuredOutputError(Exception):
    """Raised by GenAIClient.generate_structured() when the model fails to
    produce a Pydantic-valid response after the configured retries.

    Callers may catch this and fall back to legacy non-structured paths;
    `query_expansion._llm_translate` does so to keep the dictionary-only
    expansion path alive when the LLM round-trips an unparseable result.

    `reason` carries the closed-vocabulary cause (see
    `_structured_failure_reason`) OUT OF BAND of the message. The message
    embeds the pydantic ValidationError, whose `input_value=...` can echo
    client PII from the prompt — which is why `verification_service` refuses
    to log `str(exc)` at all. `reason` is enum-only and therefore safe to
    log, so a caller can name the cause without touching the unsafe text.
    """

    def __init__(self, message: str = "", *, reason: str = "") -> None:
        super().__init__(message)
        self.reason = _sanitize_structured_failure_reason(reason)


# `llm_cost_events.error_class` is varchar(64) and the recorder isolates its
# sinks: an over-long value raises only on the Postgres write, so JSONL and
# Prometheus keep the event while the SQL ledger silently loses it. Losing
# exactly the failure rows makes the failure rate read as ZERO — a diagnostic
# that hides what it diagnoses. Every composed error_class is clamped here.
ERROR_CLASS_MAX_LEN = 64

# Closed vocabulary for WHY a structured call produced no schema-valid JSON.
# Values are short by construction so `LLMStructuredOutputError:<reason>` fits
# the column with room to spare, and stable so the ledger can be grouped on
# them. NEVER put model text in here — see _structured_failure_reason.
STRUCTURED_FAILURE_NO_CANDIDATES = "NO_CANDIDATES"
STRUCTURED_FAILURE_MAX_TOKENS = "MAX_TOKENS"
STRUCTURED_FAILURE_EMPTY_TEXT = "EMPTY_TEXT"
STRUCTURED_FAILURE_INVALID_JSON = "INVALID_JSON"
STRUCTURED_FAILURE_SCHEMA_VALIDATION = "SCHEMA_VALIDATION"
STRUCTURED_FAILURE_UNATTRIBUTED = "UNATTRIBUTED"
STRUCTURED_FAILURE_BLOCKED_PREFIX = "BLOCKED_"
STRUCTURED_FAILURE_BLOCKED_REASONS = frozenset(
    {
        "BLOCKED_SAFETY",
        "BLOCKED_RECITATION",
        "BLOCKED_LANGUAGE",
        "BLOCKED_OTHER",
        "BLOCKED_BLOCKLIST",
        "BLOCKED_PROHIBITED_CONTENT",
        "BLOCKED_SPII",
        "BLOCKED_MALFORMED_FUNCTION_CALL",
        "BLOCKED_IMAGE_SAFETY",
        "BLOCKED_UNEXPECTED_TOOL_CALL",
        "BLOCKED_IMAGE_PROHIBITED_CONTENT",
        "BLOCKED_NO_IMAGE",
        "BLOCKED_IMAGE_RECITATION",
        "BLOCKED_IMAGE_OTHER",
        "BLOCKED_MODEL_ARMOR",
        "BLOCKED_JAILBREAK",
    }
)


def _sanitize_structured_failure_reason(reason: object) -> str:
    """Return only a bounded member of the structured-failure vocabulary.

    ``LLMStructuredOutputError`` is public and callers can construct it
    directly, so the constructor must enforce the same PII-safe vocabulary
    that ``_structured_failure_reason`` emits. Unknown values become the stable
    ``UNATTRIBUTED`` label rather than arbitrary logged text.
    """
    if not isinstance(reason, str):
        return STRUCTURED_FAILURE_UNATTRIBUTED

    if reason in {
        STRUCTURED_FAILURE_NO_CANDIDATES,
        STRUCTURED_FAILURE_MAX_TOKENS,
        STRUCTURED_FAILURE_EMPTY_TEXT,
        STRUCTURED_FAILURE_INVALID_JSON,
        STRUCTURED_FAILURE_SCHEMA_VALIDATION,
        STRUCTURED_FAILURE_UNATTRIBUTED,
    }:
        return reason

    if reason in STRUCTURED_FAILURE_BLOCKED_REASONS:
        return reason

    return STRUCTURED_FAILURE_UNATTRIBUTED


def _enum_name(value: object) -> str:
    """Best-effort short name for an SDK enum, int, or string.

    google-genai returns `FinishReason.MAX_TOKENS` (an enum with `.name`), but
    older/proto paths hand back a bare int or the fully-qualified `str()`.
    Normalise all three so the ledger groups on one spelling.
    """
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    text = str(value)
    # `FinishReason.MAX_TOKENS` -> `MAX_TOKENS`; a bare int stays as-is.
    return text.rsplit(".", 1)[-1]


def _clamp_error_class(value: str) -> str:
    """Keep a composed error_class inside the column. See ERROR_CLASS_MAX_LEN."""
    return value[:ERROR_CLASS_MAX_LEN]


def _gemini_error_label(exc: BaseException) -> str:
    """Compose a PII-safe, quota-distinguishing ``error_class`` from a raised
    exception.

    google-genai's ``APIError`` (base of ``ClientError``/``ServerError``,
    ``google/genai/errors.py``, verified live against the installed
    google-genai==2.7.0) carries a structured HTTP ``code`` (int) and a
    structured API ``status`` string (e.g. ``RESOURCE_EXHAUSTED``,
    ``INVALID_ARGUMENT``) alongside the bare exception message. Before this,
    every write site here recorded only ``type(e).__name__``, so a 429
    quota-exhaustion event (``ClientError``) was indistinguishable in the
    ledger from an ordinary 400 malformed-request event (also
    ``ClientError``) — the 2026-08-11 WhatsApp-silent-for-hours outage read
    only as an anonymous ``ClientError`` count.

    Reads ONLY the structured ``code``/``status`` attributes — never
    ``str(exc)`` or ``exc.message``, both of which can echo prompt fragments
    back out (same PII boundary ``_structured_failure_reason`` already
    follows). Never decides by substring on the message text (cicatrix
    family #3, guard-over-match has bitten this repo repeatedly on exactly
    that pattern — see ``llm_gateway._classify_quota_exhaustion``, which
    reads the same two structured attributes for its own, independent,
    quota alert). And never CLAIMS a code/status it did not actually read:
    an exception without these attributes, or carrying the wrong type on
    them (e.g. a ``bool`` — an ``int`` subclass in Python — on ``code``),
    degrades to the bare class name, which is exactly the previous
    behaviour for non-API exceptions (``TimeoutError``, ``ConnectionError``,
    …) and therefore never turns a successful label into a failed call.
    """
    parts = [type(exc).__name__]
    code = getattr(exc, "code", None)
    if isinstance(code, int) and not isinstance(code, bool):
        parts.append(str(code))
    status = getattr(exc, "status", None)
    if isinstance(status, str) and status:
        parts.append(status)
    return _clamp_error_class(":".join(parts))


def _structured_failure_reason(
    response: object,
    raw_text: str,
    validation_error: object | None = None,
) -> str:
    """Name why a structured call yielded nothing schema-valid.

    Four causes arrive at the ledger indistinguishable today — the model was
    safety-blocked, it hit `max_output_tokens` mid-thought, it emitted malformed
    JSON, or it emitted valid JSON that did not match the schema. They want
    different fixes. The ledger recorded only `LLMStructuredOutputError` for
    all of them, which is why 10 live verifier failures over 7 days could not
    be attributed.

    PII boundary (UU PDP / SYMBIOSIS Law 2, the same rule the verifier's own
    except-block already follows): this returns ONLY enum names off the
    response envelope. The model's text and the pydantic ValidationError —
    both of which can echo client PII back out of the prompt — never enter
    the returned string. `raw_text` is parsed locally only to distinguish
    malformed JSON from schema-invalid JSON; it is never returned or logged.
    The distinction comes from Pydantic's own terminal error metadata rather
    than reparsing with stdlib JSON, whose accepted input is not identical.
    """
    candidates = getattr(response, "candidates", None) or []

    # A prompt-level block has no candidates at all; the reason lives on
    # prompt_feedback instead, so read it before giving up on the envelope.
    if not candidates:
        feedback = getattr(response, "prompt_feedback", None)
        block = getattr(feedback, "block_reason", None) if feedback else None
        if block is not None:
            return _sanitize_structured_failure_reason(
                f"{STRUCTURED_FAILURE_BLOCKED_PREFIX}{_enum_name(block)}"
            )
        return STRUCTURED_FAILURE_NO_CANDIDATES

    finish = _enum_name(getattr(candidates[0], "finish_reason", None))

    # An abnormal termination outranks whatever text survived it. A response
    # cut off by MAX_TOKENS or SAFETY often carries a PARTIAL answer, and
    # partial JSON never validates — reading that stub as INVALID_JSON would
    # name the symptom (bad shape) and bury the cause (it was cut off).
    if finish == "MAX_TOKENS":
        return STRUCTURED_FAILURE_MAX_TOKENS
    # STOP with no text is not a block — it is an empty answer, and saying
    # "BLOCKED_STOP" would invent a cause. Only non-STOP terminations name one.
    if finish and finish not in {"STOP", "UNSPECIFIED", "FINISH_REASON_UNSPECIFIED"}:
        return _sanitize_structured_failure_reason(f"{STRUCTURED_FAILURE_BLOCKED_PREFIX}{finish}")

    # Normal termination: distinguish malformed JSON from valid JSON that
    # failed Pydantic schema validation. Use the parser that actually rejected
    # the response: stdlib json.loads() accepts some inputs (for example lone
    # UTF-16 surrogates) that pydantic-core correctly reports as json_invalid.
    # Inspect only the closed error `type`; never read, return, or log `input`.
    if raw_text.strip():
        errors_method = getattr(validation_error, "errors", None)
        if callable(errors_method):
            try:
                error_details = errors_method(include_input=False)
            except Exception:
                error_details = []
            if any(
                isinstance(detail, dict) and detail.get("type") == "json_invalid"
                for detail in error_details
            ):
                return STRUCTURED_FAILURE_INVALID_JSON
            return STRUCTURED_FAILURE_SCHEMA_VALIDATION
        return STRUCTURED_FAILURE_UNATTRIBUTED
    return STRUCTURED_FAILURE_EMPTY_TEXT


# Try to import new SDK
GENAI_AVAILABLE = False
genai = None
types = None

try:
    from google import genai as google_genai
    from google.genai import types as genai_types

    genai = google_genai
    types = genai_types
    GENAI_AVAILABLE = True
    logger.info("✅ google-genai SDK loaded successfully")
except ImportError as e:
    logger.warning("⚠️ google-genai SDK not available: %s", e)
    # Try legacy SDK as fallback
    try:
        import google.generativeai  # noqa: F401

        logger.warning("⚠️ Using deprecated google-generativeai as fallback")
    except ImportError:
        logger.error("❌ No Google AI SDK available")
        GENAI_AVAILABLE = False


def _setup_service_account_credentials() -> tuple[bool, str | None]:
    """
    Setup Service Account credentials.

    Priority 1: GOOGLE_APPLICATION_CREDENTIALS file path.
    Priority 2: JSON content in environment variables.
    """
    # 1. Check for File Path (High Priority)
    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "/app/google_credentials.json"
    if gac_path and os.path.exists(gac_path):
        try:
            with open(gac_path) as f:
                creds_dict = json.load(f)
            project_id = creds_dict.get("project_id")
            # CRITICAL: Set env var so SDK finds it!
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gac_path
            logger.info(
                "✅ Service Account credentials loaded from file: %s (project: %s)",
                gac_path,
                project_id,
            )
            return True, project_id
        except Exception as e:
            logger.warning("⚠️ Failed to read GOOGLE_APPLICATION_CREDENTIALS file: %s", e)
            # Fallback to other methods

    # 2. Check for JSON Content (Legacy / Fly.io Secrets)
    creds_json = (
        getattr(settings, "google_credentials_json", None)
        or os.environ.get("GOOGLE_CREDENTIALS_JSON")
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")  # Fly.io secret name
        or os.environ.get("GEMINI_SA_TOKEN")  # Legacy alias
    )

    if not creds_json:
        return False, None

    try:
        # Parse to validate JSON
        if isinstance(creds_json, str):
            creds_json = creds_json.strip()
            if not creds_json:
                return False, None
            creds_dict = json.loads(creds_json)
        else:
            creds_dict = creds_json

        # Extract project_id for Vertex AI
        project_id = creds_dict.get("project_id")

        # Validate private key format
        private_key = creds_dict.get("private_key", "")
        if not private_key:
            logger.warning("⚠️ Service Account credentials missing private_key")
            return False, None

        # Fix escaped newlines from environment variables
        if "\\n" in private_key:
            private_key = private_key.replace("\\n", "\n")
            creds_dict["private_key"] = private_key

        # Write to temp file
        creds_file = "/tmp/google_credentials.json"
        try:
            with open(creds_file, "w") as f:
                json.dump(creds_dict, f)
        except TypeError as e:
            # Defensive check for Mock objects during testing
            if "MagicMock" in str(e) or "Mock" in str(e):
                logger.warning(
                    "⚠️ Detected Mock object in credentials during test - skipping file write",
                )
                return False, None
            raise e  # Re-raise real serialization errors

        # Set environment variable for ADC
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file

        logger.info(
            f"✅ Service Account credentials configured from ENV: {creds_dict.get('client_email', 'unknown')} (project: {project_id})",
        )
        return True, project_id

    except (OSError, json.JSONDecodeError, KeyError) as e:
        logger.warning("⚠️ Failed to setup Service Account credentials: %s", e)
        return False, None


# Lazy initialization flags
_sa_configured = False
_sa_project_id = None
_sa_setup_done = False


# Singleton client instance
_client_instance = None


def get_genai_client() -> "GenAIClient":
    """
    Get or create singleton GenAI client instance.

    Returns:
        GenAIClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GenAIClient()
    return _client_instance


class GenAIClient:
    """
    Unified Google GenAI client wrapper.

    Provides a clean interface for:
    - Content generation (sync and async)
    - Streaming responses
    - Chat sessions
    - Model configuration

    The client uses connection pooling internally for efficiency.
    """

    # Model names — imported from centralized config (backend.llm.config)
    from backend.llm.config import ModelName as _MN

    DEFAULT_MODEL = _MN.PRIMARY
    PRO_MODEL = _MN.PRIMARY
    FALLBACK_FLASH = _MN.FALLBACK
    FALLBACK_PRO = _MN.FALLBACK
    FLASH_MODEL = _MN.PRIMARY
    PRO_HIGH_MODEL = _MN.PRIMARY

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize GenAI client.

        Supports two authentication methods:
        1. Service Account (preferred for production) - via GOOGLE_CREDENTIALS_JSON (uses Vertex AI)
        2. API Key (fallback) - via GOOGLE_API_KEY or GOOGLE_IMAGEN_API_KEY (uses AI Studio)

        Args:
            api_key: Google API key (defaults to settings.google_api_key)
        """
        # LAZY INIT: Setup Service Account credentials if not done yet
        global _sa_configured, _sa_project_id, _sa_setup_done
        if not _sa_setup_done:
            _sa_configured, _sa_project_id = _setup_service_account_credentials()
            _sa_setup_done = True

        # Try multiple API key sources
        # Priority: GOOGLEAISTUDIO_API_KEY > GOOGLE_API_KEY > GOOGLE_IMAGEN_API_KEY
        self.api_key = (
            api_key
            or os.environ.get("GOOGLEAISTUDIO_API_KEY")
            or settings.google_api_key
            or settings.google_imagen_api_key
        )
        self._client = None
        self._available = False
        self._auth_method = None

        if not GENAI_AVAILABLE:
            logger.warning("⚠️ google-genai SDK not available")
            return

        # Try Service Account first (Vertex AI mode) - PREFERRED for production
        # TEMPORARILY DISABLED: Service account lacks Vertex AI permissions
        # Will use API key fallback instead
        use_vertex_ai = os.environ.get("USE_VERTEX_AI", "false").lower() == "true"

        if use_vertex_ai and _sa_configured and _sa_project_id:
            try:
                self._client = genai.Client(
                    vertexai=True,
                    project=_sa_project_id,
                    location="us-central1",
                    api_key=None,  # Explicitly disable API Key to force Vertex
                )
                self._available = True
                self._auth_method = "service_account_vertexai"
                logger.info(
                    "✅ GenAI client initialized with Vertex AI (project: %s)",
                    _sa_project_id,
                )
                return
            except Exception as e:
                logger.warning("⚠️ Vertex AI Service Account auth failed: %s", e)

        # Fallback to GOOGLE_API_KEY (AI Studio)
        if not self.api_key:
            logger.warning("⚠️ No Google API key provided and Service Account not configured")
            return

        try:
            self._client = genai.Client(api_key=self.api_key)
            self._available = True
            self._auth_method = "api_key"
            logger.info("✅ GenAI client initialized with API Key (AI Studio)")
        except Exception as e:
            logger.error("❌ Failed to initialize GenAI client: %s", e)

    @property
    def is_available(self) -> bool:
        """Check if client is available and configured."""
        return self._available and self._client is not None

    # Default request timeout in milliseconds (R2 — prevent indefinite hang on slow models)
    DEFAULT_TIMEOUT_MS: int = 120_000  # 2 minutes

    def _get_config(
        self,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        safety_settings: list | None = None,
        timeout_ms: int | None = None,
    ) -> Any:
        """Build GenerateContentConfig with optional per-request timeout."""
        if not GENAI_AVAILABLE or types is None:
            return None

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            "http_options": types.HttpOptions(
                timeout=timeout_ms if timeout_ms is not None else self.DEFAULT_TIMEOUT_MS
            ),
        }

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        if safety_settings:
            config_kwargs["safety_settings"] = safety_settings

        return types.GenerateContentConfig(**config_kwargs)

    async def generate_content(
        self,
        contents: str | list,
        model: str | None = None,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        safety_settings: list | None = None,
        timeout_ms: int | None = None,
        endpoint: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate content asynchronously.

        Every call is recorded through
        :func:`backend.services.observability.record_llm_call` (triple-write
        Prometheus + Postgres + JSONL) in addition to the existing Redis
        metric stream.

        Args:
            contents: User message or list of messages
            model: Model name (defaults to gemini-2.0-flash-lite)
            system_instruction: System prompt
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            safety_settings: Optional safety settings
            endpoint: Caller identifier for cost attribution
                (e.g. ``"visa_oracle"``). Strongly recommended.
            request_id: HTTP correlation id if available.

        Returns:
            Dictionary with 'text', 'model', 'usage' keys
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        model = model or self.DEFAULT_MODEL
        config = self._get_config(
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            safety_settings=safety_settings,
            timeout_ms=timeout_ms,
        )

        t0 = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0
        thinking_tokens = 0
        success = False
        error_class: str | None = None
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            latency_ms = round((time.perf_counter() - t0) * 1000)
            from backend.services.llm_clients.pricing import extract_gemini_usage

            prompt_tokens, completion_tokens, cached_tokens, thinking_tokens = extract_gemini_usage(
                getattr(response, "usage_metadata", None)
            )
            success = True
            logger.info(
                "LLM call",
                extra={
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
            )
            await emit_llm_metric(
                provider="gemini",
                model=model,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return {
                "text": response.text,
                "model": model,
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                },
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000)
            error_class = _gemini_error_label(e)
            logger.error(
                "LLM call failed",
                extra={
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": latency_ms,
                    "error": str(e),
                },
            )
            await emit_llm_metric(
                provider="gemini",
                model=model,
                latency_ms=latency_ms,
                status="error",
            )
            raise
        finally:
            # Indestructible cost ledger (see
            # backend/services/observability/llm_cost_recorder.py).
            try:
                from backend.services.llm_clients.pricing import calculate_cost
                from backend.services.observability import record_llm_call

                cost_usd = calculate_cost(
                    prompt_tokens,
                    completion_tokens,
                    model,
                    cached_tokens=cached_tokens,
                    thinking_tokens=thinking_tokens,
                )
                await record_llm_call(
                    provider="gemini",
                    model=model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens + thinking_tokens,
                    cost_usd=cost_usd,
                    success=success,
                    latency_ms=round((time.perf_counter() - t0) * 1000),
                    endpoint=endpoint,
                    request_id=request_id,
                    error_class=error_class,
                    cache_hit_tokens=cached_tokens,
                )
            except Exception as rec_exc:
                logger.warning("llm_cost recorder failed for gemini: %s", rec_exc)

    async def generate_structured(
        self,
        contents: str | list,
        response_schema: type,
        model: str | None = None,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        timeout_ms: int | None = None,
        endpoint: str | None = None,
        request_id: str | None = None,
        max_retries: int = 1,
    ):
        """Generate a Pydantic-validated structured response.

        Uses google-genai's native ``response_schema`` + ``response_mime_type``
        to constrain the model to JSON matching ``response_schema``. Validates
        the resulting text with ``response_schema.model_validate_json``; on a
        ``pydantic.ValidationError`` retries up to ``max_retries`` times,
        feeding the error back into the prompt (the same pattern that
        ``instructor`` uses for OpenAI-compatible providers).

        Observability: same Prometheus + Postgres + JSONL hooks as
        :meth:`generate_content`, with an extra ``response_format=structured``
        marker so we can distinguish the two paths in dashboards.

        Args:
            contents: User message (or list of messages).
            response_schema: A Pydantic v2 ``BaseModel`` subclass.
            model: Model name (defaults to ``gemini-2.0-flash-lite``).
            system_instruction: Optional system prompt.
            max_output_tokens: Cap on completion length.
            temperature: Sampling temperature.
            timeout_ms: Per-request timeout, falls back to ``DEFAULT_TIMEOUT_MS``.
            endpoint: Caller identifier for cost attribution.
            request_id: Optional HTTP correlation id.
            max_retries: Validation retries on parse/validation failure
                (1 retry = at most 2 LLM calls in total).

        Returns:
            An instance of ``response_schema`` populated from the model output.

        Raises:
            RuntimeError: if the underlying client is not available.
            LLMStructuredOutputError: if the model fails to produce a
                schema-valid response after ``max_retries`` retries.
        """
        # Lazy-import pydantic so this module stays importable in environments
        # that don't yet have it (mirrors the SDK lazy-import pattern above).
        from pydantic import BaseModel, ValidationError

        if not isinstance(response_schema, type) or not issubclass(response_schema, BaseModel):
            raise TypeError(
                f"response_schema must be a Pydantic BaseModel subclass; got {response_schema!r}"
            )

        if not self.is_available:
            raise RuntimeError("GenAI client not available")
        if types is None:
            raise RuntimeError("google-genai SDK not loaded; cannot build config")

        model = model or self.DEFAULT_MODEL

        # Build a structured-output config. We can't reuse ``_get_config``
        # because we need ``response_mime_type`` + ``response_schema`` which
        # the helper doesn't expose; the rest of the kwargs mirror it.
        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "http_options": types.HttpOptions(
                timeout=timeout_ms if timeout_ms is not None else self.DEFAULT_TIMEOUT_MS
            ),
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        config = types.GenerateContentConfig(**config_kwargs)

        attempt_prompt: str | list = contents
        last_validation_err: ValidationError | None = None
        # Bound before the loop so the failure path can attribute a cause even
        # if the loop body never runs (max_retries < 0). A None response reads
        # as NO_CANDIDATES, which is honest rather than a NameError.
        response: Any = None
        raw_text = ""

        t0 = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0
        thinking_tokens = 0
        success = False
        error_class: str | None = None
        try:
            for attempt in range(max_retries + 1):
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=attempt_prompt,
                    config=config,
                )

                # Always accumulate token usage: retries are paid attempts too.
                # Cached and thinking tokens accumulate on the same footing —
                # a retry re-sends the same prefix (so it can hit cache again)
                # and thinks again (so it bills output again).
                from backend.services.llm_clients.pricing import extract_gemini_usage

                _p, _c, _cached, _think = extract_gemini_usage(
                    getattr(response, "usage_metadata", None)
                )
                prompt_tokens += _p
                completion_tokens += _c
                cached_tokens += _cached
                thinking_tokens += _think

                raw_text = getattr(response, "text", None) or ""
                try:
                    parsed = response_schema.model_validate_json(raw_text)
                    success = True
                    latency_ms = round((time.perf_counter() - t0) * 1000)
                    logger.info(
                        "LLM structured call",
                        extra={
                            "provider": "gemini",
                            "model": model,
                            "schema": response_schema.__name__,
                            "latency_ms": latency_ms,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "attempts": attempt + 1,
                        },
                    )
                    await emit_llm_metric(
                        provider="gemini",
                        model=model,
                        latency_ms=latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                    return parsed
                except ValidationError as ve:
                    last_validation_err = ve
                    # Append validation feedback to the next attempt so the
                    # model knows what to fix (mirrors instructor's approach).
                    if attempt < max_retries:
                        feedback = (
                            "Your previous response failed schema validation. "
                            "Errors:\n"
                            f"{ve}\n\n"
                            "Return ONLY a valid JSON object that matches the "
                            "declared schema."
                        )
                        attempt_prompt = (
                            f"{contents}\n\n---\n{feedback}"
                            if isinstance(contents, str)
                            else [contents, {"role": "user", "parts": [{"text": feedback}]}]
                        )

            # Name the cause in the ledger, not just the symptom. `response`
            # and `raw_text` are the LAST attempt's — the terminal state is the
            # one worth attributing. Enum names only; see
            # _structured_failure_reason for the PII boundary.
            failure_reason = _structured_failure_reason(
                response,
                raw_text,
                last_validation_err,
            )
            error_class = _clamp_error_class(f"LLMStructuredOutputError:{failure_reason}")
            logger.warning(
                "LLM structured call failed to validate",
                extra={
                    "provider": "gemini",
                    "model": model,
                    "schema": response_schema.__name__,
                    "reason": failure_reason,
                    "attempts": max_retries + 1,
                    "completion_tokens": completion_tokens,
                    "thinking_tokens": thinking_tokens,
                    "max_output_tokens": max_output_tokens,
                },
            )
            raise LLMStructuredOutputError(
                f"Model failed to produce {response_schema.__name__}-valid JSON "
                f"after {max_retries + 1} attempt(s) [{failure_reason}]: "
                f"{last_validation_err}",
                reason=failure_reason,
            )
        except LLMStructuredOutputError:
            raise
        except Exception as e:
            error_class = _gemini_error_label(e)
            logger.error(
                "LLM structured call failed",
                extra={
                    "provider": "gemini",
                    "model": model,
                    "schema": response_schema.__name__,
                    "error": str(e),
                },
            )
            raise
        finally:
            # Mirror the cost-recorder pattern from generate_content() so the
            # llm_cost_events ledger captures structured calls too.
            try:
                from backend.services.llm_clients.pricing import calculate_cost
                from backend.services.observability import record_llm_call

                cost_usd = calculate_cost(
                    prompt_tokens,
                    completion_tokens,
                    model,
                    cached_tokens=cached_tokens,
                    thinking_tokens=thinking_tokens,
                )
                await record_llm_call(
                    provider="gemini",
                    model=model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens + thinking_tokens,
                    cost_usd=cost_usd,
                    success=success,
                    latency_ms=round((time.perf_counter() - t0) * 1000),
                    endpoint=endpoint,
                    request_id=request_id,
                    error_class=error_class,
                    cache_hit_tokens=cached_tokens,
                )
            except Exception as rec_exc:
                logger.warning("llm_cost recorder failed for gemini: %s", rec_exc)

    async def generate_content_stream(
        self,
        contents: str | list,
        model: str | None = None,
        system_instruction: str | None = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        safety_settings: list | None = None,
        timeout_ms: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming.

        Args:
            contents: User message or list of messages
            model: Model name (defaults to gemini-2.0-flash-lite)
            system_instruction: System prompt
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            safety_settings: Optional safety settings
            timeout_ms: Request timeout in milliseconds (default: DEFAULT_TIMEOUT_MS)

        Yields:
            Text chunks as they arrive
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        model = model or self.DEFAULT_MODEL
        config = self._get_config(
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            safety_settings=safety_settings,
            timeout_ms=timeout_ms,
        )

        t0 = time.perf_counter()
        chunk_count = 0
        try:
            # google-genai's AsyncModels.generate_content_stream is a COROUTINE
            # FUNCTION -- it must be awaited to obtain the AsyncIterator, even
            # though its return annotation reads AsyncIterator[...]. Iterating the
            # call directly raises `TypeError: 'async for' requires an object with
            # __aiter__ method, got coroutine` on EVERY call, which the caller
            # catches and logs as "LLM stream failed", so the path degrades in
            # silence instead of failing loudly. Measured on google-genai 1.75.0:
            # inspect.iscoroutinefunction(...) is True. Tripwire:
            # test_genai_stream_awaits_the_sdk_coroutine.py.
            stream = await self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                if chunk.text:
                    chunk_count += 1
                    yield chunk.text
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.info(
                "LLM stream",
                extra={
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": latency_ms,
                    "chunks": chunk_count,
                },
            )
            await emit_llm_metric(
                provider="gemini",
                model=model,
                latency_ms=latency_ms,
                extra={"chunks": str(chunk_count)},
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.error(
                "LLM stream failed",
                extra={
                    "provider": "gemini",
                    "model": model,
                    "latency_ms": latency_ms,
                    "error": str(e),
                },
            )
            await emit_llm_metric(
                provider="gemini",
                model=model,
                latency_ms=latency_ms,
                status="error",
            )
            raise

    def create_chat_session(
        self,
        model: str | None = None,
        system_instruction: str | None = None,
        history: list[dict] | None = None,
    ) -> "ChatSession":
        """
        Create a new chat session.

        Args:
            model: Model name (defaults to gemini-2.0-flash-lite)
            system_instruction: System prompt
            history: Optional conversation history

        Returns:
            ChatSession instance
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        return ChatSession(
            client=self,
            model=model or self.DEFAULT_MODEL,
            system_instruction=system_instruction,
            history=history,
        )

    def create_chat(
        self,
        model: str | None = None,
        system_instruction: str | None = None,
        history: list[dict] | None = None,
    ) -> "ChatSession":
        """Alias for create_chat_session."""
        return self.create_chat_session(model, system_instruction, history)

    def start_chat(
        self,
        model: str | None = None,
        history: list[dict] | None = None,
        system_instruction: str | None = None,
    ) -> Any:
        """
        Start a chat session using the underlying SDK.
        This provides direct access to the SDK's chat object.
        Required for backward compatibility with Agentic RAG services.
        """
        if not self.is_available:
            raise RuntimeError("GenAI client not available")

        model = model or self.DEFAULT_MODEL

        # Prepare config
        config = self._get_config(system_instruction=system_instruction)

        # Create chat using the new SDK interface
        # We use the synchronous client here as ChatSession expects sync calls
        return self._client.chats.create(
            model=model,
            history=history,
            config=config,
        )


class ChatSession:
    """
    Chat session wrapper for multi-turn conversations.

    Maintains conversation history and provides methods for
    sending messages with context.
    """

    def __init__(
        self,
        client: GenAIClient,
        model: str,
        system_instruction: str | None = None,
        history: list[dict] | None = None,
    ) -> None:
        """
        Initialize chat session.

        Args:
            client: GenAIClient instance
            model: Model name
            system_instruction: System prompt
            history: Optional initial history
        """
        self._client = client
        self._model = model
        self._system_instruction = system_instruction
        self._history: list[dict] = history or []

    def _format_contents(self, message: str) -> list[dict]:
        """
        Format conversation history + new message for API.

        Args:
            message: New user message

        Returns:
            Formatted contents list
        """
        contents = []

        # Add history
        # Add history
        for msg in self._history:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Skip system messages in history (handled by system_instruction)
            if role == "system":
                continue

            # Map "assistant" to "model" for Gemini
            if role == "assistant":
                role = "model"

            # Ensure strict role compliance (user or model)
            if role not in ["user", "model"]:
                # Default to model for unknown roles (e.g. tool outputs not yet handled)
                # or log warning and skip? Ideally tool outputs have 'function' role which Gemini 2 supports
                # but for text chat, map to model or user.
                if role == "function":
                    # Pass through function/tool roles if SDK supports them
                    # But current structure expects text. Let's assume text-only history for now.
                    pass
                else:
                    role = "model"

            contents.append({"role": role, "parts": [{"text": content}]})

        # Add new message
        contents.append({"role": "user", "parts": [{"text": message}]})

        return contents

    async def send_message(
        self,
        message: str,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        """
        Send a message and get response.

        Args:
            message: User message
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dictionary with 'text', 'model', 'usage' keys
        """
        contents = self._format_contents(message)

        result = await self._client.generate_content(
            contents=contents,
            model=self._model,
            system_instruction=self._system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        # Update history
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": result["text"]})

        return result

    async def send_message_stream(
        self,
        message: str,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and stream response.

        Args:
            message: User message
            max_output_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        contents = self._format_contents(message)
        full_response = ""

        async for chunk in self._client.generate_content_stream(
            contents=contents,
            model=self._model,
            system_instruction=self._system_instruction,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        ):
            full_response += chunk
            yield chunk

        # Update history after stream completes
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": full_response})

    @property
    def history(self) -> list[dict]:
        """Get conversation history."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history = []
