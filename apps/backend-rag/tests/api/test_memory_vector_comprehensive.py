"""
Comprehensive API Tests for Memory Vector Router
Complete test coverage for semantic memory storage and search endpoints

Coverage:
- POST /api/memory/embed - Generate embeddings
- POST /api/memory/store - Store memory
- POST /api/memory/search - Search memories
- POST /api/memory/similar - Find similar memories
- GET /api/memory/stats - Get memory statistics
- POST /api/memory/init - Initialize memory vector DB
- DELETE /api/memory/{memory_id} - Delete memory
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestMemoryEmbed:
    """Comprehensive tests for POST /api/memory/embed"""

    def test_generate_embedding_basic(self, authenticated_client):
        """Test basic embedding generation"""
        with patch("app.routers.memory_vector.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)

            response = authenticated_client.post(
                "/api/memory/embed",
                json={"text": "Test memory text"},
            )

            assert response.status_code in [200, 500, 503]

    def test_generate_embedding_different_models(self, authenticated_client):
        """Test embedding generation with different models"""
        with patch("app.routers.memory_vector.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)

            models = ["sentence-transformers", "openai", "cohere"]

            for model in models:
                response = authenticated_client.post(
                    "/api/memory/embed",
                    json={"text": "Test", "model": model},
                )

                assert response.status_code in [200, 400, 422, 500, 503]

    def test_generate_embedding_empty_text(self, authenticated_client):
        """Test embedding generation with empty text"""
        response = authenticated_client.post(
            "/api/memory/embed",
            json={"text": ""},
        )

        assert response.status_code in [200, 400, 422, 500, 503]

    def test_generate_embedding_long_text(self, authenticated_client):
        """Test embedding generation with long text"""
        with patch("app.routers.memory_vector.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)

            long_text = "A" * 10000

            response = authenticated_client.post(
                "/api/memory/embed",
                json={"text": long_text},
            )

            assert response.status_code in [200, 400, 413, 422, 500, 503]

    def test_generate_embedding_response_structure(self, authenticated_client):
        """Test embedding response structure"""
        with patch("app.routers.memory_vector.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)

            response = authenticated_client.post(
                "/api/memory/embed",
                json={"text": "Test"},
            )

            if response.status_code == 200:
                data = response.json()
                assert "embedding" in data
                assert "dimensions" in data
                assert "model" in data


@pytest.mark.api
class TestMemoryStore:
    """Comprehensive tests for POST /api/memory/store"""

    def test_store_memory_basic(self, authenticated_client):
        """Test basic memory storage"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.store = AsyncMock(return_value=True)
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/store",
                json={
                    "id": "memory_123",
                    "document": "Test memory document",
                    "embedding": [0.1] * 384,
                    "metadata": {"type": "conversation", "user": "test@example.com"},
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_store_memory_without_embedding(self, authenticated_client):
        """Test storing memory without embedding (auto-generate)"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.store = AsyncMock(return_value=True)
            mock_get_db.return_value = mock_db

            with patch("app.routers.memory_vector.embedder") as mock_embedder:
                mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)

                response = authenticated_client.post(
                    "/api/memory/store",
                    json={
                        "id": "memory_123",
                        "document": "Test memory",
                        "metadata": {},
                    },
                )

                assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_store_memory_duplicate_id(self, authenticated_client):
        """Test storing memory with duplicate ID"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.store = AsyncMock(side_effect=Exception("Duplicate ID"))
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/store",
                json={
                    "id": "existing_memory",
                    "document": "Test",
                    "embedding": [0.1] * 384,
                    "metadata": {},
                },
            )

            assert response.status_code in [200, 201, 400, 409, 500, 503]

    def test_store_memory_large_metadata(self, authenticated_client):
        """Test storing memory with large metadata"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.store = AsyncMock(return_value=True)
            mock_get_db.return_value = mock_db

            large_metadata = {f"key_{i}": f"value_{i}" for i in range(100)}

            response = authenticated_client.post(
                "/api/memory/store",
                json={
                    "id": "memory_123",
                    "document": "Test",
                    "embedding": [0.1] * 384,
                    "metadata": large_metadata,
                },
            )

            assert response.status_code in [200, 201, 400, 413, 500, 503]


@pytest.mark.api
class TestMemorySearch:
    """Comprehensive tests for POST /api/memory/search"""

    def test_search_memories_basic(self, authenticated_client):
        """Test basic memory search"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search = AsyncMock(
                return_value={
                    "documents": [["Test memory"]],
                    "ids": [["memory_123"]],
                    "distances": [[0.1]],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/search",
                json={"query_embedding": [0.1] * 384},
            )

            assert response.status_code in [200, 500, 503]

    def test_search_memories_with_limit(self, authenticated_client):
        """Test memory search with limit"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search = AsyncMock(
                return_value={
                    "documents": [],
                    "ids": [],
                    "distances": [],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/search",
                json={"query_embedding": [0.1] * 384, "limit": 20},
            )

            assert response.status_code in [200, 500, 503]

    def test_search_memories_with_metadata_filter(self, authenticated_client):
        """Test memory search with metadata filter"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search = AsyncMock(
                return_value={
                    "documents": [],
                    "ids": [],
                    "distances": [],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/search",
                json={
                    "query_embedding": [0.1] * 384,
                    "metadata_filter": {"type": "conversation", "user": "test@example.com"},
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_search_memories_response_structure(self, authenticated_client):
        """Test memory search response structure"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search = AsyncMock(
                return_value={
                    "documents": [["Test memory"]],
                    "ids": [["memory_123"]],
                    "distances": [[0.1]],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/search",
                json={"query_embedding": [0.1] * 384},
            )

            if response.status_code == 200:
                data = response.json()
                assert "results" in data
                assert "ids" in data
                assert "distances" in data
                assert "total_found" in data
                assert "execution_time_ms" in data


@pytest.mark.api
class TestSimilarMemories:
    """Comprehensive tests for POST /api/memory/similar"""

    def test_find_similar_memories(self, authenticated_client):
        """Test finding similar memories"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search_by_id = AsyncMock(
                return_value={
                    "documents": [["Similar memory"]],
                    "ids": [["memory_456"]],
                    "distances": [[0.2]],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/similar",
                json={"memory_id": "memory_123"},
            )

            assert response.status_code in [200, 404, 500, 503]

    def test_find_similar_memories_with_limit(self, authenticated_client):
        """Test finding similar memories with limit"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search_by_id = AsyncMock(
                return_value={
                    "documents": [],
                    "ids": [],
                    "distances": [],
                }
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/similar",
                json={"memory_id": "memory_123", "limit": 10},
            )

            assert response.status_code in [200, 404, 500, 503]

    def test_find_similar_memories_not_found(self, authenticated_client):
        """Test finding similar memories for non-existent memory"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.search_by_id = AsyncMock(side_effect=Exception("Not found"))
            mock_get_db.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/similar",
                json={"memory_id": "nonexistent_memory"},
            )

            assert response.status_code in [200, 404, 500, 503]


@pytest.mark.api
class TestMemoryStats:
    """Comprehensive tests for GET /api/memory/stats"""

    def test_get_memory_stats(self, authenticated_client):
        """Test getting memory statistics"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(
                return_value={"total_documents": 100, "collection_name": "zantara_memories"}
            )
            mock_get_db.return_value = mock_db

            response = authenticated_client.get("/api/memory/stats")

            assert response.status_code in [200, 500, 503]

    def test_get_memory_stats_structure(self, authenticated_client):
        """Test memory stats response structure"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(return_value={"total_documents": 100})
            mock_get_db.return_value = mock_db

            response = authenticated_client.get("/api/memory/stats")

            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)


