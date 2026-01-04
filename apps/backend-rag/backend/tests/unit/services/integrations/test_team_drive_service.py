"""
Unit tests for TeamDriveService

Tests cover:
- OAuth token handling (SYSTEM token, refresh)
- File operations (list, download, upload, search)
- Folder operations (create, get path)
- CRUD operations (rename, delete, move, copy)
- Permission management (list, add, update, remove)
- Audit logging functionality
- Prometheus metrics integration

Target: >90% coverage
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_db_pool():
    """Create mock database pool with OAuth token."""
    pool = AsyncMock()
    conn = AsyncMock()

    # Default: return valid OAuth token
    conn.fetchrow = AsyncMock(
        return_value={
            "access_token": "ya29.test_token",
            "refresh_token": "1//test_refresh_token",
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )
    conn.execute = AsyncMock()

    # Context manager support
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=conn)

    return pool


@pytest.fixture
def mock_db_pool_expired_token():
    """Create mock database pool with expired OAuth token."""
    pool = AsyncMock()
    conn = AsyncMock()

    conn.fetchrow = AsyncMock(
        return_value={
            "access_token": "ya29.expired_token",
            "refresh_token": "1//test_refresh_token",
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        }
    )
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=conn)

    return pool


@pytest.fixture
def mock_drive_service():
    """Create mock Google Drive API service."""
    service = MagicMock()

    # Mock files().list()
    files_mock = MagicMock()
    files_mock.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "file_123",
                "name": "test_doc.pdf",
                "mimeType": "application/pdf",
                "size": "1024",
                "modifiedTime": "2026-01-04T10:00:00Z",
                "webViewLink": "https://drive.google.com/file/d/file_123",
            },
            {
                "id": "folder_456",
                "name": "Test Folder",
                "mimeType": "application/vnd.google-apps.folder",
                "modifiedTime": "2026-01-04T09:00:00Z",
            },
        ],
        "nextPageToken": None,
    }

    # Mock files().get()
    files_mock.get.return_value.execute.return_value = {
        "id": "file_123",
        "name": "test_doc.pdf",
        "mimeType": "application/pdf",
        "size": "1024",
        "modifiedTime": "2026-01-04T10:00:00Z",
        "webViewLink": "https://drive.google.com/file/d/file_123",
        "parents": ["parent_folder_id"],
    }

    # Mock files().create()
    files_mock.create.return_value.execute.return_value = {
        "id": "new_file_789",
        "name": "uploaded_file.pdf",
        "mimeType": "application/pdf",
        "size": "2048",
        "modifiedTime": "2026-01-04T11:00:00Z",
        "webViewLink": "https://drive.google.com/file/d/new_file_789",
    }

    # Mock files().update()
    files_mock.update.return_value.execute.return_value = {
        "id": "file_123",
        "name": "renamed_file.pdf",
        "mimeType": "application/pdf",
        "size": "1024",
        "modifiedTime": "2026-01-04T12:00:00Z",
    }

    # Mock files().delete()
    files_mock.delete.return_value.execute.return_value = {}

    # Mock files().copy()
    files_mock.copy.return_value.execute.return_value = {
        "id": "copy_file_999",
        "name": "copied_file.pdf",
        "mimeType": "application/pdf",
    }

    # Mock about().get() for connected user
    about_mock = MagicMock()
    about_mock.get.return_value.execute.return_value = {
        "user": {"emailAddress": "antonellosiano@gmail.com"}
    }

    # Mock permissions()
    permissions_mock = MagicMock()
    permissions_mock.list.return_value.execute.return_value = {
        "permissions": [
            {"id": "perm_1", "emailAddress": "user1@example.com", "role": "writer", "type": "user"},
            {"id": "perm_2", "emailAddress": "user2@example.com", "role": "reader", "type": "user"},
        ]
    }
    permissions_mock.create.return_value.execute.return_value = {
        "id": "perm_new",
        "emailAddress": "new@example.com",
        "role": "reader",
        "type": "user",
    }
    permissions_mock.update.return_value.execute.return_value = {
        "id": "perm_1",
        "emailAddress": "user1@example.com",
        "role": "owner",
        "type": "user",
    }
    permissions_mock.delete.return_value.execute.return_value = {}

    service.files.return_value = files_mock
    service.about.return_value = about_mock
    service.permissions.return_value = permissions_mock

    return service


@pytest.fixture
def team_drive_service(mock_db_pool, mock_drive_service):
    """Create TeamDriveService with mocked dependencies."""
    # settings is imported inside methods, so we patch app.core.config.settings
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.google_drive_client_id = "test_client_id"
        mock_settings.google_drive_client_secret = "test_client_secret"

        from services.integrations.team_drive_service import TeamDriveService

        service = TeamDriveService(db_pool=mock_db_pool, root_folder_id="root_folder_id_123")

        # Pre-inject the mock service to avoid OAuth/SA initialization
        service._service = mock_drive_service
        service._is_oauth_mode = True
        service._connected_as = "antonellosiano@gmail.com"

        return service


# =========================================================================
# Test: Initialization
# =========================================================================


class TestTeamDriveServiceInit:
    """Tests for service initialization."""

    def test_init_with_db_pool(self, mock_db_pool):
        """Test initialization with database pool."""
        from services.integrations.team_drive_service import TeamDriveService

        service = TeamDriveService(db_pool=mock_db_pool, root_folder_id="root_123")

        assert service._db_pool == mock_db_pool
        assert service._root_folder_id == "root_123"
        assert service._service is None
        assert service._is_oauth_mode is False

    def test_init_without_db_pool(self):
        """Test initialization without database pool (Service Account fallback)."""
        from services.integrations.team_drive_service import TeamDriveService

        service = TeamDriveService()

        assert service._db_pool is None
        assert service._root_folder_id is None

    def test_get_connection_info_oauth(self, team_drive_service):
        """Test connection info in OAuth mode."""
        info = team_drive_service.get_connection_info()

        assert info["mode"] == "oauth"
        assert info["connected_as"] == "antonellosiano@gmail.com"
        assert info["is_oauth"] is True

    def test_get_connection_info_service_account(self, mock_db_pool):
        """Test connection info in Service Account mode."""
        from services.integrations.team_drive_service import TeamDriveService

        service = TeamDriveService(db_pool=mock_db_pool)
        service._is_oauth_mode = False
        service._connected_as = "nuzantara-bot@nuzantara.iam.gserviceaccount.com"

        info = service.get_connection_info()

        assert info["mode"] == "service_account"
        assert "nuzantara-bot" in info["connected_as"]


# =========================================================================
# Test: OAuth Token Handling
# =========================================================================


class TestOAuthTokenHandling:
    """Tests for OAuth token retrieval and refresh."""

    @pytest.mark.asyncio
    async def test_get_oauth_token_valid(self, mock_db_pool):
        """Test getting valid OAuth token from database."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_drive_client_id = "test_client_id"
            mock_settings.google_drive_client_secret = "test_secret"

            from services.integrations.team_drive_service import TeamDriveService

            service = TeamDriveService(db_pool=mock_db_pool)
            token_data = await service._get_oauth_token()

            assert token_data is not None
            assert token_data["access_token"] == "ya29.test_token"
            assert token_data["refresh_token"] == "1//test_refresh_token"

    @pytest.mark.asyncio
    async def test_get_oauth_token_no_db_pool(self):
        """Test OAuth token returns None when no db_pool."""
        from services.integrations.team_drive_service import TeamDriveService

        service = TeamDriveService()
        token_data = await service._get_oauth_token()

        assert token_data is None

    @pytest.mark.asyncio
    async def test_get_oauth_token_not_found(self, mock_db_pool):
        """Test OAuth token returns None when not in database."""
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value=None
        )

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_drive_client_id = "test_client_id"
            mock_settings.google_drive_client_secret = "test_secret"

            from services.integrations.team_drive_service import TeamDriveService

            service = TeamDriveService(db_pool=mock_db_pool)
            token_data = await service._get_oauth_token()

            assert token_data is None

    @pytest.mark.asyncio
    async def test_refresh_oauth_token_success(self, mock_db_pool_expired_token):
        """Test successful OAuth token refresh."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_drive_client_id = "test_client_id"
            mock_settings.google_drive_client_secret = "test_secret"

            with patch("httpx.AsyncClient") as mock_httpx:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "access_token": "ya29.new_token",
                    "expires_in": 3600,
                }

                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_httpx.return_value = mock_client

                from services.integrations.team_drive_service import TeamDriveService

                service = TeamDriveService(db_pool=mock_db_pool_expired_token)
                new_token = await service._refresh_oauth_token("1//test_refresh")

                assert new_token == "ya29.new_token"

    @pytest.mark.asyncio
    async def test_refresh_oauth_token_failure(self, mock_db_pool_expired_token):
        """Test OAuth token refresh failure."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_drive_client_id = "test_client_id"
            mock_settings.google_drive_client_secret = "test_secret"

            with patch("httpx.AsyncClient") as mock_httpx:
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_response.text = "Invalid refresh token"

                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_httpx.return_value = mock_client

                from services.integrations.team_drive_service import TeamDriveService

                service = TeamDriveService(db_pool=mock_db_pool_expired_token)
                new_token = await service._refresh_oauth_token("1//bad_refresh")

                assert new_token is None


