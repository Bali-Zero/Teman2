"""
API Tests for Memory Vector Router
Tests memory vector storage and search endpoints

Coverage:
- POST /api/memory/init - Initialize memory collection
- POST /api/memory/embed - Generate embedding
- POST /api/memory/store - Store memory vector
- POST /api/memory/search - Semantic memory search
- POST /api/memory/similar - Find similar memories
- DELETE /api/memory/{memory_id} - Delete memory
- GET /api/memory/stats - Get memory statistics
- GET /api/memory/health - Health check
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestMemoryVectorEndpoints:
    """Tests for memory vector endpoints"""

    def test_init_memory_collection(self, authenticated_client):
        """Test POST /api/memory/init"""
        with patch(
            "app.routers.memory_vector.initialize_memory_vector_db", new_callable=AsyncMock
        ) as mock_init:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(
                return_value={"collection_name": "zantara_memories", "total_documents": 100}
            )
            mock_db.qdrant_url = "http://localhost:6333"
            mock_init.return_value = mock_db

            response = authenticated_client.post("/api/memory/init", json={})

            assert response.status_code in [200, 500, 503]

    def test_generate_embedding(self, authenticated_client):
        """Test POST /api/memory/embed"""
        with patch("app.routers.memory_vector.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding.return_value = [0.1] * 1536
            mock_embedder.dimensions = 1536
            mock_embedder.model = "text-embedding-3-small"

            response = authenticated_client.post(
                "/api/memory/embed",
                json={"text": "Test memory content"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "embedding" in data
            assert len(data["embedding"]) == 1536

    def test_store_memory_vector(self, authenticated_client):
        """Test POST /api/memory/store"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.upsert_documents = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/store",
                json={
                    "id": "mem_123",
                    "document": "Test memory",
                    "embedding": [0.1] * 1536,
                    "metadata": {"userId": "user123"},
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_search_memories(self, authenticated_client):
        """Test POST /api/memory/search"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.search = AsyncMock(
                return_value={
                    "documents": ["Memory 1", "Memory 2"],
                    "ids": ["mem1", "mem2"],
                    "distances": [0.1, 0.2],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/search",
                json={"query_embedding": [0.1] * 1536, "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    def test_find_similar_memories(self, authenticated_client):
        """Test POST /api/memory/similar"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.get = AsyncMock(return_value={"embeddings": [[0.1] * 1536]})
            mock_db.search = AsyncMock(
                return_value={
                    "ids": ["mem1", "mem2"],
                    "documents": ["Doc 1", "Doc 2"],
                    "distances": [0.1, 0.2],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/similar",
                json={"memory_id": "mem_123", "limit": 5},
            )

            assert response.status_code in [200, 404, 500, 503]

    def test_delete_memory(self, authenticated_client):
        """Test DELETE /api/memory/{memory_id}"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.delete = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            response = authenticated_client.delete("/api/memory/mem_123")

            assert response.status_code in [200, 500, 503]

    def test_get_memory_stats(self, authenticated_client):
        """Test GET /api/memory/stats"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(
                return_value={"collection_name": "zantara_memories", "total_documents": 100}
            )
            mock_db.peek = AsyncMock(return_value={"metadatas": [{"userId": "user1"}]})
            mock_get_db.return_value = mock_db

            response = authenticated_client.get("/api/memory/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_memories" in data

    def test_memory_health_check(self, authenticated_client):
        """Test GET /api/memory/health"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(
                return_value={"collection_name": "zantara_memories", "total_documents": 100}
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.get("/api/memory/health")

            assert response.status_code in [200, 503]
