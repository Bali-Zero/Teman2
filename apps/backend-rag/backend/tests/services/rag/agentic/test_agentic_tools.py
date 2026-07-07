import json

import pytest

from backend.services.rag.agentic.tools import (
    CalculatorTool,
    ImageGenerationTool,
    PricingTool,
    TeamKnowledgeTool,
    VectorSearchTool,
)


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "query": query,
                "user_level": user_level,
                "limit": limit,
                "collection": collection_override,
            },
        )
        return {
            "results": [
                {
                    "text": "PT PMA requires shareholder identity documents.",
                    "score": 0.92,
                    "metadata": {
                        "title": "PT PMA checklist",
                        "document_id": "doc-1",
                        "url": "https://example.test/pma",
                    },
                },
                {
                    "text": "PT PMA requires shareholder identity documents.",
                    "score": 0.50,
                    "metadata": {"title": "Duplicate"},
                },
            ],
        }


class FakePricingService:
    def __init__(self, loaded: bool = True) -> None:
        self.loaded = loaded
        self.search_queries: list[str] = []
        self.categories: list[str] = []

    def search_service(self, query: str) -> dict[str, object]:
        self.search_queries.append(query)
        return {"query": query, "price_idr": 12_000_000}

    def get_pricing(self, service_type: str) -> dict[str, object]:
        self.categories.append(service_type)
        return {"service_type": service_type, "items": 3}


@pytest.mark.asyncio
async def test_vector_search_uses_selected_collection_and_deduplicates_results() -> None:
    retriever = FakeRetriever()
    tool = VectorSearchTool(retriever=retriever, user_level=2)

    result = json.loads(
        await tool.execute(query="PT PMA checklist", collection="legal_unified", top_k=5),
    )

    assert retriever.calls == [
        {
            "query": "PT PMA checklist",
            "user_level": 2,
            "limit": 5,
            "collection": "legal_unified",
        },
    ]
    assert result["sources"] == [
        {
            "id": 1,
            "title": "PT PMA checklist",
            "url": "https://example.test/pma",
            "score": 0.92,
            "collection": "legal_unified",
            "doc_id": "doc-1",
            "snippet": "PT PMA requires shareholder identity documents.",
        },
    ]
    assert "Source: legal_unified" in result["content"]
    assert "ID: doc-1" in result["content"]


@pytest.mark.asyncio
async def test_calculator_formats_integer_and_rejects_unsafe_expression() -> None:
    tool = CalculatorTool()

    assert await tool.execute(expression="1000000 * 0.22") == "Result: 220,000"

    unsafe_result = await tool.execute(expression="__import__('os').system('id')")
    assert unsafe_result.startswith("Error in mathematical expression:")


@pytest.mark.asyncio
async def test_pricing_tool_uses_query_search_and_fails_closed_when_unloaded() -> None:
    service = FakePricingService()
    tool = PricingTool(pricing_service=service)

    assert await tool.execute(service_type="visa", query="D12") == str(
        {"query": "D12", "price_idr": 12_000_000},
    )
    assert service.search_queries == ["D12"]

    unavailable = await PricingTool(pricing_service=FakePricingService(loaded=False)).execute(
        service_type="all",
    )
    assert "Pricing service unavailable" in unavailable
    assert "DO NOT guess" not in unavailable


@pytest.mark.asyncio
async def test_team_knowledge_reads_json_and_searches_case_insensitively(tmp_path) -> None:
    team_file = tmp_path / "team_members.json"
    team_file.write_text(
        json.dumps(
            [
                {"name": "Ayu", "role": "Visa Specialist", "email": "ayu@example.test"},
                {"name": "Bima", "role": "Tax Advisor", "email": "bima@example.test"},
            ],
        ),
    )
    tool = TeamKnowledgeTool()
    tool._data_file = team_file

    all_members = json.loads(await tool.execute(query_type="list_all"))
    matches = json.loads(
        await tool.execute(query_type="search_by_role", search_term="visa specialist"),
    )

    assert all_members == [
        {"name": "Ayu", "role": "Visa Specialist"},
        {"name": "Bima", "role": "Tax Advisor"},
    ]
    assert matches["count"] == 1
    assert matches["matches"][0]["name"] == "Ayu"


@pytest.mark.asyncio
async def test_image_generation_returns_encoded_pollinations_url() -> None:
    result = json.loads(
        await ImageGenerationTool().execute(
            prompt="Bali Zero office with clients",
            aspect_ratio="16:9",
        ),
    )

    assert result["success"] is True
    assert result["service"] == "pollinations"
    assert "Bali%20Zero%20office%20with%20clients" in result["image_url"]
    assert "width=1024&height=576" in result["image_url"]
