"""
Tests for Qdrant error classification.

Tests the new error handling features:
- Error type classification
- Retryable vs non-retryable errors
- HTTP status code handling
"""

import pytest
from unittest.mock import MagicMock
import httpx

from backend.core.qdrant_db import QdrantErrorClassifier, QdrantErrorType


@pytest.fixture
def classifier():
    """Create QdrantErrorClassifier instance."""
    return QdrantErrorClassifier()


def test_classify_timeout_error(classifier):
    """Test that timeout errors are classified correctly."""
    error = httpx.TimeoutException("Timeout")
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.TIMEOUT
    assert retryable == True


def test_classify_connection_error(classifier):
    """Test that connection errors are classified correctly."""
    error = httpx.ConnectError("Connection failed")
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.CONNECTION
    assert retryable == True


def test_classify_client_error(classifier):
    """Test that client errors (4xx) are classified correctly."""
    response = MagicMock()
    response.status_code = 400
    error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=response)
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.CLIENT_ERROR
    assert retryable == False


def test_classify_server_error_retryable(classifier):
    """Test that server errors (5xx) are classified as retryable."""
    response = MagicMock()
    response.status_code = 500
    error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.SERVER_ERROR
    assert retryable == True


def test_classify_502_error_retryable(classifier):
    """Test that 502 errors are retryable."""
    response = MagicMock()
    response.status_code = 502
    error = httpx.HTTPStatusError("Bad gateway", request=MagicMock(), response=response)
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.SERVER_ERROR
    assert retryable == True


def test_classify_404_error_non_retryable(classifier):
    """Test that 404 errors are non-retryable."""
    response = MagicMock()
    response.status_code = 404
    error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=response)
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.CLIENT_ERROR
    assert retryable == False


def test_classify_unknown_error_non_retryable(classifier):
    """Test that unknown errors are non-retryable by default."""
    error = ValueError("Unknown error")
    error_type, retryable = classifier.classify(error)
    
    assert error_type == QdrantErrorType.NON_RETRYABLE
    assert retryable == False





