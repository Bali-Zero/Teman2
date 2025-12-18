"""
Unit tests for RetryHandler
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.retry_handler import RetryHandler


@pytest.mark.asyncio
async def test_retry_handler_success_first_attempt():
    """Test RetryHandler with successful first attempt"""
    handler = RetryHandler(max_retries=3, base_delay=0.1)

    async def operation():
        return "success"

    result = await handler.execute_with_retry(operation, "test_operation")
    assert result == "success"


@pytest.mark.asyncio
async def test_retry_handler_retry_on_retryable_error():
    """Test RetryHandler retries on retryable errors"""
    handler = RetryHandler(max_retries=3, base_delay=0.1)
    call_count = 0

    async def operation():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("Connection timeout")
        return "success"

    result = await handler.execute_with_retry(operation, "test_operation")
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_handler_max_retries_exceeded():
    """Test RetryHandler raises after max retries"""
    handler = RetryHandler(max_retries=2, base_delay=0.1)

    async def operation():
        raise ConnectionError("Connection timeout")

    with pytest.raises(ConnectionError):
        await handler.execute_with_retry(operation, "test_operation")


@pytest.mark.asyncio
async def test_retry_handler_non_retryable_error():
    """Test RetryHandler doesn't retry on non-retryable errors"""
    handler = RetryHandler(max_retries=3, base_delay=0.1)
    call_count = 0

    async def operation():
        nonlocal call_count
        call_count += 1
        raise ValueError("Non-retryable error")

    with pytest.raises(ValueError):
        await handler.execute_with_retry(operation, "test_operation")

    # Should only be called once (no retries for non-retryable errors)
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_handler_custom_retryable_errors():
    """Test RetryHandler with custom retryable errors"""
    handler = RetryHandler(max_retries=3, base_delay=0.1)
    call_count = 0

    async def operation():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("Custom retryable error")
        return "success"

    result = await handler.execute_with_retry(
        operation, "test_operation", retryable_errors=["custom"]
    )
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_handler_exponential_backoff():
    """Test RetryHandler uses exponential backoff"""
    handler = RetryHandler(max_retries=3, base_delay=0.1, backoff_factor=2)
    delays = []

    original_sleep = asyncio.sleep

    async def mock_sleep(delay):
        delays.append(delay)
        await original_sleep(0)  # Don't actually wait

    async def operation():
        raise ConnectionError("Connection timeout")

    with patch("asyncio.sleep", side_effect=mock_sleep), pytest.raises(ConnectionError):
        await handler.execute_with_retry(operation, "test_operation")

    # Should have delays: 0.1 * 2^0 = 0.1, 0.1 * 2^1 = 0.2
    assert len(delays) == 2
    assert delays[0] == pytest.approx(0.1)
    assert delays[1] == pytest.approx(0.2)










