#!/usr/bin/env python3
"""Pure tests for wa_bot_throughput_sentinel.py — NO database (W87/W96).

The organism-wide discovery this organ exists to answer: on 2026-08-23 the
WhatsApp BOT product's last successful answer and last inbound webhook were
BOTH measured at 2026-07-30T01:23:58Z — 24 days of total silence while
/health, the broker gauge, the breaker, and the seat probe all read green.
`test_guilt_regression_the_2026_07_30_24_day_wa_bot_outage_fires_p0` below
feeds that exact measured shape back in and asserts a P0 fires.

Guilt: the three alarm conditions (dead_channel/bot_broken/inbound_stale)
each get a dedicated positive test. Innocence: an ordinary business-hours
morning, a non-business day, a stale-but-answered inbound, the kill switch,
and the sub-dead-channel evening quiet all stay silent for THEIR condition.

Every test injects a fake DB connection + a fake clock + a fake `_tg_notify`
— no Postgres, no network (same pattern as
scripts/tests/test_wa_mirror_freshness_liveness.py, the model this organ is
built on).

Run:  python3 -m pytest scripts/tests/test_wa_bot_throughput_sentinel.py -q
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import wa_bot_throughput_sentinel as wbts  # noqa: E402


# ---------------------------------------------------------------- pure math (shared shape with the model)


def test_age_minutes_computes_delta():
    now = datetime(2026, 8, 17, 10, 0, tzinfo=wbts.timezone.utc)
    newest = now - timedelta(minutes=90)
    assert wbts.age_minutes(newest, now) == 90.0


def test_age_minutes_none_when_table_empty():
    now = datetime(2026, 8, 17, 10, 0, tzinfo=wbts.timezone.utc)
    assert wbts.age_minutes(None, now) is None


def test_is_stale_true_beyond_max_age():
    assert wbts.is_stale(400.0, max_age_min=180.0) is True


def test_is_stale_false_within_max_age():
    assert wbts.is_stale(100.0, max_age_min=180.0) is False


def test_is_stale_true_when_age_is_none():
    assert wbts.is_stale(None, max_age_min=180.0) is True


def test_in_business_hours_true_weekday_daytime():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)  # Monday noon
    assert wbts.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is True


def test_in_business_hours_false_at_night():
    now_wita = datetime(2026, 8, 17, 3, 0, tzinfo=wbts.WITA)  # Monday 03:00
    assert wbts.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is False


def test_in_business_hours_false_on_sunday():
    now_wita = datetime(2026, 8, 16, 12, 0, tzinfo=wbts.WITA)  # Sunday noon
    assert wbts.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is False


def test_in_business_hours_boundary_end_hour_exclusive():
    now_wita = datetime(2026, 8, 17, 20, 0, tzinfo=wbts.WITA)  # exactly 20:00
    assert wbts.in_business_hours(now_wita, start_hour=8, end_hour=20, business_days={0, 1, 2, 3, 4, 5}) is False


def test_business_hours_open_wita_floors_to_start_hour():
    now_wita = datetime(2026, 8, 17, 14, 37, tzinfo=wbts.WITA)
    opened = wbts.business_hours_open_wita(now_wita, start_hour=8)
    assert opened == datetime(2026, 8, 17, 8, 0, tzinfo=wbts.WITA)


def test_business_reference_uses_newest_when_newer_than_open():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    newest = datetime(2026, 8, 17, 11, 30, tzinfo=wbts.WITA)
    assert wbts.business_reference(newest, now_wita, start_hour=8) == newest


def test_business_reference_floors_at_today_open_for_overnight_message():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    newest = datetime(2026, 8, 17, 5, 0, tzinfo=wbts.WITA)  # overnight, before open
    ref = wbts.business_reference(newest, now_wita, start_hour=8)
    assert ref == datetime(2026, 8, 17, 8, 0, tzinfo=wbts.WITA)


def test_business_reference_floors_at_today_open_when_table_empty():
    now_wita = datetime(2026, 8, 17, 11, 1, tzinfo=wbts.WITA)
    ref = wbts.business_reference(None, now_wita, start_hour=8)
    assert ref == datetime(2026, 8, 17, 8, 0, tzinfo=wbts.WITA)


def test_business_age_minutes_computes_delta_from_reference():
    ref = datetime(2026, 8, 17, 8, 0, tzinfo=wbts.WITA)
    now_wita = datetime(2026, 8, 17, 11, 1, tzinfo=wbts.WITA)
    assert wbts.business_age_minutes(ref, now_wita) == 181.0


# ---------------------------------------------------------------- SQL shape (scoped to the BOT product's own tables)


def test_inbound_sql_targets_whatsapp_channel_never_wa_mirror():
    assert "inbound_webhooks" in wbts.INBOUND_SQL
    assert "channel = 'whatsapp'" in wbts.INBOUND_SQL
    # This organ watches the BOT product, never the wa-mirror table that
    # wa_mirror_freshness_liveness.py already owns.
    assert "whatsapp_message_context" not in wbts.INBOUND_SQL


def test_outbound_sql_targets_done_status():
    assert "wa_outbox" in wbts.OUTBOUND_SQL
    assert "status = 'done'" in wbts.OUTBOUND_SQL


# ---------------------------------------------------------------- dedup key stability


def test_dedup_keys_are_fixed_literals_not_derived_from_variable_state():
    assert wbts.BOT_BROKEN_KEY == "wa-bot:throughput:bot-broken"
    assert wbts.DEAD_CHANNEL_KEY == "wa-bot:throughput:dead-channel"
    assert wbts.INBOUND_STALE_KEY == "wa-bot:throughput:inbound-stale"
    # The variable age lives in the TEXT, never in the key.
    text_a = wbts.build_bot_broken_text(10.0, 200.0)
    text_b = wbts.build_bot_broken_text(9000.0, 5000.0)
    assert text_a != text_b
    assert wbts.BOT_BROKEN_KEY not in text_a and wbts.BOT_BROKEN_KEY not in text_b


def test_dedup_key_recovered_is_date_stamped():
    now_wita = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    assert wbts.recovered_dedup_key(now_wita) == "wa-bot:throughput:recovered:2026-08-17"


def test_alert_payload_maps_each_condition_to_its_own_tier_and_key():
    tier, key, _ = wbts._alert_payload("dead_channel", 1.0, 1.0, 1.0, 1.0)
    assert (tier, key) == ("p0", wbts.DEAD_CHANNEL_KEY)
    tier, key, _ = wbts._alert_payload("bot_broken", 1.0, 1.0, 1.0, 1.0)
    assert (tier, key) == ("p0", wbts.BOT_BROKEN_KEY)
    tier, key, _ = wbts._alert_payload("inbound_stale", 1.0, 1.0, 1.0, 1.0)
    assert (tier, key) == ("digest", wbts.INBOUND_STALE_KEY)


def _gateway_tiers() -> tuple[str, ...]:
    """Parse TIERS out of scripts/tg_notify.py WITHOUT importing it (import has
    side effects). Parsed, never copied: if someone edits the gateway's tuple,
    this reads the new value and the test below tells us."""
    import ast

    gateway = pathlib.Path(wbts._REPO) / "scripts" / "tg_notify.py"
    tree = ast.parse(gateway.read_text(encoding="utf-8"), filename=str(gateway))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TIERS" for t in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"TIERS assignment not found in {gateway}")


def test_every_tier_this_module_emits_is_accepted_by_the_real_tg_notify_gateway():
    """Regression pin, 2026-08-23: this sentinel originally emitted tier "p1",
    which tg_notify.py rejects at argparse (`choices=TIERS`) — the alert would
    have been a silent no-op, i.e. a watcher that cannot raise its voice. Two
    other live scripts still carry that bug. Read the gateway's real tuple."""
    accepted = _gateway_tiers()
    emitted = {
        wbts._alert_payload(cond, 1.0, 1.0, 1.0, 1.0)[0]
        for cond in ("dead_channel", "bot_broken", "inbound_stale")
    }
    unusable = emitted - set(accepted)
    assert not unusable, (
        f"tiers {sorted(unusable)} are not in tg_notify TIERS {accepted} — "
        "argparse would reject them and the alert would never deliver"
    )


