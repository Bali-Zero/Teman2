"""Regression: GET /api/team/hours 400 when a member is still clocked in.

Root cause (verified live 2026-07-09): get_daily_hours() in
team_timesheet_service.py guards NULL clock_out_bali/hours_worked and emits
`clock_out=None` (member still clocked in). But the DailyHours pydantic model
declared `clock_out: str` (non-nullable), so `DailyHours(**row)` raised
ValidationError, caught by the router as `Invalid date format` -> HTTP 400.
A SINGLE open shift broke the whole team-hours view for admins.

Fix: DailyHours date/clock_in/clock_out are Optional; hours_worked defaults 0.0.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.routers.team_activity import DailyHours


def test_daily_hours_accepts_open_shift_null_clock_out() -> None:
    """Guilt: a member still clocked in has clock_out=None. The model MUST
    accept it (the OLD `clock_out: str` raised ValidationError -> live 400)."""
    row = {
        "user_id": "u1",
        "email": "member@balizero.com",
        "date": "2026-07-09",
        "clock_in": "09:00",
        "clock_out": None,      # still clocked in
        "hours_worked": 0.0,
    }
    dh = DailyHours(**row)
    assert dh.clock_out is None
    assert dh.clock_in == "09:00"


def test_daily_hours_accepts_all_nulls_edge_row() -> None:
    """Edge row where the service guarded a NULL work_date/clock_in too."""
    dh = DailyHours(user_id="u2", email="e@balizero.com")
    assert dh.date is None and dh.clock_in is None and dh.clock_out is None
    assert dh.hours_worked == 0.0


def test_daily_hours_still_validates_completed_shift() -> None:
    """Innocence: a normal completed shift is unchanged (all strings present)."""
    dh = DailyHours(
        user_id="u3", email="e3@balizero.com", date="2026-07-09",
        clock_in="09:00", clock_out="17:30", hours_worked=8.5,
    )
    assert dh.clock_out == "17:30" and dh.hours_worked == 8.5


def test_daily_hours_rejects_wrong_type() -> None:
    """Innocence-of-detector: a genuinely wrong type still fails validation."""
    with pytest.raises(ValidationError):
        DailyHours(user_id="u4", email="e@balizero.com", clock_out=12345)  # int, not str|None
