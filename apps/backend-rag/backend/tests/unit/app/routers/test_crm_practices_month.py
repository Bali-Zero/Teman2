"""Tests for month filter and status history helpers in crm_practices router."""

from datetime import datetime, timezone

from backend.app.routers.crm_practices import (
    _build_status_transitions,
    _parse_month_param,
)

# ============================================================
# _parse_month_param tests
# ============================================================


class TestParseMonthParam:
    """Tests for _parse_month_param helper."""

    def test_none_returns_none(self) -> None:
        assert _parse_month_param(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_month_param("") is None

    def test_valid_month(self) -> None:
        result = _parse_month_param("2026-03")
        assert result is not None
        start, end = result
        assert start == datetime(2026, 3, 1, tzinfo=timezone.utc)
        assert end == datetime(2026, 4, 1, tzinfo=timezone.utc)

    def test_january(self) -> None:
        result = _parse_month_param("2026-01")
        assert result is not None
        start, end = result
        assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert end == datetime(2026, 2, 1, tzinfo=timezone.utc)

    def test_december_rolls_to_next_year(self) -> None:
        result = _parse_month_param("2026-12")
        assert result is not None
        start, end = result
        assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
        assert end == datetime(2027, 1, 1, tzinfo=timezone.utc)

    def test_invalid_month_13_returns_none(self) -> None:
        assert _parse_month_param("2026-13") is None

    def test_invalid_month_0_returns_none(self) -> None:
        assert _parse_month_param("2026-00") is None

    def test_garbage_string_returns_none(self) -> None:
        assert _parse_month_param("not-a-date") is None

    def test_single_value_returns_none(self) -> None:
        assert _parse_month_param("2026") is None

    def test_result_has_utc_timezone(self) -> None:
        result = _parse_month_param("2026-06")
        assert result is not None
        start, end = result
        assert start.tzinfo is timezone.utc
        assert end.tzinfo is timezone.utc


# ============================================================
# _build_status_transitions tests
# ============================================================


class TestBuildStatusTransitions:
    """Tests for _build_status_transitions helper."""

    def test_empty_rows(self) -> None:
        assert _build_status_transitions([]) == {}

    def test_single_transition_dict_changes(self) -> None:
        """When asyncpg returns JSONB as a Python dict (the normal case)."""
        rows = [
            {
                "entity_id": 10,
                "changes": {"status": "on_process"},
                "performed_at": datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc),
            },
        ]
        result = _build_status_transitions(rows)
        assert result == {10: [{"status": "on_process", "at": "2026-03-05 12:00:00+00:00"}]}

    def test_single_transition_string_changes(self) -> None:
        """When changes comes back as a JSON string (edge case)."""
        rows = [
            {
                "entity_id": 20,
                "changes": '{"status": "completed"}',
                "performed_at": datetime(2026, 3, 10, 9, 30, 0, tzinfo=timezone.utc),
            },
        ]
        result = _build_status_transitions(rows)
        assert result == {20: [{"status": "completed", "at": "2026-03-10 09:30:00+00:00"}]}

    def test_multiple_transitions_same_practice(self) -> None:
        rows = [
            {
                "entity_id": 10,
                "changes": {"status": "waiting_documents"},
                "performed_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            },
            {
                "entity_id": 10,
                "changes": {"status": "on_process"},
                "performed_at": datetime(2026, 3, 5, tzinfo=timezone.utc),
            },
            {
                "entity_id": 10,
                "changes": {"status": "completed"},
                "performed_at": datetime(2026, 3, 15, tzinfo=timezone.utc),
            },
        ]
        result = _build_status_transitions(rows)
        assert len(result[10]) == 3
        assert result[10][0]["status"] == "waiting_documents"
        assert result[10][1]["status"] == "on_process"
        assert result[10][2]["status"] == "completed"

    def test_multiple_practices(self) -> None:
        rows = [
            {
                "entity_id": 1,
                "changes": {"status": "on_process"},
                "performed_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            },
            {
                "entity_id": 2,
                "changes": {"status": "completed"},
                "performed_at": datetime(2026, 3, 2, tzinfo=timezone.utc),
            },
        ]
        result = _build_status_transitions(rows)
        assert 1 in result
        assert 2 in result
        assert len(result[1]) == 1
        assert len(result[2]) == 1

    def test_skips_rows_without_status(self) -> None:
        rows = [
            {
                "entity_id": 10,
                "changes": {"priority": "high"},
                "performed_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            },
            {
                "entity_id": 10,
                "changes": {"status": "on_process"},
                "performed_at": datetime(2026, 3, 2, tzinfo=timezone.utc),
            },
        ]
        result = _build_status_transitions(rows)
        assert len(result[10]) == 1
        assert result[10][0]["status"] == "on_process"

    def test_skips_rows_with_empty_changes_dict(self) -> None:
        rows = [
            {
                "entity_id": 10,
                "changes": {},
                "performed_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            },
        ]
        result = _build_status_transitions(rows)
        assert result == {}
