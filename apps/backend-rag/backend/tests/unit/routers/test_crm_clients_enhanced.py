"""
Enhanced Tests for CRM Clients Router
Covers Avatar, Sentiment Aura, and Advanced Queries
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_database_pool


# Re-use fixtures logic but specialized for enhanced features
@pytest.fixture
def mock_db_pool():
    from contextlib import asynccontextmanager

    pool = AsyncMock()
    conn = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


@pytest.fixture
def test_app(mock_db_pool):
    from fastapi import FastAPI

    from app.routers import crm_clients

    app = FastAPI()
    app.include_router(crm_clients.router)
    pool, conn = mock_db_pool
    app.dependency_overrides[get_database_pool] = lambda: pool
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


@pytest.fixture
def enhanced_client_data():
    return {
        "id": 1,
        "uuid": "test-uuid-123",
        "full_name": "Adit Lead",
        "email": "adit@example.com",
        "phone": "+62812345678",
        "status": "lead",
        "client_type": "individual",
        "avatar_url": "/images/team/adit.png",
        "last_sentiment": "positive",
        "last_interaction_summary": "Discussed KITAS renewal",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "tags": [],
        "whatsapp": None,
        "nationality": "Indonesia",
        "assigned_to": None,
        "first_contact_date": None,
        "last_interaction_date": None,
    }


def _create_mock_row(data):
    mock_row = MagicMock()
    for key, value in data.items():
        setattr(mock_row, key, value)
    mock_row.__getitem__ = lambda self, key: data[key]
    mock_row.get = lambda key, default=None: data.get(key, default)
    mock_row.keys = lambda: data.keys()
    # Mock dict conversion
    mock_row._asdict = lambda: data
    # Make it iterable for dict(row)
    mock_row.__iter__ = lambda: iter(data.keys())
    return mock_row


class TestEnhancedFeatures:
    def test_create_client_with_avatar(self, client, mock_db_pool, enhanced_client_data):
        """Test creating a client with avatar_url"""
        pool, conn = mock_db_pool

        # Mock DB response
        mock_row = _create_mock_row(enhanced_client_data)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        response = client.post(
            "/api/crm/clients/?created_by=admin@balizero.com",
            json={
                "full_name": "Adit Lead",
                "email": "adit@example.com",
                "phone": "+62812345678",
                "avatar_url": "/images/team/adit.png",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["avatar_url"] == "/images/team/adit.png"
        assert data["full_name"] == "Adit Lead"

    def test_list_clients_with_sentiment(self, client, mock_db_pool, enhanced_client_data):
        """Test listing clients returns sentiment and summary from lateral join"""
        pool, conn = mock_db_pool

        # Mock DB response list
        mock_row = _create_mock_row(enhanced_client_data)
        conn.fetch = AsyncMock(return_value=[mock_row])

        response = client.get("/api/crm/clients/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        client_obj = data[0]

        # Verify Sentiment Aura fields
        assert client_obj["last_sentiment"] == "positive"
        assert client_obj["last_interaction_summary"] == "Discussed KITAS renewal"
        assert client_obj["avatar_url"] == "/images/team/adit.png"

    def test_update_client_status_kanban(self, client, mock_db_pool, enhanced_client_data):
        """Test updating status (Drag & Drop scenario)"""
        pool, conn = mock_db_pool

        # Prepare updated data
        updated_data = enhanced_client_data.copy()
        updated_data["status"] = "active"

        mock_row = _create_mock_row(updated_data)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@balizero.com", json={"status": "active"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

        # Verify DB call contained status update
        args, _ = conn.fetchrow.call_args
        query = args[0]
        assert "UPDATE clients" in query
        assert "status" in query

    def test_update_client_avatar(self, client, mock_db_pool, enhanced_client_data):
        """Test updating just the avatar"""
        pool, conn = mock_db_pool

        updated_data = enhanced_client_data.copy()
        updated_data["avatar_url"] = "/new/avatar.png"

        mock_row = _create_mock_row(updated_data)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@balizero.com",
            json={"avatar_url": "/new/avatar.png"},
        )

        assert response.status_code == 200
        assert response.json()["avatar_url"] == "/new/avatar.png"

    def test_list_clients_query_structure(self, client, mock_db_pool):
        """Verify the complex SQL query structure is constructed correctly"""
        pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        client.get("/api/crm/clients/?status=active")

        # Inspect the SQL query passed to fetch
        args, _ = conn.fetch.call_args
        query = args[0]

        # Check for Critical Strategic Elements
        assert "LEFT JOIN LATERAL" in query
        assert "sentiment" in query
        assert "summary" in query
        assert "interactions" in query
        assert "ORDER BY interaction_date DESC" in query
