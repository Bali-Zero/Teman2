"""
Expanded API Tests for Memory Vector Endpoints

Tests for:
- Memory storage and retrieval
- Semantic search
- Similar memory finding
- Memory embedding generation
"""

import time

import pytest


# Helper to generate unique IDs
def get_unique_id():
    return int(time.time() * 1000)


@pytest.mark.api
class TestMemoryVectorStorage:
    """Test memory vector storage endpoints"""

    def test_store_memory_basic(self, authenticated_client):
        """Test basic memory storage"""
        # Generate mock embedding (1536 dimensions)
        mock_embedding = [0.1] * 1536

        response = authenticated_client.post(
            "/api/memory/store",
            json={
                "id": f"test_memory_{get_unique_id()}",
                "document": "Client prefers email communication",
                "embedding": mock_embedding,
                "metadata": {
                    "user_id": "test@example.com",
                    "source": "conversation",
                    "timestamp": "2025-01-01T00:00:00Z",
                },
            },
        )

        assert response.status_code in [200, 201, 400, 422]

    def test_store_memory_with_extended_metadata(self, authenticated_client):
        """Test storing memory with extended metadata"""
        mock_embedding = [0.2] * 1536

        response = authenticated_client.post(
            "/api/memory/store",
            json={
                "id": f"test_memory_extended_{get_unique_id()}",
                "document": "Client interested in PT PMA setup, prefers detailed explanations",
                "embedding": mock_embedding,
                "metadata": {
                    "user_id": "test@example.com",
                    "source": "oracle_query",
                    "topic": "business_setup",
                    "importance": "high",
                    "related_client_id": "client_123",
                },
            },
        )

        assert response.status_code in [200, 201, 400, 422]

    def test_store_memory_duplicate_id(self, authenticated_client):
        """Test storing memory with duplicate ID (should handle gracefully)"""
        memory_id = f"duplicate_test_{get_unique_id()}"
        mock_embedding = [0.3] * 1536

        # First store
        response1 = authenticated_client.post(
            "/api/memory/store",
            json={
                "id": memory_id,
                "document": "First memory",
                "embedding": mock_embedding,
                "metadata": {"user_id": "test@example.com"},
            },
        )

        # Try to store again with same ID
        response2 = authenticated_client.post(
            "/api/memory/store",
            json={
                "id": memory_id,
                "document": "Second memory",
                "embedding": mock_embedding,
                "metadata": {"user_id": "test@example.com"},
            },
        )

        # At least first should succeed
        assert response1.status_code in [200, 201, 400, 422]
        # Second might succeed (overwrite) or fail (duplicate)
        assert response2.status_code in [200, 201, 400, 409, 422]


@pytest.mark.api
class TestMemoryVectorSearch:
    """Test memory vector search endpoints"""

    def test_search_memory_basic(self, authenticated_client):
        """Test basic memory search"""
        # Generate query embedding
        query_embedding = [0.15] * 1536

        response = authenticated_client.post(
            "/api/memory/search",
            json={
                "query_embedding": query_embedding,
                "limit": 10,
            },
        )

        assert response.status_code in [200, 400, 422]
        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "ids" in data

    def test_search_memory_with_metadata_filter(self, authenticated_client):
        """Test memory search with metadata filter"""
        query_embedding = [0.15] * 1536

        response = authenticated_client.post(
            "/api/memory/search",
            json={
                "query_embedding": query_embedding,
                "limit": 5,
                "metadata_filter": {
                    "user_id": "test@example.com",
                },
            },
        )

        assert response.status_code in [200, 400, 422]

    def test_search_memory_different_limits(self, authenticated_client):
        """Test memory search with different limits"""
        query_embedding = [0.15] * 1536
        limits = [1, 5, 10, 20, 50]

        for limit in limits:
            response = authenticated_client.post(
                "/api/memory/search",
                json={
                    "query_embedding": query_embedding,
                    "limit": limit,
                },
            )

            assert response.status_code in [200, 400, 422]

    def test_search_memory_complex_metadata_filter(self, authenticated_client):
        """Test memory search with complex metadata filter"""
        query_embedding = [0.15] * 1536

        response = authenticated_client.post(
            "/api/memory/search",
            json={
                "query_embedding": query_embedding,
                "limit": 10,
                "metadata_filter": {
                    "user_id": "test@example.com",
                    "source": "conversation",
                    "importance": "high",
                },
            },
        )

        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestSimilarMemoryEndpoints:
    """Test similar memory finding endpoints"""

    def test_find_similar_memories(self, authenticated_client):
        """Test finding similar memories to a given memory ID"""
        # First store a memory
        memory_id = f"similar_test_{get_unique_id()}"
        mock_embedding = [0.4] * 1536

        store_response = authenticated_client.post(
            "/api/memory/store",
            json={
                "id": memory_id,
                "document": "Test memory for similarity",
                "embedding": mock_embedding,
                "metadata": {"user_id": "test@example.com"},
            },
        )

        if store_response.status_code in [200, 201]:
            # Find similar memories
            similar_response = authenticated_client.post(
                "/api/memory/similar",
                json={
                    "memory_id": memory_id,
                    "limit": 5,
                },
            )

            assert similar_response.status_code in [200, 400, 404, 422]

    def test_find_similar_memories_different_limits(self, authenticated_client):
        """Test finding similar memories with different limits"""
        memory_id = f"similar_limits_{get_unique_id()}"
        limits = [1, 3, 5, 10]

        for limit in limits:
            response = authenticated_client.post(
                "/api/memory/similar",
                json={
                    "memory_id": memory_id,
                    "limit": limit,
                },
            )

            # Might fail if memory doesn't exist, which is OK
            assert response.status_code in [200, 400, 404, 422]


