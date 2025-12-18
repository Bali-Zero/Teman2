"""
Unit Tests for services/conflict_resolver.py - 95% Coverage Target
Tests the ConflictResolver class
"""

import os
import sys
from pathlib import Path

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test ConflictResolver initialization
# ============================================================================


class TestConflictResolverInit:
    """Test suite for ConflictResolver initialization"""

    def test_init_creates_stats(self):
        """Test initialization creates stats dictionary"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()

        assert "conflicts_detected" in resolver.stats
        assert "conflicts_resolved" in resolver.stats
        assert "timestamp_resolutions" in resolver.stats
        assert "semantic_resolutions" in resolver.stats
        assert resolver.stats["conflicts_detected"] == 0


# ============================================================================
# Test detect_conflicts
# ============================================================================


class TestDetectConflicts:
    """Test suite for detect_conflicts method"""

    def test_detect_no_conflicts_empty_input(self):
        """Test no conflicts with empty input"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        result = resolver.detect_conflicts({})

        assert result == []
        assert resolver.stats["conflicts_detected"] == 0

    def test_detect_no_conflicts_single_collection(self):
        """Test no conflicts with single collection"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {"tax_knowledge": [{"score": 0.9, "metadata": {"title": "Tax Guide"}}]}

        result = resolver.detect_conflicts(results)

        assert result == []

    def test_detect_conflict_tax_collections(self):
        """Test detecting conflict between tax collections"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {"title": "Old Tax Guide"}}],
            "tax_updates": [{"score": 0.85, "metadata": {"title": "New Tax Update"}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert "tax_knowledge" in conflicts[0]["collections"]
        assert "tax_updates" in conflicts[0]["collections"]
        assert conflicts[0]["type"] == "temporal"
        assert resolver.stats["conflicts_detected"] == 1

    def test_detect_conflict_legal_collections(self):
        """Test detecting conflict between legal collections"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "legal_architect": [{"score": 0.75, "metadata": {"title": "Legal Framework"}}],
            "legal_updates": [{"score": 0.9, "metadata": {"title": "Legal Update"}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) >= 1
        assert any("legal_architect" in c["collections"] for c in conflicts)

    def test_detect_conflict_with_timestamp_metadata(self):
        """Test detecting conflict with timestamp metadata"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [
                {"score": 0.8, "metadata": {"title": "Tax", "timestamp": "2024-01-01"}}
            ],
            "tax_updates": [
                {"score": 0.85, "metadata": {"title": "Update", "timestamp": "2024-06-01"}}
            ],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert "timestamp1" in conflicts[0]
        assert "timestamp2" in conflicts[0]
        assert conflicts[0]["timestamp1"] == "2024-01-01"
        assert conflicts[0]["timestamp2"] == "2024-06-01"

    def test_detect_no_conflict_when_one_empty(self):
        """Test no conflict when one collection is empty"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [],
            "tax_updates": [{"score": 0.85, "metadata": {"title": "Update"}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 0

    def test_detect_semantic_conflict_type(self):
        """Test semantic conflict type detection"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.8, "metadata": {"title": "Property Guide"}}],
            "property_listings": [{"score": 0.75, "metadata": {"title": "Listings"}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "semantic"

    def test_detect_conflict_records_scores(self):
        """Test conflict detection records collection scores"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.95, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert conflicts[0]["collection1_top_score"] == 0.8
        assert conflicts[0]["collection2_top_score"] == 0.95


# ============================================================================
# Test resolve_conflicts
# ============================================================================


class TestResolveConflicts:
    """Test suite for resolve_conflicts method"""

    def test_resolve_empty_conflicts(self):
        """Test resolving empty conflicts list"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()

        resolved, reports = resolver.resolve_conflicts({}, [])

        assert resolved == []
        assert reports == []

    def test_resolve_updates_collection_wins(self):
        """Test updates collection wins over base collection"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.9, "metadata": {"title": "Old"}}],
            "tax_updates": [{"score": 0.7, "metadata": {"title": "New"}}],
        }
        conflicts = [
            {
                "collections": ["tax_knowledge", "tax_updates"],
                "type": "temporal",
                "collection1_top_score": 0.9,
                "collection2_top_score": 0.7,
            }
        ]

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # Check updates collection won
        assert any(
            r["metadata"]["conflict_resolution"]["status"] == "preferred"
            and "tax_updates" in r["metadata"].get("title", "")
            or r["metadata"]["title"] == "New"
            for r in resolved
        )
        assert reports[0]["resolution"]["winner"] == "tax_updates"
        assert "temporal_priority" in reports[0]["resolution"]["reason"]
        assert resolver.stats["timestamp_resolutions"] >= 1

    def test_resolve_base_collection_as_updates(self):
        """Test when base collection name contains 'updates'"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "legal_updates": [{"score": 0.8, "metadata": {"title": "Update"}}],
            "legal_architect": [{"score": 0.9, "metadata": {"title": "Architect"}}],
        }
        conflicts = [
            {
                "collections": ["legal_updates", "legal_architect"],
                "type": "temporal",
                "collection1_top_score": 0.8,
                "collection2_top_score": 0.9,
            }
        ]

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert reports[0]["resolution"]["winner"] == "legal_updates"

    def test_resolve_by_score_when_no_updates(self):
        """Test resolution by score when neither is updates collection"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.6, "metadata": {"title": "Property 1"}}],
            "property_listings": [{"score": 0.9, "metadata": {"title": "Property 2"}}],
        }
        conflicts = [
            {
                "collections": ["property_knowledge", "property_listings"],
                "type": "semantic",
                "collection1_top_score": 0.6,
                "collection2_top_score": 0.9,
            }
        ]

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # Higher score wins
        assert reports[0]["resolution"]["winner"] == "property_listings"
        assert reports[0]["resolution"]["reason"] == "relevance_score"
        assert resolver.stats["semantic_resolutions"] >= 1

    def test_resolve_first_wins_on_equal_score(self):
        """Test first collection wins on equal score"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "property_knowledge": [{"score": 0.8, "metadata": {"title": "Property 1"}}],
            "property_listings": [{"score": 0.8, "metadata": {"title": "Property 2"}}],
        }
        conflicts = [
            {
                "collections": ["property_knowledge", "property_listings"],
                "type": "semantic",
                "collection1_top_score": 0.8,
                "collection2_top_score": 0.8,
            }
        ]

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # First wins on equal score
        assert reports[0]["resolution"]["winner"] == "property_knowledge"

    def test_resolve_marks_loser_as_alternate(self):
        """Test loser results are marked as alternate or outdated"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.9, "metadata": {"title": "Old Tax"}}],
            "tax_updates": [{"score": 0.7, "metadata": {"title": "New Tax"}}],
        }
        conflicts = [
            {
                "collections": ["tax_knowledge", "tax_updates"],
                "type": "temporal",
                "collection1_top_score": 0.9,
                "collection2_top_score": 0.7,
            }
        ]

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        # Find loser result and check status
        loser_results = [
            r
            for r in resolved
            if r["metadata"]["conflict_resolution"]["status"] in ["outdated", "alternate"]
        ]
        assert len(loser_results) == 1

    def test_resolve_reduces_loser_score(self):
        """Test loser results have reduced score"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        original_score = 0.9
        results = {
            "tax_knowledge": [{"score": original_score, "metadata": {"title": "Old Tax"}}],
            "tax_updates": [{"score": 0.7, "metadata": {"title": "New Tax"}}],
        }
        conflicts = [
            {
                "collections": ["tax_knowledge", "tax_updates"],
                "type": "temporal",
                "collection1_top_score": original_score,
                "collection2_top_score": 0.7,
            }
        ]

        resolved, _ = resolver.resolve_conflicts(results, conflicts)

        # Loser score should be reduced
        loser = [
            r for r in resolved if r["metadata"]["conflict_resolution"]["status"] != "preferred"
        ][0]
        assert loser["score"] < original_score

    def test_resolve_increments_resolved_count(self):
        """Test resolved count increments correctly"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.9, "metadata": {}}],
            "tax_updates": [{"score": 0.7, "metadata": {}}],
        }
        conflicts = [
            {
                "collections": ["tax_knowledge", "tax_updates"],
                "type": "temporal",
                "collection1_top_score": 0.9,
                "collection2_top_score": 0.7,
            }
        ]

        resolver.resolve_conflicts(results, conflicts)

        assert resolver.stats["conflicts_resolved"] == 1


# ============================================================================
# Test get_stats
# ============================================================================


class TestGetStats:
    """Test suite for get_stats method"""

    def test_get_stats_returns_copy(self):
        """Test get_stats returns a copy of stats"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        stats = resolver.get_stats()

        # Modify returned stats
        stats["conflicts_detected"] = 999

        # Original should be unchanged
        assert resolver.stats["conflicts_detected"] == 0

    def test_get_stats_structure(self):
        """Test get_stats returns all expected keys"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        stats = resolver.get_stats()

        assert "conflicts_detected" in stats
        assert "conflicts_resolved" in stats
        assert "timestamp_resolutions" in stats
        assert "semantic_resolutions" in stats

    def test_get_stats_after_operations(self):
        """Test get_stats reflects operations"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.9, "metadata": {}}],
            "tax_updates": [{"score": 0.7, "metadata": {}}],
        }

        # Detect and resolve
        conflicts = resolver.detect_conflicts(results)
        resolver.resolve_conflicts(results, conflicts)

        stats = resolver.get_stats()

        assert stats["conflicts_detected"] == 1
        assert stats["conflicts_resolved"] == 1
        assert stats["timestamp_resolutions"] == 1


