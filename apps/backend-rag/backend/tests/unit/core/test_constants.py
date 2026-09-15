"""
Unit tests for constants modules
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.core.constants import (
    CRMConstants,
    DatabaseConstants,
    MemoryConstants,
    RoutingConstants,
    SearchConstants,
    TaxConsultantConstants,
)


class TestSearchConstants:
    """Tests for SearchConstants"""

    def test_constants_exist(self):
        """Test that all constants exist"""
        assert hasattr(SearchConstants, "PRICING_SCORE_BOOST")
        assert hasattr(SearchConstants, "CONFLICT_PENALTY_MULTIPLIER")
        assert hasattr(SearchConstants, "PRIMARY_COLLECTION_BOOST")
        assert hasattr(SearchConstants, "MAX_SCORE")

    def test_constant_values(self):
        """Test constant values"""
        assert SearchConstants.PRICING_SCORE_BOOST == 0.15
        assert SearchConstants.CONFLICT_PENALTY_MULTIPLIER == 0.7
        assert SearchConstants.PRIMARY_COLLECTION_BOOST == 1.1
        assert SearchConstants.MAX_SCORE == 1.0


class TestRoutingConstants:
    """Tests for RoutingConstants"""

    def test_constants_exist(self):
        """Test that all constants exist"""
        assert hasattr(RoutingConstants, "CONFIDENCE_THRESHOLD_HIGH")
        assert hasattr(RoutingConstants, "CONFIDENCE_THRESHOLD_LOW")
        assert hasattr(RoutingConstants, "MAX_FALLBACKS")

    def test_constant_values(self):
        """Test constant values"""
        assert RoutingConstants.CONFIDENCE_THRESHOLD_HIGH == 0.7
        assert RoutingConstants.CONFIDENCE_THRESHOLD_LOW == 0.3
        assert RoutingConstants.MAX_FALLBACKS == 3


class TestCRMConstants:
    """Tests for CRMConstants"""

    def test_constants_exist(self):
        """Test that all constants exist"""
        assert hasattr(CRMConstants, "CLIENT_CONFIDENCE_THRESHOLD_CREATE")
        assert hasattr(CRMConstants, "CLIENT_CONFIDENCE_THRESHOLD_UPDATE")
        assert hasattr(CRMConstants, "SUMMARY_MAX_LENGTH")
        assert hasattr(CRMConstants, "PRACTICES_LIMIT")

    def test_constant_values(self):
        """Test constant values"""
        assert CRMConstants.CLIENT_CONFIDENCE_THRESHOLD_CREATE == 0.5
        assert CRMConstants.CLIENT_CONFIDENCE_THRESHOLD_UPDATE == 0.6
        assert CRMConstants.SUMMARY_MAX_LENGTH == 500
        assert CRMConstants.PRACTICES_LIMIT == 10


class TestMemoryConstants:
    """Tests for MemoryConstants"""

    def test_constants_exist(self):
        """Test that all constants exist"""
        assert hasattr(MemoryConstants, "MAX_FACTS")
        assert hasattr(MemoryConstants, "MAX_SUMMARY_LENGTH")

    def test_constant_values(self):
        """Test constant values"""
        assert MemoryConstants.MAX_FACTS == 10
        assert MemoryConstants.MAX_SUMMARY_LENGTH == 500


class TestDatabaseConstants:
    """Tests for DatabaseConstants"""

    def test_constants_exist(self):
        """Test that all constants exist"""
        assert hasattr(DatabaseConstants, "POOL_MIN_SIZE")
        assert hasattr(DatabaseConstants, "POOL_MAX_SIZE")
        assert hasattr(DatabaseConstants, "COMMAND_TIMEOUT")

    def test_constant_values(self):
        """Test constant values"""
        assert DatabaseConstants.POOL_MIN_SIZE == 2
        assert DatabaseConstants.POOL_MAX_SIZE == 10
        assert DatabaseConstants.COMMAND_TIMEOUT == 60


class TestTaxConsultantConstants:
    """Tests for TaxConsultantConstants — the team_members-derived roster
    (migration 319 keeps the DB CHECK constraints in sync with this)."""

    def test_canonical_is_the_five_real_addresses(self):
        assert TaxConsultantConstants.CANONICAL == (
            "tax@balizero.com",
            "angel.tax@balizero.com",
            "kadek.tax@balizero.com",
            "dewaayu.tax@balizero.com",
            "faysha.tax@balizero.com",
        )
        assert len(TaxConsultantConstants.CANONICAL) == 5

    def test_lkpm_assignees_is_canonical_plus_krisna(self):
        assert TaxConsultantConstants.LKPM_ASSIGNEES == (
            *TaxConsultantConstants.CANONICAL,
            "krisna@balizero.com",
        )
        assert len(TaxConsultantConstants.LKPM_ASSIGNEES) == 6

    def test_manager_is_in_canonical(self):
        assert TaxConsultantConstants.MANAGER in TaxConsultantConstants.CANONICAL

    def test_non_manager_derived_by_filter_matches_canonical_minus_manager(self):
        """Mirrors how lkpm_deadline_notifier.py derives NON_MANAGER — by
        filtering out MANAGER, not by slicing CANONICAL[1:] — so the result
        holds regardless of MANAGER's position in the tuple."""
        non_manager = tuple(
            e for e in TaxConsultantConstants.CANONICAL if e != TaxConsultantConstants.MANAGER
        )
        reordered_canonical = tuple(reversed(TaxConsultantConstants.CANONICAL))
        non_manager_from_reordered = tuple(
            e for e in reordered_canonical if e != TaxConsultantConstants.MANAGER
        )
        assert set(non_manager) == set(TaxConsultantConstants.CANONICAL) - {
            TaxConsultantConstants.MANAGER
        }
        assert set(non_manager) == set(non_manager_from_reordered)

    def test_legacy_aliases_maps_both_ghosts_to_their_real_replacement(self):
        """Deliberately does not restate the two ghost strings as literals —
        `test_tax_consultant_ghost_address_guard.py` sweeps backend/ for
        them and only constants.py itself is on its exclusion list. Checks
        structural properties instead: exactly 2 legacy aliases, each
        mapping to a distinct, real (canonical) address that is not itself
        a retired alias."""
        aliases = TaxConsultantConstants.LEGACY_ALIASES
        assert len(aliases) == 2
        for ghost, real in aliases.items():
            assert real in TaxConsultantConstants.CANONICAL
            assert ghost not in TaxConsultantConstants.CANONICAL
            assert ghost != real

    def test_normalize_maps_ghost_1_to_real_1(self):
        """Ghost/real strings deliberately come from LEGACY_ALIASES rather
        than being restated as literals here — see the guard-exclusion
        reasoning on the test above."""
        ghost, real = list(TaxConsultantConstants.LEGACY_ALIASES.items())[0]
        assert TaxConsultantConstants.normalize(ghost) == real

    def test_normalize_maps_mixed_case_whitespace_ghost_2_to_real_2(self):
        ghost, real = list(TaxConsultantConstants.LEGACY_ALIASES.items())[1]
        mixed_case_padded = f"  {ghost.title()}  "
        assert TaxConsultantConstants.normalize(mixed_case_padded) == real

    def test_normalize_leaves_a_real_address_unchanged(self):
        assert TaxConsultantConstants.normalize("tax@balizero.com") == "tax@balizero.com"

    def test_normalize_leaves_an_unknown_address_unchanged(self):
        assert TaxConsultantConstants.normalize("random@email.com") == "random@email.com"

    def test_normalize_none_stays_none(self):
        assert TaxConsultantConstants.normalize(None) is None
