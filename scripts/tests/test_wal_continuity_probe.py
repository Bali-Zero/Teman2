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
        "archive_library": "",
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


def test_a_stats_reset_is_CANNOT_VERIFY_not_a_stall_and_not_a_clean_run(tmp_path):
    """A counter reset makes archived_count go BACKWARDS. That is not a FAULT — and it
    is not a CLEAN RUN either, which is what this test used to assert.

    Two cross-family refuters (kimi-code/k3, codex gpt-5.6-sol) independently attacked
    the position this file previously encoded. Codex reproduced the scenario: baseline
    count=100/last=...064, a reset, then count=1/last=...067 while ...065 and ...066 are
    genuinely missing from the archive. Every delta check skips, the failure fields were
    wiped so ARCHIVER_FAILING sees nothing, the lag reads 1 — and the probe answered OK.
    The reset erased the evidence the judgment rests on, so the only honest verdict is
    "I could not verify": exit 4, and an alert. Three of these in a row page at p0,
    because a cluster whose archiver stats are reset before every run would otherwise
    re-baseline politely forever.
    """
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    rc2, _ = run_cli(tmp_path, obs(archived_count=3, failed_count=0,
                                   stats_reset="2026-08-29 05:00:00+00",
                                   current_wal_lsn=lsn_at(120),
                                   last_archived_wal=seg_name(119)), state=state)
    assert rc2 == EXIT_CANNOT_VERIFY, "a stats reset must never read as a clean run"


def test_a_stats_reset_that_repeats_escalates_from_digest_to_p0(tmp_path, monkeypatch):
    """The escalation is the half that makes the CANNOT_VERIFY verdict load-bearing.

    Without it, a permanently-resetting cluster answers "cannot verify" at digest tier
    every night forever and nobody is ever paged — quieter than the RED it is standing
    in for. A probe that cannot see must get LOUDER (superscar #2).
    """
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier)), True)[1])
    state = tmp_path / "state.json"
    for i in range(4):
        src = tmp_path / f"o{i}.json"
        src.write_text(json.dumps(obs(archived_count=3 + i,
                                      stats_reset=f"2026-08-2{i + 5} 05:00:00+00",
                                      current_wal_lsn=lsn_at(120 + i),
                                      last_archived_wal=seg_name(119 + i))))
        probe.main(["--from-json", str(src), "--state-file", str(state)])
    tiers = [tier for _, tier in sent]
    assert tiers[1:] == ["digest", "digest", "p0"], tiers


# ---------------------------------------------------------------------------
# GUILT — one test per declared RED condition
# ---------------------------------------------------------------------------

def test_guilt_archive_mode_off_is_red_on_the_very_first_run(tmp_path):
    """THE 2026-08-09 SCAR: a legacy override turned archiving off and nothing was red.

    It must fire with no baseline, because on the day it is discovered there is none.
    """
    rc, _ = run_cli(tmp_path, obs(archive_mode="off"))
    assert rc == EXIT_RED


def test_guilt_archive_mode_on_with_neither_command_nor_library_is_still_red(tmp_path):
    """`archive_mode=on` alone is a claim, not a shipment."""
    cur = obs(archive_command="", archive_library="")
    rc, _ = run_cli(tmp_path, cur)
    assert rc == EXIT_RED
    assert probe.classify(None, probe.sanitize_observation(cur)).verdict \
        == probe.V_ARCHIVING_DISABLED


def test_innocence_an_archive_module_with_an_empty_command_is_healthy(tmp_path):
    """PG15+ replaces archive_command with archive_library. A healthy server using a
    module reports an EMPTY archive_command, and demanding the command declares it
    disabled — a false RED on a configuration Fly's postgres-flex 17.x can be running.

    Found by a cross-family refuter (codex gpt-5.6-sol) before this shipped, which is
    why it is pinned here: the fix is one `and`, and one `and` is exactly the kind of
    thing a later simplification removes.
    """
    rc, _ = run_cli(tmp_path, obs(archive_command="", archive_library="basic_archive"))
    assert rc == EXIT_OK


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


def test_guilt_rising_failed_count_with_no_recovery_is_red(tmp_path):
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    cur = obs(failed_count=4, last_failed_time="2026-08-29 05:00:00+00")
    rc2, _ = run_cli(tmp_path, cur, state=state)
    assert rc2 == EXIT_RED
    v = probe.classify(probe.sanitize_observation(obs()), probe.sanitize_observation(cur))
    assert probe.V_FAILURES_ACCUMULATING in {f.code for f in v.findings}


def test_innocence_failures_that_recovered_are_a_note_not_a_page(tmp_path):
    """The archiver retries the same segment until it succeeds. A transient error
    followed by a success is not a break in continuity, and paging p0 on it is how a
    probe teaches people to ignore it. It must still be VISIBLE."""
    rc, state = run_cli(tmp_path, obs())
    assert rc == EXIT_OK
    cur = obs(failed_count=4, last_failed_time="2026-08-28 00:00:00+00")
    rc2, _ = run_cli(tmp_path, cur, state=state)
    assert rc2 == EXIT_OK
    v = probe.classify(probe.sanitize_observation(obs()), probe.sanitize_observation(cur))
    assert probe.V_FAILURES_RECOVERED in {n.code for n in v.notes}


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
        obs(failed_count=9, last_failed_time="2026-08-29 05:00:00+00"),
        obs(current_wal_lsn=lsn_at(103)),
        obs(current_wal_lsn=lsn_at(100 + probe.MAX_LAG_SEGMENTS + 2)),
        obs(archived_count=1002, last_archived_wal=seg_name(110), current_wal_lsn=lsn_at(111)),
        # NOTHING_ARCHIVED: archiving is ON, the counter is 0 and no segment was ever
        # named, while the database has written well past its first segment. This is the
        # post-reset shape of total archiving failure, and it is the code whose ABSENCE
        # from the severity ordering made `classify` raise StopIteration — a RED that
        # crashed the probe instead of paging. This row is why that cannot recur.
        obs(archived_count=0, last_archived_wal="", last_archived_time=None,
            stats_reset="2026-08-29 05:00:00+00", current_wal_lsn=lsn_at(160)),
    ):
        v = probe.classify(prev, probe.sanitize_observation(cur))
        produced.update(f.code for f in v.findings)
    assert probe.RED_FINDINGS <= produced, f"unreachable RED codes: {probe.RED_FINDINGS - produced}"


