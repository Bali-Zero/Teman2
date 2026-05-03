"""GenomeAdapter — async-friendly wrapper around cell-core Genome.

cell_core.genome.Genome is synchronous (sqlite3). We wrap it with
``asyncio.to_thread`` so the Learner can stay fully async without holding
up the event loop.

The adapter depends on a :class:`GenomeProtocol` (duck-typed) so tests can
inject a fake without importing the real cell_core package.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# Default cell name used for War Room skill/scar entries.
WAR_ROOM_CELL = "war_room"


@runtime_checkable
class GenomeProtocol(Protocol):
    """Minimum surface we need from cell_core.genome.Genome."""

    def record_skill(
        self,
        cell: str,
        skill_id: str,
        procedure: str,
        precondition: str = "",
        success_criterion: str = "",
        confidence: float = 0.5,
        scope: str = "Project",
        inherited_from: str | None = None,
        entry_type: str = "skill",
        domain: str = "generic",
    ) -> str: ...

    def record_scar(
        self,
        cell: str,
        scar_id: str,
        procedure: str,
        precondition: str = "",
    ) -> str: ...


@dataclass
class SkillEntry:
    skill_id: str
    procedure: str
    precondition: str = ""
    success_criterion: str = ""
    confidence: float = 0.6
    domain: str = "war_room"
    scope: str = "Project"


@dataclass
class ScarEntry:
    scar_id: str
    procedure: str
    precondition: str = ""


class GenomeAdapter:
    """Async wrapper. Methods are no-ops if ``genome=None`` (Learner can still run)."""

    def __init__(
        self,
        genome: GenomeProtocol | None = None,
        cell: str = WAR_ROOM_CELL,
    ) -> None:
        self.genome = genome
        self.cell = cell

    @property
    def available(self) -> bool:
        return self.genome is not None

    async def record_skill(self, entry: SkillEntry) -> str:
        if self.genome is None:
            logger.info(
                "genome unavailable — skipped skill %s", entry.skill_id,
            )
            return "skipped"
        return await asyncio.to_thread(
            self.genome.record_skill,
            self.cell,
            entry.skill_id,
            entry.procedure,
            entry.precondition,
            entry.success_criterion,
            entry.confidence,
            entry.scope,
            None,
            "skill",
            entry.domain,
        )

    async def record_scar(self, entry: ScarEntry) -> str:
        if self.genome is None:
            logger.info(
                "genome unavailable — skipped scar %s", entry.scar_id,
            )
            return "skipped"
        return await asyncio.to_thread(
            self.genome.record_scar,
            self.cell,
            entry.scar_id,
            entry.procedure,
            entry.precondition,
        )
