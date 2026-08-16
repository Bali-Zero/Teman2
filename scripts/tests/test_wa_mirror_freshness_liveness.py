#!/usr/bin/env python3
"""Pure tests for wa_mirror_freshness_liveness.py — NO database (W87/W96).

Guilt: stale + business hours -> exactly one p0 through a fake tg_notify.
Innocence: stale outside business hours -> no p0; fresh -> no p0 either way.
Plus: dedup-key stability (a literal constant, never embeds the variable
age), DEAD-count parsing off a CANNED status table using fake numbers
(+6200000000000-style — never real staff numbers), and the business-hours /
staleness pure-function math in isolation.

Run:  python3 scripts/tests/test_wa_mirror_freshness_liveness.py
      python3 -m pytest scripts/tests/test_wa_mirror_freshness_liveness.py -q
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from datetime import datetime, timedelta

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import wa_mirror_freshness_liveness as wmfl  # noqa: E402


# ---------------------------------------------------------------- pure math


def test_age_minutes_computes_delta():
    now = datetime(2026, 8, 15, 10, 0, tzinfo=wmfl.timezone.utc)
    newest = now - timedelta(minutes=90)
    assert wmfl.age_minutes(newest, now) == 90.0


def test_age_minutes_none_when_table_empty():
    now = datetime(2026, 8, 15, 10, 0, tzinfo=wmfl.timezone.utc)
    assert wmfl.age_minutes(None, now) is None


def test_is_stale_true_beyond_max_age():
    assert wmfl.is_stale(400.0, max_age_min=360.0) is True


def test_is_stale_false_within_max_age():
    assert wmfl.is_stale(100.0, max_age_min=360.0) is False


def test_is_stale_true_when_age_is_none():
    assert wmfl.is_stale(None, max_age_min=360.0) is True


def test_in_business_hours_true_weekday_daytime():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)  # Monday noon
    assert wmfl.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is True


def test_in_business_hours_false_at_night():
    now_wita = datetime(2026, 8, 17, 3, 0, tzinfo=wmfl.WITA)  # Monday 03:00
    assert wmfl.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is False


def test_in_business_hours_false_on_sunday():
    now_wita = datetime(2026, 8, 16, 12, 0, tzinfo=wmfl.WITA)  # Sunday noon
    assert wmfl.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is False


def test_in_business_hours_boundary_end_hour_exclusive():
    now_wita = datetime(2026, 8, 17, 20, 0, tzinfo=wmfl.WITA)  # exactly 20:00
    assert wmfl.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is False


# ---------------------------------------------------------------- DEAD-count parsing (canned, fake numbers)

# Fake wa-mirror-launcher status.sh table — masked per repo convention: fake
# E.164 numbers (+6200000000000-style), never real staff numbers.
_CANNED_STATUS_TABLE_ALL_DEAD = """NAME       E164                 STATUS     PID        LAST LOG
─────────────────────────────────────────────────────────────────────────────
alice      +6200000000001 (linked) 🔴 DEAD    -          {"level":50}
bob        +6200000000002 (linked) 🔴 DEAD    -          {"level":50}
carol      +6200000000003 (no-link) ⚪ STOPPED -
"""

_CANNED_STATUS_TABLE_ALL_HEALTHY = """NAME       E164                 STATUS     PID        LAST LOG
─────────────────────────────────────────────────────────────────────────────
alice      +6200000000001 (linked) 🟢 RUNNING 11111      {"level":30}
bob        +6200000000002 (linked) 🟢 RUNNING 22222      {"level":30}
"""


def test_count_dead_lines_on_canned_table_with_dead_entries():
    assert wmfl.count_dead_lines(_CANNED_STATUS_TABLE_ALL_DEAD) == 2


def test_count_dead_lines_on_canned_table_all_healthy():
    assert wmfl.count_dead_lines(_CANNED_STATUS_TABLE_ALL_HEALTHY) == 0


def test_count_dead_lines_none_when_script_output_unavailable():
    assert wmfl.count_dead_lines(None) is None


# ---------------------------------------------------------------- dedup key stability


def test_dedup_key_is_a_fixed_literal_not_derived_from_variable_state():
    assert wmfl.DEDUP_KEY == "wa-mirror:freshness:stale"
    # build_alert_text embeds the variable age in the TEXT, never in the key.
    text_a = wmfl.build_alert_text(90.0, 2)
    text_b = wmfl.build_alert_text(9000.0, 5)
    assert text_a != text_b
    assert wmfl.DEDUP_KEY not in text_a and wmfl.DEDUP_KEY not in text_b


# ---------------------------------------------------------------- _tick guilt + innocence (FakeConn, no DB)


class _FakeConn:
    def __init__(self, newest):
        self._newest = newest

    async def fetchrow(self, query, *args):
        assert "whatsapp_message_context" in query
        return {"newest": self._newest}


def _run_tick(newest, now_wita, *, dry_run, monkeypatch, tmp_path, status_output=None):
    sent = []
    monkeypatch.setattr(wmfl, "_tg_notify", lambda tier, key, text: sent.append((tier, key, text)) or True)
    monkeypatch.setattr(wmfl, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(wmfl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(wmfl, "_run_status_script", lambda: status_output)
    monkeypatch.setenv("WA_FRESHNESS_MAX_AGE_MIN", "360")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_START", "8")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_END", "20")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_DAYS", "0,1,2,3,4,5")

    conn = _FakeConn(newest)
    rc = asyncio.run(wmfl._tick(conn, now_wita, dry_run=dry_run))
    return rc, sent


def test_guilt_stale_in_business_hours_sends_exactly_one_p0(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)  # Monday noon
    newest = now - timedelta(hours=7)  # 420min > 360min threshold
    rc, sent = _run_tick(
        newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path,
        status_output=_CANNED_STATUS_TABLE_ALL_DEAD,
    )
    assert rc == 0
    p0_sends = [s for s in sent if s[0] == "p0"]
    assert len(p0_sends) == 1
    assert p0_sends[0][1] == wmfl.DEDUP_KEY


def test_innocence_stale_outside_business_hours_sends_nothing(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 3, 0, tzinfo=wmfl.WITA)  # Monday 03:00 — night
    newest = now - timedelta(hours=7)
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_innocence_fresh_in_business_hours_sends_nothing(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = now - timedelta(minutes=5)  # well within the freshness window
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_dry_run_never_sends_even_when_stale_in_business_hours(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = now - timedelta(hours=7)
    rc, sent = _run_tick(newest, now, dry_run=True, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []
    assert not (tmp_path / "state.json").exists()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