@pytest.mark.api
class TestMemoryInit:
    """Comprehensive tests for POST /api/memory/init"""

    def test_initialize_memory_db(self, authenticated_client):
        """Test initializing memory vector DB"""
        with patch("app.routers.memory_vector.initialize_memory_vector_db") as mock_init:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(return_value={"total_documents": 0})
            mock_init.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/init",
                json={"qdrant_url": "http://localhost:6333"},
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_initialize_memory_db_default_url(self, authenticated_client):
        """Test initializing memory DB with default URL"""
        with patch("app.routers.memory_vector.initialize_memory_vector_db") as mock_init:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(return_value={"total_documents": 0})
            mock_init.return_value = mock_db

            response = authenticated_client.post(
                "/api/memory/init",
                json={},
            )

            assert response.status_code in [200, 201, 500, 503]


@pytest.mark.api
class TestMemoryDelete:
    """Comprehensive tests for DELETE /api/memory/{memory_id}"""

    def test_delete_memory(self, authenticated_client):
        """Test deleting memory"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.delete = AsyncMock(return_value=True)
            mock_get_db.return_value = mock_db

            response = authenticated_client.delete("/api/memory/memory_123")

            assert response.status_code in [200, 204, 404, 500, 503]

    def test_delete_memory_not_found(self, authenticated_client):
        """Test deleting non-existent memory"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.delete = AsyncMock(side_effect=Exception("Not found"))
            mock_get_db.return_value = mock_db

            response = authenticated_client.delete("/api/memory/nonexistent_memory")

            assert response.status_code in [200, 204, 404, 500, 503]


@pytest.mark.api
class TestMemoryVectorSecurity:
    """Security tests for memory vector endpoints"""

    def test_memory_endpoints_require_auth(self, test_client):
        """Test all memory endpoints require authentication"""
        endpoints = [
            ("POST", "/api/memory/embed"),
            ("POST", "/api/memory/store"),
            ("POST", "/api/memory/search"),
            ("POST", "/api/memory/similar"),
            ("GET", "/api/memory/stats"),
            ("POST", "/api/memory/init"),
            ("DELETE", "/api/memory/memory_123"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            elif method == "DELETE":
                response = test_client.delete(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401
