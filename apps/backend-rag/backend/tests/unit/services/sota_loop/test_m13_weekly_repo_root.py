"""Tests for m13_weekly.py's `_repo_root()` — the path-resolution bug found
2026-07-27 while classifying Pro's permanently-dirty working tree (task #64).

Context: `wr2-cron-wrapper.sh` resolved `REPO_ROOT` for its own `cd` but never
exported it as `NUZANTARA_REPO_ROOT` for the child python process, so
`_repo_root()` always fell through to `Path(__file__).resolve().parents[N]` —
and that fallback was itself off by one (parents[4] from this file lands on
`apps/`, not the repo root). Both bugs stacked to write this module's weekly
report to `apps/research/sota-social-2026-v1/` instead of
`research/sota-social-2026-v1/` for several weeks.

The fix, same shape as scripts/agent_start.py's cure (#3197, W105): prefer
the env var, then a signature-guarded `git rev-parse --show-toplevel`
derivation (deliberately NOT `--git-common-dir` — that resolves to the MAIN
checkout even from inside a worktree, which is what
infra/claude-hooks/worktree_isolation.py wants for ITS question ("where is
main"); this module wants "where is the checkout I am actually running
from", which `--show-toplevel` answers correctly and `--git-common-dir` does
not), then the corrected file-relative guess as a last resort.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from backend.services.sota_loop.m13_weekly import _repo_root

_THIS_REPO_ROOT = Path(__file__).resolve().parents[7]


def test_env_var_wins_when_set(monkeypatch) -> None:
    monkeypatch.setenv("NUZANTARA_REPO_ROOT", "/some/explicit/override")
    assert _repo_root() == Path("/some/explicit/override")


def test_show_toplevel_derivation_finds_the_real_repo_root(monkeypatch) -> None:
    """INNOCENCE: with no env var, a real invocation inside this checkout
    must land on the actual repo root — not `apps/`, not any other ancestor.
    This is the case the old off-by-one fallback got wrong, and it must also
    be the CURRENT checkout's root, not necessarily main's (worktree-safe —
    `--show-toplevel`, not `--git-common-dir`; the two diverge inside a
    worktree, verified live: `--git-common-dir` in this very worktree
    resolves to the outer main checkout's .git, `--show-toplevel` resolves
    to this worktree's own root)."""
    monkeypatch.delenv("NUZANTARA_REPO_ROOT", raising=False)
    root = _repo_root()
    assert root == _THIS_REPO_ROOT
    assert (root / "scripts" / "agent_start.py").is_file()
    assert root.name != "apps"


def test_final_fallback_math_is_correct_if_derivation_is_ever_unavailable(
    monkeypatch,
) -> None:
    """GUILT-style regression pin: even if git ever becomes unavailable (the
    only path the old bug could hide in), the literal parents[N] count must
    still land on the repo root, not on `apps/`. This is the exact arithmetic
    that was wrong before (parents[4] -> apps/); pinning parents[5] here
    means a future refactor that moves this file will fail this test loudly
    instead of silently mis-writing output again."""
    import backend.services.sota_loop.m13_weekly as m13_weekly_module

    module_file = Path(m13_weekly_module.__file__).resolve()
    assert module_file.parents[5] == _THIS_REPO_ROOT
    assert module_file.parents[4].name == "apps"


def test_derivation_rejects_a_toplevel_without_the_repo_signature(monkeypatch, tmp_path) -> None:
    """GUILT: if `git rev-parse --show-toplevel` ever resolves to somewhere
    that is NOT this repo (e.g. this file got HOME-fork-copied to a location
    inside an unrelated git checkout — cicatrix superscar #1), the signature
    guard must refuse to trust it and fall through to the file-relative
    fallback, rather than silently writing output under a foreign root. This
    is exercised by mocking the subprocess boundary directly (the function
    hardcodes cwd=this-file's-own-directory, so a plain chdir in the test
    would not reach the code path it claims to exercise — the mock is the
    honest way to inject the failure)."""
    monkeypatch.delenv("NUZANTARA_REPO_ROOT", raising=False)
    foreign_root = tmp_path / "not-nuzantara"
    foreign_root.mkdir()

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = f"{foreign_root}\n"
    monkeypatch.setattr(
        subprocess, "run", MagicMock(return_value=fake_result)
    )

    root = _repo_root()

    # Rejected the mocked-foreign toplevel and fell all the way through to
    # the file-relative fallback — which lands on the real repo root.
    assert root != foreign_root
    assert root == _THIS_REPO_ROOT
