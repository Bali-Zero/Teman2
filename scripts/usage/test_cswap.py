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
import re
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


def _write_machine_seat_map(tmp_path: Path) -> Path:
    """A by_machine block shaped like Air-M5's measured map: one seat (A3)
    reached through two profile dirs, one seat (A4) kept out of rotation."""
    for name in ("default", "acct2", "a1", "acct4", "flat-only"):
        (tmp_path / name).mkdir(exist_ok=True)
    data = {
        "claude_profiles": {str(tmp_path / "flat-only"): "AZ"},
        "by_machine": {
            "Air-M5": {
                "claude_profiles": {
                    str(tmp_path / "default"): "A3",
                    str(tmp_path / "acct2"): "A3",
                    str(tmp_path / "a1"): "A1",
                    str(tmp_path / "acct4"): "A4",
                },
                "auto_rotation_excluded": {"A4": "no role chain yet"},
            }
        },
    }
    p = tmp_path / "seat_map.json"
    p.write_text(json.dumps(data, indent=2) + "\n")
    return p


def test_load_seat_map_reads_this_machines_block(tmp_path):
    seat_map = cswap.load_seat_map(_write_machine_seat_map(tmp_path), machine="air-m5")
    assert seat_map["claude_profiles"][str(tmp_path / "a1")] == "A1"
    assert str(tmp_path / "flat-only") not in seat_map["claude_profiles"]


def test_load_seat_map_other_machine_keeps_the_flat_fallback(tmp_path):
    seat_map = cswap.load_seat_map(_write_machine_seat_map(tmp_path), machine="Nuzantara")
    assert seat_map["claude_profiles"] == {str(tmp_path / "flat-only"): "AZ"}


def test_collect_candidates_counts_one_seat_once_across_its_profile_dirs(tmp_path, monkeypatch):
    seat_map = cswap.load_seat_map(_write_machine_seat_map(tmp_path), machine="Air-M5")
    monkeypatch.setattr(cswap, "_collect_window", lambda pdir, since: {"total": 10})
    candidates = cswap.collect_candidates(seat_map, cswap._now(), exclude=set())
    by_seat = {c["seat"]: c for c in candidates}
    assert sorted(by_seat) == ["A1", "A3"]
    assert by_seat["A3"]["t5"] == 20 and by_seat["A1"]["t5"] == 10


def test_collect_candidates_never_offers_a_seat_held_out_of_rotation(tmp_path):
    seat_map = cswap.load_seat_map(_write_machine_seat_map(tmp_path), machine="Air-M5")
    seats = {c["seat"] for c in cswap.collect_candidates(seat_map, cswap._now(), exclude=set())}
    assert "A4" not in seats
    assert cswap.resolve_seat_dir(seat_map, "A4") == tmp_path / "acct4"


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


def test_collect_candidates_keeps_every_profile_dir_of_an_aggregated_seat(tmp_path, monkeypatch):
    seat_map = cswap.load_seat_map(_write_machine_seat_map(tmp_path), machine="Air-M5")
    monkeypatch.setattr(cswap, "_collect_window", lambda pdir, since: {"total": 10})
    a3 = next(c for c in cswap.collect_candidates(seat_map, cswap._now(), exclude=set()) if c["seat"] == "A3")
    assert a3["dirs"] == [str(tmp_path / "default"), str(tmp_path / "acct2")]


def test_choose_seat_recognises_the_current_seat_through_its_alias_dir():
    """Naga P2 on #7887: state on A3's SECOND profile dir, switched 5 min ago,
    A3 far over threshold — the 30-minute guard must still hold."""
    now = datetime(2026, 10, 5, 12, 0, tzinfo=cswap.WITA)
    candidates = [
        {"seat": "A3", "dir": "~/.claude", "dirs": ["~/.claude", "~/.claude-acct2"], "t5": 1000, "t7": 1000},
        {"seat": "A1", "dir": "~/.claude-a1", "dirs": ["~/.claude-a1"], "t5": 10, "t7": 10},
    ]
    state = {"active_dir": "~/.claude-acct2", "active_seat": "A3",
             "last_switch_ts": (now - timedelta(minutes=5)).isoformat()}
    assert cswap.choose_seat(candidates, state, now)["seat"] == "A3"


