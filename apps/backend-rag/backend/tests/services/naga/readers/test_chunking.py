"""Tests for ``backend.services.naga.readers.chunking.hierarchical_chunk``.

The three-level split is the contract: domain grouping (L1), per-domain
packing under ``chunk_chars`` (L2), and sentence-boundary split with
``overlap_chars`` for oversize sources (L3). These tests pin each level.
"""

from __future__ import annotations

from backend.services.naga.readers.chunking import hierarchical_chunk


def test_empty_sources_returns_empty_list() -> None:
    assert hierarchical_chunk([]) == []


def test_group_by_domain() -> None:
    """Sources from different netlocs must not share a chunk."""
    sources = [
        {"url": "https://imigrasi.go.id/a", "content": "aaa"},
        {"url": "https://bkpm.go.id/x", "content": "xxx"},
        {"url": "https://imigrasi.go.id/b", "content": "bbb"},
        {"url": "https://bkpm.go.id/y", "content": "yyy"},
    ]
    chunks = hierarchical_chunk(sources, chunk_chars=24_000)
    assert len(chunks) == 2
    domains = {c["domain"] for c in chunks}
    assert domains == {"imigrasi.go.id", "bkpm.go.id"}
    for c in chunks:
        assert all(
            c["domain"] in s["url"] for s in c["sources"]
        ), "sources inside a chunk must share its domain"


def test_packing_respects_chunk_chars_within_domain() -> None:
    """Packing must flush when the running char count would exceed ``chunk_chars``."""
    sources = [
        {"url": "https://ex.com/1", "content": "a" * 600},
        {"url": "https://ex.com/2", "content": "b" * 600},
        {"url": "https://ex.com/3", "content": "c" * 600},
    ]
    chunks = hierarchical_chunk(sources, chunk_chars=1_000)
    # Single-domain, 3 × 600 chars — cannot fit in one 1_000-char chunk.
    assert len(chunks) >= 2
    for c in chunks:
        total = sum(len(s["content"]) for s in c["sources"])
        # Each chunk must carry at least one source, but the cumulative size
        # is only forced below chunk_chars *before* admitting each new source;
        # a single oversize-but-under-max_source_chars source may pass through.
        assert total <= 1_200 or len(c["sources"]) == 1


def test_single_long_source_splits_at_sentence_boundary_with_overlap() -> None:
    """A source above ``max_source_chars`` is sentence-split with overlap."""
    # Build a long content made of distinct sentences so we can verify overlap.
    sentences = [f"Sentence {i} contains unique token ZZZ{i}." for i in range(400)]
    long_content = " ".join(sentences)
    sources = [{"url": "https://ex.com/long", "content": long_content}]

    chunks = hierarchical_chunk(
        sources,
        chunk_chars=1_000,
        overlap_chars=200,
        max_source_chars=2_000,  # forces L3 split
    )
    # Must produce multiple partial pieces.
    parts = [s for c in chunks for s in c["sources"] if s.get("partial")]
    assert len(parts) >= 2, "long source must be split into multiple parts"

    # Parts are ordered and use the L3 contract.
    for p in parts:
        assert p["partial"] is True
        assert isinstance(p["part"], int)
        # Every split part stays under chunk_chars plus one sentence worth
        # of slack (the splitter admits a sentence that just fits, then flushes).
        assert len(p["content"]) <= 1_400

    # Overlap: consecutive parts from the same URL must share some characters.
    first_two = parts[:2]
    assert first_two[0]["content"] != first_two[1]["content"]
    tail = first_two[0]["content"][-200:]
    head = first_two[1]["content"][:400]
    # At least one non-trivial substring of the tail appears at the head —
    # the splitter prepends up to overlap_chars of the previous buffer.
    assert any(
        token in head for token in tail.split() if len(token) > 4
    ), "expected overlap_chars of shared text between consecutive parts"


def test_of_total_and_chunk_index_are_consistent() -> None:
    sources = [
        {"url": f"https://a.com/{i}", "content": "x" * 500} for i in range(3)
    ]
    chunks = hierarchical_chunk(sources, chunk_chars=1_000)
    total = len(chunks)
    for i, c in enumerate(chunks):
        assert c["chunk_index"] == i
        assert c["of_total"] == total
