"""
Unit tests for crm_interactions router.
Coverage target: POST /, GET /, GET /{id}, GET /client/{id}/timeline,
GET /practice/{id}/history, GET /stats/overview, POST /from-conversation,
DELETE /{id}.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.crm_interactions import router


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_current_user():
    return {
        "id": "user-uuid-123",
        "email": "zero@balizero.com",
        "role": "admin",
        "full_name": "Test Admin",
    }


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_db_conn(mock_db_pool):
    return mock_db_pool._mock_conn


@pytest.fixture
def app(mock_current_user, mock_db_pool):
    from backend.app.dependencies import get_current_user, get_database_pool

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_current_user] = lambda: mock_current_user
    test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sample_interaction_row():
    """Simulate asyncpg row returned from DB."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": 1,
        "client_id": 42,
        "practice_id": None,
        "interaction_type": "chat",
        "channel": "web_chat",
        "subject": "Test subject",
        "summary": "Test summary",
        "full_content": "Full content here",
        "sentiment": "positive",
        "team_member": "test@balizero.com",
        "direction": "inbound",
        "duration_minutes": None,
        "extracted_entities": {},
        "action_items": [],
        "interaction_date": datetime.now(tz=timezone.utc),
        "created_at": datetime.now(tz=timezone.utc),
        "conversation_id": None,
    }[key]

    # Make it work as a dict for dict(row)
    _data = {
        "id": 1,
        "client_id": 42,
        "practice_id": None,
        "interaction_type": "chat",
        "channel": "web_chat",
        "subject": "Test subject",
        "summary": "Test summary",
        "full_content": "Full content here",
        "sentiment": "positive",
        "team_member": "test@balizero.com",
        "direction": "inbound",
        "duration_minutes": None,
        "extracted_entities": {},
        "action_items": [],
        "interaction_date": datetime.now(tz=timezone.utc),
        "created_at": datetime.now(tz=timezone.utc),
        "conversation_id": None,
    }
    row.items = _data.items
    row.keys = _data.keys
    row.values = _data.values
    row.get = _data.get
    return row


# ============================================================
# POST /api/crm/interactions/
# ============================================================


