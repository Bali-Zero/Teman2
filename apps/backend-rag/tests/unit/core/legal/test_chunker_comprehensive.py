"""
Comprehensive tests for core/legal/chunker.py
Target: 99%+ coverage
"""

from unittest.mock import MagicMock, patch

import pytest
from core.legal.chunker import LegalChunker, SemanticSplitter


class TestSemanticSplitter:
    """Test suite for SemanticSplitter"""

    @pytest.fixture
    def mock_embedder(self):
        """Mock embeddings generator"""
        embedder = MagicMock()
        embedder.generate_embeddings = MagicMock(
            return_value=[[0.1, 0.2, 0.3], [0.2, 0.3, 0.4], [0.1, 0.2, 0.3]]
        )
        return embedder

    def test_init(self, mock_embedder):
        """Test SemanticSplitter initialization"""
        splitter = SemanticSplitter(mock_embedder, similarity_threshold=0.7)
        assert splitter.embedder == mock_embedder
        assert splitter.threshold == 0.7

    def test_split_text_empty(self, mock_embedder):
        """Test split_text with empty text"""
        splitter = SemanticSplitter(mock_embedder)
        result = splitter.split_text("", max_tokens=100)
        assert result == []

    def test_split_text_single_sentence(self, mock_embedder):
        """Test split_text with single sentence"""
        splitter = SemanticSplitter(mock_embedder)
        result = splitter.split_text("Hello world.", max_tokens=100)
        assert len(result) == 1

    def test_split_text_multiple_sentences(self, mock_embedder):
        """Test split_text with multiple sentences"""
        splitter = SemanticSplitter(mock_embedder)
        text = "First sentence. Second sentence. Third sentence."
        result = splitter.split_text(text, max_tokens=100)
        assert len(result) > 0

    def test_split_sentences(self, mock_embedder):
        """Test _split_sentences"""
        splitter = SemanticSplitter(mock_embedder)
        text = "First sentence. Second sentence."
        sentences = splitter._split_sentences(text)
        assert len(sentences) == 2
        assert all(s.endswith(".") for s in sentences)

    def test_split_sentences_empty(self, mock_embedder):
        """Test _split_sentences with empty text"""
        splitter = SemanticSplitter(mock_embedder)
        sentences = splitter._split_sentences("")
        assert sentences == []

    def test_cosine_similarity(self, mock_embedder):
        """Test _cosine_similarity"""
        splitter = SemanticSplitter(mock_embedder)
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        similarity = splitter._cosine_similarity(v1, v2)
        assert similarity == 1.0

    def test_cosine_similarity_orthogonal(self, mock_embedder):
        """Test _cosine_similarity with orthogonal vectors"""
        splitter = SemanticSplitter(mock_embedder)
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        similarity = splitter._cosine_similarity(v1, v2)
        assert similarity == 0.0

    def test_cosine_similarity_zero_norm(self, mock_embedder):
        """Test _cosine_similarity with zero norm"""
        splitter = SemanticSplitter(mock_embedder)
        v1 = [0.0, 0.0]
        v2 = [1.0, 0.0]
        similarity = splitter._cosine_similarity(v1, v2)
        assert similarity == 0.0


