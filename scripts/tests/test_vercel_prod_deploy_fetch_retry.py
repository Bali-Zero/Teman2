#!/usr/bin/env python3
"""Corpus for the one network step in the unattended path: refreshing origin/main.

WHY THIS EXISTS
---------------
Measured on Mini, 2026-08-21, the day the organ was armed. Of its first five unattended runs,
four resolved the bundle-relevant commit in ~4s and one could not fetch at all. It degraded
correctly — it refused to promote against main HEAD rather than act on a commit Vercel had
skipped — and the tick 15 minutes later recovered on its own. But two things were wrong with
that minute:

  1. A single blip cost 15 minutes of blindness, on a machine whose network measurably flaps:
     the system log shows three network-configuration changes and a Wi-Fi change in the five
     minutes before the failure, and the *good* run that followed took 39s against a usual 4s.
     A lone transient must not reach the degrade at all (superscar #8: wrap the one-shot
     network action in a bounded retry).

  2. The degrade said "git fetch failed" and threw away what git actually said. `_git` collapses
     a refused connection, DNS, a bad credential and a 120s timeout into one `None`, so the
     message could not name the cause — and those four need different answers. Discriminator
     available that day and invisible in the log: `gh api` over HTTPS answered in the same
     second the SSH fetch failed, which points at the transport, not at connectivity. A message
     that does not name its cause sends the reader away from it (W106).

Bounded, not persistent: three attempts at a 120s timeout each plus backoff still ends far
inside the 900s cadence, so a genuinely dead network degrades on THIS tick instead of wedging
the organ into the next one.

Guilt AND innocence (superscar #3). Guilt: it retries, it recovers, and the failure carries
git's own words. Innocence: a healthy fetch still produces the good answer, and the retry never
wraps the read-only git calls — retrying a deterministic read buys nothing and would triple the
cost of a wedge.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

REPO = pathlib.Path(__file__).resolve().parents[2]
WRAPPER = REPO / "infra/launchagents/wrappers/mini-vercel-autopromote.sh"
PLIST = REPO / "infra/launchagents/com.nuzantara.vercel-autopromote.plist"


def _cadence_s() -> int:
    """The organ's tick, READ from the plist that defines it.

    Hardcoding 900 here would be a measure of the world frozen into a constant: true the day it
    was written, and silently wrong the day someone lowers StartInterval — with this test still
    green while the retry outlives the tick (W106). The bound has to be asked, not remembered.
    """
    m = re.search(
        r"<key>StartInterval</key>\s*<integer>(\d+)</integer>",
        PLIST.read_text(encoding="utf-8"),
    )
    assert m, "the plist no longer declares a StartInterval — re-pin this test"
    return int(m.group(1))
SHA = "665bfd40d77b10c3bac91a9e3d3309a4df3c186f"


class _Recorder:
    """Stands in for subprocess.run, replaying a scripted sequence of outcomes."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        outcome = self.outcomes.pop(0) if self.outcomes else "ok"
        if outcome == "ok":
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 120)
        raise subprocess.CalledProcessError(128, args, output="", stderr=outcome)


@pytest.fixture
def naps(monkeypatch):
    """Backoff without the wall-clock: record what it WOULD have slept."""
    slept: list[float] = []
    monkeypatch.setattr(vpd.time, "sleep", slept.append)
    return slept


# ---------------------------------------------------------------- guilt: it retries

def test_a_healthy_fetch_runs_once_and_never_sleeps(monkeypatch, naps):
    rec = _Recorder("ok")
    monkeypatch.setattr(vpd.subprocess, "run", rec)
    ok, detail = vpd._fetch_main()
    assert ok is True
    assert len(rec.calls) == 1, "a fetch that worked must not be repeated"
    assert naps == [], "nothing to back off from"
    assert "1" in detail


def test_a_transient_failure_is_ridden_out_instead_of_degrading(monkeypatch, naps):
    """The measured case: the blip that cost 15 minutes of blindness must now cost seconds."""
    rec = _Recorder("ssh: connect to host github.com port 22: Operation timed out", "ok")
    monkeypatch.setattr(vpd.subprocess, "run", rec)
    ok, _ = vpd._fetch_main()
    assert ok is True, "one blip must not reach the degrade"
    assert len(rec.calls) == 2
    assert len(naps) == 1, "it waited before the retry rather than hammering"


def test_the_retry_is_bounded_and_ends_inside_the_tick(monkeypatch, naps):
    rec = _Recorder(*(["fatal: could not read from remote repository"] * 20))
    monkeypatch.setattr(vpd.subprocess, "run", rec)
    ok, _ = vpd._fetch_main()
    assert ok is False
    assert len(rec.calls) == vpd.FETCH_ATTEMPTS
    # A retry that outlives the tick would wedge the organ into the next one. The cadence comes
    # from the plist, so lowering StartInterval without shortening the retry turns this red.
    worst = vpd.FETCH_ATTEMPTS * 120 + sum(naps)
    assert worst < _cadence_s(), f"worst-case fetch {worst}s >= tick {_cadence_s()}s"


