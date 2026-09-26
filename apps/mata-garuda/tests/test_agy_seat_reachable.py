"""The agy seat must stay reachable from the gap consumer's launchd context.

Scar #2 (Esiste != Armato), found 2026-09-25: com.matagaruda.gap.consumer ran
green (exit 0) while every agy call died in ~3 ms — the job's PATH lacks
~/.local/bin and its pinned model gemini-3.5-flash is no longer served by the
CLI — so the Regulation Watcher degraded to Ollama, 108 failures a day, with
no warning line. These pins keep the runtime side of both doors open; the
plist itself is a hot-zone path and travels in its own PR.
"""
from __future__ import annotations

import logging
import plistlib
from pathlib import Path

from mata_garuda.runtime import cli_runtime
from mata_garuda.workers import gap_consumer

REPO_ROOT = Path(__file__).resolve().parents[3]
PLIST = REPO_ROOT / "infra" / "launchagents" / "com.matagaruda.gap.consumer.plist"

# `agy models`, 2026-09-24 — research/operations/2026-09-24-agy-seat-probe.md.
SERVED_AGY_MODELS = {
    "gemini-3.8-flash-high", "gemini-3.8-flash-medium", "gemini-3.8-flash-low",
    "gemini-3.7-flash-high", "gemini-3.7-flash-medium", "gemini-3.7-flash-low",
    "gemini-3.6-flash-high", "gemini-3.6-flash-medium", "gemini-3.6-flash-low",
    "gemini-3.1-pro-high", "gemini-3.1-pro-low",
}


def _agy_model(value: str) -> str:
    return value.split(":", 1)[1] if value.startswith("agy:") else value


def test_default_agy_model_is_served():
    assert cli_runtime.DEFAULT_AGY_MODEL in SERVED_AGY_MODELS


def test_regulation_watcher_default_model_is_served():
    assert _agy_model(gap_consumer.DEFAULT_REGULATION_AGENT_MODEL) in SERVED_AGY_MODELS


def test_every_retired_alias_targets_a_served_model():
    assert set(cli_runtime.RETIRED_AGY_MODELS.values()) <= SERVED_AGY_MODELS


def test_resolve_agy_bin_prefers_path(monkeypatch):
    monkeypatch.delenv("MATA_GARUDA_AGY_BIN", raising=False)
    monkeypatch.setattr(cli_runtime.shutil, "which", lambda name: "/usr/local/bin/agy")
    assert cli_runtime._resolve_agy_bin() == "agy"


def test_resolve_agy_bin_falls_back_to_local_bin_when_path_is_thin(monkeypatch, tmp_path):
    monkeypatch.delenv("MATA_GARUDA_AGY_BIN", raising=False)
    monkeypatch.setattr(cli_runtime.shutil, "which", lambda name: None)
    monkeypatch.setattr(cli_runtime.Path, "home", classmethod(lambda cls: tmp_path))
    local = tmp_path / ".local" / "bin" / "agy"
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\n")
    assert cli_runtime._resolve_agy_bin() == str(local)


def test_resolve_agy_bin_honours_override(monkeypatch):
    monkeypatch.setenv("MATA_GARUDA_AGY_BIN", "/opt/agy/bin/agy")
    assert cli_runtime._resolve_agy_bin() == "/opt/agy/bin/agy"


def test_retired_model_is_swapped_for_a_served_one_with_a_warning(caplog):
    rt = cli_runtime.CLIRuntime(model="agy:gemini-3.5-flash")
    with caplog.at_level(logging.WARNING, logger=cli_runtime.logger.name):
        cmd = rt._build_command("ping")
    assert "gemini-3.8-flash-high" in cmd
    assert "gemini-3.5-flash" not in cmd
    assert any("retired" in rec.message for rec in caplog.records)


def test_served_model_passes_through_silently(caplog):
    with caplog.at_level(logging.WARNING, logger=cli_runtime.logger.name):
        assert cli_runtime.served_agy_model("gemini-3.1-pro-high") == "gemini-3.1-pro-high"
    assert not caplog.records


def _plist_env() -> dict[str, str]:
    with PLIST.open("rb") as fh:
        return plistlib.load(fh)["EnvironmentVariables"]


def test_plist_path_reaches_local_bin():
    env = _plist_env()
    assert "/Users/nuzantara/.local/bin" in env["PATH"].split(":")


def test_plist_agy_routed_models_are_served():
    env = _plist_env()
    routed = {
        key: _agy_model(value)
        for key, value in env.items()
        if key == "MATA_GARUDA_AGY_MODEL" or value.startswith("agy:")
    }
    assert routed
    unserved = {key: model for key, model in routed.items() if model not in SERVED_AGY_MODELS}
    assert not unserved, unserved
