"""
Unit tests for Vision RAG Service
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.vision_rag import MultiModalDocument, VisionRAGService, VisualElement


@pytest.fixture
def mock_genai():
    """Mock Google Generative AI"""
    with patch("services.rag.vision_rag.genai") as mock:
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock()
        mock.GenerativeModel.return_value = mock_model
        yield mock


@pytest.fixture
def service(mock_genai):
    return VisionRAGService()


@pytest.mark.asyncio
async def test_process_pdf_no_pymupdf(service):
    """Test handling when fitz/pymupdf is missing"""
    with patch.dict(sys.modules, {"fitz": None}):
        doc = await service.process_pdf("dummy.pdf")
        assert isinstance(doc, MultiModalDocument)
        assert doc.text_content == ""
        assert doc.visual_elements == []


@pytest.mark.asyncio
async def test_process_pdf_success(service):
    """Test successful PDF processing"""
    # Mock fitz
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Page text"
    mock_page.get_images.return_value = [(1, 0, 0, 0)]  # One dummy image
    mock_doc.__iter__.return_value = [mock_page]
    mock_doc.extract_image.return_value = {"image": b"fake_image_bytes"}

    # Mock Visual Analysis
    with patch.object(service, "_analyze_visual_element", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = VisualElement(
            element_type="chart",
            page_number=1,
            bounding_box=(0, 0, 100, 100),
            image_data=b"bytes",
            extracted_text="Chart data",
            description="A chart",
        )

        # Patch fitz module
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            # Re-import or reload might be needed if service already imported 'fitz' as None?
            # The service does "import fitz" inside the method.
            # So patching sys.modules should work if the method re-imports or if it was None before.

            result = await service.process_pdf("test.pdf")

            assert len(result.visual_elements) >= 1
            assert result.visual_elements[0].element_type == "chart"
            assert "Page text" in result.text_content


@pytest.mark.asyncio
async def test_query_with_vision(service):
    """Test querying with vision context"""
    documents = [
        MultiModalDocument(
            doc_id="doc1",
            text_content="Text content",
            visual_elements=[
                VisualElement(
                    element_type="chart",
                    page_number=1,
                    bounding_box=(0, 0, 0, 0),
                    image_data=b"img",
                    extracted_text="Graph data",
                    description="Sales graph",
                )
            ],
            metadata={},
        )
    ]

    # Mock response
    mock_response = MagicMock()
    mock_response.text = "Analysis based on chart"
    service.vision_model.generate_content_async.return_value = mock_response

    # Mock Image.open to avoid actual image processing errors on dummy bytes
    with patch("services.rag.vision_rag.Image.open"):
        response = await service.query_with_vision("Analyze sales", documents)

        assert response["answer"] == "Analysis based on chart"
        assert len(response["visuals_used"]) == 1
        assert response["visuals_used"][0]["type"] == "chart"
