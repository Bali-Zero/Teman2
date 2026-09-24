"""Tests for scripts/mutation_incremental.py's mutmut-exit-code handling (L1627).

THE DEFECT: `_run_mutmut_on_targets` passed `check=False` to `subprocess.run`
and never read `proc.returncode` — a mutmut invocation that exited non-zero
having done nothing (crashed, misconfigured, killed) fell straight through to
`_parse_mutmut_survivors(proc.stdout, path)`, which returns `[]` on empty
output, and the driver then reported `STRATO-2 PASS`. The docstring three
lines above the defect claimed the opposite ("a mutmut harness error must not
silently PASS a real regression"). Reproducer from the ledger: a stub
`mutmut` on PATH that does nothing but `exit 2` made the driver log
`STRATO-2 PASS` and return `EXIT_PASS`.

THE FIX: `_run_mutmut_on_targets` now reads `proc.returncode` and raises
`MutmutHarnessError` on any non-zero exit; `main()` catches it and returns
`EXIT_FAIL` instead of evaluating an untrustworthy (possibly empty) survivor
list.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from mutation_incremental import (  # noqa: E402
    ChangedLines,
    MutmutHarnessError,
    _run_mutmut_on_targets,
)


def _fake_proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["mutmut"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_guilt_nonzero_exit_raises_instead_of_silent_pass(monkeypatch):
    """A stub mutmut that exits 2 with no output must FAIL, not report zero
    survivors — the exact reproducer named in the ledger row (L1627)."""
    import mutation_incremental as mod

    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **k: _fake_proc(2, stdout="", stderr="boom")
    )
    target = ChangedLines(by_file={"apps/backend-rag/backend/app/x.py": frozenset({1})})
    with pytest.raises(MutmutHarnessError):
        _run_mutmut_on_targets(target, seed=1)


def test_innocence_zero_exit_zero_survivors_still_passes(monkeypatch):
    """A real mutmut run that exits 0 with no surviving mutants must still
    return an empty (not exceptional) survivor list — the fix must not turn
    every clean run red."""
    import mutation_incremental as mod

    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **k: _fake_proc(0, stdout="1/1  🎉 1 KILLED\n")
    )
    target = ChangedLines(by_file={"apps/backend-rag/backend/app/x.py": frozenset({1})})
    survivors = _run_mutmut_on_targets(target, seed=1)
    assert survivors == []


def test_innocence_zero_exit_with_survivor_is_still_parsed(monkeypatch):
    """A real mutmut run that exits 0 but DID leave a survivor must still be
    parsed and reported — the fix only tightens the non-zero-exit path."""
    import mutation_incremental as mod

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *a, **k: _fake_proc(0, stdout="#7: Survived 🙁 (1)\n"),
    )
    target = ChangedLines(by_file={"apps/backend-rag/backend/app/x.py": frozenset({1})})
    survivors = _run_mutmut_on_targets(target, seed=1)
    assert [s.key for s in survivors] == ["apps/backend-rag/backend/app/x.py#7"]