# ------------------------------------------------ unknown load (gate note on #7887)
# A counter collect_claude reports as "unknown" is not a zero: the window total
# is "unknown" (same poison rule as seat_usage_collector._sum_tok, either order)
# and a seat whose load is unknown is never the least-loaded one.


def _fake_window(monkeypatch, days):
    monkeypatch.setattr(cswap, "collect_claude",
                        lambda pdir, since: {"status": "partial", "days": days})


@pytest.mark.parametrize("days", [
    {"d1": {"in": 1, "cache_w": "unknown"}, "d2": {"in": 2, "cache_w": 4}},
    {"d1": {"in": 1, "cache_w": 4}, "d2": {"in": 2, "cache_w": "unknown"}},
])
def test_collect_window_unknown_counter_poisons_the_total_in_either_order(monkeypatch, days):
    _fake_window(monkeypatch, days)
    w = cswap._collect_window("~/x", cswap._now())
    assert w["cache_w"] == "unknown" and w["total"] == "unknown"
    assert w["in"] == 3 and w["out"] == 0, "absent counter = 0, known counters stay exact"


def test_collect_window_known_counters_still_sum_to_an_int(monkeypatch):
    _fake_window(monkeypatch, {"d1": {"in": 1, "out": 2}, "d2": {"in": 3}})
    w = cswap._collect_window("~/x", cswap._now())
    assert (w["in"], w["out"], w["total"]) == (4, 2, 6)


def test_fmt_tokens_never_raises_on_an_unknown_window():
    w = {"in": 1, "out": 0, "cache_r": 0, "cache_w": "unknown", "total": "unknown", "status": "partial"}
    assert "unknown" in cswap._fmt_tokens(w)


def test_choose_seat_never_treats_an_unknown_load_as_least_loaded():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", "unknown", "unknown"), _cand("A2", "/kaiser", 10**9, 10**9)]
    assert cswap.choose_seat(candidates, {}, now)["seat"] == "A2"
    assert cswap.choose_seat(list(reversed(candidates)), {}, now)["seat"] == "A2"


def test_choose_seat_unknown_7d_ranks_after_a_known_7d_on_a_5h_tie():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", 5, "unknown"), _cand("A2", "/kaiser", 5, 99)]
    assert cswap.choose_seat(candidates, {}, now)["seat"] == "A2"


def test_choose_seat_all_unknown_does_not_crash_and_keeps_the_current_seat():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("A1", "/a1", "unknown", 100), _cand("AZ", "/az", "unknown", 1)]
    assert cswap.choose_seat(candidates, {"active_dir": "/az"}, now)["seat"] == "AZ"
    # no state: no evidence to rank, so the choice is deterministic by seat id, not by 7d
    assert cswap.choose_seat(candidates, {}, now)["seat"] == "A1"
    assert cswap.choose_seat(list(reversed(candidates)), {}, now)["seat"] == "A1"


def test_choose_seat_unknown_current_is_dropped_even_inside_the_flip_flop_window():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", "unknown", "unknown"), _cand("A2", "/kaiser", 10, 10)]
    state = {"active_dir": "/az", "last_switch_ts": (now - timedelta(minutes=5)).isoformat()}
    assert cswap.choose_seat(candidates, state, now)["seat"] == "A2"


def test_choose_seat_naive_last_switch_stamp_never_crashes():
    aware_now = cswap._now()
    candidates = [_cand("AZ", "/az", 100, 1), _cand("A2", "/kaiser", 1, 1)]
    state = {"active_dir": "/az", "last_switch_ts": "2026-08-11T11:55:00"}
    assert cswap.choose_seat(candidates, state, aware_now)["seat"] in {"AZ", "A2"}


