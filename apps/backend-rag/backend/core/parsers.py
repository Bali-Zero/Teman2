"""
ZANTARA RAG - Document Parsers
Extract text from PDF and EPUB files
"""

import logging
import os
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    from pypdf import PdfReader

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

logger = logging.getLogger(__name__)


class DocumentParseError(Exception):
    """Custom exception for document parsing errors"""

    pass


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text as string

    Raises:
        DocumentParseError: If parsing fails
    """
    try:
        logger.info(f"Parsing PDF: {file_path}")

        reader = PdfReader(file_path)
        text_parts = []

        for page_num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except Exception as e:
                logger.warning(f"Error extracting page {page_num}: {e}")
                continue

        full_text = "\n\n".join(text_parts)

        if not full_text.strip():
            raise DocumentParseError(f"No text extracted from PDF: {file_path}")

        logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
        return full_text

    except Exception as e:
        raise DocumentParseError(f"Failed to parse PDF {file_path}: {str(e)}") from e


def extract_text_from_epub(file_path: str) -> str:
    """
    Extract text content from EPUB file.

    Args:
        file_path: Path to EPUB file

    Returns:
        Extracted text as string

    Raises:
        DocumentParseError: If parsing fails
    """
    try:
        logger.info(f"Parsing EPUB: {file_path}")

        book = epub.read_epub(file_path)
        text_parts = []

        # Extract text from each chapter
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                try:
                    content = item.get_content().decode("utf-8")
                    soup = BeautifulSoup(content, "html.parser")
                    text = soup.get_text(separator="\n", strip=True)

                    if text:
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"Error extracting chapter: {e}")
                    continue

        full_text = "\n\n".join(text_parts)

        if not full_text.strip():
            raise DocumentParseError(f"No text extracted from EPUB: {file_path}")

        logger.info(f"Successfully extracted {len(full_text)} characters from EPUB")
        return full_text

    except Exception as e:
        raise DocumentParseError(f"Failed to parse EPUB {file_path}: {str(e)}") from e


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text content from TXT file.

    Args:
        file_path: Path to TXT file

    Returns:
        Extracted text as string

    Raises:
        DocumentParseError: If parsing fails
    """
    try:
        logger.info(f"Reading TXT: {file_path}")
        with open(file_path, encoding="utf-8") as f:
            text = f.read()

        if not text.strip():
            raise DocumentParseError(f"No text extracted from TXT: {file_path}")

        logger.info(f"Successfully extracted {len(text)} characters from TXT")
        return text

    except Exception as e:
        raise DocumentParseError(f"Failed to read TXT {file_path}: {str(e)}") from e


def auto_detect_and_parse(file_path: str) -> str:
    """
    Auto-detect file type and parse accordingly.

    Args:
        file_path: Path to document file

    Returns:
        Extracted text as string

    Raises:
        DocumentParseError: If file type unsupported or parsing fails
    """
    if not os.path.exists(file_path):
        raise DocumentParseError(f"File not found: {file_path}")

    file_ext = Path(file_path).suffix.lower()

    if file_ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif file_ext == ".epub":
        return extract_text_from_epub(file_path)
    elif file_ext == ".txt":
        return extract_text_from_txt(file_path)
    elif file_ext == ".md":
        return extract_text_from_txt(file_path)  # Markdown is plain text
    else:
        raise DocumentParseError(
            f"Unsupported file type: {file_ext}. Supported formats: .pdf, .epub, .txt, .md"
        )


def get_document_info(file_path: str) -> dict:
    """
    Extract basic metadata from document.

    Args:
        file_path: Path to document

    Returns:
        Dictionary with document metadata
    """
    info = {
        "file_name": Path(file_path).name,
        "file_size_mb": os.path.getsize(file_path) / (1024 * 1024),
        "file_type": Path(file_path).suffix.lower(),
        "file_path": file_path,
    }

    try:
        if info["file_type"] == ".pdf":
            reader = PdfReader(file_path)
            info["pages"] = len(reader.pages)

            # Try to get PDF metadata
            if reader.metadata:
                info["title"] = reader.metadata.get("/Title", "")
                info["author"] = reader.metadata.get("/Author", "")

        elif info["file_type"] == ".epub":
            book = epub.read_epub(file_path)
            info["title"] = (
                book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else ""
            )
            info["author"] = (
                book.get_metadata("DC", "creator")[0][0]
                if book.get_metadata("DC", "creator")
                else ""
            )

    except Exception as e:
        logger.warning(f"Could not extract metadata from {file_path}: {e}")

    return info
