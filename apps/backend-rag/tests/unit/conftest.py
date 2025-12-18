"""
Shared fixtures for unit tests
ZANTARA Backend Test Configuration

This conftest.py provides common fixtures used across all unit tests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def mock_settings():
    """Mock settings object with all required attributes"""
    settings = MagicMock()
    settings.jwt_secret_key = "test-secret-key-minimum-32-characters-long"
    settings.openai_api_key = "test-openai-key"
    settings.anthropic_api_key = "test-anthropic-key"
    settings.google_api_key = "test-google-key"
    settings.qdrant_url = "https://qdrant.test.com"
    settings.qdrant_api_key = "test-qdrant-key"
    settings.database_url = "postgresql://test:test@localhost:5432/test"
    return settings


@pytest.fixture
def mock_logger():
    """Mock logger that captures all calls"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def mock_classifier():
    """Mock IntentClassifier with async methods"""
    classifier = AsyncMock()
    classifier.classify_intent = AsyncMock(
        return_value={
            "category": "business_simple",
            "suggested_ai": "zantara-ai",
            "confidence": 0.8,
        }
    )
    return classifier


@pytest.fixture
def mock_context_builder():
    """Mock ContextBuilder with all required methods"""
    builder = MagicMock()
    builder.build_memory_context = MagicMock(return_value="")
    builder.build_team_context = MagicMock(return_value="")
    builder.combine_contexts = MagicMock(return_value="")
    builder.detect_identity_query = MagicMock(return_value=False)
    builder.detect_zantara_query = MagicMock(return_value=False)
    builder.detect_team_query = MagicMock(return_value=False)
    return builder


@pytest.fixture
def mock_rag_manager():
    """Mock RAGManager with async methods"""
    manager = AsyncMock()
    manager.retrieve_context = AsyncMock(
        return_value={
            "context": "",
            "used_rag": False,
            "docs": [],
        }
    )
    return manager


@pytest.fixture
def mock_response_handler():
    """Mock ResponseHandler with all required methods"""
    handler = MagicMock()
    handler.classify_query = MagicMock(return_value="business")
    handler.sanitize_response = MagicMock(return_value="Sanitized response")
    return handler


@pytest.fixture
def mock_specialized_router():
    """Mock SpecializedServiceRouter with all detection methods"""
    router = MagicMock()
    router.detect_autonomous_research = MagicMock(return_value=False)
    router.detect_cross_oracle = MagicMock(return_value=False)
    router.detect_client_journey = MagicMock(return_value=False)
    return router


@pytest.fixture
def mock_ai_client():
    """Mock ZantaraAIClient with all required methods"""
    client = AsyncMock()
    client.conversational = AsyncMock(
        return_value={
            "text": "AI response",
            "model": "zantara-ai",
            "tokens": {"input": 100, "output": 50},
        }
    )
    client.conversational_with_tools = AsyncMock(
        return_value={
            "text": "AI response with tools",
            "model": "zantara-ai",
            "tokens": {"input": 100, "output": 50},
            "used_tools": True,
            "tools_called": ["tool1"],
        }
    )
    client.stream = AsyncMock()
    client.is_available = MagicMock(return_value=True)
    return client


@pytest.fixture
def mock_search_service():
    """Mock SearchService with async methods"""
    service = AsyncMock()
    service.search = AsyncMock(return_value=[])
    service.hybrid_search = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_tool_executor():
    """Mock ToolExecutor with all required methods"""
    executor = MagicMock()
    executor.get_available_tools = MagicMock(return_value=[{"name": "tool1"}])
    executor.execute_tool = AsyncMock(return_value={"result": "tool result"})
    return executor


@pytest.fixture
def mock_cultural_rag_service():
    """Mock CulturalRAGService with async methods"""
    service = AsyncMock()
    service.get_cultural_context = AsyncMock(return_value=[])
    service.build_cultural_prompt_injection = MagicMock(return_value="Cultural context")
    return service


@pytest.fixture
def mock_personality_service():
    """Mock PersonalityService with async methods"""
    service = AsyncMock()
    service.fast_chat = AsyncMock(
        return_value={
            "response": "Fast response",
            "ai_used": "personality",
            "category": "greeting",
        }
    )
    return service


@pytest.fixture
def mock_autonomous_research_service():
    """Mock AutonomousResearchService with async methods"""
    service = AsyncMock()
    service.research = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_cross_oracle_service():
    """Mock CrossOracleSynthesisService with async methods"""
    service = AsyncMock()
    service.synthesize = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_client_journey_orchestrator():
    """Mock ClientJourneyOrchestrator with async methods"""
    service = AsyncMock()
    service.orchestrate = AsyncMock(return_value=None)
    return service
