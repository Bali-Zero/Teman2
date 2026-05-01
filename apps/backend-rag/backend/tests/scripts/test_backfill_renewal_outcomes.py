"""Test post-hoc inference of renewal outcomes from historical state."""
from datetime import datetime, timedelta, timezone

from scripts.backfill_renewal_outcomes import infer_outcome


def _alert(target_date_offset_days: int = 0) -> dict:
    """Helper: build a synthetic alert row with target_date offset from now."""
    now = datetime.now(tz=timezone.utc)
    return {
        "id": 1,
        "alert_date": now - timedelta(days=30),
        "target_date": now + timedelta(days=target_date_offset_days),
    }


class TestInferOutcome:
    def test_practice_completed_in_window_returns_client_renewed(self):
        alert = _alert(target_date_offset_days=10)
        practice = {
            "status": "completed",
            "completed_at": alert["alert_date"] + timedelta(days=15),
        }
        interactions_count = 2
        assert infer_outcome(alert, practice, interactions_count) == "client_renewed"

    def test_practice_not_completed_with_interactions_returns_acted_by_team(self):
        alert = _alert(target_date_offset_days=10)
        practice = {"status": "on_process", "completed_at": None}
        interactions_count = 5
        assert infer_outcome(alert, practice, interactions_count) == "acted_by_team"

    def test_expired_no_completion_no_interactions_returns_expired_no_action(self):
        alert = _alert(target_date_offset_days=-30)  # target was 30d ago
        practice = {"status": "on_process", "completed_at": None}
        interactions_count = 0
        assert (
            infer_outcome(alert, practice, interactions_count) == "expired_no_action"
        )

    def test_no_completion_no_interactions_not_expired_returns_client_ignored(self):
        alert = _alert(target_date_offset_days=10)  # future target
        practice = {"status": "on_process", "completed_at": None}
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "client_ignored"

    def test_completed_outside_window_returns_client_ignored(self):
        # Completed 200 days after alert — outside 30d post-target window
        alert = _alert(target_date_offset_days=10)
        practice = {
            "status": "completed",
            "completed_at": alert["target_date"] + timedelta(days=200),
        }
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "client_ignored"

    def test_completed_before_alert_returns_client_ignored(self):
        # Completed BEFORE alert was sent — alert was redundant
        alert = _alert(target_date_offset_days=10)
        practice = {
            "status": "completed",
            "completed_at": alert["alert_date"] - timedelta(days=5),
        }
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "client_ignored"
