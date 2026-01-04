"""
Unit tests for document parsers
Target: >95% coverage
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.parsers import (
    DocumentParseError,
    auto_detect_and_parse,
    extract_text_from_epub,
    extract_text_from_pdf,
    extract_text_from_txt,
    get_document_info,
)


class TestDocumentParseError:
    """Tests for DocumentParseError"""

    def test_exception(self):
        """Test exception creation"""
        error = DocumentParseError("Test error")
        assert str(error) == "Test error"


class TestExtractTextFromTxt:
    """Tests for extract_text_from_txt"""

    def test_extract_text_success(self):
        """Test successful text extraction"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content\nLine 2")
            temp_path = f.name

        try:
            result = extract_text_from_txt(temp_path)
            assert "Test content" in result
            assert "Line 2" in result
        finally:
            os.unlink(temp_path)

    def test_extract_text_empty(self):
        """Test extraction from empty file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("   \n\n   ")
            temp_path = f.name

        try:
            with pytest.raises(DocumentParseError):
                extract_text_from_txt(temp_path)
        finally:
            os.unlink(temp_path)

    def test_extract_text_not_found(self):
        """Test extraction from non-existent file"""
        with pytest.raises(DocumentParseError):
            extract_text_from_txt("/nonexistent/file.txt")


class TestExtractTextFromPdf:
    """Tests for extract_text_from_pdf"""

    @patch("core.parsers.PdfReader")
    def test_extract_text_success(self, mock_reader_class):
        """Test successful PDF extraction"""
        mock_reader = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"
        mock_reader.pages = [mock_page1, mock_page2]
        mock_reader_class.return_value = mock_reader

        result = extract_text_from_pdf("/test/file.pdf")
        assert "Page 1 content" in result
        assert "Page 2 content" in result

    @patch("core.parsers.PdfReader")
    def test_extract_text_empty(self, mock_reader_class):
        """Test extraction from empty PDF"""
        mock_reader = MagicMock()
        mock_reader.pages = []
        mock_reader_class.return_value = mock_reader

        with pytest.raises(DocumentParseError):
            extract_text_from_pdf("/test/file.pdf")

    @patch("core.parsers.PdfReader")
    def test_extract_text_page_error(self, mock_reader_class):
        """Test extraction with page error"""
        mock_reader = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.side_effect = Exception("Page error")
        mock_reader.pages = [mock_page1, mock_page2]
        mock_reader_class.return_value = mock_reader

        result = extract_text_from_pdf("/test/file.pdf")
        assert "Page 1 content" in result  # Should continue despite error

    @patch("core.parsers.PdfReader")
    def test_extract_text_reader_error(self, mock_reader_class):
        """Test extraction with reader error"""
        mock_reader_class.side_effect = Exception("Reader error")

        with pytest.raises(DocumentParseError):
            extract_text_from_pdf("/test/file.pdf")


class TestExtractTextFromEpub:
    """Tests for extract_text_from_epub"""

    @patch("core.parsers.epub.read_epub")
    @patch("core.parsers.BeautifulSoup")
    def test_extract_text_success(self, mock_soup, mock_read):
        """Test successful EPUB extraction"""
        import ebooklib

        mock_book = MagicMock()
        mock_item = MagicMock()
        mock_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_item.get_content.return_value = b"<html><body>Chapter content</body></html>"
        mock_book.get_items.return_value = [mock_item]
        mock_read.return_value = mock_book

        mock_soup_instance = MagicMock()
        mock_soup_instance.get_text.return_value = "Chapter content"
        mock_soup.return_value = mock_soup_instance

        result = extract_text_from_epub("/test/file.epub")
        assert "Chapter content" in result

    @patch("core.parsers.epub.read_epub")
    def test_extract_text_empty(self, mock_read):
        """Test extraction from empty EPUB"""

        mock_book = MagicMock()
        mock_book.get_items.return_value = []
        mock_read.return_value = mock_book

        with pytest.raises(DocumentParseError):
            extract_text_from_epub("/test/file.epub")


class TestAutoDetectAndParse:
    """Tests for auto_detect_and_parse"""

    def test_auto_detect_txt(self):
        """Test auto-detection of TXT file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            result = auto_detect_and_parse(temp_path)
            assert "Test content" in result
        finally:
            os.unlink(temp_path)

    def test_auto_detect_md(self):
        """Test auto-detection of MD file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Markdown")
            temp_path = f.name

        try:
            result = auto_detect_and_parse(temp_path)
            assert "Test Markdown" in result
        finally:
            os.unlink(temp_path)

    @patch("core.parsers.extract_text_from_pdf")
    def test_auto_detect_pdf(self, mock_extract):
        """Test auto-detection of PDF file"""
        mock_extract.return_value = "PDF content"
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = f.name

        try:
            result = auto_detect_and_parse(temp_path)
            assert result == "PDF content"
            mock_extract.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)

    def test_auto_detect_unsupported(self):
        """Test auto-detection of unsupported file type"""
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(DocumentParseError):
                auto_detect_and_parse(temp_path)
        finally:
            os.unlink(temp_path)

    def test_auto_detect_not_found(self):
        """Test auto-detection of non-existent file"""
        with pytest.raises(DocumentParseError):
            auto_detect_and_parse("/nonexistent/file.txt")


class TestGetDocumentInfo:
    """Tests for get_document_info"""

    def test_get_info_txt(self):
        """Test getting info for TXT file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            info = get_document_info(temp_path)
            assert info["file_type"] == ".txt"
            assert "file_name" in info
            assert "file_size_mb" in info
        finally:
            os.unlink(temp_path)

    @patch("core.parsers.PdfReader")
    def test_get_info_pdf(self, mock_reader_class):
        """Test getting info for PDF file"""
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        mock_reader.metadata = {"/Title": "Test PDF", "/Author": "Test Author"}
        mock_reader_class.return_value = mock_reader

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = f.name

        try:
            info = get_document_info(temp_path)
            assert info["file_type"] == ".pdf"
            assert info["pages"] == 2
            assert info["title"] == "Test PDF"
            assert info["author"] == "Test Author"
        finally:
            os.unlink(temp_path)

    @patch("core.parsers.epub.read_epub")
    def test_get_info_epub(self, mock_read):
        """Test getting info for EPUB file"""
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = [("Test Title",), ("Test Author",)]
        mock_read.return_value = mock_book

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            temp_path = f.name

        try:
            info = get_document_info(temp_path)
            assert info["file_type"] == ".epub"
        finally:
            os.unlink(temp_path)
