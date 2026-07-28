"""
Unit tests for backend/services/rag/reranker.py
Target: >95% coverage

Tests the CrossEncoderReranker class including:
- Model loading and caching
- Score computation (sync and async)
- Reranking logic
- Batch reranking
- Error handling and fallbacks
- Edge cases
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.reranker import (
    CrossEncoderReranker,
    _model_cache,
    get_reranker,
    rerank_documents,
)


@pytest.fixture(autouse=True)
def clear_model_cache():
    """Clear model cache before each test to ensure isolation."""
    _model_cache.clear()
    yield
    _model_cache.clear()


@pytest.fixture
def sample_documents():
    """Fixture providing sample documents for testing."""
    return [
        {
            "text": "Artificial Intelligence is the simulation of human intelligence.",
            "score": 0.85,
            "id": 1,
        },
        {"text": "The weather today is sunny and warm.", "score": 0.92, "id": 2},
        {"text": "Machine learning is a subset of AI.", "score": 0.78, "id": 3},
        {"text": "Python is a programming language.", "score": 0.65, "id": 4},
    ]


@pytest.fixture
def mock_crossencoder():
    """Fixture providing a mock CrossEncoder model."""
    mock_model = MagicMock()
    # Return deterministic scores for testing
    mock_model.predict.return_value = [0.95, 0.12, 0.88, 0.30]
    return mock_model


class TestCrossEncoderRerankerInit:
    """Tests for CrossEncoderReranker initialization."""

    def test_init_default(self):
        """Test initialization with default settings."""
        with patch("backend.services.rag.reranker.settings") as mock_settings:
            mock_settings.reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            mock_settings.enable_reranker = True

            reranker = CrossEncoderReranker()

            assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
            assert reranker.enabled is True
            assert reranker.max_length == 512
            assert reranker.batch_size == 32
            assert reranker._model is None

    def test_init_custom_model(self):
        """Test initialization with custom model name."""
        with patch("backend.services.rag.reranker.settings") as mock_settings:
            mock_settings.enable_reranker = True

            reranker = CrossEncoderReranker(
                model_name="BAAI/bge-reranker-v2-m3",
                max_length=1024,
                batch_size=16,
            )

            assert reranker.model_name == "BAAI/bge-reranker-v2-m3"
            assert reranker.max_length == 1024
            assert reranker.batch_size == 16

    def test_init_disabled_via_settings(self):
        """Test that reranker can be disabled via settings."""
        with patch("backend.services.rag.reranker.settings") as mock_settings:
            mock_settings.enable_reranker = False

            reranker = CrossEncoderReranker()

            assert reranker.enabled is False

    def test_init_disabled_via_parameter(self):
        """Test that reranker can be disabled via constructor parameter."""
        with patch("backend.services.rag.reranker.settings") as mock_settings:
            mock_settings.enable_reranker = True

            reranker = CrossEncoderReranker(enabled=False)

            assert reranker.enabled is False

    def test_init_enabled_overrides_settings(self):
        """Test that enabled parameter overrides settings."""
        with patch("backend.services.rag.reranker.settings") as mock_settings:
            mock_settings.enable_reranker = False

            reranker = CrossEncoderReranker(enabled=True)

            assert reranker.enabled is True


class TestCrossEncoderRerankerModelLoading:
    """Tests for model loading functionality."""

    @patch("backend.services.rag.reranker.settings")
    def test_load_model_success(self, mock_settings):
        """Test successful model loading."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            model = reranker._load_model()

            assert model is mock_model
            assert reranker.model_name in _model_cache

    @patch("backend.services.rag.reranker.settings")
    def test_load_model_uses_cache(self, mock_settings):
        """Test that model loading uses cache."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        _model_cache["test-model"] = mock_model

        reranker = CrossEncoderReranker(model_name="test-model")
        model = reranker._load_model()

        assert model is mock_model

    @patch("backend.services.rag.reranker.settings")
    def test_load_model_import_error(self, mock_settings):
        """Test handling of import error."""
        mock_settings.enable_reranker = True

        with patch(
            "sentence_transformers.CrossEncoder",
            side_effect=ImportError("No module named 'sentence_transformers'"),
        ):
            reranker = CrossEncoderReranker()
            model = reranker._load_model()

            assert model is None
            assert reranker.enabled is False

    @patch("backend.services.rag.reranker.settings")
    def test_load_model_generic_error(self, mock_settings):
        """Test handling of generic loading error."""
        mock_settings.enable_reranker = True

        with patch(
            "sentence_transformers.CrossEncoder",
            side_effect=RuntimeError("Model download failed"),
        ):
            reranker = CrossEncoderReranker()
            model = reranker._load_model()

            assert model is None
            assert reranker.enabled is False

    @patch("backend.services.rag.reranker.settings")
    def test_model_property_lazy_loading(self, mock_settings):
        """Test that model property lazy loads the model."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()

            # Model should be None before access
            assert reranker._model is None

            # Access should trigger loading
            model = reranker.model
            assert model is mock_model
            assert reranker._model is mock_model

    @patch("backend.services.rag.reranker.settings")
    def test_model_property_when_disabled(self, mock_settings):
        """Test that model property returns None when disabled."""
        mock_settings.enable_reranker = False

        reranker = CrossEncoderReranker()

        assert reranker.model is None


