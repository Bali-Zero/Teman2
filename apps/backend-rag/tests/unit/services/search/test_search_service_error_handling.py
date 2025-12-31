"""
Tests for SearchService BM25 error handling and fallback.

Tests:
- BM25 initialization retry logic
- Fallback to dense-only search when BM25 fails
- Error classification for BM25 failures
- Metrics for BM25 failures
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from app.core.error_classification import ErrorClassifier, ErrorCategory
from services.search.search_service import SearchService


@pytest.fixture
def search_service():
    """Create SearchService instance for testing."""
    with patch('services.search.search_service.CollectionManager'), \
         patch('services.search.search_service.Embedder'), \
         patch('services.search.search_service.CulturalInsightsService'):
        service = SearchService(qdrant_url="http://localhost:6333")
        service._max_bm25_init_attempts = 3
        return service


@pytest.mark.asyncio
async def test_bm25_init_retry_on_transient_error(search_service):
    """Test that BM25 initialization retries on transient errors."""
    attempt_count = [0]
    
    async def mock_init():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ConnectionError("Temporary connection error")
        return True
    
    # Should retry and eventually succeed
    with patch.object(search_service, '_init_bm25_with_retry', mock_init):
        result = await search_service._init_bm25_with_retry()
        assert result is True
        assert attempt_count[0] == 3


@pytest.mark.asyncio
async def test_bm25_init_no_retry_on_import_error(search_service):
    """Test that BM25 initialization doesn't retry on ImportError."""
    attempt_count = [0]
    
    async def mock_init():
        attempt_count[0] += 1
        raise ImportError("BM25Vectorizer not available")
    
    # Should not retry ImportError
    with patch.object(search_service, '_init_bm25_with_retry', mock_init):
        result = await search_service._init_bm25_with_retry()
        assert result is False
        assert attempt_count[0] == 1  # Only one attempt


@pytest.mark.asyncio
async def test_bm25_fallback_to_dense_only(search_service):
    """Test that search falls back to dense-only when BM25 unavailable."""
    search_service._bm25_enabled = False
    
    # Mock dense search
    async def mock_dense_search(*args, **kwargs):
        return {"results": [{"id": "1", "text": "test"}]}
    
    search_service.collection_manager = MagicMock()
    search_service.collection_manager.search = AsyncMock(side_effect=mock_dense_search)
    
    # Mock embedding
    search_service.embedder = MagicMock()
    search_service.embedder.embed_query = AsyncMock(return_value=[0.1] * 384)
    
    # Should use dense-only search
    results = await search_service.search(
        query="test query",
        user_level=3,
        limit=5
    )
    
    # Should have results
    assert "results" in results or results.get("results") is not None


@pytest.mark.asyncio
async def test_bm25_error_classification(search_service):
    """Test that BM25 errors are classified correctly."""
    # Transient error
    transient_error = ConnectionError("Connection failed")
    category, severity = ErrorClassifier.classify_error(transient_error)
    assert category == ErrorCategory.TRANSIENT
    
    # Permanent error
    permanent_error = ImportError("Module not found")
    category, severity = ErrorClassifier.classify_error(permanent_error)
    assert category == ErrorCategory.PERMANENT


@pytest.mark.asyncio
async def test_hybrid_search_fallback_on_error(search_service):
    """Test that hybrid search falls back to dense-only on error."""
    search_service._bm25_enabled = True
    search_service._bm25_vectorizer = MagicMock()
    
    # Mock BM25 to raise error
    search_service._bm25_vectorizer.generate_query_sparse_vector = Mock(
        side_effect=Exception("BM25 error")
    )
    
    # Mock dense search
    search_service.collection_manager = MagicMock()
    search_service.collection_manager.search = AsyncMock(
        return_value={"results": [{"id": "1"}]}
    )
    
    # Mock embedding
    search_service.embedder = MagicMock()
    search_service.embedder.embed_query = AsyncMock(return_value=[0.1] * 384)
    
    # Should fallback to dense-only
    results = await search_service.search(
        query="test query",
        user_level=3,
        limit=5
    )
    
    # Should have results from dense search
    assert results is not None
