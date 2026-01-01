"""
Unit tests for image generation router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.image_generation import router


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


class TestImageGenerationRouter:
    """Tests for image generation router"""

    @patch("app.routers.image_generation.httpx.AsyncClient")
    @patch("app.routers.image_generation.settings")
    def test_generate_image_success(self, mock_settings, mock_client_class, client):
        """Test generating image successfully"""
        mock_settings.google_imagen_api_key = "test-key"
        
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "generatedImages": [
                {"bytesBase64Encoded": "base64data1"},
                {"bytesBase64Encoded": "base64data2"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client
        
        response = client.post(
            "/api/v1/image/generate",
            json={
                "prompt": "test prompt",
                "number_of_images": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 2

    @patch("app.routers.image_generation.settings")
    def test_generate_image_no_api_key(self, mock_settings, client):
        """Test generating image without API key"""
        mock_settings.google_imagen_api_key = None
        mock_settings.google_ai_studio_key = None
        mock_settings.google_api_key = None
        
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "test"}
        )
        assert response.status_code == 500

    @patch("app.routers.image_generation.httpx.AsyncClient")
    @patch("app.routers.image_generation.settings")
    def test_generate_image_403_error(self, mock_settings, mock_client_class, client):
        """Test generating image with 403 error"""
        mock_settings.google_imagen_api_key = "test-key"
        
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client
        
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "test"}
        )
        assert response.status_code == 403

    @patch("app.routers.image_generation.httpx.AsyncClient")
    @patch("app.routers.image_generation.settings")
    def test_generate_image_no_images(self, mock_settings, mock_client_class, client):
        """Test generating image with no images returned"""
        mock_settings.google_imagen_api_key = "test-key"
        
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"generatedImages": []}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_class.return_value = mock_client
        
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

