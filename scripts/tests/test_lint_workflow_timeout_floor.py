"""Guilt and innocence for the checkout-budget floor.

A guard that only proves guilt is how a cure becomes the next defect (cicatrix
family #3): the two jobs this lint would have caught sit next to four that a
file-level census wrongly accused, so the innocence cases are the ones that
decide whether it is usable at all.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_workflow_timeout_floor.py"
assert _MODULE_PATH.is_file(), f"lint not at {_MODULE_PATH}"
_SPEC = importlib.util.spec_from_file_location("lint_workflow_timeout_floor", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mod
_SPEC.loader.exec_module(mod)


def write(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / "workflows"
    d.mkdir(exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")
    return d


CHECKOUT_JOB = """
name: x
on: [pull_request]
jobs:
  guard:
    runs-on: ubuntu-latest
    timeout-minutes: {t}
    steps:
      - uses: actions/checkout@v7
      - run: python scripts/root_guard.py --check
"""

NO_CHECKOUT_JOB = """
name: x
on: [pull_request]
jobs:
  notify:
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - run: curl -sS https://example.invalid
"""


# --------------------------------------------------------------------------
# GUILT
# --------------------------------------------------------------------------


def test_flags_the_shape_that_killed_docs_sync_and_root_guard(tmp_path):
    root = write(tmp_path, "docs-sync.yml", CHECKOUT_JOB.format(t=2))
    found, bad, scanned = mod.offenders(root)
    assert bad == [] and scanned == 1
    assert found == [("docs-sync.yml", "guard", 2)]


@pytest.mark.parametrize("t", [1, 2, 3, 4])
def test_every_value_below_the_floor_is_flagged(tmp_path, t):
    root = write(tmp_path, "w.yml", CHECKOUT_JOB.format(t=t))
    found, _, _ = mod.offenders(root)
    assert len(found) == 1


# --------------------------------------------------------------------------
# INNOCENCE — the four the first census wrongly accused
# --------------------------------------------------------------------------


def test_a_tight_job_that_never_checks_out_is_not_flagged(tmp_path):
    """The fly-deploy jobs: 2m and 3m budgets, no checkout, not exposed."""
    root = write(tmp_path, "fly-deploy.yml", NO_CHECKOUT_JOB)
    found, _, scanned = mod.offenders(root)
    assert scanned == 1
    assert found == []


def test_a_tight_job_in_a_FILE_that_also_has_a_checkout_job_is_not_flagged(tmp_path):
    """The exact over-match of the first census: attribution is per JOB."""
    root = write(
        tmp_path,
        "mixed.yml",
        """
name: x
on: [pull_request]
jobs:
  builds:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
  pings:
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - run: echo hi
""",
    )
    found, _, scanned = mod.offenders(root)
    assert scanned == 2
    assert found == []


@pytest.mark.parametrize("delta", [0, 1, 20])
def test_a_budget_at_or_above_the_floor_is_not_flagged(tmp_path, delta):
    """Derived from the constant, so raising the floor does not falsify the
    COMPARISON. The constant's own value is pinned separately below — a test
    that reads the constant can never catch the constant being wrong."""
    root = write(tmp_path, "w.yml", CHECKOUT_JOB.format(t=mod.FLOOR_MINUTES + delta))
    found, _, _ = mod.offenders(root)
    assert found == []


def test_the_floor_value_itself_is_pinned_to_the_measurement(tmp_path):
    """Lowering the floor is the regression this whole lint exists to prevent,
    and it is a one-character edit.

    The number comes from a 645-step sample, not from the incident that
    prompted the lint: median ~15s, 11% over 60s, worst observed 599s. It is
    deliberately NOT set above that worst case — clearing it would mean raising
    64 of 114 jobs to defend an event seen twice in 645, and the honest cure is
    the 1,090 MiB checkout payload, not a bigger number here. The residual is
    declared in the module docstring rather than papered over.
    """
    assert mod.FLOOR_MINUTES == 10
    # And the comparison is strict-below, so a job sitting exactly ON the floor
    # is accepted — the 15 jobs raised in this PR sit there.
    root = write(tmp_path, "w.yml", CHECKOUT_JOB.format(t=10))
    assert mod.offenders(root)[0] == []
    root = write(tmp_path, "x.yml", CHECKOUT_JOB.format(t=9))
    assert mod.offenders(root)[0] == [("x.yml", "guard", 9)]


def test_an_undeclared_timeout_is_out_of_scope(tmp_path):
    """Default is 360 minutes — a different risk, deliberately not this one."""
    root = write(
        tmp_path,
        "w.yml",
        """
name: x
on: [pull_request]
jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
""",
    )
    found, _, scanned = mod.offenders(root)
    assert scanned == 1
    assert found == []


# --------------------------------------------------------------------------
# CANNOT-VERIFY — an empty or unreadable sweep is not a pass (W84)
# --------------------------------------------------------------------------


def test_zero_jobs_scanned_exits_cannot_verify(tmp_path, monkeypatch, capsys):
    (tmp_path / "workflows").mkdir()
    monkeypatch.setattr(sys, "argv", ["lint", "--root", str(tmp_path / "workflows")])
    assert mod.main() == 2
    assert "zero jobs scanned" in capsys.readouterr().err


def test_a_missing_root_exits_cannot_verify(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["lint", "--root", str(tmp_path / "nope")])
    assert mod.main() == 2


def test_an_unparseable_workflow_exits_cannot_verify_not_clean(tmp_path, monkeypatch, capsys):
    root = write(tmp_path, "broken.yml", "jobs:\n  a:\n   - [unclosed\n")
    monkeypatch.setattr(sys, "argv", ["lint", "--root", str(root)])
    assert mod.main() == 2
    assert "unparseable" in capsys.readouterr().err


# --------------------------------------------------------------------------
# THE REAL CORPUS — this repo must be clean, and the sweep must be real
# --------------------------------------------------------------------------


def test_the_repo_itself_passes_and_the_sweep_is_not_empty(monkeypatch):
    repo_root = next(
        p for p in Path(__file__).resolve().parents if (p / ".github" / "workflows").is_dir()
    )
    found, bad, scanned = mod.offenders(repo_root / ".github" / "workflows")
    assert bad == [], bad
    # A positive control on the sweep: this repo has ~100 jobs, so a handful
    # would mean the walker silently stopped (the count IS the control).
    assert scanned > 50, f"only {scanned} jobs scanned — the sweep is not reaching the corpus"
    assert found == [], found
