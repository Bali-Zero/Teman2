"""Tests for the PENDING-ARMS ratchet layer (scripts/pending_arms_report.py).

WHY delta-at-frozen-now, not a snapshot compared against the moving calendar:
`compute_counts()["tech_debt_overdue"]` is itself a function of `now` — every
row that was FRESH the day it was opened silently becomes overdue two days
later with zero code change and zero new debt authored. A gate that compared
a stored absolute count (e.g. "main had 440 overdue rows when this PR was
opened") against today's absolute count on HEAD would therefore redden an
otherwise-innocent PR roughly 48h after ANY existing row ages past the
overdue boundary — the PR did nothing, the calendar did. The only quantity
that is actually attributable to a PR's own diff is the DELTA between BASE
and HEAD evaluated at the *same* `now` (or, as this module also enforces:
the delta stays identical across ANY two `now` values, because ageing moves
both sides of the subtraction together). `ratchet_verdict()` is built on
that invariant: it takes two already-computed overdue counts (base, head)
and never touches a calendar itself.

Module is imported via importlib.util.spec_from_file_location (not a package
import), matching scripts/tests/test_pending_arms_report.py, because
scripts/ is a flat bag of standalone tools, not a Python package.

The three functions this suite targets — parse_ratchet_overrides,
ratchet_verdict, ratchet_selftest — are being implemented in
scripts/pending_arms_report.py in parallel with this file. Until that lands,
every test below errors with AttributeError on `par.<name>` — expected, and
reported as such rather than papered over with a stub (stubs belong in the
implementation module, never in a test file that is supposed to fail loud
until the real thing exists).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "pending_arms_report.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pending_arms_report", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


par = _load_module()

# Same frozen-date convention as the sibling report test file.
NOW = "2026-07-05"
NOW_PLUS_30 = "2026-08-04"

EM_DASH = "—"


# ---------------------------------------------------------------------------
# A. parse_ratchet_overrides
# ---------------------------------------------------------------------------


def test_em_dash_form_parses():
    text = (
        f"RATCHET-OVERRIDE: tech_debt_overdue<=445 {EM_DASH} widened for the "
        "S12 evidence-pack cutover\n"
    )
    overrides = par.parse_ratchet_overrides(text)
    assert len(overrides) == 1
    o = overrides[0]
    assert o["ceiling"] == 445
    assert o["reason"] == "widened for the S12 evidence-pack cutover"
    assert o["valid"] is True


def test_ascii_double_hyphen_form_parses_identically():
    text = (
        "RATCHET-OVERRIDE: tech_debt_overdue<=445 -- widened for the "
        "S12 evidence-pack cutover\n"
    )
    overrides = par.parse_ratchet_overrides(text)
    assert len(overrides) == 1
    o = overrides[0]
    assert o["ceiling"] == 445
    assert o["reason"] == "widened for the S12 evidence-pack cutover"
    assert o["valid"] is True


def test_html_comment_wrapped_form_parses_identically():
    text = (
        f"<!-- RATCHET-OVERRIDE: tech_debt_overdue<=445 {EM_DASH} widened for "
        "the S12 evidence-pack cutover -->\n"
    )
    overrides = par.parse_ratchet_overrides(text)
    assert len(overrides) == 1
    o = overrides[0]
    assert o["ceiling"] == 445
    assert o["reason"] == "widened for the S12 evidence-pack cutover"
    assert o["valid"] is True


def test_empty_reason_after_stripping_is_invalid():
    text = f"RATCHET-OVERRIDE: tech_debt_overdue<=445 {EM_DASH}\n"
    overrides = par.parse_ratchet_overrides(text)
    assert len(overrides) == 1
    o = overrides[0]
    # The ceiling shape is well-formed on its own; only the reason is empty —
    # this must be reported as an invalid OVERRIDE, not silently dropped as
    # "no override found here at all" (those are two different signals).
    assert o["ceiling"] == 445
    assert o["valid"] is False
    assert isinstance(o["why_invalid"], str) and o["why_invalid"] != ""


def test_no_override_line_in_text_returns_empty_list():
    text = "Just some ordinary markdown prose with no override markers at all.\n"
    assert par.parse_ratchet_overrides(text) == []


def test_three_duplicate_override_lines_from_merge_union_all_returned():
    # A `merge=union` ledger-adjacent file can legitimately carry the same
    # override line 3x when several branches each append it independently —
    # none of the duplicates may be fatal, and all three must be returned so
    # ratchet_verdict can still pick the highest ceiling among them.
    line = (
        f"RATCHET-OVERRIDE: tech_debt_overdue<=445 {EM_DASH} widened for the "
        "S12 evidence-pack cutover\n"
    )
    text = line + line + line
    overrides = par.parse_ratchet_overrides(text)
    assert len(overrides) == 3
    assert all(o["valid"] for o in overrides)
    assert all(o["ceiling"] == 445 for o in overrides)


def test_innocence_prose_mention_without_ceiling_shape_not_parsed():
    # Over-match guard (superscar family #3): the literal token
    # "RATCHET-OVERRIDE" appearing in ordinary prose, with none of the
    # `tech_debt_overdue<=<INT>` shape attached, must not be recognized as an
    # override at all — not even as an invalid one. A guard that fires on the
    # bare substring "RATCHET-OVERRIDE" would let a stray design-doc mention
    # silently manufacture a phantom override entry.
    text = (
        "We discussed RATCHET-OVERRIDE handling in the design doc during the "
        "S12 retro, but never actually wired one up this cycle.\n"
    )
    assert par.parse_ratchet_overrides(text) == []


def test_innocence_prose_QUOTING_a_whole_override_line_is_still_not_an_override():
    """The dangerous half of the over-match guard, and the one that bites.

    The case above lacks the colon, so a bare-substring implementation would
    still return []. This one embeds a syntactically PERFECT override —
    ceiling and all — mid-sentence, exactly as a runbook, a scar entry, or this
    very repo's own documentation would quote it. Under a substring check that
    line manufactures a valid ceiling-999 blanket authorisation out of prose:
    the gate is then disarmed by its own documentation.

    Mutation-verified 2026-08-31: replacing the start-of-line anchor with
    `TOKEN in line` turns this test red. Without this case the mutant survived.
    """
    text = (
        "The marker is RATCHET-OVERRIDE: tech_debt_overdue<=999 -- see the runbook "
        "for when this is legitimate.\n"
        "Never paste that into the ledger without a reviewer.\n"
    )
    assert par.parse_ratchet_overrides(text) == []


# ---------------------------------------------------------------------------
# B. ratchet_verdict — guilt and innocence, both directions
# ---------------------------------------------------------------------------


def _override(ceiling: int, reason: str = "widened", valid: bool = True, why_invalid=None) -> dict:
    return {
        "ceiling": ceiling,
        "reason": reason,
        "raw": f"RATCHET-OVERRIDE: tech_debt_overdue<={ceiling} {EM_DASH} {reason}",
        "valid": valid,
        "why_invalid": why_invalid,
    }


def test_guilt_delta_positive_no_overrides_is_red():
    v = par.ratchet_verdict(440, 441, [])
    assert v["status"] == "red"
    assert v["delta"] == 1


def test_innocence_delta_zero_is_clean():
    v = par.ratchet_verdict(440, 440, [])
    assert v["status"] == "clean"
    assert v["delta"] == 0


def test_innocence_negative_delta_rows_closed_is_clean():
    v = par.ratchet_verdict(440, 438, [])
    assert v["status"] == "clean"
    assert v["delta"] == -2


def test_innocence_valid_override_with_sufficient_ceiling_is_override():
    ov = _override(441, reason="exact ceiling match")
    v = par.ratchet_verdict(440, 441, [ov])
    assert v["status"] == "override"
    assert v["ceiling_used"] == 441
    assert v["reason_used"] == "exact ceiling match"


def test_guilt_valid_override_ceiling_too_low_is_red():
    ov = _override(440, reason="too low to cover the new debt")
    v = par.ratchet_verdict(440, 441, [ov])
    assert v["status"] == "red"


def test_guilt_override_with_empty_reason_is_ignored_and_red():
    ov = _override(445, reason="", valid=False, why_invalid="empty reason")
    v = par.ratchet_verdict(440, 441, [ov])
    assert v["status"] == "red"


def test_innocence_two_overrides_highest_valid_ceiling_wins():
    low = _override(439, reason="too low, must be ignored in favor of the higher one")
    high = _override(442, reason="the one that should win")
    v = par.ratchet_verdict(440, 441, [low, high])
    assert v["status"] == "override"
    assert v["ceiling_used"] == 442
    assert v["reason_used"] == "the one that should win"


def test_highest_wins_among_ceilings_that_are_BOTH_sufficient():
    """The case above has only ONE sufficient ceiling, so it cannot tell
    max from min — measured: swapping `max` for `min` left the whole suite
    green. Both ceilings here cover the head count, so only the real rule
    survives. This is the shape `merge=union` actually produces: two copies of
    a header line that both sides edited to different numbers.
    """
    lower_but_sufficient = _override(441, reason="the merged-in copy")
    higher = _override(445, reason="the copy that must be reported")
    v = par.ratchet_verdict(440, 441, [lower_but_sufficient, higher])
    assert v["status"] == "override"
    assert v["ceiling_used"] == 445, "the HIGHEST covering ceiling is the one in force"
    assert v["reason_used"] == "the copy that must be reported"


def test_innocence_stale_override_never_reddens_a_clean_run():
    # An override never turns a clean run red — it only ever RESCUES a red
    # one. A stale override (left over from a previous overdue cycle, whose
    # ceiling would be irrelevant since delta<=0 already) must be inert.
    ov = _override(999, reason="stale, from a previous overdue cycle")
    v = par.ratchet_verdict(440, 440, [ov])
    assert v["status"] == "clean"


# ---------------------------------------------------------------------------
# C. End-to-end on REAL fixture ledgers through load_entries + compute_counts
# ---------------------------------------------------------------------------
#
# BASE always carries two rows:
#   - "ancient stable debt row" (opened 2020-01-01): always overdue, at any
#     plausible frozen `now` — a stable, calendar-insensitive floor so the
#     absolute overdue count is never zero.
#   - "borderline entry row" (opened exactly at NOW): FRESH at NOW (age 0),
#     but becomes overdue at NOW_PLUS_30 (age 30) — this is what makes the
#     calendar-independence property in section D interesting instead of
#     vacuous (see that test's own comment).


def _base_ledger_text(now_str: str) -> str:
    return (
        "- opened 2020-01-01 | ancient stable debt row | some step | me | some proof\n"
        f"- opened {now_str} | borderline entry row | some step | me | some proof\n"
        "\n## closed (proof recorded)\n"
    )


def _head_plus_overdue_row(now_str: str) -> str:
    return (
        "- opened 2020-01-01 | ancient stable debt row | some step | me | some proof\n"
        f"- opened {now_str} | borderline entry row | some step | me | some proof\n"
        "- opened 2019-06-15 | new overdue debt row | some step | me | some proof\n"
        "\n## closed (proof recorded)\n"
    )


def _head_plus_fresh_row(now_str: str) -> str:
    return (
        "- opened 2020-01-01 | ancient stable debt row | some step | me | some proof\n"
        f"- opened {now_str} | borderline entry row | some step | me | some proof\n"
        f"- opened {now_str} | fresh new row not overdue | some step | me | some proof\n"
        "\n## closed (proof recorded)\n"
    )


def _write_ledger(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _overdue_count(ledger_path: Path, now_str: str) -> int:
    now = par._parse_now(now_str)
    entries = par.load_entries(ledger_path, now)
    return par.compute_counts(entries)["tech_debt_overdue"]


def test_head_fixture_row_parses_as_real_tech_debt_not_malformed(tmp_path):
    # Anti-vacuity check: proves the "new overdue debt row" line is a real,
    # correctly-classified TECH-DEBT-OVERDUE entry (not silently MALFORMED,
    # which the real parser would never crash on but WOULD make every
    # count-based assertion below vacuous — a malformed row is invisible to
    # compute_counts()["tech_debt_overdue"]).
    head = _write_ledger(tmp_path, "head.md", _head_plus_overdue_row(NOW))
    now = par._parse_now(NOW)
    entries = par.load_entries(head, now)
    row = next(e for e in entries if e.artifact == "new overdue debt row")
    assert not row.malformed
    assert row.cls == par.CLASS_TECH_DEBT
    assert row.overdue is True
    assert row.bucket == f"{par.CLASS_TECH_DEBT}-OVERDUE"


def test_head_adding_one_overdue_row_increases_count_by_exactly_one(tmp_path):
    base = _write_ledger(tmp_path, "base.md", _base_ledger_text(NOW))
    head = _write_ledger(tmp_path, "head.md", _head_plus_overdue_row(NOW))
    base_count = _overdue_count(base, NOW)
    head_count = _overdue_count(head, NOW)
    assert head_count == base_count + 1


def test_guilt_end_to_end_overdue_delta_is_red(tmp_path):
    base = _write_ledger(tmp_path, "base.md", _base_ledger_text(NOW))
    head = _write_ledger(tmp_path, "head.md", _head_plus_overdue_row(NOW))
    base_count = _overdue_count(base, NOW)
    head_count = _overdue_count(head, NOW)
    v = par.ratchet_verdict(base_count, head_count, [])
    assert v["status"] == "red"


def test_innocence_head_adding_a_fresh_row_does_not_change_the_count(tmp_path):
    # Load-bearing innocence case: adding a ledger row must not, by itself,
    # redden a PR — only adding an ALREADY-OVERDUE row does.
    base = _write_ledger(tmp_path, "base.md", _base_ledger_text(NOW))
    head = _write_ledger(tmp_path, "head.md", _head_plus_fresh_row(NOW))
    base_count = _overdue_count(base, NOW)
    head_count = _overdue_count(head, NOW)
    assert head_count == base_count
    v = par.ratchet_verdict(base_count, head_count, [])
    assert v["status"] == "clean"


# ---------------------------------------------------------------------------
# D. Calendar-independence: the invariant the whole design rests on
# ---------------------------------------------------------------------------


def test_delta_is_calendar_independent_while_absolute_counts_may_differ(tmp_path):
    """The same BASE/HEAD fixture pair, evaluated at two `now` values 30 days
    apart, must yield the SAME delta even though the ABSOLUTE counts on each
    side move (the "borderline entry row", opened exactly at NOW, ages from
    FRESH into overdue by NOW_PLUS_30 on BOTH base and head — since it lives
    unchanged on both sides, it shifts both counts up by one and cancels out
    of the subtraction). This is the property that makes a delta-based gate
    safe against the passage of time in a way a stored-snapshot comparison
    (see module docstring) is not.
    """
    base = _write_ledger(tmp_path, "base.md", _base_ledger_text(NOW))
    head = _write_ledger(tmp_path, "head.md", _head_plus_overdue_row(NOW))

    base_count_t1 = _overdue_count(base, NOW)
    head_count_t1 = _overdue_count(head, NOW)
    delta_t1 = head_count_t1 - base_count_t1

    base_count_t2 = _overdue_count(base, NOW_PLUS_30)
    head_count_t2 = _overdue_count(head, NOW_PLUS_30)
    delta_t2 = head_count_t2 - base_count_t2

    # The absolute counts DO move over the 30-day gap...
    assert base_count_t2 != base_count_t1
    assert head_count_t2 != head_count_t1
    # ...but the delta a ratchet gate actually judges does not.
    assert delta_t1 == delta_t2 == 1


# ---------------------------------------------------------------------------
# E. ratchet_selftest — the detector still detects
# ---------------------------------------------------------------------------


def test_ratchet_selftest_returns_zero():
    assert par.ratchet_selftest() == 0


def test_ratchet_selftest_actually_runs_its_cases(capsys):
    """`assert ratchet_selftest() == 0` alone is a tautology.

    Measured by the cross-family gate: replacing the whole self-test body with
    `return 0` leaves that assertion — AND the workflow's stand-alone self-test
    step — green, so the thing claimed to ARM this gate would be arming nothing.
    This pins the corpus itself: the named cases must be present, must all have
    passed, and must number what the design says they number.
    """
    cases = par.ratchet_selftest(return_cases=True)
    assert isinstance(cases, list) and len(cases) >= 17, f"only {len(cases)} cases"
    names = [c[0] for c in cases]
    assert all(c[1] for c in cases), [c for c in cases if not c[1]]

    # The load-bearing ones by name — each is a distinct scar, not a variant.
    for needle in (
        "premise:",                       # fixtures are real rows, not MALFORMED
        "+1 overdue row -> RED",          # the first bite
        "a FRESH row added -> CLEAN",     # what a snapshot gate gets wrong
        "a row CLOSED -> CLEAN",
        "NEW sufficient override",
        "INHERITED override authorises nothing",
        "FENCED example override authorises nothing",
        "empty reason -> RED",
        "prose quoting an override is not an override",
        "5000-digit ceiling",
        "malformed override dicts do not raise",
        "delta is identical at two far-apart dates",
        "BLOCKQUOTED example authorises nothing",
        "cannot close a ~~~ fence",
        "RESTYLING an inherited override is not a new approval",
    ):
        assert any(needle in n for n in names), f"self-test lost its {needle!r} case"

    out = capsys.readouterr().out
    assert "cases behaved as specified" in out, "the self-test must SAY what it did"


# ---------------------------------------------------------------------------
# F. run_ratchet end-to-end, in a real git repo — the invariant, pinned where
#    it can actually be broken.
#
# Everything in section D proves the calendar-independence PROPERTY through
# load_entries directly. That is not the same as proving run_ratchet USES it:
# measured 2026-08-31, mutating run_ratchet so that HEAD is evaluated at
# `now + 90 days` while BASE stays at `now` left the entire suite green. That
# mutant is precisely the design's failure mode — the ratchet silently becomes
# the calendar countdown it exists to avoid — so it gets a test that reaches
# the real function through a real base ref.
# ---------------------------------------------------------------------------

import subprocess as _sp  # noqa: E402


def _git_repo_with_ledger(tmp_path, base_text: str, head_text: str):
    """A throwaway repo: BASE committed, HEAD left in the working tree.

    Returns (ledger_path, base_sha). Nothing here touches the real repo.
    """
    repo = tmp_path / "repo"
    (repo / ".claude" / "skills" / "modus").mkdir(parents=True)
    ledger = repo / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"

    def git(*argv):
        r = _sp.run(["git", "-C", str(repo), *argv], capture_output=True, text=True)
        assert r.returncode == 0, f"git {argv}: {r.stderr}"
        return r.stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "test")
    ledger.write_text(base_text, encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")
    base_sha = git("rev-parse", "HEAD")
    ledger.write_text(head_text, encoding="utf-8")  # working tree = HEAD side
    return ledger, base_sha


def test_run_ratchet_reads_both_sides_at_the_BASE_COMMIT_date(tmp_path):
    """The verdict is a pure function of (base commit, head tree).

    An earlier version of this test asserted the OPPOSITE and blessed it: it
    expected the same unmodified branch to go RED ninety days later, which is
    precisely the calendar drift the design claims to remove. Round 2 of the
    cross-family gate caught the contradiction between the claim and the test.

    Freezing a shared `now` is not enough, because it cancels ageing only for
    rows present on BOTH sides — a row the branch ADDS ages on one side of the
    subtraction alone. Reading both sides at the base commit's date removes time
    from the computation instead of holding it still: a row opened after that
    date has a negative age and is FRESH by construction.

    The two calls below pass `now=None`, i.e. exactly what CI does.
    """
    base = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    # A row THIS BRANCH adds, dated well after the base commit (which a fresh
    # test repo makes 'today'). It must never count, today or in ten years.
    head = base + "- opened 2099-01-01 (t) | **row B** | wire it | session | CI red\n"
    ledger, base_sha = _git_repo_with_ledger(tmp_path, base, head)

    assert par.run_ratchet(ledger, None, base_sha) == 0
    # Determinism, stated as an assertion rather than assumed: same inputs,
    # same verdict, no hidden clock in between.
    assert par.run_ratchet(ledger, None, base_sha) == 0


def test_a_row_that_was_ALREADY_overdue_when_the_branch_was_cut_still_reddens(tmp_path):
    """The other half — otherwise the fix above is just 'always clean'.

    A backdated row, or an old row resurrected, IS debt arriving. It was overdue
    before this branch existed and the branch put it back: that is the thing
    worth a reviewer's attention, and the only thing the calendar cannot fake.
    """
    base = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    head = base + "- opened 2020-01-01 (t) | **resurrected row** | wire it | session | CI red\n"
    ledger, base_sha = _git_repo_with_ledger(tmp_path, base, head)
    assert par.run_ratchet(ledger, None, base_sha) == 1


def test_a_head_only_FRESH_row_never_becomes_red_however_far_the_clock_moves(tmp_path):
    """The exact scenario round 2 named: BASE has one old overdue row, HEAD adds
    a row that is fresh on the day it is written, nobody commits again.

    Under a shared-frozen-now design this reads CLEAN on day 0 and RED on day 3.
    Under the base-commit clock there is no day 3 — the answer cannot move,
    because no input to it moves. Asserted by calling with a `now` a century out
    AND with the real derived clock, and demanding they agree.
    """
    base = "- opened 2020-01-01 (t) | **ancient row** | wire it | session | CI red\n"
    head = base + "- opened 2099-06-01 (t) | **branch's own fresh row** | wire it | session | CI red\n"
    ledger, base_sha = _git_repo_with_ledger(tmp_path, base, head)
    assert par.run_ratchet(ledger, None, base_sha) == 0


def test_run_ratchet_reports_cannot_verify_not_clean_when_the_base_is_unresolvable(tmp_path):
    """Exit 3, never 0. A scan that could not look is not a clean scan (W84)."""
    base = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    ledger, _ = _git_repo_with_ledger(tmp_path, base, base)
    rc = par.run_ratchet(ledger, par._parse_now("2026-06-02"), "refs/does/not/exist")
    assert rc == 3, "an unreadable base must be CANNOT-VERIFY, not a silent pass"


def test_unresolvable_merge_base_is_cannot_verify_and_never_falls_back(tmp_path):
    """No `origin/main` (shallow CI clone, fresh repo) -> (None, reason).

    Mutation-verified 2026-08-31: making this branch fall back to the literal
    string "origin/main" left the whole suite green, and a fallback here is
    exactly the failure this design refuses — the ratchet would silently start
    answering a DIFFERENT question ("vs current main") from the one it claims
    to answer ("what did this branch author"), which is the W88/W102 pair.
    """
    base = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    ledger, _ = _git_repo_with_ledger(tmp_path, base, base)  # a repo with no remote
    resolved, why = par._resolve_ratchet_base(ledger, None)
    assert resolved is None, f"must not invent a base; got {resolved!r} ({why})"
    assert isinstance(why, str) and why.strip(), "the reason must be reportable"
    # And the CLI surface agrees: 3, not 0.
    assert par.run_ratchet(ledger, par._parse_now("2026-06-02"), None) == 3


def test_an_override_already_on_the_base_does_not_licence_this_branch(tmp_path):
    """The BLOCKER the cross-family gate found, pinned end-to-end.

    Sequence it describes: PR A raises the count and writes `<=445`; it merges.
    PR B branches from that, adds another overdue row, writes nothing. If HEAD's
    overrides are parsed without asking which of them are NEW, PR B inherits a
    sufficient ceiling and exits 0 — and the claim that "the next increase needs
    a new, separately reviewed ceiling" is simply false.
    """
    ov = "RATCHET-OVERRIDE: tech_debt_overdue<=445 -- PR A's reviewed ceiling\n"
    old_row = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    new_row = "- opened 2026-06-01 (t) | **row B** | wire it | session | CI red\n"

    # BASE already carries A's override; HEAD adds a row and nothing else.
    ledger, base_sha = _git_repo_with_ledger(
        tmp_path, base_text=old_row + ov, head_text=old_row + new_row + ov
    )
    late = par._parse_now("2026-09-01")  # both rows overdue by now
    assert par.run_ratchet(ledger, late, base_sha) == 1, (
        "an inherited ceiling must authorise nothing"
    )


def test_a_new_override_in_this_branch_does_licence_it(tmp_path):
    """The innocence half — otherwise the fix above is just 'always red'."""
    old_row = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    new_row = "- opened 2026-06-01 (t) | **row B** | wire it | session | CI red\n"
    fresh_ov = "RATCHET-OVERRIDE: tech_debt_overdue<=2 -- this branch's own, reviewed\n"
    ledger, base_sha = _git_repo_with_ledger(
        tmp_path, base_text=old_row, head_text=old_row + new_row + fresh_ov
    )
    late = par._parse_now("2026-09-01")
    assert par.run_ratchet(ledger, late, base_sha) == 0


def test_an_unreadable_head_is_cannot_verify_not_an_increase(tmp_path):
    """Exit 3, never 1. Conflating "could not read" with "this branch raised the
    count" is how a CANNOT-VERIFY gets acted on as a real finding.
    """
    row = "- opened 2026-06-01 (t) | **row A** | wire it | session | CI red\n"
    ledger, base_sha = _git_repo_with_ledger(tmp_path, base_text=row, head_text=row)
    ledger.write_bytes(b"- opened 2026-06-01 (t) | **row \xff\xfe** | x | s | p\n")
    assert par.run_ratchet(ledger, par._parse_now("2026-09-01"), base_sha) == 3


def test_selftest_premise_rejects_a_row_the_parser_calls_MALFORMED(tmp_path):
    """A count-only premise is satisfied by garbage.

    The blank-owner row below is exactly the one the cross-family gate produced:
    the real parser classes it MALFORMED, its overdue count is still 0, so a
    premise that only looked at counts stayed true and every "FRESH row added ->
    CLEAN" case downstream proved nothing (W108).
    """
    now = par._parse_now("2026-08-30")
    good_overdue = tmp_path / "a.md"
    good_overdue.write_text(
        "- opened 2026-08-01 (t) | **overdue row** | wire it | session | CI red\n",
        encoding="utf-8",
    )
    malformed_fresh = tmp_path / "b.md"
    malformed_fresh.write_text(
        "- opened 2026-08-29 (t) | **fresh row** | wire it | | CI red\n", encoding="utf-8"
    )
    ov = par.load_entries(good_overdue, now)
    bad = par.load_entries(malformed_fresh, now)

    # Premise of the premise: this really is the count-blind case.
    assert par.compute_counts(bad)["tech_debt_overdue"] == 0
    assert bad[0].cls == par.CLASS_MALFORMED

    assert par.selftest_premise_holds(ov, bad) is False
    good_fresh = tmp_path / "c.md"
    good_fresh.write_text(
        "- opened 2026-08-29 (t) | **fresh row** | wire it | session | CI red\n",
        encoding="utf-8",
    )
    assert par.selftest_premise_holds(ov, par.load_entries(good_fresh, now)) is True


def _write(tmp_path, name: str, line: str):
    p = tmp_path / name
    p.write_text(line if line.endswith("\n") else line + "\n", encoding="utf-8")
    return par.load_entries(p, par._parse_now("2026-08-30"))


def test_selftest_premise_rejects_EACH_way_a_fixture_can_be_the_wrong_row(tmp_path):
    """Every clause of the premise, not just one.

    Measured: with only the MALFORMED case above, mutating the premise's
    overdue-BUCKET clause to `True` left the whole suite green — i.e. seven of
    the eight clauses were decoration. A premise is the one check that makes
    every downstream case non-vacuous; it does not get to be half-tested.
    """
    OVERDUE = "- opened 2026-08-01 (t) | **overdue row** | wire it | session | CI red"
    FRESH = "- opened 2026-08-29 (t) | **fresh row** | wire it | session | CI red"
    MALFORMED = "- opened 2026-08-29 (t) | **fresh row** | wire it | | CI red"

    good_ov = _write(tmp_path, "ov.md", OVERDUE)
    good_fr = _write(tmp_path, "fr.md", FRESH)
    assert par.selftest_premise_holds(good_ov, good_fr) is True, "the honest pair must pass"

    # overdue side is not overdue at all (bucket FRESH) — the clause the
    # MALFORMED case cannot reach.
    assert par.selftest_premise_holds(_write(tmp_path, "x1.md", FRESH), good_fr) is False
    # overdue side unparseable
    assert par.selftest_premise_holds(_write(tmp_path, "x2.md", MALFORMED), good_fr) is False
    # fresh side is actually overdue
    assert par.selftest_premise_holds(good_ov, _write(tmp_path, "x3.md", OVERDUE)) is False
    # fresh side unparseable
    assert par.selftest_premise_holds(good_ov, _write(tmp_path, "x4.md", MALFORMED)) is False
    # wrong cardinality on either side
    assert par.selftest_premise_holds(_write(tmp_path, "x5.md", OVERDUE + "\n" + OVERDUE), good_fr) is False
    assert par.selftest_premise_holds(good_ov, _write(tmp_path, "x6.md", FRESH + "\n" + FRESH)) is False


# ---------------------------------------------------------------------------
# G. Round-2 findings — what the round-1 CURES broke or left open.
# ---------------------------------------------------------------------------

_OV999 = "RATCHET-OVERRIDE: tech_debt_overdue<=999 -- documentation example\n"


def test_a_blockquoted_example_is_not_an_authorisation():
    """`> ` was stripped along with list bullets, so the ordinary way to QUOTE
    an override in prose granted a live ceiling-999 blanket. Blockquote is the
    single most common quoting form in this repo's docs."""
    assert par.parse_ratchet_overrides("> " + _OV999) == []
    assert par.parse_ratchet_overrides(">" + _OV999) == []
    assert par.parse_ratchet_overrides("# " + _OV999) == []


