"""
Tests for agents/agents/schemas.py - Pydantic schemas for agent input validation
"""

import pytest
from pydantic import ValidationError


class TestConversationTrainerRequest:
    """Tests for ConversationTrainerRequest schema"""

    def test_default_values(self):
        """Test default values are applied correctly"""
        from backend.agents.agents.schemas import ConversationTrainerRequest

        request = ConversationTrainerRequest()
        assert request.days_back == 7

    def test_valid_days_back(self):
        """Test valid days_back values"""
        from backend.agents.agents.schemas import ConversationTrainerRequest

        # Minimum value
        request = ConversationTrainerRequest(days_back=1)
        assert request.days_back == 1

        # Maximum value
        request = ConversationTrainerRequest(days_back=365)
        assert request.days_back == 365

        # Middle value
        request = ConversationTrainerRequest(days_back=30)
        assert request.days_back == 30

    def test_invalid_days_back_too_low(self):
        """Test days_back below minimum raises error"""
        from backend.agents.agents.schemas import ConversationTrainerRequest

        with pytest.raises(ValidationError) as exc_info:
            ConversationTrainerRequest(days_back=0)
        assert "greater than or equal to 1" in str(exc_info.value).lower()

    def test_invalid_days_back_too_high(self):
        """Test days_back above maximum raises error"""
        from backend.agents.agents.schemas import ConversationTrainerRequest

        with pytest.raises(ValidationError) as exc_info:
            ConversationTrainerRequest(days_back=366)
        assert "less than or equal to 365" in str(exc_info.value).lower()


class TestKnowledgeGraphBuilderRequest:
    """Tests for KnowledgeGraphBuilderRequest schema"""

    def test_default_values(self):
        """Test default values are applied correctly"""
        from backend.agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest()
        assert request.days_back == 30
        assert request.init_schema is False

    def test_valid_days_back(self):
        """Test valid days_back values"""
        from backend.agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest(days_back=1)
        assert request.days_back == 1

        request = KnowledgeGraphBuilderRequest(days_back=365)
        assert request.days_back == 365

    def test_init_schema_true(self):
        """Test init_schema can be set to True"""
        from backend.agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest(init_schema=True)
        assert request.init_schema is True

    def test_invalid_days_back(self):
        """Test invalid days_back raises error"""
        from backend.agents.agents.schemas import KnowledgeGraphBuilderRequest

        with pytest.raises(ValidationError):
            KnowledgeGraphBuilderRequest(days_back=0)

        with pytest.raises(ValidationError):
            KnowledgeGraphBuilderRequest(days_back=366)


class TestEntitySearchRequest:
    """Tests for EntitySearchRequest schema"""

    def test_valid_request(self):
        """Test valid request"""
        from backend.agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="test query")
        assert request.query == "test query"
        assert request.top_k == 10  # default

    def test_custom_top_k(self):
        """Test custom top_k value"""
        from backend.agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="test", top_k=50)
        assert request.top_k == 50

        # Min value
        request = EntitySearchRequest(query="test", top_k=1)
        assert request.top_k == 1

        # Max value
        request = EntitySearchRequest(query="test", top_k=100)
        assert request.top_k == 100

    def test_query_min_length(self):
        """Test query minimum length validation"""
        from backend.agents.agents.schemas import EntitySearchRequest

        # Single character should work
        request = EntitySearchRequest(query="a")
        assert request.query == "a"

        # Empty string should fail
        with pytest.raises(ValidationError) as exc_info:
            EntitySearchRequest(query="")
        assert (
            "at least 1" in str(exc_info.value).lower()
            or "min_length" in str(exc_info.value).lower()
        )

    def test_query_max_length(self):
        """Test query maximum length validation"""
        from backend.agents.agents.schemas import EntitySearchRequest

        # Exactly 200 characters should work
        request = EntitySearchRequest(query="a" * 200)
        assert len(request.query) == 200

        # 201 characters should fail
        with pytest.raises(ValidationError) as exc_info:
            EntitySearchRequest(query="a" * 201)
        assert (
            "at most 200" in str(exc_info.value).lower()
            or "max_length" in str(exc_info.value).lower()
        )

    def test_invalid_top_k(self):
        """Test invalid top_k values"""
        from backend.agents.agents.schemas import EntitySearchRequest

        with pytest.raises(ValidationError):
            EntitySearchRequest(query="test", top_k=0)

        with pytest.raises(ValidationError):
            EntitySearchRequest(query="test", top_k=101)

    def test_missing_required_query(self):
        """Test that query is required"""
        from backend.agents.agents.schemas import EntitySearchRequest

        with pytest.raises(ValidationError) as exc_info:
            EntitySearchRequest()
        assert "query" in str(exc_info.value).lower()
