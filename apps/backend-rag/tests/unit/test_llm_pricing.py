"""
Tests for LLM Pricing and Token Usage module.

Tests cover:
- TokenUsage dataclass operations
- Cost calculation for various models
- Pricing table accuracy
- Edge cases and error handling
"""

import pytest

from backend.services.llm_clients.pricing import (
    LLM_PRICING,
    TokenUsage,
    calculate_cost,
    create_token_usage,
    get_model_pricing,
    list_available_models,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_token_usage_initialization_defaults(self):
        """Test default values for TokenUsage."""
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.model == "unknown"
        assert usage.cost_usd == 0.0
        assert usage.total_tokens == 0

    def test_token_usage_initialization_with_values(self):
        """Test TokenUsage with custom values."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            model="gemini-2.0-flash",
            cost_usd=0.000123,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.model == "gemini-2.0-flash"
        assert usage.cost_usd == 0.000123

    def test_total_tokens_property(self):
        """Test that total_tokens correctly sums prompt and completion."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=200)
        assert usage.total_tokens == 300

    def test_token_usage_addition(self):
        """Test adding two TokenUsage objects."""
        usage1 = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            model="gemini-2.0-flash",
            cost_usd=0.001,
        )
        usage2 = TokenUsage(
            prompt_tokens=200,
            completion_tokens=100,
            model="gemini-2.0-flash",
            cost_usd=0.002,
        )
        combined = usage1 + usage2
        assert combined.prompt_tokens == 300
        assert combined.completion_tokens == 150
        assert combined.cost_usd == 0.003
        assert combined.model == "gemini-2.0-flash"

    def test_token_usage_addition_with_unknown_model(self):
        """Test adding where first model is unknown."""
        usage1 = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            model="unknown",
            cost_usd=0.001,
        )
        usage2 = TokenUsage(
            prompt_tokens=200,
            completion_tokens=100,
            model="gemini-2.0-flash",
            cost_usd=0.002,
        )
        combined = usage1 + usage2
        assert combined.model == "gemini-2.0-flash"  # Takes the known model

    def test_token_usage_addition_with_non_token_usage(self):
        """Test adding TokenUsage with non-TokenUsage returns self."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        result = usage + "not a token usage"
        assert result is usage

    def test_token_usage_to_dict(self):
        """Test conversion to dictionary."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            model="gemini-2.0-flash",
            cost_usd=0.000123456789,
        )
        result = usage.to_dict()
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50
        assert result["total_tokens"] == 150
        assert result["model"] == "gemini-2.0-flash"
        assert result["cost_usd"] == 0.000123  # Rounded to 6 decimals


class TestCalculateCost:
    """Tests for cost calculation function."""

    def test_calculate_cost_gemini_flash(self):
        """Test cost calculation for Gemini 2.0 Flash."""
        cost = calculate_cost(
            prompt_tokens=1_000_000,  # 1M tokens
            completion_tokens=1_000_000,  # 1M tokens
            model="gemini-2.0-flash",
        )
        # Pricing: input=$0.075/1M, output=$0.30/1M
        expected = 0.075 + 0.30
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_gemini_preview_free(self):
        """Test that Gemini 3 Flash Preview is free."""
        cost = calculate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            model="gemini-3-flash-preview",
        )
        assert cost == 0.0

    def test_calculate_cost_openai_gpt4o_mini(self):
        """Test cost calculation for GPT-4o-mini."""
        cost = calculate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            model="gpt-4o-mini",
        )
        # Pricing: input=$0.15/1M, output=$0.60/1M
        expected = 0.15 + 0.60
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_unknown_model(self):
        """Test that unknown models use fallback pricing."""
        cost = calculate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            model="unknown-future-model",
        )
        # Fallback pricing: input=$1.00/1M, output=$3.00/1M
        expected = 1.00 + 3.00
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_partial_match(self):
        """Test that partial model name matching works."""
        cost = calculate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=0,
            model="models/gemini-2.0-flash",  # Has prefix
        )
        # Should match gemini-2.0-flash
        expected = 0.075
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_zero_tokens(self):
        """Test cost is zero for zero tokens."""
        cost = calculate_cost(
            prompt_tokens=0,
            completion_tokens=0,
            model="gpt-4o",
        )
        assert cost == 0.0

    def test_calculate_cost_small_token_count(self):
        """Test cost calculation for small token counts."""
        cost = calculate_cost(
            prompt_tokens=100,
            completion_tokens=50,
            model="gemini-2.0-flash",
        )
        # 100 prompt tokens * $0.075/1M + 50 completion tokens * $0.30/1M
        # = 0.0000075 + 0.000015 = 0.0000225
        # Rounded to 6 decimal places = 0.000023 (2.3e-05)
        assert cost == pytest.approx(0.000023, abs=1e-6)

    def test_calculate_cost_case_insensitive(self):
        """Test that model name matching is case insensitive."""
        cost_lower = calculate_cost(100, 50, "gemini-2.0-flash")
        cost_upper = calculate_cost(100, 50, "GEMINI-2.0-FLASH")
        assert cost_lower == cost_upper


