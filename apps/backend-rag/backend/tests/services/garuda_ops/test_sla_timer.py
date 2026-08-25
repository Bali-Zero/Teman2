"""Bite-proof for `garuda_ops.sla_timer`."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.services.garuda_ops.ports import PracticeSnapshot
from backend.services.garuda_ops.sla_timer import (
    SlaState,
    time_in_state,
    time_to_filing_deadline,
)

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
_TODAY = date(2026, 8, 25)


def _practice(*, state: str, entered_ago: timedelta, filing_deadline: date | None = None) -> PracticeSnapshot:
    return PracticeSnapshot(
        practice_aggregate_id="practice-1",
        state=state,
        state_entered_at=_NOW - entered_ago,
        filing_deadline=filing_deadline,
    )


def test_fresh_blocked_practice_is_ok() -> None:
    verdict = time_in_state(_practice(state="Blocked", entered_ago=timedelta(hours=1)), now=_NOW)
    assert verdict.state is SlaState.OK


def test_blocked_practice_past_threshold_is_overdue() -> None:
    """RED: 49h in Blocked (threshold 48h)."""
    verdict = time_in_state(_practice(state="Blocked", entered_ago=timedelta(hours=49)), now=_NOW)
    assert verdict.state is SlaState.OVERDUE


def test_blocked_practice_at_75_percent_is_warning_not_overdue() -> None:
    verdict = time_in_state(_practice(state="Blocked", entered_ago=timedelta(hours=37)), now=_NOW)
    assert verdict.state is SlaState.WARNING


def test_resuming_the_state_clears_the_overdue_state() -> None:
    """Green: reset the clock (a new state_entered_at) and OVERDUE clears."""
    stale = time_in_state(_practice(state="Blocked", entered_ago=timedelta(hours=49)), now=_NOW)
    assert stale.state is SlaState.OVERDUE
    fresh = time_in_state(_practice(state="Blocked", entered_ago=timedelta(minutes=1)), now=_NOW)
    assert fresh.state is SlaState.OK


def test_unmonitored_state_never_pages() -> None:
    verdict = time_in_state(_practice(state="Approved", entered_ago=timedelta(days=30)), now=_NOW)
    assert verdict.state is SlaState.OK
    assert verdict.threshold is None


def test_future_state_entered_at_is_rejected() -> None:
    future_practice = PracticeSnapshot(
        practice_aggregate_id="p",
        state="Received",
        state_entered_at=_NOW + timedelta(hours=1),
        filing_deadline=None,
    )
    with pytest.raises(ValueError, match="future"):
        time_in_state(future_practice, now=_NOW)


def test_filing_deadline_pages_when_two_days_or_fewer_remain() -> None:
    """RED: D-2 and a practice still In_review must page."""
    verdict = time_to_filing_deadline(
        _practice(state="In_review", entered_ago=timedelta(hours=1), filing_deadline=_TODAY + timedelta(days=2)),
        today=_TODAY,
    )
    assert verdict.should_page
    assert verdict.days_remaining == 2


def test_filing_deadline_does_not_page_with_ample_runway() -> None:
    """Green: restore runway to D-5 and the page clears."""
    verdict = time_to_filing_deadline(
        _practice(state="In_review", entered_ago=timedelta(hours=1), filing_deadline=_TODAY + timedelta(days=5)),
        today=_TODAY,
    )
    assert not verdict.should_page
    assert verdict.days_remaining == 5


def test_passed_deadline_still_in_review_pages_with_negative_days() -> None:
    verdict = time_to_filing_deadline(
        _practice(state="Blocked", entered_ago=timedelta(hours=1), filing_deadline=_TODAY - timedelta(days=1)),
        today=_TODAY,
    )
    assert verdict.should_page
    assert verdict.days_remaining == -1


def test_submitted_practice_no_longer_races_the_deadline() -> None:
    """A practice that has already been filed must not keep paging on a
    deadline it has already met — even if the calendar date has passed."""
    verdict = time_to_filing_deadline(
        _practice(state="Submitted", entered_ago=timedelta(hours=1), filing_deadline=_TODAY - timedelta(days=10)),
        today=_TODAY,
    )
    assert not verdict.should_page
    assert verdict.days_remaining is None


def test_missing_filing_deadline_on_an_active_practice_pages_not_silently_passes() -> None:
    """RED-if-wrong (refuter finding 7): a practice still racing D-7 with NO
    deadline recorded is a data gap, not 'no deadline applies' — it must
    page (fail-closed / M-06's unknown-is-never-healthy), not silently
    clear. Bite: before the fix this asserted `not should_page`."""
    verdict = time_to_filing_deadline(
        _practice(state="Received", entered_ago=timedelta(hours=1), filing_deadline=None),
        today=_TODAY,
    )
    assert verdict.should_page
    assert verdict.days_remaining is None
    assert verdict.status is SlaState.WARNING


def test_cleared_state_with_no_deadline_stays_ok() -> None:
    """Green counterpart: once the practice is Submitted/Approved/etc., the
    absence of a filing_deadline is expected (the deadline no longer
    applies), not a data gap — must NOT page."""
    verdict = time_to_filing_deadline(
        _practice(state="Delivered", entered_ago=timedelta(hours=1), filing_deadline=None),
        today=_TODAY,
    )
    assert not verdict.should_page
    assert verdict.status is SlaState.OK
