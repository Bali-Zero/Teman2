"""
Integration Tests for Agent Schemas
Tests Pydantic schema validation for agent requests
"""

import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAgentSchemasIntegration:
    """Comprehensive integration tests for agent schemas"""

    def test_conversation_trainer_request_default(self):
        """Test ConversationTrainerRequest with default values"""
        from agents.agents.schemas import ConversationTrainerRequest

        request = ConversationTrainerRequest()
        assert request.days_back == 7

    def test_conversation_trainer_request_valid(self):
        """Test ConversationTrainerRequest with valid values"""
        from agents.agents.schemas import ConversationTrainerRequest

        request = ConversationTrainerRequest(days_back=30)
        assert request.days_back == 30

    def test_conversation_trainer_request_min(self):
        """Test ConversationTrainerRequest with minimum value"""
        from agents.agents.schemas import ConversationTrainerRequest

        request = ConversationTrainerRequest(days_back=1)
        assert request.days_back == 1

    def test_conversation_trainer_request_max(self):
        """Test ConversationTrainerRequest with maximum value"""
        from agents.agents.schemas import ConversationTrainerRequest

        request = ConversationTrainerRequest(days_back=365)
        assert request.days_back == 365

    def test_conversation_trainer_request_too_low(self):
        """Test ConversationTrainerRequest with value below minimum"""
        from agents.agents.schemas import ConversationTrainerRequest

        with pytest.raises(ValidationError):
            ConversationTrainerRequest(days_back=0)

    def test_conversation_trainer_request_too_high(self):
        """Test ConversationTrainerRequest with value above maximum"""
        from agents.agents.schemas import ConversationTrainerRequest

        with pytest.raises(ValidationError):
            ConversationTrainerRequest(days_back=366)

    def test_knowledge_graph_builder_request_default(self):
        """Test KnowledgeGraphBuilderRequest with default values"""
        from agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest()
        assert request.days_back == 30
        assert request.init_schema is False

    def test_knowledge_graph_builder_request_valid(self):
        """Test KnowledgeGraphBuilderRequest with valid values"""
        from agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest(days_back=60, init_schema=True)
        assert request.days_back == 60
        assert request.init_schema is True

    def test_knowledge_graph_builder_request_min(self):
        """Test KnowledgeGraphBuilderRequest with minimum value"""
        from agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest(days_back=1)
        assert request.days_back == 1

    def test_knowledge_graph_builder_request_max(self):
        """Test KnowledgeGraphBuilderRequest with maximum value"""
        from agents.agents.schemas import KnowledgeGraphBuilderRequest

        request = KnowledgeGraphBuilderRequest(days_back=365)
        assert request.days_back == 365

    def test_knowledge_graph_builder_request_too_low(self):
        """Test KnowledgeGraphBuilderRequest with value below minimum"""
        from agents.agents.schemas import KnowledgeGraphBuilderRequest

        with pytest.raises(ValidationError):
            KnowledgeGraphBuilderRequest(days_back=0)

    def test_knowledge_graph_builder_request_too_high(self):
        """Test KnowledgeGraphBuilderRequest with value above maximum"""
        from agents.agents.schemas import KnowledgeGraphBuilderRequest

        with pytest.raises(ValidationError):
            KnowledgeGraphBuilderRequest(days_back=366)

    def test_entity_search_request_default(self):
        """Test EntitySearchRequest with default values"""
        from agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="test query")
        assert request.query == "test query"
        assert request.top_k == 10

    def test_entity_search_request_valid(self):
        """Test EntitySearchRequest with valid values"""
        from agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="search term", top_k=20)
        assert request.query == "search term"
        assert request.top_k == 20

    def test_entity_search_request_min_length(self):
        """Test EntitySearchRequest with minimum query length"""
        from agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="a")
        assert request.query == "a"

    def test_entity_search_request_max_length(self):
        """Test EntitySearchRequest with maximum query length"""
        from agents.agents.schemas import EntitySearchRequest

        query = "a" * 200
        request = EntitySearchRequest(query=query)
        assert len(request.query) == 200

    def test_entity_search_request_too_short(self):
        """Test EntitySearchRequest with query too short"""
        from agents.agents.schemas import EntitySearchRequest

        with pytest.raises(ValidationError):
            EntitySearchRequest(query="")

    def test_entity_search_request_too_long(self):
        """Test EntitySearchRequest with query too long"""
        from agents.agents.schemas import EntitySearchRequest

        with pytest.raises(ValidationError):
            EntitySearchRequest(query="a" * 201)

    def test_entity_search_request_top_k_min(self):
        """Test EntitySearchRequest with minimum top_k"""
        from agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="test", top_k=1)
        assert request.top_k == 1

    def test_entity_search_request_top_k_max(self):
        """Test EntitySearchRequest with maximum top_k"""
        from agents.agents.schemas import EntitySearchRequest

        request = EntitySearchRequest(query="test", top_k=100)
        assert request.top_k == 100

    def test_entity_search_request_top_k_too_low(self):
        """Test EntitySearchRequest with top_k below minimum"""
        from agents.agents.schemas import EntitySearchRequest

        with pytest.raises(ValidationError):
            EntitySearchRequest(query="test", top_k=0)

    def test_entity_search_request_top_k_too_high(self):
        """Test EntitySearchRequest with top_k above maximum"""
        from agents.agents.schemas import EntitySearchRequest

        with pytest.raises(ValidationError):
            EntitySearchRequest(query="test", top_k=101)
