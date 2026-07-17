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
        patch("backend.app.routers.intel.settings") as mock_settings,
    ):
        mock_actions.labels.return_value = MagicMock()
        mock_bulk_ops.labels.return_value = MagicMock()
        mock_bulk_items.labels.return_value = MagicMock()
        mock_approved.labels.return_value = MagicMock()
        mock_rejected.labels.return_value = MagicMock()
        # bulk-approve/reject are admin-gated (Case OS R3). intel._require_intel_admin
        # checks the caller email against settings.admin_emails_set; the test env
        # leaves that set empty, so seed it with the admin identity used below.
        mock_settings.admin_emails_set = frozenset({"zero@balizero.com"})

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

    # bulk-approve is admin-gated (Case OS R3). intel._require_intel_admin
    # checks the caller email against settings.admin_emails_set (NOT role),
    # so supply an allow-listed admin email.
    from backend.app.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {"email": "zero@balizero.com"}

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
            "news": [],
            "visa": [],
            "total": 0,
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


# ── get_pending_queue self-healing (stale-claim reaper + failed re-pick) ───
#
# Regression coverage for the queue-necrosis fix: `get_pending_queue` now runs
# 3 UPDATEs before the claim SELECT — (1) reaper for 'processing' rows stuck
# >2h, (2) re-pick for 'failed' rows with attempts<5, (3) the pre-existing
# dead-letter sweep. These tests assert the SQL text of each UPDATE the mocked
# connection receives, since the endpoint is exercised against a mocked
# asyncpg pool (no real DB in this test module — see `client` fixture above).


def _client_with_auth(mock_services, mock_conn=None):
    """Build a TestClient wired for the X-API-Key-gated poller endpoints.

    Unlike `client` (which overrides get_current_user for admin endpoints),
    get_pending_queue/done/failed/step-done authenticate via the
    intel_scraper_api_key header checked inside the handler body — so the
    mocked `settings` object needs that attribute set.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.routers.intel import router

    app = FastAPI()
    app.include_router(router)

    from backend.app.dependencies import get_database_pool

    conn = mock_conn if mock_conn is not None else AsyncMock()
    if mock_conn is None:
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
    mock_pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = ctx
    app.dependency_overrides[get_database_pool] = lambda: mock_pool

    return TestClient(app), conn


class TestGetPendingQueueSelfHealing:
    def test_reaper_and_failed_repick_run_before_claim(self, mock_services):
        """All 3 UPDATEs fire, in order: reaper, failed re-pick, dead-letter sweep."""
        # mock_services already patches backend.app.routers.intel.settings —
        # set the attribute the pending-queue handler checks on that same mock.
        from backend.app.routers import intel as intel_router_module

        intel_router_module.settings.intel_scraper_api_key = "test-key"
        test_client, conn = _client_with_auth(mock_services)

        response = test_client.get(
            "/api/intel/post-publish-queue/pending",
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 200
        # 3 execute() calls (reaper, failed-repick, dead-letter) + 1 fetch() (claim)
        assert conn.execute.await_count == 3
        executed_sql = [call.args[0] for call in conn.execute.await_args_list]

        reaper_sql = executed_sql[0]
        assert "status = 'pending'" in reaper_sql
        assert "status = 'processing'" in reaper_sql
        assert "started_at < NOW() - INTERVAL '2 hours'" in reaper_sql

        repick_sql = executed_sql[1]
        assert "status = 'pending'" in repick_sql
        assert "status = 'failed'" in repick_sql
        assert "attempts < 5" in repick_sql

        dead_letter_sql = executed_sql[2]
        assert "status = 'dead'" in dead_letter_sql
        assert "status = 'pending'" in dead_letter_sql
        assert "attempts >= 5" in dead_letter_sql

        # Claim SELECT still runs last, unchanged
        claim_sql = conn.fetch.await_args_list[0].args[0]
        assert "status = 'processing'" in claim_sql
        assert "attempts = attempts + 1" in claim_sql

    def test_unauthorized_without_api_key(self, mock_services):
        from backend.app.routers import intel as intel_router_module

        intel_router_module.settings.intel_scraper_api_key = "test-key"
        test_client, _conn = _client_with_auth(mock_services)
        response = test_client.get("/api/intel/post-publish-queue/pending")
        assert response.status_code == 401


# ── mark_step_done ──────────────────────────────────────────────────────────
#
# Regression coverage for the "could not determine data type of parameter $2"
# 500 (Fly prod log, reproduced live): `jsonb_build_object($2, true)` gives
# asyncpg/Postgres nothing to infer $2's type from in that position. Fix casts
# it explicitly: `jsonb_build_object($2::text, true)`. These tests pin the
# cast in the executed SQL text (mocked connection, no real DB — see
# `_client_with_auth` above) and confirm the endpoint returns 200/401 as
# expected.


class TestMarkStepDone:
    def test_step_done_casts_param_and_returns_200(self, mock_services):
        from backend.app.routers import intel as intel_router_module

        intel_router_module.settings.intel_scraper_api_key = "test-key"
        test_client, conn = _client_with_auth(mock_services)

        response = test_client.post(
            "/api/intel/post-publish-queue/step-done",
            headers={"X-API-Key": "test-key"},
            json={"slug": "test-article", "step": "hero_image"},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True, "slug": "test-article", "step": "hero_image"}

        conn.execute.assert_awaited_once()
        executed_sql = conn.execute.await_args_list[0].args[0]
        assert "jsonb_build_object($2::text, true)" in executed_sql

    def test_unauthorized_without_api_key(self, mock_services):
        from backend.app.routers import intel as intel_router_module

        intel_router_module.settings.intel_scraper_api_key = "test-key"
        test_client, _conn = _client_with_auth(mock_services)

        response = test_client.post(
            "/api/intel/post-publish-queue/step-done",
            json={"slug": "test-article", "step": "hero_image"},
        )
        assert response.status_code == 401
