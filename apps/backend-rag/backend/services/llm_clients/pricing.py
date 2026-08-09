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
#
# ``cached_input`` is the per-1M rate Google bills for prompt tokens served from
# context cache. Implicit caching is ON BY DEFAULT for every Gemini 2.5+ model
# (eligibility threshold 4,096 tokens on 3.5-flash / 3.1-pro, 2,048 on 2.5), so
# these rates apply to real traffic with no code opting in — which is exactly why
# omitting them made the ledger overstate the bill. Verified verbatim against
# https://ai.google.dev/gemini-api/docs/pricing on 2026-08-09.
# A model WITHOUT a ``cached_input`` key is billed cached tokens at the full input
# rate: conservative by construction, never under-bills.
LLM_PRICING: dict[str, dict[str, float]] = {
    # ── Active Gemini Models (primary + fallback) ──
    "gemini-3.5-flash": {
        "input": 1.50,
        "output": 9.00,
        "cached_input": 0.15,
    },
    "gemini-2.5-flash": {
        "input": 0.075,
        "output": 0.30,
        "cached_input": 0.03,
    },
    # ── Gemini Flash-Lite tier (candidate verifier/cheap lane, 2026-08-09) ──
    "gemini-3.5-flash-lite": {
        "input": 0.30,
        "output": 2.50,
        "cached_input": 0.03,
    },
    "gemini-3.1-flash-lite": {
        "input": 0.25,
        "output": 1.50,
        "cached_input": 0.025,
    },
    "gemini-2.5-flash-lite": {
        "input": 0.10,
        "output": 0.40,
        "cached_input": 0.01,
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
    # ── DeepSeek V4 flagship (2026-04-24 release) ──
    "deepseek/deepseek-v4-pro": {
        "input": 0.435,
        "output": 0.87,
    },
    "deepseek/deepseek-v4-flash": {
        "input": 0.14,
        "output": 0.28,
    },
    # Legacy alias — V4-Flash rates apply on DeepSeek side
    # (DEPRECATED 2026-07-24, kept for backward-compat with old logs)
    "deepseek/deepseek-chat": {
        "input": 0.14,
        "output": 0.28,
    },
    # ── Default fallback (conservative estimate) ──
    "unknown": {
        "input": 1.00,
        "output": 3.00,
    },
}


def extract_gemini_usage(usage_metadata: object) -> tuple[int, int, int, int]:
    """Pull (prompt, completion, cached, thinking) tokens off a google-genai response.

    ONE reader for every Gemini call site. Four hand-rolled getattr chains is how
    two of these fields stayed invisible to the ledger for a month: the recorder
    accepted ``cache_hit_tokens`` and nobody passed it, and ``thoughts_token_count``
    was never read at all.

    Field names verified against google-genai 2.7.0
    (``types.GenerateContentResponseUsageMetadata``) on 2026-08-09. Returns zeros
    for a missing/None metadata object rather than raising — cost accounting must
    never break a chat response.
    """
    if not usage_metadata:
        return 0, 0, 0, 0
    return (
        getattr(usage_metadata, "prompt_token_count", 0) or 0,
        getattr(usage_metadata, "candidates_token_count", 0) or 0,
        getattr(usage_metadata, "cached_content_token_count", 0) or 0,
        getattr(usage_metadata, "thoughts_token_count", 0) or 0,
    )


def resolve_pricing(model: str) -> dict[str, float]:
    """Resolve a model slug to its price row.

    Partial matches pick the LONGEST matching key, never the first one the dict
    happens to yield. With both ``gemini-3.5-flash`` ($1.50) and
    ``gemini-3.5-flash-lite`` ($0.30) in the table, insertion-order matching
    would bill any suffixed lite slug (e.g. ``gemini-3.5-flash-lite-preview``)
    at the parent's rate — a 5x over-charge from a substring standing in for an
    entity (superscar #3).
    """
    model_key = model.lower().strip()

    pricing = LLM_PRICING.get(model_key)
    if pricing is not None:
        return pricing

    candidates = [k for k in LLM_PRICING if k != "unknown" and (k in model_key or model_key in k)]
    if candidates:
        return LLM_PRICING[max(candidates, key=len)]

    logger.warning("Unknown model pricing: %s, using default rates", model)
    return LLM_PRICING["unknown"]


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    cached_tokens: int = 0,
    thinking_tokens: int = 0,
) -> float:
    """
    Calculate the cost in USD for a given token usage.

    Args:
        prompt_tokens: Total input tokens as reported by the provider. On Gemini
            this ALREADY INCLUDES any cache hit, so ``cached_tokens`` is treated
            as a subset and billed at the discounted rate instead of the full one.
        completion_tokens: Number of visible output tokens
        model: Model name (must match key in LLM_PRICING)
        cached_tokens: Prompt tokens served from context cache
            (``usage_metadata.cached_content_token_count``). Billed at
            ``cached_input`` when the model declares one, else at the full input
            rate. Clamped to ``prompt_tokens``.
        thinking_tokens: Reasoning tokens (``usage_metadata.thoughts_token_count``).
            Gemini reports these SEPARATELY from ``candidates_token_count`` and
            bills them at the OUTPUT rate — omitting them under-counts the bill.

    Returns:
        Cost in USD (float, 6 decimal precision)
    """
    pricing = resolve_pricing(model)

    cached = max(0, min(cached_tokens, prompt_tokens))
    fresh_input = prompt_tokens - cached
    cached_rate = pricing.get("cached_input", pricing["input"])

    input_cost = (fresh_input / 1_000_000) * pricing["input"]
    cached_cost = (cached / 1_000_000) * cached_rate
    output_cost = ((completion_tokens + max(0, thinking_tokens)) / 1_000_000) * pricing["output"]

    return round(input_cost + cached_cost + output_cost, 6)


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
    # Same longest-match resolution as calculate_cost — two functions that answer
    # "what does this model cost" must not disagree on which row wins.
    return resolve_pricing(model).copy()


