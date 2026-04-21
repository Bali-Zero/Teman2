"""
Unit tests for page-aware chunking (TODO #76).

8-test matrix from wave 1 design (PR #174 pseudocode) ported into assertions:
1. PDF single-page          → one marker, one or more chunks all page=1
2. PDF multi-page           → markers per page, every chunk tagged with source page
3. Page break mid-chunk     → a page boundary never produces a cross-page chunk
4. OCR path (no markers)    → falls back to semantic_chunk, no "page" key
5. Empty pages              → empty pages do not produce chunks, non-empty do
6. Markers mismatched       → inconsistent markers fall back, never crash
7. Backward-compat flag off → extract_text_from_pdf default returns str (no marker tuple)
8. Perf regression check    → no-marker fallback is not slower than direct semantic_chunk

Run:
    PYTHONPATH=. pytest backend/tests/unit/core/test_chunker_page_aware.py -q
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.chunker import TextChunker  # noqa: E402
from backend.core.parsers import (  # noqa: E402
    PDF_PAGE_SEPARATOR,
    _join_pages_with_markers,
    extract_text_from_pdf,
)


def _chunker(**kw) -> TextChunker:
    """Helper: build a TextChunker with predictable defaults."""
    defaults = {"chunk_size": 100, "chunk_overlap": 0, "max_chunks": 500}
    defaults.update(kw)
    return TextChunker(**defaults)


class TestJoinPagesWithMarkers:
    """Marker-math helper — load-bearing: chunker relies on identical offsets."""

    def test_three_non_empty_pages(self) -> None:
        text, markers = _join_pages_with_markers(["AAA", "BBB", "CCC"])
        assert text == "AAA\n\nBBB\n\nCCC"
        assert markers == [0, 5, 10]
        # Verify each marker actually points at the right content.
        for i, m in enumerate(markers):
            assert text[m : m + 3] == ["AAA", "BBB", "CCC"][i]

    def test_empty_middle_page(self) -> None:
        text, markers = _join_pages_with_markers(["AAA", "", "CCC"])
        # Three markers, one per input page — preserves 1:1 mapping.
        assert len(markers) == 3
        # Middle page is zero-length → marker points to the separator.
        assert text[markers[0] : markers[0] + 3] == "AAA"
        assert text[markers[2] : markers[2] + 3] == "CCC"


class TestSinglePage:
    """Matrix #1 — PDF single-page."""

    def test_single_page_text_shorter_than_chunk_size(self) -> None:
        chunker = _chunker(chunk_size=200)
        text = "single page content"
        chunks = chunker.chunk_by_pages(text, page_markers=[0])
        assert len(chunks) == 1
        assert chunks[0]["page"] == 1
        assert chunks[0]["page_chunk_index"] == 0
        assert chunks[0]["text"].strip() == "single page content"

    def test_single_page_longer_than_chunk_size_splits(self) -> None:
        chunker = _chunker(chunk_size=20)
        text = "word " * 30  # 150 chars, same page
        chunks = chunker.chunk_by_pages(text, page_markers=[0])
        assert len(chunks) > 1
        # Every chunk must still be tagged as page 1.
        for c in chunks:
            assert c["page"] == 1
        # page_chunk_index increments within the page.
        assert [c["page_chunk_index"] for c in chunks] == list(range(len(chunks)))


class TestMultiPage:
    """Matrix #2 — PDF multi-page page tagging."""

    def test_each_chunk_tagged_with_source_page(self) -> None:
        text, markers = _join_pages_with_markers(
            ["page one alpha", "page two beta", "page three gamma"],
        )
        chunks = _chunker(chunk_size=200).chunk_by_pages(text, markers)
        assert len(chunks) == 3
        pages = [c["page"] for c in chunks]
        assert pages == [1, 2, 3]
        # Chunks contain only text from their own page.
        assert "alpha" in chunks[0]["text"] and "beta" not in chunks[0]["text"]
        assert "beta" in chunks[1]["text"] and "gamma" not in chunks[1]["text"]
        assert "gamma" in chunks[2]["text"] and "alpha" not in chunks[2]["text"]


class TestPageBreakMidChunk:
    """Matrix #3 — a page boundary must NEVER merge into a cross-page chunk."""

    def test_large_chunk_size_still_splits_pages(self) -> None:
        # chunk_size is huge, semantic_chunk would happily emit one chunk —
        # but chunk_by_pages must emit one chunk PER PAGE.
        text, markers = _join_pages_with_markers(
            ["short one", "short two", "short three"],
        )
        chunks = _chunker(chunk_size=10_000).chunk_by_pages(text, markers)
        assert len(chunks) == 3
        for idx, c in enumerate(chunks, start=1):
            assert c["page"] == idx
            # No chunk should contain text from another page.
            other_markers = ["one", "two", "three"]
            expected = other_markers[idx - 1]
            for j, word in enumerate(other_markers):
                if j == idx - 1:
                    assert word in c["text"]
                else:
                    assert word not in c["text"], (
                        f"chunk {idx} leaked page-{j+1} word {word}: {c['text']!r}"
                    )


