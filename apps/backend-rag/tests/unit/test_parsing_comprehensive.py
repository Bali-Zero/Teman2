"""
Comprehensive Tests for Document Parsing Logic
Tests PDF, DOCX, and other file format parsing with error handling
"""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.parsers import (
    DocumentParseError,
    auto_detect_and_parse,
    extract_text_from_docx,
    extract_text_from_epub,
    extract_text_from_pdf,
    extract_text_from_txt,
    get_document_info,
)


class TestPDFParsing:
    """Test PDF parsing functionality"""

    def test_extract_text_from_pdf_success(self):
        """Test successful PDF text extraction"""
        with patch("backend.core.parsers.PdfReader") as mock_reader_class:
            # Mock PDF reader with pages
            mock_reader = MagicMock()
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "This is page 1 content"
            mock_page2 = MagicMock()
            mock_page2.extract_text.return_value = "This is page 2 content"

            mock_reader.pages = [mock_page1, mock_page2]
            mock_reader_class.return_value = mock_reader

            result = extract_text_from_pdf("test.pdf")

            assert "This is page 1 content" in result
            assert "This is page 2 content" in result
            assert "\n\n" in result  # Pages should be separated

    def test_extract_text_from_pdf_empty_content(self):
        """Test PDF with no extractable text"""
        with patch("backend.core.parsers.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""
            mock_reader.pages = [mock_page]
            mock_reader_class.return_value = mock_reader

            with pytest.raises(DocumentParseError, match="No text extracted"):
                extract_text_from_pdf("empty.pdf")

    def test_extract_text_from_pdf_page_error(self):
        """Test PDF with page extraction error"""
        with patch("backend.core.parsers.PdfReader") as mock_reader_class:
            mock_reader = MagicMock()
            mock_page1 = MagicMock()
            mock_page1.extract_text.return_value = "Valid content"
            mock_page2 = MagicMock()
            mock_page2.extract_text.side_effect = Exception("Page error")
            mock_reader.pages = [mock_page1, mock_page2]
            mock_reader_class.return_value = mock_reader

            # Should continue despite page error
            result = extract_text_from_pdf("partial.pdf")
            assert "Valid content" in result

    def test_extract_text_from_pdf_file_error(self):
        """Test PDF file reading error"""
        with patch("backend.core.parsers.PdfReader", side_effect=Exception("File error")):
            with pytest.raises(DocumentParseError, match="Failed to parse PDF"):
                extract_text_from_pdf("corrupt.pdf")


class TestDOCXParsing:
    """Test DOCX parsing functionality"""

    def test_extract_text_from_docx_success(self):
        """Test successful DOCX text extraction"""
        with patch("backend.core.parsers.Document") as mock_document_class:
            # Mock DOCX document
            mock_doc = MagicMock()

            # Mock paragraphs
            mock_para1 = MagicMock()
            mock_para1.text = "First paragraph content"
            mock_para2 = MagicMock()
            mock_para2.text = "Second paragraph content"
            mock_para3 = MagicMock()
            mock_para3.text = ""  # Empty paragraph should be ignored

            mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]

            # Mock empty tables
            mock_doc.tables = []

            mock_document_class.return_value = mock_doc

            result = extract_text_from_docx("test.docx")

            assert "First paragraph content" in result
            assert "Second paragraph content" in result
            assert "" not in result  # Empty paragraphs should be ignored

    def test_extract_text_from_docx_with_tables(self):
        """Test DOCX with table content"""
        with patch("backend.core.parsers.Document") as mock_document_class:
            mock_doc = MagicMock()

            # Mock paragraphs
            mock_para = MagicMock()
            mock_para.text = "Paragraph content"
            mock_doc.paragraphs = [mock_para]

            # Mock table
            mock_table = MagicMock()
            mock_row1 = MagicMock()
            mock_cell1_1 = MagicMock()
            mock_cell1_1.text = "Cell 1"
            mock_cell1_2 = MagicMock()
            mock_cell1_2.text = "Cell 2"
            mock_row1.cells = [mock_cell1_1, mock_cell1_2]

            mock_row2 = MagicMock()
            mock_cell2_1 = MagicMock()
            mock_cell2_1.text = "Cell 3"
            mock_cell2_2 = MagicMock()
            mock_cell2_2.text = ""
            mock_row2.cells = [mock_cell2_1, mock_cell2_2]

            mock_table.rows = [mock_row1, mock_row2]
            mock_doc.tables = [mock_table]

            mock_document_class.return_value = mock_doc

            result = extract_text_from_docx("table.docx")

            assert "Paragraph content" in result
            assert "Cell 1 | Cell 2" in result
            assert "Cell 3" in result

    def test_extract_text_from_docx_no_library(self):
        """Test DOCX parsing when python-docx is not installed"""
        with patch("backend.core.parsers.Document", None):
            with pytest.raises(DocumentParseError, match="python-docx not installed"):
                extract_text_from_docx("test.docx")

    def test_extract_text_from_docx_empty_content(self):
        """Test DOCX with no content"""
        with patch("backend.core.parsers.Document") as mock_document_class:
            mock_doc = MagicMock()
            mock_doc.paragraphs = []
            mock_doc.tables = []
            mock_document_class.return_value = mock_doc

            with pytest.raises(DocumentParseError, match="No text extracted"):
                extract_text_from_docx("empty.docx")

    def test_extract_text_from_docx_file_error(self):
        """Test DOCX file reading error"""
        with patch("backend.core.parsers.Document", side_effect=Exception("File error")):
            with pytest.raises(DocumentParseError, match="Failed to parse DOCX"):
                extract_text_from_docx("corrupt.docx")


