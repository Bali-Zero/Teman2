"""Grading schemas — quality gates between graph nodes."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GradeDecision(StrEnum):
    PASS = "pass"
    RETRY = "retry"
    FAIL = "fail"


class GradeResult(BaseModel):
    """Result from a grader node."""

    grader: str  # retrieval | reasoning | answer | hallucination | pricing
    decision: GradeDecision
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    retry_hint: str = ""  # guidance for the retried node


class ConfidenceScores(BaseModel):
    """6-factor confidence scoring preserved from V5.

    Each factor is 0.0-1.0. The overall score is a weighted average.
    """

    retrieval_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    source_authority: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning_coherence: float = Field(default=0.0, ge=0.0, le=1.0)
    factual_grounding: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_completeness: float = Field(default=0.0, ge=0.0, le=1.0)

    # Weights for each factor
    _weights: dict[str, float] = {
        "retrieval_relevance": 0.20,
        "source_authority": 0.15,
        "reasoning_coherence": 0.20,
        "factual_grounding": 0.20,
        "domain_coverage": 0.15,
        "answer_completeness": 0.10,
    }

    @property
    def overall(self) -> float:
        total = 0.0
        for field_name, weight in self._weights.items():
            total += getattr(self, field_name) * weight
        return round(total, 4)

    @property
    def is_high_confidence(self) -> bool:
        return self.overall >= 0.7

    @property
    def is_low_confidence(self) -> bool:
        return self.overall < 0.4