def test_multiple_faults_are_all_reported_not_just_the_first():
    """An alert that stops at the first finding hides the second fault behind it."""
    v = probe.classify(probe.sanitize_observation(obs()),
                       probe.sanitize_observation(
                           obs(archive_mode="off", failed_count=7,
                               last_failed_time="2026-08-29 05:00:00+00")))
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
    # Deliberately NOT spelled as a literal host string: `lint_tg_direct_senders.py`
    # is a textual over-match by design, so writing the URL here — even to assert its
    # ABSENCE — enrols this file in the direct-sender family it is checking against.
    # The literal-free form is also the stronger assertion: NO direct URL of any kind
    # may be handed to the gateway, not merely that one host.
    assert not any(str(a).startswith("http") for a in argv), \
        "a raw URL reached the gateway invocation — send through tg_notify, not directly"
    assert not any(str(a).isdigit() and len(str(a)) > 6 for a in argv), \
        "a chat-id-shaped literal was minted here; the gateway owns the destination"


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


# ---------------------------------------------------------------------------
# Findings the cross-family refuters raised before this shipped
# ---------------------------------------------------------------------------

def test_the_arithmetic_holds_at_a_non_default_wal_segment_size():
    """Everything is expressed in SEGMENTS, so a cluster at 64 MiB must work unchanged.

    The rest of the suite fixes 16 MiB, which is exactly how a hardcoded 256 would
    survive review. Here the same healthy and stalled scenarios are replayed with
    `wal_segment_size = 64 MiB`, where segments-per-logid is 64, not 256.
    """
    big = 64 * 1024 * 1024
    assert probe.segments_per_logid(big) == 64

    def name(segment: int, timeline: int = 1) -> str:
        return f"{timeline:08X}{segment // 64:08X}{segment % 64:08X}"

    def lsn(segment: int) -> str:
        off = segment * big
        return f"{off >> 32:X}/{off & 0xFFFFFFFF:08X}"

    prev = probe.sanitize_observation(obs(wal_segment_size=big,
                                          last_archived_wal=name(100),
                                          current_wal_lsn=lsn(101)))
    healthy = probe.sanitize_observation(obs(wal_segment_size=big, archived_count=1010,
                                             last_archived_wal=name(110),
                                             current_wal_lsn=lsn(111)))
    stalled = probe.sanitize_observation(obs(wal_segment_size=big,
                                             last_archived_wal=name(100),
                                             current_wal_lsn=lsn(103)))
    assert probe.classify(prev, healthy).exit_code == EXIT_OK
    assert probe.classify(prev, stalled).verdict == probe.V_ARCHIVING_STALLED


@pytest.mark.parametrize("voided,cur", [
    (probe.V_TIMELINE_CHANGED,
     dict(archived_count=1010, last_archived_wal="000000020000000000000064",
          current_wal_lsn="0/65000000")),
    (probe.V_STATS_RESET,
     dict(archived_count=3, stats_reset="2026-08-29 05:00:00+00",
          last_archived_wal="000000010000000000000077", current_wal_lsn="0/78000000")),
    (probe.V_NON_SEGMENT_LAST_ARCHIVED,
     dict(archived_count=1010,
          last_archived_wal="000000010000000000000064.00000028.backup",
          current_wal_lsn="0/65000000")),
])
def test_a_run_whose_checks_were_voided_still_says_so_out_loud(tmp_path, monkeypatch,
                                                              voided, cur):
    """A skipped check is not a passed check, and the difference must LEAVE the machine.

    Each of these is a legitimate event that voids real arithmetic — a failover, a
    counter reset, a `.backup` file sitting in last_archived_wal. Exiting 0 in silence
    is exactly how this organism goes blind while looking healthy (superscar #2), so
    they alert at digest tier. This test fails if any of them ever goes quiet.
    """
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier, text)), True)[1],
    )
    state = tmp_path / "state.json"
    first = tmp_path / "first.json"
    first.write_text(json.dumps(obs()))
    assert probe.main(["--from-json", str(first), "--state-file", str(state)]) == EXIT_OK
    sent.clear()

    second = tmp_path / "second.json"
    second.write_text(json.dumps(obs(**cur)))
    rc = probe.main(["--from-json", str(second), "--state-file", str(state)])
    # STATS_RESET erases the evidence rather than voiding one check, so it now exits
    # CANNOT_VERIFY; the others void a subordinate check and stay OK. Either way the
    # run must SPEAK — that is what this test is for.
    assert rc in (EXIT_OK, EXIT_CANNOT_VERIFY)
    assert sent, f"{voided} voided a check and said nothing"
    assert sent[-1][1] == "digest"
    assert voided in sent[-1][2]


def test_a_backup_or_history_filename_does_not_crash_or_falsely_accuse():
    """`last_archived_wal` is not always a segment: a base backup leaves
    `<seg>.<offset>.backup` and a timeline switch leaves `<tli>.history`. Both
    legitimately land there and bump archived_count. Neither may be read as a gap."""
    for weird in ("000000010000000000000064.00000028.backup", "00000002.history"):
        v = probe.classify(probe.sanitize_observation(obs()),
                           probe.sanitize_observation(obs(archived_count=1010,
                                                          last_archived_wal=weird)))
        assert v.exit_code == EXIT_OK
        assert probe.V_NON_SEGMENT_LAST_ARCHIVED in {n.code for n in v.notes}


def test_counters_falling_without_a_stats_reset_is_not_silent():
    """A crash can lose the stats file while `stats_reset` stays put. `count_delta` then
    goes negative, both delta checks skip on their own sign guards, and the run reports
    clean having compared nothing. Raised by the Kimi K3 refuter."""
    v = probe.classify(probe.sanitize_observation(obs()),
                       probe.sanitize_observation(obs(archived_count=7)))
    assert v.exit_code == EXIT_OK
    assert probe.V_COUNTERS_WENT_BACKWARDS in {n.code for n in v.notes}


