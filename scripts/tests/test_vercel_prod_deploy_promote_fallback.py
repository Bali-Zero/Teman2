#!/usr/bin/env python3
"""Corpus for the --promote-only fallback: promote an OLDER bundle-relevant commit when the
newest one has no READY build yet.

WHY THIS EXISTS
---------------
`_deploy_relevant_head()` always targets the SINGLE newest bundle-relevant commit. Under
--promote-only, if Vercel has not finished building THAT exact commit, the script gave up
(exit 3) even when an OLDER bundle-relevant commit — one that genuinely changes what
balizero.com serves — already has a READY, unpromoted build sitting on Vercel. Verified live
2026-08-25: production was 9 commits behind the newest bundle-relevant commit while a real
user-facing fix (a landing-page hero CTA, `apps/mouth/.../SecondHomeLanding.tsx`) sat READY
and unpromoted two commits back. The cron kept reporting the benign "nothing to promote"
warning every 15 minutes while a genuine improvement went unpublished.

The fix does NOT relax --promote-only's contract (it still never builds). It only widens
which already-built commit counts as "the thing to promote".

Guilt: the fallback finds and promotes an older READY build, and dry-run reports the same
plan without mutating anything. Innocence: it does not offer a commit production already
includes (an already-current commit is not an improvement, it is a no-op the caller already
handles), and the interactive default path (no --promote-only, no --dry-run) never consults
it at all — a build is always self-sufficient there.

No network for _ready_deployment_among_recent_bundle_commits: `_git` and `_ready_deployment_for`
are both replaced per-case. No network for end-to-end main() cases either: every boundary is
patched, mirroring test_vercel_prod_deploy_promote_only.py's harness.
"""
from __future__ import annotations

import pathlib
import sys
import unittest.mock

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

NEWEST = "f0dea7af137caae842bff39db96762090b2d9653"
OLDER = "e2760f91b024daff17ac9266053b2aa93d5de143"
OLDEST = "0df5510c6e2ca8f869b225fe5a5c2ebb09a5ae08"
LIVE = "aaaa111122223333444455556666777788889999"

CREATE_PATH = "/v13/deployments"


# ---------------------------------------------------------------- _ready_deployment_among_recent_bundle_commits


def test_finds_the_first_older_commit_with_a_ready_build():
    """NEWEST has nothing; OLDER is READY; production is behind both. Must return OLDER."""
    with unittest.mock.patch.object(vpd, "_git", return_value=f"{NEWEST}\n{OLDER}\n{OLDEST}"), \
         unittest.mock.patch.object(
             vpd, "_ready_deployment_for",
             side_effect=lambda sha: ("dpl_older", "STAGED") if sha == OLDER else None,
         ):
        assert vpd._ready_deployment_among_recent_bundle_commits(LIVE) == (OLDER, "dpl_older", "STAGED")


def test_returns_none_when_nothing_in_the_window_is_ready():
    with unittest.mock.patch.object(vpd, "_git", return_value=f"{NEWEST}\n{OLDER}"), \
         unittest.mock.patch.object(vpd, "_ready_deployment_for", return_value=None):
        assert vpd._ready_deployment_among_recent_bundle_commits(LIVE) is None


def test_returns_none_when_git_cannot_answer():
    """_git returning None (a real git failure) must not raise — .splitlines() on None would."""
    with unittest.mock.patch.object(vpd, "_git", return_value=None):
        assert vpd._ready_deployment_among_recent_bundle_commits(LIVE) is None


def test_returns_none_when_there_is_no_bundle_relevant_history_at_all():
    """_git succeeds but the path-filtered log is empty (no commit in the window touches a
    bundle path) — an empty string, not None."""
    with unittest.mock.patch.object(vpd, "_git", return_value=""):
        assert vpd._ready_deployment_among_recent_bundle_commits(LIVE) is None


# ---------------------------------------------------------------- innocence


def test_stops_at_a_commit_production_already_includes():
    """Production already serves OLDER (or something descended from it) — walking PAST it to
    OLDEST would offer a commit that is not an improvement. The loop must stop there, not
    promote something equal-or-behind current production.

    NEWEST is checked first (not yet included, not READY here) before OLDER breaks the loop —
    that single call is expected. OLDEST must never be asked about at all.
    """
    with unittest.mock.patch.object(vpd, "_git", return_value=f"{NEWEST}\n{OLDER}\n{OLDEST}"), \
         unittest.mock.patch.object(
             vpd, "_production_includes",
             side_effect=lambda target, live: target == OLDER,
         ), \
         unittest.mock.patch.object(vpd, "_ready_deployment_for", return_value=None) as ready:
        result = vpd._ready_deployment_among_recent_bundle_commits(LIVE)
    assert result is None
    checked = [c.args[0] for c in ready.call_args_list]
    assert checked == [NEWEST]
    assert OLDEST not in checked


# ---------------------------------------------------------------- main() end-to-end (promote-only)


