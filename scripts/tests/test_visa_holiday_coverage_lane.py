"""The holiday-coverage lane of `scripts/visa_freshness_sentinel.py`.

The backend answer is injected through `build_coverage_verdict(runner=...)`; the real probe and
the real decree table are exercised by the last test and by the backend suite.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import visa_freshness_sentinel as vfs  # noqa: E402
from scripts.tests.test_visa_freshness_sentinel import (  # noqa: E402
    _FAKE_GATEWAY_FAILING,
    _FAKE_LADDER_GATEWAY,
    DAY,
    T0,
    _board,
    _calls,
    _write_fake_gateway,
)

NOW = datetime.fromtimestamp(T0, tz=timezone.utc)


def _answer(outcome: str, days_left: int, gap: str = "2027-11-19") -> str:
    return json.dumps({
        "outcome": outcome, "today": "2026-10-10", "first_gap": gap, "days_left": days_left,
        "year_to_load": 2028, "product": "E23", "years_loaded": [2026, 2027],
    })


def _verdict(outcome: str, days_left: int, gap: str = "2027-11-19"):
    return vfs.build_coverage_verdict(NOW, runner=lambda cmd: _answer(outcome, days_left, gap))


def _cycle(verdict, tmp_path, gw, now_ts, dry_run=False):
    return vfs.run_alert_cycle(
        verdict, dry_run=dry_run, now_ts=now_ts,
        state_path=tmp_path / "coverage_state.json", gateway_path=gw,
    )


def test_ok_far_from_the_gap_sends_nothing(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    v = _verdict("OK", 405)
    assert v.outcome == vfs.OUTCOME_OK
    assert _cycle(v, tmp_path, gw, T0)["would_send"] is False
    assert _calls(tmp_path) == []


def test_warn_names_the_year_the_date_and_the_cure(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    v = _verdict("WARN", 30, "2026-11-09")
    assert v.outcome == vfs.OUTCOME_COVERAGE_WARN
    _cycle(v, tmp_path, gw, T0)
    (call,) = _calls(tmp_path)
    assert call[call.index("--tier") + 1] == "p0"
    text = call[-1]
    assert "Load the 2028 national holiday and cuti bersama decree into id_holidays before 2026-11-09" in text
    assert "start falling back to 'not available' on 2026-11-09" in text


def test_warn_persisting_re_alerts_every_day_not_muted_by_the_ladder(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    v = _verdict("WARN", 30)
    for day in range(5):
        _cycle(v, tmp_path, gw, T0 + day * DAY)
    assert len(_calls(tmp_path)) == 5


def test_stale_is_p0_and_opens_the_high_board_row(tmp_path, monkeypatch):
    esc = _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    v = _verdict("STALE", -3, "2026-10-07")
    assert v.outcome == vfs.OUTCOME_COVERAGE_STALE
    _cycle(v, tmp_path, gw, T0)
    assert "ALREADY falling back" in _calls(tmp_path)[0][-1]
    rows = [e for e in esc.read_all_escalations() if e.get("job") == vfs.COVERAGE_ESCALATION_JOB]
    assert rows and rows[0]["priority"] == "HIGH"


def test_a_failed_send_is_not_a_delivery_and_is_retried_next_tick(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    failing = _write_fake_gateway(tmp_path, _FAKE_GATEWAY_FAILING)
    v = _verdict("WARN", 30)
    first = _cycle(v, tmp_path, failing, T0)
    assert first["delivered"] is False
    state = json.loads((tmp_path / "coverage_state.json").read_text())
    assert "telegram_last_delivered_ts" not in state
    healthy = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    retry = _cycle(v, tmp_path, healthy, T0 + 3600)
    assert retry["reason"] == "retry-undelivered" and retry["delivered"] is True


def test_ok_after_a_warning_resolves_only_the_coverage_row(tmp_path, monkeypatch):
    esc = _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    esc.write_escalation({"job": vfs.ESCALATION_JOB, "priority": "HIGH", "outcome": "STALE"})
    _cycle(_verdict("WARN", 30), tmp_path, gw, T0)
    assert esc.is_job_open(vfs.COVERAGE_ESCALATION_JOB)
    _cycle(_verdict("OK", 405), tmp_path, gw, T0 + DAY)
    assert not esc.is_job_open(vfs.COVERAGE_ESCALATION_JOB)
    assert esc.is_job_open(vfs.ESCALATION_JOB)


def test_the_pack_lane_ok_does_not_resolve_the_coverage_row(tmp_path, monkeypatch):
    esc = _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    _cycle(_verdict("WARN", 30), tmp_path, gw, T0)
    pack_ok = vfs.classify_freshness([], NOW)
    vfs.run_alert_cycle(
        pack_ok, dry_run=False, now_ts=T0 + DAY, state_path=tmp_path / "pack_state.json",
        gateway_path=gw,
    )
    assert esc.is_job_open(vfs.COVERAGE_ESCALATION_JOB)


def test_the_lanes_never_share_a_dedup_key():
    assert vfs.dedup_key(_verdict("WARN", 30)).startswith("visa-holiday-coverage:")
    assert not vfs.dedup_key(_verdict("WARN", 30)).startswith("visa-freshness")


@pytest.mark.parametrize("bad", ["not json", "[]", json.dumps({"outcome": "???"})])
def test_a_probe_that_cannot_answer_is_cannot_verify_never_green(bad):
    v = vfs.build_coverage_verdict(NOW, runner=lambda cmd: bad)
    assert v.outcome == vfs.OUTCOME_CANNOT_VERIFY


def test_a_probe_that_raises_is_cannot_verify():
    def boom(cmd):
        raise OSError("no interpreter")

    assert vfs.build_coverage_verdict(NOW, runner=boom).outcome == vfs.OUTCOME_CANNOT_VERIFY


def test_real_probe_with_todays_data_puts_the_gap_in_the_last_loaded_year_and_is_ok():
    # Data-relative: the 2028 decree moves `years_loaded` and this expectation with it.
    probe = _real_probe("2026-10-10")
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "visa_freshness_sentinel.py"),
         "--coverage-only", "--dry-run", "--now", "2026-10-10T00:00:00Z"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out.startswith(f"HOLIDAY_COVERAGE OK first_gap={max(probe['years_loaded'])}-")


def test_visa_holiday_coverage_is_an_owner_routed_family_by_default(monkeypatch):
    monkeypatch.delenv("TG_OWNER_FAMILIES", raising=False)
    import importlib

    import tg_notify

    tg = importlib.reload(tg_notify)
    key = "visa-holiday-coverage:holiday_gap_warn:2028:s1:n0:a0"
    assert tg._owner_reserved(key)
    assert tg._owner_reserved("visa-holiday-coverage:cannot-verify")
    assert not tg._owner_reserved("visa-holiday-coverage-other-organ")
    assert tg._owner_reserved("visa-freshness:stale:25:s1:n0:a0")  # the sibling family is untouched


def _real_gateway_cycles(tmp_path, monkeypatch, days):
    """The sentinel's real send path into the REAL tg_notify.py subprocess (private spool and board,
    no Telegram credentials, dry-run so nothing leaves the process), so act-routing is decided by
    the gateway, not by a fake."""
    _board(tmp_path, monkeypatch)
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path / "spool"))
    monkeypatch.setenv("TG_BOARD_PATH", str(tmp_path / "gw_board.jsonl"))
    monkeypatch.setenv("TG_SECRETS_FILE", str(tmp_path / "no-secrets.env"))
    v = _verdict("WARN", 30)
    return [
        vfs.run_alert_cycle(
            v, dry_run=False, now_ts=T0 + d * DAY, state_path=tmp_path / "coverage_state.json"
        )
        for d in range(days)
    ]


def test_warn_reaches_the_gateways_owner_path_every_day_not_the_board(tmp_path, monkeypatch):
    monkeypatch.delenv("TG_OWNER_FAMILIES", raising=False)
    results = _real_gateway_cycles(tmp_path, monkeypatch, 3)
    assert [r["reason"] for r in results] == ["new-condition", "realert-due", "realert-due"]
    assert [r["gateway_verdict"] for r in results] == ["sent"] * 3
    assert not (tmp_path / "gw_board.jsonl").exists()
    state = json.loads((tmp_path / "coverage_state.json").read_text())
    assert state["delivered_streak"] == 3 and "route" not in state


def test_guilt_a_family_outside_the_owner_list_would_be_routed_to_the_board(tmp_path, monkeypatch):
    monkeypatch.setenv("TG_OWNER_FAMILIES", "some-other-family")
    results = _real_gateway_cycles(tmp_path, monkeypatch, 1)
    assert results[0]["gateway_verdict"] == "spooled"
    rows = [json.loads(x) for x in (tmp_path / "gw_board.jsonl").read_text().splitlines()]
    assert rows and rows[0]["type"] == "gateway_routed"


def test_the_probe_is_given_the_wita_day_the_result_page_anchors_on():
    seen = []

    def capture(cmd):
        seen.append(cmd[cmd.index("--today") + 1])
        return _answer("OK", 400)

    # 16:30Z is 00:30 WITA of the next day: the page already counts it as the next day.
    vfs.build_coverage_verdict(datetime(2027, 11, 18, 16, 30, tzinfo=timezone.utc), runner=capture)
    vfs.build_coverage_verdict(datetime(2027, 11, 18, 15, 59, tzinfo=timezone.utc), runner=capture)
    assert seen == ["2027-11-19", "2027-11-18"]


def test_at_the_wita_day_boundary_of_the_gap_the_lane_is_stale_like_the_page():
    # Real probe, real data: whatever D is, 16:30Z on D-1 is D in WITA and must read STALE.
    first = vfs.build_coverage_verdict(NOW)
    gap = datetime.fromisoformat(first.coverage["first_gap"]).date()
    eve = datetime(gap.year, gap.month, gap.day, 16, 30, tzinfo=timezone.utc) - timedelta(days=1)
    assert vfs.build_coverage_verdict(eve).outcome == vfs.OUTCOME_COVERAGE_STALE
    before = eve - timedelta(minutes=31)
    assert vfs.build_coverage_verdict(before).outcome == vfs.OUTCOME_COVERAGE_WARN


# --- L1: the STALE text keeps naming the day the gap began, not the day the clock reads ---


def _real_probe(today: str) -> dict:
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "visa_holiday_coverage_probe.py"), "--today", today],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def test_guilt_stale_text_after_the_gap_still_names_the_gap_day_not_today():
    gap = datetime.fromisoformat(_real_probe("2026-10-10")["first_gap"]).date()
    later = (gap + timedelta(days=45)).isoformat()
    cov = _real_probe(later)
    assert cov["outcome"] == "STALE" and cov["first_gap"] == gap.isoformat() != later
    verdict = vfs.build_coverage_verdict(NOW, runner=lambda cmd: json.dumps(cov))
    text = vfs.format_coverage_text(verdict)
    assert f"since {gap.isoformat()}" in text and f"before {gap.isoformat()}" in text
    assert later not in text


# --- L3: a probe that stays blind reaches the exit code, the heartbeat and the owner path ---


def _blind_runner(cmd):
    raise OSError("probe gone")


def _tick(tmp_path, gw, n, runner=_blind_runner, dry_run=False):
    now = datetime.fromtimestamp(T0 + n * vfs.CADENCE_S, tz=timezone.utc)
    verdict = vfs.apply_cannot_verify_streak(
        vfs.build_coverage_verdict(now, runner=runner), now.timestamp(),
        tmp_path / "coverage_state.json", dry_run,
    )
    return verdict, _cycle(verdict, tmp_path, gw, now.timestamp(), dry_run)


def test_n_is_a_day_of_ticks():
    assert vfs.COVERAGE_BLIND_TICKS == 4


def test_innocence_fewer_than_n_cannot_verifies_stay_digest_quiet(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    for n in range(vfs.COVERAGE_BLIND_TICKS - 1):
        verdict, _ = _tick(tmp_path, gw, n)
        assert verdict.outcome == vfs.OUTCOME_CANNOT_VERIFY
    assert all(call[call.index("--tier") + 1] == "digest" for call in _calls(tmp_path))


def test_guilt_n_in_a_row_escalates_p0_with_a_board_row_and_a_nonzero_rc(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    for n in range(vfs.COVERAGE_BLIND_TICKS):
        verdict, decision = _tick(tmp_path, gw, n)
    assert verdict.outcome == vfs.OUTCOME_COVERAGE_BLIND
    assert decision["would_send"] is True
    last = _calls(tmp_path)[-1]
    assert last[last.index("--tier") + 1] == "p0"
    assert "BLIND" in last[-1] and "4 ticks" in last[-1]
    assert vfs.COVERAGE_BLIND_RC == 4
    from scripts.sentinel_lib import escalations as esc

    assert esc.is_job_open(vfs.COVERAGE_ESCALATION_JOB)


def test_the_streak_survives_the_escalation_so_the_next_tick_is_still_blind(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    for n in range(vfs.COVERAGE_BLIND_TICKS + 2):
        verdict, _ = _tick(tmp_path, gw, n)
        assert n < vfs.COVERAGE_BLIND_TICKS - 1 or verdict.outcome == vfs.OUTCOME_COVERAGE_BLIND


def test_an_ok_resets_the_count_and_resolves_the_row(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    for n in range(vfs.COVERAGE_BLIND_TICKS):
        _tick(tmp_path, gw, n)
    ok, _ = _tick(tmp_path, gw, 10, runner=lambda cmd: _answer("OK", 400))
    assert ok.outcome == vfs.OUTCOME_OK
    from scripts.sentinel_lib import escalations as esc

    assert not esc.is_job_open(vfs.COVERAGE_ESCALATION_JOB)
    for n in range(11, 11 + vfs.COVERAGE_BLIND_TICKS - 1):
        verdict, _ = _tick(tmp_path, gw, n)
        assert verdict.outcome == vfs.OUTCOME_CANNOT_VERIFY


def test_a_warn_in_between_breaks_the_run(tmp_path, monkeypatch):
    _board(tmp_path, monkeypatch)
    gw = _write_fake_gateway(tmp_path, _FAKE_LADDER_GATEWAY)
    for n in range(vfs.COVERAGE_BLIND_TICKS - 1):
        _tick(tmp_path, gw, n)
    _tick(tmp_path, gw, 9, runner=lambda cmd: _answer("WARN", 30))
    verdict, _ = _tick(tmp_path, gw, 10)
    assert verdict.outcome == vfs.OUTCOME_CANNOT_VERIFY


def test_main_exits_4_for_a_blind_lane(tmp_path, monkeypatch):
    monkeypatch.setenv("VISA_HOLIDAY_COVERAGE_STATE", str(tmp_path / "cov.json"))
    monkeypatch.setenv("VISA_COVERAGE_PYTHON", str(tmp_path / "no-such-python"))
    rcs = [
        vfs.main(["--coverage-only", "--dry-run", "--now", "2026-10-10T00:00:00Z"])
        for _ in range(vfs.COVERAGE_BLIND_TICKS)
    ]
    assert rcs == [0] * vfs.COVERAGE_BLIND_TICKS  # dry-run never persists the streak
    monkeypatch.setenv("VISA_FRESHNESS_STATE", str(tmp_path / "pack.json"))
    state = {"cannot_verify_streak": vfs.COVERAGE_BLIND_TICKS - 1}
    (tmp_path / "cov.json").write_text(json.dumps(state))
    assert vfs.main(["--coverage-only", "--dry-run", "--now", "2026-10-10T00:00:00Z"]) == 4
