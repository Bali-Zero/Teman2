"""
Centralized LLM Configuration

Consolidates model configurations, constants, and settings to avoid duplication
across multiple LLM clients and services.
"""


# Model Names
class ModelName:
    """Gemini model names."""

    FLASH = "gemini-2.5-flash"  # Primary: Gemini 2.5 Flash (latest stable, June 2025)
    FLASH_FALLBACK = "gemini-2.5-flash"  # Fallback: Gemini 2.5 Flash
    PRO = "gemini-2.0-pro"
    PRO_EXPERIMENTAL = "gemini-2.0-pro-exp-02-05"


# OpenRouter Models
class OpenRouterModel:
    """OpenRouter model identifiers."""

    GEMINI_FLASH = "google/gemini-2.5-flash"
    DEEPSEEK_CHAT = "deepseek/deepseek-chat"


# Generation Parameters
class GenerationConfig:
    """Default generation parameters."""

    MAX_OUTPUT_TOKENS = 8192
    DEFAULT_TEMPERATURE = 0.4
    DEFAULT_TOP_P = 0.95
    DEFAULT_TOP_K = 40

    # Specific configs by use case
    CREATIVE_TEMPERATURE = 0.7
    PRECISE_TEMPERATURE = 0.2
    CODING_TEMPERATURE = 0.3


# Retry Configuration
class RetryConfig:
    """Retry and circuit breaker settings."""

    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    MAX_DELAY = 30.0
    EXPONENTIAL_BASE = 2.0

    # Circuit breaker
    CIRCUIT_FAILURE_THRESHOLD = 5
    CIRCUIT_RECOVERY_TIMEOUT = 60.0


# Token Limits
class TokenLimits:
    """Token limits for different models."""

    FLASH_INPUT = 1_048_576  # 1M tokens
    FLASH_OUTPUT = 8_192
    PRO_INPUT = 2_097_152  # 2M tokens
    PRO_OUTPUT = 8_192

    # Safety margins
    INPUT_MARGIN = 1000
    OUTPUT_MARGIN = 500


# Cost Tracking (approximate, per 1M tokens)
class ModelCost:
    """Cost per million tokens (USD)."""

    FLASH_INPUT = 0.075
    FLASH_OUTPUT = 0.30
    PRO_INPUT = 1.25
    PRO_OUTPUT = 5.00


# Timeout Configuration
class TimeoutConfig:
    """Timeout settings for LLM operations."""

    DEFAULT_TIMEOUT = 60.0
    STREAMING_TIMEOUT = 120.0
    EMBEDDING_TIMEOUT = 30.0
    HEALTH_CHECK_TIMEOUT = 10.0
