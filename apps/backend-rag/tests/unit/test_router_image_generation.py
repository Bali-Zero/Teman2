"""
Unit tests for Image Generation Router
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.image_generation import router

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create FastAPI test client"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ============================================================================
# Tests for generate endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_generate_image_success(client):
    """Test generate_image successful"""
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

    with (
        patch("app.routers.image_generation.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_class,
    ):
        mock_settings.google_ai_api_key = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        response = client.post(
            "/api/v1/image/generate",
            json={"prompt": "A beautiful sunset", "number_of_images": 1, "aspect_ratio": "1:1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) > 0


@pytest.mark.asyncio
async def test_generate_image_no_api_key(client):
    """Test generate_image without API key"""
    with patch("app.routers.image_generation.settings") as mock_settings:
        mock_settings.google_ai_api_key = None

        response = client.post("/api/v1/image/generate", json={"prompt": "Test"})

        # May return 400 (Bad Request) or 500 (Internal Server Error) depending on implementation
        assert response.status_code in [400, 500]
        assert (
            "not configured" in response.json()["detail"].lower()
            or "error" in response.json()["detail"].lower()
        )


@pytest.mark.asyncio
async def test_generate_image_api_error(client):
    """Test generate_image with API error"""
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid request"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
    )

    with (
        patch("app.routers.image_generation.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_class,
    ):
        mock_settings.google_ai_api_key = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        response = client.post("/api/v1/image/generate", json={"prompt": "Test"})

        assert response.status_code == 400  # Router raises HTTPException


@pytest.mark.asyncio
async def test_generate_image_with_parameters(client):
    """Test generate_image with all parameters"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "generatedImages": [
            {
                "bytesBase64Encoded": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            },
            {
                "bytesBase64Encoded": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch("app.routers.image_generation.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_class,
    ):
        mock_settings.google_ai_api_key = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        response = client.post(
            "/api/v1/image/generate",
            json={
                "prompt": "Test prompt",
                "number_of_images": 2,
                "aspect_ratio": "16:9",
                "safety_filter_level": "block_some",
                "person_generation": "allow_adult",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["images"]) == 2


@pytest.mark.asyncio
async def test_generate_image_exception(client):
    """Test generate_image handles exception"""
    with (
        patch("app.routers.image_generation.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_class,
    ):
        mock_settings.google_ai_api_key = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client_class.return_value = mock_client

        response = client.post("/api/v1/image/generate", json={"prompt": "Test"})

        # Router catches exception and raises HTTPException with 500
        assert response.status_code == 500
        assert (
            "error" in response.json()["detail"].lower()
            or "unexpected" in response.json()["detail"].lower()
        )
