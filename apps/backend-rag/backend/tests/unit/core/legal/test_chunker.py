"""
Tests for LegalChunker
"""

from unittest.mock import MagicMock, patch

from core.legal.chunker import LegalChunker, SemanticSplitter


class TestSemanticSplitter:
    """Test suite for SemanticSplitter"""

    def test_init(self):
        """Test splitter initialization"""
        mock_embedder = MagicMock()
        splitter = SemanticSplitter(mock_embedder, similarity_threshold=0.7)
        assert splitter.embedder == mock_embedder
        assert splitter.threshold == 0.7

    def test_split_text_empty(self):
        """Test splitting empty text"""
        mock_embedder = MagicMock()
        splitter = SemanticSplitter(mock_embedder)
        result = splitter.split_text("", max_tokens=100)

        assert result == []

    def test_split_text_single_sentence(self):
        """Test splitting text with single sentence"""
        mock_embedder = MagicMock()
        mock_embedder.generate_embeddings.return_value = [[1.0, 0.0]]
        splitter = SemanticSplitter(mock_embedder)
        text = "This is a single sentence."
        result = splitter.split_text(text, max_tokens=100)

        assert len(result) == 1
        # _split_sentences adds a period, so result will have ".." if original has "."
        assert text in result[0] or result[0] == text

    def test_split_text_multiple_sentences(self):
        """Test splitting text with multiple sentences"""
        mock_embedder = MagicMock()
        # Mock embeddings: first two similar, third different
        mock_embedder.generate_embeddings.return_value = [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],  # Similar to first
            [0.0, 0.0, 1.0],  # Different
        ]
        splitter = SemanticSplitter(mock_embedder, similarity_threshold=0.7)
        text = "First sentence. Second sentence. Third sentence."
        result = splitter.split_text(text, max_tokens=100)

        assert len(result) >= 1
        mock_embedder.generate_embeddings.assert_called_once()

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        mock_embedder = MagicMock()
        splitter = SemanticSplitter(mock_embedder)
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]  # Same vector
        similarity = splitter._cosine_similarity(v1, v2)

        assert abs(similarity - 1.0) < 0.001  # Should be 1.0

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity with orthogonal vectors"""
        mock_embedder = MagicMock()
        splitter = SemanticSplitter(mock_embedder)
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]  # Orthogonal
        similarity = splitter._cosine_similarity(v1, v2)

        assert abs(similarity - 0.0) < 0.001  # Should be 0.0

    def test_cosine_similarity_zero_norm(self):
        """Test cosine similarity with zero norm vectors"""
        mock_embedder = MagicMock()
        splitter = SemanticSplitter(mock_embedder)
        v1 = [0.0, 0.0, 0.0]
        v2 = [0.0, 0.0, 0.0]
        similarity = splitter._cosine_similarity(v1, v2)

        assert similarity == 0.0

    def test_split_sentences(self):
        """Test _split_sentences method"""
        mock_embedder = MagicMock()
        splitter = SemanticSplitter(mock_embedder)
        text = "First sentence. Second sentence. Third sentence."
        sentences = splitter._split_sentences(text)

        assert len(sentences) == 3
        assert all(s.endswith(".") for s in sentences)


class TestLegalChunker:
    """Test suite for LegalChunker"""

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_init(self, mock_create_embedder):
        """Test chunker initialization"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker(max_pasal_tokens=500)

        assert chunker.max_pasal_tokens == 500
        assert chunker.embedder == mock_embedder
        assert chunker.semantic_splitter is not None

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_init_default(self, mock_create_embedder):
        """Test chunker initialization with default max_pasal_tokens"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()

        assert chunker.max_pasal_tokens == 1000  # Default from constants

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_chunk_empty_text(self, mock_create_embedder):
        """Test chunking empty text"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}

        result = chunker.chunk("", metadata)

        assert result == []

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_chunk_whitespace_only(self, mock_create_embedder):
        """Test chunking whitespace-only text"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}

        result = chunker.chunk("   \n\t  ", metadata)

        assert result == []

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_chunk_with_pasal_structure(self, mock_create_embedder):
        """Test chunking text with Pasal structure"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        text = """Pasal 1
Ini adalah konten Pasal 1.

Pasal 2
Ini adalah konten Pasal 2."""

        result = chunker.chunk(text, metadata)

        assert len(result) > 0
        assert all("chunk_index" in chunk for chunk in result)
        assert all("total_chunks" in chunk for chunk in result)
        assert all("has_context" in chunk for chunk in result)

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_chunk_without_pasal_structure(self, mock_create_embedder):
        """Test chunking text without Pasal structure (fallback)"""
        mock_embedder = MagicMock()
        mock_embedder.generate_embeddings.return_value = [[1.0, 0.0], [0.0, 1.0]]
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        text = """This is unstructured text without Pasal markers.
It should use fallback semantic chunking."""

        result = chunker.chunk(text, metadata)

        assert len(result) > 0
        assert all("chunk_index" in chunk for chunk in result)
        assert all("total_chunks" in chunk for chunk in result)

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_chunk_with_structure(self, mock_create_embedder):
        """Test chunking with provided structure"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        structure = {
            "batang_tubuh": [
                {
                    "number": "I",
                    "title": "KETENTUAN UMUM",
                    "pasal": [{"number": "1"}],
                }
            ]
        }
        text = """Pasal 1
Content of Pasal 1."""

        result = chunker.chunk(text, metadata, structure)

        assert len(result) > 0

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_chunk_large_pasal_split_by_ayat(self, mock_create_embedder):
        """Test chunking large Pasal that gets split by Ayat"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker(max_pasal_tokens=100)  # Small limit
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        # Create a large Pasal with Ayat
        large_pasal = (
            """Pasal 1
