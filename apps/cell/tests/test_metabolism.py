"""Tests for metabolic system."""
from cell.metabolism.tracker import MetabolismTracker

def test_tracker_initial_state():
    tracker = MetabolismTracker(daily_limit=10.0)
    assert tracker.daily_spend == 0.0
    assert tracker.remaining_budget == 10.0

def test_tracker_record_cost():
    tracker = MetabolismTracker(daily_limit=10.0)
    tracker.record("gemini_flash", 0.50)
    assert tracker.daily_spend == 0.50
    assert tracker.remaining_budget == 9.50

def test_tracker_can_afford_true():
    tracker = MetabolismTracker(daily_limit=10.0)
    assert tracker.can_afford(5.0) is True

def test_tracker_can_afford_false():
    tracker = MetabolismTracker(daily_limit=10.0)
    tracker.record("opus", 8.5)
    assert tracker.can_afford(0.60) is False

def test_tracker_partition_enforcement():
    tracker = MetabolismTracker(daily_limit=10.0, partitions={"routine": 3.0, "incident": 5.0, "reserve": 2.0})
    tracker.record("gemini_flash", 2.5, partition="routine")
    assert tracker.can_afford(0.60, partition="routine") is False
    assert tracker.can_afford(0.60, partition="incident") is True

def test_tracker_reserve_untouchable():
    tracker = MetabolismTracker(daily_limit=10.0, partitions={"routine": 3.0, "incident": 5.0, "reserve": 2.0})
    assert tracker.can_afford(0.01, partition="reserve") is False

def test_tracker_reset():
    tracker = MetabolismTracker(daily_limit=10.0)
    tracker.record("opus", 8.0)
    tracker.daily_reset()
    assert tracker.daily_spend == 0.0
    assert tracker.remaining_budget == 10.0
