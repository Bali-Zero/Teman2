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
import re
import shutil
import subprocess
import sys
import uuid
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
# ---------------------------------------------------------------- wrapper command-path (Group A)
#
# Every test above that actually executes hermetic_verify.sh calls it with
# ONLY `--self-test-only` — the canary path. None of them ever pass a real
# command after `--`, so a mutation collapsing `"$@"` to `true` at step 5
# ("run + propagate") would leave every test in this file green: the
# wrapper's actual job — running the caller's command and handing back its
# exit code — was untested by anything here. These drive the real
# `-- <command...>` path end to end.


def test_command_exit_code_0_is_propagated() -> None:
    proc = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--", "true"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"`-- true` did not propagate as exit 0 (rc={proc.returncode}): "
        f"{proc.stderr.strip()}"
    )


def test_command_exit_code_7_is_propagated() -> None:
    proc = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--", "bash", "-c", "exit 7"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 7, (
        f"a command exiting 7 was not propagated as 7 (rc={proc.returncode}): "
        f"{proc.stderr.strip()}"
    )


def test_command_exit_code_127_is_propagated_for_a_missing_binary() -> None:
    proc = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--", "no_such_binary_xyz_hermetic_census_probe"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 127, (
        "a missing binary did not propagate bash's own 127 "
        f"(rc={proc.returncode}): {proc.stderr.strip()}"
    )


def test_dashdash_with_no_command_after_it_exits_2() -> None:
    """`--` with NOTHING after it — an empty command must never read as
    success (the wrapper's own contract, exit code 2)."""
    proc = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, (
        f"`--` with no command did not exit 2 (rc={proc.returncode}): "
        f"{proc.stderr.strip()}"
    )
    assert "no command given" in proc.stderr, (
        f"exit 2 fired, but not for the empty-command reason: {proc.stderr.strip()}"
    )


