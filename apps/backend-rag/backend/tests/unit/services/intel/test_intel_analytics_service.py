"""
Unit tests for IntelAnalyticsService.
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.intel.intel_analytics_service import IntelAnalyticsService
from backend.services.intel.intel_staging_service import IntelStagingService


class TestIntelAnalyticsService:
    """Test suite for IntelAnalyticsService."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for staging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def staging_service(self, temp_dir):
        """Create staging service with temp directory."""
        with patch("backend.services.intel.intel_staging_service.settings") as mock_settings:
            mock_settings.get_intel_staging_base_dir = str(temp_dir)
            service = IntelStagingService()
            service.base_staging_dir = temp_dir
            service.visa_staging_dir = temp_dir / "visa"
            service.news_staging_dir = temp_dir / "news"
            service.visa_staging_dir.mkdir(parents=True, exist_ok=True)
            service.news_staging_dir.mkdir(parents=True, exist_ok=True)
            yield service

    @pytest.fixture
    def analytics_service(self, staging_service):
        """Create analytics service."""
        return IntelAnalyticsService(staging_service)

    def test_get_intelligence_analytics_empty(self, analytics_service):
        """Test analytics with no data."""
        result = analytics_service.get_intelligence_analytics(days=7)

        assert result["period_days"] == 7
        assert result["summary"]["total_processed"] == 0
        assert result["summary"]["total_approved"] == 0
        assert result["summary"]["total_rejected"] == 0
        assert len(result["daily_trends"]) == 7

    def test_get_intelligence_analytics_with_approved_items(
        self, analytics_service, staging_service
    ):
        """Test analytics with approved items."""
        # Create archived/approved directory
        approved_dir = staging_service.visa_staging_dir / "archived" / "approved"
        approved_dir.mkdir(parents=True, exist_ok=True)

        # Create approved item file
        item_data = {
            "item_id": "visa_1",
            "title": "Test Article",
            "ingested_at": datetime.now().isoformat(),
        }
        item_file = approved_dir / "visa_1.json"
        item_file.write_text(json.dumps(item_data))

        result = analytics_service.get_intelligence_analytics(days=7)

        assert result["summary"]["total_approved"] == 1
        assert result["summary"]["total_processed"] == 1
        assert result["type_breakdown"]["visa"]["approved"] == 1

    def test_get_intelligence_analytics_with_rejected_items(
        self, analytics_service, staging_service
    ):
        """Test analytics with rejected items."""
        # Create archived/rejected directory
        rejected_dir = staging_service.visa_staging_dir / "archived" / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)

        # Create rejected item file
        item_data = {
            "item_id": "visa_1",
            "title": "Test Article",
            "rejected_at": datetime.now().isoformat(),
        }
        item_file = rejected_dir / "visa_1.json"
        item_file.write_text(json.dumps(item_data))

        result = analytics_service.get_intelligence_analytics(days=7)

        assert result["summary"]["total_rejected"] == 1
        assert result["summary"]["total_processed"] == 1
        assert result["type_breakdown"]["visa"]["rejected"] == 1

    def test_get_intelligence_analytics_approval_rate(self, analytics_service, staging_service):
        """Test approval rate calculation."""
        # Create approved items
        approved_dir = staging_service.visa_staging_dir / "archived" / "approved"
        approved_dir.mkdir(parents=True, exist_ok=True)

        for i in range(3):
            item_data = {
                "item_id": f"visa_{i}",
                "ingested_at": datetime.now().isoformat(),
            }
            (approved_dir / f"visa_{i}.json").write_text(json.dumps(item_data))

        # Create rejected items
        rejected_dir = staging_service.visa_staging_dir / "archived" / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)

        item_data = {
            "item_id": "visa_rejected",
            "rejected_at": datetime.now().isoformat(),
        }
        (rejected_dir / "visa_rejected.json").write_text(json.dumps(item_data))

        result = analytics_service.get_intelligence_analytics(days=7)

        assert result["summary"]["total_processed"] == 4
        assert result["summary"]["total_approved"] == 3
        assert result["summary"]["total_rejected"] == 1
        assert result["summary"]["approval_rate"] == 75.0
        assert result["summary"]["rejection_rate"] == 25.0

    def test_daily_trends_generation(self, analytics_service):
        """Test daily trends generation."""
        result = analytics_service.get_intelligence_analytics(days=7)

        assert len(result["daily_trends"]) == 7
        for trend in result["daily_trends"]:
            assert "date" in trend
            assert "processed" in trend
            assert "approved" in trend
            assert "rejected" in trend

    @patch("backend.services.intel.intel_analytics_service.intel_analytics_queries_total")
    def test_metrics_tracking(self, mock_metrics, analytics_service):
        """Test that metrics are tracked."""
        analytics_service.get_intelligence_analytics(days=7)

        mock_metrics.labels.assert_called_once()
