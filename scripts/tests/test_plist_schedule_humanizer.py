#!/usr/bin/env python3
"""`_humanize_plist_schedule` honors Weekday / Day / list-of-intervals.

WHY THIS EXISTS: the generated automations reference rendered
com.balizero.curiosity.weekly and com.balizero.codex-spalla-calibrate (both
`StartCalendarInterval.Weekday: 0` = Sunday) as "daily HH:MM WITA", contradicting
their own header-comment purpose ("Sunday HH:MM"). Weekly, monthly and multi-fire
schedules now read as what launchd will actually do; plain daily / hourly /
StartInterval / RunAtLoad outputs are pinned unchanged. Salvaged 2026-09-11 from
the abandoned split-design branch (agent/air-m5/infra/automations-one-author).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

gen = pytest.importorskip("generate_automations_reference")


def test_humanize_plist_schedule_weekly_sunday_weekday_zero():
    # launchd convention: Weekday 0 (and 7) both mean Sunday.
    parsed = {"StartCalendarInterval": {"Hour": 6, "Minute": 0, "Weekday": 0}}
    assert gen._humanize_plist_schedule(parsed) == "weekly Sun 06:00 WITA"


def test_humanize_plist_schedule_weekly_other_weekday():
    parsed = {"StartCalendarInterval": {"Hour": 8, "Minute": 0, "Weekday": 3}}
    assert gen._humanize_plist_schedule(parsed) == "weekly Wed 08:00 WITA"


def test_humanize_plist_schedule_monthly_day():
    parsed = {"StartCalendarInterval": {"Day": 1, "Hour": 4, "Minute": 30}}
    assert gen._humanize_plist_schedule(parsed) == "monthly day 1 04:30 WITA"


def test_humanize_plist_schedule_list_of_intervals_joined():
    parsed = {
        "StartCalendarInterval": [
            {"Hour": 2, "Minute": 15},
            {"Hour": 6, "Minute": 15},
            {"Hour": 10, "Minute": 15},
        ]
    }
    assert gen._humanize_plist_schedule(parsed) == (
        "daily 02:15 WITA; daily 06:15 WITA; daily 10:15 WITA"
    )


def test_humanize_plist_schedule_list_of_weekly_intervals_joined():
    parsed = {
        "StartCalendarInterval": [
            {"Hour": 8, "Minute": 0, "Weekday": 3},
            {"Hour": 8, "Minute": 0, "Weekday": 6},
        ]
    }
    assert gen._humanize_plist_schedule(parsed) == "weekly Wed 08:00 WITA; weekly Sat 08:00 WITA"


def test_humanize_plist_schedule_plain_daily_unchanged():
    # No Weekday/Day present -> unchanged "daily HH:MM WITA" behavior.
    parsed = {"StartCalendarInterval": {"Hour": 8, "Minute": 15}}
    assert gen._humanize_plist_schedule(parsed) == "daily 08:15 WITA"


def test_humanize_plist_schedule_start_interval_unchanged():
    # StartInterval path is untouched by the Weekday/Day rework.
    assert gen._humanize_plist_schedule({"StartInterval": 3600}) == "every 1h"
    assert gen._humanize_plist_schedule({"StartInterval": 600}) == "every 10m"
    assert gen._humanize_plist_schedule({"StartInterval": 90}) == "every 90s"


def test_humanize_plist_schedule_run_at_load_and_dash_unchanged():
    assert gen._humanize_plist_schedule({"RunAtLoad": True}) == "RunAtLoad"
    assert gen._humanize_plist_schedule({}) == "—"
