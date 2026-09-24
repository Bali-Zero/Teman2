"""The post-publish poller must hand codex subprocesses a $PATH whose FIRST codex is the
standalone channel (~/.local/bin), then the npm copy (/opt/homebrew/bin) — whatever
shape the inherited $PATH has.

2026-09-24: the poller prepended only /opt/homebrew/bin; that copy (0.149.0) could not
parse the config.toml the standalone 0.155.1 had rewritten, so 25 ticks logged
"Codex unavailable" and two articles failed 5/5 with no cover. Loaded by path — the
poller runs from a LaunchAgent with no package on sys.path. Assertions are made with
shutil.which against two fake executables: the entity is "which codex answers", not a
PATH string.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

import pytest

POLLER = Path(__file__).resolve().parents[2] / "apps" / "bali-intel-scraper" / "scripts" / "post_publish_poller.py"


def _load():
    spec = importlib.util.spec_from_file_location("_poller_under_test", POLLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def channels(tmp_path, monkeypatch):
    local = tmp_path / "local-bin"
    homebrew = tmp_path / "homebrew-bin"
    for d in (local, homebrew):
        d.mkdir()
        (d / "codex").write_text("#!/bin/sh\n")
        (d / "codex").chmod(0o755)
    mod = _load()
    monkeypatch.setattr(mod, "CODEX_BIN_DIRS", (str(local), str(homebrew)))
    monkeypatch.setattr(mod, "_codex_seat_env", lambda env: env)
    return mod, str(local), str(homebrew)


def test_codex_bin_dirs_standalone_first():
    mod = _load()
    assert mod.CODEX_BIN_DIRS == ("~/.local/bin", "/opt/homebrew/bin")
    assert mod.codex_bin_dirs()[0] == os.path.expanduser("~/.local/bin")


@pytest.mark.parametrize(
    "shape",
    [
        "",                                              # empty
        "/usr/bin:/bin",                                 # thin launchd
        "{hb}:/usr/local/bin:/usr/bin:/bin",             # the production plist, local absent
        "{hb}:/usr/bin:{local}",                         # local present but BEHIND homebrew
        "{local}:{hb}:/usr/bin",                         # already right
        "/usr/bin:{local}",                              # only the standalone, at the tail
    ],
    ids=["empty", "thin", "plist-prod", "local-behind-homebrew", "already-right", "local-tail"],
)
def test_first_codex_on_the_subprocess_path_is_the_standalone(channels, monkeypatch, shape):
    mod, local, homebrew = channels
    monkeypatch.setenv("PATH", shape.format(hb=homebrew, local=local))
    assert shutil.which("codex", path=mod._codex_env()["PATH"]) == f"{local}/codex"


def test_homebrew_only_host_still_finds_codex(channels, monkeypatch):
    """innocence: no standalone installed -> the npm copy answers."""
    mod, local, homebrew = channels
    Path(local, "codex").unlink()
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert shutil.which("codex", path=mod._codex_env()["PATH"]) == f"{homebrew}/codex"


def test_inherited_entries_survive_once_behind_the_roots(channels, monkeypatch):
    mod, local, homebrew = channels
    monkeypatch.setenv("PATH", f"{homebrew}:/usr/bin:{local}:/bin")
    assert mod._codex_env()["PATH"].split(":") == [local, homebrew, "/usr/bin", "/bin"]
