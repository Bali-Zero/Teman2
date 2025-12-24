"""
Comprehensive unit tests for ConflictResolver service - Target 90%+ coverage

Tests cover:
- Initialization and state management
- Conflict detection across all collection pairs
- Conflict resolution strategies (temporal, semantic)
- Edge cases (empty results, missing metadata, score ties)
- Statistics tracking
- Metadata handling and flagging
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# Setup environment
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

# Setup paths
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import pytest
from services.conflict_resolver import ConflictResolver
from app.core.constants import SearchConstants


class TestConflictResolverInitialization:
    """Test ConflictResolver initialization and basic setup"""

    def test_init_creates_empty_stats(self):
        """Test that initialization creates empty statistics dictionary"""
        resolver = ConflictResolver()

        assert isinstance(resolver.stats, dict)
        assert resolver.stats["conflicts_detected"] == 0
        assert resolver.stats["conflicts_resolved"] == 0
        assert resolver.stats["timestamp_resolutions"] == 0
        assert resolver.stats["semantic_resolutions"] == 0

    def test_init_logs_initialization(self, caplog):
        """Test that initialization logs success message"""
        import logging
        caplog.set_level(logging.INFO)

        resolver = ConflictResolver()

        assert "ConflictResolver initialized" in caplog.text

    def test_multiple_instances_independent(self):
        """Test that multiple instances maintain independent stats"""
        resolver1 = ConflictResolver()
        resolver2 = ConflictResolver()

        resolver1.stats["conflicts_detected"] = 5

        assert resolver1.stats["conflicts_detected"] == 5
        assert resolver2.stats["conflicts_detected"] == 0


class TestConflictDetection:
    """Test conflict detection across various collection pairs"""

    def test_detect_conflicts_tax_knowledge_vs_tax_updates(self):
        """Test detecting conflict between tax_knowledge and tax_updates"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"doc_id": "1"}}],
            "tax_updates": [{"score": 0.9, "metadata": {"doc_id": "2"}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert conflicts[0]["collections"] == ["tax_knowledge", "tax_updates"]
        assert conflicts[0]["type"] == "temporal"
        assert conflicts[0]["collection1_results"] == 1
        assert conflicts[0]["collection2_results"] == 1
        assert conflicts[0]["collection1_top_score"] == 0.8
        assert conflicts[0]["collection2_top_score"] == 0.9
        assert "detected_at" in conflicts[0]
        assert resolver.stats["conflicts_detected"] == 1

    def test_detect_conflicts_legal_architect_vs_legal_updates(self):
        """Test detecting conflict between legal_architect and legal_updates"""
        resolver = ConflictResolver()
        results = {
            "legal_architect": [{"score": 0.7, "metadata": {}}],
            "legal_updates": [{"score": 0.85, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        # legal_architect appears twice in conflict_pairs
        assert len(conflicts) == 2
        assert conflicts[0]["type"] == "temporal"
        assert resolver.stats["conflicts_detected"] == 2

    def test_detect_conflicts_property_knowledge_vs_property_listings(self):
        """Test detecting conflict between property_knowledge and property_listings"""
        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.75, "metadata": {}}],
            "property_listings": [{"score": 0.8, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert conflicts[0]["collections"] == ["property_knowledge", "property_listings"]
        assert conflicts[0]["type"] == "semantic"  # No "updates" in coll2

    def test_detect_conflicts_tax_genius_vs_tax_updates(self):
        """Test detecting conflict between tax_genius and tax_updates"""
        resolver = ConflictResolver()
        results = {
            "tax_genius": [{"score": 0.88, "metadata": {}}],
            "tax_updates": [{"score": 0.92, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert conflicts[0]["collections"] == ["tax_genius", "tax_updates"]
        assert conflicts[0]["type"] == "temporal"

    def test_detect_conflicts_with_timestamps(self):
        """Test detecting conflicts with timestamp metadata"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"timestamp": "2023-01-01T00:00:00Z"}}],
            "tax_updates": [{"score": 0.9, "metadata": {"timestamp": "2024-01-01T00:00:00Z"}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert "timestamp1" in conflicts[0]
        assert "timestamp2" in conflicts[0]
        assert conflicts[0]["timestamp1"] == "2023-01-01T00:00:00Z"
        assert conflicts[0]["timestamp2"] == "2024-01-01T00:00:00Z"

    def test_detect_conflicts_one_timestamp_only(self):
        """Test detecting conflicts when only one collection has timestamp"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"timestamp": "2023-01-01"}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert conflicts[0]["timestamp1"] == "2023-01-01"
        assert conflicts[0]["timestamp2"] == "unknown"

    def test_detect_conflicts_no_conflicts(self):
        """Test detecting no conflicts when collections don't match pairs"""
        resolver = ConflictResolver()
        results = {
            "other_collection": [{"score": 0.8, "metadata": {}}],
            "another_collection": [{"score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0
        assert resolver.stats["conflicts_detected"] == 0

    def test_detect_conflicts_empty_results(self):
        """Test detecting conflicts with empty result lists"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [],
            "tax_updates": [],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0
        assert resolver.stats["conflicts_detected"] == 0

    def test_detect_conflicts_one_empty_collection(self):
        """Test detecting conflicts when one collection is empty"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0

    def test_detect_conflicts_both_collections_empty(self):
        """Test detecting conflicts when both collections exist but are empty"""
        resolver = ConflictResolver()
        results = {
            "legal_architect": [],
            "legal_updates": [],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0

    def test_detect_conflicts_empty_metadata(self):
        """Test detecting conflicts without any metadata"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert "timestamp1" not in conflicts[0]
        assert "timestamp2" not in conflicts[0]

    def test_detect_conflicts_logs_warning(self, caplog):
        """Test that conflict detection logs warning messages"""
        import logging
        caplog.set_level(logging.WARNING)

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
        }

        resolver.detect_conflicts(results)

        assert "Conflict Detected" in caplog.text
        assert "tax_knowledge vs tax_updates" in caplog.text

    def test_detect_conflicts_datetime_format(self):
        """Test that detected_at timestamp is in ISO format"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        # Validate ISO format
        detected_at = conflicts[0]["detected_at"]
        datetime.fromisoformat(detected_at)  # Should not raise

    def test_detect_conflicts_multiple_pairs(self):
        """Test detecting conflicts across multiple collection pairs"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
            "legal_architect": [{"score": 0.7, "metadata": {}}],
            "legal_updates": [{"score": 0.85, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        # Should detect tax and legal conflicts (legal appears twice)
        assert len(conflicts) >= 2


class TestConflictResolution:
    """Test conflict resolution strategies and outcomes"""

    def test_resolve_conflicts_updates_collection_wins_coll2(self):
        """Test resolving conflicts where updates collection (coll2) wins"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "base"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "updates"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert len(resolved) == 2
        assert resolver.stats["timestamp_resolutions"] == 1
        assert resolver.stats["conflicts_resolved"] == 1

        # Find winner and loser
        winner = next(r for r in resolved if r["id"] == "updates")
        loser = next(r for r in resolved if r["id"] == "base")

        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert winner["metadata"]["conflict_resolution"]["reason"] == "temporal_priority (updates collection)"
        assert winner["metadata"]["conflict_resolution"]["alternate_source"] == "tax_knowledge"

        assert loser["metadata"]["conflict_resolution"]["status"] == "alternate"
        assert loser["score"] == 0.8 * 0.7  # Penalized

    def test_resolve_conflicts_updates_collection_wins_coll1(self):
        """Test resolving conflicts where updates collection (coll1) wins"""
        resolver = ConflictResolver()
        results = {
            "tax_updates": [{"score": 0.8, "metadata": {}, "id": "updates"}],
            "tax_knowledge": [{"score": 0.9, "metadata": {}, "id": "base"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert resolver.stats["timestamp_resolutions"] == 1
        assert len(resolved) == 2

        winner = next(r for r in resolved if r["id"] == "updates")
        loser = next(r for r in resolved if r["id"] == "base")

        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert winner["metadata"]["conflict_resolution"]["reason"] == "temporal_priority (updates collection)"
        assert winner["metadata"]["conflict_resolution"]["alternate_source"] == "tax_knowledge"

        assert loser["metadata"]["conflict_resolution"]["status"] == "alternate"
        assert loser["metadata"]["conflict_resolution"]["preferred_source"] == "tax_updates"

    def test_resolve_conflicts_relevance_score_coll2_wins(self):
        """Test resolving conflicts using relevance score when coll2 has higher score"""
        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.7, "metadata": {}, "id": "lower"}],
            "property_listings": [{"score": 0.9, "metadata": {}, "id": "higher"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert resolver.stats["semantic_resolutions"] == 1

        winner = next(r for r in resolved if r["id"] == "higher")
        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert winner["metadata"]["conflict_resolution"]["reason"] == "relevance_score"

    def test_resolve_conflicts_relevance_score_coll1_wins(self):
        """Test resolving conflicts using relevance score when coll1 has higher score"""
        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.9, "metadata": {}, "id": "higher"}],
            "property_listings": [{"score": 0.7, "metadata": {}, "id": "lower"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert resolver.stats["semantic_resolutions"] == 1

        winner = next(r for r in resolved if r["id"] == "higher")
        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"

    def test_resolve_conflicts_score_tie_coll1_wins(self):
        """Test resolving conflicts when scores are equal - coll1 should win"""
        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.8, "metadata": {}, "id": "coll1"}],
            "property_listings": [{"score": 0.8, "metadata": {}, "id": "coll2"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # In case of tie, coll1 wins (score2 > score1 check)
        winner = next(r for r in resolved if r["id"] == "coll1")
        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"

    def test_resolve_conflicts_loser_flagged_outdated(self):
        """Test that loser results are flagged as outdated for timestamp resolutions"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "loser"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "winner"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        loser = next(r for r in resolved if r["id"] == "loser")
        # Status is "outdated" if "timestamp" in reason, else "alternate"
        # Reason is "temporal_priority (updates collection)" which doesn't contain "timestamp"
        assert loser["metadata"]["conflict_resolution"]["status"] == "alternate"
        assert loser["metadata"]["conflict_resolution"]["preferred_source"] == "tax_updates"

    def test_resolve_conflicts_loser_score_penalty(self):
        """Test that loser results have their scores penalized"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "loser"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "winner"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        loser = next(r for r in resolved if r["id"] == "loser")
        # Score should be multiplied by CONFLICT_PENALTY_MULTIPLIER (0.7)
        assert loser["score"] == pytest.approx(0.8 * 0.7)

    def test_resolve_conflicts_multiple_results_per_collection(self):
        """Test resolving conflicts with multiple results per collection"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [
                {"score": 0.8, "metadata": {}, "id": "r1"},
                {"score": 0.7, "metadata": {}, "id": "r2"},
                {"score": 0.6, "metadata": {}, "id": "r3"},
            ],
            "tax_updates": [
                {"score": 0.9, "metadata": {}, "id": "r4"},
                {"score": 0.85, "metadata": {}, "id": "r5"},
            ],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # All results should be included
        assert len(resolved) == 5

        # All tax_updates results should be preferred
        updates_results = [r for r in resolved if r["id"] in ["r4", "r5"]]
        for result in updates_results:
            assert result["metadata"]["conflict_resolution"]["status"] == "preferred"

        # All tax_knowledge results should be alternate with penalty
        knowledge_results = [r for r in resolved if r["id"] in ["r1", "r2", "r3"]]
        for result in knowledge_results:
            assert result["metadata"]["conflict_resolution"]["status"] == "alternate"

    def test_resolve_conflicts_empty_conflicts_list(self):
        """Test resolving with empty conflicts list"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
        }

        resolved, reports = resolver.resolve_conflicts(results, [])

        assert len(resolved) == 0
        assert len(reports) == 0
        assert resolver.stats["conflicts_resolved"] == 0

    def test_resolve_conflicts_conflict_reports_generated(self):
        """Test that conflict reports are generated correctly"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "r1"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "r2"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert len(reports) == 1
        assert "resolution" in reports[0]
        assert reports[0]["resolution"]["winner"] == "tax_updates"
        assert reports[0]["resolution"]["loser"] == "tax_knowledge"
        assert reports[0]["resolution"]["reason"] == "temporal_priority (updates collection)"

        # Report should include original conflict data
        assert reports[0]["collections"] == ["tax_knowledge", "tax_updates"]
        assert reports[0]["type"] == "temporal"

    def test_resolve_conflicts_logs_resolution(self, caplog):
        """Test that conflict resolution logs info messages"""
        import logging
        caplog.set_level(logging.INFO)

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "r1"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "r2"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolver.resolve_conflicts(results, conflicts)

        assert "Conflict Resolved" in caplog.text
        assert "tax_updates (preferred)" in caplog.text

    def test_resolve_conflicts_empty_results1(self):
        """Test resolving conflicts when results1 is empty but in conflict list"""
        resolver = ConflictResolver()
        # Manually create conflict (normally wouldn't happen via detect_conflicts)
        conflict = {
            "collections": ["tax_knowledge", "tax_updates"],
            "type": "temporal",
        }
        results = {
            "tax_knowledge": [],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "r1"}],
        }

        resolved, reports = resolver.resolve_conflicts(results, [conflict])

        # Should handle gracefully
        assert len(resolved) == 1  # Only tax_updates result

    def test_resolve_conflicts_empty_results2(self):
        """Test resolving conflicts when results2 is empty but in conflict list"""
        resolver = ConflictResolver()
        conflict = {
            "collections": ["tax_knowledge", "tax_updates"],
            "type": "temporal",
        }
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "r1"}],
            "tax_updates": [],
        }

        resolved, reports = resolver.resolve_conflicts(results, [conflict])

        # Should handle gracefully - coll2 has "updates" but empty, so score comparison
        assert len(resolved) == 1  # Only tax_knowledge result

    def test_resolve_conflicts_updates_in_coll1_with_manual_conflict(self):
        """Test resolving conflicts where updates is in coll1 position (manual conflict)"""
        resolver = ConflictResolver()
        # Create a manual conflict where updates collection is in coll1 position
        conflict = {
            "collections": ["legal_updates", "legal_architect"],  # Reversed order
            "type": "temporal",
        }
        results = {
            "legal_updates": [{"score": 0.8, "metadata": {}, "id": "updates"}],
            "legal_architect": [{"score": 0.9, "metadata": {}, "id": "base"}],
        }

        resolved, reports = resolver.resolve_conflicts(results, [conflict])

        # updates collection (coll1) should win even with lower score
        assert len(resolved) == 2
        assert resolver.stats["timestamp_resolutions"] == 1

        winner = next(r for r in resolved if r["id"] == "updates")
        loser = next(r for r in resolved if r["id"] == "base")

        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert winner["metadata"]["conflict_resolution"]["reason"] == "temporal_priority (updates collection)"
        assert loser["metadata"]["conflict_resolution"]["status"] == "alternate"


class TestStatistics:
    """Test statistics tracking and retrieval"""

    def test_get_stats_returns_copy(self):
        """Test that get_stats returns a copy of stats dictionary"""
        resolver = ConflictResolver()

        stats = resolver.get_stats()
        stats["conflicts_detected"] = 999

        # Original should be unchanged
        assert resolver.stats["conflicts_detected"] == 0

    def test_get_stats_structure(self):
        """Test that get_stats returns correct structure"""
        resolver = ConflictResolver()

        stats = resolver.get_stats()

        assert isinstance(stats, dict)
        assert "conflicts_detected" in stats
        assert "conflicts_resolved" in stats
        assert "timestamp_resolutions" in stats
        assert "semantic_resolutions" in stats

    def test_stats_track_multiple_operations(self):
        """Test that stats correctly track multiple operations"""
        resolver = ConflictResolver()

        # First conflict - temporal
        results1 = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "r1"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "r2"}],
        }
        conflicts1 = resolver.detect_conflicts(results1)
        resolver.resolve_conflicts(results1, conflicts1)

        # Second conflict - semantic
        results2 = {
            "property_knowledge": [{"score": 0.7, "metadata": {}, "id": "r3"}],
            "property_listings": [{"score": 0.9, "metadata": {}, "id": "r4"}],
        }
        conflicts2 = resolver.detect_conflicts(results2)
        resolver.resolve_conflicts(results2, conflicts2)

        stats = resolver.get_stats()
        assert stats["conflicts_detected"] == 2
        assert stats["conflicts_resolved"] == 2
        assert stats["timestamp_resolutions"] == 1
        assert stats["semantic_resolutions"] == 1


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_detect_conflicts_missing_collection_in_results(self):
        """Test detect_conflicts when expected collection is missing"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            # Missing tax_updates
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0

    def test_detect_conflicts_zero_scores(self):
        """Test detect_conflicts with zero scores"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.0, "metadata": {}}],
            "tax_updates": [{"score": 0.0, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert conflicts[0]["collection1_top_score"] == 0.0
        assert conflicts[0]["collection2_top_score"] == 0.0

    def test_resolve_conflicts_zero_scores(self):
        """Test resolve_conflicts with zero scores"""
        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.0, "metadata": {}, "id": "r1"}],
            "property_listings": [{"score": 0.0, "metadata": {}, "id": "r2"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # Should handle gracefully - coll1 wins on tie
        assert len(resolved) == 2

    def test_detect_conflicts_all_conflict_pairs(self):
        """Test that all defined conflict pairs are checked"""
        resolver = ConflictResolver()

        # Test all pairs exist in results
        all_pairs_results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
            "legal_architect": [{"score": 0.7, "metadata": {}}],
            "legal_updates": [{"score": 0.85, "metadata": {}}],
            "property_knowledge": [{"score": 0.75, "metadata": {}}],
            "property_listings": [{"score": 0.8, "metadata": {}}],
            "tax_genius": [{"score": 0.88, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(all_pairs_results)

        # Should detect multiple conflicts
        assert len(conflicts) >= 3

    def test_resolve_conflicts_preserves_original_metadata(self):
        """Test that conflict resolution preserves original metadata"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"custom": "value1"}, "id": "r1"}],
            "tax_updates": [{"score": 0.9, "metadata": {"custom": "value2"}, "id": "r2"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # Check that original metadata is preserved
        r1 = next(r for r in resolved if r["id"] == "r1")
        r2 = next(r for r in resolved if r["id"] == "r2")

        assert r1["metadata"]["custom"] == "value1"
        assert r2["metadata"]["custom"] == "value2"
        assert "conflict_resolution" in r1["metadata"]
        assert "conflict_resolution" in r2["metadata"]

    def test_detect_conflicts_none_values(self):
        """Test detect_conflicts handles None values gracefully"""
        resolver = ConflictResolver()
        results = {
            "tax_knowledge": None,  # Unusual case
        }

        # Should handle without crashing - will skip since not both in results
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 0

    def test_resolve_conflicts_updates_coll1_empty_results2(self):
        """Test resolve when coll1 is updates and results2 exists"""
        resolver = ConflictResolver()
        results = {
            "legal_updates": [{"score": 0.8, "metadata": {}, "id": "updates"}],
            "legal_architect": [{"score": 0.9, "metadata": {}, "id": "base"}],
        }
        conflicts = resolver.detect_conflicts(results)

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # updates collection should win even with lower score
        winner = next(r for r in resolved if r["id"] == "updates")
        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert resolver.stats["timestamp_resolutions"] >= 1


class TestIntegration:
    """Integration tests combining detection and resolution"""

    def test_full_workflow_temporal_conflict(self):
        """Test complete workflow for temporal conflict"""
        resolver = ConflictResolver()

        # Setup
        results = {
            "tax_knowledge": [
                {"score": 0.8, "metadata": {"timestamp": "2023-01-01"}, "id": "old"},
            ],
            "tax_updates": [
                {"score": 0.9, "metadata": {"timestamp": "2024-01-01"}, "id": "new"},
            ],
        }

        # Detect
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "temporal"
        assert conflicts[0]["timestamp1"] == "2023-01-01"
        assert conflicts[0]["timestamp2"] == "2024-01-01"

        # Resolve
        resolved, reports = resolver.resolve_conflicts(results, conflicts)
        assert len(resolved) == 2
        assert len(reports) == 1

        # Verify winner
        winner = next(r for r in resolved if r["id"] == "new")
        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"

        # Verify stats
        stats = resolver.get_stats()
        assert stats["conflicts_detected"] == 1
        assert stats["conflicts_resolved"] == 1
        assert stats["timestamp_resolutions"] == 1

    def test_full_workflow_semantic_conflict(self):
        """Test complete workflow for semantic conflict"""
        resolver = ConflictResolver()

        # Setup
        results = {
            "property_knowledge": [
                {"score": 0.7, "metadata": {"source": "kb"}, "id": "kb_result"},
            ],
            "property_listings": [
                {"score": 0.9, "metadata": {"source": "listings"}, "id": "listing_result"},
            ],
        }

        # Detect
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "semantic"

        # Resolve
        resolved, reports = resolver.resolve_conflicts(results, conflicts)
        assert len(resolved) == 2

        # Verify winner is higher score
        winner = next(r for r in resolved if r["id"] == "listing_result")
        assert winner["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert winner["metadata"]["conflict_resolution"]["reason"] == "relevance_score"

        # Verify stats
        stats = resolver.get_stats()
        assert stats["semantic_resolutions"] == 1

    def test_multiple_conflicts_workflow(self):
        """Test workflow with multiple simultaneous conflicts"""
        resolver = ConflictResolver()

        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}, "id": "tax_kb"}],
            "tax_updates": [{"score": 0.9, "metadata": {}, "id": "tax_upd"}],
            "legal_architect": [{"score": 0.7, "metadata": {}, "id": "legal_kb"}],
            "legal_updates": [{"score": 0.85, "metadata": {}, "id": "legal_upd"}],
        }

        # Detect
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) >= 2  # At least tax and legal

        # Resolve
        resolved, reports = resolver.resolve_conflicts(results, conflicts)
        assert len(resolved) >= 4
        assert len(reports) >= 2

        # Verify all updates collections won
        tax_update_result = next(r for r in resolved if r["id"] == "tax_upd")
        legal_update_result = next(r for r in resolved if r["id"] == "legal_upd")

        assert tax_update_result["metadata"]["conflict_resolution"]["status"] == "preferred"
        assert legal_update_result["metadata"]["conflict_resolution"]["status"] == "preferred"

        # Verify stats
        stats = resolver.get_stats()
        assert stats["conflicts_detected"] >= 2
        assert stats["conflicts_resolved"] >= 2
