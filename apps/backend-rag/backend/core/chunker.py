"""
Minimal Chunker stub for tests.
"""


class Chunker:
    def __init__(self, max_tokens: int = 512, overlap: int = 0):
        self.max_tokens = max_tokens
        self.overlap = overlap

    def chunk_text(self, text: str) -> list[str]:
        if not text:
            return []
        # Very naive splitter for tests
        return [text[i : i + self.max_tokens] for i in range(0, len(text), self.max_tokens)]


def create_chunker(max_tokens: int = 512, overlap: int = 0) -> Chunker:
    return Chunker(max_tokens=max_tokens, overlap=overlap)


__all__ = ["Chunker", "create_chunker"]
"""
ZANTARA RAG - Text Chunking
Semantic text splitting for optimal RAG performance
"""

import logging
from typing import Any

try:
    from app.core.config import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Semantic text chunker using recursive text splitting.
    Optimized for book content with natural language structure.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None, max_chunks: int = None):
        """
        Initialize chunker with configuration.

        Args:
            chunk_size: Maximum characters per chunk (default from settings)
            chunk_overlap: Overlap between chunks for context (default from settings)
            max_chunks: Maximum chunks to create per document
        """
        self.chunk_size = chunk_size or (settings.chunk_size if settings else 1000)
        self.chunk_overlap = chunk_overlap or (settings.chunk_overlap if settings else 100)
        self.max_chunks = max_chunks or (settings.max_chunks_per_book if settings else 500)

        # Separators in order of preference (from most to least semantic)
        self.separators = [
            "\n\n\n",  # Chapter breaks
            "\n\n",  # Paragraph breaks
            "\n",  # Line breaks
            ". ",  # Sentence breaks
            "! ",  # Exclamation
            "? ",  # Question
            "; ",  # Semicolon
            ", ",  # Comma
            " ",  # Word breaks
            "",  # Character level
        ]

        logger.info(
            f"TextChunker initialized: chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, max_chunks={self.max_chunks}"
        )

    def _split_text_recursive(self, text: str, separator: str) -> list[str]:
        """
        Recursively split text using the given separator.

        Args:
            text: Text to split
            separator: Current separator to use

        Returns:
            List of text chunks
        """
        # First, split by current separator
        splits = text.split(separator)

        # Now combine splits into chunks that respect the chunk_size
        # Use list for efficient string concatenation (O(n) instead of O(n²))
        chunks = []
        chunk_parts = []

        for i, split in enumerate(splits):
            # Add separator back (except for empty separator)
            split_with_sep = split + separator if separator and i < len(splits) - 1 else split

            # Check if adding this split would exceed chunk_size
            potential_chunk = "".join(chunk_parts) + split_with_sep
            if len(potential_chunk) > self.chunk_size and chunk_parts:
                # Save current chunk and start new one
                chunks.append("".join(chunk_parts).strip())
                chunk_parts = [split_with_sep]
            else:
                # Add to current chunk
                chunk_parts.append(split_with_sep)

        # Don't forget the last chunk
        if chunk_parts:
            chunks.append("".join(chunk_parts).strip())

        # If any chunk is still too big, try splitting with next separator
        separator_idx = self.separators.index(separator) if separator in self.separators else -1
        if separator_idx < len(self.separators) - 1:
            next_separator = self.separators[separator_idx + 1]
            final_chunks = []
            for chunk in chunks:
                if len(chunk) > self.chunk_size:
                    final_chunks.extend(self._split_text_recursive(chunk, next_separator))
                else:
                    final_chunks.append(chunk)
            return final_chunks

        return chunks

    def chunk_text(self, text: str) -> list[str]:
        """
        Simple text chunking method (for compatibility with tests).

        Args:
            text: Text to chunk

        Returns:
            List of text chunks (strings only)
        """
        chunks = self.semantic_chunk(text)
        # Extract just the text from semantic chunks
        return [
            chunk.get("text", "") if isinstance(chunk, dict) else str(chunk) for chunk in chunks
        ]

    def semantic_chunk(self, text: str, metadata: dict[str, Any] = None) -> list[dict[str, Any]]:
        """
        Split text into semantic chunks with metadata.

        Args:
            text: Full text content to chunk
            metadata: Optional base metadata to attach to each chunk

        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []

        try:
            # Start with the first separator (most semantic)
            chunks = (
                self._split_text_recursive(text, self.separators[0]) if self.separators else [text]
            )

            # Apply overlap between chunks
            if self.chunk_overlap > 0 and len(chunks) > 1:
                overlapped_chunks = []
                for i, chunk in enumerate(chunks):
                    # Add overlap from previous chunk
                    if i > 0:
                        overlap_text = (
                            chunks[i - 1][-self.chunk_overlap :]
                            if len(chunks[i - 1]) > self.chunk_overlap
                            else chunks[i - 1]
                        )
                        chunk = overlap_text + chunk
                    overlapped_chunks.append(chunk)
                chunks = overlapped_chunks

            # Limit number of chunks if needed
            if len(chunks) > self.max_chunks:
                logger.warning(
                    f"Text split into {len(chunks)} chunks, truncating to {self.max_chunks}"
                )
                chunks = chunks[: self.max_chunks]

            # Create chunk objects with metadata
            chunk_objects = []
            for idx, chunk_text in enumerate(chunks):
                chunk_obj = {
                    "text": chunk_text,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "chunk_length": len(chunk_text),
                }

                # Add base metadata if provided
                if metadata:
                    chunk_obj.update(metadata)

                chunk_objects.append(chunk_obj)

            logger.info(
                f"Created {len(chunk_objects)} chunks "
                f"(avg length: {sum(len(c['text']) for c in chunk_objects) // len(chunk_objects) if chunk_objects else 0})"
            )

            return chunk_objects

        except Exception as e:
            logger.error(f"Error chunking text: {e}")
            raise

    def chunk_by_pages(
        self, text: str, page_markers: list[int] = None, metadata: dict[str, Any] = None
    ) -> list[dict[str, Any]]:
        """
        Alternative chunking that respects page boundaries (for PDFs).

        Args:
            text: Full text content
            page_markers: Character positions where pages start
            metadata: Base metadata

        Returns:
            List of chunks with page number tracking
        """
        if not page_markers:
            # Fall back to standard semantic chunking
            return self.semantic_chunk(text, metadata)

        # TODO: Implement page-aware chunking
        # For now, use semantic chunking
        return self.semantic_chunk(text, metadata)


def semantic_chunk(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    """
    Convenience function for quick semantic chunking.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk (approximated as characters)
        overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    chunker = TextChunker(chunk_size=max_tokens, chunk_overlap=overlap)
    chunk_objects = chunker.semantic_chunk(text)
    return [chunk["text"] for chunk in chunk_objects]
