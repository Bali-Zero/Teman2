import pytest

from backend.services.rag.agentic.orchestrator_routing import OrchestratorRoutingManager
from backend.services.rag.agentic.query_helpers import TIER_FLASH, TIER_PRO


class FakeIntentClassifier:
    def __init__(self, intent: dict[str, object]) -> None:
        self.intent = intent
        self.queries: list[str] = []

    async def classify_intent(self, query: str) -> dict[str, object]:
        self.queries.append(query)
        return self.intent


@pytest.mark.asyncio
async def test_classify_intent_delegates_to_classifier() -> None:
    classifier = FakeIntentClassifier({"suggested_ai": "pro"})
    manager = OrchestratorRoutingManager(intent_classifier=classifier)

    assert await manager.classify_intent("Need complex PT PMA advice") == {"suggested_ai": "pro"}
    assert classifier.queries == ["Need complex PT PMA advice"]


@pytest.mark.parametrize(
    ("intent", "expected_tier", "expected_deep"),
    [
        ({"suggested_ai": "deep_think"}, TIER_PRO, True),
        ({"suggested_ai": "pro"}, TIER_PRO, False),
        ({"suggested_ai": "FLASH"}, TIER_FLASH, False),
        ({}, TIER_FLASH, False),
    ],
)
def test_select_model_tier(intent, expected_tier, expected_deep) -> None:
    assert OrchestratorRoutingManager(
        intent_classifier=FakeIntentClassifier({}),
    ).select_model_tier(intent) == (expected_tier, expected_deep)


def test_create_agent_state_carries_skip_rag_and_category() -> None:
    state = OrchestratorRoutingManager(
        intent_classifier=FakeIntentClassifier({}),
    ).create_agent_state(
        query="translate this",
        intent={"skip_rag": True, "category": "translation"},
    )

    assert state.query == "translate this"
    assert state.skip_rag is True
    assert state.intent_type == "translation"


@pytest.mark.asyncio
async def test_route_query_combines_intent_tier_and_agent_state() -> None:
    manager = OrchestratorRoutingManager(
        intent_classifier=FakeIntentClassifier(
            {"suggested_ai": "deep_think", "skip_rag": False, "category": "business_complex"},
        ),
    )

    model_tier, deep_think_mode, state = await manager.route_query("PT PMA risk analysis")

    assert model_tier == TIER_PRO
    assert deep_think_mode is True
    assert state.query == "PT PMA risk analysis"
    assert state.intent_type == "business_complex"