class _Harness:
    """Same shape as test_vercel_prod_deploy_promote_only.py's harness, extended with a
    per-sha _ready_deployment_for and a fallback _git log."""

    def __init__(self, *, ready_map, served, fallback_shas="", promote_ok=True):
        self.ready_map = ready_map
        self.served = served
        self.promote_ok = promote_ok
        self.fallback_shas = fallback_shas
        self.calls: list[tuple[str, str]] = []
        self.promoted: list[str] = []

    def _api(self, method, path, body=None):
        self.calls.append((method, path))
        if method == "POST" and path == CREATE_PATH:
            return 201, {"id": "dpl_created", "readyState": "QUEUED"}
        return 200, {}

    def _ready(self, sha):
        return self.ready_map.get(sha)

    def _promote(self, dpl, sha):
        self.promoted.append(dpl)
        return self.promote_ok

    def __enter__(self):
        self._patches = [
            unittest.mock.patch.object(vpd, "_api", side_effect=self._api),
            unittest.mock.patch.object(vpd, "_promote", side_effect=self._promote),
            unittest.mock.patch.object(vpd, "_deploy_relevant_head", return_value=(NEWEST, "test")),
            unittest.mock.patch.object(vpd, "_served_commit", return_value=self.served),
            unittest.mock.patch.object(vpd, "_ready_deployment_for", side_effect=self._ready),
            unittest.mock.patch.object(vpd, "_git", return_value=self.fallback_shas),
            unittest.mock.patch.object(vpd, "_wait_terminal", return_value=("READY", None)),
            unittest.mock.patch.object(vpd, "_probe_until", return_value=True),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False

    @property
    def created_a_deployment(self) -> bool:
        return any(m == "POST" and p == CREATE_PATH for m, p in self.calls)


def _run(argv: list[str]) -> int:
    with unittest.mock.patch.object(sys, "argv", ["vercel_prod_deploy.py", *argv]):
        return vpd.main()


# ---------------------------------------------------------------- guilt


def test_promote_only_promotes_the_older_ready_build_when_the_newest_has_none():
    with _Harness(
        ready_map={OLDER: ("dpl_older", "STAGED")},
        served=LIVE,
        fallback_shas=f"{NEWEST}\n{OLDER}",
    ) as h:
        assert _run(["--promote-only"]) == 0
    assert h.promoted == ["dpl_older"]
    assert not h.created_a_deployment


def test_dry_run_reports_the_fallback_plan_and_changes_nothing():
    with _Harness(
        ready_map={OLDER: ("dpl_older", "STAGED")},
        served=LIVE,
        fallback_shas=f"{NEWEST}\n{OLDER}",
    ) as h:
        assert _run(["--promote-only", "--dry-run"]) == 0
    assert h.promoted == []
    assert not h.created_a_deployment


def test_promote_only_returns_1_when_the_fallback_promote_fails():
    with _Harness(
        ready_map={OLDER: ("dpl_older", "STAGED")},
        served=LIVE,
        fallback_shas=f"{NEWEST}\n{OLDER}",
        promote_ok=False,
    ) as h:
        assert _run(["--promote-only"]) == 1
    assert h.promoted == ["dpl_older"]
    assert not h.created_a_deployment


# ---------------------------------------------------------------- innocence


def test_promote_only_still_returns_3_when_nothing_anywhere_is_ready():
    """No READY build for the newest, and none in the fallback window either — the exact
    pre-fallback contract (exit 3, nothing built) must survive unchanged."""
    with _Harness(ready_map={}, served=LIVE, fallback_shas=f"{NEWEST}\n{OLDER}") as h:
        assert _run(["--promote-only"]) == 3
    assert h.promoted == []
    assert not h.created_a_deployment


def test_fallback_is_never_consulted_when_the_newest_already_has_a_ready_build():
    """The primary target has a READY build — the fallback scan must not even run. Proven by
    a fallback log that, if consulted, would offer a DIFFERENT deployment than the one
    promoted."""
    with _Harness(
        ready_map={NEWEST: ("dpl_newest", "STAGED"), OLDER: ("dpl_older", "STAGED")},
        served=LIVE,
        fallback_shas=f"{NEWEST}\n{OLDER}",
    ) as h:
        assert _run(["--promote-only"]) == 0
    assert h.promoted == ["dpl_newest"]


def test_interactive_default_never_calls_the_fallback_and_still_builds():
    """Innocence for the unrestricted path: no --promote-only, no --dry-run. Even with a
    fallback candidate sitting fully READY, the interactive default must still go straight
    to the create-a-deployment path for the true target — it never needs the shortcut because
    it can build sha itself, and promoting a stale fallback here would silently downgrade what
    an interactive human asked to deploy."""
    with _Harness(
        ready_map={OLDER: ("dpl_older", "STAGED")},
        served=LIVE,
        fallback_shas=f"{NEWEST}\n{OLDER}",
    ) as h:
        _run([])
    assert h.created_a_deployment
    assert h.promoted == []
