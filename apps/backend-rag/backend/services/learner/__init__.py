"""Learner — closes the War Room 2.0 loop (M14).

Reference: docs/war-room-2.0-design.md §10.

Cycle (design §10):
    1. Compute composite score per post after T+72h
    2. score > p70 → record skill in genome
    3. score < p20 OR rejected_by_zero → record scar in cicatrix
    4. Inject memoria_episodica (≤2000 chars) into next Consiglio run

Cron: nightly 03:00 WITA (design §2 cadence).
"""

from backend.services.learner.genome_adapter import (
    GenomeAdapter,
    GenomeProtocol,
    ScarEntry,
    SkillEntry,
)
from backend.services.learner.injection_builder import (
    MemoriaEpisodicaBuilder,
)
from backend.services.learner.learner_orchestrator import (
    LearnerOrchestrator,
    LearnerResult,
    LearningDecision,
)
from backend.services.learner.score_calculator import (
    CompositeScore,
    ScoreCalculator,
    ScoreInputs,
)

__all__ = [
    "CompositeScore",
    "GenomeAdapter",
    "GenomeProtocol",
    "LearnerOrchestrator",
    "LearnerResult",
    "LearningDecision",
    "MemoriaEpisodicaBuilder",
    "ScarEntry",
    "ScoreCalculator",
    "ScoreInputs",
    "SkillEntry",
]
