"""
Unit tests for the legal_ingest router's /ingest-full idempotency + retry logic.

Live observation (2026-09-10 19:00-19:07Z): PP 71/2019 and Permenkominfo 5/2020
failed on first attempt, and every later POST for the same (tipo, nomor, anno)
returned "Job gia in corso." forever — the router only treated status=='complete'
as already_exists, so a failed job could never be retried without a DB edit.
These tests cover the fix: failed/error existing jobs get reset and retried.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.legal_ingest import router
from backend.app.utils.internal_api_auth import verify_internal_api_key


async def _mock_verify_internal_api_key():
    return {"role": "test"}


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[verify_internal_api_key] = _mock_verify_internal_api_key
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _payload(url: str = "https://peraturan.go.id/files/bn1376-2020.pdf") -> dict:
    return {"url": url, "tipo": "PMK", "nomor": "5", "anno": "2020"}


def _mock_conn(existing_row):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=existing_row)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.close = AsyncMock()
    return conn


class TestIngestFullRetry:
    def test_failed_job_is_reset_and_retried(self, client):
        conn = _mock_conn({"id": "j1", "status": "failed"})

        with patch(
            "backend.app.routers.legal_ingest.asyncpg.connect",
            AsyncMock(return_value=conn),
        ):
            response = client.post("/api/legal/ingest-full", json=_payload())

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "j1"
        assert data["status"] == "pending"
        assert data["message"] == "Job precedente fallito: riavviato."

        conn.execute.assert_called_once()
        query, *params = conn.execute.call_args[0]
        assert "UPDATE legal_ingest_jobs" in query
        assert "status = 'pending'" in query
        assert "error = NULL" in query
        assert params[0] == "j1"

    def test_reset_query_guards_status_and_sets_immediate_visibility(self, client):
        """C1/C2 guilt test: the status guard stops a worker's concurrent claim
        from being clobbered by this UPDATE; visibility_at=NOW() is what makes
        the retry immediate instead of sleeping up to VISIBILITY_TIMEOUT (10 min).
        Removing either clause from the source must turn this red."""
        conn = _mock_conn({"id": "j6", "status": "failed"})

        with patch(
            "backend.app.routers.legal_ingest.asyncpg.connect",
            AsyncMock(return_value=conn),
        ):
            client.post("/api/legal/ingest-full", json=_payload())

        normalized = " ".join(conn.execute.call_args[0][0].split())
        assert "WHERE id = $1 AND status IN ('failed', 'error')" in normalized
        assert "visibility_at = NOW()" in normalized

    def test_error_status_job_is_also_reset(self, client):
        """The 'error' status alias is treated the same as 'failed'."""
        conn = _mock_conn({"id": "j2", "status": "error"})

        with patch(
            "backend.app.routers.legal_ingest.asyncpg.connect",
            AsyncMock(return_value=conn),
        ):
            response = client.post("/api/legal/ingest-full", json=_payload())

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        conn.execute.assert_called_once()

    def test_pending_job_reports_in_progress_without_reset(self, client):
        conn = _mock_conn({"id": "j3", "status": "pending"})

        with patch(
            "backend.app.routers.legal_ingest.asyncpg.connect",
            AsyncMock(return_value=conn),
        ):
            response = client.post("/api/legal/ingest-full", json=_payload())

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "j3"
        assert data["status"] == "pending"
        assert data["message"] == "Job gia in corso."
        conn.execute.assert_not_called()

    def test_in_flight_statuses_all_report_in_progress(self, client):
        for status_value in ("qdrant_done", "drive_done", "nlm_done"):
            conn = _mock_conn({"id": "j4", "status": status_value})
            with patch(
                "backend.app.routers.legal_ingest.asyncpg.connect",
                AsyncMock(return_value=conn),
            ):
                response = client.post("/api/legal/ingest-full", json=_payload())

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == status_value
            assert data["message"] == "Job gia in corso."
            conn.execute.assert_not_called()

    def test_complete_job_returns_already_exists(self, client):
        conn = _mock_conn({"id": "j5", "status": "complete"})

        with patch(
            "backend.app.routers.legal_ingest.asyncpg.connect",
            AsyncMock(return_value=conn),
        ):
            response = client.post("/api/legal/ingest-full", json=_payload())

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "j5"
        assert data["status"] == "already_exists"
        assert data["message"] == "Legge gia ingestita. Usa job_id per i dettagli."
        conn.execute.assert_not_called()
