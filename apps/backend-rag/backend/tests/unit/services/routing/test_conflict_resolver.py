"""
Unit tests for ConflictResolver
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.routing.conflict_resolver import ConflictResolver


@pytest.fixture
def conflict_resolver():
    """Create ConflictResolver instance"""
    return ConflictResolver()


class TestConflictResolver:
    """Tests for ConflictResolver"""

    def test_init(self, conflict_resolver):
        """Test initialization"""
        assert conflict_resolver.stats["conflicts_detected"] == 0
        assert conflict_resolver.stats["conflicts_resolved"] == 0

    def test_detect_conflicts_no_conflicts(self, conflict_resolver):
        """Test detecting conflicts when none exist"""
        results_by_collection = {
            "visa_oracle": [{"score": 0.8, "metadata": {}}],
            "tax_genius": [{"score": 0.7, "metadata": {}}],
        }
        conflicts = conflict_resolver.detect_conflicts(results_by_collection)
        assert isinstance(conflicts, list)

    def test_detect_conflicts_with_conflicts(self, conflict_resolver):
        """Test detecting conflicts between collections"""
        results_by_collection = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"timestamp": "2024-01-01"}}],
            "tax_updates": [{"score": 0.9, "metadata": {"timestamp": "2024-01-02"}}],
        }
        conflicts = conflict_resolver.detect_conflicts(results_by_collection)
        assert len(conflicts) > 0
        assert conflict_resolver.stats["conflicts_detected"] > 0

    def test_resolve_conflicts(self, conflict_resolver):
        """Test resolving conflicts"""
        results_by_collection = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"timestamp": "2024-01-01"}}],
            "tax_updates": [{"score": 0.9, "metadata": {"timestamp": "2024-01-02"}}],
        }
        conflicts = conflict_resolver.detect_conflicts(results_by_collection)
        resolved, flagged = conflict_resolver.resolve_conflicts(results_by_collection, conflicts)
        assert isinstance(resolved, list)
        assert isinstance(flagged, list)

    def test_get_stats(self, conflict_resolver):
        """Test getting resolver statistics"""
        stats = conflict_resolver.get_stats()
        assert isinstance(stats, dict)
        assert "conflicts_detected" in stats
        assert "conflicts_resolved" in stats
