"""Tests for LLM pricing configuration and token cost calculator."""

import pytest
from unittest.mock import patch

from backend.services.llm_clients.pricing import (
    TokenUsage,
    LLM_PRICING,
    calculate_cost,
    create_token_usage,
    get_model_pricing,
    list_available_models,
)


# ---------------------------------------------------------------------------
# calculate_cost
# ---------------------------------------------------------------------------


def test_calculate_cost_known_model() -> None:
    """calculate_cost returns correct USD for a known model."""
    # gemini-2.5-flash: input=0.075, output=0.30 per 1M tokens
    cost: float = calculate_cost(
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        model="gemini-2.5-flash",
    )
    assert cost == pytest.approx(0.075 + 0.30, abs=1e-6)


def test_calculate_cost_zero_tokens() -> None:
    """Zero tokens should produce zero cost."""
    cost: float = calculate_cost(
        prompt_tokens=0,
        completion_tokens=0,
        model="gemini-2.5-flash",
    )
    assert cost == 0.0


def test_calculate_cost_partial_match() -> None:
    """Partial model name match should still resolve pricing."""
    # "deepseek/deepseek-chat" is in the pricing table; a substring should match.
    cost_exact: float = calculate_cost(100_000, 50_000, "deepseek/deepseek-chat")
    cost_partial: float = calculate_cost(100_000, 50_000, "deepseek-chat")
    assert cost_exact == cost_partial


def test_calculate_cost_unknown_model_uses_fallback() -> None:
    """An unrecognised model should fall back to 'unknown' pricing."""
    unknown_pricing: dict[str, float] = LLM_PRICING["unknown"]
    cost: float = calculate_cost(
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        model="totally-fake-model-xyz",
    )
    expected: float = round(unknown_pricing["input"] + unknown_pricing["output"], 6)
    assert cost == pytest.approx(expected, abs=1e-6)


def test_calculate_cost_case_insensitive() -> None:
    """Model name lookup should be case-insensitive."""
    lower: float = calculate_cost(500_000, 200_000, "gemini-2.5-flash")
    upper: float = calculate_cost(500_000, 200_000, "GEMINI-2.5-FLASH")
    assert lower == upper


def test_calculate_cost_strips_whitespace() -> None:
    """Leading/trailing whitespace in model name should be ignored."""
    clean: float = calculate_cost(100_000, 100_000, "gemini-2.5-flash")
    padded: float = calculate_cost(100_000, 100_000, "  gemini-2.5-flash  ")
    assert clean == padded


def test_calculate_cost_embedding_model_zero_output() -> None:
    """Embedding model has output price 0 -- only input cost matters."""
    cost: float = calculate_cost(
        prompt_tokens=1_000_000,
        completion_tokens=500_000,
        model="text-embedding-3-small",
    )
    # output price is 0 so only input cost applies: 0.02 USD
    assert cost == pytest.approx(0.02, abs=1e-6)


# ---------------------------------------------------------------------------
# create_token_usage
# ---------------------------------------------------------------------------


def test_create_token_usage_populates_all_fields() -> None:
    """create_token_usage returns a TokenUsage with cost calculated."""
    usage: TokenUsage = create_token_usage(
        prompt_tokens=500_000,
        completion_tokens=200_000,
        model="gemini-2.5-flash",
    )
    assert usage.prompt_tokens == 500_000
    assert usage.completion_tokens == 200_000
    assert usage.model == "gemini-2.5-flash"
    assert usage.cost_usd > 0.0
    expected_cost: float = calculate_cost(500_000, 200_000, "gemini-2.5-flash")
    assert usage.cost_usd == pytest.approx(expected_cost, abs=1e-6)


def test_create_token_usage_zero_tokens() -> None:
    """Zero-token usage should result in zero cost."""
    usage: TokenUsage = create_token_usage(0, 0, "gemini-2.5-flash")
    assert usage.cost_usd == 0.0
    assert usage.total_tokens == 0


# ---------------------------------------------------------------------------
# get_model_pricing
# ---------------------------------------------------------------------------


def test_get_model_pricing_exact_match() -> None:
    """Exact model name returns correct pricing dict."""
    pricing: dict[str, float] = get_model_pricing("gemini-2.5-flash")
    assert pricing == {"input": 0.075, "output": 0.30}


def test_get_model_pricing_returns_copy() -> None:
    """Returned dict should be a copy, not a reference to the global table."""
    pricing: dict[str, float] = get_model_pricing("gemini-2.5-flash")
    pricing["input"] = 999.0
    original: dict[str, float] = get_model_pricing("gemini-2.5-flash")
    assert original["input"] != 999.0


