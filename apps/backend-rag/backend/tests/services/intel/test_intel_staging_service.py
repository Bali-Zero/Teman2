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


def test_list_pending_items_projects_tier_and_live_news_fields(tmp_path: Path) -> None:
    """GUILT (WR2 liveness rewire, break #3; red-team FIX1 2026-07-18):
    tier/published_at/relevance_score/category/live_news_score/liveness_tier/
    live_news_reasons must be projected in BOTH the staging-root branch AND
    the archived/approved branch — previously only
    id/type/title/status/detected_at/source/detection_type/content/cover_image
    were served, so live_news_score never reached the WR2 topic selector even
    when it WAS persisted in the staging JSON. live_news_reasons is
    load-bearing too: wr2_topic_selector.py reads it straight off the
    pending item (`top_item.get("live_news_reasons")`), not from a separate
    preview call — its earlier omission was a silent drop, not a deliberate
    payload-weight trim."""
    service = _service(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    service.save_staging_item(
        "visa",
        "visa-live",
        {
            "title": "Live update",
            "source_url": "https://example.com/live",
            "detected_at": now,
            "content": "content",
            "tier": "T1",
            "published_at": "2026-07-17T08:00:00Z",
            "relevance_score": 92,
            "category": "immigration",
            "live_news_score": 85,
            "liveness_tier": "breaking",
            "live_news_reasons": ["official announcement", "effective today"],
        },
    )

    archived_dir = tmp_path / "news" / "archived" / "approved"
    archived_dir.mkdir(parents=True)
    (archived_dir / "news-live.json").write_text(
        json.dumps(
            {
                "title": "Archived live update",
                "source_url": "https://example.com/archived-live",
                "detected_at": now,
                "content": "content",
                "tier": "T2",
                "published_at": "2026-07-16T08:00:00Z",
                "relevance_score": 77,
                "category": "tax",
                "live_news_score": 60,
                "liveness_tier": "developing",
                "live_news_reasons": ["price hike confirmed"],
            },
        ),
    )

    result = service.list_pending_items()

    items_by_id = {item["id"]: item for item in result["items"]}
    live = items_by_id["visa-live"]
    assert live["tier"] == "T1"
    assert live["published_at"] == "2026-07-17T08:00:00Z"
    assert live["relevance_score"] == 92
    assert live["category"] == "immigration"
    assert live["live_news_score"] == 85
    assert live["liveness_tier"] == "breaking"
    assert live["live_news_reasons"] == ["official announcement", "effective today"]

    archived = items_by_id["news-live"]
    assert archived["tier"] == "T2"
    assert archived["published_at"] == "2026-07-16T08:00:00Z"
    assert archived["relevance_score"] == 77
    assert archived["category"] == "tax"
    assert archived["live_news_score"] == 60
    assert archived["liveness_tier"] == "developing"
    assert archived["live_news_reasons"] == ["price hike confirmed"]


def test_list_pending_items_projects_enrichment_object(tmp_path: Path) -> None:
    """GUILT (WR2 enrichment passthrough, scar family #9): a non-empty
    `enrichment` persisted in staging JSON must be projected verbatim in
    BOTH the staging-root branch AND the archived/approved branch —
    wr2_topic_selector.py reads `top_item.get("enrichment")` straight off
    the pending item served by this method (via GET
    /api/intel/staging/pending), not from the raw JSON file directly, so
    omitting it here would silently drop it even after a correct write-side
    fix."""
    service = _service(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    enrichment_obj = {
        "the_facts": "Facts here.",
        "bali_zero_take": "Our take.",
        "thirty_second_brief": "Brief.",
        "faq": [{"q": "Q1", "a": "A1"}],
        "metadata": {"suggested_slug": "slug", "tags": ["tag1"]},
    }
    service.save_staging_item(
        "visa",
        "visa-enriched",
        {
            "title": "Enriched update",
            "source_url": "https://example.com/enriched",
            "detected_at": now,
            "content": "content",
            "enrichment": enrichment_obj,
        },
    )

    archived_dir = tmp_path / "news" / "archived" / "approved"
    archived_dir.mkdir(parents=True)
    (archived_dir / "news-enriched.json").write_text(
        json.dumps(
            {
                "title": "Archived enriched update",
                "source_url": "https://example.com/archived-enriched",
                "detected_at": now,
                "content": "content",
                "enrichment": enrichment_obj,
            },
        ),
    )

    result = service.list_pending_items()

    items_by_id = {item["id"]: item for item in result["items"]}
    assert items_by_id["visa-enriched"]["enrichment"] == enrichment_obj
    assert items_by_id["news-enriched"]["enrichment"] == enrichment_obj


def test_list_pending_items_defaults_enrichment_to_empty_dict_for_legacy_items(
    tmp_path: Path,
) -> None:
    """INNOCENCE: legacy staging JSON written before the enrichment
    passthrough fix has no `enrichment` key at all — projection must
    default to {} uniformly, never KeyError or bare None (mirrors the
    live_news_* trio's legacy-default contract)."""
    service = _service(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    service.save_staging_item(
        "news",
        "news-legacy-enrichment",
        {
            "title": "Legacy item",
            "source_url": "https://example.com/legacy",
            "detected_at": now,
            "content": "content",
        },
    )

    result = service.list_pending_items()

    legacy = next(
        item for item in result["items"] if item["id"] == "news-legacy-enrichment"
    )
    assert legacy["enrichment"] == {}


def test_list_pending_items_defaults_legacy_items_without_live_news_fields(
    tmp_path: Path,
) -> None:
    """INNOCENCE: legacy staging JSON written before the liveness rewire has
    no live_news_score/liveness_tier/live_news_reasons key at all —
    projection must default to 0/"evergreen"/[] uniformly, never KeyError or
    bare None."""
    service = _service(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    service.save_staging_item(
        "news",
        "news-legacy",
        {
            "title": "Legacy item",
            "source_url": "https://example.com/legacy",
            "detected_at": now,
            "content": "content",
        },
    )

    result = service.list_pending_items()

    legacy = next(item for item in result["items"] if item["id"] == "news-legacy")
    assert legacy["live_news_score"] == 0
    assert legacy["liveness_tier"] == "evergreen"
    assert legacy["live_news_reasons"] == []
    assert legacy["tier"] is None
    assert legacy["published_at"] is None
    assert legacy["relevance_score"] is None
    assert legacy["category"] is None


def test_list_pending_items_normalizes_garbage_and_null_live_news_fields(
    tmp_path: Path,
) -> None:
    """GUILT (red-team FIX2, 2026-07-18): a raw staging file with a
    non-numeric score, an unknown tier string, and a non-list reasons value
    — OR with EXPLICIT JSON null for all three (bypasses `dict.get(key,
    default)` because the key IS present; the default only applies when the
    key is missing) — must project cleanly to 0/"evergreen"/[] rather than
    raising or leaking garbage into wr2_topic_selector's
    `int(i.get("live_news_score") or 0)` hard filter (unguarded by
    try/except there)."""
    service = _service(tmp_path)
    now = datetime.now(timezone.utc).isoformat()

    service.save_staging_item(
        "news",
        "news-garbage",
        {
            "title": "Garbage fields",
            "source_url": "https://example.com/garbage",
            "detected_at": now,
            "content": "content",
            "live_news_score": "abc",
            "liveness_tier": "hot",
            "live_news_reasons": "not-a-list",
        },
    )
    service.save_staging_item(
        "news",
        "news-null",
        {
            "title": "Explicit nulls",
            "source_url": "https://example.com/null",
            "detected_at": now,
            "content": "content",
            "live_news_score": None,
            "liveness_tier": None,
            "live_news_reasons": None,
        },
    )

    result = service.list_pending_items()  # must not raise

    items_by_id = {item["id"]: item for item in result["items"]}
    for item_id in ("news-garbage", "news-null"):
        item = items_by_id[item_id]
        assert item["live_news_score"] == 0
        assert item["liveness_tier"] == "evergreen"
        assert item["live_news_reasons"] == []


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
    from backend.app.metrics import intel_staging_queue_size

    service = _service(tmp_path)
    service.save_staging_item("visa", "visa-1", {"title": "Visa"})
    service.save_staging_item("news", "news-1", {"title": "News"})

    service.update_staging_queue_metrics()

    assert intel_staging_queue_size.labels(intel_type="visa")._value.get() == 1
    assert intel_staging_queue_size.labels(intel_type="news")._value.get() == 1
