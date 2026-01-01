"""
Unit tests for AutoIngestionOrchestrator
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ingestion.auto_ingestion_orchestrator import (
    AutoIngestionOrchestrator,
    MonitoredSource,
    SourceType,
    UpdateType,
    IngestionStatus
)


@pytest.fixture
def auto_ingestion_orchestrator():
    """Create AutoIngestionOrchestrator instance"""
    return AutoIngestionOrchestrator()


class TestAutoIngestionOrchestrator:
    """Tests for AutoIngestionOrchestrator"""

    def test_init(self, auto_ingestion_orchestrator):
        """Test initialization"""
        assert auto_ingestion_orchestrator is not None
        assert isinstance(auto_ingestion_orchestrator.sources, dict)
        assert len(auto_ingestion_orchestrator.sources) > 0  # Default sources

    def test_add_source(self, auto_ingestion_orchestrator):
        """Test adding monitored source"""
        source = MonitoredSource(
            source_id="test_source",
            source_type=SourceType.GOVERNMENT_WEBSITE,
            name="Test Source",
            url="https://test.com",
            target_collection="visa_oracle"
        )
        auto_ingestion_orchestrator.add_source(source)
        assert "test_source" in auto_ingestion_orchestrator.sources

    def test_get_due_sources(self, auto_ingestion_orchestrator):
        """Test getting sources due for scraping"""
        sources = auto_ingestion_orchestrator.get_due_sources()
        assert isinstance(sources, list)

    def test_get_orchestrator_stats(self, auto_ingestion_orchestrator):
        """Test getting orchestrator statistics"""
        stats = auto_ingestion_orchestrator.get_orchestrator_stats()
        assert isinstance(stats, dict)
        assert "total_jobs" in stats

