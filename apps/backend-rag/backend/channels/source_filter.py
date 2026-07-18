"""
Source Filter — hide internal RAG source names from client-facing footers.

The agentic RAG pipeline already cites the actual regulation/law inline in
the answer text (e.g. "Source: Permenkumham 11/2024") — that stays as-is.
This module governs a SEPARATE, narrower surface: the "Fonti"/"Sources"
footer appended after the answer, which historically echoed raw internal
chunk metadata (KB doc titles, NotebookLM training-data labels, generic
"Document" placeholders) straight to clients.

Only a source with a genuine PUBLIC url AND a non-internal title is
eligible to appear in that client-facing footer.

Author: Claude Sonnet 5
Date: 2026-07-18
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Case-insensitive substring markers. Matched against "title url" combined,
# so a marker present in either field drops the source.
_INTERNAL_TITLE_MARKERS = (
    "notebooklm",
    "training data",
    "generated training",
    "session",
    "traineddata",
    "internal",
    "chunk",
    "curated_qa",
)

# Titles that carry no real information to a client — always dropped.
_GENERIC_TITLES = {"", "document", "documento"}


def _is_internal(title: str, url: str) -> bool:
    """Return True if title/url looks like an internal RAG artifact."""
    title_lower = title.strip().lower()
    url_lower = url.strip().lower()

    if title_lower in _GENERIC_TITLES:
        return True

    haystack = f"{title_lower} {url_lower}"
    return any(marker in haystack for marker in _INTERNAL_TITLE_MARKERS)


def public_sources(sources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Filter a raw RAG sources list down to genuinely public, client-safe entries.

    A source is KEPT only if:
      - it has a "url" value starting with "http://" or "https://" (a real
        public link — sources without one are internal KB chunks/doc refs
        and are dropped), AND
      - neither its title nor its url matches the internal blocklist
        (notebooklm, training data, generated training, session, traineddata,
        internal, chunk, curated_qa), case-insensitive substring match, AND
      - its title is not empty / "document" / "documento".

    Args:
        sources: Raw sources list from the RAG response (may be None).

    Returns:
        Filtered list safe to show in a client-facing "Fonti"/"Sources"
        footer. Empty list if nothing qualifies — callers should then
        suppress the footer entirely rather than render an empty section.
    """
    if not sources:
        return []

    filtered: list[dict[str, Any]] = []
    for source in sources:
        title = str(source.get("title") or "")
        url = str(source.get("url") or "")

        if not url.startswith(("http://", "https://")):
            continue
        if _is_internal(title, url):
            continue

        filtered.append(source)

    return filtered