def test_choose_seat_current_with_unknown_load_is_not_kept_as_under_threshold():
    now = datetime(2026, 8, 11, 12, 0, 0)
    candidates = [_cand("AZ", "/az", "unknown", "unknown"), _cand("A2", "/kaiser", 10, 10)]
    state = {"active_dir": "/az", "last_switch_ts": (now - timedelta(hours=3)).isoformat()}
    assert cswap.choose_seat(candidates, state, now)["seat"] == "A2"


def test_collect_candidates_aggregated_seat_with_one_unknown_profile_is_unknown(tmp_path, monkeypatch):
    seat_map = json.loads(_write_seat_map(tmp_path).read_text())
    seat_map["claude_profiles"] = {str(tmp_path / "az"): "A3", str(tmp_path / "acct2"): "A3"}
    # per profile: (5h, 7d); the first profile has an unknown 5h window
    totals = iter([{"total": "unknown"}, {"total": 7}, {"total": 4}, {"total": 2}])
    monkeypatch.setattr(cswap, "_collect_window", lambda pdir, since: next(totals))
    (a3,) = cswap.collect_candidates(seat_map, cswap._now(), exclude=set())
    assert a3["t5"] == "unknown" and a3["t7"] == 9


# --------------------------------------------------------------- exec: the headless door
#
# These run the REAL scripts/with_seat.sh (registry overridden to find a fake
# `claude`), so what the fake records is what a real child would receive.

_REPO = Path(__file__).resolve().parents[2]
_FAKE_CLAUDE = """#!/bin/bash
log="$HOME/fake-claude"; mkdir -p "$log"; id="$$-$RANDOM"
env | cut -d= -f1 | sort > "$log/$id.env"
printf '%s\\n' "${CLAUDE_CONFIG_DIR:-<unset>}" > "$log/$id.dir"
if [ -e "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/FAIL" ]; then
  echo "Failed to authenticate: OAuth session expired and could not be refreshed"; exit 1
fi
case "$*" in *PONG*) echo PONG ;; *) echo ANSWER ;; esac
"""
_CREDENTIAL_NAME = re.compile(r"TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL|_PAT$")


@pytest.fixture
def door(tmp_path, monkeypatch):
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    (fake_bin / "claude").write_text(_FAKE_CLAUDE)
    (fake_bin / "claude").chmod(0o755)
    registry = json.loads((_REPO / "infra/llm-credentials/seat-env.json").read_text())
    registry["seats"]["claude-seat"]["exec_search_path"] = [str(fake_bin)]
    reg_path = tmp_path / "seat-env.json"
    reg_path.write_text(json.dumps(registry))
    reg_path.chmod(0o600)
    monkeypatch.setenv("WITH_SEAT_REGISTRY", str(reg_path))
    for d in (".claude", "a1", "kaiser", "acct4", "acct5"):
        (tmp_path / d).mkdir()
    seat_map = tmp_path / "seat_map.json"
    seat_map.write_text(json.dumps({"claude_profiles": {
        "~/.claude": "A3", "~/a1": "A1", "~/kaiser": "A2", "~/acct4": "A4", "~/acct5": "A5"}}))
    topology = tmp_path / "topology.json"
    topology.write_text(json.dumps({"accounts": {"anthropic": {"slots": {
        "A1": {"plan": "x"}, "A5": {"status": "retired"}}}}}))

    def run(seat, *opts):
        return cswap.main(["--seat-map", str(seat_map), "exec", "--topology", str(topology),
                           "--cwd", str(tmp_path), *opts, seat, "--", "claude", "-p", "review"])
    return run


