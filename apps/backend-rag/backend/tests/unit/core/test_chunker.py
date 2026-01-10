"""
Unit tests for Chunker
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.chunker import Chunker, create_chunker


class TestChunker:
    """Tests for Chunker class"""

    def test_init_default(self):
        """Test initialization with default parameters"""
        chunker = Chunker()
        assert chunker.max_tokens == 512
        assert chunker.overlap == 0

    def test_init_custom(self):
        """Test initialization with custom parameters"""
        chunker = Chunker(max_tokens=256, overlap=50)
        assert chunker.max_tokens == 256
        assert chunker.overlap == 50

    def test_chunk_text_empty(self):
        """Test chunking empty text"""
        chunker = Chunker()
        result = chunker.chunk_text("")
        assert result == []

    def test_chunk_text_short(self):
        """Test chunking text shorter than max_tokens"""
        chunker = Chunker(max_tokens=100)
        text = "This is a short text"
        result = chunker.chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_chunk_text_exact_length(self):
        """Test chunking text exactly max_tokens length"""
        chunker = Chunker(max_tokens=10)
        text = "A" * 10
        result = chunker.chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_chunk_text_long(self):
        """Test chunking text longer than max_tokens"""
        chunker = Chunker(max_tokens=10)
        text = "A" * 25
        result = chunker.chunk_text(text)
        assert len(result) == 3  # 25 chars / 10 = 3 chunks
        assert result[0] == "A" * 10
        assert result[1] == "A" * 10
        assert result[2] == "A" * 5

    def test_chunk_text_multiple_chunks(self):
        """Test chunking creates multiple chunks"""
        chunker = Chunker(max_tokens=5)
        text = "This is a longer text that needs chunking"
        result = chunker.chunk_text(text)
        assert len(result) > 1
        # Verify all chunks together equal original text
        assert "".join(result) == text

    def test_chunk_text_with_overlap(self):
        """Test chunking with overlap parameter (even though not used in implementation)"""
        chunker = Chunker(max_tokens=10, overlap=2)
        text = "A" * 25
        result = chunker.chunk_text(text)
        # Overlap is stored but not used in current implementation
        assert chunker.overlap == 2
        assert len(result) == 3  # Still creates 3 chunks without overlap


class TestCreateChunker:
    """Tests for create_chunker function"""

    def test_create_chunker_default(self):
        """Test creating chunker with default parameters"""
        chunker = create_chunker()
        assert isinstance(chunker, Chunker)
        assert chunker.max_tokens == 512
        assert chunker.overlap == 0

    def test_create_chunker_custom(self):
        """Test creating chunker with custom parameters"""
        chunker = create_chunker(max_tokens=256, overlap=50)
        assert isinstance(chunker, Chunker)
        assert chunker.max_tokens == 256
        assert chunker.overlap == 50
