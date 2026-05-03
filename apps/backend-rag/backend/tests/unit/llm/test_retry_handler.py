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

    def test_is_retryable_error_connection(self):
        """Test retryable error detection - connection (via keywords)"""
        assert "connection" in RETRYABLE_ERROR_KEYWORDS

    def test_is_retryable_error_timeout(self):
        """Test retryable error detection - timeout (via keywords)"""
        assert "timeout" in RETRYABLE_ERROR_KEYWORDS

    def test_is_retryable_error_rate_limit(self):
        """Test retryable error detection - rate limit (via keywords)"""
        assert "rate" in RETRYABLE_ERROR_KEYWORDS

    def test_is_retryable_error_503(self):
        """Test retryable error detection - 503 (via keywords)"""
        assert "503" in RETRYABLE_ERROR_KEYWORDS

    def test_is_retryable_error_non_retryable(self):
        """Test non-retryable error - invalid input has no retry keywords"""
        error_msg = "invalid input".lower()
        assert not any(kw in error_msg for kw in RETRYABLE_ERROR_KEYWORDS)

    @pytest.mark.asyncio
    async def test_execute_success(self, retry_handler):
        """Test successful execution without retries"""

        async def func():
            return "success"

        result = await retry_handler.execute_with_retry(func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retries(self, retry_handler):
        """Test execution with retries - connection error is retried"""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("connection error")
            return "success"

        result = await retry_handler.execute_with_retry(func)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_max_retries_exceeded(self, retry_handler):
        """Test execution when max retries exceeded"""

        async def func():
            raise Exception("connection error")

        with pytest.raises(Exception, match="connection error"):
            await retry_handler.execute_with_retry(func)

    @pytest.mark.asyncio
    async def test_execute_non_retryable_error(self, retry_handler):
        """Test execution with non-retryable error - fails immediately"""

        async def func():
            raise ValueError("invalid input")

        with pytest.raises(ValueError, match="invalid input"):
            await retry_handler.execute_with_retry(func)

    def test_retryable_error_keywords(self):
        """Test retryable error keywords"""
        assert len(RETRYABLE_ERROR_KEYWORDS) > 0
        assert "connection" in RETRYABLE_ERROR_KEYWORDS
        assert "timeout" in RETRYABLE_ERROR_KEYWORDS
        assert "rate" in RETRYABLE_ERROR_KEYWORDS
