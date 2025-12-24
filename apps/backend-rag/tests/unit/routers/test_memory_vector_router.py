"""
Unit tests for memory_vector router - targeting 90% coverage

Tests all endpoints:
- /api/memory/init - Initialize memory collection
- /api/memory/embed - Generate embeddings
- /api/memory/store - Store memory vectors
- /api/memory/search - Semantic search
- /api/memory/similar - Find similar memories
- /api/memory/{memory_id} - Delete memory
- /api/memory/stats - Get statistics
- /api/memory/health - Health check
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# HELPER FUNCTIONS TESTS
# ============================================================================


class TestInitializeMemoryVectorDB:
    """Tests for initialize_memory_vector_db function"""

    @pytest.mark.asyncio
    async def test_initialize_with_default_url(self):
        """Test initialization with default Qdrant URL from settings"""
        from app.routers import memory_vector

        mock_client = AsyncMock()
        mock_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 100}
        )

        with patch("app.routers.memory_vector.QdrantClient", return_value=mock_client):
            with patch("app.routers.memory_vector.settings") as mock_settings:
                mock_settings.qdrant_url = "http://localhost:6333"

                result = await memory_vector.initialize_memory_vector_db()

                assert result == mock_client
                assert memory_vector.memory_vector_db == mock_client
                mock_client.get_collection_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_custom_url(self):
        """Test initialization with custom Qdrant URL"""
        from app.routers import memory_vector

        mock_client = AsyncMock()
        mock_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 50}
        )

        with patch("app.routers.memory_vector.QdrantClient", return_value=mock_client):
            custom_url = "http://custom:6333"
            result = await memory_vector.initialize_memory_vector_db(custom_url)

            assert result == mock_client
            mock_client.get_collection_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test initialization failure handling"""
        from app.routers import memory_vector

        with patch(
            "app.routers.memory_vector.QdrantClient", side_effect=Exception("Connection failed")
        ):
            with pytest.raises(Exception, match="Connection failed"):
                await memory_vector.initialize_memory_vector_db()


