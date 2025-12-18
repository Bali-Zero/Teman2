"""
Unit tests for Document Parsers
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.parsers import (
    DocumentParseError,
    auto_detect_and_parse,
    extract_text_from_epub,
    extract_text_from_pdf,
    get_document_info,
)


@pytest.fixture
def sample_pdf_content():
    """Create a temporary PDF file for testing"""
    # Note: In real tests, you'd use a proper PDF file
    # This is a mock for testing
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 0\ntrailer\n<<\n/Root 1 0 R\n>>\nstartxref\n0\n%%EOF"


# ============================================================================
# Tests for extract_text_from_pdf
# ============================================================================


def test_extract_text_from_pdf_success():
    """Test successful PDF extraction"""
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text = MagicMock(return_value="Test PDF content")
    mock_reader.pages = [mock_page]

    with patch("core.parsers.PdfReader", return_value=mock_reader):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf content")
            tmp_path = tmp.name

        try:
            text = extract_text_from_pdf(tmp_path)
            assert "Test PDF content" in text
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def test_extract_text_from_pdf_file_not_found():
    """Test PDF extraction with non-existent file"""
    with pytest.raises(DocumentParseError):
        extract_text_from_pdf("/nonexistent/file.pdf")


def test_extract_text_from_pdf_empty_text():
    """Test PDF extraction with empty text"""
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text = MagicMock(return_value="")
    mock_reader.pages = [mock_page]

    with patch("core.parsers.PdfReader", return_value=mock_reader):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            with pytest.raises(DocumentParseError, match="No text extracted"):
                extract_text_from_pdf(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def test_extract_text_from_pdf_page_error():
    """Test PDF extraction handles page errors gracefully"""
    mock_reader = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.extract_text = MagicMock(return_value="Page 1")
    mock_page2 = MagicMock()
    mock_page2.extract_text = MagicMock(side_effect=Exception("Page error"))
    mock_reader.pages = [mock_page1, mock_page2]

    with patch("core.parsers.PdfReader", return_value=mock_reader):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            text = extract_text_from_pdf(tmp_path)
            assert "Page 1" in text
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ============================================================================
# Tests for extract_text_from_epub
# ============================================================================


def test_extract_text_from_epub_success():
    """Test successful EPUB extraction"""
    import ebooklib

    mock_book = MagicMock()
    mock_item = MagicMock()
    # Use the actual ITEM_DOCUMENT constant value (which is 9)
    mock_item.get_type = MagicMock(return_value=ebooklib.ITEM_DOCUMENT)
    mock_item.get_content = MagicMock(return_value=b"<html><body>Test EPUB content</body></html>")
    mock_book.get_items = MagicMock(return_value=[mock_item])

    with patch("core.parsers.epub.read_epub", return_value=mock_book):
        with patch("core.parsers.BeautifulSoup") as mock_soup:
            mock_soup_instance = MagicMock()
            mock_soup_instance.get_text = MagicMock(return_value="Test EPUB content")
            mock_soup.return_value = mock_soup_instance

            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                tmp.write(b"fake epub")
                tmp_path = tmp.name

            try:
                text = extract_text_from_epub(tmp_path)
                assert "Test EPUB content" in text
            finally:
                Path(tmp_path).unlink(missing_ok=True)


def test_extract_text_from_epub_empty_text():
    """Test EPUB extraction with empty text"""
    mock_book = MagicMock()
    mock_book.get_items = MagicMock(return_value=[])

    with patch("core.parsers.epub.read_epub", return_value=mock_book):
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            tmp.write(b"fake epub")
            tmp_path = tmp.name

        try:
            with pytest.raises(DocumentParseError, match="No text extracted"):
                extract_text_from_epub(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ============================================================================
# Tests for auto_detect_and_parse
# ============================================================================


def test_auto_detect_and_parse_pdf():
    """Test auto-detect and parse PDF"""
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text = MagicMock(return_value="PDF content")
    mock_reader.pages = [mock_page]

    with patch("core.parsers.PdfReader", return_value=mock_reader):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            text = auto_detect_and_parse(tmp_path)
            assert "PDF content" in text
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def test_auto_detect_and_parse_epub():
    """Test auto-detect and parse EPUB"""
    mock_book = MagicMock()
    mock_book.get_items = MagicMock(return_value=[])

    with patch("core.parsers.epub.read_epub", return_value=mock_book):
        with patch("core.parsers.extract_text_from_epub", return_value="EPUB content"):
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                tmp.write(b"fake epub")
                tmp_path = tmp.name

            try:
                text = auto_detect_and_parse(tmp_path)
                assert text == "EPUB content"
            finally:
                Path(tmp_path).unlink(missing_ok=True)


def test_auto_detect_and_parse_unsupported_format():
    """Test auto-detect with unsupported format"""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(b"fake docx content")
        tmp_path = tmp.name

    try:
        with pytest.raises(DocumentParseError, match="Unsupported file type"):
            auto_detect_and_parse(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_auto_detect_and_parse_file_not_found():
    """Test auto-detect with non-existent file"""
    with pytest.raises(DocumentParseError, match="File not found"):
        auto_detect_and_parse("/nonexistent/file.pdf")


# ============================================================================
# Tests for get_document_info
# ============================================================================


def test_get_document_info_pdf():
    """Test getting document info for PDF"""
    mock_reader = MagicMock()
    mock_reader.pages = [MagicMock(), MagicMock()]
    mock_reader.metadata = {"/Title": "Test PDF", "/Author": "Test Author"}

    with patch("core.parsers.PdfReader", return_value=mock_reader):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            info = get_document_info(tmp_path)
            assert info["file_type"] == ".pdf"
            assert info["pages"] == 2
            assert info["title"] == "Test PDF"
            assert info["author"] == "Test Author"
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def test_get_document_info_epub():
    """Test getting document info for EPUB"""
    mock_book = MagicMock()
    mock_book.get_metadata = MagicMock(
        side_effect=lambda ns, key: {
            ("DC", "title"): [("Test EPUB",)],
            ("DC", "creator"): [("Test Author",)],
        }.get((ns, key), [])
    )

    with patch("core.parsers.epub.read_epub", return_value=mock_book):
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            tmp.write(b"fake epub")
            tmp_path = tmp.name

        try:
            info = get_document_info(tmp_path)
            assert info["file_type"] == ".epub"
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def test_get_document_info_handles_errors():
    """Test get_document_info handles errors gracefully"""
    with patch("core.parsers.PdfReader", side_effect=Exception("Read error")):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"fake pdf")
            tmp_path = tmp.name

        try:
            info = get_document_info(tmp_path)
            # Should still return basic info even if metadata extraction fails
            assert info["file_type"] == ".pdf"
            assert "file_name" in info
        finally:
            Path(tmp_path).unlink(missing_ok=True)
