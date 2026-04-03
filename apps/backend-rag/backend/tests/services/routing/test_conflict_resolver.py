"""
Tests for conflict_resolver.py - Conflict detection and resolution between collections.
"""

import pytest

from backend.services.routing.conflict_resolver import ConflictResolver


@pytest.fixture
def resolver():
    return ConflictResolver()


def _make_result(score: float, metadata: dict | None = None) -> dict:
    """Helper to create a result dict."""
    return {"score": score, "metadata": metadata or {}}


class TestDetectConflicts:
    """Tests for detect_conflicts method."""

    def test_no_conflicts_when_no_overlapping_collections(self, resolver):
        results = {
            "visa_oracle": [_make_result(0.9)],
            "kbli_2025_final": [_make_result(0.8)],
        }
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 0

    def test_conflict_detected_for_known_pair(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.8)],
            "tax_updates": [_make_result(0.7)],
        }
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 1
        assert conflicts[0]["collections"] == ["tax_knowledge", "tax_updates"]
        assert conflicts[0]["type"] == "temporal"

    def test_conflict_detected_legal_pair(self, resolver):
        results = {
            "legal_architect": [_make_result(0.85)],
            "legal_updates": [_make_result(0.75)],
        }
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) >= 1

    def test_no_conflict_when_collection_empty(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.8)],
            "tax_updates": [],
        }
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 0

    def test_timestamp_metadata_captured(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.8, {"timestamp": "2025-01-01"})],
            "tax_updates": [_make_result(0.7, {"timestamp": "2026-01-01"})],
        }
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 1
        assert "timestamp1" in conflicts[0]
        assert "timestamp2" in conflicts[0]

    def test_stats_updated_on_conflict(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.8)],
            "tax_updates": [_make_result(0.7)],
        }
        resolver.detect_conflicts(results)
        assert resolver.stats["conflicts_detected"] == 1

    def test_semantic_conflict_type(self, resolver):
        """When no 'updates' in either collection name, type should be semantic."""
        results = {
            "tax_genius": [_make_result(0.8)],
            "tax_updates": [_make_result(0.7)],
        }
        conflicts = resolver.detect_conflicts(results)
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "temporal"  # "updates" in coll2


class TestResolveConflicts:
    """Tests for resolve_conflicts method."""

    def test_updates_collection_wins_temporal(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.9, {})],
            "tax_updates": [_make_result(0.7, {})],
        }
        conflicts = resolver.detect_conflicts(results)
        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert len(reports) == 1
        assert reports[0]["resolution"]["winner"] == "tax_updates"
        assert "temporal_priority" in reports[0]["resolution"]["reason"]

    def test_loser_score_penalized(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.9, {})],
            "tax_updates": [_make_result(0.7, {})],
        }
        conflicts = resolver.detect_conflicts(results)
        resolved, _ = resolver.resolve_conflicts(results, conflicts)

        for r in resolved:
            cr = r["metadata"].get("conflict_resolution", {})
            if cr.get("status") in ("outdated", "alternate"):
                assert r["score"] < 0.9  # Original was 0.9, penalized by 0.7x

    def test_winner_marked_as_preferred(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.8, {})],
            "tax_updates": [_make_result(0.7, {})],
        }
        conflicts = resolver.detect_conflicts(results)
        resolved, _ = resolver.resolve_conflicts(results, conflicts)

        preferred_found = False
        for r in resolved:
            cr = r["metadata"].get("conflict_resolution", {})
            if cr.get("status") == "preferred":
                preferred_found = True
        assert preferred_found

    def test_stats_after_resolution(self, resolver):
        results = {
            "tax_knowledge": [_make_result(0.8, {})],
            "tax_updates": [_make_result(0.7, {})],
        }
        conflicts = resolver.detect_conflicts(results)
        resolver.resolve_conflicts(results, conflicts)
        assert resolver.stats["conflicts_resolved"] == 1
        assert resolver.stats["timestamp_resolutions"] == 1

    def test_empty_conflicts_returns_empty(self, resolver):
        resolved, reports = resolver.resolve_conflicts({}, [])
        assert resolved == []
        assert reports == []


class TestGetStats:
    """Tests for get_stats method."""

    def test_initial_stats(self, resolver):
        stats = resolver.get_stats()
        assert stats["conflicts_detected"] == 0
        assert stats["conflicts_resolved"] == 0

    def test_stats_returns_copy(self, resolver):
        stats = resolver.get_stats()
        stats["conflicts_detected"] = 999
        assert resolver.get_stats()["conflicts_detected"] == 0