def list_available_models() -> list[str]:
    """
    Get list of all models with known pricing.

    Returns:
        List of model names
    """
    return [m for m in LLM_PRICING if m != "unknown"]


# ── Per-provider/model pricing table (used by @llm_cost_tracked decorator) ──
# Keys: (provider, model)
# Values: {"input_per_token": float, "output_per_token": float}
# Prices are in USD per single token.
_PRICING_TABLE: dict[tuple[str, str], dict[str, float]] = {
    ("openai_embeddings", "text-embedding-3-small"): {
        "input_per_token": 0.02 / 1_000_000,
        "output_per_token": 0.0,
    },
    ("imagen", "imagen-4.0-ultra-generate-001"): {
        "input_per_token": 0.06,
        "output_per_token": 0.0,
    },
    ("imagen", "imagen-4.0-generate-001"): {
        "input_per_token": 0.04,
        "output_per_token": 0.0,
    },
    ("imagen", "imagen-4.0-fast-generate-001"): {
        "input_per_token": 0.02,
        "output_per_token": 0.0,
    },
    ("openai_audio", "tts-1"): {
        "input_per_token": 15.0 / 1_000_000,
        "output_per_token": 0.0,
    },
    ("openai_audio", "whisper-1"): {
        "input_per_token": 0.006 / 60,
        "output_per_token": 0.0,
    },
    # ── OpenRouter free-tier models (volume-only tracking, cost=0) ──
    ("openrouter", "google/gemini-2.0-flash-exp:free"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("openrouter", "qwen/qwen3.5-27b"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("openrouter", "mistralai/mistral-small-3.1-24b-instruct:free"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("openrouter", "qwen/qwen3.5-35b-a3b"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("openrouter", "meta-llama/llama-3.2-3b-instruct:free"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("openrouter", "openrouter-unknown"): {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    # ── DeepSeek V4 flagship (2026-04-24 release) ──
    # Source: https://api-docs.deepseek.com/news/news260424
    # V4 Pro: 1.6T params, 49B activated, 1M ctx, ``reasoning_effort`` modes
    #   (cache-miss/output rates; 75% promo to 2026-05-31 not applied here)
    ("deepseek", "deepseek-v4-pro"): {
        "input_per_token": 0.435 / 1_000_000,
        "output_per_token": 0.87 / 1_000_000,
    },
    # V4 Flash: 284B params, 13B activated, 1M ctx
    ("deepseek", "deepseek-v4-flash"): {
        "input_per_token": 0.14 / 1_000_000,
        "output_per_token": 0.28 / 1_000_000,
    },
    # Legacy aliases — DEPRECATED 2026-07-24, routed to V4-Flash on DeepSeek side
    # so V4-Flash rates apply. Kept for backward-compat with historical logs.
    ("deepseek", "deepseek-reasoner"): {
        "input_per_token": 0.14 / 1_000_000,
        "output_per_token": 0.28 / 1_000_000,
    },
    ("deepseek", "deepseek-chat"): {
        "input_per_token": 0.14 / 1_000_000,
        "output_per_token": 0.28 / 1_000_000,
    },
}


def compute_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Compute the cost in USD for a given provider/model and token usage.

    Args:
        provider: Provider tag (e.g. 'openai_embeddings', 'imagen').
        model: Model slug (e.g. 'text-embedding-3-small').
        input_tokens: Number of input tokens (or equivalent units).
        output_tokens: Number of output tokens (or equivalent units).

    Returns:
        Cost in USD as a float.

    Raises:
        KeyError: If the (provider, model) pair is not registered.
    """
    entry = _PRICING_TABLE[(provider, model)]
    return input_tokens * entry["input_per_token"] + output_tokens * entry["output_per_token"]
