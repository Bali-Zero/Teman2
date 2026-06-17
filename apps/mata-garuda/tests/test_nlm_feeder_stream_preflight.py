"""Mythos-P3: run_nlm_feeder_stream redis preflight must fail LOUD.

A redis-cli timeout is swallowed by base_worker.stream_read_new
([ERROR] -> []), so without a preflight the feeder reports a clean
processed:0 forever even when its redis is unreachable (the 33-day
silent-starvation incident). These tests pin the fail-loud behaviour.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_nlm_feeder_stream.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_nlm_feeder_stream", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_preflight_aborts_with_exit3_when_redis_unreachable(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "redis_cmd", lambda *a, **k: "[ERROR] redis-cli timeout after 5s")
    rc = mod.main()
    assert rc == 3
    out = capsys.readouterr().out
    assert "redis_unreachable" in out
    # Must NOT masquerade as a healthy 0/0/0 feed.
    assert '"fed": 0' not in out and '"processed": 0' not in out


def test_preflight_proceeds_on_pong(monkeypatch, capsys):
    mod = _load()
    empty = {"processed": 0, "fed": 0, "skipped": 0, "errors": 0}
    monkeypatch.setattr(mod, "redis_cmd", lambda *a, **k: "PONG")
    monkeypatch.setattr(mod, "KnowledgeBase", lambda *a, **k: MagicMock())
    monkeypatch.setattr(mod, "run_nlm_feeder_from_alerts", lambda *a, **k: dict(empty))
    monkeypatch.setattr(mod, "run_nlm_feeder_from_stream", lambda *a, **k: dict(empty))
    rc = mod.main()
    assert rc == 0
    assert "redis_unreachable" not in capsys.readouterr().out
