"""
Unit tests for IntelClassificationService.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.intel.intel_classification_service import IntelClassificationService


class TestIntelClassificationService:
    """Test suite for IntelClassificationService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return IntelClassificationService()

    def test_classify_visa_by_category(self, service):
        """Test classification by visa category."""
        result = service.classify_intel_type("visa", "Test Title", "Test Content")
        assert result == "visa"

    def test_classify_visa_by_keywords(self, service):
        """Test classification by visa keywords."""
        result = service.classify_intel_type(
            "news", "KITAS Application Guide", "This article discusses visa and immigration requirements"
        )
        assert result == "visa"

    def test_classify_news_default(self, service):
        """Test default classification to news."""
        result = service.classify_intel_type("news", "Bali Weather", "Today's weather in Bali")
        assert result == "news"

    def test_classify_immigration_category(self, service):
        """Test immigration category classification."""
        result = service.classify_intel_type("immigration", "Test", "Content")
        assert result == "visa"

    @patch("backend.services.intel.intel_classification_service.intel_classification_duration")
    @patch("backend.services.intel.intel_classification_service.intel_classification_total")
    def test_metrics_tracking(self, mock_total, mock_duration, service):
        """Test that metrics are tracked correctly."""
        service.classify_intel_type("visa", "Test", "Content")
        
        # Verify metrics were called
        mock_duration.observe.assert_called_once()
        mock_total.labels.assert_called_once()