def _calls(home: Path) -> list[tuple[str, list[str]]]:
    log = home / "fake-claude"
    return [((log / f"{p.stem}.dir").read_text().strip(), p.read_text().split())
            for p in sorted(log.glob("*.env"))] if log.is_dir() else []


def test_exec_refuses_a_retired_seat_before_any_call(door, tmp_path, capfd):
    assert door("A5") == cswap.REFUSED_RC
    assert "retired" in capfd.readouterr().err
    assert _calls(tmp_path) == []


def test_exec_refuses_a_silent_named_seat_and_never_falls_back(door, tmp_path, capfd):
    (tmp_path / "kaiser" / "FAIL").touch()
    assert door("A2") == cswap.REFUSED_RC
    out, err = capfd.readouterr()
    assert "REFUSED seat=A2" in err and "OAuth session expired" in err
    assert "ANSWER" not in out
    assert [d for d, _ in _calls(tmp_path)] == [str(tmp_path / "kaiser")]  # the PONG only


def test_exec_child_env_carries_no_credential(door, tmp_path, monkeypatch, capfd):
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN",
                 "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(name, "fixture-not-a-secret")
    # bash sources BASH_ENV before with_seat.sh's allowlist runs: it must never reach it.
    hook = tmp_path / "bash_env.sh"
    hook.write_text('export CLAUDE_CODE_OAUTH_TOKEN=fixture; touch "$HOME/bash_env_ran"\n')
    monkeypatch.setenv("BASH_ENV", str(hook))
    assert door("A1") == 0
    assert not (tmp_path / "bash_env_ran").exists()
    calls = _calls(tmp_path)
    assert len(calls) == 2  # PONG + the real call
    for config_dir, names in calls:
        assert config_dir == str(tmp_path / "a1")
        assert [n for n in names if _CREDENTIAL_NAME.search(n)] == []
        assert "CLAUDE_CONFIG_DIR" in names  # innocence: the seat's own name does pass


def test_exec_reports_the_seat_that_answered(door, capfd):
    assert door("A1") == 0
    out, err = capfd.readouterr()
    assert out.strip() == "ANSWER"
    assert "seat=A1 dir=~/a1 pong=ok" in err and "seat=A1 exit=0" in err


def test_exec_default_dir_runs_with_config_dir_unset(door, tmp_path):
    assert door("A3") == 0
    assert {d for d, _ in _calls(tmp_path)} == {"<unset>"}


def test_exec_auto_skips_silent_seats_loudly_and_reports_the_one_used(door, tmp_path, capfd):
    (tmp_path / ".claude" / "FAIL").touch()
    (tmp_path / "a1" / "FAIL").touch()
    assert door("auto") == 0
    out, err = capfd.readouterr()
    assert "REFUSED seat=A3" in err and "REFUSED seat=A1" in err
    assert "seat=A2 dir=~/kaiser pong=ok" in err and out.strip() == "ANSWER"
    assert str(tmp_path / "acct5") not in {d for d, _ in _calls(tmp_path)}  # retired never tried


def test_exec_auto_with_no_answering_seat_refuses(door, tmp_path, capfd):
    for d in (".claude", "a1", "kaiser", "acct4"):
        (tmp_path / d / "FAIL").touch()
    assert door("auto") == cswap.REFUSED_RC
    assert "no eligible seat answered" in capfd.readouterr().err


def test_exec_pong_must_be_the_answer_not_a_mention(door, tmp_path, capfd):
    fake = tmp_path / "fakebin" / "claude"
    fake.write_text(fake.read_text().replace("echo PONG", "echo 'Unable to return PONG'"))
    assert door("A1") == cswap.REFUSED_RC
    assert "PONG failed" in capfd.readouterr().err


def test_exec_accepts_only_seat_ids_of_this_machine(door, tmp_path):
    assert door("A9") == 2
    assert door(str(tmp_path / "kaiser")) == 2  # a literal dir would hide which seat ran
    assert _calls(tmp_path) == []
