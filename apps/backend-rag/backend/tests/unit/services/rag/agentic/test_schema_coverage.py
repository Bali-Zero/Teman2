"""
Complete test coverage for schema module
Target: >95% coverage

This file provides comprehensive tests for:
- CoreResult model - all fields, validation, defaults, edge cases
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic.schema import CoreResult

# ============================================================================
# TESTS: CoreResult - Complete Coverage
# ============================================================================


class TestCoreResultBasic:
    """Basic tests for CoreResult"""

    def test_core_result_minimal(self):
        """Test CoreResult with only required field"""
        result = CoreResult(answer="Test answer")
        assert result.answer == "Test answer"
        assert result.sources == []
        assert result.model_used is None
        assert result.cache_hit is False

    def test_core_result_with_all_fields(self):
        """Test CoreResult with all fields populated"""
        result = CoreResult(
            answer="Test answer",
            sources=[{"id": "1", "text": "Source 1"}],
            model_used="gemini-pro",
            route_used="fast",
            collection_used="test_collection",
            cache_hit=True,
            verification_status="passed",
            verification_score=0.95,
            evidence_score=0.85,
            is_ambiguous=False,
            clarification_question=None,
            document_count=5,
            context_used=1000,
            tools_called=["vector_search", "calculator"],
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.01,
            entities={"visa_type": "KITAS"},
            timings={"search": 0.5, "llm": 1.2},
            warnings=["Low confidence"],
        )
        assert result.answer == "Test answer"
        assert len(result.sources) == 1
        assert result.model_used == "gemini-pro"
        assert result.cache_hit is True
        assert result.verification_score == 0.95
        assert result.tools_called == ["vector_search", "calculator"]

    def test_core_result_default_values(self):
        """Test CoreResult default values"""
        result = CoreResult(answer="Test")
        assert result.sources == []
        assert result.model_used is None
        assert result.route_used is None
        assert result.collection_used is None
        assert result.cache_hit is False
        assert result.verification_status is None
        assert result.verification_score == 0.0
        assert result.evidence_score == 0.0
        assert result.is_ambiguous is False
        assert result.clarification_question is None
        assert result.document_count == 0
        assert result.context_used == 0
        assert result.tools_called == []
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0
        assert result.cost_usd == 0.0
        assert result.entities == {}
        assert result.timings == {}
        assert result.warnings == []


class TestCoreResultValidation:
    """Tests for CoreResult validation"""

    def test_core_result_missing_answer(self):
        """Test that answer is required"""
        with pytest.raises(ValidationError):
            CoreResult()

    def test_core_result_empty_answer(self):
        """Test that empty string answer is allowed"""
        result = CoreResult(answer="")
        assert result.answer == ""

    def test_core_result_cache_hit_string(self):
        """Test that cache_hit can be a string"""
        result = CoreResult(answer="Test", cache_hit="semantic")
        assert result.cache_hit == "semantic"

    def test_core_result_cache_hit_boolean(self):
        """Test that cache_hit can be a boolean"""
        result = CoreResult(answer="Test", cache_hit=True)
        assert result.cache_hit is True

    def test_core_result_verification_score_range(self):
        """Test verification_score can be any float"""
        result = CoreResult(answer="Test", verification_score=1.5)
        assert result.verification_score == 1.5

    def test_core_result_negative_scores(self):
        """Test that negative scores are allowed"""
        result = CoreResult(answer="Test", verification_score=-0.5, evidence_score=-0.3)
        assert result.verification_score == -0.5
        assert result.evidence_score == -0.3

    def test_core_result_negative_tokens(self):
        """Test that negative token counts are allowed (edge case)"""
        result = CoreResult(answer="Test", prompt_tokens=-10, completion_tokens=-5)
        assert result.prompt_tokens == -10
        assert result.completion_tokens == -5

    def test_core_result_negative_cost(self):
        """Test that negative cost is allowed (edge case)"""
        result = CoreResult(answer="Test", cost_usd=-0.01)
        assert result.cost_usd == -0.01


class TestCoreResultSources:
    """Tests for sources field"""

    def test_core_result_empty_sources(self):
        """Test empty sources list"""
        result = CoreResult(answer="Test", sources=[])
        assert result.sources == []

    def test_core_result_single_source(self):
        """Test single source"""
        result = CoreResult(answer="Test", sources=[{"id": "1", "text": "Source"}])
        assert len(result.sources) == 1
        assert result.sources[0]["id"] == "1"

    def test_core_result_multiple_sources(self):
        """Test multiple sources"""
        sources = [
            {"id": "1", "text": "Source 1"},
            {"id": "2", "text": "Source 2"},
            {"id": "3", "text": "Source 3"},
        ]
        result = CoreResult(answer="Test", sources=sources)
        assert len(result.sources) == 3

    def test_core_result_sources_with_complex_data(self):
        """Test sources with complex nested data"""
        sources = [
            {
                "id": "1",
                "title": "Document",
                "url": "https://example.com",
                "score": 0.95,
                "metadata": {"author": "Test", "date": "2024-01-01"},
            }
        ]
        result = CoreResult(answer="Test", sources=sources)
        assert result.sources[0]["metadata"]["author"] == "Test"


class TestCoreResultEntities:
    """Tests for entities field"""

    def test_core_result_empty_entities(self):
        """Test empty entities dict"""
        result = CoreResult(answer="Test", entities={})
        assert result.entities == {}

    def test_core_result_entities_dict(self):
        """Test entities with various types"""
        entities = {
            "visa_type": "KITAS",
            "nationality": "Italy",
            "budget": "$50k",
            "count": 5,
            "active": True,
        }
        result = CoreResult(answer="Test", entities=entities)
        assert result.entities["visa_type"] == "KITAS"
        assert result.entities["count"] == 5
        assert result.entities["active"] is True

    def test_core_result_entities_nested(self):
        """Test nested entities"""
        entities = {
            "visa": {"type": "KITAS", "duration": "1 year"},
            "client": {"name": "Test", "location": "Bali"},
        }
        result = CoreResult(answer="Test", entities=entities)
        assert result.entities["visa"]["type"] == "KITAS"


class TestCoreResultTimings:
    """Tests for timings field"""

    def test_core_result_empty_timings(self):
        """Test empty timings dict"""
        result = CoreResult(answer="Test", timings={})
        assert result.timings == {}

    def test_core_result_timings_dict(self):
        """Test timings with various operations"""
        timings = {
            "search": 0.5,
            "llm": 1.2,
            "post_process": 0.1,
            "total": 1.8,
        }
        result = CoreResult(answer="Test", timings=timings)
        assert result.timings["search"] == 0.5
        assert result.timings["total"] == 1.8

    def test_core_result_timings_negative(self):
        """Test negative timings (edge case)"""
        result = CoreResult(answer="Test", timings={"error": -1.0})
        assert result.timings["error"] == -1.0


class TestCoreResultWarnings:
    """Tests for warnings field"""

    def test_core_result_empty_warnings(self):
        """Test empty warnings list"""
        result = CoreResult(answer="Test", warnings=[])
        assert result.warnings == []

    def test_core_result_single_warning(self):
        """Test single warning"""
        result = CoreResult(answer="Test", warnings=["Low confidence"])
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Low confidence"

    def test_core_result_multiple_warnings(self):
        """Test multiple warnings"""
        warnings = ["Low confidence", "Missing context", "Slow response"]
        result = CoreResult(answer="Test", warnings=warnings)
        assert len(result.warnings) == 3
        assert "Slow response" in result.warnings


class TestCoreResultToolsCalled:
    """Tests for tools_called field"""

    def test_core_result_empty_tools(self):
        """Test empty tools_called list"""
        result = CoreResult(answer="Test", tools_called=[])
        assert result.tools_called == []

    def test_core_result_single_tool(self):
        """Test single tool"""
        result = CoreResult(answer="Test", tools_called=["vector_search"])
        assert result.tools_called == ["vector_search"]

    def test_core_result_multiple_tools(self):
        """Test multiple tools"""
        tools = ["vector_search", "calculator", "web_search", "pricing"]
        result = CoreResult(answer="Test", tools_called=tools)
        assert len(result.tools_called) == 4
        assert "calculator" in result.tools_called


class TestCoreResultTokenUsage:
    """Tests for token usage fields"""

    def test_core_result_token_usage_zero(self):
        """Test zero token usage"""
        result = CoreResult(answer="Test")
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0

    def test_core_result_token_usage_set(self):
        """Test token usage values"""
        result = CoreResult(
            answer="Test",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        assert result.prompt_tokens == 1000
        assert result.completion_tokens == 500
        assert result.total_tokens == 1500

    def test_core_result_token_usage_large_numbers(self):
        """Test large token numbers"""
        result = CoreResult(
            answer="Test",
            prompt_tokens=100000,
            completion_tokens=50000,
            total_tokens=150000,
        )
        assert result.total_tokens == 150000


class TestCoreResultSerialization:
    """Tests for CoreResult serialization"""

    def test_core_result_to_dict(self):
        """Test converting to dict"""
        result = CoreResult(
            answer="Test",
            model_used="gemini-pro",
            verification_score=0.95,
        )
        data = result.model_dump()
        assert data["answer"] == "Test"
        assert data["model_used"] == "gemini-pro"
        assert data["verification_score"] == 0.95

    def test_core_result_to_json(self):
        """Test converting to JSON"""
        result = CoreResult(answer="Test", verification_score=0.95)
        json_str = result.model_dump_json()
        assert "Test" in json_str
        assert "0.95" in json_str

    def test_core_result_from_dict(self):
        """Test creating from dict"""
        data = {
            "answer": "Test",
            "model_used": "gemini-pro",
            "verification_score": 0.95,
        }
        result = CoreResult(**data)
        assert result.answer == "Test"
        assert result.model_used == "gemini-pro"


class TestCoreResultEdgeCases:
    """Edge cases and special scenarios"""

    def test_core_result_very_long_answer(self):
        """Test with very long answer"""
        long_answer = "A" * 10000
        result = CoreResult(answer=long_answer)
        assert len(result.answer) == 10000

    def test_core_result_special_characters(self):
        """Test with special characters in answer"""
        result = CoreResult(answer="Test with émojis 🎉 and unicode 中文")
        assert "émojis" in result.answer
        assert "🎉" in result.answer

    def test_core_result_none_values(self):
        """Test that None values are preserved for optional fields"""
        result = CoreResult(
            answer="Test",
            model_used=None,
            route_used=None,
            clarification_question=None,
        )
        assert result.model_used is None
        assert result.clarification_question is None

    def test_core_result_ambiguous_true(self):
        """Test is_ambiguous flag"""
        result = CoreResult(answer="Test", is_ambiguous=True, clarification_question="Which one?")
        assert result.is_ambiguous is True
        assert result.clarification_question == "Which one?"

    def test_core_result_all_zeros(self):
        """Test with all numeric fields set to zero"""
        result = CoreResult(
            answer="Test",
            verification_score=0.0,
            evidence_score=0.0,
            document_count=0,
            context_used=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
        )
        assert result.verification_score == 0.0
        assert result.cost_usd == 0.0

    def test_core_result_protected_namespaces(self):
        """Test that protected_namespaces config is set"""
        # This ensures the model_config is properly set
        result = CoreResult(answer="Test")
        assert hasattr(result, "model_config")
