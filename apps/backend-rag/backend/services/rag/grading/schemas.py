"""Grading schemas for RAG quality gates.

Ported from packages/shared-schemas for local use in backend-rag.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GradeDecision(StrEnum):
    """Decision produced by a grader."""

    PASS = "pass"
    RETRY = "retry"
    FAIL = "fail"


class GradeResult(BaseModel):
    """Result of a grading evaluation."""

    grader: str = Field(description="Name of the grader that produced this result")
    decision: GradeDecision = Field(description="Pass / retry / fail decision")
    score: float = Field(ge=0.0, le=1.0, description="Quality score 0.0-1.0")
    reason: str = Field(default="", description="Human-readable explanation")
    retry_hint: str = Field(
        default="",
        description="Guidance for retried node (empty if PASS or FAIL)",
    )


class ConfidenceScores(BaseModel):
    """Multi-dimensional confidence scoring (6 factors)."""

    overall: float = Field(default=0.5, ge=0.0, le=1.0)
    retrieval: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: float = Field(default=0.5, ge=0.0, le=1.0)
    grounding: float = Field(default=0.5, ge=0.0, le=1.0)
    completeness: float = Field(default=0.5, ge=0.0, le=1.0)
    pricing_accuracy: float = Field(default=1.0, ge=0.0, le=1.0)

    def weighted_overall(self) -> float:
        """Compute weighted overall score."""
        weights = {
            "retrieval": 0.25,
            "reasoning": 0.20,
            "grounding": 0.30,
            "completeness": 0.15,
            "pricing_accuracy": 0.10,
        }
        total = sum(
            getattr(self, k) * w for k, w in weights.items()
        )
        return min(1.0, max(0.0, total))
