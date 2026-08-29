"""Guilt AND innocence for scripts/wal_continuity_probe.py.

The probe exists because on 2026-08-09 WAL archiving was found disabled while every
existing signal stayed green. So the thing this suite has to prove is not that the probe
runs — it is that the probe can go RED, on every one of its declared conditions, through
the SAME entry point cron uses. `classify` being correct while `main()` never reaches it
is the exact shape of W116/W120: dead code on the only path it exists for.

Every test drives an explicit `--state-file` under tmp_path. The real state lives at
`~/.agent/decisions/state/` and a test that writes there mutates production (W96).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import wal_continuity_probe as probe  # noqa: E402

EXIT_OK = probe.EXIT_OK
EXIT_RED = probe.EXIT_RED
EXIT_BLIND = probe.EXIT_BLIND
EXIT_CANNOT_VERIFY = probe.EXIT_CANNOT_VERIFY

SEG = 16777216


def obs(**over) -> dict:
    """A healthy observation. logid 0, last archived segment 100, current segment 101."""
    base = {
        "observed_at": "2026-08-29T00:00:00+00:00",
        "archive_mode": "on",
        "archive_command": "wal-g wal-push %p",
        "archived_count": 1000,
        "last_archived_wal": "000000010000000000000064",
        "last_archived_time": "2026-08-29 00:00:00+00",
        "failed_count": 0,
        "last_failed_wal": "",
        "last_failed_time": None,
        "stats_reset": "2026-01-01 00:00:00+00",
        "current_wal_lsn": "0/65000000",
        "wal_segment_size": SEG,
        "in_recovery": False,
    }
    base.update(over)
    return base


def seg_name(segment: int, timeline: int = 1) -> str:
    """Absolute segment number -> WAL filename, at the 16 MiB default."""
    per = probe.segments_per_logid(SEG)
    return f"{timeline:08X}{segment // per:08X}{segment % per:08X}"


def lsn_at(segment: int) -> str:
    off = segment * SEG
    return f"{off >> 32:X}/{off & 0xFFFFFFFF:08X}"


# Captured BEFORE the autouse fixture silences it, so the two tests that examine the
# gateway invocation can still reach the real implementation.
_REAL_SEND_ALERT = probe.send_alert


@pytest.fixture(autouse=True)
def _no_real_telegram(monkeypatch):
    """No test may spawn the real gateway. Alerts are recorded, not sent.

    Returned list is available to any test that wants to assert on what was raised.
    """
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier, text)), True)[1],
    )
    return sent


_counter = {"n": 0}


def run_cli(tmp_path: Path, observation: dict | str, *extra, state: Path | None = None):
    """Drive the real CLI the way cron does, with the reader fed from a file.

    NOT --dry-run: the state write is part of what these tests exist to check, and a
    helper that quietly disabled it made five guilt tests pass for the wrong reason.
    """
    _counter["n"] += 1
    payload = tmp_path / f"obs-{_counter['n']}.json"
    payload.write_text(observation if isinstance(observation, str) else json.dumps(observation))
    state_file = state or (tmp_path / "state.json")
    rc = probe.main([
        "--from-json", str(payload),
        "--state-file", str(state_file),
        "--json", *extra,
    ])
    return rc, state_file


# ---------------------------------------------------------------------------
# Parsing primitives — a sequence check built on a wrong parser is decoration
# ---------------------------------------------------------------------------

def test_lsn_parses_two_hex_halves():
    assert probe.parse_lsn("0/65000000") == 0x65000000
    assert probe.parse_lsn("3/00000010") == (3 << 32) | 0x10


@pytest.mark.parametrize("bad", ["", "abc", "0-65000000", "zz/00", None, 7])
def test_lsn_refuses_nonsense_instead_of_guessing(bad):
    assert probe.parse_lsn(bad) is None


def test_wal_filename_splits_timeline_logid_segno():
    assert probe.parse_wal_filename("000000010000000200000064") == (1, 2, 0x64)


@pytest.mark.parametrize("bad", ["", "0001", "00000001000000020000006", "zzzzzzzzzzzzzzzzzzzzzzzz"])
def test_wal_filename_refuses_non_wal_strings(bad):
    assert probe.parse_wal_filename(bad) is None


def test_segment_index_is_monotone_across_the_logid_boundary():
    per = probe.segments_per_logid(SEG)
    assert per == 256
    last_of_logid0 = probe.wal_segment_index(seg_name(per - 1), SEG)
    first_of_logid1 = probe.wal_segment_index(seg_name(per), SEG)
    assert first_of_logid1 == last_of_logid0 + 1


def test_segment_index_ignores_the_timeline():
    assert probe.wal_segment_index(seg_name(100, timeline=1), SEG) == \
           probe.wal_segment_index(seg_name(100, timeline=9), SEG)


# ---------------------------------------------------------------------------
# INNOCENCE — the probe must not cry wolf on a healthy or merely quiet server
# ---------------------------------------------------------------------------

def test_innocence_healthy_advance_is_green(tmp_path):
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    prev = json.loads(state.read_text())["previous"]
    rc2, _ = run_cli(tmp_path, obs(observed_at="2026-08-29T06:00:00+00:00",
                                   archived_count=1010,
                                   last_archived_wal=seg_name(110),
                                   current_wal_lsn=lsn_at(111)), state=state)
    assert rc2 == EXIT_OK
    assert prev["archived_count"] == 1000


def test_innocence_a_quiet_database_archives_nothing_and_stays_green(tmp_path):
    """Archiving happens on segment SWITCH. No writes, no switch, no archive — healthy.

    This is the innocence half of ARCHIVING_STALLED and it is why the stall check is
    not "archived_count did not move": that alone fires every night on an idle server.
    """
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(observed_at="2026-08-29T06:00:00+00:00"), state=state)
    assert rc2 == EXIT_OK


def test_innocence_first_run_on_a_healthy_server_baselines_without_alarm(tmp_path):
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    assert json.loads(state.read_text())["last_verdict"] == probe.V_FIRST_RUN


def test_innocence_timeline_change_is_a_note_not_a_gap(tmp_path):
    """A failover renumbers the timeline. Sequence arithmetic is void, not violated."""
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(archived_count=1010,
                                   last_archived_wal=seg_name(110, timeline=2),
                                   current_wal_lsn=lsn_at(111)), state=state)
    assert rc2 == EXIT_OK


def test_innocence_stats_reset_voids_deltas_instead_of_reporting_a_stall(tmp_path):
    """A counter reset makes archived_count go BACKWARDS. That is not a fault."""
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(archived_count=3, failed_count=0,
                                   stats_reset="2026-08-29 05:00:00+00",
                                   current_wal_lsn=lsn_at(120),
                                   last_archived_wal=seg_name(119)), state=state)
    assert rc2 == EXIT_OK


# ---------------------------------------------------------------------------
# GUILT — one test per declared RED condition
# ---------------------------------------------------------------------------

def test_guilt_archive_mode_off_is_red_on_the_very_first_run(tmp_path):
    """THE 2026-08-09 SCAR: a legacy override turned archiving off and nothing was red.

    It must fire with no baseline, because on the day it is discovered there is none.
    """
    rc, _ = run_cli(tmp_path, obs(archive_mode="off"))
    assert rc == EXIT_RED


def test_guilt_archive_mode_on_with_an_empty_command_is_still_red(tmp_path):
    """`archive_mode=on` alone is a claim, not a shipment."""
    rc, _ = run_cli(tmp_path, obs(archive_command=""))
    assert rc == EXIT_RED
    v = probe.classify(None, probe.sanitize_observation(obs(archive_command="")))
    assert v.verdict == probe.V_ARCHIVING_DISABLED


def test_guilt_a_failure_newer_than_the_last_success_is_red(tmp_path):
    rc, _ = run_cli(tmp_path, obs(last_failed_time="2026-08-29 05:00:00+00",
                                  last_failed_wal=seg_name(101)))
    assert rc == EXIT_RED


def test_guilt_a_failure_with_nothing_ever_archived_is_red(tmp_path):
    rc, _ = run_cli(tmp_path, obs(last_archived_time=None, last_archived_wal="",
                                  archived_count=0,
                                  last_failed_time="2026-08-29 05:00:00+00",
                                  last_failed_wal=seg_name(1)))
    assert rc == EXIT_RED


def test_guilt_rising_failed_count_is_red(tmp_path):
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(failed_count=4,
                                   last_failed_time="2026-08-28 00:00:00+00"), state=state)
    assert rc2 == EXIT_RED


def test_guilt_stalled_archiver_under_write_pressure_is_red(tmp_path):
    """archived_count frozen while the database wrote 2 segments. The core signal."""
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(observed_at="2026-08-29T06:00:00+00:00",
                                   current_wal_lsn=lsn_at(103)), state=state)
    assert rc2 == EXIT_RED
    v = probe.classify(probe.sanitize_observation(obs()),
                       probe.sanitize_observation(obs(current_wal_lsn=lsn_at(103))))
    assert v.verdict == probe.V_ARCHIVING_STALLED


def test_stall_threshold_is_actually_compared_not_decorative(tmp_path):
    """One segment below the threshold: green. At the threshold: red.

    Pins that the comparison exists. A stall check that ignored write pressure would
    make the first half red; one that never compared would make the second half green.
    """
    prev = probe.sanitize_observation(obs())
    below = probe.classify(prev, probe.sanitize_observation(
        obs(current_wal_lsn=lsn_at(101 + probe.STALL_SEGMENTS - 1))))
    at = probe.classify(prev, probe.sanitize_observation(
        obs(current_wal_lsn=lsn_at(101 + probe.STALL_SEGMENTS))))
    assert below.exit_code == EXIT_OK
    assert at.verdict == probe.V_ARCHIVING_STALLED


def test_guilt_a_skipped_segment_is_red(tmp_path):
    """The filename ran 10 segments while the counter ran 2 — 8 segments never shipped.

    This is the hole that stops a PITR mid-recovery, and no count-only check sees it.
    """
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(archived_count=1002,
                                   last_archived_wal=seg_name(110),
                                   current_wal_lsn=lsn_at(111)), state=state)
    assert rc2 == EXIT_RED
    v = probe.classify(probe.sanitize_observation(obs()),
                       probe.sanitize_observation(obs(archived_count=1002,
                                                      last_archived_wal=seg_name(110),
                                                      current_wal_lsn=lsn_at(111))))
    assert v.verdict == probe.V_SEQUENCE_GAP


def test_guilt_a_far_behind_archiver_is_red_with_no_baseline(tmp_path):
    rc, _ = run_cli(tmp_path, obs(current_wal_lsn=lsn_at(100 + probe.MAX_LAG_SEGMENTS + 2)))
    assert rc == EXIT_RED


def test_guilt_every_declared_red_code_is_reachable():
    """No RED code may exist in the contract without a path that produces it.

    A verdict nobody can trigger is documentation pretending to be a guard.
    """
    prev = probe.sanitize_observation(obs())
    produced = set()
    for cur in (
        obs(archive_mode="off"),
        obs(last_failed_time="2026-08-29 05:00:00+00"),
        obs(failed_count=9),
        obs(current_wal_lsn=lsn_at(103)),
        obs(current_wal_lsn=lsn_at(100 + probe.MAX_LAG_SEGMENTS + 2)),
        obs(archived_count=1002, last_archived_wal=seg_name(110), current_wal_lsn=lsn_at(111)),
    ):
        v = probe.classify(prev, probe.sanitize_observation(cur))
        produced.update(f.code for f in v.findings)
    assert probe.RED_FINDINGS <= produced, f"unreachable RED codes: {probe.RED_FINDINGS - produced}"


def test_multiple_faults_are_all_reported_not_just_the_first():
    """An alert that stops at the first finding hides the second fault behind it."""
    v = probe.classify(probe.sanitize_observation(obs()),
                       probe.sanitize_observation(obs(archive_mode="off", failed_count=7)))
    codes = {f.code for f in v.findings}
    assert probe.V_ARCHIVING_DISABLED in codes and probe.V_FAILURES_ACCUMULATING in codes


# ---------------------------------------------------------------------------
# CANNOT_VERIFY and the blind guard — a probe that cannot see is never green
# ---------------------------------------------------------------------------

def test_an_unreadable_read_is_cannot_verify_never_ok(tmp_path):
    rc, state = run_cli(tmp_path, "not json at all")
    assert rc == EXIT_CANNOT_VERIFY
    assert rc != EXIT_OK


def test_cannot_verify_escalates_to_p0_after_the_declared_streak(tmp_path, monkeypatch):
    """A permanently blind probe must get LOUDER, not settle into a quiet digest."""
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(probe, "send_alert",
                        lambda text, condition, tier, dry_run=False: sent.append((condition, tier)) or True)
    state = tmp_path / "state.json"
    payload = tmp_path / "bad.json"
    payload.write_text("{{{")
    for _ in range(probe.CANNOT_VERIFY_P0_STREAK):
        rc = probe.main(["--from-json", str(payload), "--state-file", str(state)])
        assert rc == EXIT_CANNOT_VERIFY
    tiers = [t for _, t in sent]
    assert tiers[0] == "digest"
    assert tiers[-1] == "p0"
    assert json.loads(state.read_text())["cannot_verify_streak"] == probe.CANNOT_VERIFY_P0_STREAK


def test_a_successful_read_clears_the_cannot_verify_streak(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "send_alert", lambda *a, **k: True)
    state = tmp_path / "state.json"
    bad = tmp_path / "bad.json"
    bad.write_text("{{{")
    probe.main(["--from-json", str(bad), "--state-file", str(state)])
    good = tmp_path / "good.json"
    good.write_text(json.dumps(obs()))
    probe.main(["--from-json", str(good), "--state-file", str(state)])
    assert json.loads(state.read_text())["cannot_verify_streak"] == 0


def test_an_observation_with_no_archiver_fields_is_blind_not_clean(tmp_path, monkeypatch):
    """W84 green-but-dead: reading the wrong thing must not report the right answer."""
    monkeypatch.setattr(probe, "send_alert", lambda *a, **k: True)
    rc, _ = run_cli(tmp_path, {"observed_at": "2026-08-29T00:00:00+00:00", "hello": "world"})
    assert rc == EXIT_BLIND


def test_a_standby_answer_is_cannot_verify_not_a_verdict_about_the_primary(tmp_path):
    """5432 is a proxy. If it routed us to a replica, pg_stat_archiver describes the
    replica — a green here would be a statement about the wrong server."""
    rc, _ = run_cli(tmp_path, obs(in_recovery=True))
    assert rc == EXIT_CANNOT_VERIFY


# ---------------------------------------------------------------------------
# Alerting contract — through the gateway, by NAME, with no secret in flight
# ---------------------------------------------------------------------------

def test_alerts_go_through_the_tg_notify_gateway_and_name_no_destination(monkeypatch):
    captured: dict = {}

    class _P:
        returncode = 0
        stderr = "tg_notify: sent"

    def fake_run(argv, **kw):
        captured["argv"] = argv
        return _P()

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    assert _REAL_SEND_ALERT("body", "archiving_disabled", "p0") is True
    argv = captured["argv"]
    assert argv[1].endswith("tg_notify.py")
    assert "--tier" in argv and "p0" in argv
    joined = " ".join(argv)
    assert "api.telegram.org" not in joined
    assert "8847435604" not in joined  # no chat id may be minted here


def test_the_dedup_key_names_the_condition_and_carries_no_measurement(monkeypatch):
    keys: list[str] = []

    class _P:
        returncode = 0
        stderr = ""

    def fake_run(argv, **kw):
        keys.append(argv[argv.index("--dedup-key") + 1])
        return _P()

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    _REAL_SEND_ALERT("archived_count=1000", "archiving_stalled", "p0")
    _REAL_SEND_ALERT("archived_count=5321", "archiving_stalled", "p0")
    assert keys[0] == keys[1], "a measurement leaked into the key — dedup would never match"
    assert "archiving_stalled" in keys[0]


def test_the_probe_never_carries_the_archive_command_value(tmp_path):
    """archive_command routinely embeds credentials. Superscar #4."""
    secret = "s3://AKIAEXAMPLE:sup3rs3cret@bucket/%f"
    rc, state = run_cli(tmp_path, obs(archive_command=secret))
    assert rc == EXIT_OK
    body = state.read_text()
    assert secret not in body and "sup3rs3cret" not in body
    assert json.loads(body)["previous"]["archive_command_set"] is True
    msg = probe.format_message(
        probe.classify(None, probe.sanitize_observation(obs(archive_command=secret))),
        probe.sanitize_observation(obs(archive_command=secret)),
    )
    assert "sup3rs3cret" not in msg


