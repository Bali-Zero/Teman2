"""
Unit tests for media router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.media import router


@pytest.fixture
def app():
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestMediaRouter:
    """Tests for media router"""

    @patch("app.routers.media.ImageGenerationService")
    def test_generate_image_success(self, mock_service_class, client):
        """Test generating image successfully"""
        mock_service = MagicMock()
        mock_service.generate_image = AsyncMock(return_value={
            "success": True,
            "url": "https://pollinations.ai/image.jpg",
            "prompt": "test prompt"
        })
        mock_service_class.return_value = mock_service
        
        response = client.post(
            "/media/generate-image",
            json={"prompt": "test prompt"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "url" in data

    @patch("app.routers.media.ImageGenerationService")
    def test_generate_image_error(self, mock_service_class, client):
        """Test generating image with error"""
        mock_service = MagicMock()
        mock_service.generate_image = AsyncMock(return_value={
            "success": False,
            "error": "Invalid prompt"
        })
        mock_service_class.return_value = mock_service
        
        response = client.post(
            "/media/generate-image",
            json={"prompt": "test"}
        )
        assert response.status_code == 400

    @patch("app.routers.media.ImageGenerationService")
    def test_generate_image_not_configured(self, mock_service_class, client):
        """Test generating image when service not configured"""
        mock_service = MagicMock()
        mock_service.generate_image = AsyncMock(return_value={
            "success": False,
            "error": "Service not configured"
        })
        mock_service_class.return_value = mock_service
        
        response = client.post(
            "/media/generate-image",
            json={"prompt": "test"}
        )
        assert response.status_code == 503

    @patch("app.routers.media.ImageGenerationService")
    def test_generate_image_exception(self, mock_service_class, client):
        """Test generating image with exception"""
        mock_service = MagicMock()
        mock_service.generate_image = AsyncMock(side_effect=Exception("Service error"))
        mock_service_class.return_value = mock_service
        
        response = client.post(
            "/media/generate-image",
            json={"prompt": "test"}
        )
        assert response.status_code == 500

    @patch("app.routers.media.Path")
    @patch("app.routers.media.shutil")
    @patch("app.routers.media.uuid")
    def test_upload_file(self, mock_uuid, mock_shutil, mock_path_class, client):
        """Test uploading a file"""
        mock_uuid.uuid4.return_value.hex = "test-uuid"
        
        # Mock Path
        mock_path = MagicMock()
        mock_path.mkdir = MagicMock()
        mock_path.__truediv__ = MagicMock(return_value=mock_path)
        mock_path_class.return_value = mock_path
        
        # Create a test file
        test_file = ("test.txt", "test content", "text/plain")
        
        response = client.post(
            "/media/upload",
            files={"file": test_file}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "url" in data

    @patch("app.routers.media.Path")
    def test_upload_file_error(self, mock_path_class, client):
        """Test uploading file with error"""
        mock_path = MagicMock()
        mock_path.mkdir.side_effect = Exception("Permission error")
        mock_path_class.return_value = mock_path
        
        test_file = ("test.txt", "test content", "text/plain")
        
        response = client.post(
            "/media/upload",
            files={"file": test_file}
        )
        assert response.status_code == 500