@pytest.mark.parametrize("cur,then", [
    (dict(current_wal_lsn=""), dict()),                       # no WAL position now
    (dict(), dict(current_wal_lsn="")),                       # none on the older side
])
def test_a_stall_check_that_cannot_run_says_so(cur, then):
    """Unreadable WAL position = the PRIMARY continuity check did not run.

    That is a narrower code than CHECKS_UNRUNNABLE and it escalates, because nothing is
    left answering the question the probe exists to ask. Contrast
    `test_a_backup_or_history_filename_does_not_crash_or_falsely_accuse`: there the
    filename-based checks void but the stall check still reads LSN and counter, so the
    run stays OK. Escalating that one too would page p0 three nights after every base
    backup, and an alert that cries wolf on a routine event is how the real one gets
    ignored.
    """
    v = probe.classify(probe.sanitize_observation(obs(**then)),
                       probe.sanitize_observation(obs(**cur)))
    assert v.exit_code == EXIT_CANNOT_VERIFY
    assert probe.V_CONTINUITY_UNCHECKED in {n.code for n in v.notes}


def test_a_non_segment_on_the_OLDER_side_also_says_so():
    """The first fix only noted a non-segment on the CURRENT side. The same silence sat
    one run earlier, on the previous observation."""
    v = probe.classify(
        probe.sanitize_observation(obs(last_archived_wal="00000002.history")),
        probe.sanitize_observation(obs(archived_count=1010,
                                       last_archived_wal=seg_name(110),
                                       current_wal_lsn=lsn_at(111))))
    assert v.exit_code == EXIT_OK
    assert probe.V_CHECKS_UNRUNNABLE in {n.code for n in v.notes}


def test_every_voiding_note_is_reachable():
    """Same rule as the RED codes: a note nobody can trigger is decoration.

    FIRST_RUN used to be EXCLUDED here, on the reasoning that it is not a voided check
    but the absence of a baseline. That exclusion was the bug: with no baseline the three
    delta conditions cannot fire, so it voids half the contract. The exclusion clause
    that used to live in this docstring is what protected the false claim, which is why
    the fix had to land in the test as well as the code.
    """
    prev = probe.sanitize_observation(obs())
    produced = set()
    for v in (
        probe.classify(None, prev),                                        # FIRST_RUN
        probe.classify(None, prev, state_status=probe.STATE_UNREADABLE),   # BASELINE_LOST
        probe.classify(None, prev, first_run_count=3),                     # BASELINE_RECURRED
    ):
        produced.update(n.code for n in v.notes)
    for then, cur in (
        (prev, obs(last_archived_wal=seg_name(110, timeline=2), archived_count=1010)),
        (prev, obs(stats_reset="2026-08-29 05:00:00+00", archived_count=3)),
        (prev, obs(archived_count=7)),
        (prev, obs(last_archived_wal="00000002.history", archived_count=1010)),
        (probe.sanitize_observation(obs(current_wal_lsn="")), obs()),
        (prev, obs(failed_count=4, last_failed_time="2026-08-28 00:00:00+00")),
        # LSN_WENT_BACKWARDS: a PITR or a restart from an older checkpoint. `written`
        # goes negative, so the stall arithmetic cannot run against it. Declared as a
        # code but produced by NOTHING until a refuter pointed at it — a note nobody can
        # trigger is decoration, which is exactly what this test is here to forbid.
        (prev, obs(current_wal_lsn=lsn_at(40), archived_count=1000)),
        # CONTINUITY_UNCHECKED via malformed counters in a hand-edited baseline.
        ({**prev, "archived_count": "1000"}, obs()),
    ):
        v = probe.classify(then, probe.sanitize_observation(cur))
        produced.update(n.code for n in v.notes)
    missing = probe.VOIDING_NOTES - produced
    assert not missing, f"unreachable voiding notes: {missing}"


# ---------------------------------------------------------------------------
# Gate conditions C1-C4 (adjudication 2026-08-29). Each of these is a state the
# suite could NOT distinguish before: the gate mutated the code and every test
# stayed green. They exist so that never happens silently again.
# ---------------------------------------------------------------------------

def test_a_RED_verdict_is_actually_DELIVERED_not_merely_computed(tmp_path, monkeypatch):
    """C1 — THE condition this whole probe exists to enforce, applied to itself.

    The gate replaced the RED `send_alert(...)` call with `pass` and all 55 tests, the
    selftest and `check-wal-continuity-probe` stayed green: the suite asserted the right
    VERDICT and never once asserted that anybody was PAGED. That is the 2026-08-09
    disease one level in — a correct answer that reaches nobody — inside the artifact
    built to catch it.

    It matters more here than for most organs because the exit code is NOT the delivery:
    the plist invokes the wrapper directly rather than routing through
    `scripts/cron-runner.sh`, so nothing downstream turns a non-zero exit into a message.
    The p0 IS the delivery.
    """
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier, text)), True)[1],
    )
    state = tmp_path / "state.json"
    first = tmp_path / "a.json"
    first.write_text(json.dumps(obs()))
    probe.main(["--from-json", str(first), "--state-file", str(state)])
    sent.clear()

    red = tmp_path / "b.json"
    red.write_text(json.dumps(obs(archive_mode="off")))
    assert probe.main(["--from-json", str(red), "--state-file", str(state)]) == EXIT_RED
    assert sent, "a RED verdict was computed and NOBODY was paged"
    condition, tier, text = sent[-1]
    assert tier == "p0", f"a RED verdict went out at {tier!r}, not p0"
    assert condition == probe.V_ARCHIVING_DISABLED.lower()
    assert probe.V_ARCHIVING_DISABLED in text


