"""
Centralized LLM Configuration — Single Source of Truth

All model names, generation params, and timeouts live here.
Every consumer MUST import from this module instead of hardcoding.

Updated: S04 LLM Solidification
"""


# ── Model Names ──────────────────────────────────────────────
class ModelName:
    """Gemini model names — the ONLY place to change model versions."""

    # Primary (Gemini 3 Flash GA)
    PRIMARY = "gemini-3-flash"
    # Fallback (Gemini 2.5 Flash — stable)
    FALLBACK = "gemini-2.5-flash"
    # Channel-facing (same as primary for cost parity)
    CHANNEL = "gemini-3-flash"


class OpenRouterModel:
    """OpenRouter model identifiers."""

    GEMINI_FLASH = "google/gemini-2.5-flash"
    DEEPSEEK_CHAT = "deepseek/deepseek-chat"


class OllamaModel:
    """Ollama local model names."""

    FAST = "qwen3.5:9b"
    HEAVY = "deepseek-r1:32b"
    KG = "qwen3.5:27b"
    JSON = "gemma3:12b"
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
