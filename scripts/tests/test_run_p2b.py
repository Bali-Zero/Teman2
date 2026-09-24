"""Tests for scripts/kbli_bench/run_p2b.py's repo_relative() — the manifest-path guilt.

The 2026-09-22 P2b re-judge manifest recorded corpus.path as an absolute worktree
path (/Users/<account>/nuzantara/.worktrees/<lane>/scripts/...), carrying the host
account name into a committed artifact (flagged by claude-sonnet-5, M5 gate session,
code review round). Guilt: an absolute corpus path is not written into the manifest.

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools, not a Python package (mirrors
scripts/tests/test_score_p2b.py convention).

Run:
    python3 -m pytest scripts/tests/test_run_p2b.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "kbli_bench" / "run_p2b.py"


@pytest.fixture(scope="module")
def run_mod():
    spec = importlib.util.spec_from_file_location("run_p2b_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_repo_relative_strips_an_absolute_worktree_path(run_mod):
    corpus = REPO_ROOT / "scripts" / "kbli_bench" / "p2b_corpus.json"
    result = run_mod.repo_relative(corpus)

    assert result == "scripts/kbli_bench/p2b_corpus.json"
    assert not result.startswith("/")
    assert str(REPO_ROOT) not in result


def test_repo_relative_accepts_an_already_relative_path(run_mod):
    rel = Path("scripts/kbli_bench/p2b_corpus.json")
    result = run_mod.repo_relative(rel)

    assert result == "scripts/kbli_bench/p2b_corpus.json"


def test_repo_relative_falls_back_outside_any_repo(run_mod, tmp_path):
    """tmp_path lives under the system tmpdir, never inside a git worktree, so the
    `git rev-parse --show-toplevel` probe exits non-zero and repo_relative must fall
    back to the path as given rather than raise."""
    outside = tmp_path / "not_a_repo" / "corpus.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("{}")

    result = run_mod.repo_relative(outside)
    assert result == str(outside)


def _make_seat(dir_path: Path, config_text: str, with_auth: bool = True) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "config.toml").write_text(config_text)
    if with_auth:
        (dir_path / "auth.json").write_text('{"dummy": "not-a-real-credential"}')
    return dir_path


def test_sanitized_codex_home_guilt_uses_the_picked_seat(run_mod, tmp_path, monkeypatch):
    """The 2026-09-22 merge-queue red: run_p2b.py invoked codex without resolving a seat
    (scripts/tests/test_codex_seat_lib.py::test_no_call_site_invokes_codex_without_choosing_a_seat).
    Guilt: when codex_seat_pick() returns a seat directory, sanitized_codex_home must copy
    FROM that directory, not from ~/.codex -- proven here by planting a decoy ~/.codex (via
    HOME) that differs from the picked seat and asserting the decoy's content never lands in
    dest. No real credential is touched: both "auth.json" files are invented dummy strings."""
    picked_seat = tmp_path / "picked-seat"
    _make_seat(picked_seat, "a = true\n[features.x]\ny = true\n")

    fake_home = tmp_path / "fake_home"
    _make_seat(fake_home / ".codex", "decoy = true\n")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(run_mod, "codex_seat_pick", lambda: str(picked_seat))

    dest = tmp_path / "dest-guilt"
    result_dest, note = run_mod.sanitized_codex_home(dest)

    assert result_dest == dest
    assert (dest / "config.toml").read_text() == "a = true\n"
    assert "decoy" not in (dest / "config.toml").read_text()
    assert "1 nested" in note


def test_sanitized_codex_home_innocence_falls_back_to_home_codex(run_mod, tmp_path, monkeypatch):
    """Innocence: when codex_seat_pick() returns None (no seat found), sanitized_codex_home
    falls back to ~/.codex -- codex's own default, exactly as before this file resolved a
    seat at all. No real credential is touched: the auth.json content is an invented dummy
    string, and HOME is monkeypatched to a tmp_path directory."""
    fake_home = tmp_path / "fake_home"
    _make_seat(fake_home / ".codex", "z = false\n")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(run_mod, "codex_seat_pick", lambda: None)

    dest = tmp_path / "dest-innocence"
    result_dest, note = run_mod.sanitized_codex_home(dest)

    assert result_dest == dest
    assert (dest / "config.toml").read_text() == "z = false\n"
    assert "0 nested" in note
