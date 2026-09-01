"""Guilt AND innocence for the fleet dashboard's probes.

WHY THIS FILE EXISTS. Every defect this dashboard shipped in review was a probe
that answered a NEIGHBOURING question and looked fine doing it: bulk `UNKNOWN`
mergeability read as "no conflict", a `merge-tree` that could not start read as
"real conflict", and a checks probe whose silence rendered as "red, no reason
given" while quietly under-counting the grouped tally. None of those are caught
by asserting the happy path. So each probe here is pinned from BOTH sides — it
must fire when it should (guilt) and must stay silent when it should not
(innocence). A guard with only one of the two is how scar family #3 gets in.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "fleet_dashboard.py"


@pytest.fixture()
def fd():
    spec = importlib.util.spec_from_file_location("fleet_dashboard_under_test", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_returning(*result):
    return lambda *a, **k: result


def _run_dispatch_for_conflict_kind(merge_tree_result):
    """A stub that answers each of `conflict_kind`'s three subprocess calls
    truthfully for the ones it isn't testing, and returns `merge_tree_result`
    only for the `git merge-tree` call. `conflict_kind` calls `_run` three
    times in sequence (fetch, rev-parse, merge-tree); a single fixed return
    value answers the FIRST call and never reaches the one under test."""
    def _run(args, timeout=90):
        if args[:2] == ["git", "fetch"]:
            return (0, "", "")
        if args[:2] == ["git", "rev-parse"]:
            return (0, "cafef00d\n", "")
        if args[:2] == ["git", "merge-tree"]:
            return merge_tree_result
        raise AssertionError(f"conflict_kind made an unexpected _run call: {args}")
    return _run


CONFLICTING_PR = {"number": 1, "mergeable": "CONFLICTING", "headRefName": "some-branch"}


ROLLUP_OK = (
    '{"data":{"repository":{"pullRequest":{"commits":{"nodes":[{"commit":'
    '{"statusCheckRollup":{"contexts":{"nodes":['
    '{"name":"CI / build","conclusion":"FAILURE"},'
    '{"name":"CI / lint","conclusion":"SUCCESS"}]}}}}]}}}}}'
)


# --------------------------------------------------------------------------
# failing_checks: a probe that could not measure must SAY SO, on the page
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rc,out,err,why",
    [
        (1, "", "rate limit exceeded", "transport failure"),
        (0, "", "", "empty body with rc=0"),
        (0, "{not json", "", "malformed JSON"),
        (0, '{"data":{"repository":{"pullRequest":{"commits":{"nodes":[]}}}}}', "", "no commits"),
        (
            0,
            '{"data":{"repository":{"pullRequest":{"commits":{"nodes":'
            '[{"commit":{"statusCheckRollup":null}}]}}}}}',
            "",
            "no rollup, contradicting the bulk query",
        ),
    ],
)
def test_guilt_unreadable_probe_is_named_not_silently_empty(fd, monkeypatch, rc, out, err, why):
    """Every way the probe can fail must surface the sentinel, never a bare []."""
    monkeypatch.setattr(fd, "_run", _run_returning(rc, out, err))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert fd.failing_checks(1) == [fd.PROBE_UNREADABLE], f"silent [] on: {why}"


def test_innocence_a_real_answer_never_carries_the_sentinel(fd, monkeypatch):
    """Good data yields the failing check's real name and nothing else."""
    monkeypatch.setattr(fd, "_run", _run_returning(0, ROLLUP_OK, ""))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    names = fd.failing_checks(1)
    assert names == ["CI / build"], names
    assert fd.PROBE_UNREADABLE not in names


def test_innocence_a_passing_check_is_not_reported_as_failing(fd, monkeypatch):
    monkeypatch.setattr(fd, "_run", _run_returning(0, ROLLUP_OK, ""))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert "CI / lint" not in fd.failing_checks(1)


def test_the_sentinel_cannot_be_mistaken_for_a_check_name(fd):
    """It groups into the causes table beside real names, so it must not look like one."""
    assert not fd.PROBE_UNREADABLE[0].isalnum()
    assert "/" not in fd.PROBE_UNREADABLE


def test_an_unreadable_probe_also_says_so_on_stderr(fd, monkeypatch):
    """The page and the log must agree — one without the other is half an alarm."""
    buf = io.StringIO()
    monkeypatch.setattr(fd, "_run", _run_returning(1, "", "boom"))
    monkeypatch.setattr(sys, "stderr", buf)
    fd.failing_checks(4242)
    assert "checks unreadable for #4242" in buf.getvalue()


# --------------------------------------------------------------------------
# conflict_kind: rc!=0 means the merge could not START — never "real conflict"
# --------------------------------------------------------------------------

def test_guilt_a_merge_that_could_not_start_is_not_called_a_real_conflict(fd, monkeypatch):
    """Scar: conflating rc!=0 with rc==1 sends a reader to hand-resolve a
    `merge=union` ledger, which deletes other lanes' rows."""
    monkeypatch.setattr(
        fd, "_run",
        _run_dispatch_for_conflict_kind((128, "", "fatal: refusing to merge unrelated histories")),
    )
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert fd.conflict_kind(CONFLICTING_PR) == "unknown"


