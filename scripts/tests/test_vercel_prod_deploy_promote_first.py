#!/usr/bin/env python3
"""Corpus for `vercel_prod_deploy._ready_deployment_for` and the promote-first path.

WHY THIS EXISTS
---------------
On 2026-07-30 production sat 2h28m behind main while a fully-built deployment for that exact
commit was already READY on Vercel, merely STAGED (never aliased). The script's answer to
"production is behind" was to create a SECOND deployment of the same tree: ~6 minutes and a
duplicate, where a promote is ~3 seconds.

The selector that finds that build is the whole optimisation, so it is the thing that has to
be proven — on guilt (it finds the promotable build) AND on innocence (it never offers up a
build that is not this commit, or not promotable). Getting innocence wrong here is worse than
having no optimisation at all: promoting the WRONG deployment publishes the wrong code.

No network. `_api` is replaced per-case with a canned response.
"""
from __future__ import annotations

import pathlib
import sys
import unittest.mock

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

SHA = "f0dea7af137caae842bff39db96762090b2d9653"
OTHER = "e2760f91b024daff17ac9266053b2aa93d5de143"


def _dep(uid, state, substate, sha):
    return {"uid": uid, "state": state, "readySubstate": substate, "meta": {"githubCommitSha": sha}}


def _with_deployments(deployments, status=200):
    """Patch _api to answer the deployment list, and record any other call."""
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path))
        if path.startswith("/v6/deployments"):
            return status, {"deployments": deployments}
        return 200, {}

    return unittest.mock.patch.object(vpd, "_api", side_effect=fake), calls


# ---------------------------------------------------------------- guilt

def test_finds_the_staged_build_for_this_commit():
    """The real observed shape: READY + STAGED + our sha. This is the 2h28m case."""
    patch, _ = _with_deployments([_dep("dpl_staged", "READY", "STAGED", SHA)])
    with patch:
        assert vpd._ready_deployment_for(SHA) == ("dpl_staged", "STAGED")


def test_picks_the_matching_commit_out_of_a_mixed_list():
    """A real list is mostly other commits — the sha, not the position, decides."""
    patch, _ = _with_deployments([
        _dep("dpl_newer", "READY", "STAGED", OTHER),
        _dep("dpl_cancel", "CANCELED", None, SHA),
        _dep("dpl_ours", "READY", "STAGED", SHA),
    ])
    with patch:
        assert vpd._ready_deployment_for(SHA) == ("dpl_ours", "STAGED")


# ------------------------------------------------------------ innocence
# Each of these, if it returned a deployment, would promote the WRONG build to production.

def test_never_offers_a_build_of_a_different_commit():
    patch, _ = _with_deployments([_dep("dpl_other", "READY", "STAGED", OTHER)])
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


def test_never_offers_a_canceled_build():
    """CANCELED is the NORMAL outcome when the ignore-step skips a commit — it has no output."""
    patch, _ = _with_deployments([_dep("dpl_cancel", "CANCELED", None, SHA)])
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


def test_never_offers_an_errored_or_still_building_one():
    patch, _ = _with_deployments([
        _dep("dpl_err", "ERROR", None, SHA),
        _dep("dpl_building", "BUILDING", None, SHA),
    ])
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


def test_deployment_with_no_commit_metadata_is_not_a_match():
    """A CLI-uploaded deployment carries no githubCommitSha; absent must never read as equal."""
    patch, _ = _with_deployments([{"uid": "dpl_cli", "state": "READY", "readySubstate": "STAGED"}])
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


def test_a_match_with_no_uid_is_skipped_not_returned_as_none_id():
    patch, _ = _with_deployments([{"uid": None, "state": "READY", "meta": {"githubCommitSha": SHA}}])
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


# --------------------------------------------------------- fail-open

def test_api_failure_returns_none_so_the_rebuild_path_still_runs():
    """Not finding a shortcut must never block the cure — only skip the optimisation."""
    patch, _ = _with_deployments([], status=500)
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


def test_empty_list_is_none_not_a_crash():
    patch, _ = _with_deployments([])
    with patch:
        assert vpd._ready_deployment_for(SHA) is None


# ------------------------------------------------- promote verdict is behavioural

def test_promote_reports_failure_when_the_domains_do_not_move():
    """HTTP 202 means 'accepted', never 'live' — the probe is the arbiter (W88)."""
    with unittest.mock.patch.object(vpd, "_api", return_value=(202, {})), \
         unittest.mock.patch.object(vpd, "_probe_until", return_value=False):
        assert vpd._promote("dpl_x", SHA) is False


def test_promote_reports_success_only_on_a_served_probe():
    with unittest.mock.patch.object(vpd, "_api", return_value=(200, {})), \
         unittest.mock.patch.object(vpd, "_probe_until", return_value=True):
        assert vpd._promote("dpl_x", SHA) is True


def test_promote_does_not_probe_when_the_request_was_refused():
    """A refused promote changed nothing; probing would just burn 8 x 15s waiting."""
    probe = unittest.mock.Mock(return_value=False)
    with unittest.mock.patch.object(vpd, "_api", return_value=(403, {"error": "nope"})), \
         unittest.mock.patch.object(vpd, "_probe_until", probe):
        assert vpd._promote("dpl_x", SHA) is False
    probe.assert_not_called()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
