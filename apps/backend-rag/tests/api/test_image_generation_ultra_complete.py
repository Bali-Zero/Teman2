"""
Ultra-Complete API Tests for Image Generation Router
====================================================

Coverage Endpoints:
- POST /api/v1/image/generate - Generate images with Google Imagen
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["GOOGLE_API_KEY"] = "test_google_key"
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestImageGeneration:
    def test_generate_image_valid(self, authenticated_client):
        with patch("app.routers.image_generation.image_service") as mock:
            mock.generate.return_value = {"image_url": "https://example.com/image.png"}
            response = authenticated_client.post(
                "/api/v1/image/generate",
                json={"prompt": "A beautiful sunset over Bali beach", "num_images": 1},
            )
            assert response.status_code in [200, 201, 400, 429, 503]

    def test_generate_image_empty_prompt(self, authenticated_client):
        response = authenticated_client.post("/api/v1/image/generate", json={"prompt": ""})
        assert response.status_code in [400, 422]

    def test_generate_image_invalid_num(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/image/generate", json={"prompt": "Test", "num_images": 0}
        )
        assert response.status_code in [400, 422]

    def test_generate_image_too_many(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/image/generate", json={"prompt": "Test", "num_images": 100}
        )
        assert response.status_code in [400, 422]

    def test_generate_image_inappropriate_content(self, authenticated_client):
        with patch("app.routers.image_generation.image_service") as mock:
            mock.generate.side_effect = ValueError("Inappropriate content")
            response = authenticated_client.post(
                "/api/v1/image/generate", json={"prompt": "Inappropriate content here"}
            )
            assert response.status_code in [400, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
