"""Tests for scripts/nlm_watchdog.py — the M5 -> Pro cross-host NLM probe.

WHY THIS EXISTS (2026-09-25 ground report, extended by a Gear-3 council pass
on HEAD 603b4a105f — codex-gpt-5.6-sol, kimi-code/k3, tp1-qwen3.8-max, all
BLOCKING): nb_generate_inventory.py already computes `near_cap` per notebook
every day on Pro, but nb-curator-daily.sh's Telegram-trigger condition never
reads it, so a full notebook can sit undetected indefinitely. Separately,
auth_sentinel.py only ever probes M5's OWN nlm cookie and leaves a
network_error/TIMEOUT shape as silent UNKNOWN forever (found, not fixed
there). This watchdog closes both gaps from M5 — and the council pass below
found and forced fixes for a second layer of guilt this file did not
originally cover: a title-leak PII surface, a login classifier that read
"Authentication invalid" as OK, a non-atomic heartbeat, a status-only alert
gate that hid a reason CHANGE while already degraded, and a producer race on
Pro's non-atomically-written inventory file.

Contract (guilt + innocence, no real ssh/nlm anywhere in this file, no real
PII anywhere in this file — any email/account string below is the synthetic
`owner@example.test`, never the real address):
  - _display_name: PII boundary on notebook identification — round 2 (codex
    #1, BLOCKING) found the round-1 `^NB-...`-prefix gate was not a boundary
    at all (`NB-CLIENT-CASE Jane Doe` matched it and still leaked). No title
    is ever shown, curated-looking or not: only the notebook's own id8, or
    "unknown".
  - classify_login: GUILT on "Authentication invalid" (rc 0 — real CLIs exit 0
    on a status line) reading as DEAD, not ok, and on any unrecognized/
    timeout/ssh-failure shape reading as unknown; INNOCENCE on the real ok
    sentinel shape (measured on Pro 2026-09-25, reproduced here without the
    real account line).
  - evaluate_inventory_data: GUILT on a notebook at/above cap_warn, a stale
    generated_at, a naive/malformed generated_at (degrades, never crashes),
    and a future generated_at (clock skew); INNOCENCE when every notebook is
    below cap_warn and the timestamp is fresh and in the past.
  - _fetch_inventory_data / run_once: retries exactly once, 5s, on a
    producer-race truncated read, and only on that failure class — never on a
    hard ssh failure. No real sleep in tests (sleep_fn injected).
  - write_heartbeat: atomic (tmp + os.replace, no partial file ever visible
    under a concurrent read), carries `note`/`last_error` (the keys
    organism_stale_detector.py's `_sidecar_note()` actually reads — verified
    2026-09-25) and `codes` (the stable comparison key), and reports write
    failure via a boolean return rather than raising.
  - maybe_alert: fires on a status transition OR a reason-CODE-set change
    while status stays degraded — proven against a real fake tg_notify.py on
    disk (W114: a fake placed inside the boundary just confirms your own
    assumption).
  - main(): an auth_sentinel import failure, an unhandled probe crash, and a
    heartbeat write failure each still leave a heartbeat and a non-zero exit
    (G9 fail-visible) — and a crash reason never carries the exception
    message, only its type name.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import nlm_watchdog  # noqa: E402


NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
SYNTHETIC_EMAIL = "owner@example.test"

# The real `nlm login --check` success shape (measured on Pro, read-only,
# 2026-09-25) — reproduced structurally with the account line synthesized.
# NEVER the real address: this string is asserted NOT to leak, and if a real
# one were pasted here that assertion would be worthless.
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


def _spy(calls, ret):
    def _fn(*a, **kw):
        calls.append((a, kw))
        return ret
    return _fn


# --- _display_name (PII boundary: id ONLY, never a title) -------------------
# Round-2 council finding (codex #1, BLOCKING): a `^NB-...` prefix gate is
# NOT a privacy boundary — `NB-CLIENT-CASE Jane Doe` matched it and leaked
# the client name verbatim. `_display_name` no longer looks at a title at
# all; it takes only `nb_id`.

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
    # The exact worst-direction failure the council found: rc 0, a status
    # line reading "invalid" — the OLD `"valid" in out.lower()` accepted this.
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
    # The real 2026-09-24 production string (auth_sentinel.py run.log).
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
    # The real output line 5 carries an account email — classify_login must
    # never surface `out` itself, only a fixed reason string, on ANY path.
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
    # Round-2 council finding (codex #1, BLOCKING): a `^NB-...`-prefixed
    # title is NOT a safe title — `NB-CLIENT-CASE Jane Doe` at cap must
    # surface only its id8, never "NB-CLIENT" nor "Jane" anywhere in the
    # output.
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
    # Round-2 council finding (kimi MINOR2, qwen MINOR1): `or 0` let a
    # non-numeric producer value pass through and raise TypeError at
    # `max()`/`>=`, which escaped run_once entirely. Must degrade with a
    # targeted reason, never crash.
    data = json.loads(_inventory([
        {"id": "aaa11111", "title": "NB-3", "source_count": "500"},
        {"id": "bbb22222", "title": "NB-8", "source_count": 10},
    ]))
    ok, reasons, ctx, codes = nlm_watchdog.evaluate_inventory_data(data, cap_warn=450, stale_hours=30, now=NOW)
    assert ok is False
    assert nlm_watchdog.Code.INVENTORY_MALFORMED in codes
    assert "non-numeric source_count" in " ".join(reasons)
    # The good notebook's count is still counted — one bad entry does not
    # discard the rest of the tick.
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
    # Round-2 council finding (codex #2, kimi MAJOR2, qwen NIT3): an
    # rc==0-but-empty first read is the SAME producer-truncation race as a
    # malformed non-empty read, and must be retried the same way.
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
    # Non-empty-but-unparseable on the first read still retries; if the
    # RETRY itself hits a hard ssh failure, that is MISSING, not MALFORMED
    # (MALFORMED is reserved for "Pro answered but the body still won't
    # parse", never for "Pro was unreachable on the second try").
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
        # organism_stale_detector.py's _sidecar_note() reads "note" or
        # "last_error" — NOT "detail". Both keys carry the same string.
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
    # W114: the real boundary is run_once -> write_heartbeat, not
    # classify_login in isolation. Inject a raw, email-bearing string into
    # login_fn itself and assert the FINAL heartbeat file on disk is clean.
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
    # The exact finding: login recovers but the inventory is now stale — same
    # STATUS (degraded), a genuinely different problem. Must not hide.
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
    # Round-2 council finding (codex #3, MAJOR): while notebook A stays
    # near-cap, notebook B newly crossing the threshold must still alert —
    # both only ever contribute the SAME `CAP_NEAR` code, so a codes-only
    # gate would silently swallow B joining.
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
    # Exception TYPE name only — the message (which could carry anything,
    # including a raw account string) must never cross the boundary.
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


def _inventory_now(notebooks):
    # main() always uses the REAL wall-clock time internally (no `now=`
    # override), so any test that drives main() end-to-end must stamp
    # `generated_at` off real time too, not the fixed `NOW` test constant —
    # otherwise the fixed constant can land far enough from real "now" to
    # trip the clock-skew/staleness check and contaminate an unrelated test.
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
    # verdict itself is OK, but the heartbeat could not be recorded — must
    # not report success.
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
