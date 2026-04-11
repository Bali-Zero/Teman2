"""Tests for backend.app.routers.intel"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_services():
    """Mock all intel services before importing the router."""
    with (
        patch("backend.app.routers.intel.staging_service") as mock_staging,
        patch("backend.app.routers.intel.approval_service") as mock_approval,
        patch("backend.app.routers.intel.analytics_service") as mock_analytics,
        patch("backend.app.routers.intel.classification_service") as mock_classification,
        patch("backend.app.routers.intel.intel_user_actions_total") as mock_actions,
        patch("backend.app.routers.intel.intel_bulk_operations_total") as mock_bulk_ops,
        patch("backend.app.routers.intel.intel_bulk_operation_items") as mock_bulk_items,
        patch("backend.app.routers.intel.intel_items_approved") as mock_approved,
        patch("backend.app.routers.intel.intel_items_rejected") as mock_rejected,
    ):
        mock_actions.labels.return_value = MagicMock()
        mock_bulk_ops.labels.return_value = MagicMock()
        mock_bulk_items.labels.return_value = MagicMock()
        mock_approved.labels.return_value = MagicMock()
        mock_rejected.labels.return_value = MagicMock()

        yield {
            "staging": mock_staging,
            "approval": mock_approval,
            "analytics": mock_analytics,
            "classification": mock_classification,
        }


@pytest.fixture
def client(mock_services):
    from backend.app.routers.intel import router

    app = FastAPI()
    app.include_router(router)

    # Override auth dependency
    from backend.app.utils.internal_api_auth import verify_internal_api_key
    app.dependency_overrides[verify_internal_api_key] = lambda: True

    # Override DB pool with proper async context manager
    from backend.app.dependencies import get_database_pool
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = ctx
    app.dependency_overrides[get_database_pool] = lambda: mock_pool

    return TestClient(app)


# ── list_pending_items ──────────────────────────────────────────────────────


class TestListPendingItems:
    def test_list_all(self, client, mock_services):
        mock_services["staging"].list_pending_items.return_value = {
            "news": [], "visa": [], "total": 0,
        }
        response = client.get("/api/intel/staging/pending")
        assert response.status_code == 200

    def test_list_with_filter(self, client, mock_services):
        mock_services["staging"].list_pending_items.return_value = {"news": [], "total": 0}
        response = client.get("/api/intel/staging/pending?type=news&filter_type=high")
        assert response.status_code == 200


# ── preview_staging_item ────────────────────────────────────────────────────


class TestPreviewStagingItem:
    def test_preview_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {
            "title": "Test Article",
            "content": "Content here",
        }
        response = client.get("/api/intel/staging/preview/news/item-123")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Article"

    def test_preview_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None
        response = client.get("/api/intel/staging/preview/news/missing")
        assert response.status_code == 404


# ── bulk_approve_items ──────────────────────────────────────────────────────


class TestBulkApproveItems:
    def test_bulk_approve_success(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["staging"].archive_item.return_value = "/path/to/archive"

        response = client.post(
            "/api/intel/staging/bulk-approve/news",
            json=["item1", "item2"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == 2

    def test_bulk_approve_item_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None

        response = client.post(
            "/api/intel/staging/bulk-approve/news",
            json=["missing1"],
        )
        data = response.json()
        assert data["failed"] == 1


# ── bulk_reject_items ───────────────────────────────────────────────────────


class TestBulkRejectItems:
    def test_bulk_reject_success(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["staging"].archive_item.return_value = "/path"

        response = client.post(
            "/api/intel/staging/bulk-reject/visa",
            json=["item1"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == 1

    def test_bulk_reject_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None

        response = client.post(
            "/api/intel/staging/bulk-reject/visa",
            json=["missing"],
        )
        data = response.json()
        assert data["failed"] == 1


# ── approve_staging_item ────────────────────────────────────────────────────


class TestApproveStagingItem:
    def test_approve_success(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["approval"].send_approval_notification = AsyncMock(return_value=True)

        response = client.post("/api/intel/staging/approve/news/item1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_approve_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None

        response = client.post("/api/intel/staging/approve/news/missing")
        assert response.status_code == 404

    def test_approve_notification_failed(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["approval"].send_approval_notification = AsyncMock(return_value=False)

        response = client.post("/api/intel/staging/approve/news/item1")
        assert response.status_code == 500


# ── edit_staging_item ───────────────────────────────────────────────────────


class TestEditStagingItem:
    def test_edit_success(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {
            "title": "Old Title",
            "content": "Old Content",
            "category": "news",
        }

        response = client.put(
            "/api/intel/staging/news/item1",
            json={"title": "New Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "title" in data["updated_fields"]

    def test_edit_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None

        response = client.put(
            "/api/intel/staging/news/missing",
            json={"title": "X"},
        )
        assert response.status_code == 404


# ── upload_cover_image ──────────────────────────────────────────────────────


class TestUploadCoverImage:
    def test_upload_success(self, client, mock_services, tmp_path):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["staging"].get_staging_dir.return_value = tmp_path
        mock_services["staging"].save_staging_item = MagicMock()

        img_b64 = base64.b64encode(b"fake_image_data").decode()
        response = client.post(
            "/api/intel/staging/news/item1/cover",
            json={"cover_image_base64": img_b64},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_upload_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None

        response = client.post(
            "/api/intel/staging/news/missing/cover",
            json={"cover_image_base64": "aW1h"},
        )
        assert response.status_code == 404

    def test_upload_invalid_base64(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}

        response = client.post(
            "/api/intel/staging/news/item1/cover",
            json={"cover_image_base64": "!!!not_base64!!!"},
        )
        assert response.status_code == 400


# ── reject_staging_item ─────────────────────────────────────────────────────


class TestRejectStagingItem:
    def test_reject_success(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["staging"].archive_item.return_value = "/archive/path"

        response = client.post("/api/intel/staging/reject/news/item1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_reject_not_found(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = None

        response = client.post("/api/intel/staging/reject/news/missing")
        assert response.status_code == 404

    def test_reject_archive_error(self, client, mock_services):
        mock_services["staging"].load_staging_item.return_value = {"title": "Test"}
        mock_services["staging"].archive_item.side_effect = Exception("disk full")

        response = client.post("/api/intel/staging/reject/news/item1")
        assert response.status_code == 500


# ── post-publish queue endpoints ────────────────────────────────────────────


class TestPostPublishQueue:
    def test_enqueue(self, client):
        response = client.post(
            "/api/intel/post-publish-queue",
            json={"slug": "test-article", "category": "business"},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_enqueue_no_slug(self, client):
        response = client.post(
            "/api/intel/post-publish-queue",
            json={"category": "business"},
        )
        assert response.status_code == 400
