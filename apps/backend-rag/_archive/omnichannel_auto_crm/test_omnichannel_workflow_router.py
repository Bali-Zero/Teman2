import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Aggressively mock dependencies to prevent import errors"""
    # Mock backend.app.dependencies
    deps_mock = types.ModuleType("backend.app.dependencies")

    def get_database():
        pass

    def get_current_user():
        pass

    def get_database_pool():
        pass

    def get_optional_database_pool():
        pass

    def get_orchestrator():
        pass

    deps_mock.get_database = get_database
    deps_mock.get_current_user = get_current_user
    deps_mock.get_database_pool = get_database_pool
    deps_mock.get_optional_database_pool = get_optional_database_pool
    deps_mock.get_orchestrator = get_orchestrator

    monkeypatch.setitem(sys.modules, "backend.app.dependencies", deps_mock)

    # Mock other routers to avoid cascading imports
    monkeypatch.setitem(sys.modules, "backend.app.routers.agentic_rag", MagicMock())
    monkeypatch.setitem(sys.modules, "backend.app.routers.health", MagicMock())
    monkeypatch.setitem(sys.modules, "backend.app.routers.ingest", MagicMock())

    # Mock metrics
    metrics_mock = types.ModuleType("backend.app.metrics")
    metrics_mock.metrics_collector = MagicMock()
    monkeypatch.setitem(sys.modules, "backend.app.metrics", metrics_mock)


@pytest.fixture
def mock_db_pool():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Setup async context manager for pool.acquire()
    async_context = AsyncMock()
    async_context.__aenter__.return_value = mock_conn
    async_context.__aexit__.return_value = None
    mock_pool.acquire.return_value = async_context

    return mock_pool


@pytest.fixture
def test_app(mock_db_pool):
    from backend.app.routers.omnichannel_workflow import get_database, router

    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    app.dependency_overrides[get_database] = lambda: mock_db_pool

    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestOmnichannelWorkflowRouter:
    def test_get_enrichment_success(self, client, mock_db_pool):
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        # Mock conversation lookup
        mock_conn.fetchrow.side_effect = [
            {"session_id": "wa_session_628123456789", "user_id": "user123"},  # conv
            {
                "full_name": "John Doe",
                "email": "john@doe.com",
                "status": "active",
                "client_type": "individual",
                "nationality": "Italian",
                "notes": "Test",
                "tags": [],
                "last_interaction_date": None,
            },  # client
        ]

        # Mock practice lookup
        mock_conn.fetchval.return_value = 1  # client_id
        mock_conn.fetch.return_value = [
            {"status": "open", "quoted_price": 1000, "practice_name": "Visa Extension"}
        ]

        response = client.get("/api/workflow/conversations/1/enrichment")

        assert response.status_code == 200
        data = response.json()
        assert data["exists_in_crm"] is True
        assert data["profile"]["full_name"] == "John Doe"
        assert len(data["practices"]) == 1

    def test_get_enrichment_not_found(self, client, mock_db_pool):
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None  # Conversation not found

        response = client.get("/api/workflow/conversations/999/enrichment")
        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"

    def test_assign_conversation(self, client, mock_db_pool):
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        response = client.patch(
            "/api/workflow/conversations/1/assign", json={"assigned_to": "agent@nuzantara.com"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify UPDATE and INSERT were called
        assert mock_conn.execute.called

    def test_update_status(self, client, mock_db_pool):
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        response = client.patch("/api/workflow/conversations/1/status", json={"status": "closed"})

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify UPDATE was called
        mock_conn.execute.assert_called_with(
            "UPDATE conversations SET status = $1 WHERE id = $2", "closed", 1
        )

    def test_get_notes(self, client, mock_db_pool):
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = [
            {
                "id": 1,
                "content": "Note 1",
                "author_name": "Agent",
                "created_at": "2026-01-01T10:00:00",
            }
        ]

        response = client.get("/api/workflow/conversations/1/notes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Note 1"

    def test_add_note(self, client, mock_db_pool):
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        response = client.post(
            "/api/workflow/conversations/1/notes",
            json={"content": "New note", "author_id": "agent1", "author_name": "John"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify INSERT was called
        mock_conn.execute.assert_called_with(
            "INSERT INTO conversation_notes (conversation_id, author_id, author_name, content) VALUES ($1, $2, $3, $4)",
            1,
            "agent1",
            "John",
            "New note",
        )
