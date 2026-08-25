"""Tests for team_bot.brain.depletion_probe. In-memory sqlite, injectable
fake clock — no real time, no real filesystem state."""

from __future__ import annotations

import pytest

from team_bot.brain.depletion_probe import DepletionProbe, UsageSample


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def _sample(now: float, total: int, model: str = "qwen3.7-plus") -> UsageSample:
    return UsageSample(ts=now, model=model, prompt_tokens=total // 2, completion_tokens=total // 2, total_tokens=total)


def test_unconfigured_probe_records_usage_but_never_alarms() -> None:
    clock = FakeClock()
    probe = DepletionProbe(clock=clock)  # quota_tokens_7d=None (default)
    assert probe.configured is False
    probe.record(_sample(clock(), 1000))
    assert probe.used_tokens() == 1000
    assert probe.remaining_fraction() is None
    assert probe.check_alarms() == []


def test_configured_probe_tracks_used_tokens() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, clock=clock)
    probe.record(_sample(clock(), 1000))
    probe.record(_sample(clock(), 2000))
    assert probe.used_tokens() == 3000
    assert probe.remaining_fraction() == pytest.approx(0.7)


def test_no_alarm_while_above_highest_threshold() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, alarm_thresholds=(0.30, 0.10), clock=clock)
    probe.record(_sample(clock(), 6000))  # 40% remaining, above 30%
    assert probe.check_alarms() == []


def test_30_percent_alarm_fires_once_when_crossed() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, alarm_thresholds=(0.30, 0.10), clock=clock)
    probe.record(_sample(clock(), 7100))  # 29% remaining
    alarms = probe.check_alarms()
    assert len(alarms) == 1
    assert alarms[0].threshold == pytest.approx(0.30)
    assert alarms[0].remaining_fraction == pytest.approx(0.29)

    # Recording more usage while still above the NEXT threshold (10%) must
    # not re-fire the 30% alarm again.
    probe.record(_sample(clock(), 100))  # 28% remaining, still above 10%
    assert probe.check_alarms() == []


def test_10_percent_alarm_fires_after_30_percent_already_fired() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, alarm_thresholds=(0.30, 0.10), clock=clock)
    probe.record(_sample(clock(), 7100))  # 29%
    probe.check_alarms()
    probe.record(_sample(clock(), 1900))  # total 9000 used -> 10% remaining exactly
    alarms = probe.check_alarms()
    assert len(alarms) == 1
    assert alarms[0].threshold == pytest.approx(0.10)


def test_both_thresholds_crossed_in_one_jump_fire_in_order() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, alarm_thresholds=(0.30, 0.10), clock=clock)
    probe.record(_sample(clock(), 9500))  # jump straight to 5% remaining
    alarms = probe.check_alarms()
    assert [a.threshold for a in alarms] == [pytest.approx(0.30), pytest.approx(0.10)]


def test_alarm_state_survives_reconstruction_same_db_path(tmp_path) -> None:
    db_path = str(tmp_path / "usage.db")
    clock = FakeClock()

    probe1 = DepletionProbe(db_path=db_path, quota_tokens_7d=10_000, clock=clock)
    probe1.record(_sample(clock(), 7100))
    fired = probe1.check_alarms()
    assert len(fired) == 1
    probe1.close()

    # A NEW instance against the SAME db must know the 30% alarm already
    # fired — a process restart must not re-alarm on the same depletion
    # level.
    probe2 = DepletionProbe(db_path=db_path, quota_tokens_7d=10_000, clock=clock)
    assert probe2.check_alarms() == []
    probe2.close()


def test_usage_outside_rolling_window_is_pruned() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, window_seconds=3600.0, clock=clock)
    probe.record(_sample(clock(), 5000))
    assert probe.used_tokens() == 5000
    clock.advance(3601.0)
    # The old sample has aged out of the 1h window.
    assert probe.used_tokens() == 0
    assert probe.remaining_fraction() == pytest.approx(1.0)


def test_remaining_fraction_clamped_when_usage_exceeds_quota() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=1000, clock=clock)
    probe.record(_sample(clock(), 5000))  # owner under-estimated the budget
    assert probe.remaining_fraction() == 0.0


def test_alarm_rearms_after_headroom_recovers() -> None:
    clock = FakeClock()
    probe = DepletionProbe(quota_tokens_7d=10_000, window_seconds=3600.0, alarm_thresholds=(0.30, 0.10), clock=clock)
    probe.record(_sample(clock(), 9500))  # 5% remaining
    first = probe.check_alarms()
    assert len(first) == 2

    clock.advance(3601.0)  # window rolls the old usage off -> 100% remaining
    assert probe.check_alarms() == []  # nothing to re-fire, back above 30%

    probe.record(_sample(clock(), 7100))  # deplete again -> 29% remaining
    second = probe.check_alarms()
    assert len(second) == 1
    assert second[0].threshold == pytest.approx(0.30)


def test_invalid_construction_args_rejected() -> None:
    with pytest.raises(ValueError):
        DepletionProbe(quota_tokens_7d=0)
    with pytest.raises(ValueError):
        DepletionProbe(quota_tokens_7d=-5)
    with pytest.raises(ValueError):
        DepletionProbe(quota_tokens_7d=100, window_seconds=0)
    with pytest.raises(ValueError):
        DepletionProbe(quota_tokens_7d=100, alarm_thresholds=(1.0,))
    with pytest.raises(ValueError):
        DepletionProbe(quota_tokens_7d=100, alarm_thresholds=(0.0,))
