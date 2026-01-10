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

from backend.services.multimodal.pdf_vision_service import PDFVisionService


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
    with patch("backend.app.core.config.settings") as mock_settings:
        mock_settings.google_api_key = "test_key"
        with (
            patch("backend.services.multimodal.pdf_vision_service.GENAI_AVAILABLE", True),
            patch(
                "backend.services.multimodal.pdf_vision_service.GenAIClient", return_value=mock_genai_client
            ),
        ):
            return PDFVisionService(api_key="test_key", ai_client=mock_genai_client)


class TestPDFVisionService:
    """Tests for PDFVisionService"""

    def test_init(self, pdf_vision_service):
        """Test initialization"""
        assert pdf_vision_service.api_key == "test_key"
        assert pdf_vision_service.model_name == "gemini-3-flash-preview"

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.google_api_key = None
            with patch("backend.services.multimodal.pdf_vision_service.GENAI_AVAILABLE", False):
                service = PDFVisionService()
                assert service._available is False

    @pytest.mark.asyncio
    async def test_analyze_page_not_available(self):
        """Test analyzing page when service not available"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.google_api_key = None
            service = PDFVisionService()
            result = await service.analyze_page("test.pdf", 1)
            assert "not available" in result.lower() or "error" in result.lower()

    def test_render_page_to_image(self, pdf_vision_service):
        """Test rendering page to image"""
        with patch("fitz.open") as mock_fitz:
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
            with patch("io.BytesIO") as mock_bytesio:
                mock_bytesio.return_value.getvalue.return_value = b"test_image_data"
                with patch("PIL.Image.open") as mock_image_open:
                    mock_image = MagicMock()
                    mock_image_open.return_value = mock_image
                    image = pdf_vision_service._render_page_to_image("test.pdf", 1)
                    assert image is not None

    def test_render_page_to_image_invalid_page(self, pdf_vision_service):
        """Test rendering invalid page number"""
        with patch("fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.__len__ = lambda self: 5  # 5 pages
            mock_fitz.return_value = mock_doc

            with pytest.raises(ValueError, match="Invalid page number"):
                pdf_vision_service._render_page_to_image("test.pdf", 10)  # Page 10 doesn't exist

    @pytest.mark.asyncio
    async def test_analyze_page_with_drive_file(self, pdf_vision_service):
        """Test analyzing page with Drive file"""
        with (
            patch("backend.services.oracle.smart_oracle.download_pdf_from_drive") as mock_download,
            patch.object(pdf_vision_service, "_render_page_to_image") as mock_render,
            patch("os.path.exists") as mock_exists,
            patch("os.remove") as mock_remove,
        ):
            mock_download.return_value = "/tmp/downloaded.pdf"
            mock_exists.return_value = True
            mock_image = MagicMock()
            mock_render.return_value = mock_image
            mock_image.save = MagicMock()

            result = await pdf_vision_service.analyze_page("drive_file_id", 1, is_drive_file=True)
            assert "error" not in result.lower() or "extracted" in result.lower()
            mock_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_page_drive_download_failed(self, pdf_vision_service):
        """Test analyzing page when Drive download fails"""
        with patch("backend.services.oracle.smart_oracle.download_pdf_from_drive") as mock_download:
            mock_download.return_value = None

            result = await pdf_vision_service.analyze_page("drive_file_id", 1, is_drive_file=True)
            assert "error" in result.lower() or "could not download" in result.lower()

    @pytest.mark.asyncio
    async def test_extract_kbli_table(self, pdf_vision_service):
        """Test extracting KBLI table"""
        with (
            patch("backend.services.oracle.smart_oracle.download_pdf_from_drive") as mock_download,
            patch.object(pdf_vision_service, "analyze_page") as mock_analyze,
            patch("os.path.exists") as mock_exists,
            patch("os.remove") as mock_remove,
        ):
            mock_download.return_value = "/tmp/kbli.pdf"
            mock_exists.return_value = True
            mock_analyze.return_value = (
                '[{"code": "12345", "title": "Test", "description": "Test desc"}]'
            )

            result = await pdf_vision_service.extract_kbli_table(
                "kbli_id", (1, 3), is_drive_file=True
            )
            assert "Page 1" in result or "Page 2" in result or "Page 3" in result
            mock_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_kbli_table_download_failed(self, pdf_vision_service):
        """Test extracting KBLI table when download fails"""
        with patch("backend.services.oracle.smart_oracle.download_pdf_from_drive") as mock_download:
            mock_download.return_value = None

            result = await pdf_vision_service.extract_kbli_table(
                "kbli_id", (1, 3), is_drive_file=True
            )
            assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_extract_text_with_ai_client(self, pdf_vision_service):
        """Test extracting text with AI client"""
        mock_ai = AsyncMock()
        mock_ai.extract_pdf_text = AsyncMock(return_value="Extracted text")
        pdf_vision_service.ai_client = mock_ai

        result = await pdf_vision_service.extract_text(b"pdf_data")
        assert result == "Extracted text"

    @pytest.mark.asyncio
    async def test_extract_text_fallback(self, pdf_vision_service):
        """Test extracting text with PyMuPDF fallback"""
        pdf_vision_service.ai_client = None

        with patch("fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Page text"
            mock_doc.__iter__ = lambda self: iter([mock_page])
            mock_doc.close = MagicMock()
            mock_fitz.return_value = mock_doc

            result = await pdf_vision_service.extract_text(b"pdf_data")
            assert "Page text" in result

    @pytest.mark.asyncio
    async def test_extract_text_error(self, pdf_vision_service):
        """Test extracting text with error"""
        pdf_vision_service.ai_client = None

        with patch("fitz.open") as mock_fitz:
            mock_fitz.side_effect = Exception("PDF error")

            result = await pdf_vision_service.extract_text(b"pdf_data")
            assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_analyze_vision_with_ai_client(self, pdf_vision_service):
        """Test analyzing vision with AI client"""
        mock_ai = AsyncMock()
        mock_ai.analyze_pdf_vision = AsyncMock(
            return_value={"text": "Analyzed text", "structure": {"pages": 1, "sections": 2}}
        )
        pdf_vision_service.ai_client = mock_ai

        result = await pdf_vision_service.analyze_vision(b"pdf_data")
        assert "text" in result
        assert "structure" in result

    @pytest.mark.asyncio
    async def test_analyze_vision_fallback(self, pdf_vision_service):
        """Test analyzing vision with fallback"""
        pdf_vision_service.ai_client = None

        with patch.object(pdf_vision_service, "extract_text") as mock_extract:
            mock_extract.return_value = "Extracted text"

            result = await pdf_vision_service.analyze_vision(b"pdf_data")
            assert result["text"] == "Extracted text"
            assert "structure" in result
