"""Pydantic schemas for the Experience Library service.

Validation at the boundary (router <-> service): trajectory_id length, outcome
whitelist, confidence range, query limit bound.

Tag slug constraint (Sprint 5.2 post-review 2026-04-15): tags are stored as
a JSON array and searched via ``LIKE '%"<tag>"%'`` against the serialised
form. ASCII slug characters keep that pattern exact-match and unambiguous;
quotes / backslashes in a tag would survive JSON escaping but the LIKE
would miss them silently. Enforcing the slug rule here turns that silent
failure into a 422 at the boundary.
"""
from __future__ import annotations

from enum import Enum

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# [a-z0-9_-]+ (case-insensitive) — matches real-world tags like "ig",
# "wa", "visa_expired", "kbli-70209". Rejects whitespace, quotes,
# backslashes, punctuation.
_TAG_PATTERN = r"^[A-Za-z0-9_-]+$"


class TrajectoryOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class TrajectoryRecord(BaseModel):
    """Payload to register an execution trajectory in the Genome."""

    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    trajectory_id: str = Field(..., min_length=1, max_length=128)
    cell: str = Field(..., min_length=1, max_length=64)
    outcome: TrajectoryOutcome
    procedure: str = Field(..., min_length=1, max_length=4000)
    tokens: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="ASCII slug tags; see module docstring.",
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("tags")
    @classmethod
    def _validate_tag_slugs(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if not re.fullmatch(_TAG_PATTERN, t)]
        if bad:
            raise ValueError(
                f"invalid tag(s) {bad!r}: expected ASCII slug [A-Za-z0-9_-]+",
            )
        return v


class TrajectoryQuery(BaseModel):
    """Read request against the Experience Library."""

    model_config = ConfigDict(use_enum_values=True)

    query: str = Field(..., min_length=1, max_length=256)
    outcome: TrajectoryOutcome | None = None
    cell: str | None = Field(default=None, max_length=64)
    tag: str | None = Field(default=None, max_length=64, pattern=_TAG_PATTERN)
    limit: int = Field(default=20, ge=1, le=100)


class TrajectoryResult(BaseModel):
    """Response row from a query — flat projection of the Genome row."""

    trajectory_id: str
    cell: str
    outcome: TrajectoryOutcome
    procedure: str
    tokens: int | None = None
    duration_ms: int | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float
    valid_from: str
