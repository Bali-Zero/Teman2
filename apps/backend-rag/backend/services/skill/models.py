"""Pydantic schemas for the Skill Registry service.

Distinct from the Experience Library (trajectories) on purpose: skills carry
precondition + procedure + success_criterion (germline) whereas trajectories
carry outcome + tokens + duration (episodic). They live in the same Genome
table, keyed by ``type``.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SkillScope(str, Enum):
    PROJECT = "Project"
    PERSONAL = "Personal"


class SkillTier(str, Enum):
    TIER1 = "tier1"
    TIER2 = "tier2"


class SkillRecord(BaseModel):
    """Payload to register a reusable skill in the Genome.

    Unlike trajectories, every skill must come with the three canonical
    fields (precondition, procedure, success_criterion). The seed script
    enforces this — no empty signal.
    """

    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    cell: str = Field(..., min_length=1, max_length=64)
    skill_id: str = Field(..., min_length=1, max_length=128)
    procedure: str = Field(..., min_length=1, max_length=4000)
    precondition: str = Field(..., min_length=1, max_length=1000)
    success_criterion: str = Field(..., min_length=1, max_length=1000)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    scope: SkillScope = SkillScope.PROJECT


class SkillQuery(BaseModel):
    """Read request against the Skill Registry.

    FTS5 match on procedure + precondition + success_criterion (inherited
    from the existing genome_fts virtual table). Optional tier filter +
    min_confidence let Thinkers narrow to the trusted subset.
    """

    model_config = ConfigDict(use_enum_values=True)

    query: str = Field(..., min_length=1, max_length=256)
    cell: str | None = Field(default=None, max_length=64)
    tier: SkillTier | None = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=20, ge=1, le=100)


class SkillResult(BaseModel):
    """Response row — flat projection of the Genome row."""

    skill_id: str
    cell: str
    procedure: str
    precondition: str
    success_criterion: str
    confidence: float
    tier: SkillTier | None = None
    uses: int = 0
    scope: SkillScope
    valid_from: str
