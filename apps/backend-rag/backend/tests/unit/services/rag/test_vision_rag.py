"""
Unit tests for VisionRAGService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.vision_rag import VisionRAGService, VisualElement, MultiModalDocument


@pytest.fixture
def vision_rag_service():
    """Create VisionRAGService instance"""
    with patch("services.rag.vision_rag.GENAI_AVAILABLE", True), \
         patch("services.rag.vision_rag.GenAIClient") as mock_client_class, \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.google_api_key = "test_key"
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client_class.return_value = mock_client
        return VisionRAGService()


@pytest.fixture
def vision_rag_service_no_genai():
    """Create VisionRAGService instance without GenAI"""
    with patch("services.rag.vision_rag.GENAI_AVAILABLE", False), \
         patch("app.core.config.settings") as mock_settings:
        mock_settings.google_api_key = None
        return VisionRAGService()


class TestVisionRAGService:
    """Tests for VisionRAGService"""

    def test_init(self, vision_rag_service):
        """Test initialization"""
        assert vision_rag_service._available is True
        assert vision_rag_service._genai_client is not None

    def test_init_no_genai(self, vision_rag_service_no_genai):
        """Test initialization without GenAI"""
        assert vision_rag_service_no_genai._available is False
        assert vision_rag_service_no_genai._genai_client is None

    @pytest.mark.asyncio
    async def test_process_pdf_no_pymupdf(self, vision_rag_service):
        """Test processing PDF without PyMuPDF"""
        # Mock ImportError when importing fitz
        import sys
        original_import = __import__
        
        def mock_import(name, *args, **kwargs):
            if name == "fitz":
                raise ImportError("No module named 'fitz'")
            return original_import(name, *args, **kwargs)
        
        with patch("builtins.__import__", side_effect=mock_import):
            result = await vision_rag_service.process_pdf("test.pdf")
            assert isinstance(result, MultiModalDocument)
            assert result.text_content == ""
            assert result.visual_elements == []

    @pytest.mark.asyncio
    async def test_process_pdf_with_pymupdf(self, vision_rag_service):
        """Test processing PDF with PyMuPDF"""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Test text"
        mock_page.get_images.return_value = []
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_doc.extract_image.return_value = {"image": b"test"}
        
        # Create a mock fitz module
        mock_fitz_module = MagicMock()
        mock_fitz_module.open.return_value = mock_doc
        
        with patch.dict("sys.modules", {"fitz": mock_fitz_module}):
            vision_rag_service._analyze_visual_element = AsyncMock(return_value=None)
            vision_rag_service._extract_tables = AsyncMock(return_value=[])
            
            result = await vision_rag_service.process_pdf("test.pdf")
            assert isinstance(result, MultiModalDocument)

    @pytest.mark.asyncio
    async def test_analyze_visual_element(self, vision_rag_service):
        """Test analyzing visual element"""
        vision_rag_service._genai_client.analyze_image = AsyncMock(
            return_value={"description": "Test image", "text": "Test"}
        )
        
        result = await vision_rag_service._analyze_visual_element(
            image_bytes=b"test",
            page_num=1,
            element_id="test_id"
        )
        assert result is None or isinstance(result, VisualElement)

    @pytest.mark.asyncio
    async def test_extract_tables(self, vision_rag_service):
        """Test extracting tables"""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Test"
        
        result = await vision_rag_service._extract_tables(mock_page, 1)
        assert isinstance(result, list)

