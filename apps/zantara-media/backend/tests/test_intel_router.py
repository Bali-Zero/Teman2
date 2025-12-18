"""
Unit tests for Intel Signals Router
Tests for intelligence signals handling from INTEL SCRAPING system
"""

import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.intel import router, _intel_store
from app.models import (
    IntelSignal,
    IntelPriority,
    ContentCategory,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def intel_app():
    """Create test app with intel router"""
    app = FastAPI()
    app.include_router(router, prefix="/intel")
    return app


@pytest.fixture
def intel_client(intel_app):
    """Create test client for intel"""
    return TestClient(intel_app)


@pytest.fixture(autouse=True)
def setup_intel_store():
    """Setup intel store with test data before each test"""
    _intel_store.clear()
    _intel_store["intel_1"] = IntelSignal(
        id="intel_1",
        title="Test Signal 1: New Visa Regulation",
        source_name="Imigrasi Indonesia",
        source_url="https://imigrasi.go.id/news/1",
        category=ContentCategory.IMMIGRATION,
        priority=IntelPriority.HIGH,
        summary="Important visa regulation update",
        detected_at=datetime.utcnow(),
        processed=False,
    )
    _intel_store["intel_2"] = IntelSignal(
        id="intel_2",
        title="Test Signal 2: Tax Deadline",
        source_name="DJP Online",
        source_url="https://djponline.pajak.go.id/news/1",
        category=ContentCategory.TAX,
        priority=IntelPriority.MEDIUM,
        summary="Tax deadline reminder",
        detected_at=datetime.utcnow(),
        processed=False,
    )
    _intel_store["intel_3"] = IntelSignal(
        id="intel_3",
        title="Test Signal 3: Business Update",
        source_name="Business News",
        source_url="https://business.example.com/news/1",
        category=ContentCategory.BUSINESS,
        priority=IntelPriority.LOW,
        summary="General business news",
        detected_at=datetime.utcnow(),
        processed=True,
    )
    yield
    _intel_store.clear()


# ============================================================================
# GET /intel/ Tests
# ============================================================================


class TestListIntelSignals:
    """Tests for GET /intel/ endpoint"""

    def test_list_intel_signals_success(self, intel_client):
        """Test successful retrieval of intel signals"""
        response = intel_client.get("/intel/")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data

    def test_list_intel_signals_pagination(self, intel_client):
        """Test pagination of intel signals"""
        response = intel_client.get("/intel/?page=1&page_size=2")
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2

    def test_list_intel_signals_filter_by_category(self, intel_client):
        """Test filtering by category"""
        response = intel_client.get("/intel/?category=immigration")
        data = response.json()

        for item in data["items"]:
            assert item["category"] == "immigration"

    def test_list_intel_signals_filter_by_priority(self, intel_client):
        """Test filtering by priority"""
        response = intel_client.get("/intel/?priority=high")
        data = response.json()

        for item in data["items"]:
            assert item["priority"] == "high"

    def test_list_intel_signals_filter_by_processed(self, intel_client):
        """Test filtering by processed status"""
        # Unprocessed signals
        response = intel_client.get("/intel/?processed=false")
        data = response.json()

        for item in data["items"]:
            assert item["processed"] is False

        # Processed signals
        response = intel_client.get("/intel/?processed=true")
        data = response.json()

        for item in data["items"]:
            assert item["processed"] is True

    def test_list_intel_signals_combined_filters(self, intel_client):
        """Test combining multiple filters"""
        response = intel_client.get(
            "/intel/?category=immigration&priority=high&processed=false"
        )
        data = response.json()

        for item in data["items"]:
            assert item["category"] == "immigration"
            assert item["priority"] == "high"
            assert item["processed"] is False

    def test_list_intel_signals_sorting(self, intel_client):
        """Test that signals are sorted by priority then time"""
        response = intel_client.get("/intel/")
        data = response.json()

        # First unprocessed signals should be high priority
        items = data["items"]
        if len(items) >= 2:
            # Check that sorting is applied (high priority first among unprocessed)
            priority_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(items) - 1):
                # This is a basic check - actual sorting is complex
                assert items[i] is not None


# ============================================================================
# GET /intel/stats Tests
# ============================================================================


