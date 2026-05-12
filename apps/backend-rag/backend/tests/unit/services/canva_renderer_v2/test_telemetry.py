"""Telemetry: JSONL append-only with size-based rotation."""
import json
from pathlib import Path

from backend.services.canva_renderer_v2._telemetry import log_telemetry


def test_telemetry_append(tmp_path, monkeypatch):
    log = tmp_path / "telemetry.jsonl"
    monkeypatch.setenv("WR2_TELEMETRY_PATH", str(log))
    log_telemetry(draft_id="abc", outcome="success", duration_s=12.3)
    log_telemetry(draft_id="xyz", outcome="canva_import_failed", duration_s=4.5, attempt=2)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["draft_id"] == "abc"
    assert json.loads(lines[1])["attempt"] == 2


def test_telemetry_swallows_io_error(tmp_path, monkeypatch):
    # Point to unwritable path; must not raise
    monkeypatch.setenv("WR2_TELEMETRY_PATH", "/proc/cannot-write-here.jsonl")
    log_telemetry(draft_id="abc", outcome="success", duration_s=1.0)


def test_telemetry_rotation_at_size_cap(tmp_path, monkeypatch):
    log = tmp_path / "telemetry.jsonl"
    monkeypatch.setenv("WR2_TELEMETRY_PATH", str(log))
    monkeypatch.setenv("WR2_TELEMETRY_MAX_BYTES", "200")  # tiny cap for test
    for i in range(20):
        log_telemetry(draft_id=f"d{i}", outcome="success", duration_s=1.0)
    # Rotated file should exist alongside
    rotated = list(tmp_path.glob("telemetry.jsonl.*"))
    assert len(rotated) >= 1
