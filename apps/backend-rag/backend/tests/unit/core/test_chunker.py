"""
Unit tests for TextChunker
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.chunker import TextChunker, Chunker, create_chunker, semantic_chunk


class TestChunker:
    """Tests for simple Chunker class"""

    def test_init(self):
        """Test initialization"""
        chunker = Chunker(max_tokens=100, overlap=10)
        assert chunker.max_tokens == 100
        assert chunker.overlap == 10

    def test_chunk_text_empty(self):
        """Test chunking empty text"""
        chunker = Chunker()
        result = chunker.chunk_text("")
        assert result == []

    def test_chunk_text_small(self):
        """Test chunking small text"""
        chunker = Chunker(max_tokens=100)
        text = "Hello world"
        result = chunker.chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_chunk_text_large(self):
        """Test chunking large text"""
        chunker = Chunker(max_tokens=10)
        text = "a" * 30
        result = chunker.chunk_text(text)
        assert len(result) == 3

    def test_create_chunker(self):
        """Test factory function"""
        chunker = create_chunker(max_tokens=200, overlap=20)
        assert chunker.max_tokens == 200
        assert chunker.overlap == 20


class TestTextChunker:
    """Tests for TextChunker class"""

    def test_init_defaults(self):
        """Test initialization with defaults"""
        with patch("core.chunker.settings", None):
            chunker = TextChunker()
            assert chunker.chunk_size == 1000
            assert chunker.chunk_overlap == 100

    def test_init_custom(self):
        """Test initialization with custom values"""
        chunker = TextChunker(chunk_size=500, chunk_overlap=50, max_chunks=100)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50
        assert chunker.max_chunks == 100

    def test_chunk_text_empty(self):
        """Test chunking empty text"""
        chunker = TextChunker()
        result = chunker.chunk_text("")
        assert result == []

    def test_chunk_text_small(self):
        """Test chunking small text"""
        chunker = TextChunker(chunk_size=1000)
        text = "This is a short text."
        result = chunker.chunk_text(text)
        assert len(result) > 0
        assert all(isinstance(chunk, str) for chunk in result)

    def test_semantic_chunk_empty(self):
        """Test semantic chunking empty text"""
        chunker = TextChunker()
        result = chunker.semantic_chunk("")
        assert result == []

    def test_semantic_chunk_simple(self):
        """Test semantic chunking simple text"""
        chunker = TextChunker(chunk_size=100)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = chunker.semantic_chunk(text)
        assert len(result) > 0
        assert all("text" in chunk for chunk in result)
        assert all("chunk_index" in chunk for chunk in result)

    def test_semantic_chunk_with_metadata(self):
        """Test semantic chunking with metadata"""
        chunker = TextChunker(chunk_size=100)
        text = "Test text with multiple paragraphs.\n\nSecond paragraph here."
        metadata = {"book_id": "123", "author": "Test Author"}
        result = chunker.semantic_chunk(text, metadata=metadata)
        assert len(result) > 0
        assert all(chunk["book_id"] == "123" for chunk in result)
        assert all(chunk["author"] == "Test Author" for chunk in result)

    def test_semantic_chunk_with_overlap(self):
        """Test semantic chunking with overlap"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph." * 10  # Long text with separators
        result = chunker.semantic_chunk(text)
        assert len(result) > 1  # Should create multiple chunks

    def test_semantic_chunk_max_chunks(self):
        """Test semantic chunking with max_chunks limit"""
        chunker = TextChunker(chunk_size=50, max_chunks=3)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph." * 20  # Very long text with separators
        result = chunker.semantic_chunk(text)
        assert len(result) <= 3

    def test_chunk_by_pages_no_markers(self):
        """Test chunk_by_pages without page markers"""
        chunker = TextChunker()
        text = "Test text"
        result = chunker.chunk_by_pages(text)
        assert len(result) > 0

    def test_chunk_by_pages_with_markers(self):
        """Test chunk_by_pages with page markers"""
        chunker = TextChunker()
        text = "Page 1 content. " * 50 + "Page 2 content. " * 50
        page_markers = [0, 800]  # Character positions
        result = chunker.chunk_by_pages(text, page_markers=page_markers)
        assert len(result) > 0

    def test_semantic_chunk_function(self):
        """Test semantic_chunk convenience function"""
        text = "Test text for chunking."
        result = semantic_chunk(text, max_tokens=10, overlap=2)
        assert isinstance(result, list)
        assert all(isinstance(chunk, str) for chunk in result)

    def test_split_text_recursive(self):
        """Test recursive text splitting"""
        chunker = TextChunker(chunk_size=20)
        text = "First.\n\nSecond.\n\nThird."
        result = chunker._split_text_recursive(text, "\n\n")
        assert len(result) > 0
        assert all(len(chunk) <= 20 or chunk == result[-1] for chunk in result)