class TestCreateTokenUsage:
    """Tests for create_token_usage factory function."""

    def test_create_token_usage_basic(self):
        """Test basic TokenUsage creation."""
        usage = create_token_usage(
            prompt_tokens=100,
            completion_tokens=50,
            model="gemini-2.0-flash",
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.model == "gemini-2.0-flash"
        assert usage.cost_usd > 0

    def test_create_token_usage_cost_calculation(self):
        """Test that cost is correctly calculated."""
        usage = create_token_usage(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            model="gemini-2.0-flash",
        )
        expected_cost = 0.075 + 0.30
        assert usage.cost_usd == pytest.approx(expected_cost, rel=1e-6)


class TestGetModelPricing:
    """Tests for get_model_pricing function."""

    def test_get_model_pricing_exact_match(self):
        """Test getting pricing for exact model name."""
        pricing = get_model_pricing("gemini-2.0-flash")
        assert pricing["input"] == 0.075
        assert pricing["output"] == 0.30

    def test_get_model_pricing_partial_match(self):
        """Test getting pricing with partial model name."""
        pricing = get_model_pricing("gemini-2.0-flash-something")
        # Should match gemini-2.0-flash
        assert pricing["input"] == 0.075

    def test_get_model_pricing_unknown(self):
        """Test getting pricing for unknown model."""
        pricing = get_model_pricing("completely-unknown-model-xyz")
        assert pricing["input"] == 1.00  # Fallback
        assert pricing["output"] == 3.00  # Fallback

    def test_get_model_pricing_returns_copy(self):
        """Test that returned dict is a copy, not the original."""
        pricing = get_model_pricing("gemini-2.0-flash")
        pricing["input"] = 999.99  # Modify the copy
        # Original should be unchanged
        assert LLM_PRICING["gemini-2.0-flash"]["input"] == 0.075


class TestListAvailableModels:
    """Tests for list_available_models function."""

    def test_list_available_models_excludes_unknown(self):
        """Test that 'unknown' is not in the list."""
        models = list_available_models()
        assert "unknown" not in models

    def test_list_available_models_contains_gemini(self):
        """Test that Gemini models are included."""
        models = list_available_models()
        assert "gemini-2.0-flash" in models
        assert "gemini-3-flash-preview" in models

    def test_list_available_models_contains_openai(self):
        """Test that OpenAI models are included."""
        models = list_available_models()
        assert "gpt-4o-mini" in models
        assert "text-embedding-3-small" in models


class TestLLMPricingTable:
    """Tests for the pricing table itself."""

    def test_all_models_have_input_output(self):
        """Test that all models have both input and output prices."""
        for model, pricing in LLM_PRICING.items():
            assert "input" in pricing, f"{model} missing 'input' price"
            assert "output" in pricing, f"{model} missing 'output' price"

    def test_all_prices_are_non_negative(self):
        """Test that all prices are non-negative."""
        for model, pricing in LLM_PRICING.items():
            assert pricing["input"] >= 0, f"{model} has negative input price"
            assert pricing["output"] >= 0, f"{model} has negative output price"

    def test_unknown_fallback_exists(self):
        """Test that unknown fallback pricing exists."""
        assert "unknown" in LLM_PRICING
        assert LLM_PRICING["unknown"]["input"] > 0
        assert LLM_PRICING["unknown"]["output"] > 0

    def test_embedding_models_have_zero_output(self):
        """Test that embedding models have zero output cost."""
        embedding_models = [
            "text-embedding-3-small",
            "text-embedding-3-large",
        ]
        for model in embedding_models:
            if model in LLM_PRICING:
                assert LLM_PRICING[model]["output"] == 0.0
