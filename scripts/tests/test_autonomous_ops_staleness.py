"""Guilt and innocence for the Autonomous-Ops staleness probe.

The defect this probe replaces was not "no check existed" — a check existed and
reported CURRENT for a contract 43 days past its own limit, because it measured
the file's mtime. So the tests that matter here are the ones that would have gone
RED against that behaviour, and against the naive re-implementation of it:

  * test_lapsed_contract_is_reported            — guilt: an old contract says LAPSED
  * test_mtime_cannot_rescue_a_lapsed_contract  — guilt: touching the file changes nothing
  * test_latest_recertification_wins            — the trap: the FIRST date is not the governing one
  * test_dates_outside_the_active_block_are_ignored — the other trap: 24 other dates in the file
  * test_no_declared_date_is_unreadable_not_fresh   — an unanswerable probe must not read as healthy
"""

from __future__ import annotations

import datetime
import importlib.util
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "check_autonomous_ops_staleness.py"

_spec = importlib.util.spec_from_file_location("check_autonomous_ops_staleness", MODULE_PATH)
assert _spec and _spec.loader
staleness = importlib.util.module_from_spec(_spec)
sys.modules["check_autonomous_ops_staleness"] = staleness
_spec.loader.exec_module(staleness)


def contract(body: str) -> str:
    """A minimal contract file with the same shape as the real one."""
    return (
        "# AUTONOMOUS OPS CONTRACT\n\n"
        "> preamble that also mentions 2019-01-01 for good measure\n\n"
        "---\n\n"
        "## Active level\n\n"
        f"{body}\n\n"
        "---\n\n"
        "## Level 1 — something else\n\n"
        "changelog stamp 2026-12-31 that must never govern anything\n"
    )


TODAY = datetime.date(2026, 8, 31)


def test_lapsed_contract_is_reported() -> None:
    """GUILT. 43 days against a 30-day limit is a lapse, and must be named one."""
    text = contract("**Level 2 — active since 2026-07-19**")
    governing, age, stale = staleness.evaluate(text, TODAY)
    assert governing == datetime.date(2026, 7, 19)
    assert age == 43
    assert stale is True


def test_fresh_contract_is_not_reported() -> None:
    """INNOCENCE. A contract inside its window must not cry wolf."""
    text = contract("**Level 2 — active since 2026-08-20**")
    governing, age, stale = staleness.evaluate(text, TODAY)
    assert governing == datetime.date(2026, 8, 20)
    assert age == 11
    assert stale is False


def test_boundary_is_strictly_greater_than_thirty() -> None:
    """The contract says '>30 days', so exactly 30 is still current."""
    at_30 = TODAY - datetime.timedelta(days=30)
    at_31 = TODAY - datetime.timedelta(days=31)
    assert staleness.evaluate(contract(f"active since {at_30.isoformat()}"), TODAY)[2] is False
    assert staleness.evaluate(contract(f"active since {at_31.isoformat()}"), TODAY)[2] is True


def test_mtime_cannot_rescue_a_lapsed_contract(tmp_path: pathlib.Path) -> None:
    """GUILT, against the exact defect being replaced.

    The old hook read the file's mtime, so a freshly written file always looked
    0 days old. Here the file is written milliseconds before the probe runs — the
    most favourable possible mtime — and the verdict must still be LAPSED.
    """
    path = tmp_path / "AUTONOMOUS_OPS.md"
    path.write_text(contract("**Level 2 — active since 2026-07-19**"), encoding="utf-8")
    age_by_mtime = (datetime.datetime.now().timestamp() - path.stat().st_mtime) / 86400
    assert age_by_mtime < 1, "precondition: the file is freshly written"

    rc = staleness.main(["--contract", str(path), "--today", TODAY.isoformat()])
    assert rc == 0, "default mode reports, it does not block"
    rc_strict = staleness.main(
        ["--contract", str(path), "--today", TODAY.isoformat(), "--strict"]
    )
    assert rc_strict == 1, "--strict must fail on a lapse the mtime would have hidden"


def test_latest_recertification_wins() -> None:
    """THE TRAP. The first declared date is not the governing one.

    The real file opens with 'active since 2026-06-11' and re-certifies to
    2026-07-19 two lines below. A probe that greps the first line reads 81 days
    where the truth is 43 — and, on a contract re-certified yesterday, would
    report a lapse that does not exist.
    """
    yesterday = TODAY - datetime.timedelta(days=1)
    text = contract(
        "**Level 2 — active since 2026-01-01**\n"
        "(Level 1 was active earlier same day.)\n"
        f"(re-certified {yesterday.isoformat()} by the owner — routine refresh.)"
    )
    governing, age, stale = staleness.evaluate(text, TODAY)
    assert governing == yesterday, "must take the maximum, not the first match"
    assert age == 1
    assert stale is False


def test_dates_outside_the_active_block_are_ignored() -> None:
    """THE OTHER TRAP. The real file carries two dozen unrelated ISO dates."""
    text = contract("**Level 2 — active since 2026-07-19**")
    assert datetime.date(2026, 12, 31) not in staleness.declared_dates(text)
    assert datetime.date(2019, 1, 1) not in staleness.declared_dates(text)
    assert staleness.declared_dates(text) == [datetime.date(2026, 7, 19)]


def test_a_date_on_a_non_declaring_line_does_not_count() -> None:
    """A date inside the block still needs a line that declares something."""
    text = contract(
        "**Level 2 — active since 2026-07-19**\n"
        "(an unrelated note mentioning 2026-08-30, which certifies nothing.)"
    )
    assert staleness.declared_dates(text) == [datetime.date(2026, 7, 19)]


def test_no_declared_date_is_unreadable_not_fresh() -> None:
    """An unanswerable probe must never read as healthy."""
    with pytest.raises(staleness.ContractUnreadable):
        staleness.evaluate(contract("**Level 2 — active**, no date at all"), TODAY)


def test_missing_section_is_unreadable_not_fresh() -> None:
    with pytest.raises(staleness.ContractUnreadable):
        staleness.evaluate("# nothing here\n\nactive since 2026-07-19\n", TODAY)


def test_missing_file_exits_two_not_zero(tmp_path: pathlib.Path) -> None:
    rc = staleness.main(["--contract", str(tmp_path / "absent.md"), "--strict"])
    assert rc == 2


def test_reads_the_real_contract_and_finds_the_recertification() -> None:
    """Against the file actually in this repo, not a fixture.

    Pins the governing date to the re-certification rather than the opening
    'active since' — the whole point of the max().
    """
    real = REPO_ROOT / "AUTONOMOUS_OPS.md"
    assert real.exists()
    dates = staleness.declared_dates(real.read_text(encoding="utf-8"))
    assert dates, "the real contract must declare at least one date"
    assert max(dates) >= datetime.date(2026, 7, 19)
    assert datetime.date(2026, 6, 11) in dates, "the opening date is still parsed…"
    assert max(dates) != datetime.date(2026, 6, 11), "…but it does not govern"
