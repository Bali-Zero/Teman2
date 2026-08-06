#!/usr/bin/env python3
"""A declared pair whose live copy is absent must be NAMED, never silent.

`check_pairs` skips any pair whose live side is not on disk — correctly, since
nothing can drift when nothing is running. But the skip was silent, so the run
printed "109 declared pair(s) ... clean" while never evaluating three of them.

Measured on the Pro, 2026-08-06, minutes after PR #3671 merged: two of the
skipped pairs were the very files that PR existed to promote (their live copies
had been moved to an attic hours earlier), and the third was a stale
declaration nobody knew was stale. The verdict was true. The conclusion any
reader draws from it — "the declared pairs are verified" — was not.

The distinction this pins: a pair scoped to ANOTHER machine is legitimate
non-applicability and must stay silent, or the real signal drowns in fleet
noise on every run. Only a pair this machine CLAIMS and cannot find is news.

    python3 -m pytest scripts/tests/test_home_fork_skipped_visibility.py -q
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT = REPO_ROOT / "scripts" / "lint_home_fork.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_home_fork_under_test", LINT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def lint():
    return _load()


@pytest.fixture()
def world(tmp_path):
    """A repo twin and a HOME, both real on disk — no mocked filesystem."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    (home / "scripts").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "present.sh").write_text("#!/bin/sh\necho hi\n")
    (home / "scripts" / "present.sh").write_text("#!/bin/sh\necho hi\n")
    (repo / "scripts" / "absent.sh").write_text("#!/bin/sh\necho gone\n")
    # NOTE: no home/scripts/absent.sh — that is the whole point.
    return home, repo


PRESENT = {"live": "~/scripts/present.sh", "repo": "scripts/present.sh", "machines": ["all"]}
ABSENT = {"live": "~/scripts/absent.sh", "repo": "scripts/absent.sh", "machines": ["all"]}
OTHER_MACHINE = {
    "live": "~/scripts/absent.sh",
    "repo": "scripts/absent.sh",
    "machines": ["some-other-box"],
}


# ── guilt: an absent live side is reported ───────────────────────────────────
def test_absent_live_copy_is_named(lint, world):
    home, repo = world
    skipped: list[str] = []
    breaches = lint.check_pairs([ABSENT], repo, home, "pro", skipped=skipped)
    assert breaches == [], "an absent live copy is not a breach"
    assert len(skipped) == 1
    assert "~/scripts/absent.sh" in skipped[0]
    assert "not on disk" in skipped[0]


def test_the_machine_it_was_declared_for_is_named(lint, world):
    """Naming the machine is what makes the line actionable on a 3-node fleet."""
    home, repo = world
    skipped: list[str] = []
    lint.check_pairs([ABSENT], repo, home, "mini", skipped=skipped)
    assert "mini" in skipped[0]


def test_a_present_pair_is_still_checked_not_skipped(lint, world):
    home, repo = world
    skipped: list[str] = []
    breaches = lint.check_pairs([PRESENT], repo, home, "pro", skipped=skipped)
    assert breaches == []
    assert skipped == [], "a live copy that EXISTS must be evaluated, never skipped"


def test_mixed_run_separates_verified_from_skipped(lint, world):
    home, repo = world
    skipped: list[str] = []
    lint.check_pairs([PRESENT, ABSENT], repo, home, "pro", skipped=skipped)
    assert len(skipped) == 1 and "absent" in skipped[0]


# ── innocence: silence where silence is correct ──────────────────────────────
def test_a_pair_scoped_to_another_machine_is_NOT_reported(lint, world):
    """Legitimate non-applicability. Reporting it would bury the real signal."""
    home, repo = world
    skipped: list[str] = []
    lint.check_pairs([OTHER_MACHINE], repo, home, "pro", skipped=skipped)
    assert skipped == []


def test_no_sink_offered_means_no_crash(lint, world):
    """Every existing caller passes no `skipped=` — they must keep working."""
    home, repo = world
    assert lint.check_pairs([ABSENT, PRESENT], repo, home, "pro") == []


# ── the exit code must not move ──────────────────────────────────────────────
def test_a_skipped_pair_never_changes_the_verdict(lint, world):
    """A diagnostic that can fail a build is not a diagnostic.

    Guilt and innocence both land on `breaches`, because that is what the exit
    code is computed from: skipped pairs contribute nothing to it, in either
    direction.
    """
    home, repo = world
    skipped: list[str] = []
    assert lint.check_pairs([ABSENT], repo, home, "pro", skipped=skipped) == []
    assert skipped, "…and yet it was reported"

    # A real divergence still breaches, with a skipped pair alongside it.
    (home / "scripts" / "present.sh").write_text("#!/bin/sh\necho DRIFTED\n")
    skipped2: list[str] = []
    breaches = lint.check_pairs([PRESENT, ABSENT], repo, home, "pro", skipped=skipped2)
    assert len(breaches) == 1 and "DIVERGED" in breaches[0]
    assert len(skipped2) == 1


def test_missing_repo_twin_is_still_a_breach_not_a_skip(lint, world):
    """The absent side decides which it is: live absent = skip, repo absent = breach."""
    home, repo = world
    (repo / "scripts" / "present.sh").unlink()
    skipped: list[str] = []
    breaches = lint.check_pairs([PRESENT], repo, home, "pro", skipped=skipped)
    assert skipped == []
    assert len(breaches) == 1 and "NO-REPO-TWIN" in breaches[0]
