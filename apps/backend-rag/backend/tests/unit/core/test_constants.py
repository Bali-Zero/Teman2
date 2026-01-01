"""
Unit tests for constants modules
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.constants import (
    SearchConstants,
    RoutingConstants,
    CRMConstants,
    MemoryConstants,
    DatabaseConstants,
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