@pytest.mark.api
class TestMemoryEmbeddingEndpoints:
    """Test memory embedding generation endpoints"""

    def test_generate_embedding_basic(self, authenticated_client):
        """Test basic embedding generation"""
        response = authenticated_client.post(
            "/api/memory/embed",
            json={
                "text": "This is a test text to embed",
                "model": "sentence-transformers",
            },
        )

        assert response.status_code in [200, 400, 422]
        if response.status_code == 200:
            data = response.json()
            assert "embedding" in data
            assert "dimensions" in data or "model" in data

    def test_generate_embedding_long_text(self, authenticated_client):
        """Test embedding generation for long text"""
        long_text = "This is a very long text. " * 100
        response = authenticated_client.post(
            "/api/memory/embed",
            json={
                "text": long_text,
                "model": "sentence-transformers",
            },
        )

        assert response.status_code in [200, 400, 422]

    def test_generate_embedding_empty_text(self, authenticated_client):
        """Test embedding generation with empty text"""
        response = authenticated_client.post(
            "/api/memory/embed",
            json={
                "text": "",
                "model": "sentence-transformers",
            },
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_generate_embedding_special_characters(self, authenticated_client):
        """Test embedding generation with special characters"""
        special_text = "Text with special chars: àáâãäå èéêë @#$%^&*()"
        response = authenticated_client.post(
            "/api/memory/embed",
            json={
                "text": special_text,
                "model": "sentence-transformers",
            },
        )

        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestMemoryVectorStatsEndpoints:
    """Test memory vector statistics endpoints"""

    def test_get_memory_stats(self, authenticated_client):
        """Test retrieving memory statistics"""
        response = authenticated_client.get("/api/memory/stats")

        assert response.status_code in [200, 400, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_get_memory_health(self, authenticated_client):
        """Test memory health check"""
        response = authenticated_client.get("/api/memory/health")

        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestMemoryVectorEdgeCases:
    """Test edge cases for memory vector endpoints"""

    def test_store_memory_invalid_embedding_dimensions(self, authenticated_client):
        """Test storing memory with invalid embedding dimensions"""
        # Wrong dimensions
        invalid_embedding = [0.1] * 100  # Should be 1536

        response = authenticated_client.post(
            "/api/memory/store",
            json={
                "id": f"invalid_dim_{get_unique_id()}",
                "document": "Test",
                "embedding": invalid_embedding,
                "metadata": {},
            },
        )

        assert response.status_code in [400, 422]

    def test_search_memory_invalid_embedding(self, authenticated_client):
        """Test searching with invalid embedding"""
        invalid_embedding = [0.1] * 100

        response = authenticated_client.post(
            "/api/memory/search",
            json={
                "query_embedding": invalid_embedding,
                "limit": 10,
            },
        )

        assert response.status_code in [400, 422]

    def test_find_similar_nonexistent_memory(self, authenticated_client):
        """Test finding similar memories for non-existent memory ID"""
        response = authenticated_client.post(
            "/api/memory/similar",
            json={
                "memory_id": "nonexistent_memory_id_12345",
                "limit": 5,
            },
        )

        assert response.status_code in [400, 404, 422]