def test_a_backtick_fence_cannot_close_a_tilde_fence():
    """CommonMark: a closer is the SAME character, at least as long, no info
    string. A boolean toggle left the fence early and the example inside became
    live."""
    text = "~~~text\ndocumented example\n```\n" + _OV999 + "```\n"
    assert par.parse_ratchet_overrides(text) == []
    # and a shorter run cannot close a longer opener
    assert par.parse_ratchet_overrides("````\n```\n" + _OV999 + "````\n") == []
    # innocence: a normal fenced block with a language tag closes properly, so
    # an override AFTER it is still seen.
    after = "```text\nexample\n```\n" + _OV999
    assert [o["ceiling"] for o in par.parse_ratchet_overrides(after)] == [999]


def test_a_fence_marker_inside_an_html_comment_does_not_swallow_a_real_override():
    """The over-match twin of the fence fix: a ``` inside a comment is not a
    fence, and treating it as one silently ate a valid override further down —
    an honest increase reddening for an invisible reason."""
    text = "<!--\n```text\n-->\n" + "RATCHET-OVERRIDE: tech_debt_overdue<=2 -- reviewed\n"
    assert [o["ceiling"] for o in par.parse_ratchet_overrides(text)] == [2]


def test_reformatting_an_inherited_override_does_not_make_it_new():
    """Keying identity on raw bytes handed back the standing blanket: re-type
    the inherited line with one extra space, or an em dash, or a comment
    wrapper, and it counted as a fresh approval nobody reviewed."""
    base = "RATCHET-OVERRIDE: tech_debt_overdue<=2 -- reviewed reason\n"
    for restyled in (
        "RATCHET-OVERRIDE: tech_debt_overdue <= 2 -- reviewed reason\n",
        f"RATCHET-OVERRIDE: tech_debt_overdue<=2 {EM_DASH} reviewed reason\n",
        "<!-- RATCHET-OVERRIDE: tech_debt_overdue<=2 -- reviewed  reason -->\n",
        "- RATCHET-OVERRIDE: tech_debt_overdue<=2 -- Reviewed Reason\n",
    ):
        fresh, inherited = par._new_overrides(base, restyled)
        assert fresh == [], f"restyling must not mint a new approval: {restyled!r}"
        assert inherited == 1

    # Innocence: a genuinely different reason IS a new approval — somebody typed
    # it, and that is exactly what a reviewer is being asked to look at.
    fresh, _ = par._new_overrides(
        base, "RATCHET-OVERRIDE: tech_debt_overdue<=2 -- a different, newly written reason\n"
    )
    assert len(fresh) == 1
    # ...and so is a different ceiling.
    fresh, _ = par._new_overrides(base, "RATCHET-OVERRIDE: tech_debt_overdue<=3 -- reviewed reason\n")
    assert len(fresh) == 1


