"""
Unit tests for ComplianceTrackerService
Target: 100% coverage
Composer: 5
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.compliance.compliance_tracker import ComplianceItem, ComplianceTrackerService


@pytest.fixture
def compliance_tracker():
    """Create ComplianceTrackerService instance"""
    return ComplianceTrackerService()


class TestComplianceTrackerService:
    """Tests for ComplianceTrackerService"""

    def test_init(self, compliance_tracker):
        """Test initialization"""
        assert compliance_tracker.compliance_items == {}
        assert compliance_tracker.tracker_stats["total_items_tracked"] == 0

    def test_add_compliance_item(self, compliance_tracker):
        """Test adding compliance item"""
        item = compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
            description="Renew visa before expiration",
        )
        assert item.client_id == "client1"
        assert item.compliance_type == "visa_renewal"
        assert item.item_id in compliance_tracker.compliance_items

    def test_add_compliance_item_with_cost(self, compliance_tracker):
        """Test adding compliance item with estimated cost"""
        item = compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
            estimated_cost=5000000.0,
        )
        assert item.estimated_cost == 5000000.0

    def test_add_compliance_item_with_documents(self, compliance_tracker):
        """Test adding compliance item with required documents"""
        item = compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
            required_documents=["passport", "visa"],
        )
        assert len(item.required_documents) == 2

    def test_get_compliance_items(self, compliance_tracker):
        """Test getting compliance items"""
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        items = compliance_tracker.get_all_items(client_id="client1")
        assert len(items) == 1
        assert items[0].client_id == "client1"

    def test_get_compliance_items_empty(self, compliance_tracker):
        """Test getting compliance items for client with none"""
        items = compliance_tracker.get_all_items(client_id="nonexistent")
        assert len(items) == 0

    def test_get_all_items(self, compliance_tracker):
        """Test getting all compliance items"""
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        compliance_tracker.add_compliance_item(
            client_id="client2",
            compliance_type="tax_filing",
            title="Tax Filing",
            deadline="2025-12-31",
        )
        all_items = compliance_tracker.get_all_items()
        assert len(all_items) == 2

    def test_get_stats(self, compliance_tracker):
        """Test getting tracker statistics"""
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        stats = compliance_tracker.get_stats()
        assert stats["total_items_tracked"] == 1
        assert stats["active_items"] == 1

    def test_update_stats(self, compliance_tracker):
        """Test stats update on item addition"""
        initial_total = compliance_tracker.tracker_stats["total_items_tracked"]
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        assert compliance_tracker.tracker_stats["total_items_tracked"] == initial_total + 1
        assert compliance_tracker.tracker_stats["compliance_type_distribution"]["visa_renewal"] == 1

    def test_get_compliance_item(self, compliance_tracker):
        """Test getting compliance item by ID"""
        item = compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        retrieved = compliance_tracker.get_compliance_item(item.item_id)
        assert retrieved == item

    def test_get_compliance_item_not_found(self, compliance_tracker):
        """Test getting non-existent compliance item"""
        result = compliance_tracker.get_compliance_item("nonexistent")
        assert result is None

    def test_get_upcoming_deadlines(self, compliance_tracker):
        """Test getting upcoming deadlines"""
        from datetime import timedelta

        # Add item with deadline in 30 days
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline=future_date,
        )

        upcoming = compliance_tracker.get_upcoming_deadlines(days_ahead=90)
        assert len(upcoming) > 0

    def test_get_upcoming_deadlines_filtered_by_client(self, compliance_tracker):
        """Test getting upcoming deadlines filtered by client"""
        from datetime import timedelta

        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline=future_date,
        )
        compliance_tracker.add_compliance_item(
            client_id="client2",
            compliance_type="tax_filing",
            title="Tax Filing",
            deadline=future_date,
        )

        upcoming = compliance_tracker.get_upcoming_deadlines(client_id="client1", days_ahead=90)
        assert all(item.client_id == "client1" for item in upcoming)

    def test_resolve_compliance_item(self, compliance_tracker):
        """Test resolving compliance item"""
        item = compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        initial_active = compliance_tracker.tracker_stats["active_items"]

        result = compliance_tracker.resolve_compliance_item(item.item_id)
        assert result is True
        assert compliance_tracker.tracker_stats["active_items"] == initial_active - 1
        assert item.item_id not in compliance_tracker.compliance_items

    def test_resolve_compliance_item_not_found(self, compliance_tracker):
        """Test resolving non-existent compliance item"""
        result = compliance_tracker.resolve_compliance_item("nonexistent")
        assert result is False

    def test_get_all_items_with_client_filter(self, compliance_tracker):
        """Test getting all items filtered by client"""
        compliance_tracker.add_compliance_item(
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            deadline="2025-12-31",
        )
        compliance_tracker.add_compliance_item(
            client_id="client2",
            compliance_type="tax_filing",
            title="Tax Filing",
            deadline="2025-12-31",
        )

        client1_items = compliance_tracker.get_all_items(client_id="client1")
        assert len(client1_items) == 1
        assert all(item.client_id == "client1" for item in client1_items)


class TestComplianceItem:
    """Tests for ComplianceItem dataclass"""

    def test_compliance_item_creation(self):
        """Test creating compliance item"""
        item = ComplianceItem(
            item_id="item1",
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            description="Renew visa",
            deadline="2025-12-31",
            requirement_details="Details",
        )
        assert item.item_id == "item1"
        assert item.client_id == "client1"
        assert item.compliance_type == "visa_renewal"

    def test_compliance_item_with_metadata(self):
        """Test compliance item with metadata"""
        item = ComplianceItem(
            item_id="item1",
            client_id="client1",
            compliance_type="visa_renewal",
            title="Visa Renewal",
            description="Renew visa",
            deadline="2025-12-31",
            requirement_details="Details",
            metadata={"priority": "high"},
        )
        assert item.metadata["priority"] == "high"
