"""Langfuse observability init (POC).

POC-scope tracing for 3 targets:
  1. RAG query route (`/api/agentic-rag/query`)
  2. Council (`ToneCouncil.run`)
  3. Federation orchestrator dispatch (scripts/federation_orchestrator.py)

Design:
- Idempotent singleton init. Safe to call N times — only first has effect.
- Kill-switch: set `LANGFUSE_ENABLED=false` (or missing keys) -> no-op.
- Zero cold-start cost when disabled: heavy imports happen INSIDE init(),
  not at module import time. Module-level import of this file is cheap.
- Anthropic calls auto-traced via OpenInference instrumentation; manual
  spans (via `@observe` or context managers) wrap our own orchestration.

Usage:
    # Once, at FastAPI startup or orchestrator main():
    from backend.core.observability import init_observability
    init_observability(service_name="nuzantara-rag")

    # Anywhere else: use the langfuse SDK directly (observe decorator or
    # `get_client().start_as_current_span(...)`). If init was not called
    # or is disabled, these become no-ops.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_INITIALIZED = False
_CLIENT: Any = None
_ENABLED_CACHED: bool | None = None


def is_enabled() -> bool:
    """Return True if Langfuse tracing should be active.

    Enabled iff LANGFUSE_ENABLED != "false" AND both keys present.
    Cached after first call — env changes mid-process are ignored by design
    (avoids torn state where some spans are captured and others dropped).
    """
    global _ENABLED_CACHED
    if _ENABLED_CACHED is not None:
        return _ENABLED_CACHED

    flag = os.getenv("LANGFUSE_ENABLED", "true").strip().lower()
    has_keys = bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and bool(
        os.getenv("LANGFUSE_SECRET_KEY")
    )
    _ENABLED_CACHED = flag != "false" and has_keys
    return _ENABLED_CACHED


def init_observability(
    service_name: str = "nuzantara-rag",
    *,
    instrument_anthropic: bool = True,
    instrument_google_genai: bool = True,
    instrument_openai: bool = True,
) -> Any | None:
    """Initialize Langfuse singleton + OpenInference instrumentation.

    Auto-traces:
      - Anthropic SDK calls (kept for parity even though prod uses Claude
        OAuth CLI; see `claude_oauth_client.py` for manual OTEL spans).
      - google-genai SDK calls — covers `GenAIClient.generate_content`,
        `generate_content_stream`, and `generate_structured` (PR #311).
      - OpenAI SDK calls — covers DeepSeek and Ollama clients which both
        ship through `openai.AsyncOpenAI`.

    Per-instrumentor opt-out via env var (overrides the kwargs above):
      `LANGFUSE_INSTRUMENT_ANTHROPIC=false`
      `LANGFUSE_INSTRUMENT_GOOGLE_GENAI=false`
      `LANGFUSE_INSTRUMENT_OPENAI=false`

    Returns the Langfuse client on success, None if disabled or on error.
    Never raises — observability failures must not break the host process.
    """
    global _INITIALIZED, _CLIENT

    if not is_enabled():
        logger.info(
            "langfuse.observability.disabled reason=%s",
            "env_flag" if os.getenv("LANGFUSE_ENABLED", "").lower() == "false" else "missing_keys",
        )
        return None

    with _LOCK:
        if _INITIALIZED:
            return _CLIENT

        try:
            from langfuse import Langfuse  # noqa: WPS433
        except Exception as exc:
            logger.warning("langfuse.import_failed error=%s", exc)
            return None

        try:
            _CLIENT = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
                environment=os.getenv("LANGFUSE_ENVIRONMENT")
                or os.getenv("FLY_APP_NAME")
                or "local",
                release=os.getenv("LANGFUSE_RELEASE") or os.getenv("FLY_MACHINE_VERSION"),
                flush_at=int(os.getenv("LANGFUSE_FLUSH_AT", "15")),
                flush_interval=float(os.getenv("LANGFUSE_FLUSH_INTERVAL", "1.0")),
            )
            # NOTE: intentionally no auth_check() here — the Langfuse SDK
            # docstring explicitly warns "This method is blocking. It is
            # discouraged to use it in production code." Validity of keys
            # is checked once at `fly secrets set` time; invalid keys at
            # runtime surface as 401s on the async flush (logged by SDK).

            # Each instrumentor is gated by both the kwarg AND a per-env-var
            # so an operator can disable a single broken instrumentor at
            # runtime via `fly secrets set` without redeploy.
            if instrument_anthropic and _instrument_enabled("ANTHROPIC"):
                _try_instrument_anthropic()
            if instrument_google_genai and _instrument_enabled("GOOGLE_GENAI"):
                _try_instrument_google_genai()
            if instrument_openai and _instrument_enabled("OPENAI"):
                _try_instrument_openai()

            _INITIALIZED = True
            logger.info(
                "langfuse.observability.ready service=%s host=%s env=%s",
                service_name,
                os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
                os.getenv("LANGFUSE_ENVIRONMENT") or os.getenv("FLY_APP_NAME") or "local",
            )
            return _CLIENT
        except Exception as exc:
            logger.warning("langfuse.init_failed error=%s", exc)
            _CLIENT = None
            _INITIALIZED = False
            return None


def _instrument_enabled(provider_key: str) -> bool:
    """Return True unless `LANGFUSE_INSTRUMENT_<PROVIDER>=false` is set.

    Lets operators kill a misbehaving instrumentor mid-flight without
    redeploying — purely additive runtime guard on top of the kwarg gate.
    """
    return os.getenv(f"LANGFUSE_INSTRUMENT_{provider_key}", "true").strip().lower() != "false"


def _build_trace_config() -> Any:
    """Build the shared OpenInference `TraceConfig` for every instrumentor.

    PII-hardened: by default we hide LLM input/output messages because
    Bali Zero queries regularly contain NPWP, NIB, passport numbers, and
    client names (UU PDP scope). Opt back in per-env by setting
    `LANGFUSE_TRACE_LLM_MESSAGES=true`. One source of truth — all
    instrumentors share the same redaction posture.
    """
    from openinference.instrumentation import TraceConfig

    trace_messages = (
        os.getenv("LANGFUSE_TRACE_LLM_MESSAGES", "false").strip().lower() == "true"
    )
    return TraceConfig(
        hide_input_messages=not trace_messages,
        hide_output_messages=not trace_messages,
        hide_input_text=not trace_messages,
        hide_output_text=not trace_messages,
    ), trace_messages


def _try_instrument_anthropic() -> None:
    """Install OpenInference Anthropic auto-instrumentation (idempotent)."""
    try:
        from openinference.instrumentation.anthropic import AnthropicInstrumentor

        config, trace_messages = _build_trace_config()
        instr = AnthropicInstrumentor()
        if not instr.is_instrumented_by_opentelemetry:
            instr.instrument(config=config)
            logger.info(
                "langfuse.anthropic_instrumentation.enabled hide_messages=%s",
                not trace_messages,
            )
    except Exception as exc:
        logger.warning("langfuse.anthropic_instrumentation.failed error=%s", exc)


def _try_instrument_google_genai() -> None:
    """Install OpenInference google-genai auto-instrumentation (idempotent).

    Covers every Gemini call routed through our `GenAIClient` — including
    `generate_content`, `generate_content_stream`, and the
    `generate_structured` method introduced in PR #311.
    """
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

        config, trace_messages = _build_trace_config()
        instr = GoogleGenAIInstrumentor()
        if not instr.is_instrumented_by_opentelemetry:
            instr.instrument(config=config)
            logger.info(
                "langfuse.google_genai_instrumentation.enabled hide_messages=%s",
                not trace_messages,
            )
    except Exception as exc:
        logger.warning("langfuse.google_genai_instrumentation.failed error=%s", exc)


def _try_instrument_openai() -> None:
    """Install OpenInference OpenAI auto-instrumentation (idempotent).

    Traces every `openai.AsyncOpenAI` instance, which includes our
    DeepSeek (`base_url=https://api.deepseek.com`) and Ollama
    (`base_url=http://localhost:11434/v1`) clients. Note: the
    `gen_ai.system` attribute on emitted spans will be `openai` for
    both — we add explicit per-call labels in a follow-up PR if the
    dashboards become noisy.
    """
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor

        config, trace_messages = _build_trace_config()
        instr = OpenAIInstrumentor()
        if not instr.is_instrumented_by_opentelemetry:
            instr.instrument(config=config)
            logger.info(
                "langfuse.openai_instrumentation.enabled hide_messages=%s",
                not trace_messages,
            )
    except Exception as exc:
        logger.warning("langfuse.openai_instrumentation.failed error=%s", exc)


def get_langfuse_client() -> Any | None:
    """Return the initialized Langfuse client, or None if not ready.

    Callers SHOULD null-check. For simple tracing prefer the `@observe`
    decorator which is itself a no-op when no client is active.
    """
    return _CLIENT


def shutdown_observability() -> None:
    """Flush pending spans. Call on FastAPI shutdown / CLI exit."""
    global _CLIENT, _INITIALIZED
    client = _CLIENT
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("langfuse.flush_failed error=%s", exc)
    # Keep _CLIENT around; a re-init would be unusual but harmless.
    _ = _INITIALIZED  # no reset — avoids double-init after shutdown


__all__ = [
    "init_observability",
    "shutdown_observability",
    "get_langfuse_client",
    "is_enabled",
]
