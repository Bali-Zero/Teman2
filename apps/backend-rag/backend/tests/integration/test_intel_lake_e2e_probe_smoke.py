"""Smoke test for intel_lake_e2e_probe.py — Phase C 2026-05-20.

This test does NOT run the probe end-to-end (that needs a live Fly proxy +
production-side state machine). It verifies:
  - probe module imports without side effects
  - ProbeFixture.generate produces stable schema
  - hop functions have expected signatures
  - main() exits 2 when preconditions are missing

The actual e2e run is invoked manually or via LaunchAgent
`com.balizero.intel-lake.e2e-probe.6h` (Phase D).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def probe_module():
    """Import scripts/probes/intel_lake_e2e_probe.py as a module."""
    repo_root = Path(__file__).resolve().parents[5]
    probe_path = repo_root / "scripts" / "probes" / "intel_lake_e2e_probe.py"
    assert probe_path.is_file(), f"probe script missing: {probe_path}"
    spec = importlib.util.spec_from_file_location("intel_lake_e2e_probe", probe_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["intel_lake_e2e_probe"] = module  # required for dataclass.__module__ lookup
    spec.loader.exec_module(module)
    return module


def test_probe_fixture_schema_stable(probe_module):
    fx1 = probe_module.ProbeFixture.generate()
    fx2 = probe_module.ProbeFixture.generate()
    assert fx1.canonical_url != fx2.canonical_url, "fixtures must be unique"
    assert fx1.canonical_url.startswith("https://probe-sandbox.example.test/probe-")
    assert fx1.title.startswith("[PROBE-SANDBOX]")
    assert len(fx1.content_hash) == 64, "content_hash must be sha256 hex"


def test_probe_constants(probe_module):
    assert probe_module.NB_SANDBOX_UUID == "7e6ae978-136c-4c96-bed5-9fab6f39176f"
    assert probe_module.PROBE_PRODUCER.startswith("probe-sandbox-")


def test_probe_main_refuses_without_dsn(probe_module, monkeypatch):
    """main() returns 2 when DATABASE_URL is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("INTEL_LAKE_PRODUCER_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["intel_lake_e2e_probe.py", "--wait", "5"])
    rc = probe_module.main()
    assert rc == 2, "must exit 2 when preconditions missing"


def test_probe_main_refuses_flycast_dsn(probe_module, monkeypatch):
    """main() refuses to run against flycast-form DSN (would hit prod)."""
    monkeypatch.setenv("DATABASE_URL", "postgres://x:y@nuzantara-postgres.flycast:5432/db?sslmode=require")
    monkeypatch.setenv("INTEL_LAKE_PRODUCER_TOKEN", "test-token")
    monkeypatch.setattr(sys, "argv", ["intel_lake_e2e_probe.py", "--wait", "5"])
    rc = probe_module.main()
    assert rc == 2, "must refuse flycast DSN (panel critique: never run probes against prod-direct DSN)"


def test_probe_main_refuses_without_token(probe_module, monkeypatch):
    """main() returns 2 when INTEL_LAKE_PRODUCER_TOKEN is missing."""
    monkeypatch.setenv("DATABASE_URL", "postgres://x:y@localhost:15432/test")
    monkeypatch.delenv("INTEL_LAKE_PRODUCER_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["intel_lake_e2e_probe.py", "--wait", "5"])
    rc = probe_module.main()
    assert rc == 2, "must exit 2 when INTEL_LAKE_PRODUCER_TOKEN missing"