# ------------------------------------------------- guilt: the failure names its own cause

def test_an_exhausted_fetch_carries_gits_own_words(monkeypatch, naps):
    said = "ssh: connect to host github.com port 22: Connection refused"
    monkeypatch.setattr(vpd.subprocess, "run", _Recorder(said, said, said))
    ok, detail = vpd._fetch_main()
    assert ok is False
    assert "port 22" in detail, f"the cause was thrown away again: {detail!r}"


def test_a_timeout_is_distinguishable_from_a_refusal(monkeypatch, naps):
    monkeypatch.setattr(vpd.subprocess, "run", _Recorder("timeout", "timeout", "timeout"))
    ok, detail = vpd._fetch_main()
    assert ok is False
    assert "timed out" in detail.lower()
    assert "refused" not in detail.lower()


def test_the_degrade_message_reaches_the_operator_with_the_cause(monkeypatch):
    monkeypatch.setattr(vpd, "_fetch_main", lambda: (False, "ssh: Connection refused"))
    monkeypatch.setattr(vpd, "_main_head", lambda: "deadbeef" * 5)
    _, how = vpd._deploy_relevant_head()
    assert "Connection refused" in how, f"the log line still hides the cause: {how!r}"


def test_the_degrade_message_still_matches_the_wrappers_own_pattern(monkeypatch):
    """The cure and the wrapper are two halves of one contract, in two languages.

    The wrapper classifies this run as an ERROR only by grepping the cure's stdout. Rewording
    the message without this pin turns the loudest failure into a benign 'nothing to promote'
    — armed, and reporting the wrong thing.
    """
    pattern = re.search(
        r"grep -q '(main HEAD[^']*)'", WRAPPER.read_text(encoding="utf-8")
    )
    assert pattern, "the wrapper no longer greps for a degraded target — re-pin this test"
    needle = pattern.group(1)

    monkeypatch.setattr(vpd, "_main_head", lambda: "deadbeef" * 5)
    monkeypatch.setattr(vpd, "_fetch_main", lambda: (False, "ssh: Connection refused"))
    _, fetch_degrade = vpd._deploy_relevant_head()
    monkeypatch.setattr(vpd, "_fetch_main", lambda: (True, "attempt 1"))
    monkeypatch.setattr(vpd, "_git", lambda *a: None)
    _, log_degrade = vpd._deploy_relevant_head()
    monkeypatch.setattr(vpd, "_git", lambda *a: "")
    _, empty_degrade = vpd._deploy_relevant_head()

    # ALL THREE fallbacks, not the two that happen to say "git". The third was invisible to the
    # original marker, so the wrapper wrote a clean `ok` over a cure that had degraded -- one
    # axis verified, a claim made about the guard.
    for message in (fetch_degrade, log_degrade, empty_degrade):
        assert needle in message, f"wrapper greps {needle!r}, cure now says {message!r}"


# ---------------------------------------------------------------------- innocence

def test_a_healthy_fetch_still_produces_the_bundle_relevant_answer(monkeypatch):
    monkeypatch.setattr(vpd, "_fetch_main", lambda: (True, "attempt 1"))
    monkeypatch.setattr(vpd, "_git", lambda *a: SHA)
    sha, how = vpd._deploy_relevant_head()
    assert sha == SHA
    assert "bundle-relevant" in how
    assert "main HEAD" not in how, "the good path must never look like a degrade"


def test_the_retry_never_wraps_the_read_only_git_calls(monkeypatch, naps):
    """`git log` is deterministic: repeating it cannot change the answer, and retrying every
    git call would triple the cost of a wedge instead of shortening it."""
    rec = _Recorder("fatal: bad revision", "fatal: bad revision", "fatal: bad revision")
    monkeypatch.setattr(vpd.subprocess, "run", rec)
    assert vpd._git("log", "-1", "--format=%H") is None
    assert len(rec.calls) == 1, "a read-only git call was retried"
    assert naps == []


def test_an_empty_history_is_still_not_a_fetch_failure(monkeypatch):
    """Innocence for the third branch: 'no bundle commit exists' must not be reported as a
    broken fetch, because they call for opposite responses."""
    monkeypatch.setattr(vpd, "_fetch_main", lambda: (True, "attempt 1"))
    monkeypatch.setattr(vpd, "_git", lambda *a: "")
    monkeypatch.setattr(vpd, "_main_head", lambda: "deadbeef" * 5)
    _, how = vpd._deploy_relevant_head()
    assert "no commit in history" in how
    assert "failed" not in how
