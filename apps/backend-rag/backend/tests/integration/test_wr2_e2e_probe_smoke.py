"""Smoke test for wr2_e2e_probe.py — Phase C 2026-05-20.

Static checks only — no live DB. The actual e2e run is invoked manually
or via LaunchAgent (Phase D).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def probe_module():
    repo_root = Path(__file__).resolve().parents[5]
    probe_path = repo_root / "scripts" / "probes" / "wr2_e2e_probe.py"
    assert probe_path.is_file(), f"probe script missing: {probe_path}"
    spec = importlib.util.spec_from_file_location("wr2_e2e_probe", probe_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_topic_prefix_constant(probe_module):
    assert probe_module.PROBE_TOPIC_PREFIX == "[PROBE-SANDBOX-2026-05-20]"


def test_probe_main_refuses_without_dsn(probe_module, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["wr2_e2e_probe.py"])
    rc = probe_module.main()
    assert rc == 2


def test_probe_main_refuses_flycast_dsn(probe_module, monkeypatch):
    """Refuse flycast — never run WR2 probe against production-direct DSN."""
    monkeypatch.setenv("DATABASE_URL", "postgres://x:y@nuzantara-postgres.flycast:5432/db?sslmode=require")
    monkeypatch.setattr(sys, "argv", ["wr2_e2e_probe.py"])
    rc = probe_module.main()
    assert rc == 2
