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
