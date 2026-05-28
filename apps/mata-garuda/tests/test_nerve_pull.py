"""Tests for bridge nerve — pull side (Fly→Pro)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from mata_garuda.bridge.cursor import BridgeCursor
from mata_garuda.bridge.nerve import pull_once


def test_pull_once_no_events_does_nothing(tmp_path: Path):
    """Empty response: cursor unchanged, nothing published."""
    cursor = BridgeCursor(tmp_path / "c.json")

    fake_resp = {"status_code": 200, "json": {"events": [], "last_id": 0}}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock(return_value="ok")

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="key",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    assert stats == {"fetched": 0, "published": 0, "errors": 0}
    assert cursor.read() == 0
    fake_xadd.assert_not_called()


def test_pull_once_publishes_each_event_and_advances_cursor(tmp_path: Path):
    """Each event becomes an Envelope and is XADDed to bridge:inbound."""
    cursor = BridgeCursor(tmp_path / "c.json")

    events = [
        {"id": 10, "type": "crm.client_created", "payload": {"a": 1},
         "created_at": "2026-04-14T00:00:00+00:00"},
        {"id": 11, "type": "crm.practice_created", "payload": {"b": 2},
         "created_at": "2026-04-14T00:00:01+00:00"},
    ]
    fake_resp = {"status_code": 200, "json": {"events": events, "last_id": 11}}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock(return_value="1-0")

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    assert stats["fetched"] == 2
    assert stats["published"] == 2
    assert stats["errors"] == 0
    assert cursor.read() == 11
    assert fake_xadd.call_count == 2
    # Verify first XADD: stream + envelope dict
    stream, envelope_dict = fake_xadd.call_args_list[0].args
    assert stream == "bridge:inbound"
    assert envelope_dict["type"] == "crm.client_created"
    assert envelope_dict["source"] == "bridge"


def test_pull_once_http_error_does_not_advance_cursor(tmp_path: Path):
    """On HTTP error cursor stays put — Pro retries next cycle."""
    cursor = BridgeCursor(tmp_path / "c.json")
    cursor.write(5)  # pretend we already consumed up to 5

    def bad_get(*a, **kw):
        raise ConnectionError("Fly is down")

    fake_xadd = MagicMock()
    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=bad_get,
        redis_xadd=fake_xadd,
    )

    assert stats["errors"] == 1
    assert stats["fetched"] == 0
    assert cursor.read() == 5  # unchanged
    fake_xadd.assert_not_called()


def test_pull_once_unauthorized_does_not_advance(tmp_path: Path):
    """401 response: log and do nothing."""
    cursor = BridgeCursor(tmp_path / "c.json")
    cursor.write(7)

    fake_resp = {"status_code": 401, "json": None, "text": "unauthorized"}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock()

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="bad",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    assert stats["errors"] == 1
    assert cursor.read() == 7


def test_pull_once_partial_publish_failure(tmp_path: Path):
    """If one event fails to publish, others succeed; cursor moves to last successful."""
    cursor = BridgeCursor(tmp_path / "c.json")

    events = [
        {"id": 10, "type": "crm.client_created", "payload": {"a": 1},
         "created_at": "2026-04-14T00:00:00+00:00"},
        {"id": 11, "type": "crm.practice_created", "payload": {"b": 2},
         "created_at": "2026-04-14T00:00:01+00:00"},
    ]
    fake_resp = {"status_code": 200, "json": {"events": events, "last_id": 11}}
    fake_get = MagicMock(return_value=fake_resp)

    # First XADD raises, second succeeds — but our impl may treat all-or-nothing or per-event
    # The contract: cursor only advances if ALL events published, OR cursor advances to last successful id.
    # We test the per-event-cursor approach: after a failure, cursor stays put.
    call_count = {"n": 0}
    def flaky_xadd(stream, fields):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("redis transient")
        return "1-0"
    fake_xadd = MagicMock(side_effect=flaky_xadd)

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    # 2 fetched, 1 published, 1 error
    assert stats["fetched"] == 2
    assert stats["published"] == 1
    assert stats["errors"] == 1
    # Cursor advances ONLY if ALL events published (safer — replays everything next cycle).
    # If you implement per-event cursor advance, change this assertion accordingly.
    # For at-least-once semantics with simple state, we keep cursor at 0 if any failure.
    assert cursor.read() == 0


# ── CICATRIX 2026-05-21 defensive payload unwrap ──────────────────────


def test_pull_once_unwraps_legacy_string_payload(tmp_path: Path):
    """CICATRIX 2026-05-21 — if the backend serves a legacy double-encoded
    row (payload is a JSON string rather than a dict), nerve.pull_once
    must defensively json.loads() it before `**payload` instead of crashing
    with 'str' object is not a mapping. Without the fallback the bridge
    sits stuck for days as we observed 2026-05-06 → 2026-05-21."""
    cursor = BridgeCursor(tmp_path / "c.json")

    legacy_payload_str = json.dumps({"client_id": 99, "email": "x@y.z"})
    events = [
        {
            "id": 50,
            "type": "crm.client_created",
            "payload": legacy_payload_str,
            "created_at": "2026-05-06T22:50:00+00:00",
        },
    ]
    fake_resp = {"status_code": 200, "json": {"events": events, "last_id": 50}}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock(return_value="1-0")

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    assert stats["fetched"] == 1
    assert stats["published"] == 1
    assert stats["errors"] == 0
    assert cursor.read() == 50
    # Verify the unwrapped payload reached redis_xadd
    _stream, envelope_dict = fake_xadd.call_args.args
    assert envelope_dict["type"] == "crm.client_created"
    # Envelope.to_redis_dict serializes payload back to a JSON string — parse it
    payload_field = envelope_dict.get("payload")
    if isinstance(payload_field, str):
        payload_field = json.loads(payload_field)
    assert payload_field["client_id"] == 99
    assert payload_field["email"] == "x@y.z"
    assert payload_field["_outbox_id"] == 50


def test_pull_once_handles_malformed_string_payload(tmp_path: Path):
    """CICATRIX 2026-05-21 — non-JSON string payload coerces to empty dict
    so cursor still advances (we don't want one corrupt row to block the
    queue indefinitely)."""
    cursor = BridgeCursor(tmp_path / "c.json")

    events = [
        {
            "id": 60,
            "type": "rag.low_confidence",
            "payload": "not valid json {{{",
            "created_at": "2026-05-21T23:00:00+00:00",
        },
    ]
    fake_resp = {"status_code": 200, "json": {"events": events, "last_id": 60}}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock(return_value="1-0")

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    # Should NOT count as error — coerced and published with empty payload
    assert stats["fetched"] == 1
    assert stats["published"] == 1
    assert stats["errors"] == 0
    assert cursor.read() == 60


def test_pull_once_handles_dict_payload_unchanged(tmp_path: Path):
    """Post-fix path: payload is already a dict (correctly inserted via
    pool codec) — pull_once consumes it without any unwrap, as before."""
    cursor = BridgeCursor(tmp_path / "c.json")

    events = [
        {
            "id": 70,
            "type": "crm.practice_completed",
            "payload": {"practice_id": "abc-123"},
            "created_at": "2026-05-22T00:00:00+00:00",
        },
    ]
    fake_resp = {"status_code": 200, "json": {"events": events, "last_id": 70}}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock(return_value="1-0")

    stats = pull_once(
        cursor=cursor,
        backend_url="https://x",
        api_key="k",
        http_get=fake_get,
        redis_xadd=fake_xadd,
    )

    assert stats["fetched"] == 1
    assert stats["published"] == 1
    assert stats["errors"] == 0
    assert cursor.read() == 70


def test_pull_once_idle_increments_heartbeat_counter(tmp_path: Path, monkeypatch):
    """W1 cicatrix 2026-05-22 — silent-idle ticks must persist a counter
    sidecar so a heartbeat log fires every N consecutive idle ticks. Without
    this, launchd shows `state=active last exit=0` while the log stays
    silent for hours, indistinguishable from a dead cron."""
    monkeypatch.setenv("BRIDGE_HEARTBEAT_IDLE_TICKS", "3")
    import importlib
    import mata_garuda.bridge.nerve as nerve_mod
    importlib.reload(nerve_mod)

    cursor = nerve_mod.BridgeCursor(tmp_path / "c.json")
    fake_resp = {"status_code": 200, "json": {"events": [], "last_id": 0}}
    fake_get = MagicMock(return_value=fake_resp)
    fake_xadd = MagicMock()

    sidecar = tmp_path / "c-idle-ticks.json"

    # Tick 1 + 2: counter accumulates, no heartbeat yet.
    for expected in (1, 2):
        nerve_mod.pull_once(
            cursor=cursor, backend_url="https://x", api_key="k",
            http_get=fake_get, redis_xadd=fake_xadd,
        )
        assert sidecar.exists()
        assert json.loads(sidecar.read_text())["count"] == expected

    # Tick 3: threshold hit → heartbeat fires, counter resets to 0.
    nerve_mod.pull_once(
        cursor=cursor, backend_url="https://x", api_key="k",
        http_get=fake_get, redis_xadd=fake_xadd,
    )
    assert json.loads(sidecar.read_text())["count"] == 0


def test_pull_once_non_idle_resets_heartbeat_counter(tmp_path: Path, monkeypatch):
    """Any tick that fetches >0 events OR errors out must clear the
    sidecar — heartbeat is only for genuine quiet periods."""
    monkeypatch.setenv("BRIDGE_HEARTBEAT_IDLE_TICKS", "5")
    import importlib
    import mata_garuda.bridge.nerve as nerve_mod
    importlib.reload(nerve_mod)

    cursor = nerve_mod.BridgeCursor(tmp_path / "c.json")
    sidecar = tmp_path / "c-idle-ticks.json"

    # Prime counter with 2 idle ticks.
    fake_get = MagicMock(return_value={"status_code": 200, "json": {"events": [], "last_id": 0}})
    fake_xadd = MagicMock()
    for _ in range(2):
        nerve_mod.pull_once(
            cursor=cursor, backend_url="https://x", api_key="k",
            http_get=fake_get, redis_xadd=fake_xadd,
        )
    assert json.loads(sidecar.read_text())["count"] == 2

    # Non-idle tick (1 event) → sidecar must be deleted.
    fake_get_evt = MagicMock(return_value={
        "status_code": 200,
        "json": {"events": [{"id": 100, "type": "crm.x", "payload": {}, "created_at": "2026-05-22T00:00:00+00:00"}], "last_id": 100},
    })
    nerve_mod.pull_once(
        cursor=cursor, backend_url="https://x", api_key="k",
        http_get=fake_get_evt, redis_xadd=MagicMock(return_value="1-0"),
    )
    assert not sidecar.exists()


# ── W2 cicatrix 2026-05-22 consecutive-error escalation ────────────────


def test_pull_once_error_streak_escalates_after_threshold(tmp_path: Path, monkeypatch, caplog):
    """W2 cicatrix 2026-05-22 — single Fly cold-restart timeout is noise
    (WARNING). 5+ consecutive timeouts means the backend is actually DOWN
    and must escalate to ERROR so dashboard/Sentry/Telegram pick it up."""
    import logging
    monkeypatch.setenv("BRIDGE_ERROR_STREAK_ALERT", "3")
    import importlib
    import mata_garuda.bridge.nerve as nerve_mod
    importlib.reload(nerve_mod)

    cursor = nerve_mod.BridgeCursor(tmp_path / "c.json")
    streak_file = tmp_path / "c-error-streak.json"

    def bad_get(*a, **kw):
        raise ConnectionError("curl exit 28: timeout")

    fake_xadd = MagicMock()

    with caplog.at_level(logging.WARNING, logger="mata_garuda.bridge.nerve"):
        # Ticks 1+2: WARNING (below threshold).
        for expected in (1, 2):
            caplog.clear()
            nerve_mod.pull_once(
                cursor=cursor, backend_url="https://x", api_key="k",
                http_get=bad_get, redis_xadd=fake_xadd,
            )
            assert streak_file.exists()
            assert json.loads(streak_file.read_text())["count"] == expected
            warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
            error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
            assert len(warning_records) == 1, f"tick {expected} should warn"
            assert not error_records, f"tick {expected} must not error yet"

        # Tick 3: hits threshold → ERROR.
        caplog.clear()
        nerve_mod.pull_once(
            cursor=cursor, backend_url="https://x", api_key="k",
            http_get=bad_get, redis_xadd=fake_xadd,
        )
        assert json.loads(streak_file.read_text())["count"] == 3
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "streak=3" in error_records[0].getMessage()
        assert "backend likely DOWN" in error_records[0].getMessage()


def test_pull_once_error_streak_resets_on_success(tmp_path: Path, monkeypatch):
    """A successful tick (200 + parseable body, even if events=[]) must
    delete the streak sidecar so the next failure starts fresh from 1."""
    monkeypatch.setenv("BRIDGE_ERROR_STREAK_ALERT", "5")
    import importlib
    import mata_garuda.bridge.nerve as nerve_mod
    importlib.reload(nerve_mod)

    cursor = nerve_mod.BridgeCursor(tmp_path / "c.json")
    streak_file = tmp_path / "c-error-streak.json"

    # Prime with 2 errors.
    def bad_get(*a, **kw):
        raise ConnectionError("curl exit 28")

    for _ in range(2):
        nerve_mod.pull_once(
            cursor=cursor, backend_url="https://x", api_key="k",
            http_get=bad_get, redis_xadd=MagicMock(),
        )
    assert json.loads(streak_file.read_text())["count"] == 2

    # Now a success: streak file must be deleted.
    good_get = MagicMock(return_value={"status_code": 200, "json": {"events": [], "last_id": 0}})
    nerve_mod.pull_once(
        cursor=cursor, backend_url="https://x", api_key="k",
        http_get=good_get, redis_xadd=MagicMock(),
    )
    assert not streak_file.exists()
