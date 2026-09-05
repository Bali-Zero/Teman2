#!/usr/bin/env python3
"""Corpus for `--promote-only`: the mode a CRON is allowed to run.

WHY THIS EXISTS
---------------
On 2026-08-21 production served a build ~22 hours old while three READY production builds sat
on Vercel unaliased, and the Frontend Live Sentinel had gone red 13 consecutive times and
DELIVERED its Telegram each time. Detection worked, the cure worked, nothing connected them:
every merge waited for a human to run the promote. The connection being added is a cron on
Mini — the one machine with both the Vercel CLI and a live credential.

A cron must not have the authority the interactive script has. Left at its default, when no
READY build exists for the target commit `main()` CREATES one: ~6 minutes plus build minutes,
every 15 minutes, unattended. "No build exists" is an anomaly that deserves eyes, not an
unattended rebuild loop — so `--promote-only` promotes what is there and refuses to build.

The three outcomes are deliberately distinct, because a wrapper reading a single failure bit
cannot tell "the promote broke" from "there was nothing to promote", and those need different
human responses:

    0  nothing to do (production already current), or promoted successfully
    1  a promote was attempted and did not move the domains
    3  no READY build for the target commit — nothing was built, deliberately
       (3 and not 2: argparse exits 2 on an unrecognised flag, and a wrapper that
        cannot tell those apart reports "nothing to promote" while nothing ran)

Guilt AND innocence, per superscar #3: the guilt cases prove it promotes when it should, the
innocence cases prove it never reaches `POST /v13/deployments` and never touches the default
path. No network: `_api` is replaced per-case and every call it receives is recorded.
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
OLD = "aaaa111122223333444455556666777788889999"

CREATE_PATH = "/v13/deployments"


class _Harness:
    """Patch every boundary `main()` crosses, and record the API calls it makes."""

    def __init__(self, *, ready, served, promote_ok=True):
        self.ready = ready
        self.served = served
        self.promote_ok = promote_ok
        self.calls: list[tuple[str, str]] = []
        self.promoted: list[str] = []

    def _api(self, method, path, body=None):
        self.calls.append((method, path))
        if method == "POST" and path == CREATE_PATH:
            return 201, {"id": "dpl_created", "readyState": "QUEUED"}
        return 200, {}

    def _promote(self, dpl, sha):
        self.promoted.append(dpl)
        return self.promote_ok

    def __enter__(self):
        self._patches = [
            unittest.mock.patch.object(vpd, "_api", side_effect=self._api),
            unittest.mock.patch.object(vpd, "_promote", side_effect=self._promote),
            unittest.mock.patch.object(vpd, "_deploy_relevant_head", return_value=(SHA, "test")),
            unittest.mock.patch.object(vpd, "_served_commit", return_value=self.served),
            unittest.mock.patch.object(vpd, "_ready_deployment_for", return_value=self.ready),
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

def test_promotes_the_staged_build_when_production_is_behind(capsys):
    """The 2026-08-21 shape: a READY build exists, the domains point elsewhere."""
    with _Harness(ready=("dpl_staged", "STAGED"), served=OLD) as h:
        assert _run(["--promote-only"]) == 0
    assert h.promoted == ["dpl_staged"]
    assert not h.created_a_deployment
    output = capsys.readouterr().out
    assert "OK — kita.balizero.com serves" in output
    assert "OK — balizero.com serves" not in output


def test_returns_3_and_builds_NOTHING_when_no_ready_build_exists():
    """The whole point of the flag. Exit 3 is 'needs eyes', not 'cure failed'."""
    with _Harness(ready=None, served=OLD) as h:
        assert _run(["--promote-only"]) == 3
    assert h.promoted == []
    assert not h.created_a_deployment


def test_returns_1_when_the_promote_does_not_move_the_domains():
    """A failed promote must NOT silently fall through to a rebuild under this flag."""
    with _Harness(ready=("dpl_staged", "STAGED"), served=OLD, promote_ok=False) as h:
        assert _run(["--promote-only"]) == 1
    assert h.promoted == ["dpl_staged"]
    assert not h.created_a_deployment


# ---------------------------------------------------------------- innocence

def test_does_nothing_at_all_when_production_is_already_current():
    """The ordinary cron tick: ~every run. It must be silent and free."""
    with _Harness(ready=("dpl_staged", "STAGED"), served=SHA) as h:
        assert _run(["--promote-only"]) == 0
    assert h.promoted == []
    assert not h.created_a_deployment


def test_dry_run_still_changes_nothing_under_promote_only():
    with _Harness(ready=None, served=OLD) as h:
        assert _run(["--promote-only", "--dry-run"]) == 0
    assert h.promoted == []
    assert not h.created_a_deployment


def test_the_no_build_code_is_not_argparses_own_usage_code():
    """Guards the distinction the wrapper depends on, at the boundary that owns it.

    argparse exits 2 for "unrecognised flag". If the no-build code were also 2, a wrapper
    reading the code alone would report the benign outcome while the script had in fact
    refused the command and cured nothing — measured live on Mini against the pre-merge copy.
    """
    with _Harness(ready=None, served=OLD):
        no_build = _run(["--promote-only"])
    with unittest.mock.patch.object(sys, "argv", ["vercel_prod_deploy.py", "--no-such-flag"]):
        with pytest.raises(SystemExit) as exc:
            vpd.main()
    assert exc.value.code == 2, "argparse's usage code changed — recheck the wrapper's mapping"
    assert no_build != exc.value.code


def test_WITHOUT_the_flag_the_build_path_is_untouched():
    """Innocence for the interactive default: no READY build still means BUILD.

    This is the case that proves the flag adds a mode instead of removing one — if this ever
    goes green by not creating a deployment, the cron's restriction leaked into the tool a
    human runs by hand.
    """
    with _Harness(ready=None, served=OLD) as h:
        _run([])
    assert h.created_a_deployment
