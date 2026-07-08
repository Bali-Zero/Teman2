"""
Tests for TeamTimesheetService.get_daily_hours null-timestamp handling.

SCAR CONTEXT (found via live prod E2E 2026-07-08):
GET /api/team/hours 500'd with "'NoneType' object has no attribute 'strftime'".
Root cause: get_daily_hours mapped rows from the daily_work_hours view calling
row["clock_out_bali"].strftime("%H:%M") unconditionally — but clock_out_bali is
NULL for a member still clocked in (no clock-out yet). .strftime() on None
raised AttributeError -> router's generic except -> HTTP 500.

Fix: guard every nullable field (clock_in_bali/clock_out_bali/work_date/
hours_worked) before formatting. These tests drive get_daily_hours with a
fake asyncpg pool whose rows carry None fields, proving the mapping no longer
raises and yields None for the missing values (guilt), while a fully-populated
row still formats correctly (innocence).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time

import pytest


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, *_args, **_kwargs):
        return self._rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, rows):
        self._conn = _FakeConn(rows)

    def acquire(self):
        return _FakeAcquire(self._conn)


def _service(rows):
    from backend.services.analytics.team_timesheet_service import TeamTimesheetService

    svc = TeamTimesheetService.__new__(TeamTimesheetService)
    svc.pool = _FakePool(rows)
    return svc


def test_null_clock_out_does_not_500() -> None:
    """GUILT: a row with clock_out_bali=None (member still clocked in) must NOT
    raise — the live 500 was exactly this. clock_out comes back as None."""
    row = {
        "user_id": 7,
        "email": "staffer@balizero.com",
        "work_date": date(2026, 7, 8),
        "clock_in_bali": time(9, 0),
        "clock_out_bali": None,  # still clocked in
        "hours_worked": None,
    }
    svc = _service([row])
    out = asyncio.get_event_loop().run_until_complete(svc.get_daily_hours(datetime(2026, 7, 8)))
    assert out[0]["clock_out"] is None
    assert out[0]["clock_in"] == "09:00"
    assert out[0]["hours_worked"] == 0.0


def test_fully_populated_row_formats_correctly() -> None:
    """INNOCENCE: a complete row still formats clock_in/clock_out as HH:MM and
    hours_worked as float — the guard must not change the happy path."""
    row = {
        "user_id": 3,
        "email": "adit@balizero.com",
        "work_date": date(2026, 7, 8),
        "clock_in_bali": time(8, 30),
        "clock_out_bali": time(17, 15),
        "hours_worked": 8.75,
    }
    svc = _service([row])
    out = asyncio.get_event_loop().run_until_complete(svc.get_daily_hours(datetime(2026, 7, 8)))
    assert out[0]["clock_in"] == "08:30"
    assert out[0]["clock_out"] == "17:15"
    assert out[0]["hours_worked"] == pytest.approx(8.75)
    assert out[0]["date"] == "2026-07-08"