@pytest.mark.parametrize("verdict_code,cur", [
    (probe.V_ARCHIVING_DISABLED, dict(archive_mode="off")),
    (probe.V_ARCHIVER_FAILING, dict(last_failed_time="2026-08-29 05:00:00+00")),
    (probe.V_FAILURES_ACCUMULATING, dict(failed_count=9, last_failed_time="2026-08-29 05:00:00+00")),
    (probe.V_ARCHIVING_STALLED, dict(current_wal_lsn=lsn_at(103))),
    (probe.V_ARCHIVING_LAGGING, dict(current_wal_lsn=lsn_at(100 + probe.MAX_LAG_SEGMENTS + 2))),
    (probe.V_SEQUENCE_GAP, dict(archived_count=1002, last_archived_wal=seg_name(110),
                                current_wal_lsn=lsn_at(111))),
])
def test_every_RED_condition_pages_at_p0(tmp_path, monkeypatch, verdict_code, cur):
    """C1, generalised: not just "a" RED delivers — EVERY declared RED delivers.

    Proving one path pages would leave the other five free to regress into a computed
    verdict nobody receives, which is exactly the shape of W107 (curing the one that bit).
    """
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier, text)), True)[1],
    )
    state = tmp_path / "state.json"
    first = tmp_path / "base.json"
    first.write_text(json.dumps(obs()))
    probe.main(["--from-json", str(first), "--state-file", str(state)])
    sent.clear()

    red = tmp_path / "red.json"
    red.write_text(json.dumps(obs(**cur)))
    assert probe.main(["--from-json", str(red), "--state-file", str(state)]) == EXIT_RED
    assert sent, f"{verdict_code} was computed and nobody was paged"
    assert sent[-1][1] == "p0"


def test_a_corrupted_baseline_is_BASELINE_LOST_not_a_quiet_first_run(tmp_path, monkeypatch):
    """C2 — `load_state` swallowed OSError and ValueError into `{}`, so a corrupted
    state file became FIRST_RUN, rc 0, in silence. With no baseline the three DELTA
    conditions cannot fire, so that is a mute switch on half the contract, disguised as
    a fresh start. Distinguishing MISSING from UNREADABLE is the whole fix."""
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier, text)), True)[1],
    )
    state = tmp_path / "state.json"
    state.write_text("this is not json")
    payload = tmp_path / "o.json"
    payload.write_text(json.dumps(obs()))
    assert probe.main(["--from-json", str(payload), "--state-file", str(state)]) == EXIT_OK
    assert sent, "a lost baseline said nothing"
    assert probe.V_BASELINE_LOST in sent[-1][2]
    assert probe.V_FIRST_RUN not in sent[-1][2]


def test_a_recurring_first_run_is_reported_because_one_is_legitimate_and_two_are_not(tmp_path):
    """C2, the adopted cure: a genuine first run happens exactly once. A baseline that
    keeps vanishing means the delta conditions have never had a chance to fire."""
    state = tmp_path / "state.json"
    payload = tmp_path / "o.json"
    payload.write_text(json.dumps(obs()))
    probe.main(["--from-json", str(payload), "--state-file", str(state)])
    saved = json.loads(state.read_text())
    assert saved["first_run_count"] == 1

    # Wipe only the baseline, the way a truncation or a hand-edit would.
    del saved["previous"]
    state.write_text(json.dumps(saved))
    probe.main(["--from-json", str(payload), "--state-file", str(state)])
    v = probe.classify(None, probe.sanitize_observation(obs()), first_run_count=1)
    assert v.verdict == probe.V_BASELINE_RECURRED


def test_first_run_itself_is_never_silent(tmp_path, monkeypatch):
    """C2 — the docstring claimed FIRST_RUN was "NOT red, but NEVER SILENT" while
    VOIDING_NOTES excluded it and a test enshrined the exclusion: a false statement about
    silence, protected by a test. A full DELETE of the state file resets first_run_count
    too, so this is the half of the cure that no wipe can suppress."""
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier, text)), True)[1],
    )
    payload = tmp_path / "o.json"
    payload.write_text(json.dumps(obs()))
    assert probe.main(["--from-json", str(payload),
                       "--state-file", str(tmp_path / "fresh.json")]) == EXIT_OK
    assert sent, "the very first run said nothing at all"
    assert sent[-1][1] == "digest"
    assert probe.V_FIRST_RUN in sent[-1][2]


def test_a_missing_wal_segment_size_is_not_reported_as_a_backup_file(tmp_path):
    """C3 — two causes reached one branch. `wal_segment_index` returns None both when
    the filename is a `.backup`/`.history` AND when `wal_segment_size` is missing, and
    the note named only the first. So a perfectly valid 24-hex segment was announced as
    "not a plain WAL segment (a .backup or .history file)". A diagnosis pointing away
    from the cause costs more than silence (W106)."""
    o = obs()
    del o["wal_segment_size"]
    v = probe.classify(None, probe.sanitize_observation(o))
    codes = {n.code for n in v.notes}
    assert probe.V_CHECKS_UNRUNNABLE in codes
    assert probe.V_NON_SEGMENT_LAST_ARCHIVED not in codes, \
        "a valid segment was called a .backup file"
    detail = next(n.detail for n in v.notes if n.code == probe.V_CHECKS_UNRUNNABLE)
    assert "wal_segment_size" in detail

    # INNOCENCE: a real non-segment must still get the non-segment note.
    v2 = probe.classify(None, probe.sanitize_observation(
        obs(last_archived_wal="00000002.history")))
    assert probe.V_NON_SEGMENT_LAST_ARCHIVED in {n.code for n in v2.notes}


