"""
Low-confidence emitter — emits rag.low_confidence events to bridge_outbox.

When the RAG produces an answer with evidence_score < 0.3, this helper writes
an event to the outbox so the Pro can pull it and dispatch enrichment agents.

Single responsibility: just the threshold check + dedup + outbox write.
Defensive: any failure is swallowed (logger.error) — must never break the RAG.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from backend.services.bridge.outbox import insert_outbox_event

logger = logging.getLogger(__name__)


# Below this threshold the RAG considers itself uncertain.
# Matches the design spec §3 confidence routing decisions.
LOW_CONFIDENCE_THRESHOLD: float = 0.3

# Dedup window: don't re-emit the same query for 24h.
LOW_CONFIDENCE_DEDUP_S: int = 24 * 3600

# Max query length stored in payload (avoid bloat for very long inputs).
QUERY_TRUNCATE_CHARS: int = 500

# In-memory dedup map: query_hash -> monotonic timestamp.
# Process-local; resets on restart (acceptable for an enrichment trigger).
_low_confidence_dedup: dict[str, float] = {}


async def maybe_emit_low_confidence(
    pool: Any,
    query: str,
    confidence: float,
) -> None:
    """If confidence < LOW_CONFIDENCE_THRESHOLD and we haven't seen this query
    in the last 24h, write a rag.low_confidence event to bridge_outbox.

    Args:
        pool: asyncpg pool (or None — gracefully skips if missing)
        query: user query that produced low confidence
        confidence: evidence/confidence score in [0.0, 1.0]

    Failures are logged and swallowed — RAG path must never fail because of
    an outbox write.
    """
    if confidence >= LOW_CONFIDENCE_THRESHOLD:
        return

    if pool is None:
        return

    # Dedup by query content hash, 24h window
    key = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    now = time.monotonic()
    # Prune stale entries inline (cheap, keeps map bounded)
    stale = [k for k, t in _low_confidence_dedup.items() if now - t > LOW_CONFIDENCE_DEDUP_S]
    for k in stale:
        del _low_confidence_dedup[k]
    if key in _low_confidence_dedup:
        return
    _low_confidence_dedup[key] = now

    try:
        async with pool.acquire() as conn:
            await insert_outbox_event(
                conn,
                event_type="rag.low_confidence",
                payload={
                    "query": query[:QUERY_TRUNCATE_CHARS],
                    "confidence": float(confidence),
                    "query_hash": key,
                },
            )
            logger.debug(
                "Emitted rag.low_confidence for query_hash=%s confidence=%.2f",
                key,
                confidence,
            )
    except Exception as e:
        logger.error("Failed to emit rag.low_confidence event: %s", e)
