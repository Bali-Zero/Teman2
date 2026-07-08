from __future__ import annotations

import pytest

from backend.services.misc.cultural_rag_service import CulturalRAGService


class _FakeCulturalInsights:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def query_insights(self, *, query: str, when_to_use: str | None, limit: int):
        self.calls.append({"query": query, "when_to_use": when_to_use, "limit": limit})
        return [{"content": "Use warm greetings.", "metadata": {"topic": "greeting"}, "score": 0.8}]


@pytest.mark.asyncio
async def test_get_cultural_context_maps_first_contact_to_usage_filter() -> None:
    insights = _FakeCulturalInsights()
    service = CulturalRAGService(cultural_insights_service=insights)

    result = await service.get_cultural_context(
        {
            "query": "ciao",
            "intent": "business_simple",
            "conversation_stage": "first_contact",
        },
        limit=4,
    )

    assert result == [
        {"content": "Use warm greetings.", "metadata": {"topic": "greeting"}, "score": 0.8},
    ]
    assert insights.calls == [
        {"query": "ciao", "when_to_use": "first_contact", "limit": 4},
    ]


@pytest.mark.asyncio
async def test_get_cultural_context_uses_null_provider_when_unconfigured() -> None:
    service = CulturalRAGService()

    assert await service.get_cultural_context({"query": "hello"}) == []


def test_build_cultural_prompt_injection_filters_low_relevance_chunks() -> None:
    service = CulturalRAGService(cultural_insights_service=_FakeCulturalInsights())

    prompt = service.build_cultural_prompt_injection(
        [
            {
                "content": "High-context communication matters.",
                "metadata": {"topic": "face_saving_culture"},
                "score": 0.75,
            },
            {
                "content": "Too weak to include.",
                "metadata": {"topic": "noise"},
                "score": 0.1,
            },
        ],
    )

    assert "Face Saving Culture" in prompt
    assert "High-context communication matters." in prompt
    assert "Too weak to include" not in prompt
    assert "How to use this intelligence" in prompt


def test_build_cultural_prompt_injection_returns_empty_string_without_chunks() -> None:
    service = CulturalRAGService(cultural_insights_service=_FakeCulturalInsights())

    assert service.build_cultural_prompt_injection([]) == ""


@pytest.mark.asyncio
async def test_get_cultural_topics_coverage_returns_expected_seed_topics() -> None:
    service = CulturalRAGService(cultural_insights_service=_FakeCulturalInsights())

    coverage = await service.get_cultural_topics_coverage()

    assert coverage["indonesian_greetings"] == 1
    assert coverage["tri_hita_karana"] == 1
    assert len(coverage) == 10
