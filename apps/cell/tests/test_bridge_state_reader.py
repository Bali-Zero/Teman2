"""Tests for `cell.sensors.bridge_state_reader`.

The bridge reader translates Genoma `bridge_source` declarations of type
`state_file` into BridgeReading records (timestamp + status + raw payload),
so the genome_aggregator_sensor can compute per-organ liveness without
modifying the organi themselves (Codex bridge insight, see
07_innervation_protocol.md §1.1 + §2.4).

The 8 tests below cover the failure modes documented in 07 §3.2 plus the
custom-field overrides documented in 09 §2.3.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cell.sensors.bridge_state_reader import (
    BridgeReading,
    BridgeStateReader,
    BridgeSource,
)


# ---------- helpers ----------------------------------------------------------


def _write_state(path: Path, *, ts: int | float, status: str = "ok", **extra) -> None:
    payload = {"ts": ts, "status": status, **extra}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _src(path: Path, **kwargs) -> BridgeSource:
    """Build a default BridgeSource for the test file."""
    return BridgeSource(
        organ_id=kwargs.pop("organ_id", "test.organ"),
        type="state_file",
        path=str(path),
        timestamp_field=kwargs.pop("timestamp_field", "ts"),
        status_field=kwargs.pop("status_field", "status"),
    )


# ---------- happy paths ------------------------------------------------------


def test_reads_present_state_file_with_default_fields(tmp_path):
    """Standard cron-agent state file (ts + status keys) is read directly."""
    f = tmp_path / "drive_poll.last.json"
    _write_state(f, ts=1774500000.0, status="ok", host="Pro")

    reader = BridgeStateReader([_src(f, organ_id="backend.crm.drive_poll")])
    readings = reader.read_all()

    assert len(readings) == 1
    r = readings[0]
    assert isinstance(r, BridgeReading)
    assert r.organ_id == "backend.crm.drive_poll"
    assert r.timestamp == 1774500000.0
    assert r.status == "ok"
    assert r.payload["host"] == "Pro"
    assert r.error == ""


def test_reads_multiple_sources_independently(tmp_path):
    """Several sources are read and emitted in the same call."""
    f1 = tmp_path / "a.json"
    f2 = tmp_path / "b.json"
    _write_state(f1, ts=100.0, status="ok")
    _write_state(f2, ts=200.0, status="failed")

    reader = BridgeStateReader([
        _src(f1, organ_id="organ.a"),
        _src(f2, organ_id="organ.b"),
    ])
    readings = {r.organ_id: r for r in reader.read_all()}

    assert readings["organ.a"].status == "ok"
    assert readings["organ.a"].timestamp == 100.0
    assert readings["organ.b"].status == "failed"
    assert readings["organ.b"].timestamp == 200.0


def test_custom_timestamp_and_status_field_names(tmp_path):
    """A source can declare alternate JSON keys for timestamp + status.

    Used by `pro.claude_max_watcher` whose state file uses `Captured` (ISO
    string) and `Plan` instead of `ts`+`status`."""
    f = tmp_path / "custom.json"
    payload = {"Captured": "2026-04-29T13:00:00+00:00", "Plan": "Max (20x)"}
    f.write_text(json.dumps(payload))

    reader = BridgeStateReader([_src(
        f,
        organ_id="custom.one",
        timestamp_field="Captured",
        status_field="Plan",
    )])
    readings = reader.read_all()

    assert len(readings) == 1
    r = readings[0]
    # ISO strings are converted to unix epoch float by the reader.
    assert r.timestamp > 0  # parsed as datetime → unix epoch
    assert r.status == "Max (20x)"


# ---------- failure modes ----------------------------------------------------


def test_missing_file_returns_reading_with_error(tmp_path):
    """A source whose path doesn't exist yields a reading with error set."""
    missing = tmp_path / "nope.json"
    reader = BridgeStateReader([_src(missing, organ_id="organ.absent")])

    readings = reader.read_all()
    assert len(readings) == 1
    r = readings[0]
    assert r.organ_id == "organ.absent"
    assert r.error  # populated
    assert "not found" in r.error.lower() or "no such file" in r.error.lower()
    assert r.status == ""
    assert r.timestamp is None


def test_corrupt_json_returns_reading_with_error(tmp_path):
    """Unparseable JSON does NOT crash; it yields a reading with error set."""
    f = tmp_path / "garbage.json"
    f.write_text("not-json{{{")

    reader = BridgeStateReader([_src(f, organ_id="organ.bad")])
    readings = reader.read_all()

    assert len(readings) == 1
    r = readings[0]
    assert r.error  # populated
    assert "json" in r.error.lower() or "parse" in r.error.lower()


def test_missing_timestamp_field_returns_error(tmp_path):
    """If the configured `timestamp_field` is absent from the JSON, error set."""
    f = tmp_path / "no_ts.json"
    f.write_text(json.dumps({"status": "ok"}))

    reader = BridgeStateReader([_src(f, organ_id="organ.no_ts")])
    readings = reader.read_all()

    assert len(readings) == 1
    r = readings[0]
    assert r.error
    assert "timestamp" in r.error.lower() or "ts" in r.error.lower()