def test_the_query_binds_each_json_key_to_its_real_column_not_just_the_key_name():
    """C4 — superscar #3 applied to my own test. The previous version asserted only that
    the words appeared SOMEWHERE in the query, so the gate swapped `a.archived_count` for
    a literal `0`, kept the JSON key, and the test stayed green: the probe would have
    read a constant forever and reported a permanent stall. Bind key to SOURCE, and
    assert on the pair."""
    # Per-LINE binding rather than an SQL parse: each key sits on its own line with the
    # expression it is bound to, and `COALESCE(a.x, '')` carries commas that a naive
    # field split would choke on.
    # A binding can SPAN LINES (`current_wal_lsn` is a three-line CASE), so continuation
    # lines are folded into the key that opened them. The first version of this parser
    # read only the opening line and would have reported the CASE as `CASE WHEN
    # pg_is_in_recovery()` — a parser that truncates its input judges something other
    # than what the query says.
    pairs: dict[str, str] = {}
    key: str | None = None
    for line in probe.ARCHIVER_QUERY.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if stripped.startswith("'"):
            key, _, rest = stripped[1:].partition("'")
            pairs[key] = rest.lstrip(",").strip()
        elif key is not None and stripped and not stripped.startswith(")"):
            pairs[key] += " " + stripped
    pairs = {k: v.strip().rstrip(",").strip() for k, v in pairs.items()}

    expected = {
        "archived_count": "a.archived_count",
        "last_archived_wal": "a.last_archived_wal",
        "last_archived_time": "a.last_archived_time",
        "failed_count": "a.failed_count",
        "last_failed_wal": "a.last_failed_wal",
        "last_failed_time": "a.last_failed_time",
        "stats_reset": "a.stats_reset",
    }
    # `column in expression` was still a SUBSTRING test, one layer in — a refuter
    # (codex gpt-5.6-sol) pointed out it accepts `0 * a.archived_count`, which contains
    # the column and reads a constant. The bound expression must be the column ITSELF,
    # allowing only the COALESCE default wrapper the query genuinely uses.
    for json_key, column in expected.items():
        assert json_key in pairs, f"the query stopped selecting {json_key}"
        expr = pairs[json_key]
        allowed = {column, f"COALESCE({column}, '')"}
        assert expr in allowed, \
            f"{json_key} is no longer read straight from {column} — it now reads {expr!r}"

    # The two remaining fields are not `a.<column>` reads, so they are pinned against
    # the exact expression instead of merely appearing SOMEWHERE in the query — the
    # same gap, and the two the previous version left as bare presence checks.
    assert pairs["in_recovery"] == "pg_is_in_recovery()"
    lsn_expr = pairs["current_wal_lsn"]
    assert "pg_current_wal_lsn()" in lsn_expr and "pg_last_wal_replay_lsn()" in lsn_expr, \
        "the WAL position must come from the server, and must pick the replay LSN in "\
        f"recovery rather than a primary-only call — it now reads {lsn_expr!r}"
    seg_expr = pairs["wal_segment_size"]
    assert "pg_settings" in seg_expr and "wal_segment_size" in seg_expr, \
        f"wal_segment_size must be read from pg_settings — it now reads {seg_expr!r}"
    assert "pg_stat_archiver" in probe.ARCHIVER_QUERY
    assert "archive_mode" in probe.ARCHIVER_QUERY
    assert "archive_library" in probe.ARCHIVER_QUERY


def test_the_machine_readable_verdict_reports_everything_the_message_does():
    """C5 — `--json` could under-report while `format_message` could not.

    Two survivors the gate measured and I re-measured at this head: truncating
    `as_dict()["findings"]` to its first element passed the whole suite, because
    `test_multiple_faults_are_all_reported_not_just_the_first` asserts on
    `verdict.findings` and never on the serialised form; and `Verdict.exit_code` was
    unpinned against the code the process actually returns, because `run()` returned a
    literal on that path. Nothing consumes `--json` today, which is exactly why it could
    drift unnoticed until something did.
    """
    v = probe.classify(probe.sanitize_observation(obs()),
                       probe.sanitize_observation(
                           obs(archive_mode="off", failed_count=7,
                               last_failed_time="2026-08-29 05:00:00+00")))
    assert len(v.findings) >= 2, "fixture no longer produces multiple findings"
    d = v.as_dict()
    assert [f["code"] for f in d["findings"]] == [f.code for f in v.findings]
    assert [n["code"] for n in d["notes"]] == [n.code for n in v.notes]
    assert d["exit_code"] == v.exit_code


