from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic import orchestrator_core
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.rag.agentic.schema import CoreResult
from backend.services.tools.definitions import AgentState


class FakeEmbedder:
    async def generate_query_embedding(self, query: str) -> list[float]:
        assert query == "cached query"
        return [0.1, 0.2, 0.3]


class FakeSemanticCache:
    def __init__(self, cached: dict | None) -> None:
        self.cached = cached
        self.calls: list[tuple[str, object]] = []

    async def get_cached_result(self, query: str, query_embedding) -> dict | None:
        self.calls.append((query, query_embedding))
        return self.cached


def make_core() -> OrchestratorCore:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.semantic_cache = None
    core.retriever = None
    core.entity_extractor = None
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None
    core.db_pool = None
    core.reasoning_engine = None
    core.llm_gateway = object()
    core.context_manager = None
    core.query_gates = None
    core.prompt_builder = None
    core.routing_manager = None
    return core


@pytest.mark.asyncio
async def test_check_semantic_cache_returns_core_result_with_embedding(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_core.time, "time", lambda: 12.0)
    core = make_core()
    core.retriever = SimpleNamespace(embedder=FakeEmbedder())
    core.semantic_cache = FakeSemanticCache(
        {
            "result": {
                "answer": "cached answer",
                "sources": [{"title": "source"}],
            },
        },
    )

    result = await core.check_semantic_cache(
        query="cached query",
        extracted_entities={"visa": ["KITAS"]},
        start_time=10.0,
    )

    assert result is not None
    assert result.answer == "cached answer"
    assert result.cache_hit is True
    assert result.entities == {"visa": ["KITAS"]}
    assert result.timings == {"total": 2.0}
    assert core.semantic_cache.calls[0][0] == "cached query"
    assert core.semantic_cache.calls[0][1].tolist() == pytest.approx([0.1, 0.2, 0.3])


@pytest.mark.asyncio
async def test_extract_entities_and_kg_context_merges_entity_and_graph_summary() -> None:
    core = make_core()
    core.entity_extractor = SimpleNamespace(
        extract_entities=AsyncMock(return_value={"visa_types": ["KITAS"]}),
    )
    core.kg_retrieval = SimpleNamespace(
        get_context_for_query=AsyncMock(
            return_value=SimpleNamespace(
                graph_summary="KG summary",
                entities_found=["KITAS"],
                relationships=["REQUIRES"],
            ),
        ),
    )

    entities, prompt_context, workflow = await core.extract_entities_and_kg_context("KITAS docs")

    assert entities == {"visa_types": ["KITAS"]}
    assert "KNOWN ENTITIES" in prompt_context
    assert "KG summary" in prompt_context
    assert workflow is None


@pytest.mark.asyncio
async def test_execute_react_loop_wraps_reasoning_engine_result() -> None:
    state = AgentState(query="question")
    usage = TokenUsage(prompt_tokens=3, completion_tokens=4, cost_usd=0.0)

    async def fake_execute_react_loop(**kwargs):
        assert kwargs["query"] == "question"
        assert kwargs["user_id"] == "user-1"
        assert kwargs["initial_prompt"] != "question"
        return state, "gemini-test", [{"role": "user"}], usage

    core = make_core()
    core.reasoning_engine = SimpleNamespace(execute_react_loop=fake_execute_react_loop)

    result_state, model, token_usage, duration = await core.execute_react_loop(
        state=state,
        chat=object(),
        system_prompt="system",
        query="question",
        user_id="user-1",
        model_tier="flash",
        tool_execution_counter={"count": 0},
    )

    assert result_state is state
    assert model == "gemini-test"
    assert token_usage is usage
    assert duration >= 0


@pytest.mark.asyncio
async def test_prepare_query_context_falls_back_when_context_loading_fails() -> None:
    core = make_core()
    core.context_manager = SimpleNamespace(
        get_full_context=AsyncMock(side_effect=RuntimeError("context down")),
    )
    core.extract_entities_and_kg_context = AsyncMock(
        return_value=({"entities": []}, "kg context", None),
    )

    user_context, history, entities, kg_context, workflow = await core.prepare_query_context(
        query="question",
        user_id="user-1",
        conversation_history=[{"role": "user"}],
    )

    assert user_context == {}
    assert history == []
    assert entities == {"entities": []}
    assert kg_context == "kg context"
    assert workflow is None


@pytest.mark.asyncio
async def test_check_gates_and_cache_returns_gate_before_cache() -> None:
    gate_result = SimpleNamespace(triggered=True)
    core_result = CoreResult(answer="gate", model_used="identity-gate")
    core = make_core()
    core.query_gates = SimpleNamespace(
        run_all_gates=lambda **kwargs: gate_result,
        gate_result_to_core_result=lambda **kwargs: core_result,
    )
    core.check_semantic_cache = AsyncMock()

    result = await core.check_gates_and_cache(
        query="who are you",
        user_context={},
        history=[],
        extracted_entities={},
        start_time=0.0,
    )

    assert result is core_result
    core.check_semantic_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_react_execution_stamps_agent_role_and_channel(monkeypatch) -> None:
    state = AgentState(query="question")
    core = make_core()
    core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    core.prompt_builder = SimpleNamespace(
        build_system_prompt=lambda **kwargs: f"PROMPT:{kwargs['additional_context']}",
    )
    monkeypatch.setattr(orchestrator_core, "build_channel_context", lambda channel: f"{channel}:ctx")

    model_tier, deep_think, prepared_state, prompt = await core.prepare_react_execution(
        query="question",
        user_context={"profile": {"id": "user-1"}},
        history=[],
        extracted_entities={},
        kg_context_str="KG",
        channel="whatsapp",
        agent_role="ops",
    )

    assert model_tier == "flash"
    assert deep_think is False
    assert prepared_state is state
    assert prepared_state.agent_role == "ops"
    assert prompt == "PROMPT:KG\n\nwhatsapp:ctx"
