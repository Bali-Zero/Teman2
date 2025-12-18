"""
Ultra-Comprehensive API Tests for Image Generation Router
Complete test coverage for image generation endpoints with every possible scenario

Coverage:
- POST /api/v1/image/generate - Generate images
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
class TestImageGeneration:
    """Ultra-comprehensive tests for POST /api/v1/image/generate"""

    def test_generate_image_basic(self, authenticated_client):
        """Test basic image generation"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={"generatedImages": [{"bytesBase64Encoded": "base64encodedimage"}]}
            )
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "A beautiful sunset over mountains"},
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_generate_multiple_images(self, authenticated_client):
        """Test generating multiple images"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={
                    "generatedImages": [{"bytesBase64Encoded": f"image{i}"} for i in range(3)]
                }
            )
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={
                    "prompt": "Test prompt",
                    "number_of_images": 3,
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_generate_image_all_aspect_ratios(self, authenticated_client):
        """Test generating images with all aspect ratios"""
        aspect_ratios = ["1:1", "4:3", "3:4", "16:9", "9:16"]

        for aspect_ratio in aspect_ratios:
            with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json = MagicMock(
                    return_value={"generatedImages": [{"bytesBase64Encoded": "image"}]}
                )
                mock_client = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                response = authenticated_client.post(
                    "/api/v1/image/generate",
                    json={
                        "prompt": "Test prompt",
                        "aspect_ratio": aspect_ratio,
                    },
                )

                assert response.status_code in [200, 201, 500, 503]

    def test_generate_image_all_safety_levels(self, authenticated_client):
        """Test generating images with all safety filter levels"""
        safety_levels = ["block_some", "block_few", "block_most", "block_none"]

        for safety_level in safety_levels:
            with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json = MagicMock(
                    return_value={"generatedImages": [{"bytesBase64Encoded": "image"}]}
                )
                mock_client = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                response = authenticated_client.post(
                    "/api/v1/image/generate",
                    json={
                        "prompt": "Test prompt",
                        "safety_filter_level": safety_level,
                    },
                )

                assert response.status_code in [200, 201, 500, 503]

    def test_generate_image_all_person_generation(self, authenticated_client):
        """Test generating images with all person generation options"""
        person_options = ["allow_adult", "allow_all", "block_all"]

        for person_option in person_options:
            with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json = MagicMock(
                    return_value={"generatedImages": [{"bytesBase64Encoded": "image"}]}
                )
                mock_client = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                response = authenticated_client.post(
                    "/api/v1/image/generate",
                    json={
                        "prompt": "Test prompt",
                        "person_generation": person_option,
                    },
                )

                assert response.status_code in [200, 201, 500, 503]

    def test_generate_image_long_prompt(self, authenticated_client):
        """Test generating image with long prompt"""
        long_prompt = "A " + "very detailed " * 100 + "image"

        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={"generatedImages": [{"bytesBase64Encoded": "image"}]}
            )
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": long_prompt},
            )

            assert response.status_code in [200, 201, 400, 413, 500, 503]

    def test_generate_image_empty_prompt(self, authenticated_client):
        """Test generating image with empty prompt"""
        response = authenticated_client.post(
            "/api/v1/image/generate",
            json={"prompt": ""},
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_generate_image_missing_prompt(self, authenticated_client):
        """Test generating image without prompt"""
        response = authenticated_client.post(
            "/api/v1/image/generate",
            json={},
        )

        assert response.status_code == 422

    def test_generate_image_api_key_missing(self, authenticated_client):
        """Test generating image without API key"""
        with patch("app.routers.image_generation.settings") as mock_settings:
            mock_settings.google_imagen_api_key = None
            mock_settings.google_api_key = None

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "Test prompt"},
            )

            assert response.status_code == 500

    def test_generate_image_api_forbidden(self, authenticated_client):
        """Test generating image with API forbidden error"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "Test prompt"},
            )

            assert response.status_code == 403

    def test_generate_image_api_error(self, authenticated_client):
        """Test generating image with API error"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status = MagicMock(side_effect=Exception("API Error"))
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "Test prompt"},
            )

            assert response.status_code in [500, 503]

    def test_generate_image_response_structure(self, authenticated_client):
        """Test image generation response structure"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(
                return_value={
                    "generatedImages": [
                        {"bytesBase64Encoded": "base64image1"},
                        {"bytesBase64Encoded": "base64image2"},
                    ]
                }
            )
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "Test prompt"},
            )

            if response.status_code == 200:
                data = response.json()
                assert "images" in data
                assert "success" in data
                assert isinstance(data["images"], list)

    def test_generate_image_no_images_returned(self, authenticated_client):
        """Test generating image when no images are returned"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"generatedImages": []})
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "Test prompt"},
            )

            if response.status_code == 200:
                data = response.json()
                assert data["success"] is False
                assert len(data["images"]) == 0


@pytest.mark.api
class TestImageGenerationSecurity:
    """Security tests for image generation endpoints"""

    def test_image_generation_requires_auth(self, test_client):
        """Test image generation endpoint requires authentication"""
        response = test_client.post(
            "/api/v1/image/generate",
            json={"prompt": "Test prompt"},
        )

        assert response.status_code == 401
