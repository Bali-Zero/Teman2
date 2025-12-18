"""
Integration tests for Embedding Service
Tests embedding generation integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestEmbeddingServiceIntegration:
    """Integration tests for Embedding Service"""

    def test_embedding_service_initialization(self):
        """Test embedding service initialization"""
        with patch("core.embeddings.create_embeddings_generator") as mock_create:
            mock_embedder = MagicMock()
            mock_embedder.model = "text-embedding-3-small"
            mock_embedder.dimensions = 1536
            mock_create.return_value = mock_embedder

            from core.embeddings import create_embeddings_generator

            embedder = create_embeddings_generator()
            assert embedder is not None
            assert embedder.dimensions == 1536

    def test_embedding_generation(self):
        """Test embedding generation"""
        with patch("core.embeddings.create_embeddings_generator") as mock_create:
            mock_embedder = MagicMock()
            mock_embedder.generate_single_embedding.return_value = [0.1] * 1536
            mock_create.return_value = mock_embedder

            from core.embeddings import create_embeddings_generator

            embedder = create_embeddings_generator()
            embedding = embedder.generate_single_embedding("Test text")

            assert len(embedding) == 1536