# =========================================================================
# Test: File Operations
# =========================================================================


class TestFileOperations:
    """Tests for file listing, download, search."""

    @pytest.mark.asyncio
    async def test_list_files_in_folder(self, team_drive_service):
        """Test listing files in a specific folder."""
        result = await team_drive_service.list_files(folder_id="folder_123")

        assert "files" in result
        assert len(result["files"]) == 2
        assert result["files"][0]["id"] == "file_123"
        assert result["files"][0]["type"] == "file"
        assert result["files"][1]["type"] == "folder"

    @pytest.mark.asyncio
    async def test_list_files_with_query(self, team_drive_service):
        """Test listing files with search query."""
        result = await team_drive_service.list_files(query="test")

        assert "files" in result

    @pytest.mark.asyncio
    async def test_list_files_uses_root_folder(self, team_drive_service):
        """Test list_files uses root_folder_id when folder_id is None."""
        result = await team_drive_service.list_files()

        # The mock should have been called (we just verify no exception)
        assert "files" in result

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, team_drive_service):
        """Test getting file metadata."""
        result = await team_drive_service.get_file_metadata(file_id="file_123")

        assert result["id"] == "file_123"
        assert result["name"] == "test_doc.pdf"
        assert result["type"] == "file"

    @pytest.mark.asyncio
    async def test_search_files(self, team_drive_service):
        """Test searching files."""
        result = await team_drive_service.search_files(query="test", file_type="pdf")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_folder_path(self, team_drive_service, mock_drive_service):
        """Test getting folder breadcrumb path."""
        # Mock the get() call for folder path traversal
        mock_drive_service.files.return_value.get.return_value.execute.side_effect = [
            {"id": "folder_2", "name": "Child Folder", "parents": ["folder_1"]},
            {"id": "folder_1", "name": "Parent Folder", "parents": []},
        ]

        result = await team_drive_service.get_folder_path(folder_id="folder_2")

        assert isinstance(result, list)
        # Path should be built from root to current folder


