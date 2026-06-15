"""Pydantic models for Skill Coach evidence cards."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillCoachStatus = Literal["proposed", "shadow_eligible", "rejected"]
RedactionStatus = Literal["passed", "failed"]


class SkillCoachEvidence(BaseModel):
    """Redacted evidence card for one proposed skill.

    The card is deliberately aggregate-only: trajectory ids and counters are
    allowed, raw trajectory payload is not.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    proposal_id: str = Field(..., min_length=1, max_length=128)
    skill_id: str = Field(..., min_length=1, max_length=128)
    cell: str = Field(..., min_length=1, max_length=64)
    tags: list[str] = Field(default_factory=list)
    scope: str = Field(default="Project")
    status: SkillCoachStatus
    source_trajectory_ids: list[str] = Field(default_factory=list)
    preconditions: str = Field(..., min_length=1, max_length=1000)
    procedure: str = Field(..., min_length=1, max_length=4000)
    success_criteria: str = Field(..., min_length=1, max_length=1000)
    confidence: float = Field(..., ge=0.0, le=0.5)
    redaction_status: RedactionStatus
    redaction_findings: list[str] = Field(default_factory=list)
    support_count: int = Field(default=0, ge=0)
    hurt_count: int = Field(default=0, ge=0)
    false_apply_count: int = Field(default=0, ge=0)
    neutral_count: int = Field(default=0, ge=0)
    history_sample_size: int = Field(default=0, ge=0)
    decision_reason: str = Field(..., min_length=1, max_length=500)
    created_at: str