class TestEPUBParsing:
    """Test EPUB parsing functionality"""

    def test_extract_text_from_epub_success(self):
        """Test successful EPUB text extraction"""
        with patch("backend.core.parsers.epub") as mock_epub:
            # Mock EPUB book
            mock_book = MagicMock()

            # Mock document items
            mock_item1 = MagicMock()
            mock_item1.get_type.return_value = mock_epub.ITEM_DOCUMENT
            mock_item1.get_content.return_value = b"<html><body>Chapter 1 content</body></html>"

            mock_item2 = MagicMock()
            mock_item2.get_type.return_value = mock_epub.ITEM_DOCUMENT
            mock_item2.get_content.return_value = b"<html><body>Chapter 2 content</body></html>"

            mock_item3 = MagicMock()
            mock_item3.get_type.return_value = mock_epub.ITEM_STYLE  # Should be ignored

            mock_book.get_items.return_value = [mock_item1, mock_item2, mock_item3]
            mock_epub.read_epub.return_value = mock_book

            result = extract_text_from_epub("test.epub")

            assert "Chapter 1 content" in result
            assert "Chapter 2 content" in result

    def test_extract_text_from_epub_empty_content(self):
        """Test EPUB with no extractable text"""
        with patch("backend.core.parsers.epub") as mock_epub:
            mock_book = MagicMock()
            mock_book.get_items.return_value = []
            mock_epub.read_epub.return_value = mock_book

            with pytest.raises(DocumentParseError, match="No text extracted"):
                extract_text_from_epub("empty.epub")

    def test_extract_text_from_epub_file_error(self):
        """Test EPUB file reading error"""
        with patch("backend.core.parsers.epub", side_effect=Exception("File error")):
            with pytest.raises(DocumentParseError, match="Failed to parse EPUB"):
                extract_text_from_epub("corrupt.epub")