# ---------------------------------------------------------------- _tick guilt + innocence (FakeConn, no DB)


class _FakeConn:
    def __init__(self, inbound_newest, outbound_newest):
        self._inbound = inbound_newest
        self._outbound = outbound_newest

    async def fetchrow(self, query, *args, **kwargs):
        if "inbound_webhooks" in query:
            return {"newest": self._inbound}
        if "wa_outbox" in query:
            return {"newest": self._outbound}
        raise AssertionError(f"unexpected query: {query}")


def _run_tick(
    inbound_newest, outbound_newest, now_wita, *, dry_run, monkeypatch, tmp_path,
    prior_state=None,
    inbound_stale_min="180", outbound_stale_min="60", dead_channel_hours="48",
    business_start="8", business_end="20", business_days="0,1,2,3,4,5",
):
    sent = []
    state_path = tmp_path / "state.json"
    if prior_state is not None:
        state_path.write_text(json.dumps(prior_state), encoding="utf-8")
    monkeypatch.setattr(wbts, "_tg_notify", lambda tier, key, text: sent.append((tier, key, text)) or True)
    monkeypatch.setattr(wbts, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(wbts, "STATE_PATH", state_path)
    monkeypatch.setenv("WA_BOT_INBOUND_STALE_MIN", inbound_stale_min)
    monkeypatch.setenv("WA_BOT_OUTBOUND_STALE_MIN", outbound_stale_min)
    monkeypatch.setenv("WA_BOT_DEAD_CHANNEL_HOURS", dead_channel_hours)
    monkeypatch.setenv("WA_BOT_BUSINESS_START", business_start)
    monkeypatch.setenv("WA_BOT_BUSINESS_END", business_end)
    monkeypatch.setenv("WA_BOT_BUSINESS_DAYS", business_days)

    conn = _FakeConn(inbound_newest, outbound_newest)
    rc = asyncio.run(wbts._tick(conn, now_wita, dry_run=dry_run))
    return rc, sent


# ---- GUILT ------------------------------------------------------------------


def test_guilt_inbound_fresh_outbound_stale_fires_bot_broken_p0(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)  # Monday noon
    inbound_newest = now - timedelta(minutes=10)  # fresh
    outbound_newest = now - timedelta(hours=3)  # stale (>60min threshold)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    p0 = [s for s in sent if s[0] == "p0"]
    assert len(p0) == 1
    assert p0[0][1] == wbts.BOT_BROKEN_KEY


def test_guilt_both_stale_past_dead_channel_window_fires_p0_outside_business_hours(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 23, 0, tzinfo=wbts.WITA)  # Monday 23:00 — outside 8-20
    inbound_newest = now - timedelta(hours=50)  # >48h
    outbound_newest = now - timedelta(hours=50)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    p0 = [s for s in sent if s[0] == "p0"]
    assert len(p0) == 1
    assert p0[0][1] == wbts.DEAD_CHANNEL_KEY


def test_guilt_inbound_stale_5h_in_business_hours_fires_inbound_stale_digest(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 14, 0, tzinfo=wbts.WITA)  # Monday afternoon
    inbound_newest = now - timedelta(hours=5)  # >180min threshold
    outbound_newest = now - timedelta(minutes=5)  # bot answered recently
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    soft = [s for s in sent if s[0] == "digest"]
    assert len(soft) == 1
    assert soft[0][1] == wbts.INBOUND_STALE_KEY
    assert not any(s[1] == wbts.BOT_BROKEN_KEY for s in sent)


def test_guilt_regression_the_2026_07_30_24_day_wa_bot_outage_fires_p0(tmp_path, monkeypatch):
    """Encodes the REAL measured incident (memory
    discovery_the_whatsapp_bot_answered_nobody_for_24_days_..._2026_08_23):
    both the last inbound webhook and the last done outbound answer landed
    at the exact same instant, 2026-07-30T01:23:58Z, and stayed there for
    24 days while every other gauge in the fleet read green. This organ
    exists specifically because nothing else caught that. Timestamps are
    real UTC (as asyncpg would hand back a TIMESTAMPTZ column)."""
    inbound_newest = datetime(2026, 7, 30, 1, 23, 58, tzinfo=timezone.utc)
    outbound_newest = datetime(2026, 7, 30, 1, 23, 58, tzinfo=timezone.utc)
    now_utc = datetime(2026, 8, 23, 6, 15, 0, tzinfo=timezone.utc)
    now_wita = now_utc.astimezone(wbts.WITA)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now_wita, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    p0 = [s for s in sent if s[0] == "p0"]
    assert len(p0) == 1
    assert p0[0][1] == wbts.DEAD_CHANNEL_KEY


# ---- INNOCENCE ----------------------------------------------------------------


def test_innocence_normal_morning_overnight_gap_never_pages(tmp_path, monkeypatch):
    # newest=Sun 20:30, now=Mon 08:05 -> ref floors at Mon 08:00, age=5min.
    # This is exactly the false-P0 shape the freshness-liveness refuter caught.
    now = datetime(2026, 8, 17, 8, 5, tzinfo=wbts.WITA)  # Monday
    inbound_newest = datetime(2026, 8, 16, 20, 30, tzinfo=wbts.WITA)  # Sunday evening
    outbound_newest = datetime(2026, 8, 16, 20, 30, tzinfo=wbts.WITA)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_innocence_sunday_outside_business_days_never_evaluates_staleness(tmp_path, monkeypatch):
    now = datetime(2026, 8, 16, 15, 0, tzinfo=wbts.WITA)  # Sunday afternoon
    inbound_newest = datetime(2026, 8, 15, 19, 0, tzinfo=wbts.WITA)  # Saturday 19:00, ~20h
    outbound_newest = datetime(2026, 8, 15, 19, 0, tzinfo=wbts.WITA)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_innocence_stale_inbound_but_outbound_newer_never_claims_bot_broken(tmp_path, monkeypatch):
    # inbound 6h old, outbound 5h old (newer than inbound — we answered the
    # last thing that arrived). inbound_stale alone may still page (P1,
    # correctly), but "bot broken" must never fire: that claim requires
    # inbound to be FRESH, and it is not.
    now = datetime(2026, 8, 17, 14, 0, tzinfo=wbts.WITA)  # Monday afternoon
    inbound_newest = now - timedelta(hours=6)
    outbound_newest = now - timedelta(hours=5)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert not any(s[1] == wbts.BOT_BROKEN_KEY for s in sent)


def test_innocence_evening_under_dead_channel_window_stays_silent(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 22, 0, tzinfo=wbts.WITA)  # Monday 22:00 — outside business hours
    inbound_newest = now - timedelta(hours=4)
    outbound_newest = now - timedelta(hours=4)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_innocence_fresh_both_signals_in_business_hours_sends_nothing(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=5)
    outbound_newest = now - timedelta(minutes=3)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []


def test_dry_run_never_sends_even_when_bot_broken_in_business_hours(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=10)
    outbound_newest = now - timedelta(hours=3)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=True,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    assert sent == []
    assert not (tmp_path / "state.json").exists()


# ---------------------------------------------------------------- alerted persisted BEFORE write


def test_alerted_flag_is_persisted_in_the_written_state_file(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=10)
    outbound_newest = now - timedelta(hours=3)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    written = json.loads((tmp_path / "state.json").read_text())
    assert written["alerted"] is True
    assert written["condition"] == "bot_broken"


def test_innocent_tick_persists_alerted_false(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=5)
    outbound_newest = now - timedelta(minutes=3)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path)
    assert rc == 0
    written = json.loads((tmp_path / "state.json").read_text())
    assert written["alerted"] is False
    assert written["condition"] is None


