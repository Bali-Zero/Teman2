"""
LLM Pricing Configuration and Token Cost Calculator.

Provides pricing tables for all LLM providers used in the system
and utilities for calculating costs from token usage.

Pricing is in USD per 1 million tokens (input/output).

Author: Nuzantara Team
Date: 2025-12-28
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage tracking for a single LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = "unknown"
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens used (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Accumulate token usage from multiple calls."""
        if not isinstance(other, TokenUsage):
            return self
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            model=self.model if self.model != "unknown" else other.model,
            cost_usd=self.cost_usd + other.cost_usd,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "cost_usd": round(self.cost_usd, 6),
        }


# Pricing per 1 million tokens (USD)
# Updated: S04 LLM Solidification
# Source: https://ai.google.dev/pricing, https://openai.com/pricing, https://openrouter.ai/models
LLM_PRICING: dict[str, dict[str, float]] = {
    # ── Active Gemini Models (primary + fallback) ──
    "gemini-3-flash": {
        "input": 0.10,
        "output": 0.40,
    },
    "gemini-2.5-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    # ── Legacy Gemini (kept for cost tracking of old logs) ──
    "gemini-3-flash-preview": {
        "input": 0.10,
        "output": 0.40,
    },
    "gemini-2.0-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    "gemini-2.0-flash-lite": {
        "input": 0.0375,
        "output": 0.15,
    },
    # ── OpenAI (embedding only) ──
    "text-embedding-3-small": {
        "input": 0.02,
        "output": 0.0,
    },
    # ── OpenRouter (fallback tier, includes markup) ──
    "google/gemini-2.5-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    "deepseek/deepseek-chat": {
        "input": 0.27,
        "output": 1.10,
    },
    # ── Default fallback (conservative estimate) ──
    "unknown": {
        "input": 1.00,
        "output": 3.00,
    },
}


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
) -> float:
    """
    Calculate the cost in USD for a given token usage.

    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model: Model name (must match key in LLM_PRICING)

    Returns:
        Cost in USD (float, 6 decimal precision)
    """
    # Normalize model name (handle variations)
    model_key = model.lower().strip()

    # Try exact match first
    pricing = LLM_PRICING.get(model_key)

    # Try partial match for model families
    if pricing is None:
        for key in LLM_PRICING:
            if key in model_key or model_key in key:
                pricing = LLM_PRICING[key]
                break

    # Fallback to unknown pricing
    if pricing is None:
        pricing = LLM_PRICING["unknown"]
        logger.warning(f"Unknown model pricing: {model}, using default rates")

    # Calculate cost (pricing is per 1M tokens)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 6)


def create_token_usage(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
) -> TokenUsage:
    """
    Create a TokenUsage object with calculated cost.

    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model: Model name

    Returns:
        TokenUsage dataclass with all fields populated
    """
    cost = calculate_cost(prompt_tokens, completion_tokens, model)

    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
        cost_usd=cost,
    )


def get_model_pricing(model: str) -> dict[str, float]:
    """
    Get pricing information for a specific model.

    Args:
        model: Model name

    Returns:
        Dict with 'input' and 'output' prices per 1M tokens
    """
    model_key = model.lower().strip()

    # Try exact match
    if model_key in LLM_PRICING:
        return LLM_PRICING[model_key].copy()

    # Try partial match
    for key in LLM_PRICING:
        if key in model_key or model_key in key:
            return LLM_PRICING[key].copy()

    return LLM_PRICING["unknown"].copy()


def list_available_models() -> list[str]:
    """
    Get list of all models with known pricing.

    Returns:
        List of model names
    """
    return [m for m in LLM_PRICING if m != "unknown"]
