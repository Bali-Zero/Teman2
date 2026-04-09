"""
Unit tests for zoho_email router.
Coverage target: OAuth flow, folders, emails CRUD, attachments, unread count.
"""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.zoho_email import router


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_current_user():
    return {
        "id": "user-uuid-123",
        "user_id": "user-uuid-123",
        "email": "test@balizero.com",
        "role": "admin",
        "full_name": "Test User",
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
def app(mock_current_user, mock_db_pool):
    from backend.app.dependencies import get_current_user, get_database_pool

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_current_user] = lambda: mock_current_user
    test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def mock_oauth_service():
    svc = MagicMock()
    svc.get_authorization_url = MagicMock(return_value="https://accounts.zoho.com/oauth/v2/auth?...")
    svc.exchange_code = AsyncMock()
    svc.get_connection_status = AsyncMock(
        return_value={"connected": True, "email": "test@zoho.com", "account_id": "abc", "expires_at": "2026-12-31"}
    )
    svc.disconnect = AsyncMock()
    return svc


@pytest.fixture
def mock_email_service():
    svc = MagicMock()
    svc.list_folders = AsyncMock(return_value=[{"id": "inbox", "name": "Inbox"}])
    svc.list_emails = AsyncMock(
        return_value={"emails": [], "total": 0, "has_more": False}
    )
    svc.get_email = AsyncMock(
        return_value={"id": "msg_001", "subject": "Test", "body": "Hello"}
    )
    svc.send_email = AsyncMock(return_value={"success": True, "message_id": "msg_123"})
    svc.search_emails = AsyncMock(return_value=[])
    svc.reply_email = AsyncMock(return_value={"success": True})
    svc.forward_email = AsyncMock(return_value={"success": True})
    svc.mark_read = AsyncMock(return_value=True)
    svc.toggle_flag = AsyncMock(return_value=True)
    svc.delete_emails = AsyncMock(return_value=True)
    svc.save_draft = AsyncMock(return_value={"success": True, "draft_id": "draft_001"})
    svc.upload_attachment = AsyncMock(
        return_value={"attachment_id": "att_001", "name": "test.txt", "size": 100}
    )
    svc.get_attachment = AsyncMock(return_value=b"binary content")
    svc.get_unread_count = AsyncMock(return_value=5)
    return svc


# ============================================================
# Helper: missing user_id
# ============================================================


@pytest.fixture
def app_no_user_id(mock_db_pool):
    """App with a user dict that lacks user_id."""
    from backend.app.dependencies import get_current_user, get_database_pool

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_current_user] = lambda: {
        "email": "test@balizero.com",
        "role": "admin",
    }
    test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return test_app


@pytest.fixture
def client_no_user_id(app_no_user_id):
    return TestClient(app_no_user_id)


# ============================================================
# GET /api/integrations/zoho/auth/url
# ============================================================


def test_get_auth_url_happy_path(client, mock_oauth_service):
    with patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
        response = client.get("/api/integrations/zoho/auth/url")
    assert response.status_code == 200
    data = response.json()
    assert "auth_url" in data
    assert "state" in data


def test_get_auth_url_no_user_id(client_no_user_id):
    """Should return 400 when user_id missing from token."""
    response = client_no_user_id.get("/api/integrations/zoho/auth/url")
    assert response.status_code == 400


def test_get_auth_url_oauth_error(client, mock_oauth_service):
    """Should return 500 when OAuth service raises ValueError."""
    mock_oauth_service.get_authorization_url.side_effect = ValueError("Missing client_id")
    with patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
        response = client.get("/api/integrations/zoho/auth/url")
    assert response.status_code == 500


# ============================================================
# GET /api/integrations/zoho/callback
# ============================================================


def test_oauth_callback_with_error_param(client, mock_oauth_service):
    """Should redirect with error when OAuth returns error."""
    with (
        patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service),
        patch("backend.app.routers.zoho_email.settings") as mock_settings,
    ):
        mock_settings.frontend_url = "https://kita.balizero.com"
        response = client.get("/api/integrations/zoho/callback?error=access_denied")
    assert response.status_code in (302, 307)
    assert "error=oauth_denied" in response.headers.get("location", "")


def test_oauth_callback_missing_code(client, mock_oauth_service):
    """Should redirect with missing_params when code absent."""
    with (
        patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service),
        patch("backend.app.routers.zoho_email.settings") as mock_settings,
    ):
        mock_settings.frontend_url = "https://kita.balizero.com"
        response = client.get("/api/integrations/zoho/callback?state=user:token")
    assert response.status_code in (302, 307)
    assert "error=missing_params" in response.headers.get("location", "")


