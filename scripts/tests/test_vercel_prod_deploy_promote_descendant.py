#!/usr/bin/env python3
"""Corpus for `vercel_prod_deploy._ready_deployment_including` — the merge-queue batch case.

WHY THIS EXISTS
---------------
2026-09-11, 03:13-03:45 WITA: the GitHub merge queue landed #6136 + #6134 + #6139 in ONE push,
so Vercel built only the batch HEAD (a docs commit) and the newest bundle-relevant commit never
had a build of its own. `_ready_deployment_for` (exact sha) found nothing; the --promote-only
fallback walks OLDER bundle-relevant commits and found nothing either. Mini's autopromote organ
exited 3 every 120s while four READY builds that all CONTAINED the cure sat STAGED, and
production served a 35-minute-old build until a human promoted one of them.

The rule is the sentinel's: production must INCLUDE the target, not EQUAL it. Guilt: the
selector finds the newest READY build on main that descends from the target. Innocence: it
never offers a build that is not on origin/main, one that does not contain the target, a
non-READY one, or the target's own build (that is `_ready_deployment_for`'s job).

No network, no git: `_api` and `_git` are replaced per-case.
"""
from __future__ import annotations

import pathlib
import sys
import unittest.mock

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

TARGET = "8a2c49cfbe96499ccbbb4d89d020e2b3b8f0a396"   # newest bundle-relevant, never built
BATCH_HEAD = "6fef72cd75ccaf38041d67b06ef7bc4cc40f9b1a"  # docs commit that closed the batch
LATER = "b7fdaf7eabea0b776c566594b7638959f1b97e66"      # a later main commit, also built
OLDER = "70546e5d9628be1f6f57fe71adc6ba9b6744fc42"      # what production served
STRAY = "b82d44e3bb000000000000000000000000000000"      # a branch build, not on main

# ancestry as git would answer it: (ancestor, descendant) pairs that are TRUE
_ANCESTRY = {
    (OLDER, TARGET), (OLDER, BATCH_HEAD), (OLDER, LATER),
    (TARGET, BATCH_HEAD), (TARGET, LATER), (BATCH_HEAD, LATER),
    (OLDER, "origin/main"), (TARGET, "origin/main"), (BATCH_HEAD, "origin/main"), (LATER, "origin/main"),
}


def _fake_git(*args):
    if args[:2] == ("merge-base", "--is-ancestor"):
        return "" if (args[2], args[3]) in _ANCESTRY else None
    raise AssertionError(f"unexpected git call {args}")


def _dep(uid, state, substate, sha):
    return {"uid": uid, "state": state, "readySubstate": substate, "meta": {"githubCommitSha": sha}}


def _with(deployments, status=200, git=_fake_git):
    def fake_api(method, path, body=None):
        assert path.startswith("/v6/deployments")
        return status, {"deployments": deployments}
    return (
        unittest.mock.patch.object(vpd, "_api", side_effect=fake_api),
        unittest.mock.patch.object(vpd, "_git", side_effect=git),
    )


# ---------------------------------------------------------------- guilt

def test_finds_the_batch_head_build_that_includes_the_target():
    """The measured shape: no build of TARGET, a STAGED build of the batch HEAD that contains it."""
    a, g = _with([_dep("dpl_head", "READY", "STAGED", BATCH_HEAD)])
    with a, g:
        assert vpd._ready_deployment_including(TARGET) == ("dpl_head", "STAGED", BATCH_HEAD)


def test_prefers_the_newest_descendant_when_several_are_ready():
    """Vercel lists newest first; the newest READY descendant carries the most of main."""
    a, g = _with([
        _dep("dpl_later", "READY", "STAGED", LATER),
        _dep("dpl_head", "READY", "STAGED", BATCH_HEAD),
    ])
    with a, g:
        assert vpd._ready_deployment_including(TARGET)[0] == "dpl_later"


# ---------------------------------------------------------------- innocence

def test_never_offers_a_build_that_does_not_contain_the_target():
    """The build production already serves is an ancestor of the target, not a cure for it."""
    a, g = _with([_dep("dpl_old", "READY", "PROMOTED", OLDER)])
    with a, g:
        assert vpd._ready_deployment_including(TARGET) is None


