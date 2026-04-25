"""Local deepseek-r1:32b hierarchical bulk reader — Gemini fallback.

Used by :mod:`backend.services.naga.orchestrator` when the primary Gemini 1M
bulk-read path raises (rate limit, timeout, context-length exceeded, network
error). Splits sources via :func:`chunking.hierarchical_chunk`, extracts
structured claims per chunk with ``deepseek-r1:32b`` on local Ollama, then
merges the per-chunk results into a single evidence envelope.

Degraded-mode contract: if **more than half** of the chunks fail (timeout,
Ollama down, JSON parse error), :class:`OllamaFallbackDegraded` is raised so
the orchestrator can surface a hard error instead of returning partial,
possibly misleading evidence. Up to 50 % of chunks may fail silently — we
log each failure but still return a merged envelope.

Concurrency is bounded by an ``asyncio.Semaphore``; default 3 in-flight
chunks keeps RAM pressure reasonable on 16 GB Air while Ollama holds the
model resident.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from backend.llm.ollama_client import MODEL_HEAVY, ollama_chat
from backend.services.naga.readers.chunking import Chunk, hierarchical_chunk

logger = logging.getLogger(__name__)

__all__ = ["OllamaFallbackDegraded", "ollama_bulk_read_hierarchical"]


class OllamaFallbackDegraded(Exception):
    """Raised when >50 % of chunks failed — evidence is too incomplete to use."""


_PROMPT_TEMPLATE: str = (
    "You are a research extraction agent. Extract structured claims from the "
    "sources below, answering these sub-questions: {sub_questions}\n\n"
    "Return ONLY JSON with this shape (no prose, no markdown fences):\n"
    '{{"claims": [{{"claim": "...", "source_url": "...", "confidence": 0.0}}], '
    '"missing": ["sub-question text not answered by the sources"]}}\n\n'
    "Sources (domain={domain}, chunk {idx}/{total}):\n{sources_block}"
)

_CODE_BLOCK_RE: re.Pattern[str] = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL,
)


def _render_sources_block(sources: list[dict]) -> str:
    """Render a chunk's sources into a deterministic textual block."""
    blocks: list[str] = []
    for src in sources:
        url = src.get("url", "")
        title = src.get("title", "")
        content = src.get("content", "")
        blocks.append(f"URL: {url}\nTitle: {title}\n{content}")
    return "\n\n---\n\n".join(blocks)


def _parse_chunk_response(raw: str) -> dict[str, Any]:
    """Parse the model's raw text into ``{"claims": [...], "missing": [...]}``.

    Accepts the response with or without a leading ```json code fence.
    Any parse failure is reported as a chunk error by returning an ``_error``
    sentinel — this mirrors the degraded-mode counting in the caller.
    """
    text = raw.strip()
    match = _CODE_BLOCK_RE.match(text)
    if match:
        text = match.group(1).strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return {"_error": f"json_parse: {exc}"}
    if not isinstance(parsed, dict):
        return {"_error": "json_not_object"}
    return parsed


async def ollama_bulk_read_hierarchical(
    sources: list[dict],
    sub_questions: list[str],
    max_concurrency: int = 3,
    per_chunk_timeout_s: float = 120.0,
    model: str = MODEL_HEAVY,
) -> dict[str, Any]:
    """Extract claims from *sources* via hierarchical chunked calls to Ollama.

    Args:
        sources: Raw source records (same shape as Gemini bulk-read input —
            each provides ``url``, ``title``, ``content``).
        sub_questions: Decomposed sub-questions the model should answer.
        max_concurrency: Maximum number of chunks in flight simultaneously.
            Keep conservative on 16 GB Air while deepseek-r1:32b is resident.
        per_chunk_timeout_s: Per-chunk wall-clock timeout. deepseek-r1:32b
            typically takes 20–40 s for a ~6K-token chunk on Air.
        model: Ollama model tag. Defaults to :data:`MODEL_HEAVY`
            (``deepseek-r1:32b``).

    Returns:
        A dict with keys:
        - ``claims``: merged list of successfully extracted claims.
        - ``missing``: sub-questions *unanimously* reported missing across
          successful chunks (conservative intersection).
        - ``chunks_processed``: number of chunks that returned usable JSON.
        - ``chunks_failed``: number of chunks that timed out, errored, or
          returned unparseable JSON.
        - ``reader``: provenance marker for the caller to record in state.

    Raises:
        OllamaFallbackDegraded: if more than half of the chunks failed, the
            aggregate evidence is considered too unreliable to return.
    """
    chunks: list[Chunk] = hierarchical_chunk(sources)
    if not chunks:
        return {
            "claims": [],
            "missing": list(sub_questions),
            "chunks_processed": 0,
            "chunks_failed": 0,
            "reader": "ollama_deepseek_r1_32b",
        }

    sem = asyncio.Semaphore(max_concurrency)
    sub_q_blob = json.dumps(sub_questions, ensure_ascii=False)

    async def _process(chunk: Chunk) -> dict[str, Any]:
        async with sem:
            prompt = _PROMPT_TEMPLATE.format(
                sub_questions=sub_q_blob,
                domain=chunk["domain"],
                idx=chunk["chunk_index"] + 1,
                total=chunk["of_total"],
                sources_block=_render_sources_block(chunk["sources"]),
            )
            messages = [{"role": "user", "content": prompt}]
            try:
                raw = await asyncio.wait_for(
                    ollama_chat(
                        messages=messages,
                        model=model,
                        temperature=0.1,
                        max_tokens=2_048,
                        timeout=per_chunk_timeout_s,
                    ),
                    timeout=per_chunk_timeout_s,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Ollama chunk %d/%d timed out after %.0fs",
                    chunk["chunk_index"] + 1,
                    chunk["of_total"],
                    per_chunk_timeout_s,
                )
                return {"_error": "timeout"}
            except Exception as exc:  # noqa: BLE001 — degraded-mode safety net
                logger.warning(
                    "Ollama chunk %d/%d raised %s: %s",
                    chunk["chunk_index"] + 1,
                    chunk["of_total"],
                    type(exc).__name__,
                    exc,
                )
                return {"_error": f"{type(exc).__name__}: {exc}"}

            if raw is None:
                logger.warning(
                    "Ollama chunk %d/%d returned None (model unavailable)",
                    chunk["chunk_index"] + 1,
                    chunk["of_total"],
                )
                return {"_error": "ollama_unavailable"}

            return _parse_chunk_response(raw)

    results = await asyncio.gather(*(_process(c) for c in chunks))

    failed = sum(1 for r in results if "_error" in r)
    if failed * 2 > len(chunks):
        raise OllamaFallbackDegraded(
            f"{failed}/{len(chunks)} chunks failed — evidence too incomplete"
        )

    merged_claims: list[dict] = []
    missing_intersect: set[str] | None = None
    for r in results:
        if "_error" in r:
            continue
        merged_claims.extend(r.get("claims", []) or [])
        chunk_missing = set(r.get("missing", []) or [])
        missing_intersect = (
            chunk_missing if missing_intersect is None else missing_intersect & chunk_missing
        )

    merged_missing = sorted(missing_intersect) if missing_intersect else []

    return {
        "claims": merged_claims,
        "missing": merged_missing,
        "chunks_processed": len(chunks) - failed,
        "chunks_failed": failed,
        "reader": "ollama_deepseek_r1_32b",
    }
