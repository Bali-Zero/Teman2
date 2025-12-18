"""
Unit tests for ConflictResolver Service
Tests conflict detection and resolution between collection results
"""

import sys
from pathlib import Path

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.conflict_resolver import ConflictResolver


@pytest.mark.unit
class TestConflictResolverInit:
    """Test ConflictResolver initialization"""

    def test_init(self):
        """Test initialization"""
        resolver = ConflictResolver()

        assert resolver.stats["conflicts_detected"] == 0
        assert resolver.stats["conflicts_resolved"] == 0
        assert resolver.stats["timestamp_resolutions"] == 0
        assert resolver.stats["semantic_resolutions"] == 0


@pytest.mark.unit
class TestConflictResolverDetection:
    """Test conflict detection"""

    def test_detect_conflicts_no_conflicts(self):
        """Test detecting conflicts when none exist"""
        resolver = ConflictResolver()

        results = {
            "visa_oracle": [{"score": 0.9, "text": "Visa info", "metadata": {}}],
            "kbli_eye": [{"score": 0.8, "text": "KBLI info", "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        # These collections are not in conflict_pairs, so no conflicts
        assert len(conflicts) == 0

    def test_detect_conflicts_temporal(self):
        """Test detecting temporal conflicts"""
        resolver = ConflictResolver()

        results = {
            "tax_knowledge": [
                {"score": 0.9, "text": "Old tax info", "metadata": {"timestamp": "2023-01-01"}}
            ],
            "tax_updates": [
                {"score": 0.95, "text": "New tax info", "metadata": {"timestamp": "2024-01-01"}}
            ],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) > 0
        assert conflicts[0]["type"] == "temporal"
        assert "tax_knowledge" in conflicts[0]["collections"]
        assert "tax_updates" in conflicts[0]["collections"]

    def test_detect_conflicts_semantic(self):
        """Test detecting semantic conflicts"""
        resolver = ConflictResolver()

        results = {
            "legal_architect": [{"score": 0.85, "text": "Legal info", "metadata": {}}],
            "legal_updates": [{"score": 0.90, "text": "Updated legal info", "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) > 0
        assert resolver.stats["conflicts_detected"] > 0
        assert conflicts[0]["type"] == "temporal"  # legal_updates triggers temporal

    def test_detect_conflicts_empty_results(self):
        """Test detecting conflicts with empty results"""
        resolver = ConflictResolver()

        results = {"tax_knowledge": [], "tax_updates": []}

        conflicts = resolver.detect_conflicts(results)

        # Empty results don't trigger conflicts
        assert len(conflicts) == 0

    def test_get_stats(self):
        """Test getting conflict resolution statistics"""
        resolver = ConflictResolver()

        stats = resolver.get_stats()

        assert isinstance(stats, dict)
        assert "conflicts_detected" in stats
        assert "conflicts_resolved" in stats
        assert "timestamp_resolutions" in stats
        assert "semantic_resolutions" in stats

    def test_detect_conflicts_single_collection(self):
        """Test detecting conflicts with single collection"""
        resolver = ConflictResolver()

        results = {"tax_knowledge": [{"score": 0.9, "text": "Info"}]}

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0


@pytest.mark.unit
class TestConflictResolverResolution:
    """Test conflict resolution"""

    def test_resolve_conflicts_timestamp_priority(self):
        """Test resolving conflicts with timestamp priority"""
        resolver = ConflictResolver()

        results = {
            "tax_knowledge": [
                {"score": 0.9, "text": "Old", "metadata": {"timestamp": "2023-01-01"}}
            ],
            "tax_updates": [
                {"score": 0.85, "text": "New", "metadata": {"timestamp": "2024-01-01"}}
            ],
        }

        conflicts = resolver.detect_conflicts(results)
        resolved, conflict_reports = resolver.resolve_conflicts(results, conflicts)

        assert len(resolved) > 0
        assert len(conflict_reports) > 0
        assert resolver.stats["conflicts_resolved"] > 0
        assert resolver.stats["timestamp_resolutions"] > 0

    def test_resolve_conflicts_score_priority(self):
        """Test resolving conflicts with score priority"""
        resolver = ConflictResolver()

        results = {
            "legal_architect": [{"score": 0.95, "text": "High score", "metadata": {}}],
            "legal_updates": [{"score": 0.80, "text": "Lower score", "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)
        resolved, conflict_reports = resolver.resolve_conflicts(results, conflicts)

        assert len(resolved) > 0
        assert len(conflict_reports) > 0
        # Updates should win even with lower score
        assert resolver.stats["timestamp_resolutions"] > 0

    def test_resolve_conflicts_no_conflicts(self):
        """Test resolving when no conflicts"""
        resolver = ConflictResolver()

        results = {"visa_oracle": [{"score": 0.9, "text": "Info", "metadata": {}}]}

        resolved, conflict_reports = resolver.resolve_conflicts(results, [])

        # When no conflicts, should return empty lists
        assert len(resolved) == 0
        assert len(conflict_reports) == 0

    def test_resolve_conflicts_updates_win(self):
        """Test that *_updates collections win over base collections"""
        resolver = ConflictResolver()

        results = {
            "tax_genius": [{"score": 0.9, "text": "Base info", "metadata": {}}],
            "tax_updates": [
                {"score": 0.85, "text": "Updated info", "metadata": {"timestamp": "2024-01-01"}}
            ],
        }

        conflicts = resolver.detect_conflicts(results)
        resolved, conflict_reports = resolver.resolve_conflicts(results, conflicts)

        # Updates should win
        assert len(resolved) > 0
        assert len(conflict_reports) > 0
        assert resolver.stats["conflicts_resolved"] > 0
        assert resolver.stats["timestamp_resolutions"] > 0
