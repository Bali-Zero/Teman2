"""
Unit tests for core/embeddings.py (Refactored for Async)
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.embeddings import (
    EmbeddingsGenerator,
    create_embeddings_generator,
    generate_embeddings,
)


class TestEmbeddingsGenerator:
    """Tests for EmbeddingsGenerator"""

    @patch("sentence_transformers.SentenceTransformer")
    def test_init_sentence_transformers(self, mock_st):
        """Test initialization with sentence-transformers"""
        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        assert generator.provider == "sentence-transformers"
        assert generator.dimensions == 384

    @patch("openai.AsyncOpenAI")
    def test_init_openai_with_key(self, mock_openai_class):
        """Test initialization with OpenAI and API key"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        generator = EmbeddingsGenerator(provider="openai", api_key="test-key")
        assert generator.provider == "openai"
        assert generator.model == "text-embedding-3-small"
        assert generator.dimensions == 1536

    @patch("backend.core.embeddings._default_settings", None)
    def test_init_openai_no_key(self):
        """Test initialization with OpenAI without API key"""
        with patch("openai.AsyncOpenAI"), pytest.raises(ValueError, match="API key"):
            EmbeddingsGenerator(provider="openai", api_key=None)

    @patch("sentence_transformers.SentenceTransformer")
    def test_init_default_provider(self, mock_st):
        """Test initialization with default provider"""
        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator()
        # May be sentence-transformers or openai depending on availability
        assert generator.provider in ["sentence-transformers", "openai"]

    @patch("sentence_transformers.SentenceTransformer", side_effect=ImportError("Not available"))
    @patch("backend.core.embeddings._default_settings", None)
    def test_init_sentence_transformers_fallback_to_openai(self, mock_st):
        """Test fallback to OpenAI when Sentence Transformers unavailable"""
        # Will try to fallback to OpenAI but fail without API key
        with pytest.raises(ValueError, match="API key"):
            EmbeddingsGenerator(provider="sentence-transformers")

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_embeddings_empty(self, mock_st):
        """Test generating embeddings for empty list"""
        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        result = await generator.generate_embeddings([])
        assert result == []

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_embeddings_sentence_transformers(self, mock_st):
        """Test generating embeddings with sentence-transformers"""
        import numpy as np

        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        result = await generator.generate_embeddings(["text1", "text2"])
        assert len(result) == 2
        assert len(result[0]) == 384

    @pytest.mark.asyncio
    @patch("openai.AsyncOpenAI")
    async def test_generate_embeddings_openai(self, mock_openai_class):
        """Test generating embeddings with OpenAI"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.embedding = [0.1] * 1536
        mock_item2 = MagicMock()
        mock_item2.embedding = [0.2] * 1536
        mock_response.data = [mock_item1, mock_item2]

        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        generator = EmbeddingsGenerator(provider="openai", api_key="test-key")
        # Use unique texts to avoid cache hit from other tests
        result = await generator.generate_embeddings(["openai_test_1", "openai_test_2"])
        assert len(result) == 2
        assert len(result[0]) == 1536

    @pytest.mark.asyncio
    @patch("openai.AsyncOpenAI")
    async def test_generate_embeddings_openai_batch(self, mock_openai_class):
        """Test OpenAI batching for large requests"""
        mock_client = MagicMock()

        # Create responses for multiple batches
        def create_batch_response(batch_size):
            mock_response = MagicMock()
            mock_items = []
            for _i in range(batch_size):
                mock_item = MagicMock()
                mock_item.embedding = [0.1] * 1536
                mock_items.append(mock_item)
            mock_response.data = mock_items
            return mock_response

        # Mock to return different responses for each batch
        mock_client.embeddings.create = AsyncMock(
            side_effect=[
                create_batch_response(2048),  # First batch
                create_batch_response(952),  # Second batch (3000 - 2048)
            ],
        )
        mock_openai_class.return_value = mock_client

        generator = EmbeddingsGenerator(provider="openai", api_key="test-key")
        texts = ["text"] * 3000  # Larger than MAX_BATCH_SIZE
        result = await generator.generate_embeddings(texts)
        assert len(result) == 3000
        assert mock_client.embeddings.create.call_count == 2  # Should batch into 2 calls

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_single_embedding(self, mock_st):
        """Test generating single embedding"""
        import numpy as np

        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.encode.return_value = np.array([[0.1] * 384])
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        result = await generator.generate_single_embedding("test text")
        assert len(result) == 384

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_query_embedding(self, mock_st):
        """Test generating query embedding"""
        import numpy as np

        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.encode.return_value = np.array([[0.1] * 384])
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        result = await generator.generate_query_embedding("query")
        assert len(result) == 384

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_batch_embeddings(self, mock_st):
        """Test generate_batch_embeddings alias"""
        import numpy as np

        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.encode.return_value = np.array([[0.1] * 384])
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        result = await generator.generate_batch_embeddings(["text"])
        assert len(result) == 1

    def test_get_model_info_openai(self):
        """Test getting model info for OpenAI"""
        with patch("openai.AsyncOpenAI"):
            generator = EmbeddingsGenerator(provider="openai", api_key="test-key")
            info = generator.get_model_info()
            assert info["provider"] == "openai"
            assert info["cost"] == "Paid (OpenAI API)"

    @patch("sentence_transformers.SentenceTransformer")
    def test_get_model_info_sentence_transformers(self, mock_st):
        """Test getting model info for sentence-transformers"""
        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        info = generator.get_model_info()
        assert info["provider"] == "sentence-transformers"
        assert info["cost"] == "FREE (Local)"

    @patch("sentence_transformers.SentenceTransformer")
    def test_create_embeddings_generator(self, mock_st):
        """Test factory function"""
        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_transformer

        generator = create_embeddings_generator()
        assert generator is not None
        assert hasattr(generator, "provider")
        assert hasattr(generator, "generate_embeddings")

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_embeddings_function(self, mock_st):
        """Test convenience function - uses sentence-transformers when no api_key"""
        import numpy as np

        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.encode.return_value = np.array([[0.1] * 384])
        mock_st.return_value = mock_transformer

        mock_settings = MagicMock()
        mock_settings.embedding_provider = "sentence-transformers"
        mock_settings.embedding_model = None
        mock_settings.openai_api_key = None
        with patch("backend.core.embeddings._default_settings", mock_settings):
            result = await generate_embeddings(["test_func_unique"], api_key=None)
        assert len(result) == 1
        assert len(result[0]) == 384

    @pytest.mark.asyncio
    @patch("sentence_transformers.SentenceTransformer")
    async def test_generate_embeddings_error_handling(self, mock_st):
        """Test error handling in generate_embeddings.

        NOTE (cicatrix scar 2026-05-10): generate_embeddings now RAISES on
        error instead of returning [] silently. The previous silent-swallow
        produced downstream length-mismatch errors in upsert.
        """
        mock_transformer = MagicMock()
        mock_transformer.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.encode.side_effect = Exception("Encoding error")
        mock_st.return_value = mock_transformer

        generator = EmbeddingsGenerator(provider="sentence-transformers")
        await generator.clear_cache()  # prevent cache hit masking the error
        with pytest.raises(Exception, match="Encoding error"):
            await generator.generate_embeddings(["test"])


# ─────────────────────────────────────────────────────────────────────
# Token-aware sub-batching tests (cicatrix scar 2026-05-10)
# OpenAI text-embedding-3-small limits: 300k tokens/request, 8192 tokens/input
# ─────────────────────────────────────────────────────────────────────
class TestTokenAwareBatching:
    """Tests for the OpenAI 300k/8192 token limit handling."""

    def test_count_tokens_with_tiktoken(self):
        """tiktoken counts a known string accurately."""
        from backend.core.embeddings import _TIKTOKEN_AVAILABLE, _count_tokens

        if not _TIKTOKEN_AVAILABLE:
            pytest.skip("tiktoken not available")
        # "hello world" tokenizes to 2 tokens in cl100k_base
        assert _count_tokens("hello world") == 2

    def test_count_tokens_fallback_chars(self):
        """Char-based fallback when tiktoken absent."""
        from backend.core import embeddings as emb

        with patch.object(emb, "_TIKTOKEN_AVAILABLE", False):
            count = emb._count_tokens("a" * 30)
            # Conservative: max(1, len/3)
            assert count == 10

    def test_split_by_token_budget_single_text_fits(self):
        """Single small text → 1 sub-batch."""
        from backend.core.embeddings import _split_by_token_budget

        sub = _split_by_token_budget(["short text"], budget=1000)
        assert len(sub) == 1
        assert sub[0] == ["short text"]

    def test_split_by_token_budget_splits_correctly(self):
        """Many texts with budget → sum of sub-batch sizes equals input count."""
        from backend.core.embeddings import _split_by_token_budget

        texts = ["lorem ipsum " * 100 for _ in range(50)]
        sub = _split_by_token_budget(texts, budget=2000)
        # Total roughly 50 × ~150-200 tok = 7500-10000 tok / 2000 = 4-8 batches
        assert 3 <= len(sub) <= 10
        # No texts dropped
        assert sum(len(s) for s in sub) == len(texts)

    def test_split_by_token_budget_oversized_single_emits_alone(self):
        """Single text > budget gets own sub-batch (will be flagged at API call)."""
        from backend.core.embeddings import _split_by_token_budget

        big = "lorem ipsum " * 50000  # ~150k tokens
        sub = _split_by_token_budget([big, "short"], budget=10_000)
        # Big alone, then short
        assert len(sub) == 2
        assert sub[0] == [big]
        assert sub[1] == ["short"]

    def test_truncate_oversized_input_under_limit(self):
        """Input under limit returned unchanged."""
        from backend.core.embeddings import _truncate_oversized_input

        text = "hello world " * 10  # well under 8192 tokens
        out = _truncate_oversized_input(text, max_tokens=7500)
        assert out == text

    def test_truncate_oversized_input_over_limit(self):
        """Input over limit truncated + [TRUNCATED] marker added."""
        from backend.core.embeddings import (
            _TIKTOKEN_AVAILABLE,
            _count_tokens,
            _truncate_oversized_input,
        )

        if not _TIKTOKEN_AVAILABLE:
            pytest.skip("tiktoken not available")
        big = "Permenkumham 22 Tahun 2023 " * 2000  # ~10k+ tokens
        original_tokens = _count_tokens(big)
        assert original_tokens > 8192  # confirm test setup is meaningful
        out = _truncate_oversized_input(big, max_tokens=7500)
        out_tokens = _count_tokens(out)
        # Should be ~7500 + few extra from " [TRUNCATED]" suffix
        assert out_tokens <= 7600
        assert "[TRUNCATED]" in out
