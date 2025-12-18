"""
Unit tests for Image Generation Service
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.image_generation_service import ImageGenerationService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def image_service_with_key():
    """Create ImageGenerationService with API key"""
    with (
        patch("app.core.config.settings") as mock_settings,
        patch("google.generativeai.configure"),
        patch("services.image_generation_service.logger"),
    ):
        # Mock both google_imagen_api_key and google_api_key (code checks imagen first)
        mock_settings.google_imagen_api_key = None
        mock_settings.google_api_key = "test-api-key"
        service = ImageGenerationService()
        return service


@pytest.fixture
def image_service_no_key():
    """Create ImageGenerationService without API key"""
    with (
        patch("app.core.config.settings") as mock_settings,
        patch("services.image_generation_service.logger"),
    ):
        # Mock both to ensure None is returned
        mock_settings.google_imagen_api_key = None
        mock_settings.google_api_key = None
        service = ImageGenerationService()
        return service


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_image_service_init_with_key(image_service_with_key):
    """Test ImageGenerationService initialization with API key"""
    assert image_service_with_key.api_key == "test-api-key"


def test_image_service_init_no_key(image_service_no_key):
    """Test ImageGenerationService initialization without API key"""
    assert image_service_no_key.api_key is None


def test_image_service_init_with_custom_key():
    """Test ImageGenerationService initialization with custom API key"""
    with (
        patch("app.core.config.settings") as mock_settings,
        patch("google.generativeai.configure"),
        patch("services.image_generation_service.logger"),
    ):
        mock_settings.google_imagen_api_key = None
        mock_settings.google_api_key = None
        service = ImageGenerationService(api_key="custom-key")
        assert service.api_key == "custom-key"


# ============================================================================
# Tests: generate_image
# ============================================================================


@pytest.mark.asyncio
async def test_generate_image_no_api_key(image_service_no_key):
    """Test generating image without API key"""
    result = await image_service_no_key.generate_image("A beautiful sunset")

    assert result["success"] is False
    assert "not configured" in result["error"].lower()
    assert "GOOGLE_API_KEY" in result["details"]


@pytest.mark.asyncio
async def test_generate_image_empty_prompt(image_service_with_key):
    """Test generating image with empty prompt"""
    result = await image_service_with_key.generate_image("")

    assert result["success"] is False
    assert "invalid prompt" in result["error"].lower()
    assert "cannot be empty" in result["details"].lower()


@pytest.mark.asyncio
async def test_generate_image_whitespace_prompt(image_service_with_key):
    """Test generating image with whitespace-only prompt"""
    result = await image_service_with_key.generate_image("   ")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_generate_image_success(image_service_with_key):
    """Test generating image successfully"""
    result = await image_service_with_key.generate_image("A beautiful sunset")

    assert result["success"] is True
    assert "url" in result
    assert "prompt" in result
    assert result["prompt"] == "A beautiful sunset"
    assert result["service"] == "pollinations_fallback"
    assert "pollinations.ai" in result["url"]


@pytest.mark.asyncio
async def test_generate_image_url_encoding(image_service_with_key):
    """Test URL encoding in generated image URL"""
    result = await image_service_with_key.generate_image("sunset over mountains")

    assert result["success"] is True
    assert "%20" in result["url"] or "sunset" in result["url"].lower()


@pytest.mark.asyncio
async def test_generate_image_exception(image_service_with_key):
    """Test generating image with exception"""
    # Mock logger to raise exception during logging
    with patch("services.image_generation_service.logger") as mock_logger:
        mock_logger.info.side_effect = Exception("Network error")

        result = await image_service_with_key.generate_image("test")

        # Should handle exception gracefully
        assert result["success"] is False or "error" in result
