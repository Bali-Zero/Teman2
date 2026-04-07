# apps/cell/cell/lifecycle/achievement_gate.py
"""AchievementGate — wraps Maturation with achievement-based phase gating.

Two-layer gating:
1. Age floor (inviolable) — from Maturation.phase
2. Achievement requirements — must be met to hold the age-based phase

Escape hatch: if age exceeds the age floor by _ESCAPE_HATCH_DAYS,
auto-promote with a warning log (prevents permanent stall).
"""
import logging
from typing import Any

from cell.lifecycle.maturation import LifecyclePhase, Maturation

logger = logging.getLogger("cell.lifecycle")

# Rank map — NEVER use >= on LifecyclePhase (str enum = alphabetical).
_PHASE_RANK: dict[LifecyclePhase, int] = {
    LifecyclePhase.EMBRIONE: 0,
    LifecyclePhase.NEONATO: 1,
    LifecyclePhase.GIOVANE: 2,
    LifecyclePhase.ADULTO: 3,
    LifecyclePhase.ANZIANO: 4,
}

_RANK_TO_PHASE: dict[int, LifecyclePhase] = {v: k for k, v in _PHASE_RANK.items()}

# Minimum age in days to even be considered for a phase (hard floor).
_AGE_FLOORS: dict[LifecyclePhase, int] = {
    LifecyclePhase.EMBRIONE: 0,
    LifecyclePhase.NEONATO: 4,
    LifecyclePhase.GIOVANE: 15,
    LifecyclePhase.ADULTO: 31,
    LifecyclePhase.ANZIANO: 180,
}

# Achievement requirements for entering a phase.
# Phases not listed (embrione, neonato) have no achievement gate.
_REQUIREMENTS: dict[str, dict[str, int | float]] = {
    "giovane": {"episodes_recorded": 10},
    "adulto": {
        "episodes_with_outcome": 50,
        "skills_in_library": 10,
        "goals_completed": 5,
    },
    "anziano": {
        "skills_stable_30d": 20,
        "skills_fitness_above_06": 0.7,
        "journal_continuity_days": 90,
    },
}

# After age_floor + this many days, auto-promote even without achievements.
_ESCAPE_HATCH_DAYS: int = 14


