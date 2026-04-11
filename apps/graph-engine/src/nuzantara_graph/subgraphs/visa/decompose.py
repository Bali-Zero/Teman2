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


_DECOMPOSE_SYSTEM = (
    "You are a visa/immigration query planner for Indonesian law. Your job is "
    "to decompose a user question into 1..5 atomic sub-questions that can be "
    "answered independently. Each sub-question should be self-contained and "
    "answerable with a single document lookup. If the original question is "
    "already atomic, return a single sub-question equal to the original."
)

_DECOMPOSE_PROMPT = """\
Decompose the following visa/immigration question into atomic sub-questions.

Rules:
1. Return between 1 and 5 sub-questions.
2. Each sub-question has: idx (0-indexed), text, needs_kb (bool), depends_on (list of idx).
3. depends_on MUST reference only PRIOR sub-questions (idx < current).
4. Prefer parallelizable (empty depends_on) over sequential.
5. Do NOT mention abolished visa types like "B211".
6. Respond in the same language as the question.

Question: {query}

Respond with ONLY a JSON object:
{{
  "sub_questions": [
    {{"idx": 0, "text": "...", "needs_kb": true, "depends_on": []}},
    ...
  ]
}}
"""


def _fallback_sub_questions(query: str) -> list[SubQuestion]:
    return [SubQuestion(idx=0, text=query, needs_kb=True, depends_on=[])]


async def decompose(
    query: str,
    llm: Any,
    max_sub_questions: int = 5,
) -> list[SubQuestion]:
    """LLM-driven decomposition with graceful fallback.

    On any failure (bad JSON, missing API key, empty response), falls back to
    a single sub-question equal to the original query.
    """
    try:
        data = await llm.generate_json(
            prompt=_DECOMPOSE_PROMPT.format(query=query),
            system=_DECOMPOSE_SYSTEM,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("decompose_llm_failed", error=str(e))
        return _fallback_sub_questions(query)

    if not isinstance(data, dict) or "sub_questions" not in data:
        logger.warning("decompose_missing_key", raw=str(data)[:200])
        return _fallback_sub_questions(query)

    raw_items = data.get("sub_questions") or []
    if not raw_items:
        return _fallback_sub_questions(query)

    sub_qs: list[SubQuestion] = []
    for i, item in enumerate(raw_items[:max_sub_questions]):
        if not isinstance(item, dict):
            continue
        try:
            sq = SubQuestion(
                idx=i,
                text=str(item.get("text", "")).strip(),
                needs_kb=bool(item.get("needs_kb", True)),
                depends_on=[
                    int(d)
                    for d in item.get("depends_on", [])
                    if isinstance(d, (int, float)) and int(d) < i
                ],
            )
        except (ValueError, TypeError) as e:
            logger.warning("decompose_invalid_item", item=str(item)[:100], error=str(e))
            continue

        if not sq.text:
            continue

        sub_qs.append(sq)

    if not sub_qs:
        return _fallback_sub_questions(query)

    return sub_qs
