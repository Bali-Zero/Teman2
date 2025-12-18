"""
Integration Tests for ConflictResolver
Tests conflict detection and resolution
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestConflictResolverIntegration:
    """Comprehensive integration tests for ConflictResolver"""

    @pytest.fixture
    def resolver(self):
        """Create ConflictResolver instance"""
        from services.conflict_resolver import ConflictResolver

        return ConflictResolver()

    def test_initialization(self, resolver):
        """Test resolver initialization"""
        assert resolver is not None
        assert resolver.stats is not None

    def test_detect_conflicts_temporal(self, resolver):
        """Test detecting temporal conflicts"""
        results_by_collection = {
            "tax_knowledge": [
                {"text": "Tax info", "score": 0.9, "metadata": {"timestamp": "2023-01-01"}}
            ],
            "tax_updates": [
                {"text": "Updated tax info", "score": 0.85, "metadata": {"timestamp": "2024-01-01"}}
            ],
        }

        conflicts = resolver.detect_conflicts(results_by_collection)

        assert len(conflicts) > 0
        assert conflicts[0]["type"] == "temporal"

    def test_detect_conflicts_semantic(self, resolver):
        """Test detecting semantic conflicts"""
        results_by_collection = {
            "legal_architect": [{"text": "Legal info", "score": 0.9, "metadata": {}}],
            "legal_updates": [{"text": "Updated legal info", "score": 0.85, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results_by_collection)

        assert len(conflicts) > 0

    def test_detect_conflicts_no_conflicts(self, resolver):
        """Test detecting no conflicts"""
        results_by_collection = {
            "tax_knowledge": [{"text": "Tax info", "score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results_by_collection)

        assert len(conflicts) == 0

    def test_resolve_conflicts_temporal_priority(self, resolver):
        """Test resolving conflicts with temporal priority"""
        results_by_collection = {
            "tax_knowledge": [{"text": "Tax info", "score": 0.9, "metadata": {}}],
            "tax_updates": [{"text": "Updated tax info", "score": 0.85, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results_by_collection)
        resolved, reports = resolver.resolve_conflicts(results_by_collection, conflicts)

        assert len(resolved) > 0
        assert len(reports) > 0
        assert reports[0]["resolution"]["winner"] == "tax_updates"

    def test_resolve_conflicts_relevance_score(self, resolver):
        """Test resolving conflicts with relevance score"""
        results_by_collection = {
            "property_knowledge": [{"text": "Property info", "score": 0.7, "metadata": {}}],
            "property_listings": [{"text": "Property listing", "score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results_by_collection)
        resolved, reports = resolver.resolve_conflicts(results_by_collection, conflicts)

        assert len(resolved) > 0
        assert len(reports) > 0

    def test_get_stats(self, resolver):
        """Test getting conflict resolution statistics"""
        stats = resolver.get_stats()

        assert stats is not None
        assert "conflicts_detected" in stats
        assert "conflicts_resolved" in stats
        assert "timestamp_resolutions" in stats
        assert "semantic_resolutions" in stats
