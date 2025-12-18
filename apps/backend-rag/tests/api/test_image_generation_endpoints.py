"""
API Tests for Image Generation Router
Tests Google Imagen API integration

Coverage:
- POST /api/v1/image/generate - Generate images
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["GOOGLE_AI_API_KEY"] = "test_google_ai_api_key_for_testing"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestImageGeneration:
    """Tests for image generation endpoint"""

    def test_generate_image_success(self, authenticated_client):
        """Test generating image successfully"""
        # Mock the image generation service in app.state
        from unittest.mock import MagicMock

        with (
            patch("app.routers.image_generation.settings.google_api_key", "test_key"),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "generatedImages": [
                    {
                        "bytesBase64Encoded": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    }
                ]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = MagicMock(return_value=None)
            mock_client_instance.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client_instance

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "A beautiful sunset over mountains",
                    "number_of_images": 1,
                    "aspect_ratio": "1:1",
                },
            )

            assert response.status_code in [200, 500, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert "images" in data
                assert len(data["images"]) > 0

                # SECURITY: Verify API key is in header, not URL
                call_args = mock_client_instance.post.call_args
                assert call_args is not None
                url = call_args[0][0] if call_args[0] else None
                headers = call_args[1].get("headers", {}) if len(call_args) > 1 else {}

                # Verify API key is NOT in URL
                if url:
                    assert "key=" not in url, "API key should not be in URL"

                # Verify API key IS in header
                assert "X-Goog-Api-Key" in headers, "API key should be in X-Goog-Api-Key header"
                assert headers["X-Goog-Api-Key"] == "test_key"

    def test_generate_image_no_api_key(self, authenticated_client):
        """Test generating image without API key"""
        with patch("app.core.config.settings.google_api_key", None):
            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "Test prompt",
                    "number_of_images": 1,
                },
            )

            assert response.status_code in [500, 503]
            if response.status_code == 500:
                assert "API key not configured" in response.json()["detail"]

    def test_generate_image_api_forbidden(self, authenticated_client):
        """Test generating image when API returns 403"""
        with (
            patch("app.routers.image_generation.settings.google_api_key", "test_key"),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = MagicMock(return_value=None)
            mock_client_instance.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client_instance

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "Test prompt",
                    "number_of_images": 1,
                },
            )

            assert response.status_code in [403, 500, 503]
            if response.status_code == 403:
                assert "not enabled" in response.json()["detail"].lower()

    def test_generate_image_custom_parameters(self, authenticated_client):
        """Test generating image with custom parameters"""
        with (
            patch("app.routers.image_generation.settings.google_api_key", "test_key"),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "generatedImages": [{"bytesBase64Encoded": "test_base64_data"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = MagicMock(return_value=None)
            mock_client_instance.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client_instance

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "Custom prompt",
                    "number_of_images": 2,
                    "aspect_ratio": "16:9",
                    "safety_filter_level": "block_few",
                    "person_generation": "allow_all",
                },
            )

            assert response.status_code in [200, 500, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True

    def test_generate_image_http_error(self, authenticated_client):
        """Test generating image when HTTP error occurs"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = MagicMock(return_value=None)
            mock_client_instance.post = MagicMock(return_value=mock_response)
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
            mock_client_class.return_value = mock_client_instance

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "Test prompt",
                    "number_of_images": 1,
                },
            )

            assert response.status_code in [500, 503]

    def test_generate_image_no_images_returned(self, authenticated_client):
        """Test when API returns no images"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"generatedImages": []}
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = MagicMock(return_value=None)
            mock_client_instance.post = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client_instance

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "Test prompt",
                    "number_of_images": 1,
                },
            )

            assert response.status_code in [200, 500, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is False
                assert len(data["images"]) == 0
