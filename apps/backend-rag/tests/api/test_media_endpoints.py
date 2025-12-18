"""
API Tests for Media Router
Tests image generation endpoint

Coverage:
- POST /media/generate-image - Generate image from prompt
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestMediaEndpoints:
    """Tests for media endpoints"""

    def test_generate_image_success(self, authenticated_client):
        """Test POST /media/generate-image - successful generation"""
        with patch("app.routers.media.ImageGenerationService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(
                return_value={
                    "success": True,
                    "url": "https://example.com/image.png",
                    "prompt": "Test prompt",
                    "service": "test_service",
                }
            )
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "A beautiful sunset"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "url" in data

    def test_generate_image_service_error(self, authenticated_client):
        """Test POST /media/generate-image - service error"""
        # Mock the ImageGenerationService to return an error
        with patch("app.routers.media.ImageGenerationService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Service not configured",
                }
            )
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "Test prompt"},
            )

            # The endpoint returns 503 for "not configured" errors
            assert response.status_code in [200, 503, 500]

    def test_generate_image_invalid_prompt(self, authenticated_client):
        """Test POST /media/generate-image - invalid prompt"""
        with patch(
            "services.image_generation_service.ImageGenerationService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(
                return_value={
                    "success": False,
                    "error": "Invalid prompt",
                }
            )
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": ""},
            )

            assert response.status_code in [400, 422, 500]

    def test_generate_image_missing_prompt(self, authenticated_client):
        """Test POST /media/generate-image - missing prompt field"""
        response = authenticated_client.post(
            "/media/generate-image",
            json={},
        )

        assert response.status_code == 422

    def test_generate_image_long_prompt(self, authenticated_client):
        """Test POST /media/generate-image - very long prompt"""
        with patch("app.routers.media.ImageGenerationService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(
                return_value={
                    "success": True,
                    "url": "https://example.com/image.png",
                    "prompt": "A" * 1000,
                }
            )
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "A" * 1000},
            )

            assert response.status_code == 200

    def test_generate_image_internal_error(self, authenticated_client):
        """Test POST /media/generate-image - internal server error"""
        with patch("app.routers.media.ImageGenerationService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(side_effect=Exception("Internal error"))
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "Test prompt"},
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_generate_image_requires_auth(self, test_client):
        """Test POST /media/generate-image - requires authentication"""
        response = test_client.post(
            "/media/generate-image",
            json={"prompt": "Test prompt"},
        )

        assert response.status_code == 401

    def test_generate_image_special_characters(self, authenticated_client):
        """Test POST /media/generate-image - prompt with special characters"""
        with patch("app.routers.media.ImageGenerationService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(
                return_value={
                    "success": True,
                    "url": "https://example.com/image.png",
                    "prompt": "Test with émojis 🎨 and spéciál chars",
                }
            )
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "Test with émojis 🎨 and spéciál chars"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_generate_image_response_structure(self, authenticated_client):
        """Test POST /media/generate-image - response structure"""
        with patch("app.routers.media.ImageGenerationService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.generate_image = AsyncMock(
                return_value={
                    "success": True,
                    "url": "https://example.com/image.png",
                    "prompt": "Test prompt",
                    "service": "test_service",
                }
            )
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/media/generate-image",
                json={"prompt": "Test prompt"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "url" in data
            assert "prompt" in data
            assert "service" in data
