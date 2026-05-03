"""
Test Multi-Domain Routing - Task 3 Debug

Tests the 3 problematic queries that were failing:
1. "Qual è il codice KBLI per ristorante?" → should hit kbli_2025_final
2. "Cosa serve per licenza SLHS a Bali?" → should hit training_conversations_hybrid
3. "Aprire ristorante come straniero: visto + PT PMA + KBLI + licenze?" → multi-domain

Run: python -m pytest tests/test_multi_domain_routing.py -v
"""

import logging
import sys

import pytest

# Configure logging to see debug output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from backend.services.routing.keyword_matcher import KeywordMatcherService
from backend.services.routing.query_router import QueryRouter
from backend.services.routing.query_router_integration import QueryRouterIntegration


class TestMultiDomainRouting:
    """Test suite for multi-domain routing fixes."""

    def setup_method(self):
        self.router = QueryRouter()
        self.integration = QueryRouterIntegration(query_router=self.router)
        self.keyword_matcher = KeywordMatcherService()

    # ── Query 1: KBLI per ristorante ──────────────────────────────────

    def test_kbli_restaurant_keywords(self):
        """KBLI query should detect kbli + restaurant keywords."""
        query = "Qual è il codice KBLI per ristorante?"
        scores = self.keyword_matcher.calculate_domain_scores(query)
        matched = self.keyword_matcher.get_matched_keywords(query, "kbli")

        assert scores["kbli"] >= 2, f"KBLI score too low: {scores['kbli']}, matched: {matched}"
        assert "kbli" in matched
        assert "ristorante" in matched or "codice kbli" in matched

    def test_kbli_restaurant_routes_correctly(self):
        """KBLI restaurant query should route to kbli_2025_final."""
        query = "Qual è il codice KBLI per ristorante?"
        collection = self.router.route(query)
        assert collection == "kbli_2025_final", f"Expected kbli_2025_final, got {collection}"

    # ── Query 2: Licenza SLHS ─────────────────────────────────────────

    def test_slhs_keywords(self):
        """SLHS query should detect business domain keywords."""
        query = "Cosa serve per licenza SLHS a Bali?"
        scores = self.keyword_matcher.calculate_domain_scores(query)
        matched_business = self.keyword_matcher.get_matched_keywords(query, "business")

        assert scores["business"] >= 2, (
            f"Business score too low: {scores['business']}, matched: {matched_business}"
        )
        assert "slhs" in matched_business
        assert "licenza" in matched_business

    def test_slhs_routes_to_business(self):
        """SLHS license query should route to training_conversations_hybrid."""
        query = "Cosa serve per licenza SLHS a Bali?"
        collection = self.router.route(query)
        assert collection == "training_conversations_hybrid", (
            f"Expected training_conversations_hybrid, got {collection}"
        )

    # ── Query 3: Multi-domain (visa + business + KBLI) ────────────────

    def test_multi_domain_detection(self):
        """Complex query should detect multiple active domains."""
        query = "Aprire ristorante come straniero: visto + PT PMA + KBLI + licenze?"
        active_domains = self.keyword_matcher.detect_multi_domain(query)

        assert len(active_domains) >= 3, (
            f"Expected >= 3 active domains, got {len(active_domains)}: {active_domains}"
        )
        # Should detect at least kbli, business, and visa
        assert "kbli" in active_domains, f"kbli not in {active_domains}"
        assert "business" in active_domains, f"business not in {active_domains}"
        assert "visa" in active_domains, f"visa not in {active_domains}"

    def test_multi_domain_fallbacks_enabled(self):
        """Multi-domain query should auto-enable fallbacks in integration."""
        query = "Aprire ristorante come straniero: visto + PT PMA + KBLI + licenze?"
        result = self.integration.route_query(query, enable_fallbacks=False)

        # Should have auto-enabled fallbacks
        assert result.get("is_multi_domain") is True, "Should detect multi-domain"
        assert len(result["collections"]) >= 3, (
            f"Expected >= 3 collections, got {len(result['collections'])}: {result['collections']}"
        )

        # Verify key collections are included
        collections = result["collections"]
        assert any("kbli" in c for c in collections), f"No KBLI collection in {collections}"
        assert any("training" in c or "business" in c for c in collections), (
            f"No business collection in {collections}"
        )
        assert any("visa" in c for c in collections), f"No visa collection in {collections}"

    # ── Keyword coverage tests ────────────────────────────────────────

    def test_italian_visa_keywords(self):
        """Italian visa keywords should be recognized."""
        query = "Ho bisogno di un visto per Bali"
        scores = self.keyword_matcher.calculate_domain_scores(query)
        assert scores["visa"] >= 1, f"Visa score too low for Italian query: {scores['visa']}"

    def test_italian_business_keywords(self):
        """Italian business keywords should be recognized."""
        query = "Come aprire una società a Bali?"
        scores = self.keyword_matcher.calculate_domain_scores(query)
        assert scores["business"] >= 1 or scores["legal"] >= 1, (
            f"No business/legal match for Italian query: business={scores['business']}, legal={scores['legal']}"
        )

    def test_license_acronyms(self):
        """Indonesian license acronyms should route to business domain."""
        acronyms = ["SLHS", "NPBBKC", "SIUP", "SIUJPT", "TDP", "BPOM", "PIRT"]
        for acronym in acronyms:
            query = f"What is {acronym}?"
            scores = self.keyword_matcher.calculate_domain_scores(query)
            assert scores["business"] >= 1, (
                f"Acronym '{acronym}' not detected in business domain: {scores}"
            )

    # ── Fallback chain tests ──────────────────────────────────────────

    def test_kbli_2025_final_has_fallback_chain(self):
        """kbli_2025_final should have a fallback chain defined."""
        from backend.services.routing.fallback_manager import FallbackManagerService

        fm = FallbackManagerService()
        assert "kbli_2025_final" in fm.FALLBACK_CHAINS, (
            "kbli_2025_final missing from FALLBACK_CHAINS"
        )
        chain = fm.FALLBACK_CHAINS["kbli_2025_final"]
        assert len(chain) >= 2, f"Fallback chain too short: {chain}"

    def test_legal_unified_hybrid_has_fallback_chain(self):
        """legal_unified_hybrid should have a fallback chain defined."""
        from backend.services.routing.fallback_manager import FallbackManagerService

        fm = FallbackManagerService()
        assert "legal_unified_hybrid" in fm.FALLBACK_CHAINS, (
            "legal_unified_hybrid missing from FALLBACK_CHAINS"
        )

    # ── Regression: single-domain queries still work ──────────────────

    def test_simple_visa_query(self):
        """Simple visa query should still route to visa_oracle."""
        query = "How to get a tourist visa for Bali?"
        collection = self.router.route(query)
        assert collection == "visa_oracle", f"Expected visa_oracle, got {collection}"

    def test_simple_tax_query(self):
        """Simple tax query should still route to tax_genius."""
        query = "What is the corporate tax rate in Indonesia?"
        collection = self.router.route(query)
        assert collection == "tax_genius", f"Expected tax_genius, got {collection}"

    def test_simple_kbli_query(self):
        """Simple KBLI query should route to kbli_2025_final."""
        query = "What is KBLI code for restaurant?"
        collection = self.router.route(query)
        assert collection == "kbli_2025_final", f"Expected kbli_2025_final, got {collection}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
