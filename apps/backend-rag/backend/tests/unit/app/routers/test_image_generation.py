"""
Unit tests for image generation router
Target: >95% coverage

Updated 2026-04-10: Router redesigned to use Pollinations.ai (free, no API key).
Previous tests mocked google_imagen/httpx — replaced with Pollinations-based tests.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.image_generation import router


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
    """Tests for image generation router (Pollinations.ai backend)"""

    def test_generate_image_success(self, client):
        """Test generating image successfully — Pollinations returns URL list."""
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "test prompt", "number_of_images": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 2
        # Each URL should be a Pollinations URL
        for url in data["images"]:
            assert "pollinations.ai" in url

    def test_generate_image_single(self, client):
        """Test generating a single image (default)."""
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "a beautiful sunset"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 1

    def test_generate_image_no_api_key(self, client):
        """Pollinations requires no API key — always succeeds."""
        response = client.post("/api/v1/image/generate", json={"prompt": "test"})
        # Pollinations is free, no API key needed — should succeed (not 500)
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_generate_image_aspect_ratio_16_9(self, client):
        """Test 16:9 aspect ratio maps to correct dimensions."""
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "landscape", "aspect_ratio": "16:9"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=1024" in data["images"][0]
        assert "height=576" in data["images"][0]

    def test_generate_image_no_images(self, client):
        """Test generating zero images — empty prompt fails."""
        response = client.post("/api/v1/image/generate", json={"prompt": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert len(data["images"]) == 0

    def test_generate_image_empty_prompt(self, client):
        """Empty prompt returns success=False, no images."""
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "   "},  # whitespace-only
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_generate_image_prompt_encoded_in_url(self, client):
        """Prompt is URL-encoded in the returned Pollinations URL."""
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "beautiful Bali temple"},
        )
        assert response.status_code == 200
        data = response.json()
        # URL should contain the encoded prompt
        assert data["images"][0].startswith("https://image.pollinations.ai/prompt/")

    def test_generate_multiple_images_have_different_seeds(self, client):
        """Multiple images should have different seed params."""
        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "test", "number_of_images": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["images"]) == 3
        # Seeds should differ
        seeds = [url.split("seed=")[1].split("&")[0] for url in data["images"]]
        assert len(set(seeds)) == 3  # All unique
