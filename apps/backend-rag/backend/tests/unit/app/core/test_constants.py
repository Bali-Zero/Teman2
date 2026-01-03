"""
Unit tests for app constants
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.constants import (
    CRMConstants,
    DatabaseConstants,
    MemoryConstants,
    RoutingConstants,
    SearchConstants,
)


class TestConstants:
    """Tests for app constants"""

    def test_search_constants(self):
        """Test SearchConstants"""
        assert SearchConstants.PRICING_SCORE_BOOST == 0.15
        assert SearchConstants.CONFLICT_PENALTY_MULTIPLIER == 0.7
        assert SearchConstants.PRIMARY_COLLECTION_BOOST == 1.1
        assert SearchConstants.MAX_SCORE == 1.0

    def test_routing_constants(self):
        """Test RoutingConstants"""
        assert RoutingConstants.CONFIDENCE_THRESHOLD_HIGH == 0.7
        assert RoutingConstants.CONFIDENCE_THRESHOLD_LOW == 0.3
        assert RoutingConstants.MAX_FALLBACKS == 3

    def test_crm_constants(self):
        """Test CRMConstants"""
        assert CRMConstants.CLIENT_CONFIDENCE_THRESHOLD_CREATE == 0.5
        assert CRMConstants.CLIENT_CONFIDENCE_THRESHOLD_UPDATE == 0.6
        assert CRMConstants.SUMMARY_MAX_LENGTH == 500
        assert CRMConstants.PRACTICES_LIMIT == 10

    def test_memory_constants(self):
        """Test MemoryConstants"""
        assert MemoryConstants.MAX_FACTS == 10
        assert MemoryConstants.MAX_SUMMARY_LENGTH == 500

    def test_database_constants(self):
        """Test DatabaseConstants"""
        assert DatabaseConstants.POOL_MIN_SIZE == 2
        assert DatabaseConstants.POOL_MAX_SIZE == 10
        assert DatabaseConstants.COMMAND_TIMEOUT == 60