def test_tilde_in_path_is_expanded(tmp_path, monkeypatch):
    """`~/...` paths are expanded to the user's home directory.

    Used by every Genoma entry — `path: ~/.agent/decisions/state/*.last.json`.
    """
    home = tmp_path / "fakehome"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    f = home / "state.json"
    _write_state(f, ts=42.0, status="ok")

    reader = BridgeStateReader([_src(
        Path("~/state.json"),  # tilde path, not absolute
        organ_id="organ.tilde",
    )])
    readings = reader.read_all()

    assert len(readings) == 1
    r = readings[0]
    assert r.error == ""
    assert r.timestamp == 42.0


def test_unsupported_bridge_type_returns_error(tmp_path):
    """Bridge type other than `state_file`/`http` is not yet implemented;
    the reader returns a reading with error rather than silently skipping
    (so the operator sees the work-not-done)."""
    f = tmp_path / "any.json"
    _write_state(f, ts=1.0, status="ok")

    src = BridgeSource(
        organ_id="organ.sql",
        type="sql_table",  # unsupported in W0
        path="sometable",
    )
    reader = BridgeStateReader([src])
    readings = reader.read_all()

    assert len(readings) == 1
    r = readings[0]
    assert r.error
    assert "unsupported" in r.error.lower() or "sql_table" in r.error.lower()


# ---------- http branch (W1.2) ----------------------------------------------


from unittest.mock import MagicMock, patch
import httpx as _httpx_mod  # alias to avoid shadowing if test names collide


def _mock_httpx_client(*, status_code: int = 200, json_body: Any = None,
                       text_body: str | None = None,
                       raise_exc: Exception | None = None):
    """Build a context-manager mock for `httpx.Client(...)` whose `.get()`
    either raises `raise_exc`, returns a response with `status_code` +
    `json_body` (or `text_body`), or both."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text_body if text_body is not None else ""
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    elif text_body is not None:
        # text-but-not-json body — simulate json() raising
        def _raise(*args, **kwargs):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        resp.json = MagicMock(side_effect=_raise)

    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    if raise_exc is not None:
        client.get = MagicMock(side_effect=raise_exc)
    else:
        client.get = MagicMock(return_value=resp)

    cls = MagicMock(return_value=client)
    return cls


def test_http_source_returns_reading_with_status_and_ts():
    """Happy path: GET 200 + valid JSON body with channels nested status."""
    cls = _mock_httpx_client(
        status_code=200,
        json_body={"ts": 1000.0, "channels": {"whatsapp": {"status": "up"}}},
    )
    src = BridgeSource(
        organ_id="channel.whatsapp",
        type="http",
        path="https://example.test/health",
        json_path="channels.whatsapp.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]

    assert reading.error == "", reading.error
    assert reading.timestamp == 1000.0
    assert reading.status == "ok"


def test_http_source_maps_degraded_status():
    cls = _mock_httpx_client(
        status_code=200,
        json_body={"ts": 1000.0, "channels": {"telegram": {"status": "degraded"}}},
    )
    src = BridgeSource(
        organ_id="channel.telegram",
        type="http",
        path="https://example.test/health",
        json_path="channels.telegram.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert reading.status == "degraded"


def test_http_source_maps_down_status_to_fail():
    cls = _mock_httpx_client(
        status_code=200,
        json_body={"ts": 1000.0, "channels": {"instagram": {"status": "down"}}},
    )
    src = BridgeSource(
        organ_id="channel.instagram",
        type="http",
        path="https://example.test/health",
        json_path="channels.instagram.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert reading.status == "fail"


def test_http_source_5xx_returns_error():
    cls = _mock_httpx_client(status_code=503, text_body="upstream down")
    src = BridgeSource(
        organ_id="channel.web",
        type="http",
        path="https://example.test/health",
        json_path="channels.web.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert "http 503" in reading.error
    assert reading.status == ""  # no status on error


def test_http_source_timeout_returns_error():
    cls = _mock_httpx_client(raise_exc=_httpx_mod.ConnectTimeout("simulated"))
    src = BridgeSource(
        organ_id="channel.whatsapp",
        type="http",
        path="https://example.test/health",
        json_path="channels.whatsapp.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert "http request failed" in reading.error
    assert "ConnectTimeout" in reading.error


def test_http_source_malformed_json_returns_error():
    cls = _mock_httpx_client(status_code=200, text_body="not json{")
    src = BridgeSource(
        organ_id="channel.whatsapp",
        type="http",
        path="https://example.test/health",
        json_path="channels.whatsapp.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert "json parse error" in reading.error


def test_http_source_missing_json_path_returns_error():
    cls = _mock_httpx_client(
        status_code=200,
        json_body={"ts": 1000.0, "channels": {}},  # whatsapp absent
    )
    src = BridgeSource(
        organ_id="channel.whatsapp",
        type="http",
        path="https://example.test/health",
        json_path="channels.whatsapp.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert "missing json_path" in reading.error
    assert reading.timestamp == 1000.0  # ts still parsed before json_path check


def test_http_source_unknown_status_vocab_maps_to_degraded():
    """Operator visibility over silence: an unknown status string from the
    backend (vocab drift) maps to `degraded` rather than `ok` or `fail`."""
    cls = _mock_httpx_client(
        status_code=200,
        json_body={"ts": 1000.0, "channels": {"whatsapp": {"status": "weird-state"}}},
    )
    src = BridgeSource(
        organ_id="channel.whatsapp",
        type="http",
        path="https://example.test/health",
        json_path="channels.whatsapp.status",
    )
    with patch("cell.sensors.bridge_state_reader.httpx.Client", cls):
        reading = BridgeStateReader([src]).read_all()[0]
    assert reading.status == "degraded"
