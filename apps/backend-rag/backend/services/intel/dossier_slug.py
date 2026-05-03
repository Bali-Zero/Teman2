"""Deterministic slug + topic-category hint for dossier compilation.

Same philosophy as ``publisher.mdx_template.build_slug``: URL-safe ASCII,
bounded length, with a short suffix that prevents collisions when the
same title appears twice in history.

For dossiers the suffix is the first 8 hex chars of the anchor signal_id,
so re-runs over the same trend produce the same slug → upsert semantics
in ``IntelRepository.upsert_dossier``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

from backend.services.intel.dossier_models import TopicCategory

_MAX_TOPIC_CHARS = 60


_CATEGORY_KEYWORDS: dict[TopicCategory, tuple[str, ...]] = {
    TopicCategory.VISA: (
        "visa", "kitas", "kitap", "b211", "b211a", "c1", "c2", "c6", "c7",
        "imigrasi", "visto", "permenkumham", "investor visa",
    ),
    TopicCategory.TAX: (
        "pph", "ppn", "pbb", "djp", "coretax", "tarif", "imposta", "ppjk",
        "wajib pajak", "tax",
    ),
    TopicCategory.KBLI: (
        "kbli", "oss", "nib", "sektor", "klasifikasi", "business classification",
    ),
    TopicCategory.PROPERTY: (
        "hak pakai", "hak milik", "hak guna", "shgb", "sertifikat",
        "property", "villa", "notaris", "land",
    ),
    TopicCategory.COMPLIANCE: (
        "lkpm", "compliance", "sanksi", "enforcement", "audit", "kepatuhan",
    ),
    TopicCategory.FINANCE: (
        "bank indonesia", "ojk", "kebijakan moneter", "finance", "banking",
    ),
    TopicCategory.CRYPTO: (
        "crypto", "bitcoin", "nft", "bappebti", "exchange",
    ),
    TopicCategory.CULTURAL: (
        "upacara", "nyepi", "galungan", "kuningan", "cultural", "adat",
    ),
    TopicCategory.MACRO: (
        "apbn", "inflasi", "pertumbuhan", "gdp", "macro", "fiscal",
    ),
}


def build_dossier_slug(topic: str, anchor_id: UUID | str | None = None) -> str:
    """URL-safe deterministic slug.

    topic   → lowercase, non-alnum → hyphen, collapse, trim to 60
    anchor_id → first 8 hex chars (no hyphens) appended as suffix
    """
    normalized = re.sub(r"[^a-z0-9]+", "-", (topic or "").lower()).strip("-")
    if not normalized:
        normalized = "trend"
    if len(normalized) > _MAX_TOPIC_CHARS:
        normalized = normalized[:_MAX_TOPIC_CHARS].rstrip("-")

    if anchor_id is None:
        return normalized

    suffix = str(anchor_id).replace("-", "")[-8:]
    return f"{normalized}-{suffix}"


def categorize_topic(topic: str) -> TopicCategory:
    """Heuristic keyword match → TopicCategory. Falls back to OTHER."""
    lower = (topic or "").lower()
    if not lower:
        return TopicCategory.OTHER
    # First match wins — order matters: more specific categories come first.
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return TopicCategory.OTHER


def flatten_topics(topics: Iterable[str]) -> str:
    """Join a sequence of short topic strings into one query-friendly title."""
    parts = [t.strip() for t in topics if t and t.strip()]
    return " · ".join(parts[:4])
