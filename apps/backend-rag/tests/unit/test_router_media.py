"""
Unit tests for Media Router
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.media import router

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


@pytest.fixture
def mock_image_generation_service():
    """Mock ImageGenerationService"""
    service = AsyncMock()
    service.generate_image = AsyncMock(
        return_value={
            "success": True,
            "url": "https://example.com/image.png",
            "prompt": "Test prompt",
            "service": "test_service",
        }
    )
    return service


# ============================================================================
# Tests for generate_image endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_generate_image_success(client, mock_image_generation_service):
    """Test generate_image successful"""
    with patch(
        "app.routers.media.ImageGenerationService", return_value=mock_image_generation_service
    ):
        response = client.post("/media/generate-image", json={"prompt": "A beautiful sunset"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "url" in data
        assert data["prompt"] == "Test prompt"


@pytest.mark.asyncio
async def test_generate_image_not_configured(client, mock_image_generation_service):
    """Test generate_image when service not configured"""
    mock_image_generation_service.generate_image.return_value = {
        "success": False,
        "error": "Service not configured",
    }

    with patch(
        "app.routers.media.ImageGenerationService", return_value=mock_image_generation_service
    ):
        response = client.post("/media/generate-image", json={"prompt": "Test"})

        assert response.status_code == 503


@pytest.mark.asyncio
async def test_generate_image_invalid_prompt(client, mock_image_generation_service):
    """Test generate_image with invalid prompt"""
    mock_image_generation_service.generate_image.return_value = {
        "success": False,
        "error": "Invalid prompt",
    }

    with patch(
        "app.routers.media.ImageGenerationService", return_value=mock_image_generation_service
    ):
        response = client.post("/media/generate-image", json={"prompt": ""})

        assert response.status_code == 400


@pytest.mark.asyncio
async def test_generate_image_generic_error(client, mock_image_generation_service):
    """Test generate_image with generic error"""
    mock_image_generation_service.generate_image.return_value = {
        "success": False,
        "error": "Generic error",
    }

    with patch(
        "app.routers.media.ImageGenerationService", return_value=mock_image_generation_service
    ):
        response = client.post("/media/generate-image", json={"prompt": "Test"})

        assert response.status_code == 500


@pytest.mark.asyncio
async def test_generate_image_exception(client, mock_image_generation_service):
    """Test generate_image handles exception"""
    mock_image_generation_service.generate_image.side_effect = Exception("Service error")

    with patch(
        "app.routers.media.ImageGenerationService", return_value=mock_image_generation_service
    ):
        response = client.post("/media/generate-image", json={"prompt": "Test"})

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_generate_image_missing_prompt(client):
    """Test generate_image with missing prompt"""
    response = client.post("/media/generate-image", json={})

    assert response.status_code == 422  # Validation error