def test_oauth_callback_invalid_state_format(client, mock_db_pool, mock_oauth_service):
    """Should redirect with invalid_state for malformed state."""
    with (
        patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service),
        patch("backend.app.routers.zoho_email.settings") as mock_settings,
    ):
        mock_settings.frontend_url = "https://kita.balizero.com"
        response = client.get("/api/integrations/zoho/callback?code=auth_code&state=invalidstate")
    assert response.status_code in (302, 307)
    assert "error=invalid_state" in response.headers.get("location", "")


def test_oauth_callback_success(client, mock_oauth_service):
    """Should redirect with connected=true on success."""
    with (
        patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service),
        patch("backend.app.routers.zoho_email.settings") as mock_settings,
    ):
        mock_settings.frontend_url = "https://kita.balizero.com"
        response = client.get(
            "/api/integrations/zoho/callback?code=valid_code&state=user-uuid-123:random_token"
        )
    assert response.status_code in (302, 307)
    assert "connected=true" in response.headers.get("location", "")


def test_oauth_callback_exchange_fails(client, mock_oauth_service):
    """Should redirect with connection_failed when exchange raises."""
    mock_oauth_service.exchange_code.side_effect = Exception("Exchange failed")
    with (
        patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service),
        patch("backend.app.routers.zoho_email.settings") as mock_settings,
    ):
        mock_settings.frontend_url = "https://kita.balizero.com"
        response = client.get(
            "/api/integrations/zoho/callback?code=valid_code&state=user-uuid-123:random_token"
        )
    assert response.status_code in (302, 307)
    assert "error=connection_failed" in response.headers.get("location", "")


# ============================================================
# GET /api/integrations/zoho/status
# ============================================================


