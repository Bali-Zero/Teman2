"""Bite-proof for `garuda_ops.deadman`: what would make this go RED?

Answer: a stale `last_success_at` (or none since monitoring started) beyond
`max_silence`. Each test below breaks that condition and restores it,
proving the alarm fires either way — not just on the happy path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.garuda_ops.deadman import DeadmanState, evaluate_deadman

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
_STARTED = _NOW - timedelta(days=1)
_WINDOW = timedelta(minutes=15)


def test_recent_success_is_healthy() -> None:
    verdict = evaluate_deadman(
        last_success_at=_NOW - timedelta(minutes=5),
        now=_NOW,
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert verdict.state is DeadmanState.HEALTHY
    assert not verdict.should_page
    assert not verdict.should_disable_flag


def test_success_exactly_at_the_window_edge_is_still_healthy() -> None:
    verdict = evaluate_deadman(
        last_success_at=_NOW - _WINDOW,
        now=_NOW,
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert verdict.state is DeadmanState.HEALTHY


def test_silence_past_the_window_is_dead_and_pages_and_disables() -> None:
    """RED case: break it by pushing the last success one second past the
    window — every consequence SYN-01 names must fire together."""
    verdict = evaluate_deadman(
        last_success_at=_NOW - _WINDOW - timedelta(seconds=1),
        now=_NOW,
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert verdict.state is DeadmanState.DEAD
    assert verdict.should_page
    assert verdict.should_disable_flag
    assert verdict.age_seconds == pytest.approx(_WINDOW.total_seconds() + 1)


def test_never_succeeded_since_monitoring_started_counts_from_start_not_epoch() -> None:
    """A probe that has NEVER produced a success (fresh deploy) must not
    silently read as healthy just because `last_success_at` is None."""
    verdict = evaluate_deadman(
        last_success_at=None,
        now=_STARTED + timedelta(minutes=1),
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert verdict.state is DeadmanState.HEALTHY  # within grace of the first window

    verdict_after_window = evaluate_deadman(
        last_success_at=None,
        now=_STARTED + _WINDOW + timedelta(seconds=1),
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert verdict_after_window.state is DeadmanState.DEAD
    assert verdict_after_window.should_disable_flag


def test_restoring_a_recent_success_turns_it_green_again() -> None:
    """A late probe alone must not silently clear a DEAD verdict — but a
    genuinely fresh success must. This proves the switch is not stuck one
    way (SYN-01: "a late probe cannot auto-enable the flag" concerns the
    flag's actual re-enable step, done by the owner; the reader's job here
    is only to reflect true current health)."""
    dead = evaluate_deadman(
        last_success_at=_NOW - timedelta(hours=2),
        now=_NOW,
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert dead.state is DeadmanState.DEAD

    recovered = evaluate_deadman(
        last_success_at=_NOW - timedelta(minutes=1),
        now=_NOW,
        max_silence=_WINDOW,
        monitoring_started_at=_STARTED,
    )
    assert recovered.state is DeadmanState.HEALTHY


def test_future_timestamps_are_rejected_not_silently_accepted() -> None:
    with pytest.raises(ValueError, match="future"):
        evaluate_deadman(
            last_success_at=_NOW + timedelta(minutes=1),
            now=_NOW,
            max_silence=_WINDOW,
            monitoring_started_at=_STARTED,
        )
    with pytest.raises(ValueError, match="precedes"):
        evaluate_deadman(
            last_success_at=None,
            now=_STARTED - timedelta(minutes=1),
            max_silence=_WINDOW,
            monitoring_started_at=_STARTED,
        )
