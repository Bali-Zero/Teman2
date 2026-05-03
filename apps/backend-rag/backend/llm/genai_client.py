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

logger = logging.getLogger(__name__)


class LLMStructuredOutputError(Exception):
    """Raised by GenAIClient.generate_structured() when the model fails to
    produce a Pydantic-valid response after the configured retries.

    Callers may catch this and fall back to legacy non-structured paths;
    `query_expansion._llm_translate` does so to keep the dictionary-only
    expansion path alive when the LLM round-trips an unparseable result.
    """


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
    logger.warning(f"⚠️ google-genai SDK not available: {e}")
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
                f"✅ Service Account credentials loaded from file: {gac_path} (project: {project_id})",
            )
            return True, project_id
        except Exception as e:
            logger.warning(f"⚠️ Failed to read GOOGLE_APPLICATION_CREDENTIALS file: {e}")
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
        logger.warning(f"⚠️ Failed to setup Service Account credentials: {e}")
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
                    f"✅ GenAI client initialized with Vertex AI (project: {_sa_project_id})",
                )
                return
            except Exception as e:
                logger.warning(f"⚠️ Vertex AI Service Account auth failed: {e}")

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
            logger.error(f"❌ Failed to initialize GenAI client: {e}")

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
        success = False
        error_class: str | None = None
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            latency_ms = round((time.perf_counter() - t0) * 1000)
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
            completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)
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
                provider="gemini", model=model, latency_ms=latency_ms,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
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
            error_class = type(e).__name__
            logger.error(
                "LLM call failed",
                extra={"provider": "gemini", "model": model, "latency_ms": latency_ms, "error": str(e)},
            )
            await emit_llm_metric(
                provider="gemini", model=model, latency_ms=latency_ms, status="error",
            )
            raise
        finally:
            # Indestructible cost ledger (see
            # backend/services/observability/llm_cost_recorder.py).
            try:
                from backend.services.llm_clients.pricing import calculate_cost
                from backend.services.observability import record_llm_call

                cost_usd = calculate_cost(prompt_tokens, completion_tokens, model)
                await record_llm_call(
                    provider="gemini",
                    model=model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    cost_usd=cost_usd,
                    success=success,
                    latency_ms=round((time.perf_counter() - t0) * 1000),
                    endpoint=endpoint,
                    request_id=request_id,
                    error_class=error_class,
                )
            except Exception as rec_exc:  # noqa: BLE001 — never break the caller
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
                "response_schema must be a Pydantic BaseModel subclass; "
                f"got {response_schema!r}"
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

        t0 = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
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
                prompt_tokens += getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens += (
                    getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                )

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

            error_class = "LLMStructuredOutputError"
            raise LLMStructuredOutputError(
                f"Model failed to produce {response_schema.__name__}-valid JSON "
                f"after {max_retries + 1} attempt(s): {last_validation_err}"
            )
        except LLMStructuredOutputError:
            raise
        except Exception as e:
            error_class = type(e).__name__
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

                cost_usd = calculate_cost(prompt_tokens, completion_tokens, model)
                await record_llm_call(
                    provider="gemini",
                    model=model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    cost_usd=cost_usd,
                    success=success,
                    latency_ms=round((time.perf_counter() - t0) * 1000),
                    endpoint=endpoint,
                    request_id=request_id,
                    error_class=error_class,
                )
            except Exception as rec_exc:  # noqa: BLE001 — never break the caller
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
            async for chunk in self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    chunk_count += 1
                    yield chunk.text
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.info(
                "LLM stream",
                extra={"provider": "gemini", "model": model, "latency_ms": latency_ms, "chunks": chunk_count},
            )
            await emit_llm_metric(
                provider="gemini", model=model, latency_ms=latency_ms,
                extra={"chunks": str(chunk_count)},
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.error(
                "LLM stream failed",
                extra={"provider": "gemini", "model": model, "latency_ms": latency_ms, "error": str(e)},
            )
            await emit_llm_metric(
                provider="gemini", model=model, latency_ms=latency_ms, status="error",
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