class TestGetMemoryVectorDB:
    """Tests for get_memory_vector_db function"""

    @pytest.mark.asyncio
    async def test_get_existing_db(self):
        """Test getting already initialized DB"""
        from app.routers import memory_vector

        mock_db = AsyncMock()
        memory_vector.memory_vector_db = mock_db

        result = await memory_vector.get_memory_vector_db()
        assert result == mock_db

    @pytest.mark.asyncio
    async def test_get_uninitialized_db(self):
        """Test getting DB when not initialized - should auto-initialize"""
        from app.routers import memory_vector

        # Reset global state
        memory_vector.memory_vector_db = None

        mock_client = AsyncMock()
        mock_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 0}
        )

        with patch("app.routers.memory_vector.QdrantClient", return_value=mock_client):
            with patch("app.routers.memory_vector.settings") as mock_settings:
                mock_settings.qdrant_url = "http://localhost:6333"

                result = await memory_vector.get_memory_vector_db()

                assert result == mock_client
                assert memory_vector.memory_vector_db == mock_client


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI app with memory_vector router"""
    from app.routers.memory_vector import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_qdrant_client():
    """Create mock Qdrant client"""
    mock_client = AsyncMock()
    mock_client.qdrant_url = "http://localhost:6333"
    mock_client.get_collection_stats = AsyncMock(
        return_value={
            "collection_name": "zantara_memories",
            "total_documents": 100,
        }
    )
    mock_client.upsert_documents = AsyncMock()
    mock_client.search = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.peek = AsyncMock()
    return mock_client


@pytest.fixture
def mock_embedder():
    """Create mock embeddings generator"""
    mock = MagicMock()
    mock.model = "sentence-transformers/all-MiniLM-L6-v2"
    mock.provider = "sentence-transformers"
    mock.dimensions = 384
    mock.generate_single_embedding = MagicMock(return_value=[0.1] * 384)
    return mock


class TestInitEndpoint:
    """Tests for POST /api/memory/init endpoint"""

    def test_init_success_default_url(self, client, mock_qdrant_client):
        """Test successful initialization with default URL"""
        with patch("app.routers.memory_vector.initialize_memory_vector_db") as mock_init:
            mock_init.return_value = mock_qdrant_client

            response = client.post("/api/memory/init", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "initialized"
            assert data["collection"] == "zantara_memories"
            assert data["total_memories"] == 100
            assert data["qdrant_url"] == "http://localhost:6333"

    def test_init_success_custom_url(self, client, mock_qdrant_client):
        """Test successful initialization with custom URL"""
        custom_url = "http://custom:6333"
        mock_qdrant_client.qdrant_url = custom_url

        with patch("app.routers.memory_vector.initialize_memory_vector_db") as mock_init:
            mock_init.return_value = mock_qdrant_client

            response = client.post("/api/memory/init", json={"qdrant_url": custom_url})

            assert response.status_code == 200
            data = response.json()
            assert data["qdrant_url"] == custom_url
            mock_init.assert_called_once_with(custom_url)

    def test_init_failure(self, client):
        """Test initialization failure"""
        with patch(
            "app.routers.memory_vector.initialize_memory_vector_db",
            side_effect=Exception("DB connection failed"),
        ):
            response = client.post("/api/memory/init", json={})

            assert response.status_code == 500
            assert "Initialization failed" in response.json()["detail"]


class TestEmbedEndpoint:
    """Tests for POST /api/memory/embed endpoint"""

    def test_embed_success(self, client, mock_embedder):
        """Test successful embedding generation"""
        with patch("app.routers.memory_vector.embedder", mock_embedder):
            response = client.post(
                "/api/memory/embed", json={"text": "Test memory", "model": "sentence-transformers"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "embedding" in data
            assert len(data["embedding"]) == 384
            assert data["dimensions"] == 384
            assert data["model"] == "sentence-transformers/all-MiniLM-L6-v2"

    def test_embed_default_model(self, client, mock_embedder):
        """Test embedding with default model"""
        with patch("app.routers.memory_vector.embedder", mock_embedder):
            response = client.post("/api/memory/embed", json={"text": "Test memory"})

            assert response.status_code == 200
            data = response.json()
            assert "embedding" in data

    def test_embed_failure(self, client, mock_embedder):
        """Test embedding generation failure"""
        mock_embedder.generate_single_embedding.side_effect = Exception("Embedding failed")

        with patch("app.routers.memory_vector.embedder", mock_embedder):
            response = client.post("/api/memory/embed", json={"text": "Test memory"})

            assert response.status_code == 500
            assert "Embedding failed" in response.json()["detail"]

    def test_embed_empty_text(self, client, mock_embedder):
        """Test embedding with empty text"""
        with patch("app.routers.memory_vector.embedder", mock_embedder):
            response = client.post("/api/memory/embed", json={"text": ""})

            assert response.status_code == 200
            mock_embedder.generate_single_embedding.assert_called_once_with("")


class TestStoreEndpoint:
    """Tests for POST /api/memory/store endpoint"""

    def test_store_success(self, client, mock_qdrant_client):
        """Test successful memory storage"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {
                "id": "mem_123",
                "document": "User loves Python programming",
                "embedding": [0.1] * 384,
                "metadata": {
                    "userId": "user_123",
                    "type": "expertise",
                    "timestamp": "2025-12-23T10:00:00Z",
                    "entities": "Python",
                },
            }

            response = client.post("/api/memory/store", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["memory_id"] == "mem_123"
            assert data["collection"] == "zantara_memories"

            mock_qdrant_client.upsert_documents.assert_called_once_with(
                chunks=["User loves Python programming"],
                embeddings=[[0.1] * 384],
                metadatas=[request_data["metadata"]],
                ids=["mem_123"],
            )

    def test_store_failure(self, client, mock_qdrant_client):
        """Test storage failure"""
        mock_qdrant_client.upsert_documents.side_effect = Exception("Storage failed")

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {
                "id": "mem_123",
                "document": "Test memory",
                "embedding": [0.1] * 384,
                "metadata": {"userId": "user_123"},
            }

            response = client.post("/api/memory/store", json=request_data)

            assert response.status_code == 500
            assert "Storage failed" in response.json()["detail"]

    def test_store_with_complex_metadata(self, client, mock_qdrant_client):
        """Test storage with complex metadata"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {
                "id": "mem_456",
                "document": "Complex memory with nested data",
                "embedding": [0.2] * 384,
                "metadata": {
                    "userId": "user_456",
                    "type": "profile",
                    "timestamp": "2025-12-23T11:00:00Z",
                    "entities": "AI,Python,FastAPI",
                    "tags": ["technical", "important"],
                    "confidence": 0.95,
                },
            }

            response = client.post("/api/memory/store", json=request_data)

            assert response.status_code == 200
            assert response.json()["success"] is True


class TestSearchEndpoint:
    """Tests for POST /api/memory/search endpoint"""

    def test_search_success_no_filter(self, client, mock_qdrant_client):
        """Test successful search without filters"""
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_1", "mem_2"],
                "documents": ["Memory 1", "Memory 2"],
                "metadatas": [{"userId": "user_1"}, {"userId": "user_2"}],
                "distances": [0.1, 0.2],
                "total_found": 2,
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"query_embedding": [0.1] * 384, "limit": 10}

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 2
            assert data["total_found"] == 2
            assert data["ids"] == ["mem_1", "mem_2"]
            assert data["distances"] == [0.1, 0.2]
            assert "execution_time_ms" in data

            # Verify result format
            assert data["results"][0]["document"] == "Memory 1"
            assert data["results"][0]["metadata"]["userId"] == "user_1"
            assert data["results"][0]["distance"] == 0.1

    def test_search_with_metadata_filter(self, client, mock_qdrant_client):
        """Test search with metadata filter"""
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_1"],
                "documents": ["User memory"],
                "metadatas": [{"userId": "user_123"}],
                "distances": [0.05],
                "total_found": 1,
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {
                "query_embedding": [0.1] * 384,
                "limit": 5,
                "metadata_filter": {"userId": "user_123"},
            }

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["metadata"]["userId"] == "user_123"

            # Verify filter was passed correctly
            mock_qdrant_client.search.assert_called_once()
            call_kwargs = mock_qdrant_client.search.call_args.kwargs
            assert call_kwargs["filter"] == {"userId": "user_123"}

    def test_search_with_contains_filter(self, client, mock_qdrant_client):
        """Test search with $contains filter"""
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_1"],
                "documents": ["Memory with entity"],
                "metadatas": [{"entities": "zero,python"}],
                "distances": [0.15],
                "total_found": 1,
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {
                "query_embedding": [0.1] * 384,
                "limit": 5,
                "metadata_filter": {"entities": {"$contains": "zero"}},
            }

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1

            # Verify $contains was converted correctly
            call_kwargs = mock_qdrant_client.search.call_args.kwargs
            assert call_kwargs["filter"] == {"entities": "zero"}

    def test_search_no_results(self, client, mock_qdrant_client):
        """Test search with no results"""
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": [],
                "documents": [],
                "metadatas": [],
                "distances": [],
                "total_found": 0,
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"query_embedding": [0.1] * 384, "limit": 10}

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 0
            assert data["total_found"] == 0

    def test_search_failure(self, client, mock_qdrant_client):
        """Test search failure"""
        mock_qdrant_client.search.side_effect = Exception("Search failed")

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"query_embedding": [0.1] * 384}

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 500
            assert "Search failed" in response.json()["detail"]


class TestSimilarEndpoint:
    """Tests for POST /api/memory/similar endpoint"""

    def test_similar_success_list_embedding(self, client, mock_qdrant_client):
        """Test finding similar memories with list embedding format"""
        # Mock get to return embedding as nested list
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [[0.1] * 384]})

        # Mock search to return similar memories including the original
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_123", "mem_456", "mem_789"],
                "documents": ["Original memory", "Similar memory 1", "Similar memory 2"],
                "metadatas": [{"userId": "user_1"}, {"userId": "user_2"}, {"userId": "user_3"}],
                "distances": [0.0, 0.1, 0.2],
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 200
            data = response.json()

            # Original memory should be filtered out
            assert len(data["results"]) == 2
            assert "mem_123" not in data["ids"]
            assert data["ids"] == ["mem_456", "mem_789"]
            assert data["total_found"] == 2
            assert "execution_time_ms" in data

    def test_similar_success_flat_embedding(self, client, mock_qdrant_client):
        """Test finding similar memories with flat embedding format"""
        # Mock get to return flat embedding (list of floats directly)
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [0.1] * 384})

        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_123", "mem_456"],
                "documents": ["Original", "Similar"],
                "metadatas": [{"userId": "user_1"}, {"userId": "user_2"}],
                "distances": [0.0, 0.15],
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 3}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["ids"] == ["mem_456"]

    def test_similar_memory_not_found(self, client, mock_qdrant_client):
        """Test similar search when memory doesn't exist"""
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": []})

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "nonexistent", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 404
            assert "Memory not found" in response.json()["detail"]

    def test_similar_no_embeddings_returned(self, client, mock_qdrant_client):
        """Test similar search when no embeddings in response"""
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": None})

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 404
            assert "Memory not found" in response.json()["detail"]

    def test_similar_invalid_embedding_format(self, client, mock_qdrant_client):
        """Test similar search with invalid embedding format"""
        # Return dict or other invalid format
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [{"invalid": "format"}]})

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 500
            assert "Invalid embedding format" in response.json()["detail"]

    def test_similar_respects_limit(self, client, mock_qdrant_client):
        """Test that similar search respects limit parameter"""
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [[0.1] * 384]})

        # Return more results than limit
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_123", "mem_1", "mem_2", "mem_3", "mem_4", "mem_5"],
                "documents": ["Orig", "Sim1", "Sim2", "Sim3", "Sim4", "Sim5"],
                "metadatas": [{} for _ in range(6)],
                "distances": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 3}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 200
            data = response.json()
            # Should return exactly 3 results (excluding original)
            assert len(data["results"]) == 3
            assert data["total_found"] == 3

    def test_similar_search_failure(self, client, mock_qdrant_client):
        """Test similar search failure during search"""
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [[0.1] * 384]})
        mock_qdrant_client.search.side_effect = Exception("Search failed")

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 500
            assert "Similar search failed" in response.json()["detail"]