class TestLegalChunker:
    """Test suite for LegalChunker"""

    @pytest.fixture
    def mock_embedder(self):
        """Mock embeddings generator"""
        embedder = MagicMock()
        embedder.generate_embeddings = MagicMock(return_value=[[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]])
        return embedder

    @pytest.fixture
    def chunker(self, mock_embedder):
        """Create LegalChunker instance"""
        with patch("core.legal.chunker.create_embeddings_generator", return_value=mock_embedder):
            return LegalChunker()

    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing"""
        return {
            "type_abbrev": "UU",
            "number": "1",
            "year": "2024",
            "topic": "Test Law",
        }

    def test_init(self, mock_embedder):
        """Test LegalChunker initialization"""
        with patch("core.legal.chunker.create_embeddings_generator", return_value=mock_embedder):
            chunker = LegalChunker()
            assert chunker.max_pasal_tokens is not None
            assert chunker.embedder == mock_embedder

    def test_init_custom_max_tokens(self, mock_embedder):
        """Test LegalChunker initialization with custom max_pasal_tokens"""
        with patch("core.legal.chunker.create_embeddings_generator", return_value=mock_embedder):
            chunker = LegalChunker(max_pasal_tokens=500)
            assert chunker.max_pasal_tokens == 500

    def test_chunk_empty_text(self, chunker, sample_metadata):
        """Test chunk with empty text"""
        result = chunker.chunk("", sample_metadata)
        assert result == []

    def test_chunk_whitespace_only(self, chunker, sample_metadata):
        """Test chunk with whitespace only"""
        result = chunker.chunk("   \n\t  ", sample_metadata)
        assert result == []

    def test_chunk_with_pasal_structure(self, chunker, sample_metadata):
        """Test chunk with Pasal structure"""
        text = "Pasal 1\nThis is pasal one content. Pasal 2\nThis is pasal two content."
        result = chunker.chunk(text, sample_metadata)
        assert len(result) > 0
        assert all("chunk_index" in chunk for chunk in result)
        assert all("total_chunks" in chunk for chunk in result)

    def test_chunk_without_pasal_structure(self, chunker, sample_metadata):
        """Test chunk without Pasal structure (fallback)"""
        text = "This is unstructured text without Pasal markers."
        result = chunker.chunk(text, sample_metadata)
        assert len(result) > 0

    def test_chunk_with_structure(self, chunker, sample_metadata):
        """Test chunk with structure parameter"""
        text = "Pasal 1\nContent here."
        structure = {
            "batang_tubuh": [
                {
                    "number": "1",
                    "title": "Test BAB",
                    "pasal": [{"number": "1"}],
                }
            ]
        }
        result = chunker.chunk(text, sample_metadata, structure=structure)
        assert len(result) > 0

    def test_split_by_pasal(self, chunker):
        """Test _split_by_pasal"""
        text = "Preamble text. Pasal 1\nPasal one content. Pasal 2\nPasal two content."
        chunks = chunker._split_by_pasal(text)
        assert len(chunks) >= 2

    def test_split_by_pasal_no_pasal(self, chunker):
        """Test _split_by_pasal with no Pasal markers"""
        text = "Just regular text without Pasal markers."
        chunks = chunker._split_by_pasal(text)
        assert len(chunks) == 1

    def test_split_by_ayat(self, chunker):
        """Test _split_by_ayat"""
        pasal_text = "Pasal 1\n(1) First ayat. (2) Second ayat."
        chunks = chunker._split_by_ayat(pasal_text, "1")
        assert len(chunks) >= 1

    def test_split_by_ayat_no_ayat(self, chunker):
        """Test _split_by_ayat with no Ayat markers"""
        pasal_text = "Pasal 1\nJust text without ayat markers."
        chunks = chunker._split_by_ayat(pasal_text, "1")
        assert len(chunks) == 1

    def test_build_context(self, chunker, sample_metadata):
        """Test _build_context"""
        context = chunker._build_context(sample_metadata)
        assert "[CONTEXT:" in context
        assert "UU" in context

    def test_build_context_with_bab(self, chunker, sample_metadata):
        """Test _build_context with BAB"""
        context = chunker._build_context(sample_metadata, bab="BAB I - Test")
        assert "BAB I" in context

    def test_build_context_with_pasal(self, chunker, sample_metadata):
        """Test _build_context with Pasal"""
        context = chunker._build_context(sample_metadata, pasal="Pasal 1")
        assert "Pasal 1" in context

    def test_build_context_with_both(self, chunker, sample_metadata):
        """Test _build_context with both BAB and Pasal"""
        context = chunker._build_context(sample_metadata, bab="BAB I - Test", pasal="Pasal 1")
        assert "BAB I" in context
        assert "Pasal 1" in context

    def test_create_chunk(self, chunker, sample_metadata):
        """Test _create_chunk"""
        chunk = chunker._create_chunk("Content here", "[CONTEXT: Test]", sample_metadata)
        assert chunk["text"].startswith("[CONTEXT:")
        assert "Content here" in chunk["text"]
        assert chunk["chunk_length"] > 0
        assert chunk["content_length"] > 0
        assert chunk["has_context"] is True

    def test_create_chunk_with_pasal(self, chunker, sample_metadata):
        """Test _create_chunk with Pasal number"""
        chunk = chunker._create_chunk(
            "Content here", "[CONTEXT: Test]", sample_metadata, pasal_num="1"
        )
        assert chunk["pasal_number"] == "1"

    def test_find_bab_for_pasal(self, chunker):
        """Test _find_bab_for_pasal"""
        structure = {
            "batang_tubuh": [
                {
                    "number": "1",
                    "title": "Test BAB",
                    "pasal": [{"number": "1"}],
                }
            ]
        }
        bab = chunker._find_bab_for_pasal(structure, "1")
        assert bab is not None
        assert "BAB 1" in bab

    def test_find_bab_for_pasal_not_found(self, chunker):
        """Test _find_bab_for_pasal when Pasal not found"""
        structure = {
            "batang_tubuh": [
                {
                    "number": "1",
                    "title": "Test BAB",
                    "pasal": [{"number": "2"}],
                }
            ]
        }
        bab = chunker._find_bab_for_pasal(structure, "1")
        assert bab is None

    def test_fallback_chunking(self, chunker, sample_metadata):
        """Test _fallback_chunking"""
        text = "Unstructured text without Pasal markers."
        chunks = chunker._fallback_chunking(text, sample_metadata)
        assert len(chunks) > 0
        assert all("chunk_index" in chunk for chunk in chunks)
        assert all("total_chunks" in chunk for chunk in chunks)

    def test_chunk_large_pasal(self, chunker, sample_metadata):
        """Test chunk with large Pasal that needs splitting"""
        # Create a large Pasal text
        large_text = "Pasal 1\n" + "Large content. " * 1000
        result = chunker.chunk(large_text, sample_metadata)
        assert len(result) > 0

    def test_chunk_pasal_with_ayat(self, chunker, sample_metadata):
        """Test chunk with Pasal containing Ayat"""
        text = "Pasal 1\n(1) First ayat content. (2) Second ayat content."
        result = chunker.chunk(text, sample_metadata)
        assert len(result) > 0
