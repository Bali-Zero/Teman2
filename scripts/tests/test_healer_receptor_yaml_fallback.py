"""yaml-import self-heal guilt+innocence (superscar #2 Esiste≠Armato).

Born 2026-07-17 (Mini healer tick): the receptor's `python3 scripts/healer_
receptor_registry.py --node mini --json` invocation resolved to Homebrew's
system python3 (3.14), which lacks PyYAML — every tick returned exit 2
"RECEPTOR BROKEN: ModuleNotFoundError: No module named 'yaml'", a broken
receptor silently reads as coverage loss. Fix: try importing yaml first;
if unavailable, re-exec once under a project venv that has it.
"""

import importlib.util
import os
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "healer_receptor_registry.py"
_spec = importlib.util.spec_from_file_location("healer_receptor_registry", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["healer_receptor_registry"] = _mod
_spec.loader.exec_module(_mod)


def test_find_yaml_venv_returns_first_existing_candidate(tmp_path):
    # innocence would be "no candidate exists" (next test) — this is guilt:
    # a real candidate must be found and returned, not just any truthy path.
    second = tmp_path / ".venv" / "bin" / "python3"
    second.parent.mkdir(parents=True)
    second.write_text("#!/bin/sh\n")
    first = tmp_path / "apps" / "backend-rag" / ".venv" / "bin" / "python3"
    first.parent.mkdir(parents=True)
    first.write_text("#!/bin/sh\n")

    found = _mod._find_yaml_venv(tmp_path)

    assert found == first  # first candidate in the tuple wins when both exist


def test_find_yaml_venv_returns_none_when_no_candidate(tmp_path):
    assert _mod._find_yaml_venv(tmp_path) is None


def test_reexec_noop_when_yaml_importable(monkeypatch):
    calls = []
    monkeypatch.setattr(_mod, "_yaml_importable", lambda: True)
    monkeypatch.setattr(os, "execve", lambda *a, **k: calls.append((a, k)))

    _mod._reexec_with_yaml_if_needed()

    assert calls == []  # yaml already importable — must not touch execve at all


def test_reexec_noop_when_guard_env_already_set(monkeypatch):
    calls = []
    monkeypatch.setattr(_mod, "_yaml_importable", lambda: False)
    monkeypatch.setenv(_mod._REEXEC_GUARD_ENV, "1")
    monkeypatch.setattr(os, "execve", lambda *a, **k: calls.append((a, k)))

    _mod._reexec_with_yaml_if_needed()

    assert calls == []  # already retried once — a second broken import must surface as exit 2, not loop


def test_reexec_noop_when_no_venv_candidate_found(monkeypatch):
    calls = []
    monkeypatch.setattr(_mod, "_yaml_importable", lambda: False)
    monkeypatch.delenv(_mod._REEXEC_GUARD_ENV, raising=False)
    monkeypatch.setattr(_mod, "_find_yaml_venv", lambda repo_root: None)
    monkeypatch.setattr(os, "execve", lambda *a, **k: calls.append((a, k)))

    _mod._reexec_with_yaml_if_needed()

    assert calls == []  # no candidate venv — falls through to the real ImportError at call site


def test_reexec_execs_found_candidate_with_guard_flag_set(monkeypatch, tmp_path):
    monkeypatch.setattr(_mod, "_yaml_importable", lambda: False)
    monkeypatch.delenv(_mod._REEXEC_GUARD_ENV, raising=False)
    candidate = tmp_path / "python3"
    monkeypatch.setattr(_mod, "_find_yaml_venv", lambda repo_root: candidate)
    captured = {}

    def fake_execve(path, argv, env):
        captured["path"] = path
        captured["argv"] = argv
        captured["env"] = env

    monkeypatch.setattr(os, "execve", fake_execve)

    monkeypatch.setattr(sys, "argv", ["healer_receptor_registry.py", "--node", "mini", "--json"])
    _mod._reexec_with_yaml_if_needed()

    assert captured["path"] == str(candidate)
    assert captured["argv"][0] == str(candidate)
    assert captured["argv"][1] == str(_MOD_PATH.resolve())
    assert captured["argv"][2:] == ["--node", "mini", "--json"]
    assert captured["env"][_mod._REEXEC_GUARD_ENV] == "1"
