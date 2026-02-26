"""
Unit tests for IntelStagingService.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.intel.intel_staging_service import IntelStagingService


class TestIntelStagingService:
    """Test suite for IntelStagingService."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for staging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def service(self, temp_dir):
        """Create service instance with temp directory."""
        with patch("backend.services.intel.intel_staging_service.settings") as mock_settings:
            mock_settings.get_intel_staging_base_dir = str(temp_dir)
            service = IntelStagingService()
            service.base_staging_dir = temp_dir
            service.visa_staging_dir = temp_dir / "visa"
            service.news_staging_dir = temp_dir / "news"
            service.visa_staging_dir.mkdir(parents=True, exist_ok=True)
            service.news_staging_dir.mkdir(parents=True, exist_ok=True)
            yield service

    def test_get_staging_dir_visa(self, service):
        """Test getting visa staging directory."""
        dir_path = service.get_staging_dir("visa")
        assert "visa" in str(dir_path)

    def test_get_staging_dir_news(self, service):
        """Test getting news staging directory."""
        dir_path = service.get_staging_dir("news")
        assert "news" in str(dir_path)

    def test_generate_item_id(self, service):
        """Test item ID generation."""
        item_id = service.generate_item_id("visa", "Test Title", "https://example.com")
        assert item_id.startswith("visa_")
        assert len(item_id) > 10

    def test_save_and_load_staging_item(self, service):
        """Test saving and loading staging item."""
        item_id = "test_item_123"
        staging_data = {
            "item_id": item_id,
            "title": "Test Article",
            "content": "Test content",
            "source_url": "https://example.com",
        }

        # Save
        file_path = service.save_staging_item("visa", item_id, staging_data)
        assert file_path.exists()

        # Load
        loaded_data = service.load_staging_item("visa", item_id)
        assert loaded_data is not None
        assert loaded_data["title"] == "Test Article"
        assert loaded_data["item_id"] == item_id

    def test_load_nonexistent_item(self, service):
        """Test loading non-existent item returns None."""
        result = service.load_staging_item("visa", "nonexistent")
        assert result is None

    def test_check_duplicate_found(self, service):
        """Test duplicate detection when duplicate exists."""
        from datetime import datetime, timedelta

        item_id = "test_item_123"
        # Use recent date so it's within the default 7-day window
        recent_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        staging_data = {
            "item_id": item_id,
            "title": "Test Article",
            "source_url": "https://example.com/article",
            "detected_at": recent_date,
        }

        # Save first item
        service.save_staging_item("visa", item_id, staging_data)

        # Check for duplicate
        duplicate = service.check_duplicate("visa", "https://example.com/article")
        assert duplicate is not None
        assert duplicate["item_id"] == item_id

    def test_check_duplicate_not_found(self, service):
        """Test duplicate detection when no duplicate exists."""
        duplicate = service.check_duplicate("visa", "https://example.com/unique")
        assert duplicate is None

    def test_list_pending_items_empty(self, service):
        """Test listing pending items when none exist."""
        result = service.list_pending_items("all")
        assert result["count"] == 0
        assert result["items"] == []

    def test_list_pending_items_with_data(self, service):
        """Test listing pending items with data."""
        # Save some items
        service.save_staging_item(
            "visa",
            "visa_1",
            {
                "item_id": "visa_1",
                "title": "Visa Article",
                "source_url": "https://example.com/visa",
                "detected_at": "2026-01-13T00:00:00",
                "status": "pending",
            },
        )
        service.save_staging_item(
            "news",
            "news_1",
            {
                "item_id": "news_1",
                "title": "News Article",
                "source_url": "https://example.com/news",
                "detected_at": "2026-01-13T00:00:00",
                "status": "pending",
            },
        )

        # List all
        result = service.list_pending_items("all")
        assert result["count"] == 2

        # List visa only
        result = service.list_pending_items("visa")
        assert result["count"] == 1
        assert result["items"][0]["type"] == "visa"

    def test_archive_item(self, service):
        """Test archiving item."""
        item_id = "test_item_123"
        staging_data = {
            "item_id": item_id,
            "title": "Test Article",
            "source_url": "https://example.com",
        }

        # Save item
        service.save_staging_item("visa", item_id, staging_data)

        # Archive
        archive_path = service.archive_item("visa", item_id, "approved")
        assert archive_path.exists()
        assert "archived" in str(archive_path)
        assert "approved" in str(archive_path)

        # Original should be gone
        staging_dir = service.get_staging_dir("visa")
        original_file = staging_dir / f"{item_id}.json"
        assert not original_file.exists()

    def test_archive_nonexistent_item(self, service):
        """Test archiving non-existent item raises error."""
        with pytest.raises(FileNotFoundError):
            service.archive_item("visa", "nonexistent", "approved")

    @patch("backend.services.intel.intel_staging_service.intel_staging_queue_size")
    def test_update_staging_queue_metrics(self, mock_metrics, service):
        """Test updating staging queue metrics."""
        # Save some items
        service.save_staging_item(
            "visa",
            "visa_1",
            {"item_id": "visa_1", "title": "Test", "source_url": "https://example.com"},
        )

        service.update_staging_queue_metrics()

        # Verify metrics were called
        assert mock_metrics.labels.call_count >= 2  # Called for visa and news