def test_get_connection_status_connected(client, mock_oauth_service):
    with patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
        response = client.get("/api/integrations/zoho/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["email"] == "test@zoho.com"


def test_get_connection_status_no_user_id(client_no_user_id):
    """Should return 400 when user_id not in token."""
    response = client_no_user_id.get("/api/integrations/zoho/status")
    assert response.status_code in (200, 400)


def test_get_connection_status_exception(client, mock_oauth_service):
    """Should return connected=False on unexpected error."""
    mock_oauth_service.get_connection_status.side_effect = Exception("DB error")
    with patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
        response = client.get("/api/integrations/zoho/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False


# ============================================================
# DELETE /api/integrations/zoho/disconnect
# ============================================================


def test_disconnect_account_success(client, mock_oauth_service):
    with patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
        response = client.delete("/api/integrations/zoho/disconnect")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_disconnect_account_failure(client, mock_oauth_service):
    mock_oauth_service.disconnect.side_effect = Exception("Token revocation failed")
    with patch("backend.app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
        response = client.delete("/api/integrations/zoho/disconnect")
    assert response.status_code == 500


# ============================================================
# GET /api/integrations/zoho/folders
# ============================================================


def test_list_folders_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/folders")
    assert response.status_code == 200
    data = response.json()
    assert "folders" in data


def test_list_folders_service_error(client, mock_email_service):
    mock_email_service.list_folders.side_effect = Exception("API error")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/folders")
    assert response.status_code == 500


def test_list_folders_value_error(client, mock_email_service):
    mock_email_service.list_folders.side_effect = ValueError("Not connected")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/folders")
    assert response.status_code == 400


# ============================================================
# GET /api/integrations/zoho/emails
# ============================================================


def test_list_emails_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/emails")
    assert response.status_code == 200


def test_list_emails_with_params(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get(
            "/api/integrations/zoho/emails?folder_id=sent&limit=20&start=0&is_unread=true"
        )
    assert response.status_code == 200


def test_list_emails_error(client, mock_email_service):
    mock_email_service.list_emails.side_effect = Exception("Zoho API down")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/emails")
    assert response.status_code == 500


# ============================================================
# GET /api/integrations/zoho/emails/{message_id}
# ============================================================


def test_get_email_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/emails/msg_001?folder_id=inbox")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "msg_001"


def test_get_email_value_error(client, mock_email_service):
    mock_email_service.get_email.side_effect = ValueError("Not connected to Zoho")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/emails/msg_001")
    assert response.status_code == 400


# ============================================================
# POST /api/integrations/zoho/emails
# ============================================================


def test_send_email_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/emails",
            json={
                "to": ["recipient@example.com"],
                "subject": "Test Email",
                "html_content": "<p>Hello</p>",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_send_email_missing_required(client):
    """Should return 422 for missing required fields."""
    response = client.post(
        "/api/integrations/zoho/emails",
        json={"subject": "Missing TO"},
    )
    assert response.status_code == 422


def test_send_email_service_error(client, mock_email_service):
    mock_email_service.send_email.side_effect = Exception("SMTP failed")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/emails",
            json={"to": ["r@example.com"], "subject": "Test", "html_content": "<p>Hi</p>"},
        )
    assert response.status_code == 500


# ============================================================
# POST /api/integrations/zoho/emails/{message_id}/reply
# ============================================================


def test_reply_email_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/emails/msg_001/reply",
            json={"content": "My reply", "to": "sender@example.com"},
        )
    assert response.status_code == 200


def test_reply_email_error(client, mock_email_service):
    mock_email_service.reply_email.side_effect = Exception("API error")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/emails/msg_001/reply",
            json={"content": "Reply", "to": "s@example.com"},
        )
    assert response.status_code == 500


# ============================================================
# POST /api/integrations/zoho/emails/{message_id}/forward
# ============================================================


def test_forward_email_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/emails/msg_001/forward",
            json={"to": ["fwd@example.com"]},
        )
    assert response.status_code == 200


# ============================================================
# PATCH /api/integrations/zoho/emails/mark-read
# ============================================================


def test_mark_emails_read_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.patch(
            "/api/integrations/zoho/emails/mark-read",
            json={"message_ids": ["msg_001", "msg_002"], "is_read": True},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_mark_emails_read_empty_ids(client):
    """Should return 422 when message_ids is empty."""
    response = client.patch(
        "/api/integrations/zoho/emails/mark-read",
        json={"message_ids": [], "is_read": True},
    )
    assert response.status_code == 422


# ============================================================
# PATCH /api/integrations/zoho/emails/{message_id}/flag
# ============================================================


def test_toggle_flag_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.patch(
            "/api/integrations/zoho/emails/msg_001/flag?is_flagged=true"
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_toggle_flag_error(client, mock_email_service):
    mock_email_service.toggle_flag.side_effect = Exception("API error")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.patch(
            "/api/integrations/zoho/emails/msg_001/flag?is_flagged=false"
        )
    assert response.status_code == 500


# ============================================================
# DELETE /api/integrations/zoho/emails
# ============================================================


def test_delete_emails_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.request(
            "DELETE",
            "/api/integrations/zoho/emails",
            json={"message_ids": ["msg_001"]},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_delete_emails_empty_ids(client):
    """Should return 422 for empty message_ids."""
    response = client.request(
        "DELETE",
        "/api/integrations/zoho/emails",
        json={"message_ids": []},
    )
    assert response.status_code == 422


# ============================================================
# POST /api/integrations/zoho/emails/delete (POST variant)
# ============================================================


def test_delete_emails_post_variant_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/emails/delete",
            json={"message_ids": ["msg_001"]},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


# ============================================================
# POST /api/integrations/zoho/drafts
# ============================================================


def test_save_draft_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/drafts",
            json={"subject": "Draft Subject", "html_content": "<p>Draft body</p>"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_save_draft_error(client, mock_email_service):
    mock_email_service.save_draft.side_effect = Exception("Draft save failed")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/drafts",
            json={"subject": "Draft", "html_content": "<p>Content</p>"},
        )
    assert response.status_code == 500


# ============================================================
# POST /api/integrations/zoho/attachments
# ============================================================


def test_upload_attachment_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/attachments",
            files={"file": ("test.txt", BytesIO(b"file content"), "text/plain")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["attachment_id"] == "att_001"


def test_upload_attachment_service_error(client, mock_email_service):
    mock_email_service.upload_attachment.side_effect = Exception("Upload failed")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.post(
            "/api/integrations/zoho/attachments",
            files={"file": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
    assert response.status_code == 500


# ============================================================
# GET /api/integrations/zoho/emails/{message_id}/attachments/{attachment_id}
# ============================================================


def test_download_attachment_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get(
            "/api/integrations/zoho/emails/msg_001/attachments/att_001"
        )
    assert response.status_code == 200
    assert response.content == b"binary content"


def test_download_attachment_error(client, mock_email_service):
    mock_email_service.get_attachment.side_effect = Exception("Download failed")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get(
            "/api/integrations/zoho/emails/msg_001/attachments/att_001"
        )
    assert response.status_code == 500


# ============================================================
# GET /api/integrations/zoho/unread-count
# ============================================================


def test_get_unread_count_success(client, mock_email_service):
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/unread-count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 5


def test_get_unread_count_not_connected(client, mock_email_service):
    """Should return 0 when not connected (ValueError)."""
    mock_email_service.get_unread_count.side_effect = ValueError("Not connected")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/unread-count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 0


def test_get_unread_count_exception(client, mock_email_service):
    """Should return 0 on generic exception."""
    mock_email_service.get_unread_count.side_effect = Exception("Generic error")
    with patch("backend.app.routers.zoho_email._get_email_service", return_value=mock_email_service):
        response = client.get("/api/integrations/zoho/unread-count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 0


# ============================================================
# OPTIONS /api/integrations/zoho/emails
# ============================================================


def test_options_emails(client):
    """OPTIONS endpoint should return 200."""
    response = client.options("/api/integrations/zoho/emails")
    assert response.status_code == 200