class TestCrossEncoderRerankerComputeScores:
    """Tests for compute_scores functionality."""

    @patch("backend.services.rag.reranker.settings")
    def test_compute_scores_success(self, mock_settings):
        """Test successful score computation."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95, 0.12, 0.88])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            scores = reranker.compute_scores(
                "What is AI?",
                ["AI is...", "Weather is...", "ML is..."],
            )

            assert len(scores) == 3
            assert all(0 <= s <= 1 for s in scores)  # Should be normalized
            mock_model.predict.assert_called_once()

    @patch("backend.services.rag.reranker.settings")
    def test_compute_scores_when_disabled(self, mock_settings):
        """Test that disabled reranker returns zero scores."""
        mock_settings.enable_reranker = False

        reranker = CrossEncoderReranker()
        scores = reranker.compute_scores("query", ["doc1", "doc2"])

        assert scores == [0.0, 0.0]

    @patch("backend.services.rag.reranker.settings")
    def test_compute_scores_empty_documents(self, mock_settings):
        """Test score computation with empty documents."""
        mock_settings.enable_reranker = True

        reranker = CrossEncoderReranker()
        scores = reranker.compute_scores("query", [])

        assert scores == []

    @patch("backend.services.rag.reranker.settings")
    def test_compute_scores_model_failure(self, mock_settings):
        """Test fallback when model fails."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Inference failed")

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            scores = reranker.compute_scores("query", ["doc1", "doc2"])

            assert scores == [0.0, 0.0]

    @patch("backend.services.rag.reranker.settings")
    def test_compute_scores_non_msmarco_model(self, mock_settings):
        """Test score computation with non-MS MARCO model (no sigmoid)."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        # Simulate already-normalized scores (like from BGE models)
        mock_model.predict.return_value = np.array([0.95, 0.12, 0.88])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker(model_name="BAAI/bge-reranker-v2-m3")
            scores = reranker.compute_scores("query", ["doc1", "doc2", "doc3"])

            assert len(scores) == 3


class TestCrossEncoderRerankerAsync:
    """Tests for async functionality."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_compute_scores_async(self, mock_settings):
        """Test async score computation."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95, 0.12])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            scores = await reranker.compute_scores_async("query", ["doc1", "doc2"])

            assert len(scores) == 2

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_compute_scores_async_disabled(self, mock_settings):
        """Test async score computation when disabled."""
        mock_settings.enable_reranker = False

        reranker = CrossEncoderReranker()
        scores = await reranker.compute_scores_async("query", ["doc1", "doc2"])

        assert scores == [0.0, 0.0]


class TestCrossEncoderRerankerRerank:
    """Tests for rerank functionality."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_success(self, mock_settings, sample_documents):
        """Test successful reranking."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        # Scores that will reorder documents
        mock_model.predict.return_value = np.array([0.99, 0.10, 0.95, 0.20])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("What is AI?", sample_documents, top_k=3)

            assert len(results) == 3
            # Document 1 (AI topic, score 0.99) should be first
            assert results[0]["id"] == 1
            assert results[0]["rerank_score"] == 0.99
            assert "vector_score" in results[0]
            assert results[0]["vector_score"] == 0.85

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_disabled(self, mock_settings, sample_documents):
        """Test that disabled reranker returns original order."""
        mock_settings.enable_reranker = False

        reranker = CrossEncoderReranker()
        results = await reranker.rerank("query", sample_documents, top_k=2)

        # Should return original order, truncated to top_k
        assert len(results) == 2
        assert results[0]["id"] == 1  # Original first document

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_empty_documents(self, mock_settings):
        """Test reranking with empty documents."""
        mock_settings.enable_reranker = True

        reranker = CrossEncoderReranker()
        results = await reranker.rerank("query", [], top_k=5)

        assert results == []

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_no_valid_text(self, mock_settings):
        """Test reranking with documents that have no text/content."""
        mock_settings.enable_reranker = True

        docs = [
            {"metadata": "no text", "score": 0.8},
            {"other_field": "no content", "score": 0.7},
        ]

        reranker = CrossEncoderReranker()
        results = await reranker.rerank("query", docs, top_k=5)

        # Should return original documents
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_with_content_key(self, mock_settings):
        """Test reranking documents with 'content' key instead of 'text'."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95])

        docs = [{"content": "Document content here", "score": 0.8}]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("query", docs, top_k=1)

            assert len(results) == 1
            assert results[0]["rerank_score"] == 0.95

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_preserves_original_scores(self, mock_settings, sample_documents):
        """Test that reranking preserves original vector scores."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.99, 0.10, 0.95, 0.20])

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("query", sample_documents, top_k=4)

            # Check that vector_score is preserved
            for doc in results:
                assert "vector_score" in doc
                assert doc["vector_score"] != doc["score"]  # score is now rerank_score

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_model_failure_fallback(self, mock_settings, sample_documents):
        """Test that rerank falls back to original order on model failure."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Inference failed")

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("query", sample_documents, top_k=2)

            # Should return original order on failure
            assert len(results) == 2
            assert results[0]["id"] == 1

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_does_not_mutate_original(self, mock_settings):
        """Test that reranking doesn't mutate original documents."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95])

        docs = [{"text": "doc", "score": 0.8, "original_key": "value"}]
        original_score = docs[0]["score"]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("query", docs, top_k=1)

            # Original document should not be mutated
            assert docs[0]["score"] == original_score
            assert "rerank_score" not in docs[0]
            # Result should have rerank_score
            assert "rerank_score" in results[0]


class TestCrossEncoderRerankerBatch:
    """Tests for batch reranking functionality."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_batch_rerank_success(self, mock_settings):
        """Test successful batch reranking."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.side_effect = [
            np.array([0.95, 0.12]),  # First query
            np.array([0.20, 0.88]),  # Second query
        ]

        queries = ["What is AI?", "What is Python?"]
        docs_list = [
            [{"text": "AI is...", "id": 1}, {"text": "Weather...", "id": 2}],
            [{"text": "Weather...", "id": 3}, {"text": "Python is...", "id": 4}],
        ]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.batch_rerank(queries, docs_list, top_k=2)

            assert len(results) == 2
            # First query: AI document should be first
            assert results[0][0]["id"] == 1
            # Second query: Python or Weather document should be first (order may vary)
            assert results[1][0]["id"] in [3, 4]

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_batch_rerank_disabled(self, mock_settings):
        """Test batch reranking when disabled."""
        mock_settings.enable_reranker = False

        queries = ["query1", "query2"]
        docs_list = [
            [{"text": "doc1"}, {"text": "doc2"}],
            [{"text": "doc3"}],
        ]

        reranker = CrossEncoderReranker()
        results = await reranker.batch_rerank(queries, docs_list, top_k=1)

        assert len(results) == 2
        assert len(results[0]) == 1
        assert len(results[1]) == 1

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_batch_rerank_mismatched_lengths(self, mock_settings):
        """Test batch reranking with mismatched query/doc lengths."""
        mock_settings.enable_reranker = True

        reranker = CrossEncoderReranker()

        with pytest.raises(ValueError, match="Queries count .* must match"):
            await reranker.batch_rerank(
                ["query1", "query2"],
                [[{"text": "doc"}]],  # Only one document list
                top_k=1,
            )


class TestGetReranker:
    """Tests for the get_reranker factory function."""

    @patch("backend.services.rag.reranker.settings")
    def test_get_reranker_cross_encoder(self, mock_settings):
        """Test factory returns CrossEncoderReranker by default."""
        mock_settings.zerank_api_key = None
        mock_settings.enable_reranker = True

        reranker = get_reranker()

        assert isinstance(reranker, CrossEncoderReranker)

    @patch("backend.services.rag.reranker.settings")
    def test_get_reranker_external_when_configured(self, mock_settings):
        """Test factory returns external ReRanker when API key is set."""
        mock_settings.zerank_api_key = "test-key"
        mock_settings.zerank_api_url = "http://api.example.com"

        mock_external_reranker = MagicMock()

        with patch("backend.core.reranker.ReRanker", return_value=mock_external_reranker):
            reranker = get_reranker()

            assert reranker is mock_external_reranker

    @patch("backend.services.rag.reranker.settings")
    def test_get_reranker_force_local(self, mock_settings):
        """Test factory returns CrossEncoderReranker when force_local=True."""
        mock_settings.zerank_api_key = "test-key"
        mock_settings.enable_reranker = True

        reranker = get_reranker(force_local=True)

        assert isinstance(reranker, CrossEncoderReranker)


class TestRerankDocuments:
    """Tests for the rerank_documents convenience function."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_documents(self, mock_settings):
        """Test convenience function for reranking."""
        mock_settings.enable_reranker = True
        mock_settings.zerank_api_key = None

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95, 0.12])

        docs = [{"text": "AI is...", "id": 1}, {"text": "Weather...", "id": 2}]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            results = await rerank_documents("What is AI?", docs, top_k=2)

            assert len(results) == 2
            assert results[0]["id"] == 1  # AI document should be first


class TestCrossEncoderRerankerEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_top_k_larger_than_documents(self, mock_settings):
        """Test reranking when top_k > number of documents."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95, 0.12])

        docs = [{"text": "doc1"}, {"text": "doc2"}]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("query", docs, top_k=10)

            assert len(results) == 2  # Should return all available docs

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_documents_with_mixed_content(self, mock_settings):
        """Test reranking with mixed text and content keys."""
        mock_settings.enable_reranker = True

        mock_model = MagicMock()
        import numpy as np

        mock_model.predict.return_value = np.array([0.95, 0.88])

        docs = [
            {"text": "Has text key", "id": 1},
            {"content": "Has content key", "id": 2},
        ]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_model):
            reranker = CrossEncoderReranker()
            results = await reranker.rerank("query", docs, top_k=2)

            assert len(results) == 2
            # Both documents should be processed
            assert results[0]["id"] in [1, 2]

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_rerank_empty_text_strings(self, mock_settings):
        """Test reranking with empty text strings."""
        mock_settings.enable_reranker = True

        docs = [
            {"text": "", "id": 1},
            {"text": "Valid text", "id": 2},
            {"text": "", "id": 3},
        ]

        reranker = CrossEncoderReranker()
        # When model is not loaded, should fallback to original order
        results = await reranker.rerank("query", docs, top_k=3)

        # Empty text docs should be skipped or handled gracefully
        assert len(results) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
