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
import json
import os
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


# ---------------------------------------------------------------- business-time reference (verbale #1)


def test_business_hours_open_wita_floors_to_start_hour():
    now_wita = datetime(2026, 8, 17, 14, 37, tzinfo=wmfl.WITA)  # Monday afternoon
    opened = wmfl.business_hours_open_wita(now_wita, start_hour=8)
    assert opened == datetime(2026, 8, 17, 8, 0, tzinfo=wmfl.WITA)


def test_business_reference_uses_newest_when_newer_than_open():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)  # Monday noon
    newest = datetime(2026, 8, 17, 11, 30, tzinfo=wmfl.WITA)  # 11:30 today
    ref = wmfl.business_reference(newest, now_wita, start_hour=8)
    assert ref == newest


def test_business_reference_floors_at_today_open_for_overnight_message():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)  # Monday noon
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wmfl.WITA)  # overnight, before open
    ref = wmfl.business_reference(newest, now_wita, start_hour=8)
    assert ref == datetime(2026, 8, 17, 8, 0, tzinfo=wmfl.WITA)


def test_business_reference_floors_at_today_open_when_table_empty():
    now_wita = datetime(2026, 8, 17, 11, 1, tzinfo=wmfl.WITA)  # Monday
    ref = wmfl.business_reference(None, now_wita, start_hour=8)
    assert ref == datetime(2026, 8, 17, 8, 0, tzinfo=wmfl.WITA)


def test_business_age_minutes_computes_delta_from_reference():
    ref = datetime(2026, 8, 17, 8, 0, tzinfo=wmfl.WITA)
    now_wita = datetime(2026, 8, 17, 11, 1, tzinfo=wmfl.WITA)
    assert wmfl.business_age_minutes(ref, now_wita) == 181.0


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


# ---------------------------------------------------------------- SQL shape (bridge-writer filter, verbale #3)


def test_freshness_sql_filters_to_the_wa_mirror_bridge_writer():
    # whatsapp_message_context is shared with the legacy meta_cloud_api
    # writer (migration 173) — without this filter a dead wa-mirror bridge
    # is masked by the other writer still inserting rows.
    assert "whatsapp_message_context" in wmfl.FRESHNESS_SQL
    assert "source = 'wa_mirror'" in wmfl.FRESHNESS_SQL


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

    async def fetchrow(self, query, *args, **kwargs):
        assert "whatsapp_message_context" in query
        return {"newest": self._newest}


def _run_tick(newest, now_wita, *, dry_run, monkeypatch, tmp_path, status_output=None,
              max_age_min="180", prior_state=None):
    sent = []
    state_path = tmp_path / "state.json"
    if prior_state is not None:
        state_path.write_text(json.dumps(prior_state), encoding="utf-8")
    monkeypatch.setattr(wmfl, "_tg_notify", lambda tier, key, text: sent.append((tier, key, text)) or True)
    monkeypatch.setattr(wmfl, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(wmfl, "STATE_PATH", state_path)
    monkeypatch.setattr(wmfl, "_run_status_script", lambda: status_output)
    monkeypatch.setenv("WA_FRESHNESS_MAX_AGE_MIN", max_age_min)
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_START", "8")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_END", "20")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_DAYS", "0,1,2,3,4,5")

    conn = _FakeConn(newest)
    rc = asyncio.run(wmfl._tick(conn, now_wita, dry_run=dry_run))
    return rc, sent


# New default (verbale #1): WA_FRESHNESS_MAX_AGE_MIN=180 (3h), evaluated
# against a business-hours-adjusted reference — max(newest, today's 08:00).


def test_guilt_overnight_message_ages_past_threshold_into_the_morning(tmp_path, monkeypatch):
    # newest=Mon 05:00, now=Mon 12:00 -> ref=Mon 08:00, business_age=240 > 180.
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)  # Monday noon
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wmfl.WITA)
    rc, sent = _run_tick(
        newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path,
        status_output=_CANNED_STATUS_TABLE_ALL_DEAD,
    )
    assert rc == 0
    p0_sends = [s for s in sent if s[0] == "p0"]
    assert len(p0_sends) == 1
    assert p0_sends[0][1] == wmfl.DEDUP_KEY


