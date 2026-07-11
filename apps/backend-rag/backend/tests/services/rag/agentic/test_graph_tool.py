from types import SimpleNamespace

import pytest

from backend.services.rag.agentic.graph_tool import GraphTraversalTool


class FakeGraphService:
    def __init__(self, candidates: list[SimpleNamespace] | None = None) -> None:
        self.candidates = candidates or []
        self.traverse_calls: list[tuple[str, int]] = []

    async def find_entity_by_name(self, entity_name: str, limit: int) -> list[SimpleNamespace]:
        assert entity_name == "Investor KITAS"
        assert limit == 1
        return self.candidates

    async def traverse(self, start_id: str, max_depth: int) -> dict[str, list[dict[str, str]]]:
        self.traverse_calls.append((start_id, max_depth))
        return {
            "nodes": [
                {"id": "n1", "name": "Investor KITAS"},
                {"id": "n2", "name": "PT PMA"},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "type": "REQUIRES"},
            ],
        }


def test_graph_tool_schema_exposes_required_entity_name() -> None:
    tool = GraphTraversalTool(graph_service=FakeGraphService())

    assert tool.name == "graph_traversal"
    assert tool.parameters_schema["required"] == ["entity_name"]
    assert "depth" in tool.parameters_schema["properties"]


@pytest.mark.asyncio
async def test_execute_traverses_first_candidate_and_clamps_depth() -> None:
    graph = FakeGraphService(
        candidates=[SimpleNamespace(id="n1", name="Investor KITAS", type="Visa")],
    )
    tool = GraphTraversalTool(graph_service=graph)

    result = await tool.execute(entity_name="Investor KITAS", depth=99)

    assert graph.traverse_calls == [("n1", 3)]
    assert "Found Entity: Investor KITAS (Visa)" in result
    assert "- [REQUIRES] -> PT PMA" in result


@pytest.mark.asyncio
async def test_execute_returns_helpful_message_when_entity_missing() -> None:
    result = await GraphTraversalTool(graph_service=FakeGraphService()).execute(
        entity_name="Investor KITAS",
    )

    assert "No entity found" in result
    assert "Investor KITAS" in result