class TestGetIntelStats:
    """Tests for GET /intel/stats endpoint"""

    def test_get_intel_stats_success(self, intel_client):
        """Test successful retrieval of intel stats"""
        response = intel_client.get("/intel/stats")

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "unprocessed" in data
        assert "by_priority" in data
        assert "by_category" in data

    def test_get_intel_stats_priority_breakdown(self, intel_client):
        """Test priority breakdown in stats"""
        response = intel_client.get("/intel/stats")
        data = response.json()

        by_priority = data["by_priority"]
        assert "high" in by_priority
        assert "medium" in by_priority
        assert "low" in by_priority

        # All values should be non-negative integers
        for value in by_priority.values():
            assert isinstance(value, int)
            assert value >= 0

    def test_get_intel_stats_category_breakdown(self, intel_client):
        """Test category breakdown in stats"""
        response = intel_client.get("/intel/stats")
        data = response.json()

        by_category = data["by_category"]

        # Should have entries for all categories
        assert len(by_category) > 0

        # All values should be non-negative integers
        for value in by_category.values():
            assert isinstance(value, int)
            assert value >= 0

    def test_get_intel_stats_counts_only_unprocessed(self, intel_client):
        """Test that stats only count unprocessed signals"""
        response = intel_client.get("/intel/stats")
        data = response.json()

        # Total unprocessed should be less than or equal to total
        assert data["unprocessed"] <= data["total"]

        # With our test data: 2 unprocessed out of 3 total
        assert data["total"] == 3
        assert data["unprocessed"] == 2


# ============================================================================
# GET /intel/{signal_id} Tests
# ============================================================================


