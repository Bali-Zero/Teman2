"""
Unit tests for agents/agents/schemas.py
Target: 100% coverage
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.agents.schemas import (
    ConversationTrainerRequest,
    EntitySearchRequest,
    KnowledgeGraphBuilderRequest,
)


class TestConversationTrainerRequest:
    """Tests for ConversationTrainerRequest schema"""

    def test_default_values(self):
        """Test default values"""
        request = ConversationTrainerRequest()
        assert request.days_back == 7

    def test_valid_days_back(self):
        """Test valid days_back values"""
        request = ConversationTrainerRequest(days_back=30)
        assert request.days_back == 30

    def test_min_days_back(self):
        """Test minimum days_back value"""
        request = ConversationTrainerRequest(days_back=1)
        assert request.days_back == 1

    def test_max_days_back(self):
        """Test maximum days_back value"""
        request = ConversationTrainerRequest(days_back=365)
        assert request.days_back == 365

    def test_invalid_days_back_zero(self):
        """Test invalid days_back (0)"""
        with pytest.raises(ValidationError):
            ConversationTrainerRequest(days_back=0)

    def test_invalid_days_back_negative(self):
        """Test invalid days_back (negative)"""
        with pytest.raises(ValidationError):
            ConversationTrainerRequest(days_back=-1)

    def test_invalid_days_back_too_large(self):
        """Test invalid days_back (> 365)"""
        with pytest.raises(ValidationError):
            ConversationTrainerRequest(days_back=366)


class TestKnowledgeGraphBuilderRequest:
    """Tests for KnowledgeGraphBuilderRequest schema"""

    def test_default_values(self):
        """Test default values"""
        request = KnowledgeGraphBuilderRequest()
        assert request.days_back == 30
        assert request.init_schema is False

    def test_custom_days_back(self):
        """Test custom days_back"""
        request = KnowledgeGraphBuilderRequest(days_back=60)
        assert request.days_back == 60

    def test_init_schema_true(self):
        """Test init_schema=True"""
        request = KnowledgeGraphBuilderRequest(init_schema=True)
        assert request.init_schema is True

    def test_min_days_back(self):
        """Test minimum days_back value"""
        request = KnowledgeGraphBuilderRequest(days_back=1)
        assert request.days_back == 1

    def test_max_days_back(self):
        """Test maximum days_back value"""
        request = KnowledgeGraphBuilderRequest(days_back=365)
        assert request.days_back == 365

    def test_invalid_days_back_zero(self):
        """Test invalid days_back (0)"""
        with pytest.raises(ValidationError):
            KnowledgeGraphBuilderRequest(days_back=0)

    def test_invalid_days_back_too_large(self):
        """Test invalid days_back (> 365)"""
        with pytest.raises(ValidationError):
            KnowledgeGraphBuilderRequest(days_back=366)


class TestEntitySearchRequest:
    """Tests for EntitySearchRequest schema"""

    def test_valid_request(self):
        """Test valid request"""
        request = EntitySearchRequest(query="PT PMA")
        assert request.query == "PT PMA"
        assert request.top_k == 10  # default

    def test_custom_top_k(self):
        """Test custom top_k"""
        request = EntitySearchRequest(query="KITAS", top_k=20)
        assert request.query == "KITAS"
        assert request.top_k == 20

    def test_min_top_k(self):
        """Test minimum top_k value"""
        request = EntitySearchRequest(query="test", top_k=1)
        assert request.top_k == 1

    def test_max_top_k(self):
        """Test maximum top_k value"""
        request = EntitySearchRequest(query="test", top_k=100)
        assert request.top_k == 100

    def test_invalid_top_k_zero(self):
        """Test invalid top_k (0)"""
        with pytest.raises(ValidationError):
            EntitySearchRequest(query="test", top_k=0)

    def test_invalid_top_k_too_large(self):
        """Test invalid top_k (> 100)"""
        with pytest.raises(ValidationError):
            EntitySearchRequest(query="test", top_k=101)

    def test_empty_query(self):
        """Test empty query string"""
        with pytest.raises(ValidationError):
            EntitySearchRequest(query="")

    def test_query_max_length(self):
        """Test query at max length (200)"""
        long_query = "a" * 200
        request = EntitySearchRequest(query=long_query)
        assert len(request.query) == 200

    def test_query_too_long(self):
        """Test query exceeding max length"""
        too_long_query = "a" * 201
        with pytest.raises(ValidationError):
            EntitySearchRequest(query=too_long_query)
