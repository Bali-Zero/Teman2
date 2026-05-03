"""Tests for the LLM gateway."""

import pytest

from nuzantara_graph.services.llm_gateway import CircuitBreaker, LLMGateway, LLMResponse


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True

    def test_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        cb.record_success()
        assert cb.failure_count == 0


class TestLLMGateway:
    @pytest.mark.asyncio
    async def test_raises_without_implementation(self):
        gw = LLMGateway()
        with pytest.raises(RuntimeError, match="All models failed"):
            await gw.generate(prompt="test")

    def test_default_models(self):
        gw = LLMGateway()
        assert gw.primary_model == "gemini-2.0-flash"
        assert gw.fallback_model == "gemini-1.5-flash"

    def test_custom_models(self):
        gw = LLMGateway(primary_model="gpt-4o", fallback_model="gpt-4o-mini")
        assert gw.primary_model == "gpt-4o"
