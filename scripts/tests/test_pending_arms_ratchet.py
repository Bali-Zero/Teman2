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


def test_run_ratchet_freezes_now_on_BOTH_sides(tmp_path):
    """Both fixture rows are FRESH at the frozen `now` and OVERDUE 90 days later.

    So the honest verdict at that `now` is CLEAN. Any implementation that lets
    the two sides drift onto different dates — `date.today()` on one of them,
    a stray `+ timedelta` — sees 0 vs 2 and reports RED on a branch that added
    a row nobody has had time to be late on yet.
    """
    d1, d2 = "2026-06-01", "2026-06-02"
    base = f"- opened {d1} (t) | **row A** | wire it | session | CI red\n"
    head = base + f"- opened {d2} (t) | **row B** | wire it | session | CI red\n"
    ledger, base_sha = _git_repo_with_ledger(tmp_path, base, head)

    frozen = par._parse_now("2026-06-02")  # both rows younger than the 48h line
    rc = par.run_ratchet(ledger, frozen, base_sha)
    assert rc == 0, "a branch adding a row nobody is late on yet must not be red"

    # And the counterpart, so this is not a test that only ever says 'clean':
    # ninety days on, both rows are overdue and the delta is real.
    late = par._parse_now("2026-09-01")
    assert par.run_ratchet(ledger, late, base_sha) == 1


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
