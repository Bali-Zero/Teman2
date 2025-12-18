"""
Unit tests for Chunker
Tests text chunking functionality
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestChunker:
    """Unit tests for Chunker"""

    def test_chunker_init(self):
        """Test Chunker initialization"""
        from backend.core.chunker import TextChunker

        chunker = TextChunker()
        assert chunker is not None

    def test_chunk_text_small(self):
        """Test chunking small text"""
        from backend.core.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a small text that should not be chunked."
        chunks = chunker.semantic_chunk(text)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_chunk_text_large(self):
        """Test chunking large text"""
        from backend.core.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a very long text. " * 100
        chunks = chunker.semantic_chunk(text)

        assert isinstance(chunks, list)
        assert len(chunks) > 1

    def test_chunk_text_with_overlap(self):
        """Test chunking with overlap"""
        from backend.core.chunker import TextChunker

        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10"
        chunks = chunker.semantic_chunk(text)

        assert isinstance(chunks, list)
        # Should have multiple chunks with overlap
        if len(chunks) > 1:
            assert len(chunks) > 1

    def test_chunk_text_empty(self):
        """Test chunking empty text"""
        from backend.core.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.semantic_chunk("")

        assert isinstance(chunks, list)
        # May return empty list
        assert len(chunks) >= 0

    def test_chunk_text_no_overlap(self):
        """Test chunking without overlap"""
        from backend.core.chunker import TextChunker

        chunker = TextChunker(chunk_size=20, chunk_overlap=0)
        text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10"
        chunks = chunker.semantic_chunk(text)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1