def test_innocence_quiet_overnight_gap_never_pages_at_next_morning_open(tmp_path, monkeypatch):
    # newest=Mon 19:55, now=Tue 09:00 -> ref=Tue 08:00, business_age=60 <= 180.
    # This is exactly the false-P0 shape the refuter caught pre-fix.
    now = datetime(2026, 8, 18, 9, 0, tzinfo=wmfl.WITA)  # Tuesday
    newest = datetime(2026, 8, 17, 19, 55, tzinfo=wmfl.WITA)  # Monday 19:55
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_innocence_weekend_gap_never_pages_monday_mid_morning(tmp_path, monkeypatch):
    # newest=Sat 19:00, now=Mon 10:30 -> ref=Mon 08:00, business_age=150 <= 180.
    now = datetime(2026, 8, 17, 10, 30, tzinfo=wmfl.WITA)  # Monday
    newest = datetime(2026, 8, 15, 19, 0, tzinfo=wmfl.WITA)  # Saturday 19:00
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_guilt_weekend_gap_pages_once_past_threshold_monday(tmp_path, monkeypatch):
    # newest=Sat 19:00, now=Mon 11:01 -> ref=Mon 08:00, business_age=181 > 180.
    now = datetime(2026, 8, 17, 11, 1, tzinfo=wmfl.WITA)  # Monday
    newest = datetime(2026, 8, 15, 19, 0, tzinfo=wmfl.WITA)  # Saturday 19:00
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    p0_sends = [s for s in sent if s[0] == "p0"]
    assert len(p0_sends) == 1


