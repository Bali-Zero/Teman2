"""TDD test suite for SurfaceRouter — R5 Phase 3.

50 canonical queries covering all 7 surfaces + edge cases.
Haiku LLM path is mocked (unit tests only); keyword path is exercised live.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.routing.surface_router import (
    Surface,
    SurfaceDecision,
    SurfaceRouter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def router() -> SurfaceRouter:
    return SurfaceRouter()


@pytest.fixture()
def router_enabled() -> SurfaceRouter:
    return SurfaceRouter(enabled=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _route(router: SurfaceRouter, query: str) -> SurfaceDecision:
    """Sync wrapper — SurfaceRouter.decide() is sync (no I/O on keyword path)."""
    return router.decide(query)


# ---------------------------------------------------------------------------
# 1. Visa surface (10 queries)
# ---------------------------------------------------------------------------

class TestVisaSurface:
    QUERIES_STRICT = [
        "Come faccio a rinnovare il mio KITAS?",
        "What documents do I need for a social visa extension?",
        "sponsor letter requirements for C1 visa",
        "imigrasi bali office hours and address",
        "tourist visa overstay penalty Indonesia",
        "multiple entry visa requirements for EU citizens",
        "KITAP application process step by step",
        "immigration circular SE/2024 about TKA",
        "dirjen imigrasi regulation on work permit sponsor",
    ]
    # "Berapa biaya" = pricing signal — ambiguous between visa info and pricing
    QUERIES_AMBIGUOUS = [
        "Berapa biaya perpanjangan B211A?",
    ]

    def test_all_visa_queries_route_to_visa_surface(self, router):
        for q in self.QUERIES_STRICT:
            decision = _route(router, q)
            assert decision.surface in (Surface.QDRANT_VISA,), (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_visa"
            )

    def test_ambiguous_visa_pricing_accepted(self, router):
        """'Berapa biaya' = pricing signal; visa price query may go to pricing surface."""
        for q in self.QUERIES_AMBIGUOUS:
            decision = _route(router, q)
            assert decision.surface in (Surface.QDRANT_VISA, Surface.QDRANT_PRICING), (
                f"Query '{q[:50]}' routed to {decision.surface}, expected visa or pricing"
            )

    def test_visa_primary_collection(self, router):
        d = _route(router, "KITAS renewal documents needed")
        assert d.primary_collection in ("visa_oracle", "immigration_circulars")

    def test_visa_latency_keyword_path(self, router):
        start = time.perf_counter()
        _route(router, "How to apply for KITAS in Bali?")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 200, f"Keyword path too slow: {elapsed_ms:.1f}ms"

    def test_visa_layer_is_keyword(self, router):
        d = _route(router, "visa extension Indonesia requirements")
        assert d.layer_used == 1


# ---------------------------------------------------------------------------
# 2. Tax surface (8 queries)
# ---------------------------------------------------------------------------

class TestTaxSurface:
    # "Quanto costa" has pricing signal — accepted ambiguity; excluded from strict test
    QUERIES_STRICT = [
        "How to calculate PPh 21 for foreign worker?",
        "pajak penghasilan badan PT PMA Indonesia",
        "VAT registration requirements for new company",
        "tax filing deadline Indonesia 2026",
        "withholding tax on rental income Bali",
        "NPWP registration for expat foreigner",
        "corporate income tax rate for PMA company",
    ]
    QUERIES_AMBIGUOUS = [
        # "costa" = pricing signal; tax service query is legitimately ambiguous
        "Quanto costa il servizio di dichiarazione fiscale?",
    ]

    def test_all_tax_queries_route_to_tax_surface(self, router):
        for q in self.QUERIES_STRICT:
            decision = _route(router, q)
            assert decision.surface == Surface.QDRANT_TAX, (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_tax"
            )

    def test_ambiguous_tax_pricing_accepted(self, router):
        """Tax+pricing queries may route to either surface — both are valid."""
        for q in self.QUERIES_AMBIGUOUS:
            decision = _route(router, q)
            assert decision.surface in (Surface.QDRANT_TAX, Surface.QDRANT_PRICING), (
                f"Query '{q[:50]}' routed to {decision.surface}, expected tax or pricing"
            )

    def test_tax_primary_collection(self, router):
        d = _route(router, "PPh 21 calculation for expat")
        assert "tax" in d.primary_collection or d.primary_collection == "tax_genius_hybrid"

    def test_tax_domain(self, router):
        d = _route(router, "pajak badan annual report")
        assert d.domain == "tax"

    @pytest.mark.asyncio
    async def test_async_tax_rate_query_matches_sync_routing(self, router):
        """Tax rate queries must not drift to pricing on the async path."""
        query = "corporate income tax rate for PMA company"

        sync_decision = router.decide(query)
        async_decision = await router.adecide(query)

        assert sync_decision.surface == Surface.QDRANT_TAX
        assert async_decision.surface == Surface.QDRANT_TAX


# ---------------------------------------------------------------------------
# 3. Company / KBLI surface (8 queries)
# ---------------------------------------------------------------------------

class TestCompanySurface:
    QUERIES = [
        "KBLI code for restaurant business in Bali",
        "How to set up a PT PMA in Indonesia?",
        "foreign investment restrictions DNPI negative list",
        "OSS NIB registration process for new company",
        "kode usaha untuk villa rental PMA",
        "minimum capital requirement for foreign company",
        "deed of establishment notaris akta pendirian",
        "business license izin usaha KBLI 56303",
    ]

    def test_all_company_queries_route_to_company_surface(self, router):
        for q in self.QUERIES:
            decision = _route(router, q)
            assert decision.surface == Surface.QDRANT_COMPANY, (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_company"
            )

    def test_kbli_in_company_collections(self, router):
        d = _route(router, "KBLI code for IT consulting services")
        assert any("kbli" in c for c in d.collections)


# ---------------------------------------------------------------------------
# 4. Property surface (6 queries)
# ---------------------------------------------------------------------------

class TestPropertySurface:
    QUERIES = [
        "Can a foreigner own freehold land in Bali?",
        "villa leasehold agreement requirements",
        "due diligence checklist for property purchase Indonesia",
        "sertipikat hak milik vs hak pakai difference",
        "real estate investment structure for WNA",
        "tanah kavling zoning regulation Bali",
    ]

    def test_all_property_queries_route_to_property_surface(self, router):
        for q in self.QUERIES:
            decision = _route(router, q)
            assert decision.surface == Surface.QDRANT_PROPERTY, (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_property"
            )


# ---------------------------------------------------------------------------
# 5. Pricing surface (5 queries)
# ---------------------------------------------------------------------------

class TestPricingSurface:
    QUERIES = [
        "How much does KITAS renewal cost at Bali Zero?",
        "quanto costa aprire una PT PMA?",
        "price list for company setup services",
        "berapa biaya jasa konsultan pajak Bali Zero?",
        "what is the fee for visa extension service?",
    ]

    def test_all_pricing_queries_route_to_pricing_surface(self, router):
        for q in self.QUERIES:
            decision = _route(router, q)
            assert decision.surface == Surface.QDRANT_PRICING, (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_pricing"
            )

    def test_pricing_collection(self, router):
        d = _route(router, "cost of PT PMA establishment Bali Zero")
        assert d.primary_collection == "bali_zero_pricing_hybrid"


# ---------------------------------------------------------------------------
# 6. News / Intel surface (5 queries)
# ---------------------------------------------------------------------------

class TestNewsSurface:
    QUERIES = [
        "latest immigration news Indonesia 2026",
        "berita terbaru perubahan regulasi visa Bali",
        "recent changes to tax regulation Indonesia",
        "new government announcement on foreign investment",
        "bali zero news regulatory update Q1 2026",
    ]

    def test_all_news_queries_route_to_news_surface(self, router):
        for q in self.QUERIES:
            decision = _route(router, q)
            assert decision.surface == Surface.QDRANT_NEWS, (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_news"
            )


# ---------------------------------------------------------------------------
# 7. Skills / Ops surface (4 queries)
# ---------------------------------------------------------------------------

class TestSkillsSurface:
    QUERIES = [
        "how to handle client KITAS renewal internal workflow",
        "ops procedure for new client onboarding checklist",
        "internal skill for drafting visa sponsorship letter",
        "team workflow for processing tax filing practice",
    ]

    def test_all_skills_queries_route_to_skills_surface(self, router):
        for q in self.QUERIES:
            decision = _route(router, q)
            assert decision.surface == Surface.QDRANT_SKILLS, (
                f"Query '{q[:50]}' routed to {decision.surface}, expected qdrant_skills"
            )

    def test_skills_surface_is_not_local_only(self, router):
        # R5 AIL #1: skills migrated to Qdrant Cloud (bali_zero_skills_hybrid)
        d = _route(router, "internal ops workflow checklist")
        assert d.is_local_only is False

    def test_skills_collection_name(self, router):
        d = _route(router, "skill for handling visa client onboarding")
        assert d.primary_collection == "bali_zero_skills_hybrid"


# ---------------------------------------------------------------------------
# 8. Ambiguous / multi-domain queries (4 queries — Haiku path mocked)
# ---------------------------------------------------------------------------

class TestAmbiguousQueries:
    """For ambiguous queries (confidence < 0.60), Haiku is called.
    Tests mock the Haiku call to keep unit tests fast.
    """

    @patch(
        "backend.services.routing.surface_router.SurfaceRouter._classify_with_haiku",
        new_callable=AsyncMock,
    )
    def test_ambiguous_tax_property(self, mock_haiku, router_enabled):
        mock_haiku.return_value = SurfaceDecision(
            surface=Surface.QDRANT_TAX,
            primary_collection="tax_genius_hybrid",
            collections=["tax_genius_hybrid", "legal_unified_hybrid_hybrid"],
            domain="tax",
            confidence=0.71,
            layer_used=2,
            is_local_only=False,
            latency_ms=1200.0,
        )
        # "how much" = pricing signal + "property tax" = genuinely multi-domain
        # Any of tax, property, or pricing is a valid surface
        d = router_enabled.decide("how much property tax do I pay on villa rental income?")
        assert d.surface in (Surface.QDRANT_TAX, Surface.QDRANT_PROPERTY, Surface.QDRANT_PRICING)

    @patch(
        "backend.services.routing.surface_router.SurfaceRouter._classify_with_haiku",
        new_callable=AsyncMock,
    )
    def test_ambiguous_company_visa(self, mock_haiku, router_enabled):
        mock_haiku.return_value = SurfaceDecision(
            surface=Surface.QDRANT_COMPANY,
            primary_collection="kbli_2025_final_hybrid",
            collections=["kbli_2025_final_hybrid", "visa_oracle"],
            domain="company",
            confidence=0.65,
            layer_used=2,
            is_local_only=False,
            latency_ms=950.0,
        )
        d = router_enabled.decide("work permit requirements for company director")
        assert d.surface in (Surface.QDRANT_COMPANY, Surface.QDRANT_VISA)

    def test_haiku_not_called_on_high_confidence(self, router_enabled):
        """High-confidence queries (visa) must not call Haiku."""
        with patch(
            "backend.services.routing.surface_router.SurfaceRouter._classify_with_haiku"
        ) as mock_haiku:
            mock_haiku.return_value = None
            d = router_enabled.decide("KITAS visa extension requirements Indonesia")
            mock_haiku.assert_not_called()
            assert d.layer_used == 1

    def test_haiku_timeout_fallback(self, router_enabled):
        """On Haiku timeout, router falls back to keyword result."""
        with patch(
            "backend.services.routing.surface_router.SurfaceRouter._classify_with_haiku",
            side_effect=TimeoutError("Haiku timeout"),
        ):
            # Should not raise, should return keyword-level result
            d = router_enabled.decide("some ambiguous multi-domain query about taxes and visas")
            assert isinstance(d, SurfaceDecision)
            assert d.layer_used == 1  # fallback to keyword


# ---------------------------------------------------------------------------
# 9. SurfaceDecision dataclass
# ---------------------------------------------------------------------------

class TestSurfaceDecision:
    def test_dataclass_fields(self, router):
        d = _route(router, "KITAS visa renewal")
        assert hasattr(d, "surface")
        assert hasattr(d, "primary_collection")
        assert hasattr(d, "collections")
        assert hasattr(d, "domain")
        assert hasattr(d, "confidence")
        assert hasattr(d, "layer_used")
        assert hasattr(d, "is_local_only")
        assert hasattr(d, "latency_ms")

    def test_confidence_range(self, router):
        d = _route(router, "Indonesian tax filing annual report")
        assert 0.0 <= d.confidence <= 1.0

    def test_collections_nonempty(self, router):
        d = _route(router, "visa extension bali")
        assert len(d.collections) >= 1

    def test_primary_in_collections(self, router):
        d = _route(router, "KBLI code for coffee shop")
        assert d.primary_collection in d.collections


# ---------------------------------------------------------------------------
# 10. Disabled mode (shadow / default)
# ---------------------------------------------------------------------------

class TestDisabledMode:
    def test_disabled_mode_still_returns_decision(self, router):
        """In shadow mode (enabled=False), decide() still returns SurfaceDecision."""
        d = router.decide("visa extension")
        assert isinstance(d, SurfaceDecision)

    def test_disabled_mode_flag(self):
        r = SurfaceRouter(enabled=False)
        assert r.enabled is False

    def test_enabled_mode_flag(self):
        r = SurfaceRouter(enabled=True)
        assert r.enabled is True


# ---------------------------------------------------------------------------
# 11. KG surface (R5 Phase 4 — Neo4j Knowledge Graph as 8th surface)
# ---------------------------------------------------------------------------

class TestKGSurface:
    """KG surface routes entity/relationship queries to KGOrchestrator (Neo4j).

    KG surface is flagged is_kg_surface=True so callers skip Qdrant collections.
    No primary_collection is required (primary_collection = "" sentinel).
    """

    QUERIES = [
        # Entity resolution
        "chi è il direttore di PT XYZ Bali?",
        "who is the owner of this company in Indonesia?",
        "siapa direktur utama perusahaan ini?",
        # Relationship traversal
        "qual è la relazione tra permesso di lavoro e KITAS?",
        "what is the relationship between KBLI and business license?",
        "hubungan antara NIB dan SIUP di Indonesia",
        # Structure / hierarchy
        "struttura societaria PT PMA Bali",
        "organigramma aziendale per PMA",
        "company ownership structure Indonesia",
        # Graph-specific patterns
        "chi conosce questo cliente?",
        "collegato a quale pratica?",
        "linked to which visa application?",
        "graph traversal company directors",
        "entity relationship company founder",
    ]

    def test_all_kg_queries_route_to_kg_surface(self, router):
        for q in self.QUERIES:
            decision = _route(router, q)
            assert decision.surface == Surface.KG, (
                f"Query '{q[:60]}' routed to {decision.surface}, expected kg"
            )

    def test_kg_is_kg_surface_flag(self, router):
        d = _route(router, "chi è il direttore di questa azienda?")
        assert d.is_kg_surface is True

    def test_kg_not_local_only(self, router):
        d = _route(router, "struttura societaria PT PMA")
        assert d.is_local_only is False

    def test_kg_primary_collection_empty(self, router):
        d = _route(router, "entity relationship company founder")
        assert d.primary_collection == ""

    def test_kg_collections_empty(self, router):
        d = _route(router, "organigramma aziendale")
        assert d.collections == []

    def test_kg_layer_is_keyword(self, router):
        d = _route(router, "chi conosce questo cliente?")
        assert d.layer_used == 1

    def test_kg_confidence_above_threshold(self, router):
        d = _route(router, "struttura societaria azienda Indonesia")
        assert d.confidence >= 0.80

    def test_kg_surface_constant_exists(self):
        assert hasattr(Surface, "KG")
        assert Surface.KG == "kg"

    def test_kg_decision_has_domain(self, router):
        d = _route(router, "relationship between KBLI and business permit")
        assert d.domain == "kg"

    def test_kg_latency_keyword_path(self, router):
        start = time.perf_counter()
        _route(router, "entity relationship company directors Indonesia")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 200, f"KG keyword path too slow: {elapsed_ms:.1f}ms"
