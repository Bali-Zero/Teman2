"""
Unit tests for QdrantClient filter conversion methods in core/qdrant_db.py
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.qdrant_db import QdrantClient


class TestQdrantFilterConversion:
    """Tests for filter conversion methods"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    def test_convert_filter_empty(self, client):
        """Test converting empty filter"""
        result = client._convert_filter_to_qdrant_format({})
        assert result is None

    def test_convert_filter_none(self, client):
        """Test converting None filter"""
        result = client._convert_filter_to_qdrant_format(None)
        assert result is None

    def test_convert_filter_direct_value(self, client):
        """Test converting filter with direct value match"""
        filter_dict = {"tier": "S"}
        result = client._convert_filter_to_qdrant_format(filter_dict)

        assert result is not None
        assert "must" in result
        assert len(result["must"]) == 1
        assert result["must"][0]["key"] == "metadata.tier"
        assert result["must"][0]["match"]["value"] == "S"

    def test_convert_filter_in_operator(self, client):
        """Test converting filter with $in operator"""
        filter_dict = {"tier": {"$in": ["S", "A"]}}
        result = client._convert_filter_to_qdrant_format(filter_dict)

        assert result is not None
        assert "must" in result
        assert len(result["must"]) == 1
        assert result["must"][0]["key"] == "metadata.tier"
        assert result["must"][0]["match"]["any"] == ["S", "A"]

    def test_convert_filter_in_empty_list(self, client):
        """Test converting filter with empty $in list"""
        filter_dict = {"tier": {"$in": []}}
        result = client._convert_filter_to_qdrant_format(filter_dict)

        # Empty $in should not create a condition
        assert result is None or "must" not in result or len(result.get("must", [])) == 0

    def test_convert_filter_ne_operator(self, client):
        """Test converting filter with $ne operator"""
        filter_dict = {"status": {"$ne": "inactive"}}
        result = client._convert_filter_to_qdrant_format(filter_dict)

        assert result is not None
        assert "must_not" in result
        assert len(result["must_not"]) == 1
        assert result["must_not"][0]["key"] == "metadata.status"
        assert result["must_not"][0]["match"]["value"] == "inactive"

    def test_convert_filter_nin_operator(self, client):
        """Test converting filter with $nin operator"""
        filter_dict = {"status": {"$nin": ["inactive", "deleted"]}}
        result = client._convert_filter_to_qdrant_format(filter_dict)

        assert result is not None
        assert "must_not" in result
        assert len(result["must_not"]) == 2  # One for each excluded value

    def test_convert_filter_multiple_conditions(self, client):
        """Test converting filter with multiple conditions"""
        filter_dict = {
            "tier": {"$in": ["S", "A"]},
            "status": "active",
            "type": {"$ne": "test"}
        }
        result = client._convert_filter_to_qdrant_format(filter_dict)

        assert result is not None
        assert "must" in result
        assert "must_not" in result
        assert len(result["must"]) == 2  # tier $in and status direct
        assert len(result["must_not"]) == 1  # type $ne

    def test_convert_filter_complex(self, client):
        """Test converting complex filter"""
        filter_dict = {
            "tier": {"$in": ["S", "A", "B"]},
            "status": {"$ne": "deleted"},
            "category": "legal"
        }
        result = client._convert_filter_to_qdrant_format(filter_dict)

        assert result is not None
        assert "must" in result
        assert "must_not" in result


class TestQdrantClientHelpers:
    """Tests for QdrantClient helper methods"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    def test_get_headers_without_api_key(self, client):
        """Test getting headers without API key"""
        client.api_key = None
        headers = client._get_headers()

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "api-key" not in headers

    def test_get_headers_with_api_key(self, client):
        """Test getting headers with API key"""
        client.api_key = "test-api-key"
        headers = client._get_headers()

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "api-key" in headers
        assert headers["api-key"] == "test-api-key"

    def test_collection_property(self, client):
        """Test collection property"""
        result = client.collection()
        assert result == client

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager"""
        async with client as ctx:
            assert ctx == client
            # Client should be initialized
            assert client._http_client is not None or await client._get_client() is not None

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing client"""
        # Initialize client first
        await client._get_client()
        assert client._http_client is not None

        await client.close()
        assert client._http_client is None

    @pytest.mark.asyncio
    async def test_get_client_creates_new(self, client):
        """Test _get_client creates new client"""
        assert client._http_client is None

        client1 = await client._get_client()
        assert client1 is not None
        assert client._http_client is not None

        # Second call should return same client
        client2 = await client._get_client()
        assert client2 == client1




