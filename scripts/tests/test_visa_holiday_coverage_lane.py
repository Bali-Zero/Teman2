"""The holiday-coverage lane of `scripts/visa_freshness_sentinel.py`.

The backend answer is injected through `build_coverage_verdict(runner=...)`; the real probe and
the real decree table are exercised by the last test and by the backend suite.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
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


def test_real_probe_with_todays_data_puts_the_gap_in_november_2027_and_is_ok():
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "visa_freshness_sentinel.py"),
         "--coverage-only", "--dry-run", "--now", "2026-10-10T00:00:00Z"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out.startswith("HOLIDAY_COVERAGE OK first_gap=2027-11-")
