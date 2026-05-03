"""GSCSensor tests — all network paths mocked. No live calls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors.gsc_sensor import GSCSensor, _GSCError


def _fake_rows(n: int) -> list[dict]:
    return [
        {
            "keys": [f"query_{i}"],
            "clicks": i,
            "impressions": i * 10,
            "ctr": 0.1,
            "position": 5.0,
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_missing_credentials_returns_yellow(tmp_path, monkeypatch):
    """If SA file is absent, sensor must return yellow + error metadata —
    never raise, never red (red is reserved for hard failures)."""
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        tmp_path / "does-not-exist.json",
    )
    reading = await GSCSensor().read()
    assert isinstance(reading, SensorReading)
    assert reading.status == "yellow"
    assert reading.metadata["error_code"] == "credentials_missing"
    assert reading.value["query_count"] == 0


@pytest.mark.asyncio
async def test_happy_path_aggregates_and_green(tmp_path, monkeypatch):
    """With 50 rows we expect green + aggregates + top_queries truncated
    to _TOP_N_KEEP (50)."""
    # Make the creds check pass by pointing at any existing file.
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )

    sensor = GSCSensor(window_days=28)
    with patch.object(
        sensor,
        "_fetch_rows_blocking",
        return_value=_fake_rows(120),
    ):
        reading = await sensor.read()

    assert reading.status == "green"
    assert reading.value["query_count"] == 120
    # clicks = 0+1+...+119 = 7140
    assert reading.value["clicks_total"] == sum(range(120))
    # impressions = each*10
    assert reading.value["impressions_total"] == sum(range(120)) * 10
    # top_queries capped at 50 and sorted by impressions desc
    tq = reading.value["top_queries"]
    assert len(tq) == 50
    assert tq[0]["impressions"] >= tq[-1]["impressions"]
    # Shape normalization: "keys: [query_N]" → "query: query_N"
    assert all("query" in row and "keys" not in row for row in tq)


@pytest.mark.asyncio
async def test_low_query_count_returns_yellow(tmp_path, monkeypatch):
    """Below 10 distinct queries → yellow (new site signal too thin)."""
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GSCSensor()
    with patch.object(sensor, "_fetch_rows_blocking", return_value=_fake_rows(5)):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["query_count"] == 5


@pytest.mark.asyncio
async def test_http_error_returns_red(tmp_path, monkeypatch):
    """GSC HttpError must surface as red — thinker treats red as
    'sensor unreliable; do not weight this signal'."""
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GSCSensor()
    with patch.object(
        sensor,
        "_fetch_rows_blocking",
        side_effect=_GSCError("http_error", "GSC API 403: Forbidden"),
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "http_error"
    assert "403" in reading.metadata["error"]


@pytest.mark.asyncio
async def test_unexpected_exception_returns_red(tmp_path, monkeypatch):
    """Sensor must swallow arbitrary exceptions — never raise to the
    PulseLoop, which would crash the pulse."""
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GSCSensor()
    with patch.object(
        sensor, "_fetch_rows_blocking", side_effect=RuntimeError("bang")
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "unexpected"


@pytest.mark.asyncio
async def test_empty_rows_returns_yellow_with_zero_counts(tmp_path, monkeypatch):
    """Valid API response with no rows — site is live but no queries yet."""
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.gsc_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GSCSensor()
    with patch.object(sensor, "_fetch_rows_blocking", return_value=[]):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["query_count"] == 0
    assert reading.value["top_queries"] == []