def test_innocence_sunday_never_pages_regardless_of_age(tmp_path, monkeypatch):
    now = datetime(2026, 8, 16, 15, 0, tzinfo=wmfl.WITA)  # Sunday afternoon
    newest = datetime(2026, 8, 10, 0, 0, tzinfo=wmfl.WITA)  # a week stale
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_guilt_null_newest_pages_past_threshold_in_business_hours(tmp_path, monkeypatch):
    # table has never had a row -> ref floors at today_open regardless.
    now = datetime(2026, 8, 17, 11, 1, tzinfo=wmfl.WITA)  # Monday
    rc, sent = _run_tick(None, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    p0_sends = [s for s in sent if s[0] == "p0"]
    assert len(p0_sends) == 1


def test_innocence_fresh_in_business_hours_sends_nothing(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = now - timedelta(minutes=5)  # well within the freshness window
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_dry_run_never_sends_even_when_stale_in_business_hours(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wmfl.WITA)
    rc, sent = _run_tick(newest, now, dry_run=True, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []
    assert not (tmp_path / "state.json").exists()


# ---------------------------------------------------------------- alerted persisted BEFORE write (verbale #5)


def test_alerted_flag_is_persisted_in_the_written_state_file(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wmfl.WITA)  # guilty -> pages
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    written = json.loads((tmp_path / "state.json").read_text())
    assert written["alerted"] is True


def test_innocent_tick_persists_alerted_false(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = now - timedelta(minutes=5)
    rc, sent = _run_tick(newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    written = json.loads((tmp_path / "state.json").read_text())
    assert written["alerted"] is False


# ---------------------------------------------------------------- recovered digest (verbale #1 follow-on)


def test_recovered_digest_sent_when_previous_alerted_and_now_fresh(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = now - timedelta(minutes=5)  # fresh now
    rc, sent = _run_tick(
        newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path,
        prior_state={"alerted": True},
    )
    assert rc == 0
    digests = [s for s in sent if s[0] == "digest"]
    assert len(digests) == 1
    assert digests[0][1] == f"wa-mirror:freshness:recovered:{now.strftime('%Y-%m-%d')}"


def test_no_recovered_digest_when_previous_was_not_alerted(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = now - timedelta(minutes=5)
    rc, sent = _run_tick(
        newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path,
        prior_state={"alerted": False},
    )
    assert rc == 0
    assert sent == []


def test_no_recovered_digest_when_still_stale(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wmfl.WITA)  # still stale
    rc, sent = _run_tick(
        newest, now, dry_run=False, monkeypatch=monkeypatch, tmp_path=tmp_path,
        prior_state={"alerted": True},
    )
    assert rc == 0
    digests = [s for s in sent if s[0] == "digest"]
    assert digests == []
    p0_sends = [s for s in sent if s[0] == "p0"]
    assert len(p0_sends) == 1


def test_dedup_key_recovered_is_date_stamped():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    assert wmfl.recovered_dedup_key(now_wita) == "wa-mirror:freshness:recovered:2026-08-17"


# ---------------------------------------------------------------- heartbeat reflects the ORGAN, not the finding (verbale #2)


def test_heartbeat_is_ok_even_when_stale_organ_not_finding(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wmfl.WITA)
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wmfl.WITA)  # stale -> would have been "degraded" pre-fix
    hb = []
    monkeypatch.setattr(wmfl, "_tg_notify", lambda *a, **k: True)
    monkeypatch.setattr(wmfl, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setattr(wmfl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(wmfl, "_run_status_script", lambda: None)
    monkeypatch.setenv("WA_FRESHNESS_MAX_AGE_MIN", "180")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_START", "8")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_END", "20")
    monkeypatch.setenv("WA_FRESHNESS_BUSINESS_DAYS", "0,1,2,3,4,5")

    conn = _FakeConn(newest)
    rc = asyncio.run(wmfl._tick(conn, now, dry_run=False))

    assert rc == 0
    assert len(hb) == 1
    status, note = hb[0]
    assert status == "ok"
    assert "stale=True" in note


# ---------------------------------------------------------------- run() wraps the whole tick, never exits uncaught (verbale #6)


class _StubConn:
    async def fetchrow(self, query, *args, **kwargs):
        return {"newest": None}

    async def close(self):
        return None


def test_run_level_kill_switch_never_reaches_the_dsn(monkeypatch):
    # verbale #10c: the freshness test suite never called run() at all — the
    # kill switch, lock/flock logic and DB-connect gating were entirely
    # untested. A fake DSN that raises if asyncpg.connect is ever invoked
    # proves the disabled path short-circuits BEFORE touching the network,
    # not merely that it returns 0.
    hb = []
    monkeypatch.setattr(wmfl, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setenv("WA_MIRROR_FRESHNESS_LIVENESS_ENABLED", "false")
    monkeypatch.setenv("INTAKE_DATABASE_URL", "postgresql://unreachable-host-must-not-be-dialed/db")

    async def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("asyncpg.connect must not be reached when the kill switch is off")

    monkeypatch.setattr(wmfl.asyncpg, "connect", _must_not_be_called)

    rc = asyncio.run(wmfl.run(dry_run=False))

    assert rc == 0
    assert hb == [("disabled", "WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=false")]


def test_run_level_kill_switch_accepts_case_insensitive_0(monkeypatch):
    hb = []
    monkeypatch.setattr(wmfl, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setenv("WA_MIRROR_FRESHNESS_LIVENESS_ENABLED", "0")
    monkeypatch.setenv("INTAKE_DATABASE_URL", "postgresql://unreachable-host-must-not-be-dialed/db")

    async def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("asyncpg.connect must not be reached when the kill switch is off")

    monkeypatch.setattr(wmfl.asyncpg, "connect", _must_not_be_called)

    rc = asyncio.run(wmfl.run(dry_run=False))

    assert rc == 0
    # note text is a fixed literal regardless of which accepted spelling
    # ("0"/"false"/"no") the caller used — only the short-circuit itself
    # (never dialing the DSN) is what this test exists to prove.
    assert hb == [("disabled", "WA_MIRROR_FRESHNESS_LIVENESS_ENABLED=false")]


def test_run_heartbeats_error_and_exits_2_on_uncaught_tick_exception(tmp_path, monkeypatch):
    hb = []
    monkeypatch.setattr(wmfl, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setattr(wmfl, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(wmfl, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setenv("WA_MIRROR_FRESHNESS_LIVENESS_ENABLED", "true")
    # A garbage env value is parsed OUTSIDE the connect-phase try/except (it
    # lives inside _tick), so pre-fix this propagated to Python's default
    # exit 1 with a bare traceback and no heartbeat at all.
    monkeypatch.setenv("WA_FRESHNESS_MAX_AGE_MIN", "not-a-number")

    async def _fake_connect(*_args, **_kwargs):
        return _StubConn()

    monkeypatch.setattr(wmfl.asyncpg, "connect", _fake_connect)

    rc = asyncio.run(wmfl.run(dry_run=True))

    assert rc == 2
    assert hb and hb[-1][0] == "error"


# ---------------------------------------------------------------- lock file chmod hardening (verbale #9)


def test_acquire_lock_hardens_a_pre_existing_loose_lock_file(tmp_path, monkeypatch):
    lock = tmp_path / "state" / "wa_mirror_freshness_liveness.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("")
    lock.chmod(0o644)  # simulate a pre-hardening-era lock file already on disk
    monkeypatch.setattr(wmfl, "LOCK_FILE", lock)

    fd = wmfl._acquire_lock_or_exit()
    try:
        assert fd is not None
        assert (lock.stat().st_mode & 0o777) == 0o600
    finally:
        if fd is not None:
            os.close(fd)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
