"""
Centralized LLM Configuration — Single Source of Truth

All model names, generation params, and timeouts live here.
Every consumer MUST import from this module instead of hardcoding.

Updated: S04 LLM Solidification
"""

import logging
import os

logger = logging.getLogger(__name__)


# ── Model Names ──────────────────────────────────────────────
# Slugs this deployment is allowed to route to. An env override outside this
# set is REFUSED (logged, default kept) rather than passed to the API: a typo
# in a Fly secret would otherwise 404 every call on the client-facing answer
# path, and the failure would look like an outage rather than a config error.
KNOWN_GEMINI_MODELS = frozenset(
    {
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    },
)


def _model_from_env(var: str, default: str) -> str:
    """Read a model slug from the environment, refusing unknown values.

    Wired 2026-08-09. `PRIMARY_MODEL_NAME` already existed as a Fly secret with
    ZERO readers repo-wide — someone meant this knob to exist and it was never
    connected, so the model was only changeable by editing a constant and
    redeploying. On `rag.gateway.chat` (78% of the LLM bill, and the path that
    answers clients) that means no fast way back from a bad choice.
    """
    raw = os.getenv(var, "").strip()
    if not raw:
        return default
    if raw not in KNOWN_GEMINI_MODELS:
        logger.error(
            "❌ %s=%r is not a known model slug — keeping %s. Known: %s",
            var,
            raw,
            default,
            sorted(KNOWN_GEMINI_MODELS),
        )
        return default
    if raw != default:
        logger.info("🔀 %s override active: %s (default %s)", var, raw, default)
    return raw


class ModelName:
    """Gemini model names — the ONLY place to change model versions.

    Defaults are the historical hardcoded values; each is overridable by a Fly
    secret so a model swap is a `fly secrets set` + restart, not a code deploy.
    Read once at import: a change needs a restart, which is what makes the
    value stable for the lifetime of a process.
    """

    # Primary — the RAG answering path (`rag.gateway.chat`) and the verifier's
    # sibling callers. Env: PRIMARY_MODEL_NAME.
    PRIMARY = _model_from_env("PRIMARY_MODEL_NAME", "gemini-3.5-flash")
    # Fallback (Gemini 2.5 Flash — stable GA). Env: FALLBACK_MODEL_NAME.
    FALLBACK = _model_from_env("FALLBACK_MODEL_NAME", "gemini-2.5-flash")
    # Channel-facing (WhatsApp/Telegram/Instagram/web via zantara_ai_client).
    # SEPARATE knob on purpose: the channels carry a different tone contract and
    # a different blast radius from the web RAG path, and rolling one back
    # should not roll back the other. Env: CHANNEL_MODEL_NAME.
    CHANNEL = _model_from_env("CHANNEL_MODEL_NAME", "gemini-3.5-flash")


class OpenRouterModel:
    """OpenRouter model identifiers."""

    GEMINI_FLASH = "google/gemini-2.5-flash"
    DEEPSEEK_CHAT = "deepseek/deepseek-chat"


class OllamaModel:
    """Ollama local model names."""

    FAST = "qwen3.5:9b"
    HEAVY = "deepseek-r1:32b"
    KG = "gemma4:26b"
    JSON = "gemma4:26b"
    VISION = "qwen2.5vl:7b"


# ── Generation Parameters ────────────────────────────────────
class GenerationConfig:
    """Default generation parameters."""

    MAX_OUTPUT_TOKENS = 8192
    DEFAULT_TEMPERATURE = 0.4
    DEFAULT_TOP_P = 0.95
    DEFAULT_TOP_K = 40

    CREATIVE_TEMPERATURE = 0.7
    PRECISE_TEMPERATURE = 0.2
    CODING_TEMPERATURE = 0.3


# ── Retry Configuration ──────────────────────────────────────
class RetryConfig:
    """Retry and circuit breaker settings."""

    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0
    EXPONENTIAL_BASE = 2.0

    CIRCUIT_FAILURE_THRESHOLD = 5
    CIRCUIT_RECOVERY_TIMEOUT = 60.0


# ── Timeout Configuration ────────────────────────────────────
class TimeoutConfig:
    """Timeout settings for LLM operations."""

    DEFAULT_TIMEOUT = 60.0
    STREAMING_TIMEOUT = 120.0
    EMBEDDING_TIMEOUT = 30.0
    HEALTH_CHECK_TIMEOUT = 10.0
