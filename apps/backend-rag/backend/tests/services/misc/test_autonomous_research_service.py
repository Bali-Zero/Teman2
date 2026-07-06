from __future__ import annotations

import pytest

from backend.services.misc.autonomous_research_service import (
    AutonomousResearchService,
    ResearchStep,
)


class FakeRouter:
    def __init__(self, collections: list[str] | None = None) -> None:
        self.collections = collections or ["legal_updates", "tax_genius", "visa_oracle"]
        self.calls: list[dict[str, object]] = []

    def route_with_confidence(
        self,
        query: str,
        return_fallbacks: bool = False,
    ) -> tuple[str, float, list[str]]:
        self.calls.append({"query": query, "return_fallbacks": return_fallbacks})
        return self.collections[0], 0.88, self.collections


class FakeSearchService:
    def __init__(self, results: list[dict] | None = None) -> None:
        self.results = results or []
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
    ) -> dict[str, list[dict]]:
        self.calls.append(
            {
                "query": query,
                "user_level": user_level,
                "limit": limit,
                "collection_override": collection_override,
            },
        )
        return {"results": self.results}


class FakeZantaraService:
    def __init__(self, text: str = "Synthesized answer") -> None:
        self.text = text
        self.calls: list[dict[str, object]] = []

    async def conversational(self, **kwargs) -> dict[str, str]:
        self.calls.append(kwargs)
        return {"text": self.text}


def _service(
    *,
    results: list[dict] | None = None,
    collections: list[str] | None = None,
    synthesis: str = "Synthesized answer",
) -> tuple[AutonomousResearchService, FakeSearchService, FakeRouter, FakeZantaraService]:
    search = FakeSearchService(results)
    router = FakeRouter(collections)
    zantara = FakeZantaraService(synthesis)
    return AutonomousResearchService(search, router, zantara), search, router, zantara


@pytest.mark.asyncio
async def test_analyze_gaps_detects_insufficient_and_low_confidence_results() -> None:
    service, _, _, _ = _service()

    insufficient = await service.analyze_gaps("crypto company", [], [])
    low_confidence = await service.analyze_gaps(
        "crypto company",
        [{"text": "possible permit", "score": 0.2}, {"text": "uncertain", "score": 0.3}, {"text": "depends", "score": 0.4}],
        ["legal_updates"],
    )

    assert insufficient == (True, ["crypto company"], "Insufficient results found")
    assert low_confidence == (
        True,
        ["crypto company", "crypto company requirements", "crypto company process"],
        "Low confidence in current results",
    )


def test_select_next_collection_skips_previously_searched_collections() -> None:
    service, _, router, _ = _service(collections=["kbli", "legal", "tax"])

    assert service.select_next_collection("PMA setup", ["kbli"]) == "legal"
    assert service.select_next_collection("PMA setup", ["kbli", "legal", "tax"]) is None
    assert router.calls[0] == {"query": "PMA setup", "return_fallbacks": True}


@pytest.mark.asyncio
async def test_expand_query_keeps_original_and_focuses_on_detected_terms() -> None:
    service, _, _, _ = _service()

    expansions = await service.expand_query(
        "open fintech company",
        ["PT PMA needs NIB before KITAS sponsorship"],
    )

    assert expansions == [
        "open fintech company",
        "PT for open fintech company",
        "PMA for open fintech company",
    ]


@pytest.mark.asyncio
async def test_research_iteration_searches_selected_collection_and_truncates_findings() -> None:
    long_text = "A" * 220
    service, search, _, _ = _service(
        results=[
            {"text": long_text, "score": 0.8},
            {"text": "short finding", "score": 0.6},
        ],
    )
    searched: list[str] = []

    step = await service.research_iteration(
        query="PT PMA crypto",
        step_number=1,
        collections_searched=searched,
        user_level=4,
    )

    assert step.collection == "legal_updates"
    assert searched == ["legal_updates"]
    assert step.results_found == 2
    assert step.confidence == pytest.approx(0.7)
    assert step.key_findings == [f"{'A' * 200}...", "short finding"]
    assert search.calls == [
        {
            "query": "PT PMA crypto",
            "user_level": 4,
            "limit": 5,
            "collection_override": "legal_updates",
        },
    ]


@pytest.mark.asyncio
async def test_synthesize_research_uses_zantara_and_combines_confidence_with_coverage() -> None:
    service, _, _, zantara = _service(synthesis="Final research answer")
    steps = [
        ResearchStep(1, "legal", "query", "why", 2, 0.6, ["legal finding"]),
        ResearchStep(2, "tax", "query", "why", 3, 0.8, ["tax finding"]),
    ]

    answer, confidence = await service.synthesize_research("query", steps)

    assert answer == "Final research answer"
    assert confidence == pytest.approx(0.9)
    assert "LEGAL" in zantara.calls[0]["message"]
    assert zantara.calls[0]["user_id"] == "autonomous_research"


@pytest.mark.asyncio
async def test_research_stops_after_high_confidence_step_and_updates_stats() -> None:
    service, _, _, _ = _service(
        results=[
            {"text": "OJK crypto regulation", "score": 0.82},
            {"text": "PMA licensing path", "score": 0.78},
            {"text": "tax treatment", "score": 0.8},
        ],
        synthesis="High confidence answer",
    )

    result = await service.research("crypto company setup", user_level=5)
    stats = service.get_research_stats()

    assert result.original_query == "crypto company setup"
    assert result.total_steps == 1
    assert result.collections_explored == ["legal_updates"]
    assert result.final_answer == "High confidence answer"
    assert result.confidence == pytest.approx(1.0)
    assert result.sources_consulted == 3
    assert "High confidence achieved" in result.reasoning_chain[-1]
    assert stats["total_researches"] == 1
    assert stats["avg_iterations"] == 1.0
    assert stats["avg_confidence"] == pytest.approx(1.0)
    assert stats["max_iterations_rate"] == "0.0%"


@pytest.mark.asyncio
async def test_synthesize_research_returns_low_confidence_when_no_findings_exist() -> None:
    service, _, _, zantara = _service()

    answer, confidence = await service.synthesize_research(
        "unknown topic",
        [ResearchStep(1, "legal", "unknown topic", "why", 0, 0.0, [])],
    )

    assert "couldn't find sufficient information" in answer
    assert confidence == 0.1
    assert zantara.calls == []