# ---------------------------------------------------------------- recovered digest


def test_recovered_digest_sent_when_previous_alerted_and_now_clear(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=5)
    outbound_newest = now - timedelta(minutes=3)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path, prior_state={"alerted": True})
    assert rc == 0
    digests = [s for s in sent if s[0] == "digest"]
    assert len(digests) == 1
    assert digests[0][1] == f"wa-bot:throughput:recovered:{now.strftime('%Y-%m-%d')}"


def test_no_recovered_digest_when_previous_was_not_alerted(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=5)
    outbound_newest = now - timedelta(minutes=3)
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path, prior_state={"alerted": False})
    assert rc == 0
    assert sent == []


def test_no_recovered_digest_when_still_alerting(tmp_path, monkeypatch):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=wbts.WITA)
    inbound_newest = now - timedelta(minutes=10)
    outbound_newest = now - timedelta(hours=3)  # still bot_broken
    rc, sent = _run_tick(inbound_newest, outbound_newest, now, dry_run=False,
                          monkeypatch=monkeypatch, tmp_path=tmp_path, prior_state={"alerted": True})
    assert rc == 0
    assert [s for s in sent if s[0] == "digest"] == []
    assert len([s for s in sent if s[0] == "p0"]) == 1


# ---------------------------------------------------------------- run() wraps the whole tick (verbale #6 shape)


