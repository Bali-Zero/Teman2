"""
Unit tests for PDFVisionService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.multimodal.pdf_vision_service import PDFVisionService


@pytest.fixture
def mock_genai_client():
    """Mock GenAI client"""
    client = MagicMock()
    client.is_available = True
    client.generate_content = AsyncMock(return_value={"text": "Extracted table data"})
    return client


@pytest.fixture
def pdf_vision_service(mock_genai_client):
    """Create PDFVisionService instance"""
    with patch('app.core.config.settings') as mock_settings:
        mock_settings.google_api_key = "test_key"
        with patch('services.multimodal.pdf_vision_service.GENAI_AVAILABLE', True):
            with patch('services.multimodal.pdf_vision_service.GenAIClient', return_value=mock_genai_client):
                return PDFVisionService(api_key="test_key", ai_client=mock_genai_client)


class TestPDFVisionService:
    """Tests for PDFVisionService"""

    def test_init(self, pdf_vision_service):
        """Test initialization"""
        assert pdf_vision_service.api_key == "test_key"
        assert pdf_vision_service.model_name == "gemini-3-flash-preview"

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.google_api_key = None
            with patch('services.multimodal.pdf_vision_service.GENAI_AVAILABLE', False):
                service = PDFVisionService()
                assert service._available is False

    @pytest.mark.asyncio
    async def test_analyze_page_not_available(self):
        """Test analyzing page when service not available"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.google_api_key = None
            service = PDFVisionService()
            result = await service.analyze_page("test.pdf", 1)
            assert "not available" in result.lower() or "error" in result.lower()

    def test_render_page_to_image(self, pdf_vision_service):
        """Test rendering page to image"""
        with patch('fitz.open') as mock_fitz:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_pixmap = MagicMock()
            mock_pixmap.tobytes.return_value = b"test_image_data"
            mock_pixmap.width = 100
            mock_pixmap.height = 100
            mock_page.get_pixmap.return_value = mock_pixmap
            mock_doc.__getitem__.return_value = mock_page
            mock_doc.__len__ = lambda self: 1
            mock_fitz.return_value = mock_doc
            with patch('io.BytesIO') as mock_bytesio:
                mock_bytesio.return_value.getvalue.return_value = b"test_image_data"
                with patch('PIL.Image.open') as mock_image_open:
                    mock_image = MagicMock()
                    mock_image_open.return_value = mock_image
                    image = pdf_vision_service._render_page_to_image("test.pdf", 1)
                    assert image is not None

