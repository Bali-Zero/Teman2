"""
Unit tests for ImageGenerationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.image_generation_service import ImageGenerationService


class TestImageGenerationService:
    """Tests for ImageGenerationService"""

    def test_init_with_api_key(self):
        """Test initialization with API key"""
        service = ImageGenerationService(api_key="test_key")
        assert service.api_key == "test_key"

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_imagen_api_key = None
            mock_settings.google_api_key = None
            service = ImageGenerationService()
            assert service.api_key is None

    def test_init_with_settings_api_key(self):
        """Test initialization with settings API key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_imagen_api_key = "imagen_key"
            service = ImageGenerationService()
            assert service.api_key == "imagen_key"

    def test_init_fallback_to_google_api_key(self):
        """Test initialization with fallback to google_api_key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_imagen_api_key = None
            mock_settings.google_api_key = "google_key"
            service = ImageGenerationService()
            assert service.api_key == "google_key"

    @pytest.mark.asyncio
    async def test_generate_image_no_api_key(self):
        """Test generating image without API key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.google_imagen_api_key = None
            mock_settings.google_api_key = None
            service = ImageGenerationService(api_key=None)
            result = await service.generate_image("test prompt")
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_image_empty_prompt(self):
        """Test generating image with empty prompt"""
        service = ImageGenerationService(api_key="test_key")
        result = await service.generate_image("")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_image_whitespace_prompt(self):
        """Test generating image with whitespace-only prompt"""
        service = ImageGenerationService(api_key="test_key")
        result = await service.generate_image("   ")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_image_success(self):
        """Test successful image generation"""
        service = ImageGenerationService(api_key="test_key")
        result = await service.generate_image("test prompt")
        assert result["success"] is True
        assert "url" in result
        assert result["service"] == "pollinations_fallback"
