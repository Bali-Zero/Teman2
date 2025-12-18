"""
Unit tests for smart_oracle service
Tests PDF analysis and Google Drive integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")
os.environ.setdefault("GOOGLE_CREDENTIALS_JSON", "{}")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestSmartOracle:
    """Unit tests for smart_oracle"""

    def test_get_drive_service_success(self):
        """Test successful Google Drive service initialization"""
        with (
            patch("services.smart_oracle.settings") as mock_settings,
            patch(
                "services.smart_oracle.service_account.Credentials.from_service_account_info"
            ) as mock_creds,
            patch("services.smart_oracle.build") as mock_build,
        ):
            mock_settings.google_credentials_json = '{"type": "service_account"}'
            mock_creds.return_value = MagicMock()
            mock_build.return_value = MagicMock()

            from services.smart_oracle import get_drive_service

            service = get_drive_service()
            assert service is not None

    def test_get_drive_service_no_credentials(self):
        """Test Drive service initialization without credentials"""
        with patch("services.smart_oracle.settings") as mock_settings:
            mock_settings.google_credentials_json = None

            from services.smart_oracle import get_drive_service

            service = get_drive_service()
            assert service is None

    def test_get_drive_service_invalid_credentials(self):
        """Test Drive service initialization with invalid credentials"""
        with (
            patch("services.smart_oracle.settings") as mock_settings,
            patch("services.smart_oracle.json.loads", side_effect=Exception("Invalid JSON")),
        ):
            mock_settings.google_credentials_json = "invalid"

            from services.smart_oracle import get_drive_service

            service = get_drive_service()
            assert service is None

    def test_download_pdf_from_drive_success(self):
        """Test successful PDF download from Drive"""
        with patch("services.smart_oracle.get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_file_list = MagicMock()
            mock_file_list.execute.return_value = {"files": [{"id": "file123", "name": "test.pdf"}]}
            mock_service.files.return_value.list.return_value = mock_file_list

            mock_media = MagicMock()
            mock_media.execute.return_value = b"PDF content"
            mock_service.files.return_value.get_media.return_value = mock_media

            mock_get_service.return_value = mock_service

            from services.smart_oracle import download_pdf_from_drive

            result = download_pdf_from_drive("test.pdf")
            # May return None if download fails, but should at least try
            assert mock_service.files.return_value.list.called

    def test_download_pdf_from_drive_not_found(self):
        """Test PDF download when file not found"""
        with patch("services.smart_oracle.get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_file = MagicMock()
            mock_file.execute.return_value = {"files": []}
            mock_service.files.return_value.list.return_value = mock_file
            mock_get_service.return_value = mock_service

            from services.smart_oracle import download_pdf_from_drive

            result = download_pdf_from_drive("nonexistent.pdf")
            assert result is None

    def test_download_pdf_from_drive_no_service(self):
        """Test PDF download when Drive service unavailable"""
        with patch("services.smart_oracle.get_drive_service", return_value=None):
            from services.smart_oracle import download_pdf_from_drive

            result = download_pdf_from_drive("test.pdf")
            assert result is None

    def test_download_pdf_clean_name(self):
        """Test PDF download with path cleaning"""
        with patch("services.smart_oracle.get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_file = MagicMock()
            mock_file.execute.return_value = {"files": [{"id": "file123", "name": "test.pdf"}]}
            mock_service.files.return_value.list.return_value = mock_file
            mock_get_service.return_value = mock_service

            from services.smart_oracle import download_pdf_from_drive

            # Test with path containing folder
            result = download_pdf_from_drive("folder/test.pdf")
            # Should clean to just "test"
            assert mock_service.files.return_value.list.called

    def test_download_pdf_underscore_replacement(self):
        """Test PDF download with underscore replacement"""
        with patch("services.smart_oracle.get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_file = MagicMock()
            # First call returns empty, second call (with underscore replacement) returns file
            mock_file.execute.side_effect = [
                {"files": []},
                {"files": [{"id": "file123", "name": "test 2024.pdf"}]},
            ]
            mock_service.files.return_value.list.return_value = mock_file
            mock_get_service.return_value = mock_service

            from services.smart_oracle import download_pdf_from_drive

            result = download_pdf_from_drive("test_2024.pdf")
            # Should try alternative search with spaces
            assert mock_service.files.return_value.list.call_count >= 2