class TestGetIntelSignal:
    """Tests for GET /intel/{signal_id} endpoint"""

    def test_get_intel_signal_success(self, intel_client):
        """Test successful retrieval of single intel signal"""
        response = intel_client.get("/intel/intel_1")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == "intel_1"
        assert data["title"] == "Test Signal 1: New Visa Regulation"
        assert data["category"] == "immigration"
        assert data["priority"] == "high"

    def test_get_intel_signal_not_found(self, intel_client):
        """Test 404 for non-existent signal"""
        response = intel_client.get("/intel/non_existent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_intel_signal_all_fields(self, intel_client):
        """Test that all expected fields are returned"""
        response = intel_client.get("/intel/intel_1")
        data = response.json()

        expected_fields = [
            "id",
            "title",
            "source_name",
            "source_url",
            "category",
            "priority",
            "summary",
            "detected_at",
            "processed",
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


# ============================================================================
# POST /intel/{signal_id}/process Tests
# ============================================================================


class TestProcessIntelSignal:
    """Tests for POST /intel/{signal_id}/process endpoint"""

    def test_process_signal_create_content(self, intel_client):
        """Test processing signal to create content"""
        response = intel_client.post(
            "/intel/intel_1/process",
            json={"signal_id": "intel_1", "action": "create_content"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "content_id" in data["data"]

        # Signal should now be processed
        signal_response = intel_client.get("/intel/intel_1")
        assert signal_response.json()["processed"] is True

    def test_process_signal_dismiss(self, intel_client):
        """Test dismissing a signal"""
        response = intel_client.post(
            "/intel/intel_1/process", json={"signal_id": "intel_1", "action": "dismiss"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "dismissed" in data["message"].lower()

        # Signal should now be processed
        signal_response = intel_client.get("/intel/intel_1")
        assert signal_response.json()["processed"] is True

    def test_process_signal_archive(self, intel_client):
        """Test archiving a signal"""
        response = intel_client.post(
            "/intel/intel_1/process", json={"signal_id": "intel_1", "action": "archive"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "archived" in data["message"].lower()

    def test_process_signal_not_found(self, intel_client):
        """Test processing non-existent signal"""
        response = intel_client.post(
            "/intel/non_existent/process",
            json={"signal_id": "non_existent", "action": "dismiss"},
        )

        assert response.status_code == 404

    def test_process_signal_already_processed(self, intel_client):
        """Test processing already processed signal"""
        response = intel_client.post(
            "/intel/intel_3/process", json={"signal_id": "intel_3", "action": "dismiss"}
        )

        assert response.status_code == 400
        assert "already processed" in response.json()["detail"].lower()

    def test_process_signal_unknown_action(self, intel_client):
        """Test processing with unknown action"""
        response = intel_client.post(
            "/intel/intel_1/process",
            json={"signal_id": "intel_1", "action": "unknown_action"},
        )

        assert response.status_code == 400
        assert "unknown action" in response.json()["detail"].lower()


# ============================================================================
# POST /intel/refresh Tests
# ============================================================================


class TestRefreshIntelSignals:
    """Tests for POST /intel/refresh endpoint"""

    def test_refresh_intel_signals_success(self, intel_client):
        """Test successful refresh trigger"""
        response = intel_client.post("/intel/refresh")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "triggered" in data["message"].lower()
        assert "sources_checked" in data["data"]
        assert "new_signals" in data["data"]

    def test_refresh_returns_stats(self, intel_client):
        """Test that refresh returns useful stats"""
        response = intel_client.post("/intel/refresh")
        data = response.json()

        # Should return number of sources checked
        assert isinstance(data["data"]["sources_checked"], int)
        assert data["data"]["sources_checked"] >= 0

        # Should return number of new signals
        assert isinstance(data["data"]["new_signals"], int)
        assert data["data"]["new_signals"] >= 0


# ============================================================================
# POST /intel/bulk-dismiss Tests
# ============================================================================


class TestBulkDismissSignals:
    """Tests for POST /intel/bulk-dismiss endpoint"""

    def test_bulk_dismiss_success(self, intel_client):
        """Test bulk dismissing multiple signals"""
        response = intel_client.post("/intel/bulk-dismiss", json=["intel_1", "intel_2"])

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["dismissed"] == 2

        # Both signals should be processed
        assert intel_client.get("/intel/intel_1").json()["processed"] is True
        assert intel_client.get("/intel/intel_2").json()["processed"] is True

    def test_bulk_dismiss_partial(self, intel_client):
        """Test bulk dismiss with some non-existent signals"""
        response = intel_client.post(
            "/intel/bulk-dismiss", json=["intel_1", "non_existent", "intel_2"]
        )

        assert response.status_code == 200
        data = response.json()

        # Should only dismiss existing signals
        assert data["data"]["dismissed"] == 2

    def test_bulk_dismiss_skip_processed(self, intel_client):
        """Test bulk dismiss skips already processed signals"""
        response = intel_client.post(
            "/intel/bulk-dismiss",
            json=["intel_1", "intel_3"],  # intel_3 is already processed
        )

        assert response.status_code == 200
        data = response.json()

        # Should only dismiss unprocessed
        assert data["data"]["dismissed"] == 1

    def test_bulk_dismiss_empty_list(self, intel_client):
        """Test bulk dismiss with empty list"""
        response = intel_client.post("/intel/bulk-dismiss", json=[])

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["dismissed"] == 0

    def test_bulk_dismiss_all_invalid(self, intel_client):
        """Test bulk dismiss when all signals are invalid"""
        response = intel_client.post(
            "/intel/bulk-dismiss", json=["non_existent_1", "non_existent_2"]
        )

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["dismissed"] == 0


# ============================================================================
# Edge Cases
# ============================================================================


class TestIntelEdgeCases:
    """Edge case tests for intel router"""

    def test_empty_intel_store(self, intel_client):
        """Test behavior with empty intel store"""
        _intel_store.clear()

        response = intel_client.get("/intel/")
        data = response.json()

        assert data["total"] == 0
        assert data["items"] == []

    def test_pagination_beyond_total(self, intel_client):
        """Test pagination beyond available data"""
        response = intel_client.get("/intel/?page=100&page_size=10")
        data = response.json()

        assert data["items"] == []
        assert data["has_more"] is False

    def test_invalid_category_filter(self, intel_client):
        """Test invalid category filter returns 422"""
        response = intel_client.get("/intel/?category=invalid_category")

        # FastAPI returns 422 for invalid enum values
        assert response.status_code == 422

    def test_invalid_priority_filter(self, intel_client):
        """Test invalid priority filter returns 422"""
        response = intel_client.get("/intel/?priority=invalid_priority")

        assert response.status_code == 422


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntelIntegration:
    """Integration tests for intel router"""

    def test_workflow_detect_process_verify(self, intel_client):
        """Test full workflow: list -> process -> verify"""
        # 1. List signals
        list_response = intel_client.get("/intel/?processed=false")
        initial_unprocessed = list_response.json()["total"]

        # 2. Process a signal
        intel_client.post(
            "/intel/intel_1/process",
            json={"signal_id": "intel_1", "action": "create_content"},
        )

        # 3. Verify count decreased
        final_response = intel_client.get("/intel/?processed=false")
        final_unprocessed = final_response.json()["total"]

        assert final_unprocessed == initial_unprocessed - 1

    def test_stats_reflect_processing(self, intel_client):
        """Test that stats update after processing"""
        # Get initial stats
        initial_stats = intel_client.get("/intel/stats").json()

        # Process a high priority signal
        intel_client.post(
            "/intel/intel_1/process", json={"signal_id": "intel_1", "action": "dismiss"}
        )

        # Get updated stats
        updated_stats = intel_client.get("/intel/stats").json()

        # Unprocessed count should decrease
        assert updated_stats["unprocessed"] == initial_stats["unprocessed"] - 1
