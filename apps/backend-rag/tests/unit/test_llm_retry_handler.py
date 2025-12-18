"""
Unit tests for RetryHandler - Exponential backoff retry logic
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.llm.retry_handler import RETRYABLE_ERROR_KEYWORDS, RetryHandler


class TestRetryHandler:
    """Test suite for RetryHandler class"""

    def test_init_default_parameters(self):
        """Test initialization with default parameters"""
        handler = RetryHandler()

        assert handler.max_retries == 3
        assert handler.base_delay == 2.0
        assert handler.backoff_factor == 2

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters"""
        handler = RetryHandler(max_retries=5, base_delay=1.0, backoff_factor=3)

        assert handler.max_retries == 5
        assert handler.base_delay == 1.0
        assert handler.backoff_factor == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self):
        """Test successful operation on first attempt"""
        handler = RetryHandler()
        mock_operation = AsyncMock(return_value="success")

        result = await handler.execute_with_retry(
            operation=mock_operation, operation_name="test_op"
        )

        assert result == "success"
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retries(self):
        """Test successful operation after retries"""
        handler = RetryHandler()
        mock_operation = AsyncMock(
            side_effect=[
                Exception("Connection timeout"),  # First attempt fails
                Exception("API rate limit"),  # Second attempt fails
                "success",  # Third attempt succeeds
            ]
        )

        result = await handler.execute_with_retry(
            operation=mock_operation, operation_name="test_op"
        )

        assert result == "success"
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self):
        """Test operation fails after all retries"""
        handler = RetryHandler(max_retries=3)
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(Exception, match="Connection timeout"):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable_error(self):
        """Test non-retryable error fails immediately"""
        handler = RetryHandler()
        mock_operation = AsyncMock(
            side_effect=Exception("Invalid input")  # Not a retryable error
        )

        with pytest.raises(Exception, match="Invalid input"):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        # Should fail immediately without retry
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_exponential_backoff(self):
        """Test exponential backoff delays"""
        handler = RetryHandler(max_retries=3, base_delay=1.0, backoff_factor=2)
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch("asyncio.sleep") as mock_sleep:
            with pytest.raises(Exception):
                await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

            # Check exponential backoff: 1.0, 2.0 (two sleeps for 3 attempts)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1.0)  # 1.0 * (2^0) = 1.0
            mock_sleep.assert_any_call(2.0)  # 1.0 * (2^1) = 2.0

    @pytest.mark.asyncio
    async def test_execute_with_retry_custom_retryable_errors(self):
        """Test with custom retryable error keywords"""
        handler = RetryHandler()
        mock_operation = AsyncMock(side_effect=Exception("Custom error"))

        with pytest.raises(Exception, match="Custom error"):
            await handler.execute_with_retry(
                operation=mock_operation, operation_name="test_op", retryable_errors=["custom"]
            )

        # Should fail immediately - "custom error" doesn't match "custom" (case-sensitive)
        # Wait, the code uses .lower(), so it should match
        # Let me reconsider...
        # error_msg = str(e).lower() -> "custom error"
        # "custom" in "custom error" -> True
        # So it should retry

        # Actually, it should retry and fail after max retries
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_empty_retryable_errors(self):
        """Test with empty retryable errors list"""
        handler = RetryHandler()
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(Exception, match="Connection timeout"):
            await handler.execute_with_retry(
                operation=mock_operation,
                operation_name="test_op",
                retryable_errors=[],  # No retryable errors
            )

        # Should fail immediately
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_default_retryable_keywords(self):
        """Test that default retryable keywords work"""
        handler = RetryHandler()

        # Test each default keyword
        for keyword in RETRYABLE_ERROR_KEYWORDS:
            mock_operation = AsyncMock(side_effect=Exception(f"Error with {keyword}"))

            with pytest.raises(Exception):
                await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

            # Should retry (fail after max_retries)
            assert mock_operation.call_count == 3
            mock_operation.reset_mock()

    @pytest.mark.asyncio
    async def test_execute_with_retry_case_insensitive(self):
        """Test error matching is case-insensitive"""
        handler = RetryHandler()
        mock_operation = AsyncMock(
            side_effect=Exception("CONNECTION TIMEOUT")  # Uppercase
        )

        with pytest.raises(Exception):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        # Should match "connection" keyword (case-insensitive)
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_operation_name_logging(self):
        """Test that operation name is used in logging"""
        handler = RetryHandler()
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch("backend.llm.retry_handler.logger") as mock_logger:
            with pytest.raises(Exception):
                await handler.execute_with_retry(
                    operation=mock_operation, operation_name="custom_operation"
                )

            # Check that operation name appears in logs
            assert any(
                "custom_operation" in str(call) for call in mock_logger.warning.call_args_list
            )

    @pytest.mark.asyncio
    async def test_execute_with_retry_zero_max_retries(self):
        """Test with max_retries=0 (no retries)"""
        handler = RetryHandler(max_retries=0)
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(Exception, match="Connection timeout"):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        # Should not retry
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_large_backoff_factor(self):
        """Test with large backoff factor"""
        handler = RetryHandler(max_retries=3, base_delay=1.0, backoff_factor=10)
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch("asyncio.sleep") as mock_sleep:
            with pytest.raises(Exception):
                await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

            # Check backoff: 1.0 * 10^0 = 1.0, 1.0 * 10^1 = 10.0
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(10.0)

    @pytest.mark.asyncio
    async def test_execute_with_retry_fractional_delay(self):
        """Test with fractional base delay"""
        handler = RetryHandler(max_retries=2, base_delay=0.5, backoff_factor=2)
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch("asyncio.sleep") as mock_sleep:
            with pytest.raises(Exception):
                await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

            # Check backoff: 0.5 * 2^0 = 0.5
            mock_sleep.assert_called_once_with(0.5)

    @pytest.mark.asyncio
    async def test_execute_with_retry_returns_correct_value(self):
        """Test that correct return value is passed through"""
        handler = RetryHandler()
        expected_result = {"status": "success", "data": [1, 2, 3]}
        mock_operation = AsyncMock(return_value=expected_result)

        result = await handler.execute_with_retry(
            operation=mock_operation, operation_name="test_op"
        )

        assert result == expected_result

    @pytest.mark.asyncio
    async def test_execute_with_retry_returns_none(self):
        """Test that None return value is handled correctly"""
        handler = RetryHandler()
        mock_operation = AsyncMock(return_value=None)

        result = await handler.execute_with_retry(
            operation=mock_operation, operation_name="test_op"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_with_retry_multiple_error_keywords(self):
        """Test error matching with multiple keywords"""
        handler = RetryHandler()

        # Error containing multiple keywords
        mock_operation = AsyncMock(side_effect=Exception("Network connection timeout"))

        with pytest.raises(Exception):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        # Should match both "network" and "connection" and "timeout"
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_error_503(self):
        """Test retry on 503 Service Unavailable"""
        handler = RetryHandler()
        mock_operation = AsyncMock(side_effect=Exception("HTTP 503 Service Unavailable"))

        with pytest.raises(Exception):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_error_429(self):
        """Test retry on 429 Rate Limit"""
        handler = RetryHandler()
        mock_operation = AsyncMock(side_effect=Exception("HTTP 429 Too Many Requests"))

        with pytest.raises(Exception):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_partial_match(self):
        """Test error keyword partial matching"""
        handler = RetryHandler()
        mock_operation = AsyncMock(
            side_effect=Exception("disconnection error")  # Contains "connection"
        )

        with pytest.raises(Exception):
            await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

        # Should match "connection" keyword
        assert mock_operation.call_count == 3

    def test_retryable_error_keywords_constant(self):
        """Test RETRYABLE_ERROR_KEYWORDS constant"""
        expected_keywords = [
            "connection",
            "timeout",
            "network",
            "api",
            "rate",
            "server",
            "unavailable",
            "503",
            "502",
            "429",
        ]

        assert expected_keywords == RETRYABLE_ERROR_KEYWORDS

    @pytest.mark.asyncio
    async def test_execute_with_retry_logging_attempts(self):
        """Test that retry attempts are logged correctly"""
        handler = RetryHandler(max_retries=3)
        mock_operation = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch("backend.llm.retry_handler.logger") as mock_logger:
            with pytest.raises(Exception):
                await handler.execute_with_retry(operation=mock_operation, operation_name="test_op")

            # Should log warning for first 2 attempts, error for last
            assert mock_logger.warning.call_count == 2
            assert mock_logger.error.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_retry_async_operation(self):
        """Test with actual async operation"""
        handler = RetryHandler()
        call_count = 0

        async def async_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Connection timeout")
            return "success"

        result = await handler.execute_with_retry(
            operation=async_operation, operation_name="test_op"
        )

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_different_exceptions(self):
        """Test with different exception types"""
        handler = RetryHandler()
        mock_operation = AsyncMock(
            side_effect=[
                ConnectionError("Network error"),  # Retryable
                TimeoutError("Timeout"),  # Retryable
                "success",
            ]
        )

        result = await handler.execute_with_retry(
            operation=mock_operation, operation_name="test_op"
        )

        assert result == "success"
        assert mock_operation.call_count == 3
