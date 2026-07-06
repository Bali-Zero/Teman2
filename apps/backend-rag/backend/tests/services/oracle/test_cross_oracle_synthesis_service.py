from __future__ import annotations

from typing import Any

import pytest

from backend.services.oracle.cross_oracle_synthesis_service import (
    CrossOracleSynthesisService,
    OracleQuery,
)


class FakeSearchService:
    def __init__(self, *, fail_collection: str | None = None) -> None:
        self.fail_collection = fail_collection
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "query": query,
                "user_level": user_level,
                "limit": limit,
                "collection_override": collection_override,
            },
        )
        if collection_override == self.fail_collection:
            raise RuntimeError("search unavailable")
        return {
            "results": [
                {
                    "text": f"{collection_override} guidance for {query}",
                    "score": 0.91,
                },
            ],
        }


class FakeZantaraClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, Any]] = []

    async def generate_text(
        self,
        *,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, str]:
        self.calls.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        return {"text": self.text}


SYNTHESIS_TEXT = """## Integrated Recommendation
Open the restaurant through a compliant company setup.

## Timeline
6 to 8 weeks.

## Investment Required
IDR 120 million minimum operating setup.

## Key Requirements
- Confirm KBLI classification
- Prepare company deeds

## Potential Risks
- Wrong license scope
- Underestimated tax obligations
"""


def make_service(
    *,
    search: FakeSearchService | None = None,
    zantara: FakeZantaraClient | None = None,
) -> CrossOracleSynthesisService:
    return CrossOracleSynthesisService(
        search_service=search or FakeSearchService(),
        zantara_ai_client=zantara or FakeZantaraClient(SYNTHESIS_TEXT),
    )


def test_classify_scenario_scores_business_setup_query() -> None:
    service = make_service()

    scenario, confidence = service.classify_scenario(
        "I want to open a restaurant company in Canggu",
    )

    assert scenario == "business_setup"
    assert confidence == pytest.approx(0.6)


def test_determine_oracles_includes_required_and_optional_sources() -> None:
    service = make_service()

    oracle_queries = service.determine_oracles("open a cafe", "business_setup")

    collections = [query.collection for query in oracle_queries]
    assert collections[:3] == ["kbli_2025_final", "legal_architect", "tax_genius"]
    assert "visa_oracle" in collections
    assert "property_knowledge" in collections
    assert all(query.priority == 1 for query in oracle_queries[:3])
    assert all(query.priority == 2 for query in oracle_queries[3:])


def test_determine_oracles_uses_default_for_unknown_scenario() -> None:
    service = make_service()

    oracle_queries = service.determine_oracles("tell me something", "general")

    assert oracle_queries == [
        OracleQuery(
            collection="visa_oracle",
            query="tell me something",
            priority=1,
            rationale="Default Oracle",
        ),
    ]


@pytest.mark.asyncio
async def test_query_oracle_passes_access_level_and_collection() -> None:
    search = FakeSearchService()
    service = make_service(search=search)

    result = await service.query_oracle(
        OracleQuery(collection="tax_genius", query="tax for PMA", rationale="needed"),
        user_level=7,
    )

    assert result["success"] is True
    assert result["collection"] == "tax_genius"
    assert result["result_count"] == 1
    assert search.calls == [
        {
            "query": "tax for PMA",
            "user_level": 7,
            "limit": 3,
            "collection_override": "tax_genius",
        },
    ]


@pytest.mark.asyncio
async def test_query_oracle_returns_error_payload_on_search_failure() -> None:
    service = make_service(search=FakeSearchService(fail_collection="tax_genius"))

    result = await service.query_oracle(
        OracleQuery(collection="tax_genius", query="tax for PMA"),
    )

    assert result["success"] is False
    assert result["result_count"] == 0
    assert result["results"] == []
    assert result["error"] == "search unavailable"


@pytest.mark.asyncio
async def test_query_all_oracles_returns_results_keyed_by_collection() -> None:
    service = make_service()

    results = await service.query_all_oracles(
        [
            OracleQuery(collection="kbli_2025_final", query="restaurant"),
            OracleQuery(collection="legal_architect", query="restaurant"),
        ],
        user_level=4,
    )

    assert set(results) == {"kbli_2025_final", "legal_architect"}
    assert results["kbli_2025_final"]["success"] is True
    assert results["legal_architect"]["result_count"] == 1


@pytest.mark.asyncio
async def test_synthesize_with_zantara_includes_successful_oracle_context() -> None:
    zantara = FakeZantaraClient(SYNTHESIS_TEXT)
    service = make_service(zantara=zantara)

    result = await service.synthesize_with_zantara(
        query="open a restaurant",
        scenario_type="business_setup",
        oracle_results={
            "kbli_2025_final": {
                "success": True,
                "results": [{"text": "KBLI 56101 restaurant classification"}],
            },
            "tax_genius": {"success": False, "results": []},
        },
    )

    assert result == SYNTHESIS_TEXT
    assert "KBLI 56101 restaurant classification" in zantara.calls[0]["prompt"]
    assert "TAX GENIUS" not in zantara.calls[0]["prompt"]
    assert zantara.calls[0]["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_synthesize_returns_structured_result_and_updates_stats() -> None:
    service = make_service()

    result = await service.synthesize(
        "I want to open a restaurant company in Canggu",
        user_level=5,
        use_cache=False,
    )

    assert result.scenario_type == "business_setup"
    assert result.confidence == pytest.approx(0.6)
    assert result.timeline == "6 to 8 weeks."
    assert result.investment == "IDR 120 million minimum operating setup."
    assert result.key_requirements == [
        "Confirm KBLI classification",
        "Prepare company deeds",
    ]
    assert result.risks == ["Wrong license scope", "Underestimated tax obligations"]
    assert set(result.oracles_consulted) == {
        "kbli_2025_final",
        "legal_architect",
        "tax_genius",
        "visa_oracle",
        "property_knowledge",
        "bali_zero_pricing_hybrid",
    }

    stats = service.get_synthesis_stats()
    assert stats["total_syntheses"] == 1
    assert stats["avg_oracles_consulted"] == 6
    assert stats["scenario_distribution"] == {"business_setup": 1}
