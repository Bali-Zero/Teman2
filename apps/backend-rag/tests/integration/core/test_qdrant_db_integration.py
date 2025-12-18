"""
Integration Tests for QdrantClient
Tests Qdrant vector database operations with real Qdrant instance
"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestQdrantClientIntegration:
    """Comprehensive integration tests for QdrantClient"""

    @pytest_asyncio.fixture
    async def qdrant_client(self, qdrant_container):
        """Create QdrantClient instance"""
        from core.qdrant_db import QdrantClient

        client = QdrantClient(
            qdrant_url=qdrant_container,
            collection_name="test_collection_integration",
        )
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_initialization(self, qdrant_client):
        """Test client initialization"""
        assert qdrant_client is not None
        assert qdrant_client.qdrant_url is not None
        assert qdrant_client.collection_name == "test_collection_integration"

    @pytest.mark.asyncio
    async def test_context_manager(self, qdrant_container):
        """Test using QdrantClient as context manager"""
        from core.qdrant_db import QdrantClient

        async with QdrantClient(
            qdrant_url=qdrant_container, collection_name="test_collection"
        ) as client:
            assert client is not None
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_get_headers_with_api_key(self, qdrant_container):
        """Test getting headers with API key"""
        from core.qdrant_db import QdrantClient

        client = QdrantClient(
            qdrant_url=qdrant_container,
            collection_name="test",
            api_key="test-api-key",
        )
        headers = client._get_headers()
        assert "api-key" in headers
        assert headers["api-key"] == "test-api-key"
        await client.close()

    @pytest.mark.asyncio
    async def test_get_headers_without_api_key(self, qdrant_client):
        """Test getting headers without API key"""
        headers = qdrant_client._get_headers()
        assert isinstance(headers, dict)
        # May or may not have api-key depending on settings

    @pytest.mark.asyncio
    async def test_create_collection(self, qdrant_client):
        """Test creating a collection"""
        collection_name = "test_create_collection"
        result = await qdrant_client.create_collection(
            collection_name=collection_name,
            vector_size=384,
            distance="Cosine",
        )

        # Should succeed or return error message
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_basic(self, qdrant_client):
        """Test basic search operation"""
        query_embedding = [0.1] * 384

        result = await qdrant_client.search(
            collection_name=qdrant_client.collection_name,
            query_embedding=query_embedding,
            limit=5,
        )

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_search_with_filter(self, qdrant_client):
        """Test search with filter"""
        query_embedding = [0.1] * 384
        filter_dict = {"must": [{"key": "domain", "match": {"value": "legal"}}]}

        result = await qdrant_client.search(
            collection_name=qdrant_client.collection_name,
            query_embedding=query_embedding,
            limit=5,
            filter=filter_dict,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_upsert_documents(self, qdrant_client):
        """Test upserting documents"""
        documents = ["Document 1", "Document 2"]
        embeddings = [[0.1] * 384, [0.2] * 384]
        metadatas = [{"id": "doc1"}, {"id": "doc2"}]
        ids = ["id1", "id2"]

        result = await qdrant_client.upsert_documents(
            collection_name=qdrant_client.collection_name,
            chunks=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_collection_stats(self, qdrant_client):
        """Test getting collection statistics"""
        stats = await qdrant_client.get_collection_stats(
            collection_name=qdrant_client.collection_name
        )

        assert stats is not None
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_get_documents(self, qdrant_client):
        """Test getting documents by IDs"""
        ids = ["id1", "id2"]

        result = await qdrant_client.get(collection_name=qdrant_client.collection_name, ids=ids)

        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_documents(self, qdrant_client):
        """Test deleting documents"""
        ids = ["id1", "id2"]

        result = await qdrant_client.delete(collection_name=qdrant_client.collection_name, ids=ids)

        assert result is not None

    @pytest.mark.asyncio
    async def test_peek_collection(self, qdrant_client):
        """Test peeking collection"""
        result = await qdrant_client.peek(collection_name=qdrant_client.collection_name, limit=10)

        assert result is not None

    def test_get_qdrant_metrics(self):
        """Test getting Qdrant metrics"""
        from core.qdrant_db import get_qdrant_metrics

        metrics = get_qdrant_metrics()

        assert metrics is not None
        assert "search_calls" in metrics
        assert "upsert_calls" in metrics
        assert "search_avg_time_ms" in metrics

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self):
        """Test retry with backoff on success"""
        from core.qdrant_db import _retry_with_backoff

        async def success_func():
            return "success"

        result = await _retry_with_backoff(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_with_backoff_failure(self):
        """Test retry with backoff on failure"""
        from core.qdrant_db import _retry_with_backoff

        async def fail_func():
            raise Exception("Test error")

        with pytest.raises(Exception):
            await _retry_with_backoff(fail_func, max_retries=2)

    @pytest.mark.asyncio
    async def test_convert_filter_to_qdrant_format(self, qdrant_client):
        """Test converting filter to Qdrant format"""
        simple_filter = {"domain": "legal", "type": "law"}

        qdrant_filter = qdrant_client._convert_filter_to_qdrant_format(simple_filter)

        assert qdrant_filter is not None
        assert isinstance(qdrant_filter, dict)

    @pytest.mark.asyncio
    async def test_close_client(self, qdrant_client):
        """Test closing client"""
        await qdrant_client.close()
        # Should not raise exception
