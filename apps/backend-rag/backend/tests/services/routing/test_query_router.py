from __future__ import annotations

from typing import Any

import pytest

from backend.services.routing.query_router import QueryRouter


def complete_scores(**overrides: int) -> dict[str, int]:
    scores = {
        "visa": 0,
        "kbli": 0,
        "tax": 0,
        "legal": 0,
        "property": 0,
        "team": 0,
        "books": 0,
        "circular": 0,
        "business": 0,
        "news": 0,
    }
    scores.update(overrides)
    return scores


def test_route_selects_expected_core_collections() -> None:
    router = QueryRouter()

    assert router.route("Investor KITAS visa requirements") == "visa_oracle"
    assert router.route("KBLI business classification for a cafe") == "kbli_2025_final"
    assert router.route("How to calculate pajak and PPN") == "tax_genius"
    assert router.route("No obvious domain keywords here") == "legal_unified"


@pytest.mark.asyncio
async def test_route_query_returns_collection_confidence_and_fallbacks() -> None:
    router = QueryRouter()

    result = await router.route_query("Investor KITAS visa requirements", user_id="user-1")

    assert result["collection_name"] == "visa_oracle"
    assert 0 <= result["confidence"] <= 1
    assert result["fallbacks"][0] == "visa_oracle"


def test_calculate_confidence_delegates_to_confidence_service() -> None:
    router = QueryRouter()

    class FakeConfidenceCalculator:
        def calculate_confidence(self, query: str, domain_scores: dict[str, int]) -> float:
            assert query == "visa query"
            assert domain_scores == {"visa": 2}
            return 0.73

    router.confidence_calculator = FakeConfidenceCalculator()

    assert router.calculate_confidence("visa query", {"visa": 2}) == 0.73


def test_get_fallback_collections_delegates_to_fallback_manager() -> None:
    router = QueryRouter()

    class FakeFallbackManager:
        def get_fallback_collections(
            self,
            primary_collection: str,
            confidence: float,
            max_fallbacks: int,
        ) -> list[str]:
            assert primary_collection == "visa_oracle"
            assert confidence == 0.42
            assert max_fallbacks == 2
            return ["visa_oracle", "legal_architect"]

    router.fallback_manager = FakeFallbackManager()

    assert router.get_fallback_collections("visa_oracle", 0.42, max_fallbacks=2) == [
        "visa_oracle",
        "legal_architect",
    ]


def test_route_with_confidence_records_fallback_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    router = QueryRouter()
    recorded: list[dict[str, Any]] = []

    monkeypatch.setattr(router, "_check_priority_overrides", lambda query: None)
    monkeypatch.setattr(
        router,
        "_calculate_domain_scores",
        lambda query: complete_scores(visa=2),
    )
    monkeypatch.setattr(
        router,
        "get_fallback_collections",
        lambda collection, confidence: [collection, "legal_architect"],
    )

    class FakeRoutingStats:
        fallback_stats: dict[str, int] = {}

        def record_route(self, **kwargs: Any) -> None:
            recorded.append(kwargs)

    router.routing_stats = FakeRoutingStats()

    collection, confidence, collections = router.route_with_confidence("visa question")

    assert collection == "visa_oracle"
    assert 0 <= confidence <= 1
    assert collections == ["visa_oracle", "legal_architect"]
    assert recorded == [
        {
            "confidence": confidence,
            "fallbacks_used": True,
            "confidence_threshold_high": router.CONFIDENCE_THRESHOLD_HIGH,
            "confidence_threshold_low": router.CONFIDENCE_THRESHOLD_LOW,
        },
    ]


def test_route_with_confidence_returns_override_without_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    router = QueryRouter()

    monkeypatch.setattr(router, "_check_priority_overrides", lambda query: "bali_zero_pricing_hybrid")

    assert router.route_with_confidence("who is the team") == (
        "bali_zero_pricing_hybrid",
        1.0,
        ["bali_zero_pricing_hybrid"],
    )


def test_get_routing_stats_exposes_scores_matches_and_collection() -> None:
    router = QueryRouter()

    stats = router.get_routing_stats("KITAS visa requirement")

    assert stats["query"] == "KITAS visa requirement"
    assert stats["selected_collection"] in {"visa_oracle", "immigration_circulars"}
    assert stats["domain_scores"]["visa"] > 0
    assert "visa" in stats["matched_keywords"]
    assert stats["total_matches"] == sum(stats["domain_scores"].values())


def test_get_fallback_stats_delegates_to_routing_stats() -> None:
    router = QueryRouter()

    class FakeRoutingStats:
        fallback_stats: dict[str, int] = {"fallbacks_used": 3}

        def get_fallback_stats(self) -> dict[str, int]:
            return self.fallback_stats

    router.routing_stats = FakeRoutingStats()

    assert router.get_fallback_stats() == {"fallbacks_used": 3}