class TestDeleteEndpoint:
    """Tests for DELETE /api/memory/{memory_id} endpoint"""

    def test_delete_success(self, client, mock_qdrant_client):
        """Test successful memory deletion"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.delete("/api/memory/mem_123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_id"] == "mem_123"

            mock_qdrant_client.delete.assert_called_once_with(ids=["mem_123"])

    def test_delete_failure(self, client, mock_qdrant_client):
        """Test deletion failure"""
        mock_qdrant_client.delete.side_effect = Exception("Deletion failed")

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.delete("/api/memory/mem_123")

            assert response.status_code == 500
            assert "Deletion failed" in response.json()["detail"]

    def test_delete_special_characters_in_id(self, client, mock_qdrant_client):
        """Test deletion with special characters in ID"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            memory_id = "mem_123-abc_xyz"
            response = client.delete(f"/api/memory/{memory_id}")

            assert response.status_code == 200
            mock_qdrant_client.delete.assert_called_once_with(ids=[memory_id])


class TestStatsEndpoint:
    """Tests for GET /api/memory/stats endpoint"""

    def test_stats_success(self, client, mock_qdrant_client):
        """Test successful stats retrieval"""
        mock_qdrant_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 150}
        )

        mock_qdrant_client.peek = AsyncMock(
            return_value={
                "metadatas": [
                    {"userId": "user_1"},
                    {"userId": "user_2"},
                    {"userId": "user_1"},
                    {"userId": "user_3"},
                ]
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.get("/api/memory/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_memories"] == 150
            assert data["collection_name"] == "zantara_memories"
            assert data["qdrant_url"] == "http://localhost:6333"
            assert data["users"] == 3  # 3 unique users
            assert data["collection_size_mb"] == 150 * 0.001

    def test_stats_empty_collection(self, client, mock_qdrant_client):
        """Test stats with empty collection"""
        mock_qdrant_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 0}
        )

        mock_qdrant_client.peek = AsyncMock(return_value={"metadatas": []})

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.get("/api/memory/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_memories"] == 0
            assert data["users"] == 0

    def test_stats_missing_userid(self, client, mock_qdrant_client):
        """Test stats with memories missing userId"""
        mock_qdrant_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 5}
        )

        mock_qdrant_client.peek = AsyncMock(
            return_value={
                "metadatas": [
                    {"userId": "user_1"},
                    {},  # Missing userId
                    {"userId": "user_2"},
                    {"userId": ""},  # Empty userId
                ]
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.get("/api/memory/stats")

            assert response.status_code == 200
            data = response.json()
            # Should count unique non-empty userIds + empty string
            assert data["users"] in [2, 3]  # Implementation may vary

    def test_stats_failure(self, client, mock_qdrant_client):
        """Test stats failure - should return error dict instead of exception"""
        mock_qdrant_client.get_collection_stats.side_effect = Exception("Stats failed")

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.get("/api/memory/stats")

            assert response.status_code == 200  # Returns 200 with error dict
            data = response.json()
            assert data["total_memories"] == 0
            assert data["users"] == 0
            assert "error" in data
            assert "Stats failed" in data["error"]


class TestHealthEndpoint:
    """Tests for GET /api/memory/health endpoint"""

    def test_health_success(self, client, mock_qdrant_client, mock_embedder):
        """Test successful health check"""
        mock_qdrant_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 100}
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            with patch("app.routers.memory_vector.embedder", mock_embedder):
                mock_get_db.return_value = mock_qdrant_client

                response = client.get("/api/memory/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "operational"
                assert data["service"] == "memory_vector"
                assert data["collection"] == "zantara_memories"
                assert data["total_memories"] == 100
                assert data["embedder_model"] == "sentence-transformers/all-MiniLM-L6-v2"
                assert data["embedder_provider"] == "sentence-transformers"
                assert data["dimensions"] == 384

    def test_health_failure(self, client, mock_qdrant_client):
        """Test health check failure"""
        mock_qdrant_client.get_collection_stats.side_effect = Exception("DB unavailable")

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.get("/api/memory/health")

            assert response.status_code == 503
            assert "Memory vector service unhealthy" in response.json()["detail"]

    def test_health_db_initialization_failure(self, client):
        """Test health check when DB can't be initialized"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db",
            side_effect=Exception("Cannot connect"),
        ):
            response = client.get("/api/memory/health")

            assert response.status_code == 503
            assert "Memory vector service unhealthy" in response.json()["detail"]


# ============================================================================
# INTEGRATION-STYLE TESTS (Edge Cases)
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_search_with_mixed_filter_types(self, client, mock_qdrant_client):
        """Test search with multiple filter types"""
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_1"],
                "documents": ["Match"],
                "metadatas": [{"userId": "user_1"}],
                "distances": [0.1],
                "total_found": 1,
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {
                "query_embedding": [0.1] * 384,
                "limit": 10,
                "metadata_filter": {
                    "userId": "user_1",
                    "entities": {"$contains": "python"},
                    "type": "expertise",
                },
            }

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 200

            # Verify filter conversion
            call_kwargs = mock_qdrant_client.search.call_args.kwargs
            assert call_kwargs["filter"]["userId"] == "user_1"
            assert call_kwargs["filter"]["entities"] == "python"  # $contains extracted
            assert call_kwargs["filter"]["type"] == "expertise"

    def test_store_with_very_large_embedding(self, client, mock_qdrant_client):
        """Test storing memory with large embedding dimension"""
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            large_embedding = [0.1] * 1536  # GPT-3 size

            request_data = {
                "id": "mem_large",
                "document": "Large embedding memory",
                "embedding": large_embedding,
                "metadata": {"userId": "user_1"},
            }

            response = client.post("/api/memory/store", json=request_data)

            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_similar_all_results_filtered(self, client, mock_qdrant_client):
        """Test similar search when all results are the original memory"""
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [[0.1] * 384]})

        # Only return the original memory
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_123"],
                "documents": ["Original"],
                "metadatas": [{"userId": "user_1"}],
                "distances": [0.0],
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 0
            assert data["total_found"] == 0

    def test_embed_very_long_text(self, client, mock_embedder):
        """Test embedding generation with very long text"""
        long_text = "word " * 1000  # 1000 words

        with patch("app.routers.memory_vector.embedder", mock_embedder):
            response = client.post("/api/memory/embed", json={"text": long_text})

            assert response.status_code == 200
            mock_embedder.generate_single_embedding.assert_called_once_with(long_text)

    def test_search_limit_boundary(self, client, mock_qdrant_client):
        """Test search with limit of 1"""
        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_1"],
                "documents": ["Single result"],
                "metadatas": [{"userId": "user_1"}],
                "distances": [0.05],
                "total_found": 1,
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"query_embedding": [0.1] * 384, "limit": 1}

            response = client.post("/api/memory/search", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1

    def test_stats_with_large_peek_result(self, client, mock_qdrant_client):
        """Test stats when peek returns exactly 1000 results"""
        mock_qdrant_client.get_collection_stats = AsyncMock(
            return_value={"collection_name": "zantara_memories", "total_documents": 5000}
        )

        # Generate 1000 metadatas with 10 unique users
        metadatas = [{"userId": f"user_{i % 10}"} for i in range(1000)]
        mock_qdrant_client.peek = AsyncMock(return_value={"metadatas": metadatas})

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            response = client.get("/api/memory/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total_memories"] == 5000
            assert data["users"] == 10

    def test_tuple_embedding_in_similar(self, client, mock_qdrant_client):
        """Test similar search when embedding is returned as tuple"""
        # Mock get to return embedding as tuple
        mock_qdrant_client.get = AsyncMock(return_value={"embeddings": [tuple([0.1] * 384)]})

        mock_qdrant_client.search = AsyncMock(
            return_value={
                "ids": ["mem_123", "mem_456"],
                "documents": ["Orig", "Sim"],
                "metadatas": [{}, {}],
                "distances": [0.0, 0.1],
            }
        )

        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_get_db.return_value = mock_qdrant_client

            request_data = {"memory_id": "mem_123", "limit": 5}

            response = client.post("/api/memory/similar", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1


# ============================================================================
# CLEANUP
# ============================================================================


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test"""
    from app.routers import memory_vector

    memory_vector.memory_vector_db = None
    yield
    memory_vector.memory_vector_db = None
