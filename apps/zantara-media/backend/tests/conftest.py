"""
ZANTARA MEDIA - Test Configuration
Shared fixtures and configuration for pytest
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add app to path
app_path = Path(__file__).parent.parent / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))


# ============================================================================
# App Fixture
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application"""
    from app.main import app as main_app

    return main_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client"""
    return TestClient(app)


# ============================================================================
# Mock Data Fixtures
# ============================================================================


@pytest.fixture
def mock_dashboard_stats():
    """Mock dashboard statistics"""
    return {
        "today": {
            "published": 8,
            "scheduled": 12,
            "in_review": 3,
            "intel_signals": 12,
            "engagements": 15420,
        },
        "week": {
            "total_published": 34,
            "total_engagements": 89500,
            "new_leads": 156,
            "avg_engagement_rate": 4.2,
        },
        "platforms": [
            {"platform": "twitter", "posts": 12, "engagements": 4500, "growth": 2.3},
            {"platform": "linkedin", "posts": 8, "engagements": 3200, "growth": 5.1},
        ],
    }


@pytest.fixture
def mock_intel_signal():
    """Mock intel signal data"""
    from app.models import ContentCategory, IntelPriority, IntelSignal

    return IntelSignal(
        id="intel_test_1",
        title="Test Signal: New Visa Regulation",
        source_name="Test Source",
        source_url="https://test.example.com/news/1",
        category=ContentCategory.IMMIGRATION,
        priority=IntelPriority.HIGH,
        summary="Test summary for the signal",
        detected_at=datetime.utcnow(),
        processed=False,
    )


@pytest.fixture
def mock_distribution():
    """Mock distribution data"""
    from app.models import Distribution, DistributionPlatform, DistributionStatus

    return Distribution(
        id="dist_test_1",
        content_id="content_1",
        platform=DistributionPlatform.TWITTER,
        status=DistributionStatus.PENDING,
        scheduled_at=None,
        published_at=None,
    )


# ============================================================================
# Database Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg database pool"""
    pool = MagicMock()
    pool.acquire = MagicMock()
    pool.close = AsyncMock()

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 1")
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)

    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    return pool


@pytest.fixture
def mock_content_repository(mock_db_pool):
    """Mock content repository"""
    repo = MagicMock()
    repo.get_all = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


# ============================================================================
# Service Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_scheduler_service():
    """Mock scheduler service"""
    from app.services.scheduler import SchedulerService

    service = MagicMock(spec=SchedulerService)
    service.is_running = False
    service.start = AsyncMock()
    service.stop = AsyncMock()
    service.trigger_manual_run = AsyncMock(
        return_value={"success": True, "stats": {"articles_generated": 5}}
    )
    service.get_status = MagicMock(
        return_value={
            "running": True,
            "jobs": [
                {
                    "id": "daily_content_generation",
                    "name": "Daily Content Generation Pipeline",
                    "next_run": "2025-01-11T06:00:00+08:00",
                    "trigger": "cron[hour='6', minute='0']",
                }
            ],
        }
    )
    return service


@pytest.fixture
def mock_distributor_service():
    """Mock distributor service"""
    from app.services.distributor import DistributorService

    service = MagicMock(spec=DistributorService)
    service.create_distribution = AsyncMock()
    service.publish = AsyncMock()
    service.get_pending_queue = AsyncMock(return_value=[])
    service.get_scheduled = AsyncMock(return_value=[])
    service.cancel_distribution = AsyncMock(return_value=True)
    service.get_metrics = AsyncMock()
    return service


# ============================================================================
# Cleanup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_stores():
    """Reset in-memory stores before each test"""
    # Import and clear stores
    from app.routers import distribution, intel

    distribution._distribution_store.clear()
    # Reset intel store to default mock data
    intel._intel_store.clear()
    yield
    # Clean up after test
    distribution._distribution_store.clear()
    intel._intel_store.clear()