def test_innocence_a_clean_merge_tree_is_a_phantom(fd, monkeypatch):
    monkeypatch.setattr(fd, "_run", _run_dispatch_for_conflict_kind((0, "sometree", "")))
    assert fd.conflict_kind(CONFLICTING_PR) == "phantom"


def test_innocence_a_content_conflict_is_real(fd, monkeypatch):
    monkeypatch.setattr(fd, "_run", _run_dispatch_for_conflict_kind((1, "tree\nsome/file.py", "")))
    assert fd.conflict_kind(CONFLICTING_PR) == "real"


# --------------------------------------------------------------------------
# the Dependabot flag: the ENTITY and its login, not a substring of a name


# --------------------------------------------------------------------------
# a failing check is not only the one literally called "FAILURE"
# --------------------------------------------------------------------------

def _rollup(*contexts: dict) -> str:
    import json as _j
    return _j.dumps({"data": {"repository": {"pullRequest": {"commits": {"nodes": [
        {"commit": {"statusCheckRollup": {"contexts": {"nodes": list(contexts)}}}}]}}}}})


@pytest.mark.parametrize("verdict", sorted(v for v in
    {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR"}))
def test_guilt_every_failure_shaped_verdict_is_reported(fd, monkeypatch, verdict):
    """Testing `== "FAILURE"` alone left a red PR contributing to NO row in the
    causes table — it read as "nothing wrong here" by omission, which is worse
    than the unreadable sentinel because not even a row said the tally was short.
    """
    monkeypatch.setattr(fd, "_run", _run_returning(
        0, _rollup({"name": "CI / build", "conclusion": verdict}), ""))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert fd.failing_checks(1) == ["CI / build"], f"{verdict} was dropped"


@pytest.mark.parametrize("verdict", ["SUCCESS", "NEUTRAL", "SKIPPED", "STALE", "PENDING"])
def test_innocence_a_benign_verdict_is_never_reported_as_failing(fd, monkeypatch, verdict):
    monkeypatch.setattr(fd, "_run", _run_returning(
        0, _rollup({"name": "CI / build", "conclusion": verdict}), ""))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert fd.failing_checks(1) == []


def test_an_unknown_verdict_is_named_not_silently_dropped(fd, monkeypatch):
    """A value GitHub adds later belongs in neither list. Naming it errs toward
    "failing", which makes the page more alarming than reality — the safe
    direction, and the one every defect in this file got backwards."""
    monkeypatch.setattr(fd, "_run", _run_returning(
        0, _rollup({"name": "CI / build", "conclusion": "SOME_FUTURE_STATE"}), ""))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    names = fd.failing_checks(1)
    assert names == ["CI / build (SOME_FUTURE_STATE)"], names


def test_the_two_verdict_sets_do_not_overlap(fd):
    assert not (fd.FAILING_VERDICTS & fd.BENIGN_VERDICTS)


# --------------------------------------------------------------------------
# the Dependabot predicate: called, not grepped
# --------------------------------------------------------------------------

def test_guilt_a_real_dependabot_pr_is_flagged(fd):
    assert fd.is_dependabot({"author": {"__typename": "Bot", "login": "dependabot"}})


@pytest.mark.parametrize("author,why", [
    ({"__typename": "Bot", "login": "renovate"}, "another bot shares the Bot type"),
    ({"__typename": "Bot", "login": "github-actions"}, "so does github-actions"),
    ({"__typename": "User", "login": "dependabot"}, "a human could take the name"),
    ({}, "no author fields at all"),
    (None, "author absent"),
])
def test_innocence_only_dependabot_is_flagged(fd, author, why):
    """Pins the AND. Flipping it to OR reinstated the 'is any bot' bug while the
    old source-grep test stayed green — two substrings never pinned their join."""
    assert not fd.is_dependabot({"author": author}), why


# --------------------------------------------------------------------------
# the main-checkout warning: behaviour, not a forbidden literal
# --------------------------------------------------------------------------

def test_guilt_a_primary_checkout_under_any_name_is_warned_about(fd, monkeypatch, tmp_path):
    """Forbidding the literal `GIT_CWD.name ==` did not stop `!=` with an early
    return from reinstating name-dependence. This calls the function instead."""
    odd = tmp_path / "a-clone-named-something-else"
    (odd / ".git").mkdir(parents=True)
    buf = io.StringIO()
    monkeypatch.setattr(fd, "GIT_CWD", odd)
    monkeypatch.setattr(sys, "stderr", buf)
    fd._warn_if_main_checkout()
    assert "MAIN checkout" in buf.getvalue()


def test_innocence_a_linked_worktree_is_not_warned_about(fd, monkeypatch, tmp_path):
    """In a linked worktree `.git` is a FILE pointing at the real object store."""
    wt = tmp_path / "nuzantara"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /somewhere/else\n")
    buf = io.StringIO()
    monkeypatch.setattr(fd, "GIT_CWD", wt)
    monkeypatch.setattr(sys, "stderr", buf)
    fd._warn_if_main_checkout()
    assert buf.getvalue() == ""
