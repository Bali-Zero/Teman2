"""
Integration Tests for Oracle Ingest Router
Tests oracle_ingest endpoints with real Qdrant database
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.oracle_ingest import router


@pytest.fixture
def test_app():
    """Create FastAPI test app with oracle_ingest router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.mark.integration
class TestOracleIngestIntegration:
    """Integration tests for oracle_ingest router"""

    @pytest.mark.asyncio
    async def test_ingest_documents_single(self, test_client, qdrant_client):
        """Test ingesting a single document"""
        response = test_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "This is a test legal document about contract law. It contains important information about legal obligations and responsibilities.",
                        "metadata": {
                            "law_id": "UU-001",
                            "pasal": "Pasal 1",
                            "category": "contract",
                            "type": "law",
                        },
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["documents_ingested"] == 1
        assert "execution_time_ms" in data

    @pytest.mark.asyncio
    async def test_ingest_documents_multiple(self, test_client, qdrant_client):
        """Test ingesting multiple documents"""
        response = test_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "First legal document about property rights and ownership.",
                        "metadata": {
                            "law_id": "UU-002",
                            "pasal": "Pasal 1",
                            "category": "property",
                        },
                    },
                    {
                        "content": "Second legal document about inheritance and succession.",
                        "metadata": {
                            "law_id": "UU-003",
                            "pasal": "Pasal 2",
                            "category": "inheritance",
                        },
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["documents_ingested"] == 2

    @pytest.mark.asyncio
    async def test_list_collections(self, test_client, qdrant_client):
        """Test listing collections"""
        # First create a collection by ingesting a document
        test_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "Test document for collection listing.",
                        "metadata": {"law_id": "TEST", "category": "test"},
                    }
                ],
            },
        )

        # Then list collections
        response = test_client.get("/api/oracle/collections")

        assert response.status_code == 200
        data = response.json()
        assert "collections" in data
        assert isinstance(data["collections"], list)
        # Should contain at least legal_intelligence collection
        collection_names = [c["name"] for c in data["collections"]]
        assert "legal_intelligence" in collection_names

    @pytest.mark.asyncio
    async def test_ingest_with_custom_collection(self, test_client, qdrant_client):
        """Test ingesting to a custom collection"""
        collection_name = "test_custom_collection"

        response = test_client.post(
            "/api/oracle/ingest",
            json={
                "collection": collection_name,
                "documents": [
                    {
                        "content": "Document for custom collection testing.",
                        "metadata": {"test": True, "collection": collection_name},
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify collection exists
        list_response = test_client.get("/api/oracle/collections")
        assert list_response.status_code == 200
        collections = list_response.json()["collections"]
        collection_names = [c["name"] for c in collections]
        assert collection_name in collection_names