def test_the_wrapped_command_actually_runs(tmp_path: Path) -> None:
    """THE test that kills `"$@"` -> `true`. Give the wrapper a command
    whose side effect (a sentinel file) exists only if the command itself
    ran — not merely if the wrapper exited 0."""
    sentinel = tmp_path / "sentinel.txt"
    assert not sentinel.exists()
    proc = subprocess.run(
        ["bash", str(_WRAPPER_PATH), "--", "bash", "-c", f"echo ran > {sentinel}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"the sentinel-writing command failed (rc={proc.returncode}): "
        f"{proc.stderr.strip()}"
    )
    assert sentinel.exists(), (
        "the wrapper exited 0 but the wrapped command's own side effect "
        'never happened — this is exactly what `"$@"` collapsed to `true` '
        "looks like, and every other test in this file would stay green"
    )
    assert sentinel.read_text().strip() == "ran"


def test_hermetic_env_reaches_the_wrapped_child() -> None:
    """The exported PYTHONDONTWRITEBYTECODE and PYTEST_ADDOPTS must reach
    the CHILD process, not merely exist in the wrapper's own shell. Run with
    the ambient value stripped first (`_env_without_hermetic`, below) so a
    passing child value cannot be the caller's own export leaking through,
    unrelated to anything the wrapper itself did."""
    proc = subprocess.run(
        [
            "bash",
            str(_WRAPPER_PATH),
            "--",
            "python3",
            "-c",
            "import os; print(os.environ.get('PYTHONDONTWRITEBYTECODE')); "
            "print(os.environ.get('PYTEST_ADDOPTS'))",
        ],
        cwd=_REPO_ROOT,
        env=_env_without_hermetic(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"the probe command failed (rc={proc.returncode}): {proc.stderr.strip()}"
    )
    lines = proc.stdout.strip().splitlines()
    assert lines[0] == "1", (
        "PYTHONDONTWRITEBYTECODE did not reach the wrapped child as '1': "
        f"got {lines[0]!r} (full stdout={proc.stdout!r})"
    )
    assert "-p no:cacheprovider" in lines[1], (
        "PYTEST_ADDOPTS did not carry -p no:cacheprovider into the wrapped "
        f"child: got {lines[1]!r}"
    )


# ---------------------------------------------------------------- SWEPT_TREES / PRUNED_DIRS pins (Group B)
#
# SWEPT_TREES was WRONG on first write ("scripts apps"), missing
# "packages/" even though scripts/mutation_incremental.py's own
# include_glob default already mutates files there — found by the
# cross-family refuter against the FINISHED diff, because nothing pinned
# the two lists against each other. PYTHONDONTWRITEBYTECODE suppresses
# WRITES, never READS, so a tree the sweep does not cover is a tree whose
# stale bytecode the measurement below can still read. These tests parse
# both constants out of the live source (never re-derive them by hand,
# which would drift the moment either side changes).

_SWEPT_TREES_RE = re.compile(r'^SWEPT_TREES="([^"]*)"', re.MULTILINE)
_PRUNED_DIRS_RE = re.compile(r'^PRUNED_DIRS="([^"]*)"', re.MULTILINE)
_INCLUDE_GLOB_RE = re.compile(r"include_glob:\s*Sequence\[str\]\s*=\s*\(([^)]*)\)")
_MUTATION_DRIVER_PATH = _REPO_ROOT / "scripts" / "mutation_incremental.py"


def test_swept_trees_is_a_superset_of_the_drivers_include_glob() -> None:
    """PREMISE CHECK first: if either regex stops matching the source it is
    supposed to read, the pin has stopped pinning and must fail loudly
    rather than silently comparing two empty sets and reporting clean."""
    wrapper_text = _WRAPPER_PATH.read_text(encoding="utf-8")
    swept_match = _SWEPT_TREES_RE.search(wrapper_text)
    assert swept_match, (
        'SWEPT_TREES="..." not found in hermetic_verify.sh — the pin '
        "stopped matching, so it stopped pinning"
    )
    swept_trees = set(swept_match.group(1).split())
    assert swept_trees, "SWEPT_TREES matched but parsed to an empty set"

    driver_text = _MUTATION_DRIVER_PATH.read_text(encoding="utf-8")
    include_match = _INCLUDE_GLOB_RE.search(driver_text)
    assert include_match, (
        "include_glob default not found in mutation_incremental.py — the "
        "pin stopped matching, so it stopped pinning"
    )
    include_glob = re.findall(r'"([^"]*)"', include_match.group(1))
    assert include_glob, "include_glob matched but parsed to an empty list"

    missing = sorted({tree.rstrip("/") for tree in include_glob} - swept_trees)
    assert not missing, (
        f"SWEPT_TREES={sorted(swept_trees)} does not cover include_glob "
        f"tree(s) {missing} — a tree the sweep misses is a tree whose "
        "stale bytecode gets READ (PYTHONDONTWRITEBYTECODE suppresses "
        "writes, not reads), exactly the gap the cross-family refuter "
        "found on the finished diff"
    )


def test_pruned_dirs_covers_the_measured_vendor_trees() -> None:
    """3216 of 3679 __pycache__ dirs under apps/ in the main checkout live
    inside a virtualenv or node_modules (measured 2026-08-29, re-measured
    here before writing this docstring: find apps -type d -name
    __pycache__) — sweeping them costs minutes of pointless recompilation
    per invocation and buys nothing, since the instruments mutate
    first-party source only."""
    wrapper_text = _WRAPPER_PATH.read_text(encoding="utf-8")
    pruned_match = _PRUNED_DIRS_RE.search(wrapper_text)
    assert pruned_match, (
        'PRUNED_DIRS="..." not found in hermetic_verify.sh — the pin '
        "stopped matching, so it stopped pinning"
    )
    pruned_dirs = set(pruned_match.group(1).split())
    required = {".venv", "node_modules", "site-packages", ".git"}
    missing = sorted(required - pruned_dirs)
    assert not missing, (
        f"PRUNED_DIRS={sorted(pruned_dirs)} is missing {missing} — sweeping "
        "a vendor tree that cannot hold stale bytecode for a first-party "
        "mutation is pure cost with no correctness gain"
    )


# ---------------------------------------------------------------- post-run defeat detection (Group C)
#
# The self-canary (exercised above via --self-test-only) proves the
# environment was hermetic BEFORE a command runs. Step 6 of
# hermetic_verify.sh is what proves the command did not defeat it mid-run —
# an accepted limitation the refuter treated as measurable rather than
# merely declared. These tests drive the REAL wrapper end to end against a
# real `.py` module planted directly under this repo's tracked packages/
# tree (a SWEPT_TREES member): the post-run check inspects THIS repo's
# SWEPT_TREES, not a fixture tree elsewhere, so the probe must actually
# live there.


def _make_packages_probe() -> tuple[str, Path]:
    """Writes a throwaway `.py` module directly under packages/ and returns
    (module_name, packages_dir). Caller MUST clean up via
    `_cleanup_packages_probe`, including on failure — a `finally` block."""
    probe_dir = _REPO_ROOT / "packages"
    name = f"_hermetic_census_probe_{uuid.uuid4().hex[:12]}"
    (probe_dir / f"{name}.py").write_text("VALUE = 1\n", encoding="utf-8")
    return name, probe_dir


def _cleanup_packages_probe(name: str, probe_dir: Path) -> None:
    (probe_dir / f"{name}.py").unlink(missing_ok=True)
    for pyc in (probe_dir / "__pycache__").glob(f"{name}.*"):
        pyc.unlink(missing_ok=True)


def test_post_run_check_catches_a_command_that_defeats_the_env() -> None:
    """GUILT (Group C1): `env -u PYTHONDONTWRITEBYTECODE` around the
    child's own python3 call re-enables bytecode writing for that one
    process, despite the wrapper's export. A .pyc lands under packages/ and
    the post-run check must refuse to certify the run as hermetic — even
    though the wrapped command itself exited 0."""
    name, probe_dir = _make_packages_probe()
    try:
        proc = subprocess.run(
            [
                "bash",
                str(_WRAPPER_PATH),
                "--",
                "env",
                "-u",
                "PYTHONDONTWRITEBYTECODE",
                "python3",
                "-c",
                f"import {name}",
            ],
            cwd=str(probe_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        _cleanup_packages_probe(name, probe_dir)

    assert proc.returncode == 3, (
        "a command that used `env -u PYTHONDONTWRITEBYTECODE` to defeat "
        f"the hermetic environment was not caught (rc={proc.returncode}): "
        f"{proc.stderr.strip()}"
    )
    assert "POST-RUN CHECK FAILED" in proc.stderr, (
        f"the wrapper failed, but not via the post-run check: {proc.stderr.strip()}"
    )


def test_post_run_check_stays_clean_when_the_command_keeps_the_env() -> None:
    """INNOCENCE (Group C2): the IDENTICAL command WITHOUT `env -u` must
    exit 0. The pair differs in exactly one thing — this is what makes C1
    discriminating rather than decorative."""
    name, probe_dir = _make_packages_probe()
    try:
        proc = subprocess.run(
            ["bash", str(_WRAPPER_PATH), "--", "python3", "-c", f"import {name}"],
            cwd=str(probe_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        _cleanup_packages_probe(name, probe_dir)

    assert proc.returncode == 0, (
        "the identical command without `env -u` should leave the hermetic "
        f"environment intact (rc={proc.returncode}): {proc.stderr.strip()}"
    )


# ---------------------------------------------------------------- lint block-scalar / earlier-line bypasses (Group D)
#
# Both bypasses below were live on the finished diff before the
# cross-family refuter caught them, exercised directly on
# find_run_blocks/find_unwrapped_mentions (the same functions
# evaluate_workflows drives per block), not through a workflow file on
# disk.


def test_lint_an_earlier_already_exited_wrapper_line_does_not_excuse_the_next_one() -> None:
    """GUILT: `run: |` block, line 1 a complete wrapper self-test call,
    line 2 a bare instrument call with NO backslash continuation between
    them. "Wrapper mentioned somewhere earlier in this block" is not the
    same claim as "wrapping THIS invocation" — line 1 already ran and
    exited by the time line 2 runs bare. Measured as a live bypass by the
    cross-family refuter."""
    text = (
        "jobs:\n"
        "  x:\n"
        "    steps:\n"
        "      - run: |\n"
        "          bash scripts/hermetic_verify.sh --self-test-only\n"
        f"          python3 {_INSTRUMENT} -v\n"
    )
    blocks = lint.find_run_blocks(text, "earlier-line.yml")
    assert len(blocks) == 1
    violations = lint.find_unwrapped_mentions(blocks[0], (_INSTRUMENT,))
    assert len(violations) == 1, (
        "the instrument line must be reported as unwrapped — a completed, "
        "already-exited wrapper call on an earlier line does not protect "
        f"it, got {violations}"
    )


def test_lint_block_scalar_indentation_indicator_is_recognised() -> None:
    """GUILT: `run: |2` (an explicit YAML indentation indicator). The
    first version of the block-scalar regex accepted only the chomping
    indicator, so `|2` fell through to the single-line branch and NONE of
    the block's following lines were ever scanned — a silent false
    NEGATIVE, i.e. a working bypass of this entire lint via one digit.
    Found by the cross-family refuter; reproduced here before fixing."""
    text = (
        "jobs:\n"
        "  x:\n"
        "    steps:\n"
        "      - run: |2\n"
        f"          python3 {_INSTRUMENT} -v\n"
    )
    blocks = lint.find_run_blocks(text, "block-indicator.yml")
    assert len(blocks) == 1, (
        "`run: |2` was not recognised as a block scalar — its content "
        f"line(s) were never scanned at all, got {len(blocks)} block(s) "
        f"with lines {[b.lines for b in blocks]}"
    )
    violations = lint.find_unwrapped_mentions(blocks[0], (_INSTRUMENT,))
    assert len(violations) == 1, (
        "expected the bare instrument line under `run: |2` to be caught, "
        f"got {violations}"
    )


def test_lint_same_line_wrapped_invocation_is_innocent() -> None:
    """INNOCENCE, paired with the two guilt tests above: the ordinary
    wrapped single-line shape must not be flagged."""
    text = (
        "jobs:\n"
        "  x:\n"
        "    steps:\n"
        f"      - run: bash scripts/hermetic_verify.sh -- python3 {_INSTRUMENT} -v\n"
    )
    blocks = lint.find_run_blocks(text, "same-line.yml")
    assert len(blocks) == 1
    violations = lint.find_unwrapped_mentions(blocks[0], (_INSTRUMENT,))
    assert violations == [], f"a properly wrapped same-line call was flagged: {violations}"


def test_lint_backslash_continued_wrapping_is_innocent() -> None:
    """INNOCENCE: the legitimate multi-line wrapping shape (wrapper on one
    line ending in a backslash, instrument on the next) must not be
    flagged — this is the shape `_continues_to` exists to keep working
    while the earlier-already-exited-line bypass above is closed."""
    text = (
        "jobs:\n"
        "  x:\n"
        "    steps:\n"
        "      - run: |\n"
        "          bash scripts/hermetic_verify.sh -- \\\n"
        f"            python3 {_INSTRUMENT} -v\n"
    )
    blocks = lint.find_run_blocks(text, "continued.yml")
    assert len(blocks) == 1
    violations = lint.find_unwrapped_mentions(blocks[0], (_INSTRUMENT,))
    assert violations == [], (
        f"a legitimately backslash-continued wrapped call was flagged: {violations}"
    )


# ---------------------------------------------------------------- workflow wiring (Group E)
#
# push: paths: and the pull_request "Did relevant paths change?" step's
# grep regex are one relevance decision expressed for two event shapes
# (workflow comment, "the two are one relevance decision..."). Before the
# fix, the grep regex was missing the three W121 trust-path entries the
# push filter already had: a PR editing ONLY the wrapper — including one
# disabling it — never triggered this gate's own self-canary. Found by the
# cross-family refuter.

_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "p1s2-mutation-incremental.yml"
_REQUIRED_RELEVANT_PATHS = {
    "scripts/mutation_incremental.py",
    "scripts/test_mutation_incremental.py",
    ".github/workflows/p1s2-mutation-incremental.yml",
    "scripts/hermetic_verify.sh",
    "scripts/ci/lint_hermetic_instruments.py",
    "scripts/tests/test_hermetic_census.py",
}


def _extract_indented_block(text: str, key_line_re: re.Pattern[str]) -> str | None:
    """Every line strictly more indented than a line matching key_line_re,
    stopping at the first non-blank line that is not — same convention as
    lint_hermetic_instruments.find_run_blocks' block-scalar scan. Returns
    None if key_line_re never matches anything (the caller's premise
    check)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not key_line_re.match(line):
            continue
        key_indent = len(line) - len(line.lstrip(" "))
        block_lines: list[str] = []
        for nxt in lines[i + 1 :]:
            if nxt.strip() == "":
                block_lines.append(nxt)
                continue
            if len(nxt) - len(nxt.lstrip(" ")) <= key_indent:
                break
            block_lines.append(nxt)
        return "\n".join(block_lines)
    return None


def test_push_paths_and_pull_request_grep_regex_are_the_same_set() -> None:
    """PREMISE CHECK first: if either extraction stops matching, the pin
    has stopped pinning and must fail loudly rather than comparing two
    empty/partial sets and reporting clean."""
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")

    push_block = _extract_indented_block(text, re.compile(r"^    paths:\s*$"))
    assert push_block is not None, (
        "no `    paths:` key found under push: in "
        "p1s2-mutation-incremental.yml — the pin stopped matching, so it "
        "stopped pinning"
    )
    # Comment-stripped BEFORE extraction. A cross-family refuter (round 2)
    # showed this test passed for the wrong reason without it: the extraction
    # is a bare quoted-string scan, so
    #     paths:
    #       # - "scripts/hermetic_verify.sh"
    # still "contains" the path and satisfies the assertion, while GitHub does
    # not treat a commented line as an active path at all. Commenting out a
    # trigger is the cheapest possible way to disarm this workflow, and it is
    # exactly what this pin exists to catch. (Same form-for-entity mistake the
    # census lint itself had to fix earlier in this PR — a lint that counted a
    # wrapper mention inside a `#` comment as protection.)
    push_lines = [ln for ln in push_block.splitlines() if not ln.lstrip().startswith("#")]
    push_paths = set(re.findall(r'"([^"]*)"', "\n".join(push_lines)))
    assert push_paths, "push: paths: matched but parsed to an empty set"

    grep_match = re.search(r"grep -qE \\\n\s+'\^\(([^)]*)\)\$'", text)
    assert grep_match, (
        'the anchored grep alternation in the "Did relevant paths change?" '
        "step was not found — the pin stopped matching, so it stopped "
        "pinning"
    )
    grep_paths = {alt.replace("\\.", ".") for alt in grep_match.group(1).split("|")}
    assert grep_paths, "grep regex matched but parsed to an empty set"

    assert push_paths == grep_paths, (
        f"push: paths: {sorted(push_paths)} and the pull_request grep "
        f"regex {sorted(grep_paths)} have DIVERGED — they are one "
        "relevance decision expressed for two event shapes and must name "
        "the exact same paths, or a push-triggered run and a "
        "pull_request-triggered run disagree about which changes matter"
    )
    missing_from_push = _REQUIRED_RELEVANT_PATHS - push_paths
    missing_from_grep = _REQUIRED_RELEVANT_PATHS - grep_paths
    assert not missing_from_push and not missing_from_grep, (
        f"missing from push: paths:: {sorted(missing_from_push)}; missing "
        f"from the grep regex: {sorted(missing_from_grep)} — omitting any "
        "of the W121 trust-path files means a PR editing ONLY that file "
        "(including one disabling it) never runs this gate's own "
        "self-canary (superscar #2 / W108)"
    )


def test_the_workflow_EXECUTES_the_census_and_the_corpus_not_merely_triggers_on_them() -> None:
    """Trigger membership is not execution, and this PR shipped that confusion.

    The sibling test above pins that the wrapper, the census lint and this
    corpus appear in `push: paths:` and in the sentinel regex. That makes the
    workflow RUN when they change. It says nothing about whether the workflow
    ever invokes them — and it did not: a round-2 cross-family refuter found
    `lint_hermetic_instruments.py` named in this repo's workflows ONLY as a
    trigger path, and this corpus executed nowhere but `scripts/tests/ sweep`,
    which is `continue-on-error: true` and in no required context.

    So the census that enforces "every instrument runs wrapped" was itself
    unenforced, and the corpus proving the wrapper works could not go red.
    Third instance of superscar #2 found inside this single PR, and the one
    the PR's own commit message accuses its predecessor of.

    The two are pinned with different strictness on purpose, matching how they
    are wired: the lint must be invoked UNCONDITIONALLY (its subject is every
    workflow in the tree, including ones this workflow's sentinel never
    matches), the corpus may be relevance-gated (its subject is this
    workflow's own trust-path files).
    """
    wf = _REPO_ROOT / ".github" / "workflows" / "p1s2-mutation-incremental.yml"
    assert wf.is_file(), f"{wf} is missing — this pin cannot verify anything"
    lines = wf.read_text(encoding="utf-8").splitlines()

    def _invocation_line(needle: str) -> int | None:
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("run:") and needle in stripped:
                return i
        return None

    lint_at = _invocation_line("scripts/ci/lint_hermetic_instruments.py")
    corpus_at = _invocation_line("scripts/tests/test_hermetic_census.py")

    missing = [
        name
        for name, at in (
            ("the census lint", lint_at),
            ("this corpus", corpus_at),
        )
        if at is None
    ]
    assert not missing, (
        f"{wf.name} does not INVOKE {missing} in any `run:` step — it only "
        "names them under `paths:`/the sentinel regex, which decides WHETHER "
        "THE JOB RUNS, never whether these are executed. A guard that is "
        "triggered but not invoked is disarmed with a green check on top."
    )

    # The lint must not be relevance-gated. Walk back to its step's `if:`, if
    # any: a gated census cannot see a bare invocation added to an unrelated
    # workflow, which is the case it exists for.
    assert lint_at is not None  # narrowed by the assertion above
    step_start = lint_at
    while step_start > 0 and not lines[step_start].lstrip().startswith("- name:"):
        step_start -= 1
    gated = any(
        lines[i].strip().startswith("if:")
        for i in range(step_start, lint_at)
    )
    assert not gated, (
        "the census lint step carries an `if:` condition. It must run on every "
        "PR: a PR that adds a bare instrument invocation to an UNRELATED "
        "workflow touches none of this workflow's sentinel paths, so a gated "
        "census would never see the one edit it is for."
    )


# --------------------------------------------------------------------------
# The census bypass matrix. Three successive proximity rules were each
# defeated by their own twin — "anywhere earlier in the block" by a completed
# call on the line above; "same line or backslash-joined" by `&& \` on the
# joining line; "reject separators before the backslash" by the same separator
# on ONE line. Every version answered "is a wrapper mention NEAR this
# instrument?" when the question is "is this instrument running INSIDE a
# wrapped command?".
#
# The rule is now shell-command segmentation, and this table is the reason it
# cannot be quietly replaced by a fourth proximity heuristic: every historical
# bypass is here as a named row, so a regression re-opens a row rather than
# passing silently.
# --------------------------------------------------------------------------
_CENSUS_GUILT = [
    (
        "round-1 bypass: a COMPLETED wrapper call on the line above",
        "        - name: x\n          run: |\n            bash scripts/hermetic_verify.sh --self-test-only\n            python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "round-2 bypass: `&&` before the backslash continuation",
        "        - name: x\n          run: |\n            bash scripts/hermetic_verify.sh --self-test-only && \\\n              python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "round-3 bypass: the SAME shape on one line, `;` separator",
        "        - name: x\n          run: bash scripts/hermetic_verify.sh -- echo ok; python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "round-3 bypass: the SAME shape on one line, `&&` separator",
        "        - name: x\n          run: bash scripts/hermetic_verify.sh -- true && python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "round-3 bypass: the SAME shape on one line, pipe separator",
        "        - name: x\n          run: bash scripts/hermetic_verify.sh -- true | python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "block-scalar indentation indicator left the block unscanned",
        "        - name: x\n          run: |2\n            python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "block-scalar trailing YAML comment left the block unscanned",
        "        - name: x\n          run: | # keep hermetic\n            python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "a wrapper mention inside a shell COMMENT is not protection",
        "        - name: x\n          run: |\n            # bash scripts/hermetic_verify.sh -- disabled\n            python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "the plainest case: a bare invocation",
        "        - name: x\n          run: python3 scripts/mutation_incremental.py -v\n",
    ),
]

_CENSUS_INNOCENCE = [
    (
        "same-line wrapping",
        "        - name: x\n          run: bash scripts/hermetic_verify.sh -- python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "multi-line wrapping via a genuine continuation",
        "        - name: x\n          run: |\n            bash scripts/hermetic_verify.sh -- \\\n              python3 scripts/mutation_incremental.py -v\n",
    ),
    (
        "a wrapped invocation piped to tee — the pipe does not orphan it",
        "        - name: x\n          run: bash scripts/hermetic_verify.sh -- python3 scripts/mutation_incremental.py -v 2>&1 | tee log\n",
    ),
]


def _census_violations(yaml_text: str) -> int:
    total = 0
    for block in lint.find_run_blocks(yaml_text, "fixture.yml"):
        total += len(lint.find_unwrapped_mentions(block, lint.INSTRUMENTS))
    return total


@pytest.mark.parametrize("label,fixture", _CENSUS_GUILT, ids=[x[0] for x in _CENSUS_GUILT])
def test_census_catches_every_historical_bypass(label: str, fixture: str) -> None:
    assert _census_violations(fixture) > 0, (
        f"the census did NOT flag: {label}. Each row here defeated a previous "
        "version of this rule; a green row means a proximity heuristic has "
        "crept back in."
    )


@pytest.mark.parametrize("label,fixture", _CENSUS_INNOCENCE, ids=[x[0] for x in _CENSUS_INNOCENCE])
def test_census_does_not_flag_a_legitimately_wrapped_invocation(label: str, fixture: str) -> None:
    assert _census_violations(fixture) == 0, (
        f"the census FALSELY flagged: {label}. Closing a bypass by refusing "
        "every wrapping shape is not closing it."
    )


def test_a_FAILING_command_keeps_its_own_exit_code_even_when_it_defeats_the_env(tmp_path: Path) -> None:
    """The post-run check must not overwrite a real failure with a generic 3.

    A refuter mutated `if [ "$rc" -eq 0 ]` to `if true` and the whole corpus
    stayed green: the wrapper's deliberate asymmetry — a green produced under a
    defeated environment becomes 3, a red keeps its own code because that code
    carries more information — was narrated in the header and pinned by nothing.
    """
    probe_pkg = _REPO_ROOT / "packages" / f"_hv_failpin_{uuid.uuid4().hex[:8]}"
    probe_pkg.mkdir(parents=True, exist_ok=True)
    (probe_pkg / "__init__.py").write_text("X = 1\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            [
                "bash", str(_WRAPPER_PATH), "--",
                "env", "-u", "PYTHONDONTWRITEBYTECODE", "python3", "-c",
                f"import sys; sys.path.insert(0, {str(_REPO_ROOT / 'packages')!r}); "
                f"import {probe_pkg.name}; sys.exit(7)",
            ],
            capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=120,
        )
        assert proc.returncode == 7, (
            "a command that FAILED and also defeated the environment must keep its own "
            f"exit code, not be flattened to 3 — got {proc.returncode}"
        )
        assert "WARNING" in proc.stderr and "defeated" in proc.stderr, (
            "the defeat must still be reported loudly on a failing run; stderr was: "
            f"{proc.stderr[-400:]}"
        )
    finally:
        shutil.rmtree(probe_pkg, ignore_errors=True)
        for cache in (_REPO_ROOT / "packages").rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def test_an_ambient_PYTHONPYCACHEPREFIX_does_not_reach_the_child() -> None:
    """`unset PYTHONPYCACHEPREFIX` is load-bearing and was pinned by nothing.

    A refuter deleted that line and the corpus stayed green. An inherited
    redirect target makes the write-suppression meaningless for whatever path
    it points at — and the sweep, which is what actually protects an
    already-poisoned checkout, would then be sweeping the wrong place.

    This pins the ordinary case the wrapper CAN control (a prefix inherited
    from its caller). It deliberately does not claim to cover a child that
    re-sets the variable itself — that limit is measured and declared in the
    wrapper's own header.
    """
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = "/tmp/should-not-survive-the-wrapper"
    proc = subprocess.run(
        [
            "bash", str(_WRAPPER_PATH), "--",
            "python3", "-c", "import os; print(os.environ.get('PYTHONPYCACHEPREFIX', 'UNSET'))",
        ],
        capture_output=True, text=True, cwd=str(_REPO_ROOT), env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert proc.stdout.strip().endswith("UNSET"), (
        "an ambient PYTHONPYCACHEPREFIX reached the child — the wrapper's `unset` "
        f"is not doing its job. child saw: {proc.stdout.strip()!r}"
    )