def test_a_red_run_still_advances_the_baseline(tmp_path, monkeypatch):
    """Otherwise the next run compares against a frozen past and reports the same stall
    forever, long after it is fixed."""
    monkeypatch.setattr(probe, "send_alert", lambda *a, **k: True)
    state = tmp_path / "state.json"
    first = tmp_path / "a.json"
    first.write_text(json.dumps(obs()))
    probe.main(["--from-json", str(first), "--state-file", str(state)])
    second = tmp_path / "b.json"
    second.write_text(json.dumps(obs(current_wal_lsn=lsn_at(103))))
    assert probe.main(["--from-json", str(second), "--state-file", str(state)]) == EXIT_RED
    assert json.loads(state.read_text())["previous"]["current_wal_lsn"] == lsn_at(103)


def test_dry_run_writes_no_state_at_all(tmp_path):
    state = tmp_path / "state.json"
    run_cli(tmp_path, obs(), "--dry-run", state=state)
    assert not state.exists()


def test_the_default_state_path_is_read_at_call_time_so_tests_can_redirect(monkeypatch, tmp_path):
    monkeypatch.setenv("WAL_PROBE_STATE_FILE", str(tmp_path / "redirected.json"))
    assert probe.state_path() == tmp_path / "redirected.json"
    monkeypatch.delenv("WAL_PROBE_STATE_FILE")
    assert probe.state_path().name == "wal_continuity_probe.state.json"


# ---------------------------------------------------------------------------
# The selftest is part of the contract — the wrapper runs it as a smoke check
# ---------------------------------------------------------------------------

def test_selftest_passes_as_a_subprocess():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "wal_continuity_probe.py"), "--selftest"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST PASS" in proc.stdout


def test_the_query_reads_archiver_state_and_not_a_proxy():
    """The single most important line of the file: what it asks Postgres for.

    A timestamp on a backup object, or an exit code, would be a proxy. These are the
    facts themselves.
    """
    q = probe.ARCHIVER_QUERY
    for field in ("pg_stat_archiver", "archived_count", "last_archived_wal",
                  "last_failed_wal", "last_failed_time", "stats_reset",
                  "archive_mode", "wal_segment_size", "pg_is_in_recovery"):
        assert field in q, f"the probe stopped asking for {field}"
