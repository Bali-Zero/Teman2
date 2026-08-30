"""Guilt and innocence for the pytest verbosity guard, and for its wiring.

The guard's whole claim is that it reads EFFECTIVE verbosity — config
``addopts`` plus argv — rather than argv alone. The pair that proves it is
``test_one_q_is_guilty_in_a_root_whose_config_already_sets_q`` against
``test_one_q_is_innocent_in_a_root_whose_config_does_not``: identical command
line, opposite verdict, and only the config differs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD_DIR = REPO_ROOT / "scripts" / "pytest_guards"
REFERENCE_CONFTEST = REPO_ROOT / "apps" / "backend-rag" / "conftest.py"

sys.path.insert(0, str(GUARD_DIR))

from config_roots import (  # noqa: E402
    pytest_config_roots,
    unwired_roots,
    winning_config,
)
from pytest_verbosity_guard import summary_is_suppressed  # noqa: E402

#: Roots deliberately left unwired, each with the reason visible here rather
#: than absent from a list. An exemption nobody can see is how a grandfather
#: list stops being reviewable.
EXEMPT_ROOTS = frozenset(
    {
        # Vendored third-party source. We do not add our own conftest to code
        # we re-sync from upstream; a diff there is noise at every bump.
        "vendor/evoskill",
    }
)


# --------------------------------------------------------------------------
# The guard itself, driven through a real pytest subprocess.
# --------------------------------------------------------------------------


def _make_root(tmp_path: Path, *, ini_addopts: str) -> Path:
    """A throwaway pytest root with the guard reachable by the same walk-up
    the real conftests use (``<ancestor>/scripts/pytest_guards``)."""
    guards = tmp_path / "scripts" / "pytest_guards"
    guards.mkdir(parents=True)
    (guards / "pytest_verbosity_guard.py").write_bytes(
        (GUARD_DIR / "pytest_verbosity_guard.py").read_bytes()
    )

    root = tmp_path / "root"
    root.mkdir()
    (root / "pytest.ini").write_text(f"[pytest]\naddopts =\n{ini_addopts}\n")
    (root / "conftest.py").write_bytes(REFERENCE_CONFTEST.read_bytes())
    (root / "test_sample.py").write_text("def test_passes():\n    assert True\n")
    return root


def _run(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *argv],
        cwd=root,
        capture_output=True,
        text=True,
    )


def test_a_normal_run_is_untouched(tmp_path: Path) -> None:
    """INNOCENCE: the guard is silent when the tally is printed."""
    result = _run(_make_root(tmp_path, ini_addopts="    -q"))
    assert result.returncode == 0
    assert "1 passed" in result.stdout
    assert "verbosity" not in result.stdout


def test_one_q_is_guilty_in_a_root_whose_config_already_sets_q(
    tmp_path: Path,
) -> None:
    """GUILT: config ``-q`` plus argv ``-q`` reaches -2 and the tally vanishes."""
    result = _run(_make_root(tmp_path, ini_addopts="    -q"), "-q")
    assert result.returncode != 0
    assert "effective verbosity is -2" in result.stdout + result.stderr
    assert "pytest_verbosity_guard.py" in result.stdout + result.stderr


def test_one_q_is_innocent_in_a_root_whose_config_does_not(tmp_path: Path) -> None:
    """INNOCENCE, and the pair that proves the guard reads EFFECTIVE verbosity.

    Same argv as the guilty test above. Only the config differs, so a guard
    that merely counted ``-q`` on the command line would fail here.
    """
    result = _run(_make_root(tmp_path, ini_addopts="    -ra"), "-q")
    assert result.returncode == 0
    assert "1 passed" in result.stdout


def test_adding_v_restores_the_tally_and_the_guard_stands_down(
    tmp_path: Path,
) -> None:
    """INNOCENCE: ``-q -v`` cancels back to -1 — measured, not assumed."""
    result = _run(_make_root(tmp_path, ini_addopts="    -q"), "-q", "-v")
    assert result.returncode == 0
    assert "1 passed" in result.stdout


def test_qq_on_the_command_line_is_guilty_with_no_help_from_the_config(
    tmp_path: Path,
) -> None:
    """GUILT: argv alone can reach -2 in a root whose config is quiet-free."""
    result = _run(_make_root(tmp_path, ini_addopts="    -ra"), "-q", "-q")
    assert result.returncode != 0
    assert "effective verbosity is -2" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("verbosity", "suppressed"),
    [(1, False), (0, False), (-1, False), (-2, True), (-3, True)],
)
def test_the_threshold_matches_the_measured_boundary(
    verbosity: int, suppressed: bool
) -> None:
    assert summary_is_suppressed(verbosity) is suppressed


# --------------------------------------------------------------------------
# The wiring: every pytest root carries the guard, and the list is derived.
# --------------------------------------------------------------------------


def test_every_pytest_root_is_wired(tmp_path: Path) -> None:
    missing = unwired_roots(REPO_ROOT, REFERENCE_CONFTEST.read_bytes(), EXEMPT_ROOTS)
    assert missing == [], (
        "pytest roots missing the verbosity guard (or carrying a diverged "
        f"copy): {missing}. Copy apps/backend-rag/conftest.py into each, or "
        "add it to EXEMPT_ROOTS with the reason written down."
    )


def test_the_wiring_check_can_actually_report_a_missing_root(
    tmp_path: Path,
) -> None:
    """GUILT for the checker: an unwired root must be named, not counted.

    Without this, a checker that returned ``[]`` unconditionally would keep
    the test above green forever — W107, cured one wrapper out of five.
    """
    reference = b"# canonical wiring\n"
    for name in ("wired_a", "wired_b", "forgotten"):
        root = tmp_path / name
        root.mkdir()
        (root / "pytest.ini").write_text("[pytest]\n")
        if name != "forgotten":
            (root / "conftest.py").write_bytes(reference)

    assert unwired_roots(tmp_path, reference, frozenset()) == ["forgotten"]


def test_a_diverged_copy_counts_as_unwired(tmp_path: Path) -> None:
    """GUILT: byte-equality, not mere presence — a stale copy is not wiring."""
    root = tmp_path / "drifted"
    root.mkdir()
    (root / "pytest.ini").write_text("[pytest]\n")
    (root / "conftest.py").write_bytes(b"# an older wiring\n")

    assert unwired_roots(tmp_path, b"# canonical wiring\n", frozenset()) == ["drifted"]


def test_an_exempt_root_is_not_reported(tmp_path: Path) -> None:
    """INNOCENCE for the checker: exemptions are honoured."""
    root = tmp_path / "vendored"
    root.mkdir()
    (root / "pytest.ini").write_text("[pytest]\n")

    assert unwired_roots(tmp_path, b"x", frozenset({"vendored"})) == []


# --------------------------------------------------------------------------
# Second layer, for the ONE population the guard cannot see.
#
# `--noconftest` stops pytest loading conftest files, so the guard never runs
# — measured 2026-08-29, not assumed. That is the whole reason this check
# exists: it is not a redundant copy of the guard, it covers the invocations
# the guard is structurally blind to. Everything else is left to the guard,
# which reads resolved verbosity and cannot be fooled by flag arithmetic.
# --------------------------------------------------------------------------

#: Files that actually execute (or instruct someone to execute) pytest.
#:
#: `apps/**/*.py` and `scripts/**/*.py` were added 2026-08-30, after this
#: scan was found to have no `*.py` glob at all: the Python population this
#: verbosity-guard PR is named for had been swept by hand (a targeted
#: `grep`, not this check), so a Python call site that ALSO used
#: `--noconftest` would have gone undetected by both the live guard (blind
#: by construction to `--noconftest`) and this static scanner (blind for
#: lack of a glob) — a defect generator, not merely a gap. Scoped to
#: `apps/`/`scripts/` rather than a bare `**/*.py`: those are the two
#: directories this PR's own hand-swept population lives in, and a
#: repo-wide glob would additionally walk vendored/virtualenv trees this
#: check has no business reading.
_SCANNED_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "scripts/**/*.sh",
    "scripts/**/*.py",
    "infra/**/*.sh",
    "apps/**/*.py",
    "Makefile",
)

_QUIET_FLAGS = ("-q", "-qq", "-qqq", "--quiet")


#: This scanner reads raw source text, not executed strings — so once the
#: `*.py` globs above made it scan `scripts/tests/`, it started reading its
#: OWN fixture literals as if they were real invocations: a test string that
#: DEMONSTRATES a guilty line (`test_the_call_site_scan_can_actually_report_one`)
#: and a test string that deliberately CONTAINS the words "pytest"/"--noconftest"/
#: "-q" to prove the scanner leaves a non-pytest line alone
#: (`test_the_call_site_scan_leaves_innocent_lines_alone`'s `.replace("pytest",
#: "pytst")` case) both matched, measured 2026-08-30. Self-exclusion, not a
#: directory-wide carve-out: other files under `scripts/` genuinely invoke
#: pytest for real and must stay in scope.
_SELF_PATH = Path(__file__).resolve()


def _quiet_noconftest_call_sites(root: Path) -> list[str]:
    """Committed pytest invocations that go quiet AND skip conftests."""
    findings: list[str] = []
    for pattern in _SCANNED_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path.resolve() == _SELF_PATH:
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if "pytest" not in line or "--noconftest" not in line:
                    continue
                if any(f" {flag}" in line for flag in _QUIET_FLAGS):
                    findings.append(f"{path.relative_to(root).as_posix()}:{number}")
    return findings


#: `.github/workflows/p3-sandbox-gates.yml:125` was the ONE invocation in this
#: repo the guard could not see — a `--collect-only` importability gate that
#: was NOT actually blind to failure (measured 2026-08-29 at effective
#: verbosity -2, pytest still exits 5 on "no tests collected" and 2 on a
#: collection error, and that step's exit code is what the job fails on; what
#: it lost was the readable listing) — but its `-q` was still redundant, since
#: that root's own `pytest.ini` addopts already carries one.
#:
#: A prior version of this comment justified leaving it in place by claiming
#: touching it would move this PR's deterministic gear floor from 2 to 3 —
#: false: this PR's floor was already 3, from the hot-zone-path term alone,
#: because it already edits `fly-deploy.yml` and `tests.yml`. There was no
#: real reason left to keep the `-q`, so it was dropped 2026-08-30 (same PR)
#: and this set is pinned to empty rather than removed outright, so a NEW
#: quiet+`--noconftest` invocation still turns this characterisation test red
#: instead of silently widening scope.
KNOWN_UNGUARDABLE_CALL_SITES: tuple[str, ...] = ()


def test_no_new_invocation_goes_quiet_behind_noconftest() -> None:
    """`--noconftest` skips the guard, so these need their own check.

    Pinned to the empty tuple: every invocation this scan can see is clean.
    Stays a real assertion, not a vacuous one — it goes red the moment ANY
    quiet+`--noconftest` invocation is committed, known or new.
    """
    findings = _quiet_noconftest_call_sites(REPO_ROOT)
    assert findings == list(KNOWN_UNGUARDABLE_CALL_SITES), (
        "these invocations suppress the tally AND skip conftests, so the "
        f"verbosity guard cannot see them: {findings}. Drop the quiet flag — "
        "the guard is not available as a safety net here."
    )


def test_the_call_site_scan_can_actually_report_one(tmp_path: Path) -> None:
    """GUILT for the scanner."""
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "steps:\n  - run: python -m pytest tests/ --collect-only -q --noconftest\n"
    )
    assert _quiet_noconftest_call_sites(tmp_path) == [".github/workflows/ci.yml:2"]


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest tests/ --collect-only --noconftest",  # no quiet flag
        "python -m pytest tests/ -q",  # quiet, but the guard CAN see it
        "echo 'not a pytest --noconftest -q line'".replace("pytest", "pytst"),
    ],
    ids=["noconftest-without-quiet", "quiet-without-noconftest", "not-pytest"],
)
def test_the_call_site_scan_leaves_innocent_lines_alone(
    tmp_path: Path, command: str
) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(f"steps:\n  - run: {command}\n")
    assert _quiet_noconftest_call_sites(tmp_path) == []


def test_a_directory_with_two_configs_is_one_root_not_two() -> None:
    """``apps/backend-rag`` carries a ``pytest.ini`` AND a pyproject pytest
    section. pytest reads the ini and ignores the block, so the dead config
    must not demand its own wiring."""
    backend_rag = REPO_ROOT / "apps" / "backend-rag"
    assert (backend_rag / "pytest.ini").is_file()
    assert "[tool.pytest.ini_options]" in (backend_rag / "pyproject.toml").read_text(
        encoding="utf-8"
    )

    roots = pytest_config_roots(REPO_ROOT)
    assert roots.count(backend_rag) == 1
    assert winning_config(backend_rag) == backend_rag / "pytest.ini"
