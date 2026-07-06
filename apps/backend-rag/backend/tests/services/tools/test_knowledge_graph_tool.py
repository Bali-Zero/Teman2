import pytest

from backend.services.tools.knowledge_graph_tool import KnowledgeGraphTool


class FakeKnowledgeGraphBuilder:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[tuple[str, int]] = []

    async def query_graph(self, entity_name: str, max_depth: int) -> dict:
        self.calls.append((entity_name, max_depth))
        return self.result


def test_knowledge_graph_tool_metadata_and_schema() -> None:
    tool = KnowledgeGraphTool(FakeKnowledgeGraphBuilder({"found": False}))

    assert tool.name == "knowledge_graph_search"
    assert "knowledge graph" in tool.description.lower()
    assert tool.parameters_schema["required"] == ["entity"]
    assert "depth" in tool.parameters_schema["properties"]


@pytest.mark.asyncio
async def test_execute_clamps_depth_and_returns_not_found_message() -> None:
    builder = FakeKnowledgeGraphBuilder({"found": False})
    tool = KnowledgeGraphTool(builder)

    result = await tool.execute(entity="PT PMA", depth=99)

    assert builder.calls == [("PT PMA", 2)]
    assert "No entity found" in result
    assert "PT PMA" in result


@pytest.mark.asyncio
async def test_execute_formats_relationships_and_filters_by_type() -> None:
    builder = FakeKnowledgeGraphBuilder(
        {
            "found": True,
            "query": "PT PMA",
            "total_entities": 3,
            "total_relationships": 2,
            "start_entity": {
                "entity_id": "pt-pma",
                "name": "PT PMA",
                "entity_type": "company",
                "description": "Foreign-owned company",
            },
            "entities": [
                {"entity_id": "pt-pma", "name": "PT PMA"},
                {"entity_id": "nib", "name": "NIB"},
                {"entity_id": "cost", "name": "Setup Cost"},
            ],
            "relationships": [
                {
                    "source_entity_id": "pt-pma",
                    "target_entity_id": "nib",
                    "relationship_type": "requires",
                    "properties": {"stage": "setup", "confidence": 0.91},
                },
                {
                    "source_entity_id": "pt-pma",
                    "target_entity_id": "cost",
                    "relationship_type": "costs",
                    "properties": {},
                },
            ],
        }
    )
    tool = KnowledgeGraphTool(builder)

    result = await tool.execute(entity="PT PMA", depth=0, relationship_type="requires")

    assert builder.calls == [("PT PMA", 1)]
    assert "Found subgraph for 'PT PMA' (3 nodes, 2 edges):" in result
    assert "[FOCUS] PT PMA (company)" in result
    assert "[This] --REQUIRES--> NIB (stage=setup)" in result
    assert "COSTS" not in result
