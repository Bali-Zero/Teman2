"""Tests for graph routing logic."""

from nuzantara_graph.graph.constants import RouteDecision
from nuzantara_graph.graph.router import route_after_grade, route_after_understand
from nuzantara_schemas.grading import GradeDecision, GradeResult
from nuzantara_schemas.state import GraphState, IntentType


class TestRouteAfterUnderstand:
    def test_greeting_routes_direct(self):
        state = GraphState(query="Hello!", intent=IntentType.GREETING)
        assert route_after_understand(state) == RouteDecision.DIRECT

    def test_business_setup_routes_company(self):
        state = GraphState(query="How to set up PT PMA?", intent=IntentType.BUSINESS_SETUP)
        assert route_after_understand(state) == RouteDecision.SUBGRAPH_COMPANY

    def test_visa_routes_visa(self):
        state = GraphState(query="KITAS requirements", intent=IntentType.VISA)
        assert route_after_understand(state) == RouteDecision.SUBGRAPH_VISA

    def test_property_routes_property(self):
        state = GraphState(query="Hak Pakai rules", intent=IntentType.PROPERTY)
        assert route_after_understand(state) == RouteDecision.SUBGRAPH_PROPERTY

    def test_tax_routes_tax(self):
        state = GraphState(query="PPh rates", intent=IntentType.TAX)
        assert route_after_understand(state) == RouteDecision.SUBGRAPH_TAX

    def test_general_routes_retrieve(self):
        state = GraphState(query="What is Bali like?", intent=IntentType.GENERAL)
        assert route_after_understand(state) == RouteDecision.RETRIEVE

    def test_kbli_routes_retrieve(self):
        state = GraphState(query="KBLI 56101", intent=IntentType.KBLI)
        assert route_after_understand(state) == RouteDecision.RETRIEVE


class TestRouteAfterGrade:
    def test_pass_continues(self):
        state = GraphState(query="test")
        state.grades.append(
            GradeResult(grader="retrieval", decision=GradeDecision.PASS, score=0.9)
        )
        assert route_after_grade(state, "retrieve", "reason") == "continue"

    def test_retry_when_corrections_available(self):
        state = GraphState(query="test", correction_count=0)
        state.grades.append(
            GradeResult(grader="retrieval", decision=GradeDecision.RETRY, score=0.4)
        )
        assert route_after_grade(state, "retrieve", "reason") == "retry"

    def test_fail_triggers_fail_fast(self):
        state = GraphState(query="test")
        state.grades.append(
            GradeResult(grader="retrieval", decision=GradeDecision.FAIL, score=0.1)
        )
        assert route_after_grade(state, "retrieve", "reason") == "fail_fast"

    def test_retry_exhausted_continues(self):
        state = GraphState(query="test", correction_count=2, max_corrections=2)
        state.grades.append(
            GradeResult(grader="retrieval", decision=GradeDecision.RETRY, score=0.4)
        )
        assert route_after_grade(state, "retrieve", "reason") == "continue"

    def test_no_grades_continues(self):
        state = GraphState(query="test")
        assert route_after_grade(state, "retrieve", "reason") == "continue"

    def test_fail_fast_even_with_corrections_available(self):
        """FAIL always triggers fail_fast, regardless of correction_count."""
        state = GraphState(query="test", correction_count=0)
        state.grades.append(
            GradeResult(grader="retrieval", decision=GradeDecision.FAIL, score=0.05)
        )
        assert route_after_grade(state, "retrieve", "reason") == "fail_fast"
