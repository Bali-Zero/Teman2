"""
Unit tests for RetryHandler
Target: 100% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.retry_handler import RETRYABLE_ERROR_KEYWORDS, RetryHandler


@pytest.fixture
def retry_handler():
    """Create RetryHandler instance"""
    return RetryHandler(max_retries=3, base_delay=0.1, backoff_factor=2)


class TestRetryHandler:
    """Tests for RetryHandler"""

    def test_init(self):
        """Test initialization"""
        handler = RetryHandler()
        assert handler.max_retries == 3
        assert handler.base_delay == 2.0
        assert handler.backoff_factor == 2

    def test_init_custom(self):
        """Test initialization with custom parameters"""
        handler = RetryHandler(max_retries=5, base_delay=1.0, backoff_factor=3)
        assert handler.max_retries == 5
        assert handler.base_delay == 1.0
        assert handler.backoff_factor == 3

    def test_is_retryable_error_connection(self, retry_handler):
        """Test retryable error detection - connection"""
        error = Exception("connection error")
        assert retry_handler.is_retryable_error(error) is True

    def test_is_retryable_error_timeout(self, retry_handler):
        """Test retryable error detection - timeout"""
        error = Exception("timeout occurred")
        assert retry_handler.is_retryable_error(error) is True

    def test_is_retryable_error_rate_limit(self, retry_handler):
        """Test retryable error detection - rate limit"""
        error = Exception("rate limit exceeded")
        assert retry_handler.is_retryable_error(error) is True

    def test_is_retryable_error_503(self, retry_handler):
        """Test retryable error detection - 503"""
        error = Exception("503 service unavailable")
        assert retry_handler.is_retryable_error(error) is True

    def test_is_retryable_error_non_retryable(self, retry_handler):
        """Test non-retryable error"""
        error = ValueError("invalid input")
        assert retry_handler.is_retryable_error(error) is False

    @pytest.mark.asyncio
    async def test_execute_success(self, retry_handler):
        """Test successful execution without retries"""

        async def func():
            return "success"

        result = await retry_handler.execute(func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retries(self, retry_handler):
        """Test execution with retries"""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("connection error")
            return "success"

        result = await retry_handler.execute(func)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_max_retries_exceeded(self, retry_handler):
        """Test execution when max retries exceeded"""

        async def func():
            raise Exception("connection error")

        with pytest.raises(Exception, match="connection error"):
            await retry_handler.execute(func)

    @pytest.mark.asyncio
    async def test_execute_non_retryable_error(self, retry_handler):
        """Test execution with non-retryable error"""

        async def func():
            raise ValueError("invalid input")

        with pytest.raises(ValueError, match="invalid input"):
            await retry_handler.execute(func)

    def test_retryable_error_keywords(self):
        """Test retryable error keywords"""
        assert len(RETRYABLE_ERROR_KEYWORDS) > 0
        assert "connection" in RETRYABLE_ERROR_KEYWORDS
        assert "timeout" in RETRYABLE_ERROR_KEYWORDS
        assert "rate" in RETRYABLE_ERROR_KEYWORDS
