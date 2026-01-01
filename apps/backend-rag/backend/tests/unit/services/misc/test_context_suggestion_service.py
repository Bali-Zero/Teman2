"""
Unit tests for ContextSuggestionService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.context_suggestion_service import ContextSuggestionService, get_context_suggestion_service


class TestContextSuggestionService:
    """Tests for ContextSuggestionService"""

    def test_init(self):
        """Test initialization"""
        service = ContextSuggestionService()
        assert service.db_pool is None

    def test_init_with_db_pool(self):
        """Test initialization with db_pool"""
        mock_pool = MagicMock()
        service = ContextSuggestionService(db_pool=mock_pool)
        assert service.db_pool == mock_pool

    @pytest.mark.asyncio
    async def test_get_suggestions_empty(self):
        """Test getting suggestions (currently returns empty)"""
        service = ContextSuggestionService()
        suggestions = await service.get_suggestions(
            query="What is KITAS?",
            user_id="user123",
            response="KITAS is a work permit"
        )
        assert suggestions == []

    @pytest.mark.asyncio
    async def test_get_suggestions_with_history(self):
        """Test getting suggestions with conversation history"""
        service = ContextSuggestionService()
        history = [
            {"role": "user", "content": "What is KITAS?"},
            {"role": "assistant", "content": "KITAS is a work permit"}
        ]
        suggestions = await service.get_suggestions(
            query="What is KITAS?",
            user_id="user123",
            response="KITAS is a work permit",
            conversation_history=history
        )
        assert suggestions == []

    def test_get_context_suggestion_service_singleton(self):
        """Test singleton pattern"""
        service1 = get_context_suggestion_service()
        service2 = get_context_suggestion_service()
        assert service1 is service2

    def test_get_context_suggestion_service_with_pool(self):
        """Test getting service with db_pool"""
        # Reset singleton first
        import services.misc.context_suggestion_service as module
        module._context_suggestion_service = None
        
        mock_pool = MagicMock()
        service = get_context_suggestion_service(db_pool=mock_pool)
        assert service.db_pool == mock_pool