def test_the_clock_is_the_BASE_COMMIT_date_and_not_today(tmp_path):
    """The discriminating case, and it needs a base commit in the PAST.

    Measured: with a base commit dated today (what a throwaway repo gives you),
    `date.today()` and the base-commit date are the same day, so every earlier
    test in this file passes under BOTH implementations — the mutant that
    reverts the clock to `date.today()` survived the whole suite. A fixture too
    poor to reach the thing you meant to measure measures itself (W108).

    Here the base commit is backdated 100 days and the branch adds a row opened
    10 days ago. Under the base-commit clock that row is in the FUTURE, fresh,
    and cannot count. Under a wall-clock it is 10 days old, overdue, and the
    branch reddens for the calendar — the exact drift the design removes.
    """
    import datetime as _dt
    import os as _os

    today = _dt.date.today()
    base_day = today - _dt.timedelta(days=100)
    row_day = today - _dt.timedelta(days=10)

    repo = tmp_path / "repo"
    (repo / ".claude" / "skills" / "modus").mkdir(parents=True)
    ledger = repo / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"

    env = dict(_os.environ)
    stamp = f"{base_day.isoformat()}T12:00:00+00:00"
    env.update(GIT_COMMITTER_DATE=stamp, GIT_AUTHOR_DATE=stamp)

    def git(*argv, e=None):
        r = _sp.run(["git", "-C", str(repo), *argv], capture_output=True, text=True, env=e)
        assert r.returncode == 0, f"git {argv}: {r.stderr}"
        return r.stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "test")
    old_row = f"- opened {(base_day - _dt.timedelta(days=30)).isoformat()} (t) | **row A** | wire it | session | CI red\n"
    ledger.write_text(old_row, encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base", e=env)
    base_sha = git("rev-parse", "HEAD")

    # Premise: the backdating actually took, or this test proves nothing.
    assert par._base_commit_date(ledger, base_sha) == base_day

    ledger.write_text(
        old_row + f"- opened {row_day.isoformat()} (t) | **row B** | wire it | session | CI red\n",
        encoding="utf-8",
    )

    # Premise 2: under a wall clock this WOULD be red — otherwise the assertion
    # below is satisfied by an implementation that never reddens at all.
    assert par.run_ratchet(ledger, _dt.date.today(), base_sha) == 1

    assert par.run_ratchet(ledger, None, base_sha) == 0, (
        "the branch's own row, opened after the base commit, must never count"
    )


# ---------------------------------------------------------------------------
# H. Round-3 findings (third family, kimi-code/k3) — chiefly the rebase case.
# ---------------------------------------------------------------------------


def _repo_with_dates(tmp_path, base_text, head_text, base_day, branch_day):
    """A repo whose BASE is dated `base_day` and whose branch commit carries
    author date `branch_day` — the only way to tell "the base moved" apart from
    "the branch is old"."""
    import os as _os

    repo = tmp_path / "repo"
    (repo / ".claude" / "skills" / "modus").mkdir(parents=True)
    ledger = repo / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"

    def git(*argv, day=None):
        env = dict(_os.environ)
        if day is not None:
            stamp = f"{day.isoformat()}T12:00:00+00:00"
            env.update(GIT_COMMITTER_DATE=stamp, GIT_AUTHOR_DATE=stamp)
        r = _sp.run(["git", "-C", str(repo), *argv], capture_output=True, text=True, env=env)
        assert r.returncode == 0, f"git {argv}: {r.stderr}"
        return r.stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "test")
    ledger.write_text(base_text, encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base", day=base_day)
    base_sha = git("rev-parse", "HEAD")
    ledger.write_text(head_text, encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "branch work", day=branch_day)
    return ledger, base_sha


def test_a_rebase_does_not_redden_a_branch_that_added_a_FRESH_row(tmp_path):
    """The third family's MAJOR, and the most likely false positive in this repo.

    A branch opens a row on day X. Three days later the merge queue makes it
    rebase — routine, and "branch must be up to date" forces it. With the BASE
    COMMIT's date as the clock, the new base is day X+3, the row is now 3 days
    old *at the base date*, and the branch reddens demanding an override for a
    row nobody is late on. Same tree, different verdict, moved by hygiene rather
    than by authorship.

    The clock is therefore the branch's OWN start — its oldest author date since
    the base — which a rebase preserves. Simulated here by a base dated AFTER
    the branch's own commit, which is exactly what a rebase produces.
    """
    import datetime as _dt

    today = _dt.date.today()
    branch_day = today - _dt.timedelta(days=40)   # the branch opened its row here
    base_day = today - _dt.timedelta(days=37)     # rebased onto a newer main
    base = f"- opened {(branch_day - _dt.timedelta(days=200)).isoformat()} (t) | **old row** | x | s | p\n"
    head = base + f"- opened {branch_day.isoformat()} (t) | **the branch's fresh row** | x | s | p\n"
    ledger, base_sha = _repo_with_dates(tmp_path, base, head, base_day, branch_day)

    # Premise: the base really is NEWER than the branch commit — i.e. a rebase.
    assert par._base_commit_date(ledger, base_sha) == base_day
    assert par._branch_start_date(ledger, base_sha) == branch_day
    assert base_day > branch_day

    # Premise 2: under the base-commit clock this WOULD be red, so the assertion
    # below is not satisfied by an implementation that never reddens.
    assert par.run_ratchet(ledger, base_day, base_sha) == 1

    assert par.run_ratchet(ledger, None, base_sha) == 0, (
        "a rebase must not turn a fresh row into debt"
    )


def test_a_backdated_row_still_reddens_under_the_branch_start_clock(tmp_path):
    """The innocence half of the clock change — it must not become 'never red'."""
    import datetime as _dt

    today = _dt.date.today()
    branch_day = today - _dt.timedelta(days=40)
    base_day = today - _dt.timedelta(days=37)
    base = f"- opened {(branch_day - _dt.timedelta(days=200)).isoformat()} (t) | **old row** | x | s | p\n"
    head = base + "- opened 2020-01-01 (t) | **resurrected row** | x | s | p\n"
    ledger, base_sha = _repo_with_dates(tmp_path, base, head, base_day, branch_day)
    assert par.run_ratchet(ledger, None, base_sha) == 1


def test_a_future_dated_clock_is_cannot_verify_not_a_verdict(tmp_path):
    """A skewed or forged commit date in the future makes every row the branch
    adds look overdue, so every row-adding PR reddens until main moves. Refuse
    to judge rather than judge from it."""
    import datetime as _dt

    future = _dt.date.today() + _dt.timedelta(days=400)
    base = "- opened 2026-01-01 (t) | **old row** | x | s | p\n"
    head = base + "- opened 2026-01-02 (t) | **another** | x | s | p\n"
    ledger, base_sha = _repo_with_dates(tmp_path, base, head, future, future)
    assert par.run_ratchet(ledger, None, base_sha) == 3


def test_a_malformed_override_in_the_base_does_not_swallow_a_new_one(tmp_path):
    """Every malformed override parses to (None, ""), so keying identity over
    ALL overrides made one old typo hide every new one — the author's mistake
    silently eaten by someone else's."""
    base = "RATCHET-OVERRIDE: garbage\n"
    head = base + "RATCHET-OVERRIDE: tech_debt_overdue<=44x -- my typo\n"
    fresh, inherited = par._new_overrides(base, head)
    assert inherited == 0, "an invalid line is never 'the same approval' as another invalid line"
    assert len(fresh) == 2 and all(not o["valid"] for o in fresh)
    assert all(o["why_invalid"] for o in fresh), "each must carry a reportable reason"


def test_the_RED_output_names_an_override_rejected_for_its_indentation(capsys, tmp_path):
    """The promised safety valve, which was DEAD code until the third family
    read the comment that promised it (W116). An author who HAS written an
    override — indented under a list item, legal Markdown — must be told that,
    not told 'add an override'."""
    import datetime as _dt

    today = _dt.date.today()
    branch_day = today - _dt.timedelta(days=5)
    base = "- opened 2026-01-01 (t) | **old row** | x | s | p\n"
    head = (
        base
        + "- opened 2020-01-01 (t) | **resurrected** | x | s | p\n"
        + "- notes:\n"
        + "      RATCHET-OVERRIDE: tech_debt_overdue<=443 -- reviewed, legal list continuation\n"
    )
    ledger, base_sha = _repo_with_dates(tmp_path, base, head, branch_day, branch_day)
    assert par.run_ratchet(ledger, None, base_sha) == 1
    out = capsys.readouterr().out
    assert "indented four or more spaces" in out, out[-400:]
    assert "reviewed, legal list continuation" in out


def test_an_override_hidden_after_a_same_line_comment_reopen_does_not_authorise():
    """`<!-- x --> prose <!--` closes and RE-OPENS on one line. Testing the two
    markers independently read everything below as outside a comment, so an
    override invisible in the rendered document AUTHORISED."""
    text = "<!-- a --> prose <!--\nRATCHET-OVERRIDE: tech_debt_overdue<=999 -- hidden\n"
    assert par.parse_ratchet_overrides(text) == []


def test_an_override_after_a_multiline_comment_closes_is_still_seen():
    """The drop direction of the same fix: text after `-->` is live Markdown."""
    text = "<!--\nnote\n--> RATCHET-OVERRIDE: tech_debt_overdue<=2 -- reviewed\n"
    assert [o["ceiling"] for o in par.parse_ratchet_overrides(text)] == [2]