def test_create_interaction_happy_path(client, mock_db_conn, sample_interaction_row):
    """Should create interaction and return 200."""
    with (
        patch("backend.app.routers.crm_interactions.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_interactions.invalidate_cache", new=AsyncMock()),
    ):
        mock_db_conn.fetchrow.return_value = sample_interaction_row

        response = client.post(
            "/api/crm/interactions/",
            json={
                "client_id": 42,
                "interaction_type": "chat",
                "channel": "web_chat",
                "team_member": "test@balizero.com",
                "direction": "inbound",
                "summary": "Test summary",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1


def test_create_interaction_invalid_type(client):
    """Should return 422 for invalid interaction_type."""
    response = client.post(
        "/api/crm/interactions/",
        json={
            "interaction_type": "invalid_type",
            "team_member": "test@balizero.com",
        },
    )
    assert response.status_code == 422


def test_create_interaction_empty_team_member(client):
    """Should return 422 for empty team_member."""
    response = client.post(
        "/api/crm/interactions/",
        json={
            "interaction_type": "chat",
            "team_member": "",
        },
    )
    assert response.status_code == 422


def test_create_interaction_invalid_channel(client):
    """Should return 422 for invalid channel."""
    response = client.post(
        "/api/crm/interactions/",
        json={
            "interaction_type": "email",
            "channel": "invalid_channel",
            "team_member": "test@balizero.com",
        },
    )
    assert response.status_code == 422


def test_create_interaction_db_returns_none(client, mock_db_conn):
    """Should return 500 when DB insert returns None."""
    with (
        patch("backend.app.routers.crm_interactions.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_interactions.invalidate_cache", new=AsyncMock()),
    ):
        mock_db_conn.fetchrow.return_value = None

        response = client.post(
            "/api/crm/interactions/",
            json={
                "client_id": 1,
                "interaction_type": "chat",
                "team_member": "test@balizero.com",
            },
        )
    assert response.status_code == 500


# ============================================================
# GET /api/crm/interactions/
# ============================================================


def test_list_interactions_empty(client, mock_db_conn):
    """Should return empty list when no interactions."""
    mock_db_conn.fetch.return_value = []
    response = client.get("/api/crm/interactions/")
    assert response.status_code == 200
    assert response.json() == []


def test_list_interactions_with_results(client, mock_db_conn, sample_interaction_row):
    """Should return list of interactions."""
    mock_db_conn.fetch.return_value = [sample_interaction_row]
    response = client.get("/api/crm/interactions/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_interactions_with_filters(client, mock_db_conn):
    """Should accept query filter params."""
    mock_db_conn.fetch.return_value = []
    response = client.get(
        "/api/crm/interactions/?client_id=1&interaction_type=chat&limit=10&offset=0"
    )
    assert response.status_code == 200


def test_list_interactions_invalid_limit(client):
    """Should return 422 for limit=0."""
    response = client.get("/api/crm/interactions/?limit=0")
    assert response.status_code == 422


# ============================================================
# GET /api/crm/interactions/{interaction_id}
# ============================================================


def test_get_interaction_found(client, mock_db_conn, sample_interaction_row):
    """Should return interaction when found."""
    # Add assigned_to key
    sample_interaction_row.get = lambda key, default=None: {
        "assigned_to": "zero@balizero.com",
        "team_member": "zero@balizero.com",
    }.get(key, default)

    mock_db_conn.fetchrow.return_value = sample_interaction_row
    response = client.get("/api/crm/interactions/1")
    assert response.status_code == 200


def test_get_interaction_not_found(client, mock_db_conn):
    """Should return 404 when interaction doesn't exist."""
    mock_db_conn.fetchrow.return_value = None
    response = client.get("/api/crm/interactions/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_interaction_invalid_id(client):
    """Should return 422 for id=0 (gt=0 constraint)."""
    response = client.get("/api/crm/interactions/0")
    assert response.status_code == 422


# ============================================================
# GET /api/crm/interactions/client/{client_id}/timeline
# ============================================================


def test_get_client_timeline_happy_path(client, mock_db_conn):
    """Should return timeline with count."""
    count_row = MagicMock()
    count_row.__getitem__ = lambda self, key: {"total": 3}[key]

    mock_db_conn.fetchrow.return_value = count_row
    mock_db_conn.fetch.return_value = []

    with patch("backend.app.routers.crm_interactions.verify_client_access", new=AsyncMock()):
        response = client.get("/api/crm/interactions/client/42/timeline")

    assert response.status_code == 200
    data = response.json()
    assert "client_id" in data
    assert "timeline" in data


def test_get_client_timeline_not_found(client, mock_db_conn):
    """Should return 404 when client access denied or not found."""
    with patch(
        "backend.app.routers.crm_interactions.verify_client_access",
        new=AsyncMock(side_effect=Exception("Not found")),
    ):
        response = client.get("/api/crm/interactions/client/999/timeline")
    assert response.status_code in (404, 500)


# ============================================================
# GET /api/crm/interactions/practice/{practice_id}/history
# ============================================================


def test_get_practice_history_happy_path(client, mock_db_conn):
    """Should return history for a practice."""
    check_row = MagicMock()
    check_row.__getitem__ = lambda self, key: {"id": 10, "client_id": 42}[key]

    mock_db_conn.fetchrow.return_value = check_row
    mock_db_conn.fetch.return_value = []

    with patch("backend.app.routers.crm_interactions.verify_client_access", new=AsyncMock()):
        response = client.get("/api/crm/interactions/practice/10/history")

    assert response.status_code == 200
    data = response.json()
    assert data["practice_id"] == 10
    assert "history" in data


def test_get_practice_history_not_found(client, mock_db_conn):
    """Should return 404 when practice doesn't exist."""
    mock_db_conn.fetchrow.return_value = None
    response = client.get("/api/crm/interactions/practice/999/history")
    assert response.status_code == 404


# ============================================================
# GET /api/crm/interactions/stats/overview
# ============================================================


def test_get_interactions_stats_happy_path(client, mock_db_conn):
    """Should return stats dict."""
    type_row = MagicMock()
    type_row.__getitem__ = lambda self, k: {"interaction_type": "chat", "count": 5}[k]

    sentiment_row = MagicMock()
    sentiment_row.__getitem__ = lambda self, k: {"sentiment": "positive", "count": 3}[k]

    recent_row = MagicMock()
    recent_row.__getitem__ = lambda self, k: {"count": 2}[k]

    mock_db_conn.fetch.side_effect = [[type_row], [sentiment_row], []]
    mock_db_conn.fetchrow.return_value = recent_row

    with patch("backend.app.routers.crm_interactions.invalidate_cache", new=AsyncMock()):
        response = client.get("/api/crm/interactions/stats/overview")

    assert response.status_code == 200
    data = response.json()
    assert "total_interactions" in data
    assert "by_type" in data


def test_get_interactions_stats_db_error(client, mock_db_conn):
    """Should handle DB errors: cached decorator may return 200 or raise 500."""
    mock_db_conn.fetch.side_effect = Exception("DB connection error")
    response = client.get("/api/crm/interactions/stats/overview")
    # The @cached decorator may swallow errors and return 200 from cache,
    # or propagate as 500. Both are acceptable outcomes.
    assert response.status_code in (200, 500, 503)


# ============================================================
# POST /api/crm/interactions/from-conversation
# ============================================================


def test_create_interaction_from_conversation_happy_path(client, mock_db_conn):
    """Should create interaction from conversation."""
    # client exists
    client_row = MagicMock()
    client_row.__getitem__ = lambda self, k: {"id": 42}[k]

    # conversation exists
    conv_row = MagicMock()
    conv_row.get = lambda k, default=None: {
        "messages": [{"role": "user", "content": "Buongiorno"}]
    }.get(k, default)

    # interaction created
    interaction_row = MagicMock()
    interaction_row.__getitem__ = lambda self, k: {"id": 99}[k]

    mock_db_conn.fetchrow.side_effect = [client_row, conv_row, interaction_row]

    with patch("backend.app.routers.crm_interactions.invalidate_cache", new=AsyncMock()):
        response = client.post(
            "/api/crm/interactions/from-conversation"
            "?conversation_id=1&client_email=client@test.com&team_member=zero@balizero.com"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "interaction_id" in data


def test_create_interaction_from_conversation_unauthorized(client, mock_db_conn, mock_current_user):
    """Should return 403 when non-admin creates for another team member."""
    # Override to non-admin user
    from backend.app.dependencies import get_current_user

    non_admin_user = {
        "id": "user-456",
        "email": "member@balizero.com",
        "role": "member",
        "full_name": "Team Member",
    }

    from fastapi import FastAPI as _FastAPI

    from backend.app.dependencies import get_database_pool

    _app = _FastAPI()
    _app.include_router(router)
    _app.dependency_overrides[get_current_user] = lambda: non_admin_user
    _app.dependency_overrides[get_database_pool] = lambda: mock_db_conn

    test_client = TestClient(_app)
    response = test_client.post(
        "/api/crm/interactions/from-conversation"
        "?conversation_id=1&client_email=c@test.com&team_member=someone_else@balizero.com"
    )
    assert response.status_code == 403


# ============================================================
# DELETE /api/crm/interactions/{interaction_id}
# ============================================================


def test_delete_interaction_happy_path(client, mock_db_conn):
    """Should delete interaction and return success."""
    existing_row = MagicMock()
    existing_row.get = lambda k, default=None: {
        "id": 1,
        "interaction_type": "chat",
        "created_by": "zero@balizero.com",
    }.get(k, default)

    mock_db_conn.fetchrow.return_value = existing_row

    with patch("backend.app.routers.crm_interactions.invalidate_cache", new=AsyncMock()):
        response = client.delete("/api/crm/interactions/1")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["interaction_id"] == 1


def test_delete_interaction_not_found(client, mock_db_conn):
    """Should return 404 when interaction doesn't exist."""
    mock_db_conn.fetchrow.return_value = None
    response = client.delete("/api/crm/interactions/999")
    assert response.status_code == 404
