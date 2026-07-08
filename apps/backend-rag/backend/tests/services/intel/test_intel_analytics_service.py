import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.services.intel.intel_analytics_service import IntelAnalyticsService


class FakeStagingService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def get_staging_dir(self, intel_type: str) -> Path:
        return self.base_dir / intel_type


def _write_json(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_get_intelligence_analytics_counts_recent_archived_items(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=30)
    service = IntelAnalyticsService(FakeStagingService(tmp_path))  # type: ignore[arg-type]

    _write_json(
        tmp_path / "visa" / "archived" / "approved" / "visa-approved.json",
        {"ingested_at": now.isoformat()},
    )
    _write_json(
        tmp_path / "visa" / "archived" / "rejected" / "visa-rejected.json",
        {"rejected_at": now.isoformat()},
    )
    _write_json(
        tmp_path / "news" / "archived" / "approved" / "news-approved-old.json",
        {"ingested_at": old.isoformat()},
    )
    _write_json(
        tmp_path / "news" / "archived" / "published" / "news-published.json",
        {"published_at": now.isoformat()},
    )

    analytics = service.get_intelligence_analytics(days=7)

    assert analytics["period_days"] == 7
    assert analytics["summary"]["total_processed"] == 2
    assert analytics["summary"]["total_approved"] == 1
    assert analytics["summary"]["total_rejected"] == 1
    assert analytics["summary"]["total_published"] == 1
    assert analytics["summary"]["approval_rate"] == 50.0
    assert analytics["summary"]["rejection_rate"] == 50.0
    assert analytics["type_breakdown"]["visa"] == {
        "processed": 2,
        "approved": 1,
        "rejected": 1,
    }
    assert len(analytics["daily_trends"]) == 7
    assert analytics["daily_trends"][-1]["processed"] == 2
    assert analytics["daily_trends"][-1]["published"] == 1


def test_get_intelligence_analytics_handles_empty_archive(tmp_path: Path) -> None:
    service = IntelAnalyticsService(FakeStagingService(tmp_path))  # type: ignore[arg-type]

    analytics = service.get_intelligence_analytics(days=3)

    assert analytics["summary"]["total_processed"] == 0
    assert analytics["summary"]["approval_rate"] == 0.0
    assert analytics["daily_trends"] == [
        {
            "date": analytics["daily_trends"][0]["date"],
            "processed": 0,
            "approved": 0,
            "rejected": 0,
            "published": 0,
        },
        {
            "date": analytics["daily_trends"][1]["date"],
            "processed": 0,
            "approved": 0,
            "rejected": 0,
            "published": 0,
        },
        {
            "date": analytics["daily_trends"][2]["date"],
            "processed": 0,
            "approved": 0,
            "rejected": 0,
            "published": 0,
        },
    ]