class TestOCRPath:
    """Matrix #4 — OCR returns no reliable markers; chunker must degrade to semantic."""

    def test_empty_markers_list_triggers_fallback(self) -> None:
        # parsers.py returns ([], text) for OCR path. Chunker treats
        # falsy page_markers as "no markers" and uses semantic_chunk.
        chunker = _chunker(chunk_size=100)
        text = "ocr extracted text " * 10
        chunks = chunker.chunk_by_pages(text, page_markers=[])
        # Must produce SOME chunks and NONE should carry a "page" key
        # since the fallback path has no page info.
        assert len(chunks) >= 1
        for c in chunks:
            assert "page" not in c

    def test_none_markers_triggers_fallback(self) -> None:
        chunker = _chunker(chunk_size=100)
        chunks = chunker.chunk_by_pages("something", page_markers=None)
        assert len(chunks) == 1
        assert "page" not in chunks[0]


class TestEmptyPages:
    """Matrix #5 — empty pages must not emit chunks, non-empty must."""

    def test_empty_pages_skipped(self) -> None:
        text, markers = _join_pages_with_markers(
            ["content page one", "", "content page three", "", ""],
        )
        chunks = _chunker(chunk_size=500).chunk_by_pages(text, markers)
        # Only pages 1 and 3 should produce chunks.
        pages = sorted({c["page"] for c in chunks})
        assert pages == [1, 3]
        assert any("page one" in c["text"] for c in chunks)
        assert any("page three" in c["text"] for c in chunks)


class TestMarkersMismatched:
    """Matrix #6 — garbage markers must not crash; fall back to semantic."""

    def test_markers_out_of_range_fall_back(self) -> None:
        chunker = _chunker(chunk_size=100)
        text = "short text"
        # Marker past end of text.
        chunks = chunker.chunk_by_pages(text, page_markers=[0, 999])
        assert len(chunks) >= 1
        for c in chunks:
            assert "page" not in c  # fallback path drops page info

    def test_markers_non_monotonic_fall_back(self) -> None:
        chunker = _chunker(chunk_size=100)
        text = "some reasonably long page content here that is fine"
        chunks = chunker.chunk_by_pages(text, page_markers=[10, 5, 20])
        assert len(chunks) >= 1
        for c in chunks:
            assert "page" not in c

    def test_markers_negative_fall_back(self) -> None:
        chunker = _chunker(chunk_size=100)
        chunks = chunker.chunk_by_pages("text", page_markers=[-1, 2])
        assert len(chunks) >= 1
        for c in chunks:
            assert "page" not in c


class TestBackwardCompat:
    """Matrix #7 — the new return_page_markers flag must default False."""

    @patch("backend.core.parsers.PdfReader")
    def test_default_flag_returns_str(self, mock_reader_class) -> None:
        p1, p2 = MagicMock(), MagicMock()
        p1.extract_text.return_value = "Page 1 content"
        p2.extract_text.return_value = "Page 2 content"
        mock_reader_class.return_value.pages = [p1, p2]

        result = extract_text_from_pdf("/fake.pdf")
        # Existing callers receive str exactly as before.
        assert isinstance(result, str)
        assert "Page 1 content" in result and "Page 2 content" in result

    @patch("backend.core.parsers.PdfReader")
    def test_flag_true_returns_tuple_with_markers(self, mock_reader_class) -> None:
        p1, p2, p3 = MagicMock(), MagicMock(), MagicMock()
        p1.extract_text.return_value = "Alpha"
        p2.extract_text.return_value = "Beta"
        p3.extract_text.return_value = "Gamma"
        mock_reader_class.return_value.pages = [p1, p2, p3]

        result = extract_text_from_pdf("/fake.pdf", return_page_markers=True)
        assert isinstance(result, tuple) and len(result) == 2
        text, markers = result
        assert markers == [0, len("Alpha") + len(PDF_PAGE_SEPARATOR),
                           len("Alpha") + len(PDF_PAGE_SEPARATOR)
                           + len("Beta") + len(PDF_PAGE_SEPARATOR)]
        # And markers produced by the parser round-trip through the chunker.
        chunks = _chunker(chunk_size=200).chunk_by_pages(text, markers)
        assert [c["page"] for c in chunks] == [1, 2, 3]


class TestPerfRegression:
    """Matrix #8 — fallback path must not be meaningfully slower than semantic_chunk."""

    def test_fallback_no_marker_not_slower_than_semantic(self) -> None:
        chunker = _chunker(chunk_size=200)
        text = ("paragraph with some words. " * 50 + "\n\n") * 20  # ~28K chars

        # Direct semantic_chunk — upper bound on fallback cost.
        t0 = time.perf_counter()
        for _ in range(5):
            chunker.semantic_chunk(text)
        baseline = (time.perf_counter() - t0) / 5

        # chunk_by_pages with no markers — same call path internally.
        t0 = time.perf_counter()
        for _ in range(5):
            chunker.chunk_by_pages(text, page_markers=None)
        fallback = (time.perf_counter() - t0) / 5

        # Allow 3x slack for CI noise; the two should be effectively identical.
        assert fallback < baseline * 3 + 0.01, (
            f"chunk_by_pages fallback {fallback*1000:.2f}ms "
            f"vs semantic_chunk {baseline*1000:.2f}ms "
            "— fallback is not supposed to add overhead."
        )
