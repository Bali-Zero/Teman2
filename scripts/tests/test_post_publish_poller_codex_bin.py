"""The post-publish poller must hand codex subprocesses a $PATH whose FIRST codex is the
standalone channel (~/.local/bin), then the npm copy (/opt/homebrew/bin).

2026-09-24: the poller prepended only /opt/homebrew/bin; that copy (0.149.0) could not
parse the config.toml the standalone 0.155.1 had rewritten, so 25 ticks logged
"Codex unavailable" and two articles failed 5/5 with no cover. Loaded by path — the
poller runs from a LaunchAgent with no package on sys.path.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

POLLER = Path(__file__).resolve().parents[2] / "apps" / "bali-intel-scraper" / "scripts" / "post_publish_poller.py"


def _load():
    spec = importlib.util.spec_from_file_location("_poller_under_test", POLLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_codex_bin_dirs_standalone_first():
    mod = _load()
    assert mod.CODEX_BIN_DIRS[0] == "~/.local/bin"
    assert mod.CODEX_BIN_DIRS[1] == "/opt/homebrew/bin"
    assert mod.codex_bin_dirs()[0] == os.path.expanduser("~/.local/bin")


def test_codex_env_thin_launchd_path_gets_both_roots_in_order(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_codex_seat_env", lambda env: env)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    path = mod._codex_env()["PATH"].split(":")
    assert path[:2] == [os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin"]
    assert path[2:] == ["/usr/bin", "/bin"]


def test_codex_env_does_not_duplicate_roots_already_present(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_codex_seat_env", lambda env: env)
    local = os.path.expanduser("~/.local/bin")
    monkeypatch.setenv("PATH", f"{local}:/opt/homebrew/bin:/usr/bin")
    assert mod._codex_env()["PATH"] == f"{local}:/opt/homebrew/bin:/usr/bin"


def test_codex_env_empty_path_is_just_the_roots(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_codex_seat_env", lambda env: env)
    monkeypatch.setenv("PATH", "")
    assert mod._codex_env()["PATH"] == f"{os.path.expanduser('~/.local/bin')}:/opt/homebrew/bin"