@pytest.mark.parametrize("fixture,expected_rc", [
    (dict(archive_mode="off"), EXIT_RED),
    (dict(), EXIT_OK),
])
def test_the_json_exit_code_field_equals_the_code_the_process_returns(tmp_path,
                                                                     monkeypatch, capsys,
                                                                     fixture, expected_rc):
    """The other half of C5: the serialised `exit_code` and the process's real exit
    status are two different values, and only one of them is read by a human."""
    monkeypatch.setattr(probe, "send_alert",
                        lambda text, condition, tier, dry_run=False: True)
    src = tmp_path / "o.json"
    src.write_text(json.dumps(obs(**fixture)))
    rc = probe.main(["--from-json", str(src), "--state-file", str(tmp_path / "s.json"),
                     "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):])
    assert rc == expected_rc
    assert payload["exit_code"] == rc, (
        "the JSON says one thing and the process exits another — a consumer reading the "
        "payload and a wrapper reading $? would disagree about the same run")


def test_detection_latency_at_one_segment_per_run_is_pinned():
    """The blind window, turned into a number the code must keep.

    Archiving frozen, the database writing exactly ONE segment between runs. This test
    ITSELF carried a stale claim for one round: it drove `classify` without threading the
    carried pressure back in, so it measured a probe that had already been replaced and
    stayed green while pinning the OLD latency of 7. A test that does not feed the code
    what production feeds it measures a world that no longer exists — the same class of
    error as the prose it is here to police.

    With the deficit accumulating across runs, one segment per run crosses
    STALL_SEGMENTS on the second run. Pinned so a future tuning of either constant
    cannot move the latency in silence.
    """
    archived_at = 100
    prev = probe.sanitize_observation(obs(last_archived_wal=seg_name(archived_at),
                                          current_wal_lsn=lsn_at(archived_at + 1)))
    greens = 0
    carried = 0
    for run in range(1, 30):
        cur = probe.sanitize_observation(
            obs(last_archived_wal=seg_name(archived_at),          # nothing ever archived
                current_wal_lsn=lsn_at(archived_at + 1 + run)))   # one more segment/run
        v = probe.classify(prev, cur, carried_pressure=carried)
        carried = v.pressure
        if v.exit_code != EXIT_OK:
            break
        greens += 1
        prev = cur
    else:                                                          # pragma: no cover
        pytest.fail("archiving was frozen for 29 runs and the probe never went red")

    assert greens == 1, (
        f"detection latency changed: {greens} green runs before the first RED. The "
        "docstring's §WHAT THIS PROBE CANNOT SEE entry 4 states 1 green then RED on run 2 "
        "— update BOTH or neither."
    )
    assert v.verdict == probe.V_ARCHIVING_STALLED


# ---------------------------------------------------------------------------
# Council round 2026-08-29 (kimi-code/k3 + codex gpt-5.6-sol, refute-mandate).
# Every test below reproduces a state in which the probe answered GREEN, or
# crashed, while the WAL chain was broken. They are the seats' findings turned
# into guards, so the same false green cannot come back quietly.
# ---------------------------------------------------------------------------

def test_the_severity_ordering_covers_every_RED_code():
    """STRUCTURAL. The ordering and the membership set were two lists, and they diverged.

    `RED_FINDINGS` gained NOTHING_ARCHIVED; the ordering list inside `classify` did not.
    `next(c for c in order ...)` then raised StopIteration on exactly the total-archiving-
    failure state the code had just been taught to detect: no p0, no baseline advance, a
    traceback into a log nobody reads. Reproduced by codex gpt-5.6-sol before the fix.

    Deriving one from the other makes the divergence unrepresentable — this test pins
    that they stay derived, so a future edit cannot re-split them.
    """
    assert set(probe.RED_SEVERITY_ORDER) == set(probe.RED_FINDINGS)
    assert len(probe.RED_SEVERITY_ORDER) == len(probe.RED_FINDINGS), "duplicate in ordering"


def test_guilt_total_archiving_failure_after_a_stats_reset_is_RED_not_a_crash(tmp_path,
                                                                             monkeypatch):
    """THE 2026-08-09 SHAPE, one layer deeper: broken archiver AND wiped statistics.

    After `pg_stat_reset_shared('archiver')` there is no failure to see, no segment to
    index and no delta to compare. Every relative check is blind by construction. The
    only thing left that can still speak is an ABSOLUTE one: archiving is enabled, the
    database has written past its first segment, and the archiver has shipped nothing at
    all. Without it the cluster reports clean forever while holding no restorable chain.
    """
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        probe, "send_alert",
        lambda text, condition, tier, dry_run=False: (sent.append((condition, tier)), True)[1])
    state = tmp_path / "state.json"
    src = tmp_path / "o.json"
    src.write_text(json.dumps(obs(archived_count=0, last_archived_wal="",
                                  last_archived_time=None,
                                  stats_reset="2026-08-29 05:00:00+00",
                                  current_wal_lsn=lsn_at(160))))
    assert probe.main(["--from-json", str(src), "--state-file", str(state)]) == EXIT_RED
    assert sent and sent[-1] == ("nothing_archived", "p0")


def test_innocence_a_brand_new_cluster_inside_its_first_segment_is_not_accused():
    """The counterpart to the test above. A cluster that has genuinely not filled its
    first WAL segment has archived nothing for an innocent reason, and calling that a
    total archiving failure would be a false RED on every fresh install."""
    v = probe.classify(None, probe.sanitize_observation(
        obs(archived_count=0, last_archived_wal="", last_archived_time=None,
            current_wal_lsn="0/00A00000")))
    assert probe.V_NOTHING_ARCHIVED not in {f.code for f in v.findings}
    assert v.exit_code == EXIT_OK


def test_guilt_an_archiver_dead_on_a_quiet_database_goes_RED_instead_of_green_forever():
    """The widest hole codex gpt-5.6-sol found, and the one closest to the founding scar.

    The stall check compared a SINGLE interval and the baseline advanced every run, so
    write pressure never accumulated. An archiver that died on a database writing one
    segment a night never reached the 2-segment floor — not once, ever. It reported
    clean indefinitely while the chain was already broken.

    Carrying the shortfall in the state file is the fix: run after run the deficit adds
    up until it crosses the floor. This test walks that timeline one segment at a time
    and fails if the probe is still green when the deficit has passed it.
    """
    prev = probe.sanitize_observation(obs(archived_count=1000,
                                          last_archived_wal=seg_name(100),
                                          current_wal_lsn=lsn_at(101)))
    carried = 0
    verdicts = []
    for n in range(1, 5):
        cur = probe.sanitize_observation(obs(archived_count=1000,          # never moves
                                             last_archived_wal=seg_name(100),
                                             current_wal_lsn=lsn_at(101 + n)))
        v = probe.classify(prev, cur, carried_pressure=carried)
        carried = v.pressure
        verdicts.append(v)
        prev = cur                       # the baseline advances, as it does in production
    # One segment per run: green on the first (pressure 1 < floor 2), red from the
    # second onward. Before the accumulator, EVERY one of these was green.
    assert verdicts[0].exit_code == EXIT_OK
    assert all(v.verdict == probe.V_ARCHIVING_STALLED for v in verdicts[1:]), \
        [v.verdict for v in verdicts]


def test_guilt_an_archiver_shipping_half_of_what_is_written_is_caught():
    """`count_delta == 0` gated the whole stall check, so an archiver falling
    permanently behind — 2 segments written, 1 shipped, every single run — disarmed it
    by shipping ANYTHING. The deficit is what matters, not whether it is total."""
    prev = probe.sanitize_observation(obs(archived_count=1000,
                                          last_archived_wal=seg_name(100),
                                          current_wal_lsn=lsn_at(101)))
    carried = 0
    for n in range(1, 4):
        cur = probe.sanitize_observation(obs(archived_count=1000 + n,       # ships 1
                                             last_archived_wal=seg_name(100 + n),
                                             current_wal_lsn=lsn_at(101 + 2 * n)))  # writes 2
        v = probe.classify(prev, cur, carried_pressure=carried)
        carried = v.pressure
        prev = cur
    assert v.verdict == probe.V_ARCHIVING_STALLED, v.as_dict()


def test_innocence_an_archiver_that_catches_up_repays_its_deficit():
    """The accumulator must be repayable, or the first slow night poisons every night
    after it and the probe becomes a stuck alarm — which is a broken alarm."""
    prev = probe.sanitize_observation(obs(archived_count=1000,
                                          last_archived_wal=seg_name(100),
                                          current_wal_lsn=lsn_at(101)))
    behind = probe.sanitize_observation(obs(archived_count=1000,
                                            last_archived_wal=seg_name(100),
                                            current_wal_lsn=lsn_at(102)))
    v1 = probe.classify(prev, behind)
    assert v1.pressure == 1 and v1.exit_code == EXIT_OK
    caught_up = probe.sanitize_observation(obs(archived_count=1003,
                                               last_archived_wal=seg_name(103),
                                               current_wal_lsn=lsn_at(103)))
    v2 = probe.classify(behind, caught_up, carried_pressure=v1.pressure)
    assert v2.pressure == 0, "a caught-up archiver must clear the carried deficit"
    assert v2.exit_code == EXIT_OK


def test_a_RED_the_gateway_REFUSED_to_send_is_reported_as_unreported(tmp_path,
                                                                    monkeypatch):
    """C1 proved the CALL, not the DELIVERY — found independently by both council seats.

    `send_alert` already returns False when the gateway's own verdict says the message
    did not leave the machine, and `run` threw that answer away: the probe could compute
    a perfect p0, fail to deliver it, write a fresh baseline and exit 1 into a heartbeat
    nobody reads. Every C1 test monkeypatched `send_alert` with a lambda returning True
    unconditionally, so all of them passed against a gateway that refused everything.

    The probe cannot make Telegram work. It CAN refuse to pretend it was reported.
    """
    monkeypatch.setattr(probe, "send_alert",
                        lambda text, condition, tier, dry_run=False: False)
    state = tmp_path / "state.json"
    src = tmp_path / "o.json"
    src.write_text(json.dumps(obs(archive_mode="off")))
    rc = probe.main(["--from-json", str(src), "--state-file", str(state), "--json"])
    assert rc == EXIT_RED
    saved = json.loads(state.read_text())
    assert saved["last_alert_delivered"] is False


def test_a_malformed_state_file_does_not_crash_or_read_as_a_clean_run(tmp_path):
    """C2 validated the outer container only (codex gpt-5.6-sol).

    `{"previous": []}` parsed as STATE_OK and then `previous.get(...)` raised
    AttributeError; a `first_run_count` of `"three"` crashed `int()`. A reliability probe
    that dies because its OWN bookkeeping file is malformed is a probe that stopped
    watching, and launchd will happily report the failure as a single non-zero exit in a
    log nobody reads.
    """
    state = tmp_path / "state.json"
    src = tmp_path / "o.json"
    src.write_text(json.dumps(obs()))
    for broken in ('{"previous": [], "first_run_count": "three"}',
                   '{"previous": "nonsense", "cannot_verify_streak": null}',
                   '{"previous": {"archived_count": "1000"}}'):
        state.write_text(broken)
        rc = probe.main(["--from-json", str(src), "--state-file", str(state)])
        assert rc in (EXIT_OK, EXIT_CANNOT_VERIFY), broken


def test_a_WAL_position_that_moved_backwards_is_not_silent():
    """A PITR or a restart from an older checkpoint makes `written` negative. It failed
    the threshold comparison and produced NOTHING — green silence at the moment the WAL
    chain deserves the most attention. TIMELINE_CHANGED does not cover it: with a broken
    archiver `last_archived_wal` still carries the old timeline."""
    v = probe.classify(
        probe.sanitize_observation(obs(archived_count=1000, last_archived_wal=seg_name(199),
                                       current_wal_lsn=lsn_at(200))),
        probe.sanitize_observation(obs(archived_count=1000, last_archived_wal=seg_name(149),
                                       current_wal_lsn=lsn_at(150))))
    assert probe.V_LSN_WENT_BACKWARDS in {n.code for n in v.notes}
    # No RED fires here — the lag is one segment and the counter is intact — so without
    # the escalation this run would have exited 0 in silence.
    assert v.exit_code == EXIT_CANNOT_VERIFY, v.as_dict()


def test_an_unrecognised_last_archived_wal_is_not_described_as_a_backup_file():
    """The note asserted a benign cause — "a .backup or .history file" — for ANY value it
    could not parse, including a corrupt or truncated one. A message that explains away
    what it does not understand teaches its reader to dismiss it."""
    v = probe.classify(None, probe.sanitize_observation(obs(last_archived_wal="GARBAGE")))
    note = next(n for n in v.notes if n.code == probe.V_NON_SEGMENT_LAST_ARCHIVED)
    assert "cannot tell those apart" in note.detail


def test_every_send_alert_call_in_this_module_reads_its_verdict():
    """STRUCTURAL, and the reason it is structural: the blind-guard p0 discarded its
    delivery verdict for a whole round, cured only because C5 sent me back into that
    function. The RED path had been fixed; the identical site one branch over had not.
    That is W107 — curing one wrapper of five — and enumerating "the two I have seen"
    would have left the same question open for the next branch somebody adds.

    So the assertion is about the CLASS: every call to `send_alert` anywhere in the
    module must have its return value bound or tested. A bare expression-statement call
    is a delivery nobody read.
    """
    import ast
    src = Path(probe.__file__).read_text()
    tree = ast.parse(src)

    def is_send_alert(node: ast.AST) -> bool:
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "send_alert")

    discarded = [n.lineno for n in ast.walk(tree)
                 if isinstance(n, ast.Expr) and is_send_alert(n.value)]
    assert not discarded, (
        f"send_alert's verdict is discarded at line(s) {discarded} — the gateway can "
        "refuse a message and exit 0, so an unread return is an alert that may never "
        "have left the machine")

    total = sum(1 for n in ast.walk(tree) if is_send_alert(n))
    assert total >= 6, f"expected every alert path to be present, found {total} call(s)"


