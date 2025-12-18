"""
Unit tests for Semantic Chunking
"""

from unittest.mock import MagicMock, patch

import pytest
from core.legal.chunker import LegalChunker, SemanticSplitter


@pytest.fixture
def mock_embedder():
    """Mock EmbeddingsGenerator"""
    embedder = MagicMock()

    # Simple mock: return vectors based on sentence length/content to simulate similarity
    def generate_embeddings(sentences):
        embeddings = []
        for s in sentences:
            if "apple" in s:
                embeddings.append([1.0, 0.0])  # Apple vector
            elif "banana" in s:
                embeddings.append([0.9, 0.1])  # Banana vector (close to apple)
            elif "car" in s:
                embeddings.append([0.0, 1.0])  # Car vector (far from apple)
            else:
                embeddings.append([0.5, 0.5])  # Neutral
        return embeddings

    embedder.generate_embeddings.side_effect = generate_embeddings
    return embedder


def test_semantic_splitter_cosine_similarity():
    """Test cosine similarity calculation"""
    splitter = SemanticSplitter(MagicMock())
    v1 = [1.0, 0.0]
    v2 = [1.0, 0.0]
    assert splitter._cosine_similarity(v1, v2) == 1.0

    v3 = [0.0, 1.0]
    assert splitter._cosine_similarity(v1, v3) == 0.0


def test_semantic_splitter_grouping(mock_embedder):
    """Test grouping of semantically similar sentences"""
    splitter = SemanticSplitter(mock_embedder, similarity_threshold=0.8)

    text = "I like apple. I like banana. I drive a car."
    # Apple and Banana should be grouped (0.9 similarity). Car should be separate.

    chunks = splitter.split_text(text, max_tokens=1000)

    assert len(chunks) == 2
    assert "apple" in chunks[0] and "banana" in chunks[0]
    assert "car" in chunks[1]


def test_semantic_splitter_max_tokens(mock_embedder):
    """Test splitting when max tokens exceeded despite high similarity"""
    splitter = SemanticSplitter(mock_embedder, similarity_threshold=0.0)  # Always group if possible

    text = "Sentence one. Sentence two."
    # Force split by setting low max_tokens
    chunks = splitter.split_text(text, max_tokens=10)

    # Should be split because combined length > 10
    assert len(chunks) == 2


@pytest.mark.asyncio
async def test_legal_chunker_fallback_semantic(mock_embedder):
    """Test LegalChunker uses semantic splitting for fallback"""
    with patch("core.legal.chunker.create_embeddings_generator", return_value=mock_embedder):
        chunker = LegalChunker(max_pasal_tokens=1000)

        text = "I like apple. I like banana. I drive a car."
        metadata = {"type_abbrev": "UU", "number": "1", "year": "2024", "topic": "Test"}

        # Should use fallback because no "Pasal" pattern
        chunks = chunker.chunk(text, metadata)

        assert len(chunks) == 2
        assert "apple" in chunks[0]["text"]
        assert "car" in chunks[1]["text"]
        assert chunks[0]["has_context"] is True