(1) First ayat with lots of content. """
            * 50
        )  # Make it large
        text = large_pasal

        result = chunker.chunk(text, metadata)

        assert len(result) > 0

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_build_context(self, mock_create_embedder):
        """Test _build_context method"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}

        context = chunker._build_context(metadata)

        assert "[CONTEXT:" in context
        assert "UU" in context
        assert "NO 12" in context
        assert "TAHUN 2024" in context
        assert "TENTANG TEST" in context

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_build_context_with_bab(self, mock_create_embedder):
        """Test _build_context with BAB"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}

        context = chunker._build_context(metadata, bab="BAB I - KETENTUAN UMUM")

        assert "BAB I" in context

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_build_context_with_pasal(self, mock_create_embedder):
        """Test _build_context with Pasal"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}

        context = chunker._build_context(metadata, pasal="Pasal 1")

        assert "Pasal 1" in context

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_create_chunk(self, mock_create_embedder):
        """Test _create_chunk method"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        content = "Test content"
        context = "[CONTEXT: UU NO 12 TAHUN 2024 TENTANG TEST]"

        chunk = chunker._create_chunk(content, context, metadata)

        assert chunk["text"] == f"{context}\n\n{content}"
        assert chunk["chunk_length"] > 0
        assert chunk["content_length"] == len(content)
        assert chunk["has_context"] is True
        assert chunk["type_abbrev"] == "UU"
        assert chunk["number"] == "12"

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_create_chunk_with_pasal_num(self, mock_create_embedder):
        """Test _create_chunk with Pasal number"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        content = "Test content"
        context = "[CONTEXT: UU NO 12 TAHUN 2024 TENTANG TEST]"

        chunk = chunker._create_chunk(content, context, metadata, pasal_num="1")

        assert chunk["pasal_number"] == "1"

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_split_by_pasal(self, mock_create_embedder):
        """Test _split_by_pasal method"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        text = """Preamble text.

Pasal 1
Content of Pasal 1.

Pasal 2
Content of Pasal 2."""

        chunks = chunker._split_by_pasal(text)

        assert len(chunks) >= 2  # Preamble + at least 2 Pasal

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_split_by_ayat(self, mock_create_embedder):
        """Test _split_by_ayat method"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        pasal_text = """(1) First ayat content.
(2) Second ayat content.
(3) Third ayat content."""

        chunks = chunker._split_by_ayat(pasal_text, "1")

        assert len(chunks) == 3
        assert all("Pasal 1" in chunk for chunk in chunks)
        assert all("Ayat" in chunk for chunk in chunks)

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_split_by_ayat_no_ayat(self, mock_create_embedder):
        """Test _split_by_ayat with no Ayat"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        pasal_text = "Content without ayat markers."

        chunks = chunker._split_by_ayat(pasal_text, "1")

        assert len(chunks) == 1
        assert chunks[0] == pasal_text

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_find_bab_for_pasal(self, mock_create_embedder):
        """Test _find_bab_for_pasal method"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        structure = {
            "batang_tubuh": [
                {
                    "number": "I",
                    "title": "KETENTUAN UMUM",
                    "pasal": [{"number": "1"}],
                }
            ]
        }

        bab_context = chunker._find_bab_for_pasal(structure, "1")

        assert bab_context is not None
        assert "BAB I" in bab_context

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_find_bab_for_pasal_not_found(self, mock_create_embedder):
        """Test _find_bab_for_pasal when Pasal not found"""
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        structure = {
            "batang_tubuh": [
                {
                    "number": "I",
                    "title": "KETENTUAN UMUM",
                    "pasal": [{"number": "1"}],
                }
            ]
        }

        bab_context = chunker._find_bab_for_pasal(structure, "99")

        assert bab_context is None

    @patch("core.legal.chunker.create_embeddings_generator")
    def test_fallback_chunking(self, mock_create_embedder):
        """Test _fallback_chunking method"""
        mock_embedder = MagicMock()
        mock_embedder.generate_embeddings.return_value = [[1.0, 0.0], [0.0, 1.0]]
        mock_create_embedder.return_value = mock_embedder
        chunker = LegalChunker()
        metadata = {"type_abbrev": "UU", "number": "12", "year": "2024", "topic": "TEST"}
        text = "Unstructured text without Pasal markers."

        chunks = chunker._fallback_chunking(text, metadata)

        assert len(chunks) > 0
        assert all("chunk_index" in chunk for chunk in chunks)
        assert all("total_chunks" in chunk for chunk in chunks)