def test_cannot_verify_tier_escalates_exactly_at_the_streak_threshold():
    """Innocence and guilt for the helper that replaced a fragile local.

    A blind probe must get LOUDER, never quieter (superscar #2): below the threshold the
    alert is a digest, at and above it a p0. Both directions are pinned so a mutation
    that returns a constant dies here whichever constant it picks.
    """
    n = probe.CANNOT_VERIFY_P0_STREAK
    assert probe.cannot_verify_tier(n - 1) == "digest"
    assert probe.cannot_verify_tier(n) == "p0"
    assert probe.cannot_verify_tier(n + 5) == "p0"


def test_no_local_named_tier_is_bound_inside_run():
    """STRUCTURAL, and structural for the same reason as the send_alert class assertion.

    CodeQL flagged, at error severity, that `run()` bound `tier` in ONE arm of an
    if/else and read it from a LATER `elif`. It was safe only because both tested the
    same `verdict.exit_code` — a correlation nothing in the code stated. Widening that
    `elif` by one value turns the paging branch into an `UnboundLocalError`: the p0
    computed and never sent, which is this probe's whole defect class turned inward.

    Asserting "it is initialised before use" would pass again the moment someone adds a
    plain default, and a default silently picks a tier for a state nobody considered. So
    the assertion is that the LOCAL does not exist: the tier is derived at the point of
    use, from `streak`, which both arms bind.
    """
    import ast
    tree = ast.parse(Path(probe.__file__).read_text())
    run_fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "run")
    bound = sorted({
        t.lineno for node in ast.walk(run_fn)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(t, ast.Name) and t.id == "tier"
    })
    assert not bound, (
        f"`run()` binds a local named `tier` at line(s) {bound} — derive it from "
        "`streak` via cannot_verify_tier() at the point of use instead, so no branch "
        "can read a tier that another branch was supposed to have set")


