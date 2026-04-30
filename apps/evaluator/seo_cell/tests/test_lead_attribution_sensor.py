"""LeadAttributionSensor tests — all DB paths mocked.

Sprint 2 sensor that closes the A3 anomaly: the thinker previously
hardcoded `lead_count = 0`, permanently locking the pre_natal gate.
This sensor reads `clients.referrer_url` (migration 118) and counts
leads whose first-touch came from a known organic search domain.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors.lead_attribution_sensor import (
    LeadAttributionSensor,
    _is_organic_referrer,
    _domain_of,
)


def _fake_rows(referrers: list[str]) -> list[dict]:
    """Build rows that match the SELECT shape in _fetch_leads."""
    now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    return [
        {
            "referrer_url": ref,
            "landing_page": f"/visa/post-{i}",
            "first_touch_at": now,
        }
        for i, ref in enumerate(referrers)
    ]


@pytest.mark.asyncio
async def test_missing_db_url_returns_yellow(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reading = await LeadAttributionSensor().read()
    assert isinstance(reading, SensorReading)
    assert reading.status == "yellow"
    assert reading.metadata["error_code"] == "db_url_missing"
    assert reading.value["lead_count"] == 0


@pytest.mark.asyncio
async def test_happy_path_counts_only_organic():
    sensor = LeadAttributionSensor(db_url="postgres://fake")
    rows = _fake_rows([
        "https://www.google.com/search?q=bali+visa",     # organic ✓
        "https://duckduckgo.com/",                        # organic ✓
        "https://bing.com/?q=kbli",                       # organic ✓
        "https://facebook.com/balizero",                  # social ✗
        "https://t.co/xyz",                               # social ✗
        "https://kita.balizero.com/login",                # internal ✗
        "https://random-blog.com/article",                # unknown ✗
    ])
    with patch.object(sensor, "_fetch_leads", return_value=rows):
        reading = await sensor.read()
    assert reading.status == "green"
    assert reading.value["lead_count"] == 3
    assert reading.metadata["scanned_rows"] == 7


@pytest.mark.asyncio
async def test_empty_window_returns_yellow():
    sensor = LeadAttributionSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_leads", return_value=[]):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["lead_count"] == 0


@pytest.mark.asyncio
async def test_only_non_organic_returns_yellow():
    """All referers are social/internal — gate must NOT advance."""
    sensor = LeadAttributionSensor(db_url="postgres://fake")
    rows = _fake_rows([
        "https://instagram.com/balizero",
        "https://wa.me/628123456",
        "https://balizero.com/about",
    ])
    with patch.object(sensor, "_fetch_leads", return_value=rows):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["lead_count"] == 0


@pytest.mark.asyncio
async def test_db_error_returns_red():
    sensor = LeadAttributionSensor(db_url="postgres://fake")

    async def _boom(*_a, **_k):  # noqa: ANN001
        from apps.evaluator.seo_cell.sensors.lead_attribution_sensor import (
            _LeadAttributionError,
        )
        raise _LeadAttributionError("db_error", "connect failed: gaierror(8)")

    with patch.object(sensor, "_fetch_leads", side_effect=_boom):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "db_error"
    assert reading.value["lead_count"] == 0


@pytest.mark.asyncio
async def test_unexpected_exception_returns_red():
    sensor = LeadAttributionSensor(db_url="postgres://fake")

    async def _boom(*_a, **_k):  # noqa: ANN001
        raise RuntimeError("kaboom")

    with patch.object(sensor, "_fetch_leads", side_effect=_boom):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "unexpected"


@pytest.mark.asyncio
async def test_aggregates_by_landing_page():
    sensor = LeadAttributionSensor(db_url="postgres://fake")
    now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    rows = [
        {"referrer_url": "https://google.com/search?q=visa",
         "landing_page": "/visa", "first_touch_at": now},
        {"referrer_url": "https://google.com/search?q=visa+kitas",
         "landing_page": "/visa", "first_touch_at": now},
        {"referrer_url": "https://google.com/search?q=kbli",
         "landing_page": "/kbli", "first_touch_at": now},
    ]
    with patch.object(sensor, "_fetch_leads", return_value=rows):
        reading = await sensor.read()
    assert reading.value["by_landing_page"] == {"/visa": 2, "/kbli": 1}


@pytest.mark.asyncio
async def test_recent_leads_top_n_capped():
    sensor = LeadAttributionSensor(db_url="postgres://fake")
    rows = _fake_rows(["https://google.com/search"] * 100)
    with patch.object(sensor, "_fetch_leads", return_value=rows):
        reading = await sensor.read()
    assert reading.value["lead_count"] == 100
    assert len(reading.value["recent_leads"]) == 50  # _TOP_N_KEEP


@pytest.mark.asyncio
async def test_null_referrer_treated_as_non_organic():
    """SQL filter excludes NULL referrer_url, but defensive: helper too."""
    sensor = LeadAttributionSensor(db_url="postgres://fake")
    rows = [
        {"referrer_url": None, "landing_page": "/", "first_touch_at": None},
        {"referrer_url": "https://google.com/", "landing_page": "/visa",
         "first_touch_at": datetime(2026, 4, 1, tzinfo=timezone.utc)},
    ]
    with patch.object(sensor, "_fetch_leads", return_value=rows):
        reading = await sensor.read()
    assert reading.value["lead_count"] == 1


def test_is_organic_referrer_classifier():
    # Organic search engines
    assert _is_organic_referrer("https://www.google.com/search?q=visa") is True
    assert _is_organic_referrer("https://google.co.id/") is True
    assert _is_organic_referrer("https://duckduckgo.com/") is True
    # Social
    assert _is_organic_referrer("https://facebook.com/p/123") is False
    assert _is_organic_referrer("https://t.co/abc") is False
    # Internal
    assert _is_organic_referrer("https://balizero.com/about") is False
    assert _is_organic_referrer("https://kita.balizero.com/x") is False
    # Unknown / weird
    assert _is_organic_referrer(None) is False
    assert _is_organic_referrer("") is False
    assert _is_organic_referrer("not-a-url") is False
    assert _is_organic_referrer("https://random-blog.example/") is False


def test_domain_of_helper():
    assert _domain_of("https://www.google.com/x") == "www.google.com"
    assert _domain_of("https://X.COM/y") == "x.com"
    assert _domain_of(None) is None
    assert _domain_of("") is None
