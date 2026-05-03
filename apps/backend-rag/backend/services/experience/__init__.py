"""Experience Library — service wrapper around cell-core Genome trajectories.

Organo: records/queries execution trajectories (success|failure|partial) on the
canonical Genome store. Complements skill/pattern/scar entries — episodes, not
consolidated skills.

Produces: Genome rows (type='trajectory') in the shared SQLite KB.
Consumes: /api/experience/record calls from cells post-run + /api/experience/query
          calls from Thinkers before reasoning from scratch (SYMBIOSIS Pilastro 2).
"""
from backend.services.experience.models import (
    TrajectoryOutcome,
    TrajectoryQuery,
    TrajectoryRecord,
    TrajectoryResult,
)
from backend.services.experience.service import ExperienceService

__all__ = [
    "ExperienceService",
    "TrajectoryOutcome",
    "TrajectoryQuery",
    "TrajectoryRecord",
    "TrajectoryResult",
]