def test_classify_advertises_no_clock_it_does_not_read():
    """`classify` had a `now: datetime | None = None` parameter it never read (CodeQL
    notice: "Variable now is not used"). Every temporal judgment it makes is relative —
    last-success against last-failure, this run's counters against the previous run's —
    so the seam governed nothing while looking like it governed everything, and the
    first test to pin time through it would have been green and proved nothing.

    That is W129 inverted: there a real injected clock was dropped by a caller, here the
    seam had nothing to govern. W129's cure is to WIRE the clock and prove it with two
    injected instants; the cure here is to DELETE it, because wiring would have to
    invent an absolute staleness rule that no RED path defines. This test fails if the
    parameter comes back without such a rule arriving with it.
    """
    import inspect
    params = inspect.signature(probe.classify).parameters
    assert "now" not in params, (
        "classify() takes a `now` parameter again. If an absolute staleness check now "
        "exists, wire it and pin it the W129 way — the SAME fixture at two injected "
        "instants yielding different verdicts, so no wall clock satisfies both. If it "
        "does not, the parameter is a seam that lies about what it controls.")
    # Over the AST, never over the source text: the first draft of this assertion was a
    # `"datetime.now" not in inspect.getsource(...)` substring test, and it failed on the
    # DOCSTRING above that explains why the clock was removed. A guard that a comment can
    # trip is superscar #3, and one that a comment can SATISFY is the same bug pointed
    # the other way — so this walks for a real Call node.
    import ast
    fn = next(n for n in ast.walk(ast.parse(Path(probe.__file__).read_text()))
              if isinstance(n, ast.FunctionDef) and n.name == "classify")
    clock_reads = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("now", "utcnow", "today")
    ]
    assert not clock_reads, (
        f"classify() reads the wall clock at line(s) {clock_reads} — a pure verdict "
        "function whose answer depends on when it runs cannot be pinned by any fixture")


# ---------------------------------------------------------------------------
# Dual observation source (2026-08-31): `scripts/pg.sh` is the PROVEN path (measured
# live: reaches the primary through Fly's HA-aware proxy, returned `in_recovery: false`).
# `fly ssh console` is kept as a fallback and was never deleted — `read_archiver_state`'s
# own docstring states the philosophy: probe both, in order, and LOG which one won.
# ---------------------------------------------------------------------------

def test_innocence_pg_sh_succeeding_means_fly_is_never_invoked(monkeypatch):
    """pg.sh is tried FIRST. When it already produced a good observation, calling out to
    `fly ssh console` too would be wasted latency and an unnecessary extra prod touch —
    the dispatcher must short-circuit, not probe every source unconditionally."""
    fly_calls: list[int] = []
    monkeypatch.setattr(probe, "read_archiver_state_via_pg_sh",
                        lambda timeout=60: (obs(), None))
    monkeypatch.setattr(probe, "read_archiver_state_via_fly",
                        lambda timeout=90: (fly_calls.append(1), (None, "must not run"))[1])
    result, reason = probe.read_archiver_state()
    assert reason is None
    assert result == obs()
    assert fly_calls == [], "fly ssh console ran even though pg.sh already succeeded"


def test_innocence_pg_sh_failing_falls_through_to_fly_and_names_the_winner(capsys, monkeypatch):
    """The 'add a source, never delete one' contract only means something if the
    fallback actually runs on failure, and if a human reading the log can tell WHICH
    source answered — the same requirement `read_archiver_state_via_fly` already
    enforces one level down, between its two credentials."""
    monkeypatch.setattr(probe, "read_archiver_state_via_pg_sh",
                        lambda timeout=60: (None, "pg.sh: proxy on :15432 down"))
    monkeypatch.setattr(probe, "read_archiver_state_via_fly",
                        lambda timeout=90: (obs(), None))
    result, reason = probe.read_archiver_state()
    assert reason is None
    assert result == obs()
    out = capsys.readouterr().out
    assert "fly ssh console" in out, "the log never named which source was accepted"


def test_guilt_both_sources_failing_is_cannot_verify_never_clean(tmp_path, monkeypatch):
    """pg.sh fails, falls through to fly, fly ALSO fails: the dispatcher must report
    failure — never fabricate an observation — and the failure reason must preserve
    BOTH sources' own words, not just the last one tried (a page that only shows the
    final attempt hides the first cause from whoever reads it).

    Exercised through the real CLI entry point `run()` uses when NOT --from-json, so
    this is the guilt case for the actual code path cron drives, not only the pure
    dispatcher in isolation.
    """
    monkeypatch.setattr(probe, "read_archiver_state_via_pg_sh",
                        lambda timeout=60: (None, "pg.sh: proxy on :15432 down"))
    monkeypatch.setattr(probe, "read_archiver_state_via_fly",
                        lambda timeout=90: (None, "fly: no credential produced a parseable row"))

    result, reason = probe.read_archiver_state()
    assert result is None
    assert reason is not None and "pg.sh" in reason and "fly" in reason
    assert "proxy on :15432 down" in reason
    assert "no credential produced a parseable row" in reason

    state = tmp_path / "state.json"
    rc = probe.main(["--dry-run", "--json", "--state-file", str(state)])
    assert rc == EXIT_CANNOT_VERIFY
    assert not state.exists(), "dry-run must still write no state, even on CANNOT_VERIFY"
