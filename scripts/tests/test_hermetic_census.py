"""Guilt + innocence + blind-scan guards for scripts/ci/lint_hermetic_instruments.py,
plus a real reproduction of the W121 stale-bytecode trap driving
scripts/hermetic_verify.sh (cicatrix-scars.md W121).

Every fixture repo built here is a throwaway tmp_path tree, never the real
repo — `lint.discover_tracked_workflows` (which shells out to `git
ls-files`) is monkeypatched to return an explicit file list instead of
requiring a real git init per fixture, same convention as
scripts/tests/test_lint_pg_dsn_credentials.py's `_tracked_files` patch.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LINT_PATH = _REPO_ROOT / "scripts" / "ci" / "lint_hermetic_instruments.py"
_WRAPPER_PATH = _REPO_ROOT / "scripts" / "hermetic_verify.sh"

_SPEC = importlib.util.spec_from_file_location("lint_hermetic_instruments", _LINT_PATH)
assert _SPEC and _SPEC.loader
lint = importlib.util.module_from_spec(_SPEC)
sys.modules["lint_hermetic_instruments"] = lint
_SPEC.loader.exec_module(lint)

_INSTRUMENT = "scripts/mutation_incremental.py"


def _make_repo(tmp_path: Path, *, with_instrument: bool = True) -> Path:
    if with_instrument:
        instrument = tmp_path / _INSTRUMENT
        instrument.parent.mkdir(parents=True, exist_ok=True)
        instrument.write_text("# fixture instrument\n")
    return tmp_path


def _write_workflow(root: Path, name: str, run_line: str) -> Path:
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    path = wf_dir / name
    path.write_text(f"jobs:\n  x:\n    steps:\n      - {run_line}\n")
    return path


# ---------------------------------------------------------------- guilt/innocence


def test_guilt_a_bare_instrument_invocation_exits_one(tmp_path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    wf = _write_workflow(root, "guilty.yml", f"run: python3 {_INSTRUMENT} -v")
    monkeypatch.setattr(lint, "discover_tracked_workflows", lambda repo_root: [wf])
    assert lint.main(["--repo-root", str(root)]) == 1


def test_innocence_the_same_invocation_wrapped_exits_zero(tmp_path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    wf = _write_workflow(
        root,
        "wrapped.yml",
        f"run: bash scripts/hermetic_verify.sh -- python3 {_INSTRUMENT} -v",
    )
    monkeypatch.setattr(lint, "discover_tracked_workflows", lambda repo_root: [wf])
    assert lint.main(["--repo-root", str(root)]) == 0


def test_guilt_a_COMMENTED_OUT_wrapper_does_not_count_as_a_wrapper(
    tmp_path, monkeypatch
) -> None:
    """`# scripts/hermetic_verify.sh -- disabled` above a bare instrument call.

    Measured before the cure: the lint matched the wrapper's path string
    anywhere in the block, comments included, so disabling the wrapper by
    commenting it out left the guard GREEN. That is the same form-for-entity
    substitution the lint exists to stop, committed inside the lint.
    """
    root = _make_repo(tmp_path)
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf = wf_dir / "commented.yml"
    wf.write_text(
        "jobs:\n"
        "  x:\n"
        "    steps:\n"
        "      - run: |\n"
        "          # scripts/hermetic_verify.sh -- disabled for now\n"
        f"          python3 {_INSTRUMENT} -v\n"
    )
    monkeypatch.setattr(lint, "discover_tracked_workflows", lambda repo_root: [wf])
    rc = lint.main(["--repo-root", str(root)])
    assert rc == 1, (
        "a wrapper mention inside a shell comment was accepted as an "
        f"invocation (rc={rc}) — the guard read the FORM, not the entity"
    )


def test_innocence_a_workflow_that_never_mentions_the_instrument_exits_zero(
    tmp_path, monkeypatch
) -> None:
    root = _make_repo(tmp_path)
    wf = _write_workflow(root, "unrelated.yml", "run: echo hello")
    monkeypatch.setattr(lint, "discover_tracked_workflows", lambda repo_root: [wf])
    assert lint.main(["--repo-root", str(root)]) == 0


def test_the_embedded_selftest_passes() -> None:
    assert lint.selftest() == 0


# ---------------------------------------------------------------- blind-scan guards


def test_zero_workflows_scanned_is_cannot_verify_not_a_pass(tmp_path, monkeypatch) -> None:
    """W84 'esiste != armato': an empty scan must never read as clean (exit 0)."""
    root = _make_repo(tmp_path)
    monkeypatch.setattr(lint, "discover_tracked_workflows", lambda repo_root: [])
    assert lint.main(["--repo-root", str(root)]) == 3


def test_a_declared_but_missing_instrument_is_cannot_verify(tmp_path, monkeypatch) -> None:
    """A lint guarding a deleted/renamed file guards nothing."""
    root = _make_repo(tmp_path, with_instrument=False)
    wf = _write_workflow(root, "innocent.yml", "run: echo hello")
    monkeypatch.setattr(lint, "discover_tracked_workflows", lambda repo_root: [wf])
    assert lint.main(["--repo-root", str(root)]) == 3


# ---------------------------------------------------------------- live-tree assertion


def test_the_live_tree_has_zero_unwrapped_instrument_invocations(capsys) -> None:
    """Runs the real lint against the real repo — not a fixture. If this goes
    red, FAIL loudly with the violations printed; do not soften it."""
    rc = lint.main(["--repo-root", str(lint.REPO_ROOT)])
    captured = capsys.readouterr()
    assert rc == 0, (
        "the live tree has an unwrapped measurement-instrument invocation "
        f"(cicatrix W121):\n{captured.out}"
    )


# ---------------------------------------------------------------- W121 reproduction


def test_w121_stale_bytecode_reuse_is_real_on_this_machine_without_hermetic_env(
    tmp_path, monkeypatch
) -> None:
    """Reproduces W121's exact shape driving nothing but the bare interpreter
    (PYTHONDONTWRITEBYTECODE explicitly unset): mutate-preserving-length +
    restore-mtime while a `.pyc` from a prior import is still on disk. If
    this platform's Python does not cache bytecode by default, or happens to
    recompile anyway, this is not a hermetic_verify.sh defect — skip
    explicitly rather than silently pass (never claim a trap is real when it
    wasn't observed)."""
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    monkeypatch.delenv("PYTHONPYCACHEPREFIX", raising=False)

    probe = tmp_path / "probe.py"
    probe.write_text("def v():\n    return 11111\n")

    first = subprocess.run(
        [sys.executable, "-c", "import probe; print(probe.v())"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert first.returncode == 0, f"fresh probe import failed: {first.stderr}"
    assert first.stdout.strip() == "11111"

    if not (tmp_path / "__pycache__").is_dir():
        pytest.skip(
            "this interpreter did not cache bytecode for a fresh import with "
            "PYTHONDONTWRITEBYTECODE unset — the W121 trap's precondition "
            "does not hold on this platform, skipping rather than asserting "
            "a reproduction that was not observed"
        )

    mtime_ref = probe.stat().st_mtime, probe.stat().st_mtime_ns
    text = probe.read_text()
    mutated = text.replace("11111", "22222")
    assert mutated != text
    probe.write_text(mutated)
    import os

    os.utime(probe, ns=(mtime_ref[1], mtime_ref[1]))

    second = subprocess.run(
        [sys.executable, "-c", "import probe; print(probe.v())"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert second.returncode == 0, f"mutated probe import failed: {second.stderr}"

    if second.stdout.strip() == "22222":
        pytest.skip(
            "this interpreter recompiled the mutated probe instead of reusing "
            "stale bytecode — the W121 trap did not reproduce on this "
            "platform, skipping rather than asserting a reproduction that "
            "was not observed"
        )

    assert second.stdout.strip() == "11111", (
        "expected the stale-bytecode trap to reproduce (stale 11111) or to "
        "cleanly not reproduce (fresh 22222, handled above) — got neither, "
        "so the reproduction itself is unreliable on this platform"
    )


def test_hermetic_verify_self_test_only_exits_zero_when_hermetic() -> None:
    """The wrapper's OWN self-canary — internally it sets
    PYTHONDONTWRITEBYTECODE=1 before reproducing the same mutate/restore
    shape, so under a genuinely hermetic environment it must pass."""
    result = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--self-test-only"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"hermetic_verify.sh --self-test-only failed:\nstdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )


# --------------------------------------------------- the canary must be able to FAIL
#
# Everything above proves the wrapper exits 0 when the environment is already
# hermetic. That is worth nothing on its own: a canary that has lost the
# ability to fail exits 0 too, and this whole file exists because a green from
# an instrument that cannot go red is the disease, not the health.
#
# Both tests below therefore run with PYTHONDONTWRITEBYTECODE explicitly
# REMOVED from the child's environment. Measured: without that, the ambient
# value exported by whoever ran pytest is inherited, and a wrapper with its own
# export deleted still passes — the test proves the SHELL was hermetic, not the
# wrapper.


def _env_without_hermetic() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    return env


def test_wrapper_establishes_hermeticity_itself_not_inherited_from_the_caller() -> None:
    """The wrapper passes even when the caller's env is NOT hermetic."""
    proc = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--self-test-only"],
        cwd=_REPO_ROOT,
        env=_env_without_hermetic(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "the wrapper could not establish a hermetic environment on its own "
        f"(rc={proc.returncode}): {proc.stderr.strip()}"
    )


def test_a_wrapper_that_stopped_enforcing_the_env_is_CAUGHT_by_its_own_canary(
    tmp_path: Path,
) -> None:
    """GUILT: sabotage the wrapper's export, and its canary must refuse.

    This is the mutation that matters. A copy of the real wrapper — not a
    fixture reimplementation, which would drift — has its
    PYTHONDONTWRITEBYTECODE export renamed. Run in a non-hermetic environment
    it must exit 3 and say so, or the canary is decoration.
    """
    source = _WRAPPER_PATH.read_text(encoding="utf-8")
    marker = "export PYTHONDONTWRITEBYTECODE=1"
    assert marker in source, (
        "the wrapper no longer contains the export this test sabotages — the "
        "guard may have moved, and this test has silently stopped guarding"
    )
    sabotaged = tmp_path / "hermetic_verify_sabotaged.sh"
    sabotaged.write_text(
        source.replace(marker, "export HERMETIC_SABOTAGE_MARKER=1", 1),
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["bash", str(sabotaged), "--self-test-only"],
        cwd=_REPO_ROOT,
        env=_env_without_hermetic(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3, (
        "a wrapper that no longer exports PYTHONDONTWRITEBYTECODE still "
        f"reported success (rc={proc.returncode}) — its canary cannot fail, so "
        "its green means nothing"
    )
    assert "SELF-CANARY FAILED" in proc.stderr, (
        "the sabotaged wrapper failed, but not via the canary — it must be the "
        f"canary that refuses, not an unrelated error: {proc.stderr.strip()}"
    )
    # WHICH check fired is part of the contract. Without pinning it, deleting
    # any one of the canary's checks survives, because a surviving sibling
    # check catches the same sabotage and the test cannot tell them apart —
    # measured: two separate mutations both survived a message-blind assertion.
    assert "__pycache__ appeared" in proc.stderr, (
        "the export was removed, so the FIRST check to fire must be the "
        "__pycache__ probe. A different message means that check is gone and "
        f"a sibling caught the sabotage instead: {proc.stderr.strip()}"
    )


def test_the_stale_value_check_is_load_bearing_on_its_own(tmp_path: Path) -> None:
    """GUILT for the OTHER canary check, isolated from the first one.

    Sabotage the export AND neuter the __pycache__ probe, so only the
    stale-value comparison is left to notice. If it has been weakened, nothing
    refuses and the wrapper reports success on a compromised environment.
    """
    source = _WRAPPER_PATH.read_text(encoding="utf-8")
    export_marker = "export PYTHONDONTWRITEBYTECODE=1"
    pycache_marker = 'if [ "$_n_after_run1" -gt 0 ]; then'
    for marker in (export_marker, pycache_marker):
        assert marker in source, (
            f"the wrapper no longer contains {marker!r}; this test sabotages a "
            "guard that has moved, so it has silently stopped guarding"
        )
    sabotaged = tmp_path / "only_stale_check_left.sh"
    sabotaged.write_text(
        source.replace(export_marker, "export HERMETIC_SABOTAGE_MARKER=1", 1)
        .replace(pycache_marker, "if false; then", 1),
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["bash", str(sabotaged), "--self-test-only"],
        cwd=_REPO_ROOT,
        env=_env_without_hermetic(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3, (
        "with only the stale-value check left, a non-hermetic environment "
        f"still reported success (rc={proc.returncode})"
    )
    assert "still returned the OLD value" in proc.stderr, (
        "the refusal did not come from the stale-value comparison: "
        f"{proc.stderr.strip()}"
    )

