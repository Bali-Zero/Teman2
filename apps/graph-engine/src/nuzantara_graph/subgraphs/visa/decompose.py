"""Query decomposition: B211 pre-filter + LLM-driven sub-question generation."""

from __future__ import annotations

import re
from typing import Any

import structlog

from nuzantara_graph.subgraphs.visa.types import Chunk, SubQuestion

logger = structlog.get_logger()

_B211_PATTERN = re.compile(
    r"(?i)\b(b[-\s]?211[a]?|social[-\s]visit[-\s]visa|visit[-\s]visa[-\s]b[-\s]?211[a]?)\b"
)

_B211_REPLACEMENT = "KITAS/ITAS or e-visa (C-series)"

_B211_NOTE_CONTENT = (
    "The B211 visit visa was abolished. Current options for temporary stay "
    "are C-series e-visas (C1 tourism, C2 business, C7 social-cultural) or "
    "KITAS/ITAS for stays longer than 60 days. This sub-question has been "
    "rewritten accordingly."
)


def rewrite_legacy_visa_terms(query: str) -> tuple[str, Chunk | None]:
    """Rewrite B211/social-visit-visa mentions to current alternatives.

    Returns (rewritten_query, system_note_chunk | None). If no legacy term
    is present, returns (query, None).
    """
    if not _B211_PATTERN.search(query):
        return query, None

    rewritten = _B211_PATTERN.sub(_B211_REPLACEMENT, query)

    note = Chunk(
        doc_id="SYSTEM:b211_rewrite",
        span_start=0,
        span_end=len(_B211_NOTE_CONTENT),
        score=1.0,
        content=_B211_NOTE_CONTENT,
    )

    logger.info("b211_rewrite", original=query[:80], rewritten=rewritten[:80])
    return rewritten, note
