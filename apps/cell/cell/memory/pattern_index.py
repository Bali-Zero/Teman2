"""Pattern Index — FAISS-backed short-term pattern matching.

Stores past (situation → action) pairs as dense vectors.
When a new situation arrives, finds the closest historical match.
If similarity > threshold, CELL can reuse the past decision
without calling any LLM (free, <1ms).

Vector format (8 dims):
  [green, yellow, red, rt_norm, budget_norm, db_ok, qdrant_ok, error_rate_norm]
  health_one_hot: [1,0,0]=green, [0,1,0]=yellow, [0,0,1]=red
  response_time_norm: ms / 10000.0 (clipped to 1.0)
  budget_pct_norm: 0.0 – 1.0
  db_ok: 1.0 if DB connected, 0.0 otherwise
  qdrant_ok: 1.0 if Qdrant healthy, 0.0 otherwise
  error_rate_norm: errors_in_5min / 10.0 (clipped to 1.0)
"""
import asyncio
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

_VECTOR_DIM = 8  # [green, yellow, red, rt_norm, budget_norm, db_ok, qdrant_ok, error_rate_norm]
_SIMILARITY_THRESHOLD = 0.75  # cosine similarity — covers sensor variation (db_ok/qdrant_ok)


@dataclass
class PatternEntry:
    action: str
    reason: str
    confidence: float
    tier_used: int
    health_status: str
    response_time_ms: int
    budget_pct: float
    db_ok: float = 1.0
    qdrant_ok: float = 1.0
    error_rate_norm: float = 0.0
    timestamp: float = field(default_factory=time.time)


def _encode(
    health_status: str,
    response_time_ms: int,
    budget_pct: float,
    db_ok: float = 1.0,
    qdrant_ok: float = 1.0,
    error_rate_norm: float = 0.0,
) -> np.ndarray:
    """Encode a situation into an 8-dim float32 vector."""
    health = health_status.lower()
    one_hot = [
        1.0 if health == "green" else 0.0,
        1.0 if health == "yellow" else 0.0,
        1.0 if health == "red" else 0.0,
    ]
    rt_norm = min(response_time_ms / 10_000.0, 1.0)
    budget_norm = min(max(budget_pct, 0.0), 1.0)
    vec = np.array(
        one_hot + [rt_norm, budget_norm, float(db_ok), float(qdrant_ok), float(error_rate_norm)],
        dtype=np.float32,
    )
    # L2-normalize for cosine similarity via IndexFlatIP
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


class PatternIndex:
    """FAISS index for past (situation → action) patterns.

    Backed by PostgreSQL for persistence across restarts.
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
            logger.info("PatternIndex initialized (FAISS IndexFlatIP, dim=8)")
        else:
            logger.info("PatternIndex disabled (faiss not available)")

    async def load_from_db(self) -> int:
        """Load the most recent 500 patterns from DB into memory.

        Returns the count of patterns loaded.
        """
        from cell.core.db import load_patterns
        rows = await load_patterns(limit=self.MAX_SIZE)
        if not rows:
            logger.info("PatternIndex: no patterns in DB to load")
            return 0

        self._entries = []
        for row in rows:
            entry = PatternEntry(
                action=row["action"],
                reason=row["reason"],
                confidence=float(row["confidence"]),
                tier_used=int(row["tier_used"]),
                health_status=row["health_status"],
                response_time_ms=int(row["response_time_ms"]),
                budget_pct=float(row["budget_pct"]),
                timestamp=row["created_at"].timestamp() if row.get("created_at") else time.time(),
            )
            self._entries.append(entry)

        self._dirty = True  # rebuild index from loaded entries
        if _FAISS_AVAILABLE and self._index is not None:
            self._rebuild()

        logger.info(f"PatternIndex: {len(self._entries)} patterns loaded from DB")
        return len(self._entries)

    async def persist_to_db(self, entry: PatternEntry) -> None:
        """Persist a single pattern entry to the DB (fire-and-forget)."""
        from cell.core.db import save_pattern
        await save_pattern(
            health_status=entry.health_status,
            response_time_ms=entry.response_time_ms,
            budget_pct=entry.budget_pct,
            action=entry.action,
            reason=entry.reason,
            confidence=entry.confidence,
            tier_used=entry.tier_used,
        )

    def add(
        self,
        health_status: str,
        response_time_ms: int,
        budget_pct: float,
        action: str,
        reason: str,
        confidence: float,
        tier_used: int,
        db_ok: float = 1.0,
        qdrant_ok: float = 1.0,
        error_rate_norm: float = 0.0,
    ) -> None:
        """Record a resolved situation → action pair.

        Adds to FAISS in-memory index synchronously, then schedules
        async DB persistence as a fire-and-forget task.
        """
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
            db_ok=db_ok,
            qdrant_ok=qdrant_ok,
            error_rate_norm=error_rate_norm,
        )
        self._entries.append(entry)

        # Evict oldest if over capacity
        if len(self._entries) > self.MAX_SIZE:
            self._entries = self._entries[-self.MAX_SIZE:]
            self._dirty = True  # need full rebuild
        else:
            # Fast path: add single vector
            vec = _encode(health_status, response_time_ms, budget_pct, db_ok, qdrant_ok, error_rate_norm)
            self._index.add(vec.reshape(1, -1))

        # Fire-and-forget DB persistence
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.persist_to_db(entry))
        except RuntimeError:
            pass  # No running loop — skip persistence (e.g. during tests)

    def _rebuild(self) -> None:
        """Rebuild FAISS index from scratch (after eviction or load)."""
        if not _FAISS_AVAILABLE or self._index is None:
            return
        self._index.reset()
        if not self._entries:
            self._dirty = False
            return
        vecs = np.stack([
            _encode(e.health_status, e.response_time_ms, e.budget_pct, e.db_ok, e.qdrant_ok, e.error_rate_norm)
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
        db_ok: float = 1.0,
        qdrant_ok: float = 1.0,
        error_rate_norm: float = 0.0,
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

        query = _encode(health_status, response_time_ms, budget_pct, db_ok, qdrant_ok, error_rate_norm).reshape(1, -1)
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
