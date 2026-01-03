"""
Unit tests for QdrantErrorClassifier in core/qdrant_db.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.qdrant_db import QdrantErrorClassifier, QdrantErrorType


class TestQdrantErrorClassifier:
    """Tests for QdrantErrorClassifier"""

    def test_init(self):
        """Test QdrantErrorClassifier initialization"""
        classifier = QdrantErrorClassifier()
        assert {500, 502, 503, 504} == classifier.RETRYABLE_STATUS_CODES
        assert {400, 401, 403, 404, 422} == classifier.NON_RETRYABLE_STATUS_CODES

    def test_classify_timeout_exception(self):
        """Test classifying TimeoutException"""
        classifier = QdrantErrorClassifier()
        error = httpx.TimeoutException("Request timeout")
        error_type, retryable = classifier.classify(error)

        assert error_type == QdrantErrorType.TIMEOUT
        assert retryable is True

    def test_classify_connect_error(self):
        """Test classifying ConnectError"""
        classifier = QdrantErrorClassifier()
        error = httpx.ConnectError("Connection failed")
        error_type, retryable = classifier.classify(error)

        assert error_type == QdrantErrorType.CONNECTION
        assert retryable is True

    def test_classify_retryable_status_code(self):
        """Test classifying retryable HTTP status codes"""
        classifier = QdrantErrorClassifier()

        for status_code in [500, 502, 503, 504]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

            error_type, retryable = classifier.classify(error)

            assert error_type == QdrantErrorType.SERVER_ERROR
            assert retryable is True

    def test_classify_non_retryable_status_code(self):
        """Test classifying non-retryable HTTP status codes"""
        classifier = QdrantErrorClassifier()

        for status_code in [400, 401, 403, 404, 422]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            error = httpx.HTTPStatusError("Client error", request=MagicMock(), response=mock_response)

            error_type, retryable = classifier.classify(error)

            assert error_type == QdrantErrorType.CLIENT_ERROR
            assert retryable is False

    def test_classify_unknown_status_code(self):
        """Test classifying unknown HTTP status code"""
        classifier = QdrantErrorClassifier()

        mock_response = MagicMock()
        mock_response.status_code = 418  # Unknown status code
        error = httpx.HTTPStatusError("Unknown error", request=MagicMock(), response=mock_response)

        error_type, retryable = classifier.classify(error)

        assert error_type == QdrantErrorType.SERVER_ERROR
        assert retryable is False  # Conservative approach

    def test_classify_unknown_exception(self):
        """Test classifying unknown exception type"""
        classifier = QdrantErrorClassifier()
        error = ValueError("Unknown error")

        error_type, retryable = classifier.classify(error)

        assert error_type == QdrantErrorType.NON_RETRYABLE
        assert retryable is False


class TestQdrantMetrics:
    """Tests for Qdrant metrics functions"""

    def test_get_qdrant_metrics_empty(self):
        """Test getting metrics when no operations performed"""
        from core.qdrant_db import _qdrant_metrics, get_qdrant_metrics

        # Reset metrics
        original = _qdrant_metrics.copy()
        _qdrant_metrics.update({
            "search_calls": 0,
            "search_total_time": 0.0,
            "upsert_calls": 0,
            "upsert_total_time": 0.0,
            "upsert_documents_total": 0,
            "retry_count": 0,
            "errors": 0,
        })

        try:
            metrics = get_qdrant_metrics()

            assert metrics["search_calls"] == 0
            assert metrics["search_avg_time_ms"] == 0.0
            assert metrics["upsert_calls"] == 0
            assert metrics["upsert_avg_time_ms"] == 0.0
            assert metrics["upsert_avg_docs_per_call"] == 0.0
        finally:
            _qdrant_metrics.update(original)

    def test_get_qdrant_metrics_with_data(self):
        """Test getting metrics with operation data"""
        from core.qdrant_db import _qdrant_metrics, get_qdrant_metrics

        # Save original
        original = _qdrant_metrics.copy()

        # Set test data
        _qdrant_metrics.update({
            "search_calls": 10,
            "search_total_time": 5.0,  # 5 seconds total
            "upsert_calls": 5,
            "upsert_total_time": 2.5,  # 2.5 seconds total
            "upsert_documents_total": 100,
            "retry_count": 2,
            "errors": 1,
        })

        try:
            metrics = get_qdrant_metrics()

            assert metrics["search_calls"] == 10
            assert metrics["search_avg_time_ms"] == 500.0  # 5.0 / 10 * 1000
            assert metrics["upsert_calls"] == 5
            assert metrics["upsert_avg_time_ms"] == 500.0  # 2.5 / 5 * 1000
            assert metrics["upsert_avg_docs_per_call"] == 20.0  # 100 / 5
            assert metrics["retry_count"] == 2
            assert metrics["errors"] == 1
        finally:
            _qdrant_metrics.update(original)


class TestRetryWithBackoff:
    """Tests for _retry_with_backoff function"""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test retry succeeds on first attempt"""
        from core.qdrant_db import _retry_with_backoff

        async def success_func():
            return "success"

        result = await _retry_with_backoff(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_retries(self):
        """Test retry succeeds after some failures"""
        from core.qdrant_db import _retry_with_backoff

        attempts = []

        async def retry_func():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await _retry_with_backoff(retry_func, max_retries=3)
        assert result == "success"
        assert len(attempts) == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry raises exception when all retries exhausted"""
        from core.qdrant_db import _retry_with_backoff

        async def fail_func():
            raise ValueError("Persistent error")

        with pytest.raises(ValueError):
            await _retry_with_backoff(fail_func, max_retries=2)

    @pytest.mark.asyncio
    async def test_retry_with_backoff_delay(self):
        """Test that retry uses exponential backoff"""
        import asyncio

        from core.qdrant_db import _retry_with_backoff

        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.001)  # Small delay for test

        attempts = []

        async def retry_func():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("Error")
            return "success"

        with patch("asyncio.sleep", mock_sleep):
            result = await _retry_with_backoff(retry_func, max_retries=2, base_delay=0.1)

        assert result == "success"
        # Should have one delay (after first failure)
        assert len(delays) >= 1




