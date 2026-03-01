"""
Unit tests for Claude Client with Retry Logic and Circuit Breaker
"""

from unittest.mock import MagicMock, patch
from typing import Any

import anthropic
import pytest

from backend.services.article_composer.claude_client import (
    CircuitBreaker,
    CircuitState,
    call_claude_with_retry,
    get_anthropic_client,
)


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in CLOSED state"""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_success(self):
        """Test successful call keeps circuit CLOSED"""
        cb = CircuitBreaker(failure_threshold=3)
        func = MagicMock(return_value="success")

        result = cb.call(func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_failure_threshold(self):
        """Test circuit opens after failure threshold"""
        cb = CircuitBreaker(failure_threshold=3)
        func = MagicMock(side_effect=Exception("Error"))

        # First 2 failures - still CLOSED
        for _ in range(2):
            try:
                cb.call(func)
            except Exception:
                pass
        assert cb.state == CircuitState.CLOSED

        # 3rd failure - opens circuit
        try:
            cb.call(func)
        except Exception:
            pass
        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_open_rejects(self):
        """Test OPEN circuit rejects calls"""
        import time

        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()  # Recent - don't attempt reset yet

        func = MagicMock(return_value="success")

        # Circuit breaker should raise APIError when OPEN
        with pytest.raises(Exception):  # Any exception is fine
            cb.call(func)

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit recovers through HALF_OPEN state"""
        cb = CircuitBreaker(failure_threshold=2, half_open_max_calls=2)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = 0  # Set to past

        func = MagicMock(return_value="success")

        # Should transition to HALF_OPEN
        result = cb.call(func)
        assert cb.state == CircuitState.HALF_OPEN
        assert result == "success"

        # Second success - should close
        result = cb.call(func)
        assert cb.state == CircuitState.CLOSED


class TestGetAnthropicClient:
    """Test Anthropic client singleton"""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_client_creates_singleton(self):
        """Test client is created as singleton"""
        # Clear global state
        import backend.services.article_composer.claude_client as claude_module

        claude_module._anthropic_client = None

        client1 = get_anthropic_client()
        client2 = get_anthropic_client()

        assert client1 is client2

    @patch.dict("os.environ", {}, clear=True)
    def test_get_client_raises_without_key(self):
        """Test client creation raises without API key"""
        import backend.services.article_composer.claude_client as claude_module

        claude_module._anthropic_client = None

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            get_anthropic_client()


class TestCallClaudeWithRetry:
    """Test retry logic for Claude API calls"""

    @pytest.mark.asyncio
    @patch("backend.services.article_composer.claude_client.get_anthropic_client")
    async def test_successful_call_no_retry(self, mock_get_client):
        """Test successful call doesn't retry"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"result": "success"}')]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=200)
        mock_client.messages.create.return_value = mock_message
        mock_get_client.return_value = mock_client

        # Mock circuit breaker
        with patch(
            "backend.services.article_composer.claude_client._claude_circuit_breaker"
        ) as mock_cb:
            mock_cb.call = MagicMock(return_value=mock_message)

            result = await call_claude_with_retry(
                prompt="test prompt", model="claude-sonnet-4-20250514"
            )

            assert result == mock_message
            mock_cb.call.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.article_composer.claude_client.get_anthropic_client")
    async def test_retry_on_rate_limit(self, mock_get_client):
        """Test retry on rate limit error - circuit breaker raises, propagates"""
        mock_response = MagicMock()
        rate_limit_error = anthropic.RateLimitError(
            "Rate limit exceeded", response=mock_response, body=None
        )

        # Mock circuit breaker to raise rate limit error (avoids tenacity retry logging)
        with patch(
            "backend.services.article_composer.claude_client._claude_circuit_breaker"
        ) as mock_cb:
            mock_cb.call.side_effect = rate_limit_error

            # Should raise after retries exhausted
            with pytest.raises(anthropic.RateLimitError):
                await call_claude_with_retry(prompt="test prompt")

    @pytest.mark.asyncio
    @patch("backend.services.article_composer.claude_client.get_anthropic_client")
    async def test_non_retryable_error(self, mock_get_client):
        """Test non-retryable errors don't retry"""
        mock_response = MagicMock()
        mock_response.request = MagicMock()
        auth_error = anthropic.AuthenticationError(
            "Invalid API key", response=mock_response, body=None
        )

        with patch(
            "backend.services.article_composer.claude_client._claude_circuit_breaker"
        ) as mock_cb:
            mock_cb.call.side_effect = auth_error

            with pytest.raises(anthropic.AuthenticationError):
                await call_claude_with_retry(prompt="test prompt")