# ============================================================================
# Test edge cases
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases"""

    def test_multiple_conflicts_in_same_resolution(self):
        """Test resolving multiple conflicts at once"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.85, "metadata": {}}],
            "legal_architect": [{"score": 0.75, "metadata": {}}],
            "legal_updates": [{"score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) >= 2
        assert resolver.stats["conflicts_detected"] >= 2

        resolved, reports = resolver.resolve_conflicts(results, conflicts)

        assert len(reports) >= 2
        assert resolver.stats["conflicts_resolved"] >= 2

    def test_tax_genius_conflict_pair(self):
        """Test tax_genius vs tax_updates conflict pair"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_genius": [{"score": 0.85, "metadata": {}}],
            "tax_updates": [{"score": 0.9, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert len(conflicts) == 1
        assert "tax_genius" in conflicts[0]["collections"]

    def test_conflict_detected_at_timestamp(self):
        """Test conflict has detected_at timestamp"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.85, "metadata": {}}],
        }

        conflicts = resolver.detect_conflicts(results)

        assert "detected_at" in conflicts[0]
        # Should be ISO format
        assert "T" in conflicts[0]["detected_at"]

    def test_conflict_report_includes_original(self):
        """Test conflict report includes original conflict info"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()
        results = {
            "tax_knowledge": [{"score": 0.8, "metadata": {}}],
            "tax_updates": [{"score": 0.85, "metadata": {}}],
        }
        conflicts = resolver.detect_conflicts(results)

        _, reports = resolver.resolve_conflicts(results, conflicts)

        # Report should contain original conflict fields
        assert "collections" in reports[0]
        assert "type" in reports[0]
        assert "resolution" in reports[0]