def test_get_model_pricing_unknown_model() -> None:
    """Unknown model falls back to 'unknown' pricing."""
    pricing: dict[str, float] = get_model_pricing("nonexistent-model-abc")
    assert pricing == LLM_PRICING["unknown"]


def test_get_model_pricing_partial_match() -> None:
    """Partial model name resolves via substring matching."""
    pricing: dict[str, float] = get_model_pricing("deepseek-chat")
    assert "input" in pricing
    assert "output" in pricing
    # Should match deepseek/deepseek-chat pricing
    assert pricing == LLM_PRICING["deepseek/deepseek-chat"]


# ---------------------------------------------------------------------------
# list_available_models
# ---------------------------------------------------------------------------


def test_list_available_models_excludes_unknown() -> None:
    """'unknown' should NOT appear in the available models list."""
    models: list[str] = list_available_models()
    assert "unknown" not in models


def test_list_available_models_returns_known_entries() -> None:
    """All non-unknown keys from LLM_PRICING should be in the list."""
    models: list[str] = list_available_models()
    expected: list[str] = [m for m in LLM_PRICING if m != "unknown"]
    assert set(models) == set(expected)


def test_list_available_models_not_empty() -> None:
    """There should be at least one model with known pricing."""
    models: list[str] = list_available_models()
    assert len(models) > 0


# ---------------------------------------------------------------------------
# TokenUsage.total_tokens
# ---------------------------------------------------------------------------


def test_total_tokens_property() -> None:
    """total_tokens is the sum of prompt + completion tokens."""
    usage: TokenUsage = TokenUsage(prompt_tokens=150, completion_tokens=350)
    assert usage.total_tokens == 500


def test_total_tokens_defaults_zero() -> None:
    """Default TokenUsage has 0 total tokens."""
    usage: TokenUsage = TokenUsage()
    assert usage.total_tokens == 0


# ---------------------------------------------------------------------------
# TokenUsage.to_dict
# ---------------------------------------------------------------------------


def test_to_dict_structure() -> None:
    """to_dict returns all expected keys with correct values."""
    usage: TokenUsage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=200,
        model="gemini-2.5-flash",
        cost_usd=0.000123456,
    )
    result: dict = usage.to_dict()
    assert result["prompt_tokens"] == 100
    assert result["completion_tokens"] == 200
    assert result["total_tokens"] == 300
    assert result["model"] == "gemini-2.5-flash"
    assert result["cost_usd"] == round(0.000123456, 6)


def test_to_dict_cost_rounding() -> None:
    """cost_usd in to_dict should be rounded to 6 decimal places."""
    usage: TokenUsage = TokenUsage(cost_usd=0.1234567890)
    result: dict = usage.to_dict()
    assert result["cost_usd"] == 0.123457  # rounded at 6th decimal


# ---------------------------------------------------------------------------
# TokenUsage.__add__
# ---------------------------------------------------------------------------


def test_token_usage_add_accumulates() -> None:
    """Adding two TokenUsage objects accumulates all numeric fields."""
    a: TokenUsage = TokenUsage(
        prompt_tokens=100, completion_tokens=50, model="gemini-2.5-flash", cost_usd=0.01
    )
    b: TokenUsage = TokenUsage(
        prompt_tokens=200, completion_tokens=150, model="gemini-2.5-flash", cost_usd=0.02
    )
    combined: TokenUsage = a + b
    assert combined.prompt_tokens == 300
    assert combined.completion_tokens == 200
    assert combined.cost_usd == pytest.approx(0.03, abs=1e-6)
    assert combined.total_tokens == 500


def test_token_usage_add_prefers_known_model() -> None:
    """When one operand has model='unknown', the other model is kept."""
    a: TokenUsage = TokenUsage(model="unknown", prompt_tokens=10)
    b: TokenUsage = TokenUsage(model="gemini-2.5-flash", prompt_tokens=20)
    combined: TokenUsage = a + b
    assert combined.model == "gemini-2.5-flash"


def test_token_usage_add_keeps_first_model_when_both_known() -> None:
    """When both have known models, the left operand's model wins."""
    a: TokenUsage = TokenUsage(model="gemini-2.5-flash", prompt_tokens=10)
    b: TokenUsage = TokenUsage(model="deepseek/deepseek-chat", prompt_tokens=20)
    combined: TokenUsage = a + b
    assert combined.model == "gemini-2.5-flash"


def test_token_usage_add_non_token_usage_returns_self() -> None:
    """Adding a non-TokenUsage value should return self unchanged."""
    a: TokenUsage = TokenUsage(prompt_tokens=100, completion_tokens=50, cost_usd=0.01)
    result: TokenUsage = a + 42  # type: ignore[operator]
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.cost_usd == 0.01
