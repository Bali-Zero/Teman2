"""Tests for the hallucination grader."""

from nuzantara_graph.graders.hallucination_grader import HallucinationGrader
from nuzantara_schemas.grading import GradeDecision
from nuzantara_schemas.state import GraphState, RetrievedDocument


class TestHallucinationGrader:
    def setup_method(self):
        self.grader = HallucinationGrader()

    def test_well_grounded_answer_passes(self):
        state = GraphState(
            query="PT PMA capital requirements",
            answer="The minimum capital for a PT PMA is 10 billion IDR. Foreign ownership can be up to 100%.",
            retrieved_documents=[
                RetrievedDocument(
                    id="d1",
                    content="PT PMA minimum capital requirement is 10 billion IDR. Foreign ownership up to 100%.",
                    score=0.9,
                ),
            ],
            sources=[{"id": "d1"}],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_no_sources_low_score(self):
        state = GraphState(
            query="Test",
            answer="The capital requirement is 10 billion IDR for foreign companies.",
            retrieved_documents=[],
            kg_entities=[],
        )
        result = self.grader.grade(state)
        assert result.score < 0.2  # no sources = highly suspect

    def test_empty_answer_passes(self):
        """No answer means nothing to check — vacuously true."""
        state = GraphState(query="Test", answer="")
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS

    def test_fabricated_answer_fails(self):
        """Answer with claims not in any source documents."""
        state = GraphState(
            query="Test",
            answer="According to the 2025 Jakarta Metropolitan Regulation, all businesses must register with the BKPM office in Menteng by submitting form X-42B.",
            retrieved_documents=[
                RetrievedDocument(
                    id="d1",
                    content="Business registration is done through OSS (Online Single Submission) system.",
                    score=0.6,
                ),
            ],
        )
        result = self.grader.grade(state)
        assert result.score < 0.8  # should flag low grounding

    def test_kg_entities_count_as_sources(self):
        state = GraphState(
            query="KBLI restaurant",
            answer="The KBLI code for restaurant business is 56101, classified under Restoran category.",
            retrieved_documents=[],
            kg_entities=[
                {"entity_id": "kbli:56101", "label": "Restoran", "description": "Restaurant KBLI code 56101"},
            ],
        )
        result = self.grader.grade(state)
        # KG entities provide grounding for the answer
        assert result.score > 0.3

    def test_system_fallback_answer_is_neutral_pass(self):
        """When the planner emits a known system fallback string (e.g. the
        visa planner's 'I cannot produce a fully-cited answer...'), the
        hallucination grader should NOT run the keyword-overlap heuristic
        at all. It should record a neutral PASS with a clear reason,
        because the string is explicitly a non-answer escalation."""
        state = GraphState(
            query="Obscure query with no KB coverage",
            answer=(
                "I cannot produce a fully-cited answer for this query. "
                "Please rephrase or contact support for visa assistance."
            ),
            retrieved_documents=[
                RetrievedDocument(
                    id="SYSTEM:b211_rewrite",
                    content="The B211 visa was abolished...",
                    score=1.0,
                )
            ],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS
        assert "system_fallback" in result.reason.lower() or "fallback" in result.reason.lower()

    def test_rephrase_style_fallback_detected(self):
        """The fail_fast node emits its own rephrase message — the grader
        should recognize it as a non-answer too."""
        state = GraphState(
            query="Test",
            answer=(
                "I wasn't able to provide a reliable answer to your question. "
                "Could you try rephrasing it with more specific details?"
            ),
            retrieved_documents=[],
        )
        result = self.grader.grade(state)
        assert result.decision == GradeDecision.PASS
        assert "fallback" in result.reason.lower()

    def test_real_answer_with_same_keywords_still_evaluated(self):
        """Safety check: a real answer that happens to contain the word
        'rephrase' or 'cannot' should NOT be mistaken for a fallback.
        The detector requires an exact prefix match, not keyword overlap."""
        state = GraphState(
            query="KITAS duration",
            answer=(
                "KITAS is valid for 12 months and cannot be issued without "
                "a sponsoring company."
            ),
            retrieved_documents=[
                RetrievedDocument(
                    id="d1",
                    content="KITAS duration is 12 months. A sponsor company is required.",
                    score=0.9,
                )
            ],
        )
        result = self.grader.grade(state)
        # Normal heuristic ran — not the fallback short-circuit
        assert "fallback" not in result.reason.lower()
