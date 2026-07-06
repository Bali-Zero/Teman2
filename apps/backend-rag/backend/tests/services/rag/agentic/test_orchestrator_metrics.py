import logging
from types import SimpleNamespace

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic import orchestrator_metrics
from backend.services.rag.agentic.orchestrator_metrics import OrchestratorMetricsManager
from backend.services.tools.definitions import AgentState, AgentStep, ToolCall


class FakeMetricsCollector:
    def __init__(self) -> None:
        self.rag_queries: list[dict[str, object]] = []
        self.rag_detailed: list[dict[str, object]] = []
        self.llm_usage: list[dict[str, object]] = []

    def record_rag_query(self, **kwargs) -> None:
        self.rag_queries.append(kwargs)

    def record_rag_detailed_metrics(self, **kwargs) -> None:
        self.rag_detailed.append(kwargs)

    def record_llm_token_usage(self, **kwargs) -> None:
        self.llm_usage.append(kwargs)


def build_state() -> AgentState:
    return AgentState(
        query="PT PMA requirements",
        steps=[
            AgentStep(
                step_number=1,
                thought="search",
                action=ToolCall(
                    tool_name="vector_search",
                    arguments={"collection": "legal_unified"},
                    result="source A",
                    execution_time=0.25,
                ),
                observation="abcde",
            ),
            AgentStep(
                step_number=2,
                thought="calculate",
                action=ToolCall(
                    tool_name="calculator",
                    arguments={"expression": "100 * 2"},
                    result="200",
                    execution_time=0.05,
                ),
                observation="xyz",
            ),
        ],
    )


def test_extract_timings_from_state_separates_search_tools_and_llm(monkeypatch) -> None:
    manager = OrchestratorMetricsManager()
    state = build_state()
    monkeypatch.setattr(orchestrator_metrics.time, "time", lambda: 110.0)

    timings = manager.extract_timings_from_state(
        state=state,
        reasoning_duration=1.0,
        start_time=100.0,
    )

    assert timings["total"] == 10.0
    assert timings["tools"] == 0.30
    assert timings["search"] == 0.25
    assert timings["llm"] == 0.70
    assert timings["reasoning"] == 1.0


def test_extract_state_collections_sources_and_context_length() -> None:
    manager = OrchestratorMetricsManager()
    state = build_state()

    assert manager.extract_collections_from_state(state) == {"legal_unified"}
    assert manager.extract_sources_from_state(state) == ["source A", "200"]
    assert manager.calculate_context_used(state) == len("abcde") + len("xyz")

    state.sources = [{"title": "preferred"}]
    assert manager.extract_sources_from_state(state) == [{"title": "preferred"}]


def test_record_rag_and_token_metrics(monkeypatch) -> None:
    collector = FakeMetricsCollector()
    monkeypatch.setattr(orchestrator_metrics, "metrics_collector", collector)
    state = build_state()
    state.evidence_score = 0.82

    manager = OrchestratorMetricsManager()
    manager.record_rag_metrics(
        state=state,
        collections_used={"legal_unified"},
        tool_execution_count=2,
        context_used=64,
        execution_time=1.25,
        sources=["source A", "source B"],
    )
    manager.record_token_usage(
        model_used="gemini-test",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001),
        endpoint="rag",
    )

    assert collector.rag_queries == [
        {
            "collection": "legal_unified",
            "route_used": "agentic",
            "status": "success",
            "context_tokens": 64,
        },
    ]
    assert collector.rag_detailed[0]["documents_count"] == 2
    assert collector.rag_detailed[0]["evidence_score"] == 0.82
    assert collector.llm_usage == [
        {
            "model": "gemini-test",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost_usd": 0.001,
            "endpoint": "rag",
        },
    ]


def test_log_query_completion_emits_structured_extra(caplog) -> None:
    manager = OrchestratorMetricsManager()
    state = build_state()
    state.evidence_score = 0.91

    with caplog.at_level(logging.INFO, logger=orchestrator_metrics.logger.name):
        manager.log_query_completion(
            user_id=None,
            query="PT PMA requirements",
            model_used="gemini-test",
            execution_time=1.2345,
            state=state,
            collections_used={"legal_unified"},
            tool_execution_count=1,
            token_usage=SimpleNamespace(total_tokens=99, cost_usd=0.012345),
        )

    record = caplog.records[-1]
    assert record.user_id == "anonymous"
    assert record.model_used == "gemini-test"
    assert record.duration_s == 1.234
    assert record.route == "agentic"
    assert record.tools == ["legal_unified"]
