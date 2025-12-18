"""
Integration Tests for LegalChunker
Tests semantic chunking of Indonesian legal documents
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestLegalChunkerIntegration:
    """Comprehensive integration tests for LegalChunker"""

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder"""
        mock_embedder = MagicMock()
        mock_embedder.generate_embeddings = MagicMock(
            return_value=[[0.1] * 384, [0.2] * 384, [0.3] * 384]
        )
        return mock_embedder

    @pytest.fixture
    def chunker(self, mock_embedder):
        """Create LegalChunker instance"""
        with patch("core.legal.chunker.create_embeddings_generator", return_value=mock_embedder):
            from core.legal.chunker import LegalChunker

            chunker = LegalChunker(max_pasal_tokens=1000)
            chunker.embedder = mock_embedder
            return chunker

    def test_initialization(self, chunker):
        """Test chunker initialization"""
        assert chunker is not None
        assert chunker.max_pasal_tokens == 1000
        assert chunker.embedder is not None

    def test_chunk_with_pasal_structure(self, chunker):
        """Test chunking document with Pasal structure"""
        text = """
        Pasal 1
        Ketentuan umum tentang visa dan izin tinggal.

        Pasal 2
        Prosedur aplikasi visa harus dilakukan melalui sistem online.
        """

        metadata = {"type": "regulation", "number": "UU 1/2023"}

        chunks = chunker.chunk(text, metadata)

        assert chunks is not None
        assert len(chunks) > 0
        assert all("text" in chunk for chunk in chunks)

    def test_chunk_without_pasal_structure(self, chunker):
        """Test chunking document without Pasal structure"""
        text = "This is a general document without Pasal structure. It contains multiple sentences."

        metadata = {"type": "document"}

        chunks = chunker.chunk(text, metadata)

        assert chunks is not None
        # Should use fallback chunking

    def test_chunk_empty_text(self, chunker):
        """Test chunking empty text"""
        chunks = chunker.chunk("", {})

        assert chunks == []

    def test_chunk_with_metadata(self, chunker):
        """Test chunking with metadata"""
        text = "Pasal 1\nTest content."

        metadata = {
            "type": "law",
            "number": "UU 1/2023",
            "year": 2023,
            "topic": "immigration",
        }

        chunks = chunker.chunk(text, metadata)

        assert chunks is not None
        assert len(chunks) > 0
        # Metadata should be included in chunks
        assert all("metadata" in chunk for chunk in chunks)

    def test_chunk_large_pasal(self, chunker):
        """Test chunking large Pasal that exceeds max_tokens"""
        # Create large Pasal text
        large_text = "Pasal 1\n" + "This is a very long text. " * 200

        metadata = {"type": "law"}

        chunks = chunker.chunk(large_text, metadata)

        assert chunks is not None
        # Large Pasal should be split further

    def test_semantic_splitter_split_text(self, chunker):
        """Test semantic splitter"""
        text = "Sentence one. Sentence two. Sentence three."

        chunks = chunker.semantic_splitter.split_text(text, max_tokens=50)

        assert chunks is not None
        assert len(chunks) > 0

    def test_semantic_splitter_cosine_similarity(self, chunker):
        """Test cosine similarity calculation"""
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]

        similarity = chunker.semantic_splitter._cosine_similarity(v1, v2)

        assert similarity == 1.0  # Identical vectors

    def test_chunk_with_structure(self, chunker):
        """Test chunking with provided structure"""
        text = "Pasal 1\nTest content."

        metadata = {"type": "law"}

        structure = {
            "batang_tubuh": [
                {
                    "number": "I",
                    "title": "Ketentuan Umum",
                    "pasal": [{"number": "1", "text": "Test content."}],
                }
            ]
        }

        chunks = chunker.chunk(text, metadata, structure=structure)

        assert chunks is not None
        assert len(chunks) > 0

    def test_chunk_with_ayat(self, chunker):
        """Test chunking Pasal with Ayat"""
        text = """
        Pasal 1
        (1) Ayat pertama tentang visa.
        (2) Ayat kedua tentang izin tinggal.
        (3) Ayat ketiga tentang prosedur.
        """

        metadata = {"type": "law"}

        chunks = chunker.chunk(text, metadata)

        assert chunks is not None
        # Should split by Ayat if Pasal is too large
