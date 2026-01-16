"""
Unit tests for OrchestratorRoutingManager

Test coverage target: >95%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.rag.agentic.orchestrator_routing import OrchestratorRoutingManager
from backend.services.tools.definitions import AgentState


@pytest.fixture
def mock_intent_classifier():
    """Mock IntentClassifier"""
    classifier = MagicMock()
    classifier.classify_intent = AsyncMock(
        return_value={
            "suggested_ai": "FLASH",
            "deep_think_mode": False,
            "skip_rag": False,
            "category": "simple",
        }
    )
    return classifier


@pytest.fixture
def routing_manager(mock_intent_classifier):
    """Create OrchestratorRoutingManager instance"""
    return OrchestratorRoutingManager(intent_classifier=mock_intent_classifier)


@pytest.fixture
def routing_manager_default():
    """Create OrchestratorRoutingManager with default IntentClassifier"""
    return OrchestratorRoutingManager()


@pytest.mark.asyncio
async def test_classify_intent_success(routing_manager, mock_intent_classifier):
    """Test successful intent classification"""
    intent = await routing_manager.classify_intent("test query")

    assert intent["suggested_ai"] == "FLASH"
    assert intent["deep_think_mode"] is False
    mock_intent_classifier.classify_intent.assert_called_once_with("test query")


@pytest.mark.asyncio
async def test_select_model_tier_flash(routing_manager):
    """Test model tier selection for FLASH"""
    intent = {"suggested_ai": "FLASH", "deep_think_mode": False}
    tier, deep_think = routing_manager.select_model_tier(intent)

    from backend.services.rag.agentic.query_helpers import TIER_FLASH

    assert tier == TIER_FLASH
    assert deep_think is False


@pytest.mark.asyncio
async def test_select_model_tier_pro(routing_manager):
    """Test model tier selection for PRO"""
    intent = {"suggested_ai": "pro", "deep_think_mode": False}
    tier, deep_think = routing_manager.select_model_tier(intent)

    from backend.services.rag.agentic.query_helpers import TIER_PRO

    assert tier == TIER_PRO
    assert deep_think is False


@pytest.mark.asyncio
async def test_select_model_tier_deep_think(routing_manager):
    """Test model tier selection for deep_think"""
    intent = {"suggested_ai": "deep_think", "deep_think_mode": True}
    tier, deep_think = routing_manager.select_model_tier(intent)

    from backend.services.rag.agentic.query_helpers import TIER_PRO

    assert tier == TIER_PRO
    assert deep_think is True


@pytest.mark.asyncio
async def test_create_agent_state(routing_manager):
    """Test AgentState creation"""
    intent = {"skip_rag": False, "category": "business_complex"}
    state = routing_manager.create_agent_state("test query", intent)

    assert isinstance(state, AgentState)
    assert state.query == "test query"
    assert state.skip_rag is False
    assert state.intent_type == "business_complex"


@pytest.mark.asyncio
async def test_create_agent_state_defaults(routing_manager):
    """Test AgentState creation with default values"""
    intent = {}  # Empty intent
    state = routing_manager.create_agent_state("test query", intent)

    assert state.skip_rag is False
    assert state.intent_type == "simple"


@pytest.mark.asyncio
async def test_route_query_complete(routing_manager, mock_intent_classifier):
    """Test complete routing flow"""
    mock_intent_classifier.classify_intent.return_value = {
        "suggested_ai": "pro",
        "deep_think_mode": False,
        "skip_rag": False,
        "category": "business",
    }

    tier, deep_think, state = await routing_manager.route_query("test query")

    from backend.services.rag.agentic.query_helpers import TIER_PRO

    assert tier == TIER_PRO
    assert deep_think is False
    assert isinstance(state, AgentState)
    assert state.query == "test query"
    assert state.intent_type == "business"


@pytest.mark.asyncio
async def test_route_query_deep_think(routing_manager, mock_intent_classifier):
    """Test routing with deep think mode"""
    mock_intent_classifier.classify_intent.return_value = {
        "suggested_ai": "deep_think",
        "deep_think_mode": True,
        "skip_rag": False,
        "category": "complex",
    }

    tier, deep_think, state = await routing_manager.route_query("complex query")

    from backend.services.rag.agentic.query_helpers import TIER_PRO

    assert tier == TIER_PRO
    assert deep_think is True
    assert state.intent_type == "complex"


@pytest.mark.asyncio
async def test_routing_manager_default_init(routing_manager_default):
    """Test routing manager initialization with default IntentClassifier"""
    assert routing_manager_default.intent_classifier is not None
    # Should be able to classify without errors
    intent = await routing_manager_default.classify_intent("test")
    assert "suggested_ai" in intent
