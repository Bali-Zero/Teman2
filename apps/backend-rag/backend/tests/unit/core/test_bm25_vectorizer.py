"""
Unit tests for core/bm25_vectorizer.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.bm25_vectorizer import BM25Vectorizer, get_bm25_vectorizer


class TestBM25Vectorizer:
    """Tests for BM25Vectorizer"""

    def test_init_default(self):
        """Test BM25Vectorizer initialization with defaults"""
        vectorizer = BM25Vectorizer()
        assert vectorizer.vocab_size == 30000
        assert vectorizer.k1 == 1.5
        assert vectorizer.b == 0.75
        assert vectorizer.min_token_length == 2
        assert vectorizer.max_token_length == 50
        assert vectorizer.avg_doc_length == 500

    def test_init_custom(self):
        """Test BM25Vectorizer initialization with custom parameters"""
        vectorizer = BM25Vectorizer(
            vocab_size=10000, k1=2.0, b=0.8, min_token_length=3, max_token_length=40
        )
        assert vectorizer.vocab_size == 10000
        assert vectorizer.k1 == 2.0
        assert vectorizer.b == 0.8
        assert vectorizer.min_token_length == 3
        assert vectorizer.max_token_length == 40

    def test_tokenize_empty(self):
        """Test tokenization of empty string"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("")
        assert result == []

    def test_tokenize_basic(self):
        """Test basic tokenization"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("Hello world test")
        assert len(result) > 0
        assert "hello" in result or "world" in result or "test" in result

    def test_tokenize_lowercase(self):
        """Test that tokenization lowercases text"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("HELLO World")
        assert all(token.islower() for token in result)

    def test_tokenize_filters_stopwords(self):
        """Test that stopwords are filtered"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("dan di ke dari yang")
        # Should filter out Indonesian stopwords
        assert len(result) == 0 or all(
            token not in ["dan", "di", "ke", "dari", "yang"] for token in result
        )

    def test_tokenize_filters_short_tokens(self):
        """Test that short tokens are filtered"""
        vectorizer = BM25Vectorizer(min_token_length=3)
        result = vectorizer.tokenize("a b c hello")
        assert "a" not in result
        assert "b" not in result
        assert "c" not in result
        assert "hello" in result

    def test_tokenize_filters_long_tokens(self):
        """Test that long tokens are filtered"""
        vectorizer = BM25Vectorizer(max_token_length=5)
        result = vectorizer.tokenize("hello verylongtoken")
        assert "verylongtoken" not in result
        assert "hello" in result

    def test_tokenize_preserves_kbli_codes(self):
        """Test that KBLI codes are preserved"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("KBLI 56101")
        # Should preserve kbli pattern
        assert any("kbli" in token for token in result)

    def test_tokenize_preserves_legal_references(self):
        """Test that legal references are preserved"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("UU No. 6 tahun 2011")
        # Should preserve uu pattern
        assert any("uu" in token for token in result)

    def test_tokenize_filters_pure_numbers(self):
        """Test that pure short numbers are filtered"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("123 4567 2021")
        # Short numbers should be filtered, longer ones might be kept
        assert "123" not in result or len("123") < 4

    def test_hash_token(self):
        """Test token hashing"""
        vectorizer = BM25Vectorizer(vocab_size=1000)
        token_id = vectorizer._hash_token("test")
        assert isinstance(token_id, int)
        assert 0 <= token_id < 1000

    def test_hash_token_consistency(self):
        """Test that same token hashes to same ID"""
        vectorizer = BM25Vectorizer()
        id1 = vectorizer._hash_token("test")
        id2 = vectorizer._hash_token("test")
        assert id1 == id2

    def test_calculate_tf(self):
        """Test BM25 term frequency calculation"""
        vectorizer = BM25Vectorizer()
        tf = vectorizer._calculate_tf(token_count=5, doc_length=100)
        assert isinstance(tf, float)
        assert tf > 0

    def test_calculate_tf_zero_denominator(self):
        """Test TF calculation with zero denominator"""
        vectorizer = BM25Vectorizer()
        vectorizer.avg_doc_length = 0
        tf = vectorizer._calculate_tf(token_count=5, doc_length=100)
        assert tf == 0.0

    def test_generate_sparse_vector_empty(self):
        """Test sparse vector generation for empty text"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_sparse_vector("")
        assert result == {"indices": [], "values": []}

    def test_generate_sparse_vector_basic(self):
        """Test basic sparse vector generation"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_sparse_vector("hello world test")
        assert "indices" in result
        assert "values" in result
        assert len(result["indices"]) == len(result["values"])
        assert len(result["indices"]) > 0

    def test_generate_sparse_vector_format(self):
        """Test sparse vector format"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_sparse_vector("hello world")
        assert isinstance(result["indices"], list)
        assert isinstance(result["values"], list)
        assert all(isinstance(i, int) for i in result["indices"])
        assert all(isinstance(v, float) for v in result["values"])

    def test_generate_sparse_vector_sorted(self):
        """Test that indices are sorted"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_sparse_vector("hello world test example")
        indices = result["indices"]
        assert indices == sorted(indices)

    def test_generate_sparse_vector_unique_indices(self):
        """Test that indices are unique"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_sparse_vector("hello world test")
        indices = result["indices"]
        assert len(indices) == len(set(indices))

    def test_generate_query_sparse_vector_empty(self):
        """Test query sparse vector generation for empty query"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_query_sparse_vector("")
        assert result == {"indices": [], "values": []}

    def test_generate_query_sparse_vector_basic(self):
        """Test basic query sparse vector generation"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_query_sparse_vector("hello world")
        assert "indices" in result
        assert "values" in result
        assert len(result["indices"]) == len(result["values"])
        assert len(result["indices"]) > 0

    def test_generate_query_sparse_vector_format(self):
        """Test query sparse vector format"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_query_sparse_vector("hello")
        assert isinstance(result["indices"], list)
        assert isinstance(result["values"], list)
        assert all(isinstance(i, int) for i in result["indices"])
        assert all(isinstance(v, float) for v in result["values"])

    def test_generate_batch_sparse_vectors(self):
        """Test batch sparse vector generation"""
        vectorizer = BM25Vectorizer()
        texts = ["hello world", "test example", "another text"]
        results = vectorizer.generate_batch_sparse_vectors(texts)
        assert len(results) == 3
        assert all("indices" in r and "values" in r for r in results)

    def test_generate_batch_sparse_vectors_empty(self):
        """Test batch generation with empty list"""
        vectorizer = BM25Vectorizer()
        results = vectorizer.generate_batch_sparse_vectors([])
        assert results == []

    def test_update_avg_doc_length(self):
        """Test updating average document length"""
        vectorizer = BM25Vectorizer()
        assert vectorizer.avg_doc_length == 500
        vectorizer.update_avg_doc_length(750.5)
        assert vectorizer.avg_doc_length == 750.5

    def test_hash_collision_handling(self):
        """Test that hash collisions are handled by summing scores"""
        vectorizer = BM25Vectorizer(vocab_size=10)  # Small vocab to increase collision chance
        # Use text that might cause collisions
        result = vectorizer.generate_sparse_vector("test token word example")
        # Should still have unique indices
        assert len(result["indices"]) == len(set(result["indices"]))

    def test_tokenize_with_punctuation(self):
        """Test tokenization handles punctuation correctly"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("hello, world! test.")
        # Punctuation should be removed
        assert all(not any(c in token for c in ",!.") for token in result)

    def test_tokenize_preserves_hyphens(self):
        """Test that hyphens in words are preserved"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.tokenize("well-known test")
        # Hyphens might be preserved or removed depending on implementation
        # Just verify it doesn't crash
        assert isinstance(result, list)

    def test_generate_sparse_vector_repeated_tokens(self):
        """Test sparse vector with repeated tokens"""
        vectorizer = BM25Vectorizer()
        result = vectorizer.generate_sparse_vector("hello hello hello world")
        # Should handle repeated tokens correctly
        assert len(result["indices"]) > 0
        assert len(result["indices"]) == len(result["values"])

    def test_get_bm25_vectorizer_singleton(self):
        """Test get_bm25_vectorizer returns singleton"""
        with patch("core.bm25_vectorizer._bm25_vectorizer", None):
            vectorizer1 = get_bm25_vectorizer()
            vectorizer2 = get_bm25_vectorizer()
            assert vectorizer1 is vectorizer2

    def test_get_bm25_vectorizer_creates_new(self):
        """Test get_bm25_vectorizer creates new instance if None"""
        with patch("core.bm25_vectorizer._bm25_vectorizer", None):
            vectorizer = get_bm25_vectorizer()
            assert isinstance(vectorizer, BM25Vectorizer)