# =========================================================================
# Test: CRUD Operations
# =========================================================================


class TestCRUDOperations:
    """Tests for create, rename, delete, move, copy."""

    @pytest.mark.asyncio
    async def test_upload_file(self, team_drive_service):
        """Test uploading a file."""
        with patch("services.integrations.team_drive_service.MediaIoBaseUpload"):
            result = await team_drive_service.upload_file(
                file_content=b"test content",
                filename="test_upload.txt",
                mime_type="text/plain",
                parent_folder_id="folder_123",
            )

            assert result["id"] == "new_file_789"
            assert result["type"] == "file"

    @pytest.mark.asyncio
    async def test_create_folder(self, team_drive_service):
        """Test creating a folder."""
        result = await team_drive_service.create_folder(
            name="New Folder", parent_folder_id="parent_folder_id"
        )

        assert result["type"] == "folder"

    @pytest.mark.asyncio
    async def test_create_google_doc(self, team_drive_service):
        """Test creating a Google Doc."""
        result = await team_drive_service.create_google_doc(
            name="New Document", parent_folder_id="parent_folder_id", doc_type="document"
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_create_google_doc_invalid_type(self, team_drive_service):
        """Test creating Google Doc with invalid type raises error."""
        with pytest.raises(ValueError, match="Invalid doc_type"):
            await team_drive_service.create_google_doc(
                name="Test", parent_folder_id="folder_id", doc_type="invalid_type"
            )

    @pytest.mark.asyncio
    async def test_rename_file(self, team_drive_service):
        """Test renaming a file."""
        result = await team_drive_service.rename_file(file_id="file_123", new_name="new_name.pdf")

        assert result["name"] == "renamed_file.pdf"

    @pytest.mark.asyncio
    async def test_delete_file_to_trash(self, team_drive_service):
        """Test deleting file to trash."""
        result = await team_drive_service.delete_file(file_id="file_123", permanent=False)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_file_permanent(self, team_drive_service):
        """Test permanently deleting a file."""
        result = await team_drive_service.delete_file(file_id="file_123", permanent=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_move_file(self, team_drive_service):
        """Test moving a file to different folder."""
        result = await team_drive_service.move_file(
            file_id="file_123", new_parent_id="new_folder_id", old_parent_id="old_folder_id"
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_copy_file(self, team_drive_service):
        """Test copying a file."""
        result = await team_drive_service.copy_file(
            file_id="file_123", new_name="copied_file.pdf", parent_folder_id="target_folder_id"
        )

        assert result["id"] == "copy_file_999"


# =========================================================================
# Test: Permission Management
# =========================================================================


class TestPermissionManagement:
    """Tests for permission operations."""

    @pytest.mark.asyncio
    async def test_list_permissions(self, team_drive_service):
        """Test listing file permissions."""
        result = await team_drive_service.list_permissions(file_id="file_123")

        assert len(result) == 2
        assert result[0]["email"] == "user1@example.com"
        assert result[0]["role"] == "writer"

    @pytest.mark.asyncio
    async def test_add_permission(self, team_drive_service):
        """Test adding permission to a file."""
        result = await team_drive_service.add_permission(
            file_id="file_123", email="new_user@example.com", role="reader", send_notification=True
        )

        assert result["email"] == "new@example.com"
        assert result["role"] == "reader"

    @pytest.mark.asyncio
    async def test_update_permission(self, team_drive_service):
        """Test updating permission role."""
        result = await team_drive_service.update_permission(
            file_id="file_123", permission_id="perm_1", role="owner"
        )

        assert result["role"] == "owner"

    @pytest.mark.asyncio
    async def test_remove_permission(self, team_drive_service):
        """Test removing permission."""
        result = await team_drive_service.remove_permission(
            file_id="file_123", permission_id="perm_1"
        )

        assert result is True


# =========================================================================
# Test: Audit Logging
# =========================================================================


class TestAuditLogging:
    """Tests for audit logging functionality."""

    def test_audit_logger_initialization(self):
        """Test DriveAuditLogger initializes correctly."""
        from services.integrations.team_drive_service import DriveAuditLogger

        logger = DriveAuditLogger()
        assert logger.audit_logger is not None

    def test_audit_logger_log_success(self):
        """Test logging successful operation."""
        from services.integrations.team_drive_service import DriveAuditLogger

        logger = DriveAuditLogger()

        with patch.object(logger.audit_logger, "info") as mock_info:
            logger.log(
                operation="list_files",
                user_email="test@example.com",
                status="success",
                file_id="file_123",
                duration_ms=150.5,
            )

            mock_info.assert_called_once()
            # Verify JSON structure
            call_args = mock_info.call_args[0][0]
            log_data = json.loads(call_args)

            assert log_data["operation"] == "list_files"
            assert log_data["user_email"] == "test@example.com"
            assert log_data["status"] == "success"
            assert log_data["duration_ms"] == 150.5

    def test_audit_logger_log_error(self):
        """Test logging failed operation with error message."""
        from services.integrations.team_drive_service import DriveAuditLogger

        logger = DriveAuditLogger()

        with patch.object(logger.audit_logger, "info") as mock_info:
            logger.log(
                operation="upload_file",
                user_email="test@example.com",
                status="error",
                file_name="test.pdf",
                error_message="Quota exceeded",
            )

            call_args = mock_info.call_args[0][0]
            log_data = json.loads(call_args)

            assert log_data["status"] == "error"
            assert log_data["error"] == "Quota exceeded"

    def test_audit_logger_error_classification(self):
        """Test error message classification."""
        from services.integrations.team_drive_service import DriveAuditLogger

        logger = DriveAuditLogger()

        assert logger._classify_error("storageQuotaExceeded") == "quota_exceeded"
        assert logger._classify_error("Permission denied") == "permission_denied"
        assert logger._classify_error("File not found") == "not_found"
        assert logger._classify_error("Rate limit exceeded") == "rate_limited"
        assert logger._classify_error("Invalid token") == "auth_error"
        assert logger._classify_error("Connection timeout") == "timeout"
        assert logger._classify_error("Network error") == "network_error"
        assert logger._classify_error("Unknown issue") == "unknown"

    @pytest.mark.asyncio
    async def test_drive_operation_decorator_success(self, team_drive_service):
        """Test that @drive_operation decorator logs success."""
        with patch("services.integrations.team_drive_service.audit_logger") as mock_audit:
            await team_drive_service.list_files(folder_id="test_folder")

            mock_audit.log.assert_called_once()
            call_kwargs = mock_audit.log.call_args[1]

            assert call_kwargs["operation"] == "list_files"
            assert call_kwargs["status"] == "success"
            assert call_kwargs["user_email"] == "antonellosiano@gmail.com"

    @pytest.mark.asyncio
    async def test_drive_operation_decorator_error(self, team_drive_service, mock_drive_service):
        """Test that @drive_operation decorator logs errors."""
        # Make the operation fail
        mock_drive_service.files.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        with patch("services.integrations.team_drive_service.audit_logger") as mock_audit:
            with pytest.raises(Exception, match="API Error"):
                await team_drive_service.list_files(folder_id="test_folder")

            mock_audit.log.assert_called_once()
            call_kwargs = mock_audit.log.call_args[1]

            assert call_kwargs["status"] == "error"
            assert call_kwargs["error_message"] == "API Error"


# =========================================================================
# Test: Metrics Integration
# =========================================================================


class TestMetricsIntegration:
    """Tests for Prometheus metrics integration."""

    def test_metrics_import(self):
        """Test metrics can be imported when available."""
        from services.integrations.team_drive_service import METRICS_ENABLED

        # Should be True or False depending on environment
        assert isinstance(METRICS_ENABLED, bool)

    @pytest.mark.asyncio
    async def test_oauth_refresh_records_metrics(self, mock_db_pool_expired_token):
        """Test OAuth token refresh records metrics."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_drive_client_id = "test_id"
            mock_settings.google_drive_client_secret = "test_secret"

            with patch("services.integrations.team_drive_service.METRICS_ENABLED", True):
                with patch(
                    "services.integrations.team_drive_service.metrics_collector"
                ) as mock_metrics:
                    with patch("httpx.AsyncClient") as mock_httpx:
                        mock_response = MagicMock()
                        mock_response.status_code = 200
                        mock_response.json.return_value = {
                            "access_token": "new_token",
                            "expires_in": 3600,
                        }

                        mock_client = AsyncMock()
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=None)
                        mock_client.post = AsyncMock(return_value=mock_response)
                        mock_httpx.return_value = mock_client

                        from services.integrations.team_drive_service import TeamDriveService

                        service = TeamDriveService(db_pool=mock_db_pool_expired_token)
                        await service._refresh_oauth_token("refresh_token")

                        mock_metrics.record_drive_oauth_refresh.assert_called_with("success")
                        mock_metrics.set_drive_oauth_expiry.assert_called_with(3600)


# =========================================================================
# Test: Singleton Pattern
# =========================================================================


class TestSingletonPattern:
    """Tests for get_team_drive_service singleton."""

    def test_get_team_drive_service_with_pool(self, mock_db_pool):
        """Test getting service instance with db_pool."""
        from services.integrations.team_drive_service import get_team_drive_service

        with patch.dict("os.environ", {"GOOGLE_DRIVE_ROOT_FOLDER_ID": "root_123"}):
            service = get_team_drive_service(db_pool=mock_db_pool)

            assert service._db_pool == mock_db_pool
            assert service._root_folder_id == "root_123"

    def test_get_team_drive_service_without_pool(self):
        """Test getting service instance without db_pool."""
        from services.integrations.team_drive_service import get_team_drive_service

        service = get_team_drive_service()

        assert service._db_pool is None
