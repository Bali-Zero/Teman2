"""Experience service — thin wrapper around cell_core.genome.Genome.

One responsibility: translate Pydantic trajectory records to/from the Genome
SQLite store. Graceful degradation: if cell-core is unavailable at import
time the service reports is_available=False and record/query become no-ops,
so the rest of the backend keeps running (SYMBIOSIS Legge 4).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from backend.services.experience.models import (
    TrajectoryQuery,
    TrajectoryRecord,
    TrajectoryResult,
)

logger = logging.getLogger(__name__)

try:  # Graceful degradation — backend must still boot if cell-core is missing.
    from cell_core.genome import Genome  # type: ignore[import-not-found]

    _GENOME_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised via monkeypatch in tests.
    Genome = None  # type: ignore[assignment]
    _GENOME_AVAILABLE = False
    logger.warning(
        "cell_core.genome not importable — ExperienceService will run in "
        "degraded mode (record/query become no-ops).",
    )


DEFAULT_DB_PATH = os.environ.get(
    "EXPERIENCE_DB_PATH",
    os.path.expanduser("~/.nuzantara/experience.db"),
)


class ExperienceService:
    """Record and query execution trajectories in the Genome store."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._genome: Any = None
        if _GENOME_AVAILABLE and Genome is not None:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            self._genome = Genome(db_path=self._db_path)

    @property
    def is_available(self) -> bool:
        return self._genome is not None

    def record(self, record: TrajectoryRecord) -> dict[str, Any]:
        """Persist a trajectory. Idempotent via trajectory_id upsert."""
        if not self.is_available:
            return {
                "action": "skipped",
                "reason": "genome_unavailable",
                "trajectory_id": record.trajectory_id,
            }
        action = self._genome.record_trajectory(
            cell=record.cell,
            trajectory_id=record.trajectory_id,
            outcome=record.outcome
            if isinstance(record.outcome, str)
            else record.outcome.value,
            procedure=record.procedure,
            tokens=record.tokens,
            duration_ms=record.duration_ms,
            tags=record.tags,
            confidence=record.confidence,
        )
        return {"action": action, "trajectory_id": record.trajectory_id}

    def query(self, request: TrajectoryQuery) -> list[TrajectoryResult]:
        """FTS5 search with optional outcome/cell/tag filters."""
        if not self.is_available:
            return []
        outcome = request.outcome
        if outcome is not None and not isinstance(outcome, str):
            outcome = outcome.value
        rows = self._genome.search_trajectories(
            query=request.query,
            outcome=outcome,
            cell=request.cell,
            tag=request.tag,
            limit=request.limit,
        )
        return [self._row_to_result(r) for r in rows]

    def stats(self, cell: str | None = None) -> dict[str, Any]:
        if not self.is_available:
            return {"total": 0, "by_outcome": {"success": 0, "failure": 0, "partial": 0}}
        return self._genome.trajectory_stats(cell=cell)

    def get_by_id(self, trajectory_id: str) -> TrajectoryResult | None:
        """Fetch one trajectory row by id. Returns None if missing or if the
        row exists but has a non-trajectory type (skill/pattern/scar/insight).
        Used by the router to return 404 vs 200 cleanly."""
        if not self.is_available:
            return None
        row = self._genome.get_trajectory(trajectory_id)
        return self._row_to_result(row) if row is not None else None

    @staticmethod
    def _row_to_result(row: dict[str, Any]) -> TrajectoryResult:
        tags_raw = row.get("tags")
        tags: list[str] = []
        if isinstance(tags_raw, str) and tags_raw:
            try:
                parsed = json.loads(tags_raw)
                if isinstance(parsed, list):
                    tags = [str(t) for t in parsed]
            except json.JSONDecodeError:
                tags = []
        return TrajectoryResult(
            trajectory_id=row["id"],
            cell=row["cell_origin"],
            outcome=row["outcome"],
            procedure=row["procedure"],
            tokens=row.get("tokens"),
            duration_ms=row.get("duration_ms"),
            tags=tags,
            confidence=row["confidence"],
            valid_from=row["valid_from"],
        )
