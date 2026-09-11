"""Guilt + innocence for `scripts/lane_outcome_report.py`.

THE TEST THIS CORPUS EXISTS FOR is `test_the_origin_must_be_EARLIER_than_the_fix`.
The first implementation sliced `commits[:i]` to mean "commits before i" while
`git log` returns NEWEST FIRST, so every "origin" was a commit from the FUTURE of
the fix that supposedly corrected it. Measured on the real 2026-08-20..23 window:

  * before the cure: 26 chains
  * after:           21 chains
  * (fix, origin) pairs in common: ZERO of 21

So the defect corrupted the count AND every single attribution, and — this is the
part worth remembering — the BROKEN number (26) sits inside the spec's ±3
acceptance band around a hand-measured 27, while the CORRECT number (21) does not.
An implementation can pass its acceptance criterion precisely by being wrong. The
spec says in its own words that "±3 agreement is not validation of the heuristic";
this corpus is what validates it instead.

Everything here is pure — `files_for` is injected, no git, no network, no clock.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("lane_outcome_report", _SCRIPTS / "lane_outcome_report.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: `@dataclass` resolves `cls.__module__` through
    # `sys.modules` while processing the class, and a module that is not there
    # yet makes it fail with a bare `'NoneType' object has no attribute
    # '__dict__'` that says nothing about the real cause.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _c(sha: str, ts: int, subject: str):
    return mod.Commit(sha=sha, ts=ts, subject=subject, pr=mod.parse_pr_number(subject))


# ------------------------------------------------------------------ the ordering


def test_the_origin_must_be_EARLIER_than_the_fix() -> None:
    """Fed a NEWEST-FIRST list, exactly as `git log` produces it.

    `feat` is older than `fix` and they share a file, so the pair is a real
    correction. An implementation that trusts list position instead of the clock
    finds nothing here (the only candidate sits AFTER the fix in the list), so
    this case is red for the shape the first version shipped.
    """
    newest_first = [
        _c("bbb", 200, "fix(x): repair the thing (#2)"),
        _c("aaa", 100, "feat(x): the thing (#1)"),
    ]
    files = {"aaa": frozenset({"src/x.py"}), "bbb": frozenset({"src/x.py"})}
    chains = mod.correction_chains(newest_first, files.__getitem__)

    assert len(chains) == 1, chains
    assert chains[0].fix_sha == "bbb" and chains[0].origin_sha == "aaa"


def test_a_fix_is_never_corrected_by_a_LATER_commit() -> None:
    """The inverse: the only overlapping non-fix commit came AFTER the fix.

    Nothing in the window explains this fix, so it is not a correction chain.
    The buggy version reported it as one.
    """
    commits = [
        _c("bbb", 300, "feat(x): later work (#2)"),
        _c("aaa", 100, "fix(x): repair (#1)"),
    ]
    files = {"aaa": frozenset({"src/x.py"}), "bbb": frozenset({"src/x.py"})}
    assert mod.correction_chains(commits, files.__getitem__) == []


def test_the_EARLIEST_overlapping_origin_is_the_one_reported() -> None:
    commits = [
        _c("fix", 400, "fix(x): repair (#3)"),
        _c("mid", 200, "feat(x): second touch (#2)"),
        _c("old", 100, "feat(x): first touch (#1)"),
    ]
    files = {k: frozenset({"src/x.py"}) for k in ("old", "mid", "fix")}
    chains = mod.correction_chains(commits, files.__getitem__)

    assert len(chains) == 1
    assert chains[0].origin_sha == "old", "reported a later origin than the earliest overlapping one"


def test_a_fix_that_touches_a_DIFFERENT_surface_is_not_a_correction() -> None:
    """The whole reason the metric is file-overlap and not the subject prefix.

    A `fix:` subject over an unrelated file corrects nothing in this window, and
    counting it would reward relabelling — Goodhart, straight into the metric.
    """
    commits = [
        _c("bbb", 200, "fix(y): unrelated repair (#2)"),
        _c("aaa", 100, "feat(x): the thing (#1)"),
    ]
    files = {"aaa": frozenset({"src/x.py"}), "bbb": frozenset({"src/y.py"})}
    assert mod.correction_chains(commits, files.__getitem__) == []


def test_a_fix_correcting_another_fix_does_not_count() -> None:
    """The origin must be a non-fix commit, or a fix-of-a-fix chain double-counts
    the same underlying defect."""
    commits = [
        _c("ccc", 300, "fix(x): repair the repair (#3)"),
        _c("bbb", 200, "fix(x): repair (#2)"),
    ]
    files = {k: frozenset({"src/x.py"}) for k in ("bbb", "ccc")}
    assert mod.correction_chains(commits, files.__getitem__) == []


def test_high_churn_paths_are_removed_from_BOTH_sides() -> None:
    """Measured on the real window: `.claude/skills/modus/PENDING-ARMS.md` is the
    shared file for several reported chains — a ledger nearly every PR touches, so
    it manufactures overlap between commits that have nothing to do with each
    other. Excluding it from one side only would still match.
    """
    ledger = ".claude/skills/modus/PENDING-ARMS.md"
    commits = [
        _c("bbb", 200, "fix(x): repair (#2)"),
        _c("aaa", 100, "feat(y): unrelated (#1)"),
    ]
    files = {"aaa": frozenset({ledger, "src/y.py"}), "bbb": frozenset({ledger, "src/x.py"})}

    assert len(mod.correction_chains(commits, files.__getitem__)) == 1
    assert mod.correction_chains(commits, files.__getitem__, frozenset({ledger})) == []


def test_a_fix_and_its_origin_landing_in_the_SAME_SECOND_still_chain(tmp_path: Path) -> None:
    """A merge queue lands several squash commits in one second.

    The first guard was `earlier.ts >= commit.ts`, which rejected every
    same-second pair — so a fix and the commit it corrected could never chain if
    they landed together, a silent undercount precisely on the busiest batches.
    The docstring already promised ties would be resolved by position; the code
    did the opposite.
    """
    same_second = [
        _c("bbb", 100, "fix(x): repair (#2)"),
        _c("aaa", 100, "feat(x): the thing (#1)"),
    ]
    files = {k: frozenset({"src/x.py"}) for k in ("aaa", "bbb")}
    chains = mod.correction_chains(same_second, files.__getitem__)

    assert len(chains) == 1, "a same-second pair was rejected"
    assert chains[0].origin_sha == "aaa"


@pytest.mark.parametrize(
    "hours,expected_p90",
    [
        ([1.0, 100.0], 100.0),  # n=2: int() truncation reported the MINIMUM here
        ([1.0], 1.0),
        ([1.0, 2.0, 3.0, 100.0], 100.0),
    ],
)
def test_p90_is_never_below_the_median_and_never_the_minimum(hours, expected_p90) -> None:
    """`int((n-1)*0.9)` truncates to index 0 at n=2, so `[1h, 100h]` came back as
    "p90 1h". A percentile that can return the smallest sample is not a
    percentile."""
    prs = [
        {"createdAt": "2026-08-01T00:00:00Z", "mergedAt": _plus(h)}
        for h in hours
    ]
    t = mod.time_to_merge(prs)
    assert t["p90_hours"] == expected_p90, t
    assert t["p90_hours"] >= t["median_hours"], t


def _plus(hours: float) -> str:
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return (base + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_the_rate_denominator_excludes_fixes_that_CANNOT_chain() -> None:
    """A fix whose only file is high-churn can never chain, by construction.

    Counting it in the denominator deflates the rate by exactly the number of
    fixes the exclusion made ineligible — so the harder you tune the noise
    filter, the better the rate looks. A metric that pays you to hide its own
    inputs.

    Measured on the real window this does NOT move (every fix there touches
    something besides the ledger), which is why it is pinned here: without a
    fixture the branch would be unexercised code that looks like a safeguard.
    """
    ledger = ".claude/skills/modus/PENDING-ARMS.md"
    commits = [
        _c("ccc", 300, "fix(ledger): only the ledger (#3)"),
        _c("bbb", 200, "fix(x): real repair (#2)"),
        _c("aaa", 100, "feat(x): the thing (#1)"),
    ]
    files = {
        "aaa": frozenset({"src/x.py"}),
        "bbb": frozenset({"src/x.py"}),
        "ccc": frozenset({ledger}),
    }
    high = frozenset({ledger})
    # Call the MODULE's rule, never a copy of it. The first version of this test
    # recomputed the comprehension inline, so the mutation that deleted the
    # eligibility check from the source survived — the test was proving only that
    # it could do arithmetic.
    assert mod.eligible_fix_commits(commits, files.__getitem__, high) == 1
    assert mod.eligible_fix_commits(commits, files.__getitem__, frozenset()) == 2
    assert len(mod.correction_chains(commits, files.__getitem__, high)) == 1


def test_a_duplicated_commit_is_neither_its_own_origin_nor_two_chains() -> None:
    """A duplicated entry in the input made a commit its own origin and emitted
    the same chain twice, inflating the rate."""
    dup = _c("fix", 200, "fix(x): repair (#2)")
    commits = [dup, dup, _c("aaa", 100, "feat(x): the thing (#1)")]
    files = {"aaa": frozenset({"src/x.py"}), "fix": frozenset({"src/x.py"})}
    chains = mod.correction_chains(commits, files.__getitem__)

    assert len(chains) == 1, chains
    assert chains[0].origin_sha == "aaa", "a commit became its own origin"


def test_a_real_repo_subject_without_conventional_punctuation_still_counts() -> None:
    """`fix queue baseline census and public timing (#4047)` is a REAL squash
    subject here and is plainly a fix; requiring `:` or `(` dropped it from BOTH
    the numerator and the denominator."""
    assert mod.is_fix("fix queue baseline census and public timing (#4047)")
    assert not mod.is_fix("fixup! fix(x): repair (#9)")
    assert not mod.is_fix("prefix: still not a fix")


def test_the_pr_marker_must_be_at_the_LITERAL_end() -> None:
    """Python's `$` also matches just before a final newline, so a subject with a
    trailing newline was accepted although the marker is not where the function
    promises it is."""
    assert mod.parse_pr_number("fix: x (#42)") == 42
    assert mod.parse_pr_number("fix: x (#42)\n") is None


def test_a_duplicated_PR_number_is_counted_once() -> None:
    """`number` was fetched and never used, so a duplicated row counted twice in
    the denominator and once more in the numerator: 2/3 where the truth is 1/2."""
    rows = [
        {"number": 1, "headRefName": "agent/mini-pro2/craft-l/x"},
        {"number": 1, "headRefName": "agent/mini-pro2/craft-l/x"},
        {"number": 2, "headRefName": "docs/auto-sync-1"},
    ]
    a = mod.attribution(mod._dedupe_prs(rows))
    assert (a["attributed"], a["total"]) == (1, 2), a


def test_a_negative_duration_is_discarded_and_counted_not_averaged_in() -> None:
    """A merge before its own creation is clock skew, never a latency. Letting it
    into the distribution can drag the median and even the p90 negative."""
    t = mod.time_to_merge(
        [
            {"createdAt": "2026-08-01T02:00:00Z", "mergedAt": "2026-08-01T01:00:00Z"},
            {"createdAt": "2026-08-01T00:00:00Z", "mergedAt": "2026-08-01T05:00:00Z"},
        ]
    )
    assert t["n"] == 1 and t["negative_discarded"] == 1, t
    assert t["median_hours"] == 5.0 and t["p90_hours"] >= 0.0, t


@pytest.mark.parametrize(
    "tail,expected",
    [
        (b"", ""),                 # new/empty file: the heading may start at byte 0
        (b"e\n", "\n"),            # ends with a newline but no blank line
        (b"\n\n", ""),             # already separated
        (b"line", "\n\n"),         # no terminal newline at all — the worst case
    ],
)
def test_the_appended_section_is_separated_by_a_BLANK_line(tail: bytes, expected: str) -> None:
    """The tool must not generate output that fails the repo's own formatter.

    Markdown wants a blank line before a heading and this repo's prettier check
    enforces it, so without the separator every PR that ran `--write` would be
    blocked by the report it had just published. Measured: prettier's ONLY
    complaint about the first generated section was exactly this missing line.

    `b"line"` is the worse case: the `## ` heading concatenates onto the last
    line and renders as prose, so the section is published and is not a section.
    """
    assert mod.separator_for(tail) == expected


def test_the_rendered_section_is_a_heading_and_ends_cleanly() -> None:
    md = mod.render_markdown(
        mod.build_report(since="2026-08-20", until="2026-08-20", use_gh=False),
        "2026-08-20",
        "2026-08-20",
        "mini",
    )
    assert md.startswith("## ") and md.endswith("\n"), repr(md[:40] + " ... " + md[-20:])


# --------------------------------------------------------------------- the parser


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("feat(db): migration 299 (#5335)", 5335),
        ("fix: a thing (#1)", 1),
        ("chore: mentions (#123) in the middle", None),  # not a merge marker
        ("no marker at all", None),
        ("trailing space (#42) ", None),
    ],
)
def test_parse_pr_number_is_anchored_at_the_END(subject: str, expected: int | None) -> None:
    """204/204 real squash subjects end in `(#NNNN)`. A `(#123)` mid-subject is
    prose, not a merge marker, and treating it as one attributes a commit to
    whatever PR its author happened to mention."""
    assert mod.parse_pr_number(subject) == expected


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("fix: x", True),
        ("fix(scope): x", True),
        ("prefix: not a fix", False),
        ("Fix: capitalised", False),
        (" fix: leading space", False),
        ("feat: x", False),
    ],
)
def test_is_fix_is_anchored_at_the_START(subject: str, expected: bool) -> None:
    """`prefix:` contains `fix` — the substring trap (superscar #3) applied to
    this module's own candidate filter."""
    assert mod.is_fix(subject) is expected


# ---------------------------------------------------------------- attribution


def test_attribution_parses_host_and_lane_from_the_branch() -> None:
    prs = [
        {"headRefName": "agent/mini-pro2/craft-l/home-fork-bak-discover"},
        {"headRefName": "agent/air-m5/ops/vercel-autopromote"},
        {"headRefName": "docs/auto-sync-1234"},
    ]
    a = mod.attribution(prs)
    assert a["total"] == 3 and a["attributed"] == 2
    assert a["by_host"] == {"mini-pro2": 1, "air-m5": 1}
    assert a["by_lane"]["craft-l"] == 1


def test_attribution_never_crashes_on_a_missing_branch_and_never_divides_by_zero() -> None:
    assert mod.attribution([])["share"] == 0.0
    a = mod.attribution([{"headRefName": None}, {}, {"headRefName": ""}])
    assert a["total"] == 3 and a["attributed"] == 0 and a["share"] == 0.0


# ------------------------------------------------------------------- honesty


def test_nothing_in_this_module_calls_it_time_to_GREEN() -> None:
    """True time-to-green needs check-suite history this module never fetches.

    Calling `mergedAt - createdAt` "time-to-green" would be a claim about CI that
    nothing here measured — the exact shape of over-claim these lanes exist to
    catch. The name is pinned so a future edit cannot quietly upgrade it.
    """
    # Judge the ENTITY, not the form. The first version of this test grepped the
    # source and went red on the module's own docstring, which says "never
    # `time_to_green`" — i.e. it flagged the prose that ENFORCES the rule. Same
    # over-match class this repo files under superscar #3, committed inside the
    # test written to prevent an over-claim.
    #
    # What actually matters is what the module NAMES things: its public symbols
    # and the keys it emits, because those are what a downstream reader consumes.
    symbols = [n for n in dir(mod) if not n.startswith("_")]
    assert not [n for n in symbols if "green" in n.lower()], symbols

    report = mod.build_report(since="2026-08-20", until="2026-08-20", use_gh=False)
    keys = set()

    def _walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                keys.add(str(k))
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    _walk(report)
    assert not [k for k in keys if "green" in k.lower()], sorted(keys)


def test_skipping_gh_is_reported_as_skipped_not_as_zero() -> None:
    """`--no-gh` must be distinguishable from "fetched and found nothing".

    Without the marker a caller reads 0% attribution and concludes the fleet is
    unattributed, when in fact nobody asked. Superscar #2 in a report field.

    The first version of this test asserted the EXIT CODE and nothing else, so a
    mutation pinning the marker to "fetched" — the exact lie the test is named
    for — survived it. Third vacuous fixture of this lane, all three found by
    mutation rather than by reading.
    """
    skipped = mod.build_report(since="2026-08-20", until="2026-08-20", use_gh=False)
    assert skipped["gh"] == "skipped", skipped["gh"]
    assert skipped["attribution"]["total"] == 0

    # And the opposite state must be distinguishable, or the marker is a constant
    # wearing the costume of a measurement.
    #
    # `_fetch_prs` is STUBBED, not called. The first version invoked the real one,
    # which shells out to `gh` — so this "pure" unit test would have failed on a
    # CI runner with no token, for the runner's auth state rather than for the
    # source's behaviour. A red that can mean two things is worse than no test.
    real = mod._fetch_prs
    mod._fetch_prs = lambda repo, since, until: [
        {"number": 1, "headRefName": "agent/mini-pro2/craft-l/x",
         "createdAt": "2026-08-29T00:00:00Z", "mergedAt": "2026-08-29T01:00:00Z"}
    ]
    try:
        fetched = mod.build_report(since="2026-08-29", until="2026-08-30", use_gh=True)
    finally:
        mod._fetch_prs = real
    assert fetched["gh"] == "fetched", fetched["gh"]
    assert fetched["attribution"]["attributed"] == 1
