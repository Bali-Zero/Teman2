from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.routing.specialized_service_router import SpecializedServiceRouter


class FakeAutonomousResearchService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def research(self, *, query: str, user_level: int) -> SimpleNamespace:
        self.calls.append({"query": query, "user_level": user_level})
        if self.fail:
            raise RuntimeError("research failed")
        return SimpleNamespace(
            final_answer="Research answer",
            total_steps=3,
            collections_explored=["visa_oracle", "legal_unified"],
            confidence=0.82,
            sources_consulted=5,
            duration_ms=1234,
        )


class FakeCrossOracleService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def synthesize(
        self,
        *,
        query: str,
        user_level: int,
        use_cache: bool,
    ) -> SimpleNamespace:
        self.calls.append(
            {"query": query, "user_level": user_level, "use_cache": use_cache},
        )
        if self.fail:
            raise RuntimeError("synthesis failed")
        return SimpleNamespace(
            synthesis="Integrated plan",
            scenario_type="business_setup",
            oracles_consulted=["kbli_2025_final", "tax_genius"],
            confidence=0.76,
            timeline="6 weeks",
            investment="IDR 120 million",
            key_requirements=["KBLI"],
            risks=["Wrong license"],
        )


class FakeJourneyService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def create_journey(self, *, journey_type: str, client_id: str) -> SimpleNamespace:
        self.calls.append({"journey_type": journey_type, "client_id": client_id})
        return SimpleNamespace(
            title="PT PMA Setup",
            journey_id="journey-1",
            status=SimpleNamespace(value="active"),
            steps=[
                SimpleNamespace(
                    title="Collect documents",
                    description="Gather shareholder documents.",
                    required_documents=["passport", "address proof"],
                ),
            ],
        )


def test_detect_autonomous_research_requires_service_business_category_and_signal() -> None:
    assert (
        SpecializedServiceRouter().detect_autonomous_research(
            "how to handle crypto visa",
            "business_complex",
        )
        is False
    )

    router = SpecializedServiceRouter(autonomous_research_service=object())

    assert router.detect_autonomous_research("how to handle crypto visa", "casual") is False
    assert router.detect_autonomous_research("how to handle crypto visa", "business_complex") is True
    assert (
        router.detect_autonomous_research(
            "how to structure an uncommon business with multiple permits in Bali",
            "business_simple",
        )
        is True
    )


@pytest.mark.asyncio
async def test_route_autonomous_research_maps_result_and_handles_failures() -> None:
    service = FakeAutonomousResearchService()
    router = SpecializedServiceRouter(autonomous_research_service=service)

    result = await router.route_autonomous_research("research this", user_level=6)

    assert result is not None
    assert result["response"] == "Research answer"
    assert result["category"] == "autonomous_research"
    assert result["autonomous_research"] == {
        "total_steps": 3,
        "collections_explored": ["visa_oracle", "legal_unified"],
        "confidence": 0.82,
        "sources_consulted": 5,
        "duration_ms": 1234,
    }
    assert service.calls == [{"query": "research this", "user_level": 6}]

    failing_router = SpecializedServiceRouter(
        autonomous_research_service=FakeAutonomousResearchService(fail=True),
    )
    assert await failing_router.route_autonomous_research("research this") is None


def test_detect_cross_oracle_requires_business_setup_and_comprehensive_signal() -> None:
    router = SpecializedServiceRouter(cross_oracle_synthesis_service=object())

    assert router.detect_cross_oracle("open restaurant with full timeline", "business_complex")
    assert router.detect_cross_oracle("open restaurant", "business_complex") is False
    assert router.detect_cross_oracle("open restaurant with full timeline", "casual") is False
    assert SpecializedServiceRouter().detect_cross_oracle("open restaurant full", "business_complex") is False


@pytest.mark.asyncio
async def test_route_cross_oracle_maps_result_and_handles_failures() -> None:
    service = FakeCrossOracleService()
    router = SpecializedServiceRouter(cross_oracle_synthesis_service=service)

    result = await router.route_cross_oracle("open restaurant", user_level=4, use_cache=False)

    assert result is not None
    assert result["response"] == "Integrated plan"
    assert result["category"] == "cross_oracle_synthesis"
    assert result["cross_oracle_synthesis"] == {
        "scenario_type": "business_setup",
        "oracles_consulted": ["kbli_2025_final", "tax_genius"],
        "confidence": 0.76,
        "timeline": "6 weeks",
        "investment": "IDR 120 million",
        "key_requirements": ["KBLI"],
        "risks": ["Wrong license"],
    }
    assert service.calls == [
        {"query": "open restaurant", "user_level": 4, "use_cache": False},
    ]

    failing_router = SpecializedServiceRouter(
        cross_oracle_synthesis_service=FakeCrossOracleService(fail=True),
    )
    assert await failing_router.route_cross_oracle("open restaurant") is None


def test_detect_client_journey_requires_start_keyword_and_journey_type() -> None:
    router = SpecializedServiceRouter(client_journey_orchestrator=object())

    assert router.detect_client_journey("start process for PT PMA", "business_simple")
    assert router.detect_client_journey("start process", "business_simple") is False
    assert router.detect_client_journey("PT PMA setup info", "business_simple") is False
    assert SpecializedServiceRouter().detect_client_journey("start process for PT PMA", "business_simple") is False


@pytest.mark.asyncio
async def test_route_client_journey_creates_journey_for_detected_type() -> None:
    service = FakeJourneyService()
    router = SpecializedServiceRouter(client_journey_orchestrator=service)

    result = await router.route_client_journey("start process for PT PMA", user_id="client-1")

    assert result is not None
    assert "PT PMA Setup" in result["response"]
    assert result["category"] == "client_journey"
    assert result["used_rag"] is False
    assert result["client_journey"] == {
        "journey_id": "journey-1",
        "status": "active",
        "current_step": "Collect documents",
    }
    assert service.calls == [{"journey_type": "pt_pma_setup", "client_id": "client-1"}]


@pytest.mark.asyncio
async def test_route_client_journey_returns_none_without_known_journey_type() -> None:
    router = SpecializedServiceRouter(client_journey_orchestrator=FakeJourneyService())

    assert await router.route_client_journey("start a generic process", "client-1") is None
