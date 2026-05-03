"""Skill Registry service — thin wrapper around cell_core.genome.Genome.

Mirrors ExperienceService for trajectories, but:
- Filters rows by ``type='skill'`` (or ``type='pattern'`` later if we promote
  patterns to first-class alongside skills).
- Exposes the tier column via SkillQuery + get_top_skills.
- Reads merge-proposals from the shared jsonl (written by Day 5 job).

Graceful degradation: if cell-core can't be imported, ``is_available`` is
False and record/query/stats return safe empty defaults.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from backend.services.skill.models import (
    SkillQuery,
    SkillRecord,
    SkillResult,
    SkillScope,
    SkillTier,
)

logger = logging.getLogger(__name__)

try:
    from cell_core.genome import Genome  # type: ignore[import-not-found]

    _GENOME_AVAILABLE = True
except ImportError:  # pragma: no cover
    Genome = None  # type: ignore[assignment]
    _GENOME_AVAILABLE = False
    logger.warning(
        "cell_core.genome not importable — SkillService will run in "
        "degraded mode (record/query become no-ops).",
    )


DEFAULT_DB_PATH = os.environ.get(
    "EXPERIENCE_DB_PATH",
    os.path.expanduser("~/.nuzantara/experience.db"),
)

# Shared artefact path for the Day 5 merge-proposals job. Kept alongside
# escalations rather than in a tracked dir — content is machine-generated
# noise that shouldn't pollute git history.
MERGE_PROPOSALS_PATH = os.environ.get(
    "SKILL_MERGE_PROPOSALS_PATH",
    os.path.expanduser("~/.nuzantara/skill_merge_proposals.jsonl"),
)


class SkillService:
    """Record and query reusable skills in the shared Genome store."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._genome: Any = None
        if _GENOME_AVAILABLE and Genome is not None:
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            self._genome = Genome(db_path=self._db_path)

    @property
    def is_available(self) -> bool:
        return self._genome is not None

    # ─── write ──────────────────────────────────────────────────────

    def record(self, record: SkillRecord) -> dict[str, Any]:
        """Persist a skill. Idempotent via skill_id upsert (tier preserved)."""
        if not self.is_available:
            return {
                "action": "skipped",
                "reason": "genome_unavailable",
                "skill_id": record.skill_id,
            }
        scope = record.scope.value if hasattr(record.scope, "value") else record.scope
        action = self._genome.record_skill(
            cell=record.cell,
            skill_id=record.skill_id,
            procedure=record.procedure,
            precondition=record.precondition,
            success_criterion=record.success_criterion,
            confidence=record.confidence,
            scope=scope,
            entry_type="skill",
        )
        return {"action": action, "skill_id": record.skill_id}

    # ─── read ───────────────────────────────────────────────────────

    def query(self, request: SkillQuery) -> list[SkillResult]:
        """FTS5 search + tier + cell + min_confidence filters.

        Implemented by running Genome.search then filtering in-memory — the
        search API returns all types, we keep only skills. For production
        scale we can push the tier/type/confidence filters down; current
        corpus is small enough to filter client-side.
        """
        if not self.is_available:
            return []
        rows = self._genome.search(query=request.query, limit=request.limit * 4)
        out: list[SkillResult] = []
        tier_filter = request.tier.value if hasattr(request.tier, "value") else request.tier
        for row in rows:
            if row.get("type") != "skill":
                continue
            if request.cell and row.get("cell_origin") != request.cell:
                continue
            if tier_filter is not None and row.get("tier") != tier_filter:
                continue
            if row.get("confidence", 0.0) < request.min_confidence:
                continue
            out.append(self._row_to_result(row))
            if len(out) >= request.limit:
                break
        return out

    def stats(self) -> dict[str, Any]:
        """Aggregate counts by tier + cell + average confidence.

        Does not take a cell parameter: global view is the common dashboard
        shape. Per-cell slices are derivable from the ``by_cell`` map.
        """
        if not self.is_available:
            return {
                "total": 0,
                "by_tier": {"tier1": 0, "tier2": 0, "untiered": 0},
                "by_cell": {},
                "avg_confidence": 0.0,
            }
        import sqlite3  # Local import keeps this file safe to import without sqlite3
        today = self._today()
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            base_where = (
                "WHERE type='skill' AND (valid_to IS NULL OR valid_to > ?)"
            )
            total = conn.execute(
                f"SELECT COUNT(*) FROM genome {base_where}", (today,),
            ).fetchone()[0]
            avg_conf = conn.execute(
                f"SELECT COALESCE(AVG(confidence), 0) FROM genome {base_where}",
                (today,),
            ).fetchone()[0]
            by_tier = {"tier1": 0, "tier2": 0, "untiered": 0}
            for r in conn.execute(
                f"SELECT tier, COUNT(*) c FROM genome {base_where} GROUP BY tier",
                (today,),
            ).fetchall():
                key = r["tier"] if r["tier"] in ("tier1", "tier2") else "untiered"
                by_tier[key] += r["c"]
            by_cell = {
                r["cell_origin"]: r["c"]
                for r in conn.execute(
                    f"SELECT cell_origin, COUNT(*) c FROM genome {base_where} "
                    f"GROUP BY cell_origin ORDER BY c DESC",
                    (today,),
                ).fetchall()
            }
        finally:
            conn.close()
        return {
            "total": total,
            "by_tier": by_tier,
            "by_cell": by_cell,
            "avg_confidence": round(avg_conf, 3),
        }

    def get_top_skills(
        self, tier: SkillTier | str = SkillTier.TIER1, limit: int = 20,
    ) -> list[SkillResult]:
        """Return active skills at the requested tier, ordered by confidence."""
        if not self.is_available:
            return []
        tier_value = tier.value if hasattr(tier, "value") else tier
        import sqlite3
        today = self._today()
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT * FROM genome
                   WHERE type='skill'
                     AND tier = ?
                     AND (valid_to IS NULL OR valid_to > ?)
                   ORDER BY confidence DESC, uses DESC
                   LIMIT ?""",
                (tier_value, today, limit),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_result(dict(r)) for r in rows]

    def get_by_id(self, skill_id: str) -> SkillResult | None:
        """Fetch one skill row by id. Returns None for missing or non-skill rows."""
        if not self.is_available:
            return None
        import sqlite3
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM genome WHERE id = ? AND type = 'skill'",
                (skill_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_result(dict(row)) if row is not None else None

    def merge_proposals(self) -> list[dict[str, Any]]:
        """Read the jsonl of merge-proposals emitted by the Day 5 job.

        Empty list when the file does not exist yet — the job runs weekly.
        """
        if not os.path.exists(MERGE_PROPOSALS_PATH):
            return []
        proposals: list[dict[str, Any]] = []
        with open(MERGE_PROPOSALS_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    proposals.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("skip malformed merge-proposal line: %r", line[:80])
        return proposals

    # ─── helpers ────────────────────────────────────────────────────

    @staticmethod
    def _today() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def _row_to_result(row: dict[str, Any]) -> SkillResult:
        tier_raw = row.get("tier")
        tier = SkillTier(tier_raw) if tier_raw in ("tier1", "tier2") else None
        scope_raw = row.get("scope") or "Project"
        scope = SkillScope(scope_raw) if scope_raw in ("Project", "Personal") else SkillScope.PROJECT
        return SkillResult(
            skill_id=row["id"],
            cell=row["cell_origin"],
            procedure=row["procedure"],
            precondition=row.get("precondition") or "",
            success_criterion=row.get("success_criterion") or "",
            confidence=row["confidence"],
            tier=tier,
            uses=row.get("uses", 0) or 0,
            scope=scope,
            valid_from=row["valid_from"],
        )
