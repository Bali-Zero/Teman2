"""
Unit Tests for llm/retry_handler.py - 95% Coverage Target
Tests the RetryHandler class
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test RetryHandler initialization
# ============================================================================


class TestRetryHandlerInit:
    """Test suite for RetryHandler initialization"""

    def test_init_default_values(self):
        """Test initialization with default values"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler()

        assert handler.max_retries == 3
        assert handler.base_delay == 2.0
        assert handler.backoff_factor == 2

    def test_init_custom_values(self):
        """Test initialization with custom values"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=5, base_delay=1.0, backoff_factor=3)

        assert handler.max_retries == 5
        assert handler.base_delay == 1.0
        assert handler.backoff_factor == 3


# ============================================================================
# Test execute_with_retry
# ============================================================================


class TestExecuteWithRetry:
    """Test suite for execute_with_retry method"""

    @pytest.mark.asyncio
    async def test_execute_success_first_attempt(self):
        """Test successful execution on first attempt"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler()

        async def success_operation():
            return "success"

        result = await handler.execute_with_retry(success_operation, "test_op")

        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_retry_on_connection_error(self):
        """Test retry on connection error"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=3, base_delay=0.01, backoff_factor=2)

        call_count = [0]

        async def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Connection timeout")
            return "success after retry"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(flaky_operation, "test_op")

        assert result == "success after retry"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_execute_retry_on_timeout_error(self):
        """Test retry on timeout error"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=3, base_delay=0.01, backoff_factor=2)

        call_count = [0]

        async def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Request timeout exceeded")
            return "success"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(flaky_operation, "test_op")

        assert result == "success"
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_execute_no_retry_on_non_retryable_error(self):
        """Test no retry on non-retryable error"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=3)

        call_count = [0]

        async def failing_operation():
            call_count[0] += 1
            raise ValueError("Invalid input parameter")

        with pytest.raises(ValueError, match="Invalid input parameter"):
            await handler.execute_with_retry(failing_operation, "test_op")

        # Should only call once - no retry for non-retryable errors
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_execute_exhausts_retries(self):
        """Test that retries are exhausted for persistent errors"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=3, base_delay=0.01)

        call_count = [0]

        async def always_fail():
            call_count[0] += 1
            raise Exception("Connection refused - server unavailable")

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Connection refused"):
                await handler.execute_with_retry(always_fail, "test_op")

        # Should try all 3 times
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_execute_with_custom_retryable_errors(self):
        """Test retry with custom retryable error keywords"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=3, base_delay=0.01)

        call_count = [0]

        async def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Custom retryable error happened")
            return "success"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(
                flaky_operation, "test_op", retryable_errors=["custom", "retryable"]
            )

        assert result == "success"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_execute_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=4, base_delay=1.0, backoff_factor=2)

        call_count = [0]
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        async def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 4:
                raise Exception("Connection error")
            return "success"

        with patch("llm.retry_handler.asyncio.sleep", side_effect=mock_sleep):
            result = await handler.execute_with_retry(flaky_operation, "test_op")

        assert result == "success"
        # Check exponential backoff: 1*2^0=1, 1*2^1=2, 1*2^2=4
        assert sleep_calls == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_execute_retry_503_error(self):
        """Test retry on 503 service unavailable"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01)

        call_count = [0]

        async def service_unavailable():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("HTTP 503 Service Unavailable")
            return "recovered"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(service_unavailable, "test_op")

        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_execute_retry_429_rate_limit(self):
        """Test retry on 429 rate limit error"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01)

        call_count = [0]

        async def rate_limited():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("HTTP 429 Too Many Requests")
            return "success after rate limit"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(rate_limited, "test_op")

        assert result == "success after rate limit"

    @pytest.mark.asyncio
    async def test_execute_retry_502_bad_gateway(self):
        """Test retry on 502 bad gateway"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01)

        call_count = [0]

        async def bad_gateway():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("HTTP 502 Bad Gateway")
            return "success"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(bad_gateway, "test_op")

        assert result == "success"


# ============================================================================
# Test module constants
# ============================================================================


class TestModuleConstants:
    """Test suite for module constants"""

    def test_retryable_error_keywords(self):
        """Test RETRYABLE_ERROR_KEYWORDS constant"""
        from llm.retry_handler import RETRYABLE_ERROR_KEYWORDS

        assert "connection" in RETRYABLE_ERROR_KEYWORDS
        assert "timeout" in RETRYABLE_ERROR_KEYWORDS
        assert "network" in RETRYABLE_ERROR_KEYWORDS
        assert "api" in RETRYABLE_ERROR_KEYWORDS
        assert "rate" in RETRYABLE_ERROR_KEYWORDS
        assert "server" in RETRYABLE_ERROR_KEYWORDS
        assert "unavailable" in RETRYABLE_ERROR_KEYWORDS
        assert "503" in RETRYABLE_ERROR_KEYWORDS
        assert "502" in RETRYABLE_ERROR_KEYWORDS
        assert "429" in RETRYABLE_ERROR_KEYWORDS


# ============================================================================
# Test edge cases
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases"""

    @pytest.mark.asyncio
    async def test_execute_with_zero_retries(self):
        """Test execution with zero retries"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=0)

        async def operation():
            return "success"

        # With 0 retries, the for loop doesn't execute
        # This tests the fallback RuntimeError path
        with pytest.raises(RuntimeError, match="failed after 0 attempts"):
            await handler.execute_with_retry(operation, "zero_retry_op")

    @pytest.mark.asyncio
    async def test_execute_last_exception_raised(self):
        """Test that last_exception is raised if set"""
        from llm.retry_handler import RetryHandler

        # This test ensures the last_exception path is covered
        handler = RetryHandler(max_retries=1, base_delay=0.01)

        call_count = [0]

        async def fail_once():
            call_count[0] += 1
            # Non-retryable error on first call
            raise TypeError("Not retryable")

        with pytest.raises(TypeError, match="Not retryable"):
            await handler.execute_with_retry(fail_once, "test_op")

    @pytest.mark.asyncio
    async def test_execute_single_retry_succeeds(self):
        """Test operation succeeds on single retry"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01)

        call_count = [0]

        async def succeed_second_time():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Network error")
            return "success"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(succeed_second_time, "test_op")

        assert result == "success"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_execute_api_error_retry(self):
        """Test retry on generic API error"""
        from llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01)

        call_count = [0]

        async def api_failure():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API request failed")
            return "recovered"

        with patch("llm.retry_handler.asyncio.sleep", new_callable=AsyncMock):
            result = await handler.execute_with_retry(api_failure, "api_call")

        assert result == "recovered"
