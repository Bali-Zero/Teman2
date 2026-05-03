"""GA4Sensor tests — all network paths mocked. No live calls."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors.ga4_sensor import GA4Sensor, _GA4Error


def _fake_response(n_pages: int) -> dict:
    """Mirror the shape of Analytics Data API v1beta runReport response."""
    rows = []
    for i in range(n_pages):
        rows.append(
            {
                "dimensionValues": [{"value": f"/page_{i}"}],
                "metricValues": [
                    {"value": str((i + 1) * 10)},    # sessions
                    {"value": str(i)},               # conversions
                ],
            }
        )
    return {"rows": rows}


@pytest.mark.asyncio
async def test_missing_credentials_returns_yellow(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        tmp_path / "does-not-exist.json",
    )
    reading = await GA4Sensor().read()
    assert isinstance(reading, SensorReading)
    assert reading.status == "yellow"
    assert reading.metadata["error_code"] == "credentials_missing"
    assert reading.value["page_count"] == 0


@pytest.mark.asyncio
async def test_happy_path_aggregates_and_green(tmp_path, monkeypatch):
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GA4Sensor(property_id="fake-123")
    with patch.object(sensor, "_fetch_report_blocking", return_value=_fake_response(60)):
        reading = await sensor.read()

    assert reading.status == "green"
    assert reading.value["page_count"] == 60
    # sessions = sum((i+1)*10 for i in 0..59) = 10*sum(1..60) = 10*1830 = 18300
    assert reading.value["sessions_total"] == 18300
    # conversions = sum(0..59) = 1770
    assert reading.value["conversions_total"] == 1770
    # sessions_by_page retained only top-50
    assert len(reading.value["sessions_by_page"]) == 50
    assert len(reading.value["conversions_by_page"]) == 50
    # Property ID propagated to metadata
    assert reading.metadata["property_id"] == "fake-123"


@pytest.mark.asyncio
async def test_low_page_count_returns_yellow(tmp_path, monkeypatch):
    """Below 5 distinct pages → yellow (signal too thin)."""
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GA4Sensor()
    with patch.object(sensor, "_fetch_report_blocking", return_value=_fake_response(3)):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["page_count"] == 3


@pytest.mark.asyncio
async def test_http_error_returns_red(tmp_path, monkeypatch):
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GA4Sensor()
    with patch.object(
        sensor,
        "_fetch_report_blocking",
        side_effect=_GA4Error("http_error", "GA4 API 403: Forbidden"),
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "http_error"


@pytest.mark.asyncio
async def test_unexpected_exception_returns_red(tmp_path, monkeypatch):
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GA4Sensor()
    with patch.object(
        sensor, "_fetch_report_blocking", side_effect=RuntimeError("bang")
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "unexpected"


@pytest.mark.asyncio
async def test_empty_rows_returns_yellow(tmp_path, monkeypatch):
    fake_creds = tmp_path / "creds.json"
    fake_creds.write_text("{}")
    monkeypatch.setattr(
        "apps.evaluator.seo_cell.sensors.ga4_sensor.GOOGLE_CREDENTIALS_PATH",
        fake_creds,
    )
    sensor = GA4Sensor()
    with patch.object(sensor, "_fetch_report_blocking", return_value={"rows": []}):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["page_count"] == 0
    assert reading.value["sessions_by_page"] == {}


def test_property_id_from_env(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "env-prop-999")
    sensor = GA4Sensor()
    assert sensor._property_id == "env-prop-999"


def test_property_id_constructor_beats_env(monkeypatch):
    monkeypatch.setenv("GA4_PROPERTY_ID", "env-prop-999")
    sensor = GA4Sensor(property_id="explicit-7")
    assert sensor._property_id == "explicit-7"
