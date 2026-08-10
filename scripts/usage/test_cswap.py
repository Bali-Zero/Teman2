"""Tests for cswap.py — Claude-profile rotation.

W96 discipline: NOTHING here touches the real $HOME. Every test isolates
via `monkeypatch.setenv("HOME", str(tmp_path))` — `Path.home()` honors
`$HOME` on POSIX, and CLAUDE_CONFIG_DIR-style `os.path.expanduser("~/...")`
paths follow the same env var, so both the profile-dir resolution AND the
lock/state paths (`~/.config/cswap/...`) land under tmp_path automatically,
with no real dotfile ever read or written.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cswap  # noqa: E402


# --------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    yield tmp_path


def _write_seat_map(tmp_path: Path) -> Path:
    p = tmp_path / "seat_map.json"
    (tmp_path / "az").mkdir(exist_ok=True)
    (tmp_path / "kaiser").mkdir(exist_ok=True)
    (tmp_path / "acct2").mkdir(exist_ok=True)
    (tmp_path / "acct3").mkdir(exist_ok=True)
    (tmp_path / "zero-team").mkdir(exist_ok=True)
    data = {
        "_doc": "test seat map",
        "_status": "UNARMED_until_fingerprint",
        "claude_profiles": {
            str(tmp_path / "az"): "AZ",
            str(tmp_path / "kaiser"): "A2",
            str(tmp_path / "acct2"): "A1",
            str(tmp_path / "acct3"): "A3",
            str(tmp_path / "acct4-missing"): "orphan (no seat exists — verify and retire)",
            str(tmp_path / "zero-team"): "AZ-legacy-verify",
        },
    }
    p.write_text(json.dumps(data, indent=2) + "\n")
    return p


# --------------------------------------------------------------- (c) orphan/legacy exclusion


def test_is_eligible_excludes_orphan_and_legacy():
    assert cswap.is_eligible("A2") is True
    assert cswap.is_eligible("AZ") is True
    assert cswap.is_eligible("orphan (no seat exists — verify and retire)") is False
    assert cswap.is_eligible("AZ-legacy-verify") is False


def test_resolve_seat_dir_refuses_unknown_seat(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    seat_map = cswap.load_seat_map(seat_map_path)
    with pytest.raises(ValueError, match="unknown seat"):
        cswap.resolve_seat_dir(seat_map, "NOT-A-SEAT")


def test_resolve_seat_dir_refuses_orphan_by_token(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    seat_map = cswap.load_seat_map(seat_map_path)
    with pytest.raises(ValueError, match="excluded"):
        cswap.resolve_seat_dir(seat_map, "orphan (no seat exists — verify and retire)")


def test_resolve_seat_dir_refuses_orphan_by_literal_path_entity_not_token(tmp_path):
    """cicatrix-superscar.md family #3: the refusal must key on the resolved
    directory (entity), not just the seat-id string (form) — otherwise
    `cswap run ~/.claude-acct4` bypasses the exact same guard that
    `cswap run orphan` correctly blocks."""
    seat_map_path = _write_seat_map(tmp_path)
    seat_map = cswap.load_seat_map(seat_map_path)
    orphan_dir = str(tmp_path / "acct4-missing")
    (tmp_path / "acct4-missing").mkdir()  # make it exist, as a real bystander dir would
    with pytest.raises(ValueError, match="excluded seat"):
        cswap.resolve_seat_dir(seat_map, orphan_dir)


def test_collect_candidates_excludes_orphan_and_legacy(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    seat_map = cswap.load_seat_map(seat_map_path)
    now = cswap._now()
    candidates = cswap.collect_candidates(seat_map, now, exclude=set())
    seats = {c["seat"] for c in candidates}
    assert seats == {"AZ", "A2", "A1", "A3"}
    assert "orphan (no seat exists — verify and retire)" not in seats
    assert "AZ-legacy-verify" not in seats


def test_list_warns_but_does_not_crash_on_orphan(tmp_path, capsys):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_list(seat_map_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "WARN excluded seat=orphan" in out
    assert "WARN excluded seat=AZ-legacy-verify" in out


# --------------------------------------------------------------- (e) seat resolution A2 -> kaiser


def test_resolve_seat_dir_a2_maps_to_kaiser(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    seat_map = cswap.load_seat_map(seat_map_path)
    resolved = cswap.resolve_seat_dir(seat_map, "A2")
    assert resolved == (tmp_path / "kaiser").resolve() or resolved == tmp_path / "kaiser"


def test_resolve_seat_dir_falls_back_to_literal_directory(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    seat_map = cswap.load_seat_map(seat_map_path)
    literal = tmp_path / "some-other-real-dir"
    literal.mkdir()
    assert cswap.resolve_seat_dir(seat_map, str(literal)) == literal


# --------------------------------------------------------------- (b) hysteresis


def _cand(seat: str, dir_: str, t5: int, t7: int) -> dict:
    return {"seat": seat, "dir": dir_, "path": Path(dir_), "t5": t5, "t7": t7}


def test_choose_seat_keeps_current_when_under_threshold():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", 1000, 5000), _cand("A2", "/kaiser", 10, 50)]
    # AZ is current, at 1000 which is NOT >= 90% of max(1000)=1000... it IS
    # exactly the max here, so use a case where current is comfortably under.
    candidates = [_cand("AZ", "/az", 100, 500), _cand("A2", "/kaiser", 1000, 5000)]
    state = {"active_dir": "/az"}  # current = AZ, far under the max (A2=1000)
    chosen = cswap.choose_seat(candidates, state, now)
    assert chosen["seat"] == "AZ", "current seat under 90% of max must be KEPT even though A2 has higher usage than AZ (ranking would pick AZ anyway here, so also assert the inverse below)"


def test_choose_seat_keeps_current_under_threshold_even_when_a_lower_usage_candidate_exists():
    now = datetime(2026, 8, 11, 12, 0, 0)
    # current (AZ) at 500, max observed is A2 at 1000 -> 500 < 0.9*1000=900 -> KEEP.
    # A1 has LOWER usage (10) than AZ and would win a naive ranking.
    candidates = [_cand("AZ", "/az", 500, 500), _cand("A2", "/kaiser", 1000, 1000),
                  _cand("A1", "/acct2", 10, 10)]
    state = {"active_dir": "/az"}
    chosen = cswap.choose_seat(candidates, state, now)
    assert chosen["seat"] == "AZ", "hysteresis must keep the under-threshold current seat, not chase the globally-lowest candidate"


def test_choose_seat_flip_flop_guard_recent_switch_keeps_current_even_over_threshold():
    """Guilt case: current is AT/OVER the 90% threshold (so the primary
    keep-condition fails) but the last switch was <30min ago — the
    anti-flip-flop hysteresis must still keep it."""
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", 1000, 1000), _cand("A2", "/kaiser", 10, 10)]
    state = {"active_dir": "/az", "last_switch_ts": (now - timedelta(minutes=5)).isoformat()}
    chosen = cswap.choose_seat(candidates, state, now)
    assert chosen["seat"] == "AZ", "a switch 5 minutes ago must block another switch (flip-flop guard)"


def test_choose_seat_switches_when_over_threshold_and_switch_is_old():
    """Innocence case: current is over threshold AND the last switch was
    long ago (>30min) -> both keep-conditions fail -> must rotate to the
    least-loaded candidate."""
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", 1000, 1000), _cand("A2", "/kaiser", 10, 10)]
    state = {"active_dir": "/az", "last_switch_ts": (now - timedelta(hours=2)).isoformat()}
    chosen = cswap.choose_seat(candidates, state, now)
    assert chosen["seat"] == "A2", "over-threshold + stale switch must rotate to the least-loaded seat"


def test_choose_seat_no_prior_state_bootstraps_to_least_loaded():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", 1000, 1000), _cand("A2", "/kaiser", 10, 10)]
    chosen = cswap.choose_seat(candidates, {}, now)
    assert chosen["seat"] == "A2"


def test_choose_seat_ties_on_5h_break_on_7d():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", 100, 900), _cand("A2", "/kaiser", 100, 50)]
    chosen = cswap.choose_seat(candidates, {}, now)
    assert chosen["seat"] == "A2", "equal 5h consumption must tie-break on the lower 7d figure"


def test_choose_seat_raises_on_empty_candidates():
    with pytest.raises(ValueError):
        cswap.choose_seat([], {}, datetime(2026, 8, 11, 12, 0, 0))


# --------------------------------------------------------------- (a) anti-collision lock


def test_acquire_lock_second_call_fails_while_first_holds(tmp_path):
    lock_dir = tmp_path / "auto.lock"
    assert cswap.acquire_lock(lock_dir) is True
    # second acquirer, same process still "holding" (pid file = our own live pid)
    assert cswap.acquire_lock(lock_dir) is False, "guilt — a second acquirer must fail while the lock is held"


def test_acquire_lock_succeeds_after_release(tmp_path):
    lock_dir = tmp_path / "auto.lock"
    assert cswap.acquire_lock(lock_dir) is True
    cswap.release_lock(lock_dir)
    assert cswap.acquire_lock(lock_dir) is True, "innocence — a released lock must be acquirable again"
    cswap.release_lock(lock_dir)


def test_acquire_lock_reclaims_stale_dead_pid_lock(tmp_path):
    """Same discipline as scripts/tests/test_prepush_suite_lock.sh Case 3: a
    REAL pid, explicitly waited-for to completion, so it is GUARANTEED dead
    — never a magic number that merely looks plausible."""
    proc = subprocess.Popen(["true"])
    dead_pid = proc.pid
    proc.wait()

    lock_dir = tmp_path / "auto.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(str(dead_pid))

    assert cswap.acquire_lock(lock_dir) is True, "a dead-pid holder must be reclaimed, not honored"
    assert (lock_dir / "pid").read_text().strip() == str(os.getpid())


def test_acquire_lock_unreadable_pid_file_is_treated_as_stale(tmp_path):
    lock_dir = tmp_path / "auto.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text("not-a-number")
    assert cswap.acquire_lock(lock_dir) is True


def test_cmd_auto_exits_75_when_lock_held(tmp_path, monkeypatch):
    seat_map_path = _write_seat_map(tmp_path)
    lock_dir = cswap._lock_dir_path()
    assert cswap.acquire_lock(lock_dir) is True  # simulate another `auto` in flight
    try:
        rc = cswap.cmd_auto(seat_map_path, do_print=False, do_activate=False, exclude=[])
        assert rc == cswap.LOCK_TIMEOUT_RC == 75
    finally:
        cswap.release_lock(lock_dir)


def test_cmd_auto_proceeds_once_lock_is_free(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_auto(seat_map_path, do_print=False, do_activate=False, exclude=[])
    assert rc == 0
    # lock must be released afterwards, not leaked
    assert not cswap._lock_dir_path().exists()


def test_cmd_auto_with_exclude_removes_seat_from_ranking(tmp_path, capsys):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_auto(seat_map_path, do_print=False, do_activate=False,
                         exclude=["AZ", "A2", "A1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "seat=A3" in out


def test_cmd_auto_no_eligible_seats_returns_3(tmp_path):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_auto(seat_map_path, do_print=False, do_activate=False,
                         exclude=["AZ", "A2", "A1", "A3"])
    assert rc == 3


def test_cmd_auto_activate_writes_state_and_print_is_dir_only(tmp_path, capsys):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_auto(seat_map_path, do_print=True, do_activate=True, exclude=[])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(tmp_path / "az") or Path(out).is_dir()
    state = cswap.load_state(cswap._state_path())
    assert state["active_dir"] == out
    assert "last_switch_ts" in state


# --------------------------------------------------------------- (d) fingerprint redaction guard


def _fake_proc(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude", "auth", "status"], returncode=rc,
                                        stdout=stdout, stderr=stderr)


def test_fingerprint_one_parses_logged_in_json():
    runner = lambda _pdir: _fake_proc(stdout=json.dumps({  # noqa: E731
        "loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
        "email": "someone@example.com", "orgName": "Example Org", "subscriptionType": "max",
    }))
    result = cswap.fingerprint_one(Path("/whatever"), runner=runner)
    assert result["parse_status"] == "ok"
    assert "someone@example.com" in result["identity"]
    assert "max" in result["identity"]


def test_fingerprint_one_parses_logged_out_json():
    runner = lambda _pdir: _fake_proc(  # noqa: E731
        stdout=json.dumps({"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty"}),
        rc=1,
    )
    result = cswap.fingerprint_one(Path("/whatever"), runner=runner)
    assert result["parse_status"] == "ok"
    assert "not logged in" in result["identity"]


def test_fingerprint_one_never_writes_a_secret_shaped_raw_line(tmp_path):
    """(d) guilt case: unparseable output that CONTAINS a token-shaped value
    must be redacted, never written verbatim."""
    leaky = "warning: using cached ANTHROPIC_AUTH_TOKEN=sk-ant-abcdEFGH1234567890abcdEFGH before falling back"
    runner = lambda _pdir: _fake_proc(stdout=leaky, rc=0)  # noqa: E731
    result = cswap.fingerprint_one(Path("/whatever"), runner=runner)
    assert result["parse_status"] == "unparsed"
    assert "sk-ant" not in result["identity"]
    assert "REDACTED" in result["identity"]

    # end-to-end: run the real command and confirm the string never lands
    # in the seat_map.json bytes on disk either.
    seat_map_path = tmp_path / "seat_map.json"
    seat_map_path.write_text(json.dumps({
        "claude_profiles": {str(tmp_path): "AZ"},
    }))
    fp_path = tmp_path / "fingerprints.json"
    cswap.cmd_fingerprint(seat_map_path, fingerprints_path=fp_path, runner=runner)
    on_disk = seat_map_path.read_text()
    assert "sk-ant" not in on_disk


def test_fingerprint_one_innocence_plain_prose_line_is_not_redacted():
    """(d) innocence case: an ordinary short, non-secret-shaped line must
    pass through untouched — the redaction guard must not be so broad it
    eats every unparsed line."""
    runner = lambda _pdir: _fake_proc(stdout="claude: command not found")  # noqa: E731
    result = cswap.fingerprint_one(Path("/whatever"), runner=runner)
    assert result["identity"] == "claude: command not found"
    assert "REDACTED" not in result["identity"]


def test_write_json_local_preserves_literal_utf8(tmp_path):
    """Regression pin: json.dumps() defaults to ensure_ascii=True, which
    would \\u-escape any em-dash/§ an identity/orgName string carries.
    _write_json_local (used by both cmd_fingerprint and save_state) must
    round-trip UTF-8 literally instead."""
    path = tmp_path / "local.json"
    cswap._write_json_local(path, {"_doc": "profili — mappa §3.1"})
    raw = path.read_bytes()
    assert "—".encode() in raw
    assert "§".encode() in raw
    assert b"\\u2014" not in raw


def test_write_json_local_chmods_0600(tmp_path):
    path = tmp_path / "local.json"
    cswap._write_json_local(path, {"a": 1})
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_cmd_fingerprint_skips_missing_dirs_and_writes_local_only(tmp_path, capsys):
    az = tmp_path / "az"
    az.mkdir()
    seat_map_before = json.dumps({
        "_status": "mapping only — see local fingerprints",
        "claude_profiles": {
            str(az): "AZ",
            str(tmp_path / "nonexistent"): "A1",
        },
    })
    seat_map_path = tmp_path / "seat_map.json"
    seat_map_path.write_text(seat_map_before)
    fp_path = tmp_path / "fingerprints.json"
    runner = lambda _pdir: _fake_proc(  # noqa: E731
        stdout=json.dumps({"loggedIn": True, "email": "x@y.z", "subscriptionType": "max"}))
    rc = cswap.cmd_fingerprint(seat_map_path, fingerprints_path=fp_path, runner=runner)
    assert rc == 0
    out = capsys.readouterr().out
    assert "SKIP A1" in out

    # seat_map.json is untouched — cmd_fingerprint never writes to it.
    assert seat_map_path.read_text() == seat_map_before

    written = json.loads(fp_path.read_text())
    assert str(az) in written
    assert str(tmp_path / "nonexistent") not in written


def test_cmd_fingerprint_never_writes_identity_into_the_tracked_seat_map(tmp_path):
    """Team-lead ruling 2026-08-11: seat_map.json is tracked in the PUBLIC
    Bali-Zero/Teman2 repo — a real personal email must NEVER land there
    (same scar class as the committed-team-PINs incident). Guilt: the local
    fingerprints file legitimately carries the email. Innocence: the tracked
    seat_map.json stays byte-identical to before the run."""
    az = tmp_path / "az"
    az.mkdir()
    seat_map_before = json.dumps({"_doc": "mapping only", "claude_profiles": {str(az): "AZ"}})
    seat_map_path = tmp_path / "seat_map.json"
    seat_map_path.write_text(seat_map_before)
    fp_path = tmp_path / "fingerprints.json"
    real_email = "kaiser198719871987@gmail.com"
    runner = lambda _pdir: _fake_proc(  # noqa: E731
        stdout=json.dumps({"loggedIn": True, "email": real_email, "subscriptionType": "max"}))

    rc = cswap.cmd_fingerprint(seat_map_path, fingerprints_path=fp_path, runner=runner)
    assert rc == 0

    # guilt: the tracked seat_map.json must be byte-for-byte unchanged.
    assert seat_map_path.read_text() == seat_map_before
    assert real_email not in seat_map_path.read_text()

    # innocence: the LOCAL fingerprints file legitimately carries it, 0600.
    local_raw = fp_path.read_text()
    assert real_email in local_raw
    assert oct(fp_path.stat().st_mode & 0o777) == "0o600"


def test_cmd_list_reads_identity_from_local_fingerprints_not_seat_map(tmp_path, capsys):
    az = tmp_path / "az"
    az.mkdir()
    seat_map_path = tmp_path / "seat_map.json"
    seat_map_path.write_text(json.dumps({"claude_profiles": {str(az): "AZ"}}))
    fp_path = tmp_path / "fingerprints.json"
    fp_path.write_text(json.dumps({str(az): {"identity": "someone@example.com (max)"}}))

    rc = cswap.cmd_list(seat_map_path, fp_path)
    assert rc == 0
    assert "someone@example.com" in capsys.readouterr().out


# --------------------------------------------------------------- run wiring (no execvpe in tests)


def test_cmd_run_refuses_unknown_seat_without_execing(tmp_path, capsys):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_run(seat_map_path, "NOT-A-SEAT", [])
    assert rc == 2
    assert "unknown seat" in capsys.readouterr().err


def test_cmd_run_refuses_orphan_without_execing(tmp_path, capsys):
    seat_map_path = _write_seat_map(tmp_path)
    rc = cswap.cmd_run(seat_map_path, "orphan (no seat exists — verify and retire)", [])
    assert rc == 2
    assert "excluded" in capsys.readouterr().err


def test_strip_leading_separator():
    assert cswap._strip_leading_separator(["--", "claude", "-p", "x"]) == ["claude", "-p", "x"]
    assert cswap._strip_leading_separator(["claude"]) == ["claude"]
    assert cswap._strip_leading_separator([]) == []
