"""Hierarchical chunking for bulk reading with limited-context local models.

Used by ``ollama_reader.ollama_bulk_read_hierarchical`` when the Gemini 1M
context path fails and the research loop has to fall back to
``deepseek-r1:32b`` (~32K effective tokens). The three-level split keeps
per-chunk payload small enough to fit while preserving enough context per
source for extraction to be useful:

- **L1 — group by domain.** Sources coming from the same ``urlparse(url).netloc``
  share provenance and style; batching them together reduces prompt
  switching cost for the model.
- **L2 — pack into ``chunk_chars`` windows.** Within a domain group, pack
  consecutive sources until the running character budget would be exceeded.
- **L3 — sentence-split oversize sources.** A single source longer than
  ``max_source_chars`` is split on sentence boundaries
  (``re.split(r'(?<=[.!?])\\s+', ...)``) with ``overlap_chars`` of trailing
  text carried into the next part to preserve context across the seam.
"""

from __future__ import annotations

import re
from typing import TypedDict
from urllib.parse import urlparse

__all__ = ["Chunk", "hierarchical_chunk"]


class Chunk(TypedDict):
    """One hierarchical-chunk unit produced by :func:`hierarchical_chunk`."""

    chunk_index: int
    of_total: int
    domain: str
    sources: list[dict]


_SENTENCE_SPLIT_RE: re.Pattern[str] = re.compile(r"(?<=[.!?])\s+")


def hierarchical_chunk(
    sources: list[dict],
    chunk_chars: int = 24_000,
    overlap_chars: int = 1_200,
    max_source_chars: int = 96_000,
) -> list[Chunk]:
    """Split *sources* into domain-grouped, size-bounded chunks.

    Args:
        sources: Raw source records. Each must provide ``url`` and ``content``;
            ``title`` and other keys are preserved verbatim on output.
        chunk_chars: Target upper bound for total characters per emitted chunk.
            ~24K chars ≈ 6K tokens, leaves budget for the extraction prompt
            and the model's JSON response inside deepseek-r1:32b's ~32K window.
        overlap_chars: When a single source is sentence-split, the trailing
            ``overlap_chars`` of the previous part are prepended to the next
            part. Protects against claims that straddle the seam.
        max_source_chars: Any source longer than this is sentence-split
            before packing. ``96_000 = 4 × chunk_chars`` by default.

    Returns:
        A list of :class:`Chunk` dicts. ``chunk_index`` is the 0-based
        position in the returned list; ``of_total`` is the list length (same
        for every element), provided for the extraction prompt so the model
        can report progress. Sources split by L3 carry ``partial=True`` and
        a 0-based ``part`` index.
    """
    if not sources:
        return []

    groups: dict[str, list[dict]] = {}
    for src in sources:
        netloc = urlparse(src.get("url", "")).netloc or "unknown"
        groups.setdefault(netloc, []).append(src)

    expanded: list[tuple[str, dict]] = []
    for domain, src_list in groups.items():
        for src in src_list:
            content: str = src.get("content", "")
            if len(content) <= max_source_chars:
                expanded.append((domain, src))
                continue

            sentences = _SENTENCE_SPLIT_RE.split(content)
            buf = ""
            part_idx = 0
            for sent in sentences:
                if not sent:
                    continue
                prospective = (buf + " " + sent).strip() if buf else sent
                if len(prospective) > chunk_chars and buf:
                    expanded.append(
                        (
                            domain,
                            {
                                **src,
                                "content": buf,
                                "partial": True,
                                "part": part_idx,
                            },
                        )
                    )
                    tail = buf[-overlap_chars:] if len(buf) > overlap_chars else ""
                    buf = (tail + " " + sent).strip() if tail else sent
                    part_idx += 1
                else:
                    buf = prospective
            if buf:
                expanded.append(
                    (
                        domain,
                        {
                            **src,
                            "content": buf,
                            "partial": True,
                            "part": part_idx,
                        },
                    )
                )

    chunks: list[Chunk] = []
    current_domain: str | None = None
    current_sources: list[dict] = []
    current_chars = 0

    for domain, src in expanded:
        src_len = len(src.get("content", ""))
        needs_flush = (current_domain is not None and current_domain != domain) or (
            current_chars + src_len > chunk_chars
        )
        if needs_flush and current_sources:
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    of_total=0,
                    domain=current_domain or "unknown",
                    sources=current_sources,
                )
            )
            current_sources = []
            current_chars = 0
        current_domain = domain
        current_sources.append(src)
        current_chars += src_len

    if current_sources:
        chunks.append(
            Chunk(
                chunk_index=len(chunks),
                of_total=0,
                domain=current_domain or "unknown",
                sources=current_sources,
            )
        )

    total = len(chunks)
    for c in chunks:
        c["of_total"] = total

    return chunks
