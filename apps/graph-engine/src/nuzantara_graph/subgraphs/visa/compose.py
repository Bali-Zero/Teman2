"""Final composer with deterministic citation enforcement."""

from __future__ import annotations

import re
from typing import Any

import structlog

from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence

logger = structlog.get_logger()

_CITATION_PATTERN = re.compile(r"\[([^\[\]:]+):(\d+)-(\d+)\]")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_SYSTEM_FALLBACK = (
    "I cannot produce a fully-cited answer for this query. "
    "Please rephrase or contact support for visa assistance."
)

_UNCITABLE_LINE = "(unable to cite this claim; refer to the documents below)"

_COMPOSE_SYSTEM = (
    "You are a visa/immigration expert producing a final cited answer. "
    "EVERY sentence in your response MUST end with a citation in the form "
    "[doc_id:start-end] pointing to one of the provided chunks. Do not "
    "invent citations. Do not use chunks that were not provided. If you "
    "cannot cite a claim, omit it. Respond in the same language as the "
    "user's question."
)

_COMPOSE_PROMPT = """\
User question: {query}

Available evidence chunks (you MAY cite ONLY these):
{chunks}

Write a clear, factual answer to the user's question. EVERY sentence MUST end
with a citation of the form [doc_id:start-end] from the list above.
"""


def _all_chunks(
    evidences: list[NodeEvidence],
    system_notes: list[Chunk],
) -> list[Chunk]:
    out: list[Chunk] = list(system_notes)
    for ev in evidences:
        out.extend(ev.chunks)
    return out


def _format_chunks_for_prompt(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no chunks available)"
    return "\n\n".join(
        f"[{c.doc_id}:{c.span_start}-{c.span_end}] {c.content}"
        for c in chunks[:20]
    )


def _split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _known_doc_ids(chunks: list[Chunk]) -> set[str]:
    return {c.doc_id for c in chunks}


def _auto_attribute(sentence: str, chunks: list[Chunk]) -> str | None:
    """Return a citation from the best-matching chunk if token overlap ≥ 0.5."""
    sent_low = sentence.lower()
    sent_tokens = set(re.findall(r"\w{4,}", sent_low))
    if not sent_tokens:
        return None

    best: tuple[float, Chunk] | None = None
    for c in chunks:
        c_tokens = set(re.findall(r"\w{4,}", c.content.lower()))
        if not c_tokens:
            continue
        overlap = len(sent_tokens & c_tokens)
        ratio = overlap / max(1, len(sent_tokens))
        if ratio >= 0.5 and (best is None or ratio > best[0]):
            best = (ratio, c)

    if best is None:
        return None
    return best[1].citation()


def enforce_citations(text: str, chunks: list[Chunk]) -> str:
    """Deterministic citation linter.

    - Sentences containing a valid citation to a known doc_id are kept.
    - Sentences without a citation but with ≥50% token overlap to a chunk
      receive an auto-attribution.
    - Remaining sentences are replaced with the uncitable-line fallback.
    - If every sentence becomes the uncitable line, return the system
      fallback.
    """
    if not chunks:
        return _SYSTEM_FALLBACK

    known = _known_doc_ids(chunks)
    sentences = _split_sentences(text)
    if not sentences:
        return _SYSTEM_FALLBACK

    approved: list[str] = []
    for sentence in sentences:
        matches = _CITATION_PATTERN.findall(sentence)
        valid_citation = any(m[0] in known for m in matches)

        if valid_citation:
            approved.append(sentence)
            continue

        attribution = _auto_attribute(sentence, chunks)
        if attribution:
            if sentence.endswith((".", "!", "?")):
                approved.append(f"{sentence[:-1]} {attribution}{sentence[-1]}")
            else:
                approved.append(f"{sentence} {attribution}")
            continue

        approved.append(_UNCITABLE_LINE)

    if all(s == _UNCITABLE_LINE for s in approved):
        return _SYSTEM_FALLBACK

    return " ".join(approved)


async def compose(
    query: str,
    evidences: list[NodeEvidence],
    system_notes: list[Chunk],
    llm: Any,
) -> str:
    """Produce the final cited answer."""
    chunks = _all_chunks(evidences, system_notes)

    if not chunks:
        logger.info("compose_no_chunks")
        return _SYSTEM_FALLBACK

    prompt = _COMPOSE_PROMPT.format(
        query=query,
        chunks=_format_chunks_for_prompt(chunks),
    )

    try:
        response = await llm.generate(
            prompt=prompt,
            system=_COMPOSE_SYSTEM,
            temperature=0.0,
        )
        raw = getattr(response, "content", str(response))
    except Exception as e:
        logger.warning("compose_llm_failed", error=str(e))
        return _SYSTEM_FALLBACK

    return enforce_citations(raw, chunks)
