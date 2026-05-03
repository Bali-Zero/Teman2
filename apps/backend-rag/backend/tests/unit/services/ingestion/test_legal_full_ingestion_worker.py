"""Unit tests for backend/services/ingestion/legal_full_ingestion_worker.py"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _AsyncCM:
    """Reusable async context manager returning a fixed connection mock."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _AsyncTxCM:
    """Async context manager mimicking a DB transaction."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def mock_db_pool():
    """Create a mock asyncpg pool.

    pool.acquire() returns a synchronous async-CM (not a coroutine).
    """
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncTxCM())

    pool.acquire.return_value = _AsyncCM(conn)

    return pool, conn


@pytest.fixture
def mock_app_state():
    return MagicMock()


# ---------------------------------------------------------------------------
# _claim_job
# ---------------------------------------------------------------------------


class TestClaimJob:
    @pytest.mark.asyncio
    async def test_claim_returns_row(self, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = {"id": "job-1", "status": "pending"}

        from backend.services.ingestion.legal_full_ingestion_worker import _claim_job

        result = await _claim_job(conn)
        assert result["id"] == "job-1"
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_claim_returns_none_when_empty(self, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchrow.return_value = None

        from backend.services.ingestion.legal_full_ingestion_worker import _claim_job

        result = await _claim_job(conn)
        assert result is None


# ---------------------------------------------------------------------------
# _update_job
# ---------------------------------------------------------------------------


class TestUpdateJob:
    @pytest.mark.asyncio
    async def test_update_job_calls_execute(self, mock_db_pool):
        _, conn = mock_db_pool

        from backend.services.ingestion.legal_full_ingestion_worker import _update_job

        await _update_job(conn, "job-1", status="qdrant_done", qdrant_chunks=10)
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        # Should include job_id and field values
        assert call_args[0][1] == "job-1"

    @pytest.mark.asyncio
    async def test_update_single_field(self, mock_db_pool):
        _, conn = mock_db_pool

        from backend.services.ingestion.legal_full_ingestion_worker import _update_job

        await _update_job(conn, "job-2", status="failed")
        conn.execute.assert_called_once()


# ---------------------------------------------------------------------------
# _download_pdf
# ---------------------------------------------------------------------------


class TestDownloadPdf:
    @pytest.mark.asyncio
    async def test_download_success(self):
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 test content"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "backend.services.ingestion.legal_full_ingestion_worker.httpx.AsyncClient",
            return_value=mock_client,
        ), patch("pathlib.Path.write_bytes") as mock_write, patch(
            "tempfile.mkdtemp", return_value="/tmp/test_dl"
        ):
            from backend.services.ingestion.legal_full_ingestion_worker import (
                _download_pdf,
            )

            result = await _download_pdf(
                "https://example.com/doc.pdf", "PP", "123", "2024"
            )

        assert isinstance(result, Path)
        assert "PP_123_2024.pdf" in str(result)

    @pytest.mark.asyncio
    async def test_download_http_error(self):
        import httpx

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "backend.services.ingestion.legal_full_ingestion_worker.httpx.AsyncClient",
            return_value=mock_client,
        ), patch("tempfile.mkdtemp", return_value="/tmp/err"):
            from backend.services.ingestion.legal_full_ingestion_worker import (
                _download_pdf,
            )

            with pytest.raises(httpx.HTTPStatusError):
                await _download_pdf("https://example.com/bad", "PP", "1", "2024")


# ---------------------------------------------------------------------------
# _build_drive_service
# ---------------------------------------------------------------------------


class TestBuildDriveService:
    def test_no_credentials_returns_none(self):
        with patch.dict(
            "os.environ",
            {"GOOGLE_SERVICE_ACCOUNT_JSON": "", "GOOGLE_SERVICE_ACCOUNT": ""},
            clear=False,
        ):
            from backend.services.ingestion.legal_full_ingestion_worker import (
                _build_drive_service,
            )

            result = _build_drive_service()
        assert result is None

    def test_invalid_json_returns_none(self):
        with patch.dict(
            "os.environ",
            {"GOOGLE_SERVICE_ACCOUNT_JSON": "not-json", "GOOGLE_SERVICE_ACCOUNT": ""},
            clear=False,
        ):
            from backend.services.ingestion.legal_full_ingestion_worker import (
                _build_drive_service,
            )

            result = _build_drive_service()
        # Returns None because json.loads fails and base64 decode also fails
        assert result is None

    def test_valid_credentials_builds_service(self):
        import json

        creds = {
            "type": "service_account",
            "project_id": "test",
            "private_key_id": "x",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "test@test.iam.gserviceaccount.com",
            "client_id": "123",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        with patch.dict(
            "os.environ",
            {"GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(creds)},
            clear=False,
        ), patch(
            "google.oauth2.service_account.Credentials.from_service_account_info"
        ) as mock_creds, patch(
            "googleapiclient.discovery.build"
        ) as mock_build:
            mock_creds.return_value = MagicMock()
            mock_build.return_value = MagicMock()

            from backend.services.ingestion.legal_full_ingestion_worker import (
                _build_drive_service,
            )

            result = _build_drive_service()

        assert result is not None


# ---------------------------------------------------------------------------
# _drive_upload_file
# ---------------------------------------------------------------------------


class TestDriveUploadFile:
    def test_upload_returns_file_info(self):
        mock_service = MagicMock()
        mock_service.files.return_value.create.return_value.execute.return_value = {
            "id": "file-123",
            "webViewLink": "https://drive.google.com/file/d/file-123/view",
        }

        with patch(
            "googleapiclient.http.MediaIoBaseUpload",
            MagicMock,
        ):
            from backend.services.ingestion.legal_full_ingestion_worker import (
                _drive_upload_file,
            )

            pdf_path = MagicMock(spec=Path)
            pdf_path.read_bytes.return_value = b"pdf content"

            result = _drive_upload_file(mock_service, pdf_path, "folder-1", "doc.pdf")

        assert result["file_id"] == "file-123"
        assert "drive.google.com" in result["web_view_link"]


# ---------------------------------------------------------------------------
# _drive_get_or_create_folder
# ---------------------------------------------------------------------------


class TestDriveGetOrCreateFolder:
    def test_existing_folder_returned(self):
        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "existing-folder"}]
        }

        from backend.services.ingestion.legal_full_ingestion_worker import (
            _drive_get_or_create_folder,
        )

        result = _drive_get_or_create_folder(mock_service, "PERATURAN", "root")
        assert result == "existing-folder"

    def test_creates_folder_when_missing(self):
        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": []
        }
        mock_service.files.return_value.create.return_value.execute.return_value = {
            "id": "new-folder"
        }

        from backend.services.ingestion.legal_full_ingestion_worker import (
            _drive_get_or_create_folder,
        )

        result = _drive_get_or_create_folder(mock_service, "PERATURAN", "root")
        assert result == "new-folder"


# ---------------------------------------------------------------------------
# _drive_find_file
# ---------------------------------------------------------------------------


class TestDriveFindFile:
    def test_file_found(self):
        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "f1", "webViewLink": "https://drive/f1"}]
        }

        from backend.services.ingestion.legal_full_ingestion_worker import (
            _drive_find_file,
        )

        result = _drive_find_file(mock_service, "doc.pdf", "folder-1")
        assert result["file_id"] == "f1"

    def test_file_not_found(self):
        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": []
        }

        from backend.services.ingestion.legal_full_ingestion_worker import (
            _drive_find_file,
        )

        result = _drive_find_file(mock_service, "missing.pdf", "folder-1")
        assert result is None


# ---------------------------------------------------------------------------
# _process_one_job
# ---------------------------------------------------------------------------


class TestProcessOneJob:
    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(self, mock_db_pool, mock_app_state):
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = None

        # Need transaction context manager
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock()
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction.return_value = tx

        from backend.services.ingestion.legal_full_ingestion_worker import (
            _process_one_job,
        )

        await _process_one_job(pool, mock_app_state)

    @pytest.mark.asyncio
    async def test_pending_job_no_source_url_fails(
        self, mock_db_pool, mock_app_state
    ):
        pool, conn = mock_db_pool

        job = {
            "id": "job-1",
            "tipo": "PP",
            "nomor": "123",
            "anno": "2024",
            "source_url": "",
            "nb_target": "NB-3",
            "titolo": "Test",
            "status": "pending",
        }

        # First call (in transaction): claim job
        # Second call: update to failed
        conn.fetchrow.return_value = job

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock()
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction.return_value = tx

        from backend.services.ingestion.legal_full_ingestion_worker import (
            _process_one_job,
        )

        await _process_one_job(pool, mock_app_state)

        # Should have called execute to mark failed
        assert conn.execute.called


# ---------------------------------------------------------------------------
# run_worker
# ---------------------------------------------------------------------------


class TestRunWorker:
    @pytest.mark.asyncio
    async def test_worker_handles_cancellation(self, mock_db_pool, mock_app_state):
        pool, conn = mock_db_pool

        with patch(
            "backend.services.ingestion.legal_full_ingestion_worker._process_one_job",
            new_callable=AsyncMock,
        ) as mock_process:
            # Simulate cancellation after first call
            mock_process.side_effect = asyncio.CancelledError()

            from backend.services.ingestion.legal_full_ingestion_worker import (
                run_worker,
            )

            await run_worker(pool, mock_app_state)
            # Should return gracefully

    @pytest.mark.asyncio
    async def test_worker_handles_exception(self, mock_db_pool, mock_app_state):
        pool, conn = mock_db_pool
        call_count = 0

        async def mock_process(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("db error")
            raise asyncio.CancelledError()

        with patch(
            "backend.services.ingestion.legal_full_ingestion_worker._process_one_job",
            side_effect=mock_process,
        ), patch(
            "backend.services.ingestion.legal_full_ingestion_worker.WORKER_INTERVAL", 0
        ):
            from backend.services.ingestion.legal_full_ingestion_worker import (
                run_worker,
            )

            await run_worker(pool, mock_app_state)

        assert call_count == 2  # First error, then cancel