class _StubConn:
    async def fetchrow(self, query, *args, **kwargs):
        return {"newest": None}

    async def close(self):
        return None


def test_run_level_kill_switch_never_reaches_the_dsn(monkeypatch):
    hb = []
    monkeypatch.setattr(wbts, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setenv("WA_BOT_THROUGHPUT_SENTINEL_ENABLED", "false")
    monkeypatch.setenv("INTAKE_DATABASE_URL", "postgresql://unreachable-host-must-not-be-dialed/db")

    async def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("asyncpg.connect must not be reached when the kill switch is off")

    monkeypatch.setattr(wbts.asyncpg, "connect", _must_not_be_called)

    rc = asyncio.run(wbts.run(dry_run=False))

    assert rc == 0
    assert hb == [("disabled", "WA_BOT_THROUGHPUT_SENTINEL_ENABLED=false")]


def test_run_level_kill_switch_accepts_case_insensitive_0(monkeypatch):
    hb = []
    monkeypatch.setattr(wbts, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setenv("WA_BOT_THROUGHPUT_SENTINEL_ENABLED", "0")
    monkeypatch.setenv("INTAKE_DATABASE_URL", "postgresql://unreachable-host-must-not-be-dialed/db")

    async def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("asyncpg.connect must not be reached when the kill switch is off")

    monkeypatch.setattr(wbts.asyncpg, "connect", _must_not_be_called)

    rc = asyncio.run(wbts.run(dry_run=False))

    assert rc == 0
    assert hb == [("disabled", "WA_BOT_THROUGHPUT_SENTINEL_ENABLED=false")]


def test_run_heartbeats_error_and_exits_2_on_uncaught_tick_exception(tmp_path, monkeypatch):
    hb = []
    monkeypatch.setattr(wbts, "_heartbeat", lambda status, note="": hb.append((status, note)))
    monkeypatch.setattr(wbts, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(wbts, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setenv("WA_BOT_THROUGHPUT_SENTINEL_ENABLED", "true")
    # A garbage env value is parsed OUTSIDE the connect-phase try/except (it
    # lives inside _tick) — pre-fix this would propagate to Python's default
    # exit 1 with a bare traceback and no heartbeat at all.
    monkeypatch.setenv("WA_BOT_INBOUND_STALE_MIN", "not-a-number")

    async def _fake_connect(*_args, **_kwargs):
        return _StubConn()

    monkeypatch.setattr(wbts.asyncpg, "connect", _fake_connect)

    rc = asyncio.run(wbts.run(dry_run=True))

    assert rc == 2
    assert hb and hb[-1][0] == "error"


def test_run_PAGES_not_merely_heartbeats_when_the_tick_fails(tmp_path, monkeypatch):
    """A heartbeat file is not an alarm — nothing pages off it. If a revoked
    GRANT, a renamed column or an unreachable DB kills the tick, this organ must
    say so out loud, or it goes mute in exactly the way the 24-day outage it was
    built for went mute. Mutation-verified 2026-08-23: without the _tg_notify in
    run()'s except branch, every other test in this file still passed."""
    sent = []
    monkeypatch.setattr(wbts, "_tg_notify", lambda t, k, x: (sent.append((t, k, x)) or True))
    monkeypatch.setattr(wbts, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(wbts, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(wbts, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setenv("WA_BOT_THROUGHPUT_SENTINEL_ENABLED", "true")
    monkeypatch.setenv("WA_BOT_INBOUND_STALE_MIN", "not-a-number")

    async def _fake_connect(*_args, **_kwargs):
        return _StubConn()

    monkeypatch.setattr(wbts.asyncpg, "connect", _fake_connect)

    rc = asyncio.run(wbts.run(dry_run=False))

    assert rc == 2
    assert len(sent) == 1, "a failed tick must page exactly once"
    tier, key, text = sent[0]
    assert tier == "p0"
    assert key == wbts.WRONG_DB_KEY
    # The text must say the WATCHER is down, not that the channel is — an
    # operator reading it should go fix the sentinel, not go hunt WhatsApp.
    assert "sentinel" in text.lower()
    assert "ValueError" in text  # the real cause is named, not swallowed


def test_run_stays_silent_on_a_failed_tick_when_dry_run(tmp_path, monkeypatch):
    """Innocence half: --dry-run must never page, not even on failure."""
    sent = []
    monkeypatch.setattr(wbts, "_tg_notify", lambda t, k, x: (sent.append(k) or True))
    monkeypatch.setattr(wbts, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(wbts, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(wbts, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setenv("WA_BOT_THROUGHPUT_SENTINEL_ENABLED", "true")
    monkeypatch.setenv("WA_BOT_INBOUND_STALE_MIN", "not-a-number")

    async def _fake_connect(*_args, **_kwargs):
        return _StubConn()

    monkeypatch.setattr(wbts.asyncpg, "connect", _fake_connect)

    assert asyncio.run(wbts.run(dry_run=True)) == 2
    assert sent == []


def test_acquire_lock_hardens_a_pre_existing_loose_lock_file(tmp_path, monkeypatch):
    lock = tmp_path / "state" / "wa_bot_throughput_sentinel.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("")
    lock.chmod(0o644)  # simulate a pre-hardening-era lock file already on disk
    monkeypatch.setattr(wbts, "LOCK_FILE", lock)

    fd = wbts._acquire_lock_or_exit()
    try:
        assert fd is not None
        assert (lock.stat().st_mode & 0o777) == 0o600
    finally:
        if fd is not None:
            import os

            os.close(fd)


# ------------------------------------------------- wrong-database short-circuit (guilt + innocence)


class _HistConn:
    """FakeConn that also answers HISTORY_SQL, so the wrong-database branch is
    reachable. `rows` is the (outbox_rows, inbound_rows) pair that branch reads."""

    def __init__(self, inbound, outbound, rows=(0, 0)):
        self.inbound, self.outbound, self.rows = inbound, outbound, rows

    async def fetchrow(self, sql, *a, **kw):
        q = " ".join(sql.split()).lower()
        if "count(*)" in q:
            return {"outbox_rows": self.rows[0], "inbound_rows": self.rows[1]}
        if "inbound_webhooks" in q:
            return {"newest": self.inbound}
        return {"newest": self.outbound}


def _run_hist_tick(conn, now, monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(wbts, "_tg_notify", lambda t, k, x: (sent.append((t, k)) or True))
    monkeypatch.setattr(wbts, "_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(wbts, "_write_state", lambda s: None)
    monkeypatch.setattr(wbts, "_read_state", lambda: None)
    rc = asyncio.run(wbts._tick(conn, now, dry_run=False))
    return rc, sent


def test_guilt_both_tables_entirely_empty_reports_wrong_database_not_a_dead_channel(
    tmp_path, monkeypatch
):
    """The local dev DB carries both tables with ZERO rows (measured 2026-08-23).
    Run there, the organ must say "I am blind", never "the channel is dead" — a
    p0 on every tick forever is an alarm nobody reads."""
    now = datetime(2026, 8, 17, 14, 0, tzinfo=wbts.WITA)
    rc, sent = _run_hist_tick(_HistConn(None, None, rows=(0, 0)), now, monkeypatch, tmp_path)
    assert rc == 2
    assert [k for _, k in sent] == [wbts.WRONG_DB_KEY]
    assert wbts.DEAD_CHANNEL_KEY not in [k for _, k in sent]


def test_innocence_null_signals_but_real_history_is_a_dead_channel_not_a_wrong_database(
    tmp_path, monkeypatch
):
    """A truncated PROD table also reads NULL — but prod carried 325 wa_outbox
    rows while the bot was dead, so history>0 must still reach dead_channel.
    This is the pair that stops the new short-circuit from swallowing a real
    outage."""
    now = datetime(2026, 8, 17, 14, 0, tzinfo=wbts.WITA)
    rc, sent = _run_hist_tick(_HistConn(None, None, rows=(325, 244)), now, monkeypatch, tmp_path)
    assert rc == 0
    assert [k for _, k in sent] == [wbts.DEAD_CHANNEL_KEY]


def test_innocence_one_signal_present_never_consults_history_at_all(tmp_path, monkeypatch):
    """The short-circuit requires BOTH signals NULL. With one present the organ
    must classify normally — a conn that raises on HISTORY_SQL proves it is
    never even queried."""

    class NoHistory(_HistConn):
        async def fetchrow(self, sql, *a, **kw):
            if "count(*)" in " ".join(sql.split()).lower():
                raise AssertionError("HISTORY_SQL must not run when a signal exists")
            return await super().fetchrow(sql, *a, **kw)

    now = datetime(2026, 8, 17, 14, 0, tzinfo=wbts.WITA)
    fresh = now - timedelta(minutes=5)
    rc, sent = _run_hist_tick(NoHistory(fresh, None), now, monkeypatch, tmp_path)
    assert rc == 0
    assert [k for _, k in sent] == [wbts.BOT_BROKEN_KEY]


def test_wrong_db_text_blames_configuration_and_never_claims_the_channel_is_down():
    """Wording is load-bearing: an operator reading this must go check a DSN, not
    go restart WhatsApp."""
    text = wbts.build_wrong_db_text()
    assert "INTAKE_DATABASE_URL" in text
    assert "CONFIGURATION" in text.upper()
    for forbidden in ("channel is dead", "bot is dead", "no client"):
        assert forbidden not in text.lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
