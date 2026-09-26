"""Tests for scripts/nlm_watchdog.py — the M5 -> Pro cross-host NLM probe.

No real ssh, nlm or Telegram call runs here: probes, sleep and tg_notify.py are
injected or replaced by fakes. No real PII: the only account string is the
synthetic `owner@example.test`.

Covered, guilt and innocence:
  - _display_name: a notebook is named by its id8 (or "unknown"), never a title.
  - classify_login: "Authentication invalid" at rc 0 is dead; an unrecognized
    shape and an ssh timeout are unknown; the success shape is ok; the raw
    output never reaches the reason.
  - evaluate_inventory_data: a notebook at/above cap_warn, a non-numeric
    source_count, a malformed notebooks list, and a stale, naive or future
    `generated_at` degrade; a fresh inventory below cap_warn is ok.
  - _fetch_inventory_data: an empty or unparseable read is retried once; an ssh
    failure is not retried.
  - write_heartbeat / read_previous_state: atomic write, `note`/`last_error`
    and `codes` keys, False on a write failure.
  - maybe_alert: sends on a change of status, code set or near_cap_ids; silent
    otherwise and on a first tick that is ok.
  - main(): import failure and probe crash write a degraded heartbeat and exit
    1 (the crash reason is the exception type name only); a heartbeat write
    failure exits 1; --dry-run writes nothing.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import nlm_watchdog  # noqa: E402


NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
SYNTHETIC_EMAIL = "owner@example.test"

# Shape of `nlm login --check` success output, with a synthetic account line.
REAL_SHAPE_OK_OUTPUT = (
    "Checking credentials for profile: default...\n"
    "✓ Authentication valid!\n"
    "  Profile: default\n"
    "  Notebooks found: 62\n"
    f"  Account: {SYNTHETIC_EMAIL}\n"
)


def _inventory(notebooks, generated_at=None):
    return json.dumps({
        "generated_at": (generated_at or NOW).isoformat(),
        "notebook_count": len(notebooks),
        "notebooks": notebooks,
    })


@pytest.fixture(autouse=True)
def _no_real_tg_notify(tmp_path, monkeypatch):
    # The real tg_notify.py reads ~/.nuzantara-secrets.env; tests that check
    # Telegram install their own fake.
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", tmp_path / "absent-tg_notify.py")


# --- _display_name (PII boundary: id ONLY, never a title) -------------------

def test_display_name_returns_id_prefix():
    assert nlm_watchdog._display_name("dc5d01cd-e99f-4c8f") == "dc5d01cd"


def test_display_name_missing_id_falls_back_to_unknown():
    assert nlm_watchdog._display_name(None) == "unknown"
    assert nlm_watchdog._display_name("") == "unknown"


# --- classify_login -----------------------------------------------------------

def test_classify_login_ok_on_real_shape():
    ok, reason, code = nlm_watchdog.classify_login(0, REAL_SHAPE_OK_OUTPUT)
    assert ok is True
    assert reason == ""
    assert code is None


def test_classify_login_guilty_on_authentication_invalid_rc0():
    # rc 0 with a status line containing "valid" as a substring.
    ok, reason, code = nlm_watchdog.classify_login(0, "Authentication invalid")
    assert ok is False
    assert code == nlm_watchdog.Code.LOGIN_DEAD
    assert "dead" in reason


def test_classify_login_guilty_on_dead_cookie_phrase():
    ok, reason, code = nlm_watchdog.classify_login(
        1, "Authentication expired — please login again."
    )
    assert ok is False
    assert code == nlm_watchdog.Code.LOGIN_DEAD


def test_classify_login_guilty_on_unknown_shape():
    ok, reason, code = nlm_watchdog.classify_login(
        1, "✗ Authentication failed: Could not reach NotebookLM (network_error: ...)"
    )
    assert ok is False
    assert code == nlm_watchdog.Code.LOGIN_UNKNOWN


def test_classify_login_guilty_on_ssh_timeout():
    ok, reason, code = nlm_watchdog.classify_login(124, "TIMEOUT")
    assert ok is False
    assert code == nlm_watchdog.Code.LOGIN_UNKNOWN
    assert reason


def test_classify_login_never_echoes_raw_output():
    # The reason is fixed text on every path, never `out`.
    for rc, out in (
        (0, REAL_SHAPE_OK_OUTPUT),
        (0, "Authentication invalid"),
        (1, "some garbage " + SYNTHETIC_EMAIL),
    ):
        _, reason, _ = nlm_watchdog.classify_login(rc, out)
        assert SYNTHETIC_EMAIL not in reason
        assert "garbage" not in reason


# --- evaluate_inventory_data ---------------------------------------------------

def test_evaluate_inventory_innocent_when_all_below_cap_and_fresh():
    data = json.loads(_inventory([
        {"id": "aaa11111", "title": "NB-3: Company Setup", "source_count": 359},
        {"id": "bbb22222", "title": "NB-8 Expat Life Bali", "source_count": 208},
    ]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is True
    assert reasons == []
    assert codes == set()
    assert ctx["max_source_count"] == 359


def test_evaluate_inventory_guilty_on_notebook_at_cap_shows_id_and_count():
    data = json.loads(_inventory([
        {"id": "dc5d01cd-e99f", "title": "NB-INTEL-AIResearch — Daily AI Intelligence", "source_count": 500},
    ]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.CAP_NEAR in codes
    assert "dc5d01cd" in reasons[0]
    assert "500" in reasons[0]
    assert ctx["near_cap_ids"] == ["dc5d01cd"]


def test_evaluate_inventory_never_leaks_any_title_curated_or_not():
    # An `NB-`-prefixed title can still carry a client name: only the id8 shows.
    data = json.loads(_inventory([
        {"id": "abcd1234xyz", "title": "NB-CLIENT-CASE Jane Doe", "source_count": 460},
    ]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.CAP_NEAR in codes
    joined = " ".join(reasons)
    assert "abcd1234" in joined
    assert "NB-CLIENT" not in joined
    assert "Jane" not in joined
    assert ctx["near_cap_ids"] == ["abcd1234"]


def test_evaluate_inventory_near_cap_ids_tracks_multiple_notebooks():
    data = json.loads(_inventory([
        {"id": "aaa11111", "title": "NB-3", "source_count": 460},
        {"id": "bbb22222", "title": "NB-8", "source_count": 470},
        {"id": "ccc33333", "title": "NB-9", "source_count": 10},
    ]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert ctx["near_cap_ids"] == ["aaa11111", "bbb22222"]


def test_evaluate_inventory_guilty_on_non_numeric_source_count_skips_not_crashes():
    data = json.loads(_inventory([
        {"id": "aaa11111", "title": "NB-3", "source_count": "500"},
        {"id": "bbb22222", "title": "NB-8", "source_count": 10},
    ]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_MALFORMED in codes
    assert "non-numeric source_count" in " ".join(reasons)
    # The numeric entry is still counted.
    assert ctx["max_source_count"] == 10


def test_evaluate_inventory_bool_source_count_treated_as_non_numeric():
    # bool is an int subclass in Python — must NOT be accepted as a count.
    data = json.loads(_inventory([{"id": "aaa11111", "title": "NB-3", "source_count": True}]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_MALFORMED in codes


def test_evaluate_inventory_guilty_on_malformed_notebooks_list():
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(
        {"generated_at": NOW.isoformat(), "notebooks": "not-a-list"}, cap_warn=450, stale_hours=30, now=NOW
    )
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_MALFORMED in codes


def test_evaluate_inventory_guilty_on_stale_timestamp():
    old = NOW - timedelta(hours=48)
    data = json.loads(_inventory([{"id": "x", "title": "NB-3", "source_count": 10}], generated_at=old))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_STALE in codes
    assert ctx["inventory_age_h"] == 48.0


def test_evaluate_inventory_innocent_at_exactly_stale_boundary():
    just_under = NOW - timedelta(hours=29)
    data = json.loads(_inventory([{"id": "x", "title": "NB-3", "source_count": 10}], generated_at=just_under))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is True
    assert codes == set()


def test_evaluate_inventory_guilty_on_naive_timestamp_degrades_not_crashes():
    # No tzinfo — `now (aware) - ts (naive)` raises TypeError if uncaught.
    data = {
        "generated_at": "2026-09-24T04:00:00",  # naive, no offset
        "notebooks": [{"id": "x", "title": "NB-3", "source_count": 10}],
    }
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_TIMESTAMP_INVALID in codes
    assert "inventory_age_h" not in ctx


def test_evaluate_inventory_guilty_on_future_timestamp_clock_skew():
    future = NOW + timedelta(minutes=20)
    data = json.loads(_inventory([{"id": "x", "title": "NB-3", "source_count": 10}], generated_at=future))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_TIMESTAMP_INVALID in codes
    assert "future" in reasons[0] or "clock skew" in reasons[0]


def test_evaluate_inventory_innocent_on_tiny_future_skew_within_tolerance():
    # 5 minutes is inside the 10-minute clock-skew tolerance.
    slightly_future = NOW + timedelta(minutes=5)
    data = json.loads(_inventory([{"id": "x", "title": "NB-3", "source_count": 10}], generated_at=slightly_future))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is True


def test_evaluate_inventory_handles_plus_seven_offset_correctly():
    # 2026-09-25T19:00:00+07:00 == 2026-09-25T12:00:00Z == NOW exactly.
    data = {
        "generated_at": "2026-09-25T19:00:00+07:00",
        "notebooks": [{"id": "x", "title": "NB-3", "source_count": 10}],
    }
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is True
    assert ctx["inventory_age_h"] == 0.0


# --- _fetch_inventory_data / retry-on-race ------------------------------------

def test_fetch_inventory_retries_once_then_succeeds():
    good = _inventory([{"id": "x", "title": "NB-3", "source_count": 10}])
    responses = iter([(0, "{truncated"), (0, good)])
    sleeps = []
    data, reason, code = nlm_watchdog._fetch_inventory_data(
        inventory_fn=lambda: next(responses), sleep_fn=lambda s: sleeps.append(s), retry_delay_s=5.0
    )
    assert data is not None
    assert reason is None
    assert sleeps == [5.0]


def test_fetch_inventory_degrades_after_retry_still_fails():
    responses = iter([(0, "{truncated"), (0, "{still truncated")])
    sleeps = []
    data, reason, code = nlm_watchdog._fetch_inventory_data(
        inventory_fn=lambda: next(responses), sleep_fn=lambda s: sleeps.append(s), retry_delay_s=5.0
    )
    assert data is None
    assert code == nlm_watchdog.Code.INVENTORY_MALFORMED
    assert "retry" in reason
    assert sleeps == [5.0]


def test_fetch_inventory_first_empty_retries_then_succeeds():
    good = _inventory([{"id": "x", "title": "NB-3", "source_count": 10}])
    responses = iter([(0, ""), (0, good)])
    sleeps = []
    data, reason, code = nlm_watchdog._fetch_inventory_data(
        inventory_fn=lambda: next(responses), sleep_fn=lambda s: sleeps.append(s), retry_delay_s=5.0
    )
    assert data is not None
    assert reason is None
    assert sleeps == [5.0]


def test_fetch_inventory_first_empty_second_empty_reports_missing():
    responses = iter([(0, ""), (0, "   ")])
    sleeps = []
    data, reason, code = nlm_watchdog._fetch_inventory_data(
        inventory_fn=lambda: next(responses), sleep_fn=lambda s: sleeps.append(s), retry_delay_s=5.0
    )
    assert data is None
    assert code == nlm_watchdog.Code.INVENTORY_MISSING
    assert sleeps == [5.0]


def test_fetch_inventory_first_malformed_second_ssh_fails_reports_missing():
    # An ssh failure on the retry is MISSING, not MALFORMED.
    responses = iter([(0, "{truncated"), (255, "")])
    sleeps = []
    data, reason, code = nlm_watchdog._fetch_inventory_data(
        inventory_fn=lambda: next(responses), sleep_fn=lambda s: sleeps.append(s), retry_delay_s=5.0
    )
    assert data is None
    assert code == nlm_watchdog.Code.INVENTORY_MISSING
    assert sleeps == [5.0]


def test_fetch_inventory_ssh_failure_never_retries():
    calls = []
    def _fn():
        calls.append(1)
        return (255, "")
    sleeps = []
    data, reason, code = nlm_watchdog._fetch_inventory_data(
        inventory_fn=_fn, sleep_fn=lambda s: sleeps.append(s), retry_delay_s=5.0
    )
    assert data is None
    assert code == nlm_watchdog.Code.INVENTORY_MISSING
    assert len(calls) == 1  # no retry on a hard ssh failure
    assert sleeps == []


# --- run_once (composition, injected fakes, no real ssh, no real sleep) -----

def test_run_once_innocent_when_both_probes_clean():
    raw = _inventory([{"id": "x", "title": "NB-3", "source_count": 10}])
    v = nlm_watchdog.run_once(
        login_fn=lambda: (0, REAL_SHAPE_OK_OUTPUT),
        inventory_fn=lambda: (0, raw),
        cap_warn=450, stale_hours=30, now=NOW, sleep_fn=lambda s: None,
    )
    assert v.ok is True
    assert v.reasons == []
    assert v.codes == set()


def test_run_once_guilty_on_login_failure_alone():
    raw = _inventory([{"id": "x", "title": "NB-3", "source_count": 10}])
    v = nlm_watchdog.run_once(
        login_fn=lambda: (0, "Authentication invalid"),
        inventory_fn=lambda: (0, raw),
        cap_warn=450, stale_hours=30, now=NOW, sleep_fn=lambda s: None,
    )
    assert v.ok is False
    assert v.codes == {nlm_watchdog.Code.LOGIN_DEAD}


def test_run_once_guilty_on_inventory_fetch_failure():
    v = nlm_watchdog.run_once(
        login_fn=lambda: (0, REAL_SHAPE_OK_OUTPUT),
        inventory_fn=lambda: (255, ""),
        cap_warn=450, stale_hours=30, now=NOW, sleep_fn=lambda s: None,
    )
    assert v.ok is False
    assert v.codes == {nlm_watchdog.Code.INVENTORY_MISSING}


def test_run_once_accumulates_both_failures_as_distinct_codes():
    v = nlm_watchdog.run_once(
        login_fn=lambda: (124, "TIMEOUT"),
        inventory_fn=lambda: (0, _inventory([{"id": "x", "title": "NB-3", "source_count": 500}])),
        cap_warn=450, stale_hours=30, now=NOW, sleep_fn=lambda s: None,
    )
    assert v.ok is False
    assert v.codes == {nlm_watchdog.Code.LOGIN_UNKNOWN, nlm_watchdog.Code.CAP_NEAR}


# --- heartbeat (G2, atomic write) --------------------------------------------

def test_write_heartbeat_ok_shape(tmp_path):
    hb = tmp_path / "nlm-watchdog.json"
    v = nlm_watchdog.Verdict(ok=True, reasons=[], codes=set(), ctx={"max_source_count": 10})
    assert nlm_watchdog.write_heartbeat(v, path=hb) is True
    data = json.loads(hb.read_text())
    assert data["status"] == "ok"
    assert data["organ"] == "nlm-watchdog"
    assert data["codes"] == []
    assert "note" not in data
    assert data["max_source_count"] == 10


def test_write_heartbeat_degraded_shape_uses_note_and_last_error_keys():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        hb = Path(d) / "nlm-watchdog.json"
        v = nlm_watchdog.Verdict(ok=False, reasons=["pro nlm login dead"], codes={nlm_watchdog.Code.LOGIN_DEAD})
        nlm_watchdog.write_heartbeat(v, path=hb)
        data = json.loads(hb.read_text())
        assert data["status"] == "degraded"
        # organism_stale_detector.py's _sidecar_note() reads "note" or "last_error".
        assert "dead" in data["note"]
        assert data["last_error"] == data["note"]
        assert data["codes"] == [nlm_watchdog.Code.LOGIN_DEAD]


def test_write_heartbeat_leaves_no_tmp_file_behind(tmp_path):
    hb = tmp_path / "nlm-watchdog.json"
    v = nlm_watchdog.Verdict(ok=True)
    nlm_watchdog.write_heartbeat(v, path=hb)
    leftovers = list(tmp_path.glob("*.tmp.*"))
    assert leftovers == []


def test_write_heartbeat_never_carries_raw_login_output_end_to_end(tmp_path):
    # W114: checks the file on disk after run_once -> write_heartbeat.
    hb = tmp_path / "nlm-watchdog.json"
    raw_email_bearing_output = f"logged in as {SYNTHETIC_EMAIL}, token ok, no valid marker here"
    v = nlm_watchdog.run_once(
        login_fn=lambda: (0, raw_email_bearing_output),
        inventory_fn=lambda: (0, _inventory([{"id": "x", "title": "NB-3", "source_count": 1}])),
        now=NOW, sleep_fn=lambda s: None,
    )
    nlm_watchdog.write_heartbeat(v, path=hb)
    assert SYNTHETIC_EMAIL not in hb.read_text()


def test_write_heartbeat_returns_false_on_write_failure(tmp_path, monkeypatch):
    hb = tmp_path / "nlm-watchdog.json"

    def _boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(nlm_watchdog.os, "replace", _boom)
    v = nlm_watchdog.Verdict(ok=True)
    assert nlm_watchdog.write_heartbeat(v, path=hb) is False


def test_read_previous_state_missing_file_returns_none_and_empty_set(tmp_path):
    status, codes, near_cap_ids = nlm_watchdog.read_previous_state(path=tmp_path / "absent.json")
    assert status is None
    assert codes == set()
    assert near_cap_ids == []


def test_read_previous_state_round_trips_codes(tmp_path):
    hb = tmp_path / "nlm-watchdog.json"
    v = nlm_watchdog.Verdict(ok=False, reasons=["x"], codes={nlm_watchdog.Code.LOGIN_DEAD})
    nlm_watchdog.write_heartbeat(v, path=hb)
    status, codes, near_cap_ids = nlm_watchdog.read_previous_state(path=hb)
    assert status == "degraded"
    assert codes == {nlm_watchdog.Code.LOGIN_DEAD}
    assert near_cap_ids == []


def test_read_previous_state_round_trips_near_cap_ids(tmp_path):
    hb = tmp_path / "nlm-watchdog.json"
    v = nlm_watchdog.Verdict(
        ok=False, reasons=["near cap"], codes={nlm_watchdog.Code.CAP_NEAR},
        ctx={"near_cap_ids": ["bbb22222", "aaa11111"]},
    )
    nlm_watchdog.write_heartbeat(v, path=hb)
    status, codes, near_cap_ids = nlm_watchdog.read_previous_state(path=hb)
    assert near_cap_ids == ["aaa11111", "bbb22222"]  # sorted on read back


# --- maybe_alert: transition- AND reason-code-gated Telegram ----------------

def _install_fake_tg_notify(tmp_path):
    fake = tmp_path / "tg_notify.py"
    marker = tmp_path / "called.jsonl"
    fake.write_text(textwrap.dedent(f"""\
        import sys, json
        with open({str(marker)!r}, "a") as f:
            f.write(json.dumps(sys.argv[1:]) + "\\n")
        print("tg_notify: sent")
    """))
    return fake, marker


def test_maybe_alert_fires_on_ok_to_degraded_transition(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=False, reasons=["pro nlm login dead"], codes={nlm_watchdog.Code.LOGIN_DEAD})
    fired = nlm_watchdog.maybe_alert(v, previous_status="ok", previous_codes=set())
    assert fired is True
    assert marker.exists()
    argv = json.loads(marker.read_text().splitlines()[0])
    assert "--tier" in argv and "p0" in argv


def test_maybe_alert_fires_on_degraded_to_ok_recovery(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=True, reasons=[], codes=set())
    fired = nlm_watchdog.maybe_alert(v, previous_status="degraded", previous_codes={nlm_watchdog.Code.LOGIN_DEAD})
    assert fired is True
    assert marker.exists()


def test_maybe_alert_silent_on_same_status_ok(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=True, reasons=[], codes=set())
    fired = nlm_watchdog.maybe_alert(v, previous_status="ok", previous_codes=set())
    assert fired is False
    assert not marker.exists()


def test_maybe_alert_silent_on_degraded_to_degraded_same_codes(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=False, reasons=["x"], codes={nlm_watchdog.Code.LOGIN_DEAD})
    fired = nlm_watchdog.maybe_alert(v, previous_status="degraded", previous_codes={nlm_watchdog.Code.LOGIN_DEAD})
    assert fired is False
    assert not marker.exists()


def test_maybe_alert_fires_on_degraded_to_degraded_different_codes(tmp_path, monkeypatch):
    # Status stays degraded, the problem changes.
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=False, reasons=["inventory stale"], codes={nlm_watchdog.Code.INVENTORY_STALE})
    fired = nlm_watchdog.maybe_alert(v, previous_status="degraded", previous_codes={nlm_watchdog.Code.LOGIN_DEAD})
    assert fired is True
    assert marker.exists()


def test_maybe_alert_silent_on_first_ever_tick_that_reads_ok(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=True, reasons=[], codes=set())
    fired = nlm_watchdog.maybe_alert(v, previous_status=None, previous_codes=set())
    assert fired is False
    assert not marker.exists()


def test_maybe_alert_fires_on_first_ever_tick_that_reads_degraded(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(ok=False, reasons=["pro nlm login dead"], codes={nlm_watchdog.Code.LOGIN_DEAD})
    fired = nlm_watchdog.maybe_alert(v, previous_status=None, previous_codes=set())
    assert fired is True
    assert marker.exists()


def test_maybe_alert_fires_when_a_new_notebook_joins_near_cap(tmp_path, monkeypatch):
    # Same status and code set; near_cap_ids gains a notebook.
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(
        ok=False, reasons=["near cap"], codes={nlm_watchdog.Code.CAP_NEAR},
        ctx={"near_cap_ids": ["aaa11111", "bbb22222"]},
    )
    fired = nlm_watchdog.maybe_alert(
        v, previous_status="degraded", previous_codes={nlm_watchdog.Code.CAP_NEAR},
        previous_near_cap_ids=["aaa11111"],
    )
    assert fired is True
    assert marker.exists()


def test_maybe_alert_silent_when_near_cap_set_is_unchanged(tmp_path, monkeypatch):
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    v = nlm_watchdog.Verdict(
        ok=False, reasons=["near cap"], codes={nlm_watchdog.Code.CAP_NEAR},
        ctx={"near_cap_ids": ["aaa11111", "bbb22222"]},
    )
    fired = nlm_watchdog.maybe_alert(
        v, previous_status="degraded", previous_codes={nlm_watchdog.Code.CAP_NEAR},
        previous_near_cap_ids=["bbb22222", "aaa11111"],  # same set, different order
    )
    assert fired is False
    assert not marker.exists()


def test_maybe_alert_telegram_failure_does_not_raise(tmp_path, monkeypatch):
    broken = tmp_path / "tg_notify.py"
    broken.write_text("import sys; sys.exit(3)\n")
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", broken)
    v = nlm_watchdog.Verdict(ok=False, reasons=["x"], codes={nlm_watchdog.Code.LOGIN_DEAD})
    fired = nlm_watchdog.maybe_alert(v, previous_status="ok", previous_codes=set())
    assert fired is True  # attempted, even though the gateway itself failed


# --- main() fail-visibility (G9) ---------------------------------------------

def test_main_writes_degraded_heartbeat_on_probe_crash_without_leaking_message(tmp_path, monkeypatch):
    hb = tmp_path / "nlm-watchdog.json"
    monkeypatch.setattr(nlm_watchdog, "HEARTBEAT_PATH", hb)

    def _boom(*_a, **_kw):
        raise RuntimeError(f"kaboom leaking {SYNTHETIC_EMAIL}")

    monkeypatch.setattr(nlm_watchdog, "live_login_probe", _boom)
    rc = nlm_watchdog.main(["--ssh-connect-timeout", "1", "--ssh-timeout", "1"])
    assert rc == 1
    data = json.loads(hb.read_text())
    assert data["status"] == "degraded"
    assert data["codes"] == [nlm_watchdog.Code.CRASHED]
    assert "RuntimeError" in data["note"]
    # Exception type name only, never its message.
    assert "kaboom" not in data["note"]
    assert SYNTHETIC_EMAIL not in data["note"]


def test_main_reports_import_failure_as_degraded_without_crashing(tmp_path, monkeypatch):
    hb = tmp_path / "nlm-watchdog.json"
    monkeypatch.setattr(nlm_watchdog, "HEARTBEAT_PATH", hb)
    monkeypatch.setattr(nlm_watchdog, "AUTH_SENTINEL_IMPORT_ERROR", "ImportError")
    rc = nlm_watchdog.main([])
    assert rc == 1
    data = json.loads(hb.read_text())
    assert data["status"] == "degraded"
    assert data["codes"] == [nlm_watchdog.Code.IMPORT_FAILED]


def test_module_reload_with_auth_sentinel_blocked_actually_sends_telegram(tmp_path):
    """`sys.modules["auth_sentinel"] = None` makes the module's own import
    raise on reload, so the real except branch sets AUTH_SENTINEL_IMPORT_ERROR.
    `_run` is not patched: the fake tg_notify.py writes a marker file only when
    a real subprocess executes it."""
    import importlib

    hb = tmp_path / "nlm-watchdog.json"
    hb.write_text(json.dumps({"organ": "nlm-watchdog", "status": "ok", "codes": []}))
    marker = tmp_path / "tg-called.marker"
    fake_tg = tmp_path / "tg_notify.py"
    fake_tg.write_text(
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text('called')\n"
        "sys.exit(0)\n"
    )

    saved_auth_sentinel = sys.modules.get("auth_sentinel")
    sys.modules["auth_sentinel"] = None  # forces a genuine ImportError below
    try:
        mod = importlib.reload(nlm_watchdog)
        assert mod.AUTH_SENTINEL_IMPORT_ERROR is not None, (
            "auth_sentinel import did not actually fail — test setup is broken"
        )
        mod.HEARTBEAT_PATH = hb
        mod.TG_NOTIFY = fake_tg
        rc = mod.main([])
        data = json.loads(hb.read_text())
    finally:
        if saved_auth_sentinel is not None:
            sys.modules["auth_sentinel"] = saved_auth_sentinel
        else:
            sys.modules.pop("auth_sentinel", None)
        importlib.reload(nlm_watchdog)  # restore normal state for every other test

    assert rc != 0
    assert data["status"] == "degraded"
    assert data["codes"] == [nlm_watchdog.Code.IMPORT_FAILED]
    assert marker.exists(), "tg_notify.py was never actually executed"


def _inventory_now(notebooks):
    # main() uses the wall clock, so tests driving main() stamp real time.
    return _inventory(notebooks, generated_at=datetime.now(timezone.utc))


def test_main_heartbeat_write_failure_forces_nonzero_exit(tmp_path, monkeypatch):
    hb = tmp_path / "nlm-watchdog.json"
    monkeypatch.setattr(nlm_watchdog, "HEARTBEAT_PATH", hb)
    monkeypatch.setattr(nlm_watchdog, "live_login_probe", lambda *_a, **_kw: (0, REAL_SHAPE_OK_OUTPUT))
    monkeypatch.setattr(
        nlm_watchdog, "live_inventory_fetch",
        lambda *_a, **_kw: (0, _inventory_now([{"id": "x", "title": "NB-3", "source_count": 1}])),
    )
    monkeypatch.setattr(nlm_watchdog, "write_heartbeat", lambda *_a, **_kw: False)
    rc = nlm_watchdog.main([])
    # The verdict is ok, but it was not recorded.
    assert rc == 1


def test_main_dry_run_writes_no_heartbeat_and_no_telegram(tmp_path, monkeypatch):
    hb = tmp_path / "nlm-watchdog.json"
    monkeypatch.setattr(nlm_watchdog, "HEARTBEAT_PATH", hb)
    fake, marker = _install_fake_tg_notify(tmp_path)
    monkeypatch.setattr(nlm_watchdog, "TG_NOTIFY", fake)
    monkeypatch.setattr(nlm_watchdog, "live_login_probe", lambda *_a, **_kw: (0, REAL_SHAPE_OK_OUTPUT))
    monkeypatch.setattr(
        nlm_watchdog, "live_inventory_fetch",
        lambda *_a, **_kw: (0, _inventory_now([{"id": "x", "title": "NB-3", "source_count": 10}])),
    )
    rc = nlm_watchdog.main(["--dry-run"])
    assert rc == 0
    assert not hb.exists()
    assert not marker.exists()


def test_main_cap_warn_flag_flags_a_notebook_the_default_would_not(tmp_path, monkeypatch):
    hb = tmp_path / "nlm-watchdog.json"
    monkeypatch.setattr(nlm_watchdog, "HEARTBEAT_PATH", hb)
    monkeypatch.setattr(nlm_watchdog, "live_login_probe", lambda *_a, **_kw: (0, REAL_SHAPE_OK_OUTPUT))
    monkeypatch.setattr(
        nlm_watchdog, "live_inventory_fetch",
        lambda *_a, **_kw: (0, _inventory_now([{"id": "x", "title": "NB-PROBE-SANDBOX", "source_count": 433}])),
    )
    rc = nlm_watchdog.main(["--cap-warn", "400", "--no-heartbeat"])
    assert rc == 1  # 433 >= 400, degraded — the default 450 would have read this as ok
