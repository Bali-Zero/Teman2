import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.services.intel.intel_staging_service import IntelStagingService


def _service(tmp_path: Path) -> IntelStagingService:
    service = IntelStagingService.__new__(IntelStagingService)
    service.base_staging_dir = tmp_path
    service.visa_staging_dir = tmp_path / "visa"
    service.news_staging_dir = tmp_path / "news"
    service.visa_staging_dir.mkdir()
    service.news_staging_dir.mkdir()
    return service


def test_get_staging_dir_returns_type_specific_directory(tmp_path: Path) -> None:
    service = _service(tmp_path)

    assert service.get_staging_dir("visa") == tmp_path / "visa"
    assert service.get_staging_dir("news") == tmp_path / "news"


def test_generate_item_id_includes_type_timestamp_and_hash(tmp_path: Path) -> None:
    service = _service(tmp_path)

    item_id = service.generate_item_id(
        intel_type="visa",
        title="New KITAS rule",
        source_url="https://example.com/kitas",
    )

    assert re.fullmatch(r"visa_\d{8}_\d{6}_[0-9a-f]{8}", item_id)


def test_save_and_load_staging_item_round_trip_json(tmp_path: Path) -> None:
    service = _service(tmp_path)
    data = {
        "title": "Immigration update",
        "source_url": "https://example.com/news",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    path = service.save_staging_item("news", "news-1", data)

    assert path == tmp_path / "news" / "news-1.json"
    assert not (tmp_path / "news" / "news-1.json.tmp").exists()
    assert service.load_staging_item("news", "news-1") == data
    assert service.load_staging_item("news", "missing") is None


def test_check_duplicate_respects_recent_source_url(tmp_path: Path) -> None:
    service = _service(tmp_path)
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    old = datetime.now(timezone.utc) - timedelta(days=30)

    service.save_staging_item(
        "visa",
        "old",
        {
            "source_url": "https://example.com/old",
            "detected_at": old.isoformat(),
        },
    )
    expected = {
        "source_url": "https://example.com/current",
        "detected_at": recent.isoformat(),
        "title": "Current",
    }
    service.save_staging_item("visa", "current", expected)

    assert service.check_duplicate("visa", "https://example.com/current", days=7) == expected
    assert service.check_duplicate("visa", "https://example.com/old", days=7) is None


def test_list_pending_items_includes_archived_published_and_searches(tmp_path: Path) -> None:
    service = _service(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    service.save_staging_item(
        "visa",
        "visa-1",
        {
            "title": "Visa update",
            "source_url": "https://example.com/visa",
            "detected_at": now,
            "content": "KITAS",
        },
    )

    approved_dir = tmp_path / "news" / "archived" / "approved"
    approved_dir.mkdir(parents=True)
    (approved_dir / "published-1.json").write_text(
        json.dumps(
            {
                "title": "Published update",
                "source_url": "https://example.com/published",
                "detected_at": now,
                "content": "News",
            },
        ),
    )

    result = service.list_pending_items(
        intel_type="all",
        filter_type="pending",
        sort_type="date",
        search="visa",
    )

    assert result["count"] == 2
    statuses = {item["id"]: item["status"] for item in result["items"]}
    assert statuses["visa-1"] == "pending"
    assert statuses["published-1"] == "published"


def test_archive_item_moves_file_to_archive_bucket(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.save_staging_item("news", "news-1", {"title": "To approve"})

    archive_path = service.archive_item("news", "news-1", "approved")

    assert archive_path == tmp_path / "news" / "archived" / "approved" / "news-1.json"
    assert archive_path.exists()
    assert not (tmp_path / "news" / "news-1.json").exists()


def test_archive_item_raises_for_missing_item(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(FileNotFoundError):
        service.archive_item("visa", "missing", "rejected")


def test_update_staging_queue_metrics_does_not_require_real_services(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.save_staging_item("visa", "visa-1", {"title": "Visa"})
    service.save_staging_item("news", "news-1", {"title": "News"})

    service.update_staging_queue_metrics()