class TestTXTParsing:
    """Test TXT parsing functionality"""

    def test_extract_text_from_txt_success(self):
        """Test successful TXT text extraction"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("Line 1\nLine 2\nLine 3")
            tmp_path = tmp.name

        try:
            result = extract_text_from_txt(tmp_path)
            assert "Line 1" in result
            assert "Line 2" in result
            assert "Line 3" in result
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_extract_text_from_txt_empty_file(self):
        """Test TXT with empty content"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("")
            tmp_path = tmp.name

        try:
            with pytest.raises(DocumentParseError, match="No text extracted"):
                extract_text_from_txt(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_extract_text_from_txt_file_not_found(self):
        """Test TXT file not found"""
        with pytest.raises(DocumentParseError, match="Failed to read TXT"):
            extract_text_from_txt("nonexistent.txt")


class TestAutoDetectParsing:
    """Test automatic file type detection and parsing"""

    def test_auto_detect_pdf(self):
        """Test auto-detection of PDF files"""
        with patch("backend.core.parsers.extract_text_from_pdf") as mock_pdf:
            mock_pdf.return_value = "PDF content"

            result = auto_detect_and_parse("test.pdf")

            assert result == "PDF content"
            mock_pdf.assert_called_once_with("test.pdf")

    def test_auto_detect_docx(self):
        """Test auto-detection of DOCX files"""
        with patch("backend.core.parsers.extract_text_from_docx") as mock_docx:
            mock_docx.return_value = "DOCX content"

            result = auto_detect_and_parse("test.docx")

            assert result == "DOCX content"
            mock_docx.assert_called_once_with("test.docx")

    def test_auto_detect_epub(self):
        """Test auto-detection of EPUB files"""
        with patch("backend.core.parsers.extract_text_from_epub") as mock_epub:
            mock_epub.return_value = "EPUB content"

            result = auto_detect_and_parse("test.epub")

            assert result == "EPUB content"
            mock_epub.assert_called_once_with("test.epub")

    def test_auto_detect_txt(self):
        """Test auto-detection of TXT files"""
        with patch("backend.core.parsers.extract_text_from_txt") as mock_txt:
            mock_txt.return_value = "TXT content"

            result = auto_detect_and_parse("test.txt")

            assert result == "TXT content"
            mock_txt.assert_called_once_with("test.txt")

    def test_auto_detect_markdown(self):
        """Test auto-detection of Markdown files (treated as TXT)"""
        with patch("backend.core.parsers.extract_text_from_txt") as mock_txt:
            mock_txt.return_value = "Markdown content"

            result = auto_detect_and_parse("test.md")

            assert result == "Markdown content"
            mock_txt.assert_called_once_with("test.md")

    def test_auto_detect_unsupported_format(self):
        """Test auto-detection with unsupported file format"""
        with pytest.raises(DocumentParseError, match="Unsupported file type"):
            auto_detect_and_parse("test.xyz")

    def test_auto_detect_file_not_found(self):
        """Test auto-detection with non-existent file"""
        with pytest.raises(DocumentParseError, match="File not found"):
            auto_detect_and_parse("nonexistent.pdf")

    def test_auto_detect_case_insensitive(self):
        """Test auto-detection is case insensitive"""
        with patch("backend.core.parsers.extract_text_from_pdf") as mock_pdf:
            mock_pdf.return_value = "PDF content"

            result = auto_detect_and_parse("test.PDF")

            assert result == "PDF content"
            mock_pdf.assert_called_once_with("test.PDF")


class TestDocumentInfo:
    """Test document information extraction"""

    def test_get_document_info_pdf(self):
        """Test PDF document info extraction"""
        with (
            patch("backend.core.parsers.PdfReader") as mock_reader_class,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            # Mock file stats
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB

            # Mock PDF reader
            mock_reader = MagicMock()
            mock_reader.pages = [MagicMock(), MagicMock()]  # 2 pages
            mock_reader.metadata = {"/Title": "Test Document", "/Author": "Test Author"}
            mock_reader_class.return_value = mock_reader

            result = get_document_info("test.pdf")

            assert result["file_name"] == "test.pdf"
            assert result["file_size_mb"] == 1.0
            assert result["file_type"] == ".pdf"
            assert result["pages"] == 2
            assert result["title"] == "Test Document"
            assert result["author"] == "Test Author"

    def test_get_document_info_docx(self):
        """Test DOCX document info extraction"""
        with (
            patch("backend.core.parsers.Document") as mock_document_class,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            # Mock file stats
            mock_stat.return_value.st_size = 512 * 1024  # 512KB

            # Mock DOCX document
            mock_doc = MagicMock()
            mock_doc.paragraphs = [MagicMock() for _ in range(10)]  # 10 paragraphs

            mock_props = MagicMock()
            mock_props.title = "DOCX Document"
            mock_props.author = "DOCX Author"
            mock_doc.core_properties = mock_props

            mock_document_class.return_value = mock_doc

            result = get_document_info("test.docx")

            assert result["file_name"] == "test.docx"
            assert result["file_size_mb"] == 0.5
            assert result["file_type"] == ".docx"
            assert result["pages"] == 10  # Paragraph count as page approximation
            assert result["title"] == "DOCX Document"
            assert result["author"] == "DOCX Author"

    def test_get_document_info_no_library(self):
        """Test document info when required library is missing"""
        with (
            patch("backend.core.parsers.Document", None),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 1024
            result = get_document_info("test.docx")

            # Should still return basic info
            assert result["file_name"] == "test.docx"
            assert result["file_type"] == ".docx"
            assert result["title"] == ""
            assert result["author"] == ""

    def test_get_document_info_epub(self):
        """Test EPUB document info extraction"""
        with (
            patch("backend.core.parsers.epub") as mock_epub,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 2 * 1024 * 1024  # 2MB

            mock_book = MagicMock()
            mock_book.get_metadata.side_effect = [
                [("Test EPUB Title", None)],  # title
                [("EPUB Author", None)],  # author
            ]
            mock_epub.read_epub.return_value = mock_book

            result = get_document_info("test.epub")

            assert result["file_name"] == "test.epub"
            assert result["file_size_mb"] == 2.0
            assert result["file_type"] == ".epub"
            assert result["title"] == "Test EPUB Title"
            assert result["author"] == "EPUB Author"

    def test_get_document_info_error_handling(self):
        """Test error handling in document info extraction"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat", side_effect=Exception("File error")),
        ):
            result = get_document_info("test.pdf")

            # Should return basic info despite error
            assert result["file_name"] == "test.pdf"
            assert "file_size_mb" in result


class TestIntegrationScenarios:
    """Integration tests for realistic parsing scenarios"""

    def test_parse_corrupted_pdf_fallback(self):
        """Test handling of corrupted PDF files"""
        with patch("backend.core.parsers.PdfReader", side_effect=Exception("Corrupted PDF")):
            with pytest.raises(DocumentParseError):
                auto_detect_and_parse("corrupted.pdf")

    def test_parse_large_file_performance(self):
        """Test parsing performance with large content"""
        with patch("backend.core.parsers.PdfReader") as mock_reader_class:
            # Mock large content
            large_content = "Content " * 10000  # Large document
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = large_content
            mock_reader.pages = [mock_page]
            mock_reader_class.return_value = mock_reader

            start_time = time.time()
            result = auto_detect_and_parse("large.pdf")
            duration = time.time() - start_time

            assert len(result) > 50000  # Should be large
            assert duration < 1.0  # Should be reasonably fast

    def test_mixed_content_extraction(self):
        """Test extraction from mixed content documents"""
        with patch("backend.core.parsers.Document") as mock_document_class:
            mock_doc = MagicMock()

            # Mixed paragraphs and tables
            mock_para1 = MagicMock()
            mock_para1.text = "Introduction paragraph"
            mock_para2 = MagicMock()
            mock_para2.text = "Conclusion paragraph"

            mock_table = MagicMock()
            mock_row = MagicMock()
            mock_cell1 = MagicMock()
            mock_cell1.text = "Header"
            mock_cell2 = MagicMock()
            mock_cell2.text = "Data"
            mock_row.cells = [mock_cell1, mock_cell2]
            mock_table.rows = [mock_row]

            mock_doc.paragraphs = [mock_para1, mock_para2]
            mock_doc.tables = [mock_table]
            mock_document_class.return_value = mock_doc

            result = extract_text_from_docx("mixed.docx")

            assert "Introduction paragraph" in result
            assert "Conclusion paragraph" in result
            assert "Header | Data" in result
            assert result.count("\n\n") >= 2  # Proper separation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