def test_never_offers_a_build_of_a_commit_that_is_not_on_main():
    """A branch build can be READY and even descend from the target after a rebase — never it."""
    stray_ancestry = _ANCESTRY | {(TARGET, STRAY)}
    def git(*args):
        if args[:2] == ("merge-base", "--is-ancestor"):
            return "" if (args[2], args[3]) in stray_ancestry else None
        raise AssertionError(args)
    a, g = _with([_dep("dpl_stray", "READY", "STAGED", STRAY)], git=git)
    with a, g:
        assert vpd._ready_deployment_including(TARGET) is None


def test_never_offers_a_canceled_errored_or_building_one():
    a, g = _with([
        _dep("dpl_c", "CANCELED", None, LATER),
        _dep("dpl_e", "ERROR", None, LATER),
        _dep("dpl_b", "BUILDING", None, LATER),
    ])
    with a, g:
        assert vpd._ready_deployment_including(TARGET) is None


def test_the_targets_own_build_is_not_this_selectors_answer():
    """Exact matches belong to _ready_deployment_for; this one only widens to descendants."""
    a, g = _with([_dep("dpl_exact", "READY", "STAGED", TARGET)])
    with a, g:
        assert vpd._ready_deployment_including(TARGET) is None


def test_git_that_cannot_answer_fails_closed():
    a, g = _with([_dep("dpl_head", "READY", "STAGED", BATCH_HEAD)], git=lambda *a: None)
    with a, g:
        assert vpd._ready_deployment_including(TARGET) is None


def test_api_failure_returns_none_so_the_rebuild_path_still_runs():
    a, g = _with([], status=500)
    with a, g:
        assert vpd._ready_deployment_including(TARGET) is None


# ---------------------------------------------------------------- end to end: the probe follows the build

def test_promote_only_promotes_the_descendant_and_probes_for_ITS_sha(capsys):
    """After promoting the batch HEAD's build, production serves BATCH_HEAD, not TARGET. The
    probe compares by equality, so it must be told the build's sha — or a correct promote
    would be reported as a failure."""
    promoted = []
    probed = []

    def fake_promote(dpl, sha):
        promoted.append((dpl, sha))
        probed.append(sha)
        return True

    with unittest.mock.patch.object(vpd, "_served_commit", return_value=OLDER), \
         unittest.mock.patch.object(vpd, "_production_includes", side_effect=lambda target, live: target == OLDER), \
         unittest.mock.patch.object(vpd, "_ready_deployment_for", return_value=None), \
         unittest.mock.patch.object(vpd, "_ready_deployment_including", return_value=("dpl_head", "STAGED", BATCH_HEAD)), \
         unittest.mock.patch.object(vpd, "_promote", side_effect=fake_promote), \
         unittest.mock.patch.object(sys, "argv", ["vercel_prod_deploy.py", "--ref", TARGET, "--promote-only"]):
        assert vpd.main() == 0
    assert promoted == [("dpl_head", BATCH_HEAD)]
    out = capsys.readouterr().out
    assert "merge-queue batch" in out and BATCH_HEAD[:9] in out


def test_dry_run_reports_the_descendant_plan_and_changes_nothing():
    calls = []
    with unittest.mock.patch.object(vpd, "_served_commit", return_value=OLDER), \
         unittest.mock.patch.object(vpd, "_production_includes", return_value=False), \
         unittest.mock.patch.object(vpd, "_ready_deployment_for", return_value=None), \
         unittest.mock.patch.object(vpd, "_ready_deployment_including", return_value=("dpl_head", "STAGED", BATCH_HEAD)), \
         unittest.mock.patch.object(vpd, "_api", side_effect=lambda *a, **k: calls.append(a) or (200, {})), \
         unittest.mock.patch.object(vpd, "_promote", side_effect=AssertionError("dry-run must not promote")), \
         unittest.mock.patch.object(sys, "argv", ["vercel_prod_deploy.py", "--ref", TARGET, "--dry-run"]):
        assert vpd.main() == 0
    assert calls == []
