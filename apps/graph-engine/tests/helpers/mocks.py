"""Mock services for testing graph nodes."""

from __future__ import annotations

import json
from typing import Any

from nuzantara_graph.services import Services
from nuzantara_graph.services.llm_gateway import LLMGateway, LLMResponse
from nuzantara_graph.services.vector_store import VectorStore
from nuzantara_graph.services.kg_store import KGStore
from nuzantara_schemas.state import RetrievedDocument


class MockLLMGateway(LLMGateway):
    """LLM gateway that returns pre-configured responses."""

    def __init__(self, responses: dict[str, Any] | None = None):
        super().__init__()
        self._responses = responses or {}
        self._call_count = 0
        self._last_prompt = ""
        self._last_system = ""

    async def generate(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        self._call_count += 1
        self._last_prompt = prompt
        self._last_system = system
        content = self._responses.get("generate", '{"result": "mock"}')
        if callable(content):
            content = content(prompt, system)
        return LLMResponse(
            content=content if isinstance(content, str) else json.dumps(content),
            model="mock-model",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
        )

    async def generate_json(self, prompt: str, system: str = "", **kwargs) -> dict[str, Any]:
        self._call_count += 1
        self._last_prompt = prompt
        self._last_system = system
        result = self._responses.get("generate_json", {"result": "mock"})
        if callable(result):
            result = result(prompt, system)
        return result


class MockVectorStore(VectorStore):
    """Vector store that returns pre-configured documents."""

    def __init__(self, documents: list[RetrievedDocument] | None = None):
        super().__init__()
        self.documents = documents or []

    async def search_by_text(self, query: str, **kwargs) -> list[RetrievedDocument]:
        return self.documents

    async def search(self, query_embedding: list[float], **kwargs) -> list[RetrievedDocument]:
        return self.documents


class MockKGStore(KGStore):
    """KG store that returns pre-configured entities and relationships."""

    def __init__(
        self,
        entities: list[dict[str, Any]] | None = None,
        relationships: list[dict[str, Any]] | None = None,
    ):
        super().__init__()
        self._entities = entities or []
        self._relationships = relationships or []

    async def get_entities(self, **kwargs) -> list[dict[str, Any]]:
        return self._entities

    async def get_relationships(self, **kwargs) -> list[dict[str, Any]]:
        return self._relationships

    async def search_entities(self, **kwargs) -> list[dict[str, Any]]:
        return self._entities


def make_mock_services(
    llm_responses: dict[str, Any] | None = None,
    documents: list[RetrievedDocument] | None = None,
    kg_entities: list[dict[str, Any]] | None = None,
    kg_relationships: list[dict[str, Any]] | None = None,
) -> Services:
    """Create a Services container with all mocks configured."""
    return Services(
        llm=MockLLMGateway(responses=llm_responses),
        vector_store=MockVectorStore(documents=documents),
        kg_store=MockKGStore(entities=kg_entities, relationships=kg_relationships),
    )
