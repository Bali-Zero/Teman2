"""Sprint 1.B 2026-05-02: ChannelSensor.bridge_channels_to_sidecar() emits one
sidecar per channel after HTTP poll.

Spec ref: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
"""
from unittest.mock import patch

import pytest

from cell.sensors.channel_sensor import ChannelSensor


@pytest.mark.asyncio
async def test_bridge_emits_sidecar_per_channel():
    """4 channels polled → 4 sidecars emitted with mapped status."""
    sensor = ChannelSensor()

    fake_responses = {
        "whatsapp": {"status": "ok", "queue_depth": 5, "last_event_seen_at": 12345.0},
        "telegram": {"status": "ok", "queue_depth": 0, "last_event_seen_at": None},
        "instagram": {"status": "ok", "queue_depth": 1, "last_event_seen_at": 67890.0},
        "web": {"status": "degraded", "queue_depth": 50, "last_event_seen_at": 11111.0},
    }

    async def fake_http_get(url):
        for name, body in fake_responses.items():
            if f"/{name}/health" in url:
                return body
        raise AssertionError(f"unexpected url {url}")

    captured: list[tuple[str, str, dict]] = []

    def fake_emit(organ_id, status, metadata=None, **kwargs):
        captured.append((organ_id, status, dict(metadata or {})))
        return True

    with (
        patch.object(sensor, "_http_get_channel_health", side_effect=fake_http_get),
        patch("cell.sensors.channel_sensor.emit_organ_last_seen", side_effect=fake_emit),
    ):
        results = await sensor.bridge_channels_to_sidecar()

    assert len(captured) == 4
    organ_ids = {entry[0] for entry in captured}
    assert organ_ids == {
        "channel.whatsapp",
        "channel.telegram",
        "channel.instagram",
        "channel.web",
    }

    by_organ = {entry[0]: entry for entry in captured}
    assert by_organ["channel.whatsapp"][1] == "ok"
    assert by_organ["channel.web"][1] == "degraded"
    assert by_organ["channel.web"][2]["queue_depth"] == 50

    assert results == {
        "whatsapp": "ok",
        "telegram": "ok",
        "instagram": "ok",
        "web": "degraded",
    }


@pytest.mark.asyncio
async def test_bridge_emits_fail_on_http_error():
    """HTTP error on a single channel → fail sidecar for that channel only;
    others continue normally."""
    sensor = ChannelSensor()

    async def fake_http_get(url):
        if "/whatsapp/" in url:
            raise ConnectionError("simulated network failure")
        return {"status": "ok", "queue_depth": 0, "last_event_seen_at": None}

    captured: list[tuple[str, str, dict]] = []

    def fake_emit(organ_id, status, metadata=None, **kwargs):
        captured.append((organ_id, status, dict(metadata or {})))
        return True

    with (
        patch.object(sensor, "_http_get_channel_health", side_effect=fake_http_get),
        patch("cell.sensors.channel_sensor.emit_organ_last_seen", side_effect=fake_emit),
    ):
        results = await sensor.bridge_channels_to_sidecar()

    assert len(captured) == 4
    statuses = {entry[0]: entry[1] for entry in captured}
    assert statuses["channel.whatsapp"] == "fail"
    assert statuses["channel.telegram"] == "ok"
    assert statuses["channel.instagram"] == "ok"
    assert statuses["channel.web"] == "ok"

    whatsapp_meta = next(
        entry[2] for entry in captured if entry[0] == "channel.whatsapp"
    )
    assert "error" in whatsapp_meta
    assert "simulated network failure" in whatsapp_meta["error"]

    assert results["whatsapp"] == "fail"