class AchievementGate:
    """Wraps Maturation with achievement-based phase gating.

    Parameters
    ----------
    base : Maturation
        The age-based lifecycle tracker.
    pool : asyncpg.Pool (or mock)
        Database connection pool for achievement queries.
    self_model : optional
        SelfModel instance (unused now, reserved for future introspection).
    """

    def __init__(
        self,
        base: Maturation,
        pool: Any,
        self_model: Any = None,
    ) -> None:
        self._base = base
        self._pool = pool
        self._self_model = self_model

    # ------------------------------------------------------------------
    # Delegation — backward-compatible pass-through to Maturation
    # ------------------------------------------------------------------

    @property
    def phase(self) -> LifecyclePhase:
        """Raw age-based phase (no achievement check)."""
        return self._base.phase

    @property
    def age_days(self) -> int:
        return self._base.age_days

    def can_act(self) -> bool:
        return self._base.can_act()

    def can_dream(self) -> bool:
        return self._base.can_dream()

    def can_reason_deep(self) -> bool:
        return self._base.can_reason_deep()

    def action_confidence_threshold(self) -> float:
        return self._base.action_confidence_threshold()

    def to_prompt_context(self) -> str:
        return self._base.to_prompt_context()

    def log_phase(self) -> None:
        return self._base.log_phase()

    # ------------------------------------------------------------------
    # Achievement queries
    # ------------------------------------------------------------------

    async def achievements(self) -> dict[str, int | float]:
        """Query all 7 achievement metrics from the database."""
        async with self._pool.acquire() as conn:
            episodes_recorded: int = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_episodes"
            )

            episodes_with_outcome: int = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_episodes "
                "WHERE outcome IN ('success', 'failure')"
            )

            skills_in_library: int = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_skills WHERE status = 'active'"
            )

            goals_completed: int = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_goals WHERE status = 'resolved'"
            )

            skills_stable_30d: int = await conn.fetchval(
                "SELECT COUNT(DISTINCT s.id) FROM cell_skills s "
                "WHERE s.status = 'active' "
                "AND s.created_at < NOW() - INTERVAL '30 days' "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM cell_skill_audit a "
                "  WHERE a.skill_id = s.id "
                "  AND a.action IN ('rolled_back', 'apoptosed') "
                "  AND a.created_at > NOW() - INTERVAL '30 days'"
                ")"
            )

            skills_fitness_above_06: float = await conn.fetchval(
                "SELECT COALESCE("
                "  AVG(CASE WHEN fitness > 0.6 THEN 1.0 ELSE 0.0 END), 0.0"
                ") FROM cell_skills WHERE status = 'active'"
            )

            journal_continuity_days: int = await conn.fetchval(
                "SELECT COUNT(DISTINCT journal_date) FROM cell_journal "
                "WHERE journal_date > CURRENT_DATE - INTERVAL '90 days'"
            )

        return {
            "episodes_recorded": episodes_recorded,
            "episodes_with_outcome": episodes_with_outcome,
            "skills_in_library": skills_in_library,
            "goals_completed": goals_completed,
            "skills_stable_30d": skills_stable_30d,
            "skills_fitness_above_06": skills_fitness_above_06,
            "journal_continuity_days": journal_continuity_days,
        }

    # ------------------------------------------------------------------
    # Effective phase (with achievement gating)
    # ------------------------------------------------------------------

    async def effective_phase(
        self,
    ) -> tuple[LifecyclePhase, dict[str, Any]]:
        """Determine effective phase after achievement gating.

        Returns
        -------
        (phase, info) where info contains:
            - achievements: dict of all 7 metrics
            - missing_for_next: list of human-readable missing requirements
        """
        base_phase = self._base.phase
        base_rank = _PHASE_RANK[base_phase]
        achv = await self.achievements()

        # Walk backward from the age-based phase.
        effective_rank = base_rank
        for rank in range(base_rank, 1, -1):  # stop at 2 (giovane min)
            phase_name = _RANK_TO_PHASE[rank].value
            reqs = _REQUIREMENTS.get(phase_name)
            if reqs is None:
                # No requirements for this phase — it holds.
                continue
            if not self._meets_requirements(achv, reqs):
                # Check escape hatch before demoting.
                phase_floor = _AGE_FLOORS[_RANK_TO_PHASE[rank]]
                if self._base.age_days >= phase_floor + _ESCAPE_HATCH_DAYS:
                    logger.warning(
                        "AchievementGate ESCAPE HATCH: age %d >= floor %d + %d, "
                        "auto-promoting to %s despite unmet requirements",
                        self._base.age_days,
                        phase_floor,
                        _ESCAPE_HATCH_DAYS,
                        phase_name,
                    )
                else:
                    effective_rank = rank - 1
            # If requirements met or escape hatch triggered, keep the rank.

        effective = _RANK_TO_PHASE[effective_rank]
        missing = self._missing_for_next(achv, effective)
        return effective, {"achievements": achv, "missing_for_next": missing}

    async def missing_for_next_phase(self) -> list[str]:
        """Convenience: return only the missing requirements list."""
        _, info = await self.effective_phase()
        return info["missing_for_next"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _meets_requirements(
        achv: dict[str, int | float],
        reqs: dict[str, int | float],
    ) -> bool:
        """Check if achievements meet all requirements."""
        for key, threshold in reqs.items():
            if achv.get(key, 0) < threshold:
                return False
        return True

    @staticmethod
    def _missing_for_next(
        achv: dict[str, int | float],
        current_phase: LifecyclePhase,
    ) -> list[str]:
        """List human-readable descriptions of what's missing for the next phase."""
        current_rank = _PHASE_RANK[current_phase]
        next_rank = current_rank + 1
        if next_rank not in _RANK_TO_PHASE:
            return []  # Already at max phase.
        next_phase = _RANK_TO_PHASE[next_rank]
        reqs = _REQUIREMENTS.get(next_phase.value)
        if reqs is None:
            return []  # Next phase has no achievement gate.
        missing: list[str] = []
        for key, threshold in reqs.items():
            current_val = achv.get(key, 0)
            if current_val < threshold:
                missing.append(
                    f"{key}: {current_val}/{threshold}"
                )
        return missing
