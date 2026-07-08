from __future__ import annotations

from backend.services.routing.query_router_integration import QueryRouterIntegration


class FakeKeywordMatcher:
    def __init__(self, domains: list[str] | None = None) -> None:
        self.domains = domains or []

    def detect_multi_domain(self, query: str) -> list[str]:
        return self.domains


class FakeRouter:
    def __init__(self, domains: list[str] | None = None) -> None:
        self.keyword_matcher = FakeKeywordMatcher(domains)
        self.route_calls: list[str] = []
        self.confidence_calls: list[tuple[str, bool]] = []

    def route(self, query: str) -> str:
        self.route_calls.append(query)
        return "visa_oracle"

    def route_with_confidence(
        self,
        query: str,
        *,
        return_fallbacks: bool,
    ) -> tuple[str, float, list[str]]:
        self.confidence_calls.append((query, return_fallbacks))
        return "visa_oracle", 0.64, ["visa_oracle"]


def test_is_pricing_query_matches_supported_languages() -> None:
    integration = QueryRouterIntegration(query_router=FakeRouter())

    assert integration.is_pricing_query("How much does KITAS cost?") is True
    assert integration.is_pricing_query("Quanto costa il visto?") is True
    assert integration.is_pricing_query("Berapa biaya KITAS?") is True
    assert integration.is_pricing_query("Explain KITAS documents") is False


def test_route_query_honors_collection_override() -> None:
    router = FakeRouter()
    integration = QueryRouterIntegration(query_router=router)

    result = integration.route_query("anything", collection_override="legal_unified")

    assert result == {
        "collection_name": "legal_unified",
        "collections": ["legal_unified"],
        "confidence": 1.0,
        "is_pricing": False,
    }
    assert router.route_calls == []


def test_route_query_sends_pricing_to_pricing_collection() -> None:
    integration = QueryRouterIntegration(query_router=FakeRouter())

    result = integration.route_query("How much does company setup cost?")

    assert result == {
        "collection_name": "bali_zero_pricing_hybrid",
        "collections": ["bali_zero_pricing_hybrid", "legal_unified"],
        "confidence": 0.95,
        "is_pricing": True,
    }


def test_route_query_auto_enables_fallbacks_for_multi_domain_query() -> None:
    router = FakeRouter(domains=["visa", "tax"])
    integration = QueryRouterIntegration(query_router=router)

    result = integration.route_query("KITAS tax obligations")

    assert result["collection_name"] == "visa_oracle"
    assert result["confidence"] == 0.64
    assert result["is_multi_domain"] is True
    assert result["active_domains"] == ["visa", "tax"]
    assert result["collections"] == ["visa_oracle", "tax_genius"]
    assert router.confidence_calls == [("KITAS tax obligations", True)]


def test_route_query_uses_simple_router_when_fallbacks_are_disabled() -> None:
    router = FakeRouter()
    integration = QueryRouterIntegration(query_router=router)

    result = integration.route_query("KITAS documents")

    assert result == {
        "collection_name": "visa_oracle",
        "collections": ["visa_oracle"],
        "confidence": 1.0,
        "is_pricing": False,
    }
    assert router.route_calls == ["KITAS documents"]
