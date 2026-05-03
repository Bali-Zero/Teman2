"""Tests for Self-RAG Grader — retrieval quality gate.

# Organo: backend-rag/grading → produce GradeResult → consuma da orchestrator_core
"""

from __future__ import annotations

import pytest

from backend.services.rag.grading.context import GradingContext, RetrievedDoc
from backend.services.rag.grading.schemas import GradeDecision
from backend.services.rag.grading.self_rag_grader import SelfRAGGrader


class TestSelfRAGGrader:
    """Self-RAG grader decides if retrieved docs are sufficient for reasoning."""

    def setup_method(self) -> None:
        self.grader = SelfRAGGrader()

    def _make_docs(
        self, scores: list[float], contents: list[str] | None = None
    ) -> list[RetrievedDoc]:
        if contents is None:
            contents = [f"Document about visa process step {i}" for i in range(len(scores))]
        return [
            RetrievedDoc(content=c, score=s, source=f"collection_{i}")
            for i, (s, c) in enumerate(zip(scores, contents))
        ]

    # ── PASS cases ──

    def test_high_quality_docs_pass(self) -> None:
        """High-score docs with substantial content → PASS."""
        docs = self._make_docs(
            [0.85, 0.80, 0.75, 0.70],
            [
                "KITAS work permit requires RPTKA approval from BKPM before application.",
                "The sponsor company must have a valid NIB from OSS system.",
                "Processing time for KITAS is typically 15-20 working days.",
                "Required documents include passport copy, sponsor letter, and photo.",
            ],
        )
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.PASS
        assert result.score >= 0.5

    def test_good_top_docs_pass(self) -> None:
        """Top 3 docs are good with substantial content even if tail is weak → PASS."""
        docs = self._make_docs(
            [0.90, 0.82, 0.75, 0.20, 0.10],
            [
                "KITAS work permit requires RPTKA approval from the Ministry of Manpower before sponsor company can apply.",
                "The sponsor company must have a valid NIB and meet the minimum capital requirements for hiring foreign workers.",
                "Processing time for KITAS is typically 15-20 working days after complete submission of all required documents.",
                "Short doc",
                "Irrelevant",
            ],
        )
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.PASS

    # ── RETRY cases (trigger HyDE) ──

    def test_mediocre_docs_retry(self) -> None:
        """Medium-quality docs → RETRY with HyDE hint."""
        docs = self._make_docs([0.45, 0.40, 0.35, 0.30])
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.RETRY
        assert "hyde" in result.retry_hint.lower()

    def test_sparse_content_retry(self) -> None:
        """Docs have scores but minimal content → RETRY."""
        docs = self._make_docs(
            [0.70, 0.65, 0.60],
            ["ok", "yes", "no"],  # trivially short content
        )
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.RETRY

    # ── FAIL cases ──

    def test_no_docs_fail(self) -> None:
        """No documents retrieved → FAIL."""
        ctx = GradingContext(retrieved_documents=[])
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.FAIL
        assert result.score == 0.0

    def test_garbage_docs_fail(self) -> None:
        """Very low scores → FAIL (don't even bother with HyDE)."""
        docs = self._make_docs([0.05, 0.03, 0.02])
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.FAIL

    # ── Edge cases ──

    def test_single_excellent_doc(self) -> None:
        """Single high-quality doc → PASS (common for exact FAQ matches)."""
        docs = self._make_docs(
            [0.95],
            ["KITAS processing requires valid RPTKA, sponsor letter, and passport copy."],
        )
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert result.decision == GradeDecision.PASS

    def test_grader_name(self) -> None:
        """Grader identifies itself correctly."""
        assert self.grader.grader_name == "self_rag"

    def test_score_clamped(self) -> None:
        """Score is always in [0.0, 1.0]."""
        docs = self._make_docs([1.5, 1.2, 0.99])  # inflated scores
        ctx = GradingContext(retrieved_documents=docs)
        result = self.grader.grade(ctx)
        assert 0.0 <= result.score <= 1.0

    def test_content_relevance_boost(self) -> None:
        """Docs with substantial content (>100 chars) get relevance boost."""
        short_docs = self._make_docs([0.50, 0.50], ["x", "y"])
        long_docs = self._make_docs(
            [0.50, 0.50],
            [
                "Detailed explanation of KITAS work permit requirements including RPTKA sponsor letter",
                "Complete guide to Indonesian business visa process with step-by-step instructions",
            ],
        )
        ctx_short = GradingContext(retrieved_documents=short_docs)
        ctx_long = GradingContext(retrieved_documents=long_docs)
        result_short = self.grader.grade(ctx_short)
        result_long = self.grader.grade(ctx_long)
        assert result_long.score > result_short.score
