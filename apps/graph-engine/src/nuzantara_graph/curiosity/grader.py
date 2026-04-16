"""CuriosityGrader — validates research evidence before proposing to KG.

# Organo: graph-engine/curiosity → produce GradeResult → consuma da orchestrator

Wraps the Self-RAG grading interface to evaluate evidence gathered by
dispatchers. Uses the same scoring model (relevance 60% + substance 40%)
but with curiosity-specific thresholds:

  >= 0.60 → PROPOSE (create KG proposal)
  0.15 - 0.60 → MORE_RESEARCH (try different tier or query expansion)
  < 0.15 → ABSTAIN (evidence is garbage, skip)
"""
from __future__ import annotations

import logging
from typing import Any

from nuzantara_graph.curiosity.models import GradeResult, ResearchEvidence

logger = logging.getLogger(__name__)

# Curiosity-specific thresholds (distinct from RAG Self-RAG thresholds)
PROPOSE_THRESHOLD = 0.60
MORE_RESEARCH_THRESHOLD = 0.15

# Content length thresholds (same as Self-RAG for consistency)
_MIN_USEFUL_CONTENT_LEN = 50
_GOOD_CONTENT_LEN = 100


class CuriosityGrader:
    """Validates research evidence for KG proposal worthiness.

    Uses a simplified Self-RAG scoring model adapted for curiosity evidence:
    - No retrieval scores (evidence comes from dispatchers, not vector search)
    - Focuses on content substance and citation presence
    """

    def grade(
        self,
        gap_topic: str,
        domain: str,
        evidence: list[ResearchEvidence],
    ) -> GradeResult:
        """Grade research evidence for proposal worthiness.

        Args:
            gap_topic: The gap topic being researched.
            domain: Domain of the gap (immigration, tax, etc.).
            evidence: List of evidence gathered from dispatchers.

        Returns:
            GradeResult with score, decision, and reason.
        """
        if not evidence:
            return GradeResult(
                score=0.0,
                decision="abstain",
                reason="No evidence gathered",
            )

        # ── Score component 1: Content substance (50% weight) ──
        content_lengths = [len(e.content.strip()) for e in evidence]
        useful_docs = sum(1 for cl in content_lengths if cl >= _MIN_USEFUL_CONTENT_LEN)
        substantial_docs = sum(1 for cl in content_lengths if cl >= _GOOD_CONTENT_LEN)

        useful_ratio = useful_docs / len(evidence)
        substantial_ratio = substantial_docs / len(evidence)
        substance_score = useful_ratio * 0.5 + substantial_ratio * 0.5

        # ── Score component 2: Citation quality (30% weight) ──
        cited_count = sum(1 for e in evidence if e.citations)
        citation_ratio = cited_count / len(evidence)

        # ── Score component 3: Source confidence (20% weight) ──
        avg_confidence = sum(e.confidence for e in evidence) / len(evidence)

        # ── Combined score ──
        combined = (
            substance_score * 0.50
            + citation_ratio * 0.30
            + avg_confidence * 0.20
        )
        combined = max(0.0, min(1.0, combined))

        # ── Decision ──
        if combined >= PROPOSE_THRESHOLD:
            decision = "propose"
            reason = (
                f"Evidence sufficient (score={combined:.2f}). "
                f"{substantial_docs}/{len(evidence)} substantial, "
                f"{cited_count}/{len(evidence)} cited."
            )
        elif combined >= MORE_RESEARCH_THRESHOLD:
            decision = "more_research"
            reason = (
                f"Evidence marginal (score={combined:.2f}). "
                f"{useful_docs}/{len(evidence)} useful, "
                f"{cited_count}/{len(evidence)} cited. "
                f"Try higher tier or expanded queries."
            )
        else:
            decision = "abstain"
            reason = (
                f"Evidence insufficient (score={combined:.2f}). "
                f"Only {useful_docs}/{len(evidence)} useful docs."
            )

        logger.info(
            "curiosity_grade: topic=%s domain=%s score=%.2f decision=%s",
            gap_topic[:40], domain, combined, decision,
        )

        return GradeResult(score=combined, decision=decision, reason=reason)
