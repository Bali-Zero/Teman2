"""Pattern Index — FAISS-backed short-term pattern matching.

Stores past (situation → action) pairs as dense vectors.
When a new situation arrives, finds the closest historical match.
If similarity > threshold, CELL can reuse the past decision
without calling any LLM (free, <1ms).

Vector format: [health_one_hot(3), response_time_norm, budget_pct_norm]
  health_one_hot: [1,0,0]=green, [0,1,0]=yellow, [0,0,1]=red
  response_time_norm: ms / 10000.0 (clipped to 1.0)
  budget_pct_norm: 0.0 – 1.0
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger("cell.memory.pattern")

try:
    import faiss  # type: ignore[import-untyped]
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False
    logger.warning("faiss-cpu not installed — PatternIndex disabled")

_VECTOR_DIM = 5  # [green, yellow, red, rt_norm, budget_norm]
_SIMILARITY_THRESHOLD = 0.97  # cosine similarity — very tight match required


@dataclass
class PatternEntry:
    action: str
    reason: str
    confidence: float
    tier_used: int
    health_status: str
    response_time_ms: int
    budget_pct: float
    timestamp: float = field(default_factory=time.time)


def _encode(health_status: str, response_time_ms: int, budget_pct: float) -> np.ndarray:
    """Encode a situation into a 5-dim float32 vector."""
    health = health_status.lower()
    one_hot = [
        1.0 if health == "green" else 0.0,
        1.0 if health == "yellow" else 0.0,
        1.0 if health == "red" else 0.0,
    ]
    rt_norm = min(response_time_ms / 10_000.0, 1.0)
    budget_norm = min(max(budget_pct, 0.0), 1.0)
    vec = np.array(one_hot + [rt_norm, budget_norm], dtype=np.float32)
    # L2-normalize for cosine similarity via IndexFlatIP
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


class PatternIndex:
    """In-memory FAISS index for past (situation → action) patterns.

    Thread-safe for single asyncio event loop (no locks needed).
    Max 500 patterns — old ones evicted when full.
    """

    MAX_SIZE = 500

    def __init__(self) -> None:
        self._entries: list[PatternEntry] = []
        self._index: Any = None  # faiss.IndexFlatIP or None
        self._dirty = False  # rebuild index on next search

        if _FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(_VECTOR_DIM)
            logger.info("PatternIndex initialized (FAISS IndexFlatIP, dim=5)")
        else:
            logger.info("PatternIndex disabled (faiss not available)")

    def add(
        self,
        health_status: str,
        response_time_ms: int,
        budget_pct: float,
        action: str,
        reason: str,
        confidence: float,
        tier_used: int,
    ) -> None:
        """Record a resolved situation → action pair."""
        if not _FAISS_AVAILABLE or self._index is None:
            return

        entry = PatternEntry(
            action=action,
            reason=reason,
            confidence=confidence,
            tier_used=tier_used,
            health_status=health_status,
            response_time_ms=response_time_ms,
            budget_pct=budget_pct,
        )
        self._entries.append(entry)

        # Evict oldest if over capacity
        if len(self._entries) > self.MAX_SIZE:
            self._entries = self._entries[-self.MAX_SIZE:]
            self._dirty = True  # need full rebuild
        else:
            # Fast path: add single vector
            vec = _encode(health_status, response_time_ms, budget_pct)
            self._index.add(vec.reshape(1, -1))

    def _rebuild(self) -> None:
        """Rebuild FAISS index from scratch (after eviction)."""
        if not _FAISS_AVAILABLE or self._index is None:
            return
        self._index.reset()
        if not self._entries:
            return
        vecs = np.stack([
            _encode(e.health_status, e.response_time_ms, e.budget_pct)
            for e in self._entries
        ])
        self._index.add(vecs)
        self._dirty = False
        logger.debug(f"PatternIndex rebuilt: {len(self._entries)} patterns")

    def find_similar(
        self,
        health_status: str,
        response_time_ms: int,
        budget_pct: float,
    ) -> PatternEntry | None:
        """Find the most similar past situation.

        Returns PatternEntry if cosine similarity >= threshold, else None.
        """
        if not _FAISS_AVAILABLE or self._index is None or not self._entries:
            return None

        if self._dirty:
            self._rebuild()

        if self._index.ntotal == 0:
            return None

        query = _encode(health_status, response_time_ms, budget_pct).reshape(1, -1)
        scores, indices = self._index.search(query, 1)
        score = float(scores[0][0])
        idx = int(indices[0][0])

        if idx < 0 or idx >= len(self._entries):
            return None

        if score >= _SIMILARITY_THRESHOLD:
            entry = self._entries[idx]
            logger.info(
                f"PatternIndex HIT: similarity={score:.4f} "
                f"→ action={entry.action} (was tier {entry.tier_used})"
            )
            return entry

        logger.debug(f"PatternIndex MISS: best similarity={score:.4f} < {_SIMILARITY_THRESHOLD}")
        return None

    @property
    def size(self) -> int:
        return len(self._entries)
