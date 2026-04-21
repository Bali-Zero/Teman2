"""
Minimal Chunker stub for tests.
"""


class Chunker:
    def __init__(self, max_tokens: int = 512, overlap: int = 0) -> None:
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
    from backend.app.core.config import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Semantic text chunker using recursive text splitting.
    Optimized for book content with natural language structure.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None, max_chunks: int = None) -> None:
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
            f"overlap={self.chunk_overlap}, max_chunks={self.max_chunks}",
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
                    f"Text split into {len(chunks)} chunks, truncating to {self.max_chunks}",
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
                f"(avg length: {sum(len(c['text']) for c in chunk_objects) // len(chunk_objects) if chunk_objects else 0})",
            )

            return chunk_objects

        except Exception as e:
            logger.error(f"Error chunking text: {e}")
            raise

    def chunk_by_pages(
        self, text: str, page_markers: list[int] = None, metadata: dict[str, Any] = None,
    ) -> list[dict[str, Any]]:
        """
        Page-aware chunking: honours page boundaries from PDF extraction.

        Each chunk is guaranteed to contain text from exactly ONE source page,
        so ``chunk["page"]`` can be trusted downstream (citations, UI, KG
        ingestion). When a page is longer than ``chunk_size`` the per-page
        text is split with the standard semantic splitter; when it is shorter
        it becomes a single chunk. Consecutive pages are NEVER merged, which
        is the whole point compared to ``semantic_chunk``.

        Args:
            text: Full joined text as produced by parsers
                (``extract_text_from_pdf(..., return_page_markers=True)``).
            page_markers: Character offsets where each page starts in
                ``text``. ``page_markers[i]`` is the start of page ``i+1``.
                When falsy OR the marker list is inconsistent with ``text``,
                we fall back to standard semantic chunking (OCR path,
                markers mismatched content, etc.).
            metadata: Optional base metadata propagated to every chunk.

        Returns:
            List of chunk dicts. Each chunk carries at minimum:
            ``text``, ``chunk_index``, ``total_chunks``, ``chunk_length``,
            ``page`` (1-based page number), ``page_chunk_index``
            (index within that page).
        """
        if not page_markers or not text or not text.strip():
            return self.semantic_chunk(text, metadata)

        # Sanity: markers must be strictly sorted and inside [0, len(text)].
        # Any violation (e.g. OCR-path with empty markers, corrupt offsets)
        # is treated as "no markers" so we degrade gracefully instead of
        # producing garbage page numbers.
        text_len = len(text)
        prev = -1
        for off in page_markers:
            if not isinstance(off, int) or off < 0 or off > text_len or off <= prev:
                logger.warning(
                    "chunk_by_pages: inconsistent page_markers (%s for text len %d); "
                    "falling back to semantic_chunk.",
                    page_markers,
                    text_len,
                )
                return self.semantic_chunk(text, metadata)
            prev = off

        # Slice the full text at each marker boundary so we know exactly
        # what text belongs to which page. The last page runs to EOF.
        page_texts: list[str] = []
        for i, start in enumerate(page_markers):
            end = page_markers[i + 1] if i + 1 < len(page_markers) else text_len
            page_texts.append(text[start:end])

        # Chunk each page individually, respecting chunk_size. The overlap
        # policy here is deliberately intra-page only — overlap that crosses
        # a page boundary would defeat the purpose of page-aware chunking.
        chunk_objects: list[dict[str, Any]] = []
        for page_idx, page_text in enumerate(page_texts, start=1):
            if not page_text.strip():
                continue
            try:
                if self.separators:
                    raw_chunks = self._split_text_recursive(page_text, self.separators[0])
                else:
                    raw_chunks = [page_text]
            except Exception as e:
                logger.error(f"Error chunking page {page_idx}: {e}")
                raise

            if self.chunk_overlap > 0 and len(raw_chunks) > 1:
                overlapped: list[str] = []
                for i, chunk in enumerate(raw_chunks):
                    if i > 0:
                        overlap_text = (
                            raw_chunks[i - 1][-self.chunk_overlap:]
                            if len(raw_chunks[i - 1]) > self.chunk_overlap
                            else raw_chunks[i - 1]
                        )
                        chunk = overlap_text + chunk
                    overlapped.append(chunk)
                raw_chunks = overlapped

            for local_idx, chunk_text in enumerate(raw_chunks):
                if not chunk_text.strip():
                    continue
                obj = {
                    "text": chunk_text,
                    "page": page_idx,
                    "page_chunk_index": local_idx,
                    "chunk_length": len(chunk_text),
                }
                if metadata:
                    obj.update(metadata)
                    # Never let caller-provided metadata shadow the
                    # page-tracking fields — they are load-bearing.
                    obj["page"] = page_idx
                    obj["page_chunk_index"] = local_idx
                chunk_objects.append(obj)

        # Truncate AFTER per-page chunking to honour the max_chunks cap.
        if len(chunk_objects) > self.max_chunks:
            logger.warning(
                f"chunk_by_pages: produced {len(chunk_objects)} chunks, "
                f"truncating to {self.max_chunks}",
            )
            chunk_objects = chunk_objects[: self.max_chunks]

        # Fill in global chunk_index / total_chunks (computed last so it
        # reflects the post-truncation reality).
        total = len(chunk_objects)
        for idx, obj in enumerate(chunk_objects):
            obj["chunk_index"] = idx
            obj["total_chunks"] = total

        logger.info(
            "chunk_by_pages: %d chunks across %d pages (avg length: %d)",
            total,
            len(page_texts),
            sum(c["chunk_length"] for c in chunk_objects) // total if total else 0,
        )
        return chunk_objects


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
