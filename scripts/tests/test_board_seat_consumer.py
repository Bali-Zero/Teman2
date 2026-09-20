"""The consumer must close what it can PROVE is over, and nothing else.

Every cure here is asserted from both sides — the row that must close AND the
row that must not (guilt and innocence, superscar #3). A drainer that only
proves it drains is indistinguishable from one that empties the board.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import board_seat_consumer as bsc  # noqa: E402
from sentinel_lib import escalations  # noqa: E402

MACHINE = "TestBox"
NOW = time.time()


def _routed(job: str, ts: float, machine: str = MACHINE) -> dict:
    return {
        "ts": ts, "type": "gateway_routed", "job": job, "priority": "NORMAL",
        "status": "pending", "error_summary": "boom", "context": "cron:x",
        "machine": machine, "_writer": "tg-gateway", "origin_tier": "p0",
        "cure_lane": {"owner": "seat", "note": "routed by tg_notify"},
    }


class World:
    """A board and a run-state dir of our own, with the two verbs every test needs."""

    def __init__(self, root: Path, board: Path) -> None:
        self.root, self.board = root, board

    def __truediv__(self, other: str) -> Path:
        return self.root / other

    def append(self, row: dict) -> None:
        with open(self.board, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def rows(self) -> list[dict]:
        return [json.loads(ln) for ln in self.board.read_text().splitlines() if ln.strip()]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """TG_BOARD_PATH is deliberately NOT used: it overrides the gateway's board
    for the whole process and has already turned 21 unrelated gateway tests red
    once. The library's own file map is what this consumer reads."""
    board = tmp_path / "escalations_pro.jsonl"
    monkeypatch.setattr(escalations, "_MACHINE_FILES", {"pro": board, "air": tmp_path / "air.jsonl"})
    monkeypatch.setattr(escalations, "_current_machine", lambda: "pro")
    monkeypatch.setenv("ESCALATIONS_USE_SQLITE", "false")
    monkeypatch.setenv("BOARD_CONSUMER_MACHINE", MACHINE)
    monkeypatch.setenv("BOARD_CONSUMER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("BOARD_CONSUMER_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("BOARD_CONSUMER_HEALER_PIDFILE", str(tmp_path / "healer.pid"))
    (tmp_path / "state").mkdir()

    return World(tmp_path, board)


def _run_state(world, job: str, status: str, ts: float, exit_code: int = 0) -> None:
    (world / "state" / f"{job}.last.json").write_text(
        json.dumps({"job": job, "ts": ts, "status": status, "exit_code": exit_code}), encoding="utf-8"
    )


# ------------------------------------------------------------------ selection
def test_only_seat_owned_routed_rows_are_picked_up(world):
    world.append(_routed("cron-fail:alpha", NOW))
    world.append({
        "ts": NOW, "type": "main_required_red", "job": "main-required-red:x",
        "priority": "HIGH", "status": "pending", "machine": MACHINE,
        "cure_lane": {"owner": "session", "note": "a human reads this"},
    })
    world.append({"ts": NOW, "type": "gateway_routed", "job": "no-lane:y",
                  "priority": "NORMAL", "status": "pending", "machine": MACHINE})

    picked = [r["job"] for r in bsc.open_seat_rows()]
    assert picked == ["cron-fail:alpha"], "owner=session and lane-less rows are not this consumer's"


def test_an_already_resolved_job_is_not_picked_up_again(world):
    world.append(_routed("cron-fail:alpha", NOW - 60))
    world.append({"ts": NOW, "job": "cron-fail:alpha", "status": "resolved", "resolved_at": NOW})
    assert bsc.open_seat_rows() == [], "the board is append-only: collapse per job before judging"


# ------------------------------------------------------------------ cron-fail
def test_a_cron_that_recovered_is_closed_with_its_proof(world):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW - 60)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert [r["job"] for r in report["resolved"]] == ["cron-fail:alpha"]
    assert "status=ok" in report["resolved"][0]["proof"]
    closing = [r for r in world.rows() if r.get("status") == "resolved"]
    assert len(closing) == 1 and closing[0]["job"] == "cron-fail:alpha", \
        "the resolution must carry the SAME job or no reader collapses the pair"


def test_a_cron_still_failing_is_left_open(world):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "failed", NOW - 60, exit_code=2)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert report["left"][0]["why"] == bsc.NOT_CURABLE
    assert not [r for r in world.rows() if r.get("status") == "resolved"]


def test_a_cron_whose_last_run_predates_the_alert_is_left_open(world):
    """An ok that is OLDER than the alarm is the run that preceded the failure."""
    world.append(_routed("cron-fail:alpha", NOW))
    _run_state(world, "alpha", "ok", NOW - 7200)

    assert bsc.consume(max_rows=10, dry_run=False)["resolved"] == []


def test_a_cron_with_no_run_state_file_is_left_open(world):
    world.append(_routed("cron-fail:wr2.draft_generator.job", NOW))
    report = bsc.consume(max_rows=10, dry_run=False)
    assert report["resolved"] == []
    assert "invisible to this probe" in report["left"][0]["detail"]


def test_the_family_is_matched_as_an_entity_not_as_a_substring(world):
    """`cron-failure:` and `xcron-fail:` both CONTAIN the family name."""
    world.append(_routed("cron-failure:alpha", NOW - 3600))
    world.append(_routed("xcron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert all("no cure registered" in item["detail"] for item in report["left"])


# ------------------------------------------------------------------ stale lock
def test_a_recycled_healer_pid_gets_its_pidfile_removed(world, monkeypatch):
    world.append(_routed("healer-pro:stale-lock", NOW - 3600))
    (world / "healer.pid").write_text("4242")
    monkeypatch.setattr(bsc, "_pid_is_a_live_healer", lambda pid: False)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert [r["job"] for r in report["resolved"]] == ["healer-pro:stale-lock"]
    assert not (world / "healer.pid").exists()


def test_a_live_healer_keeps_its_lock(world, monkeypatch):
    world.append(_routed("healer-pro:stale-lock", NOW - 3600))
    (world / "healer.pid").write_text("4242")
    monkeypatch.setattr(bsc, "_pid_is_a_live_healer", lambda pid: True)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert (world / "healer.pid").exists(), "removing it would let a second healer start beside it"


def test_an_undecidable_pid_refuses_to_cure(world, monkeypatch):
    world.append(_routed("healer-pro:stale-lock", NOW - 3600))
    (world / "healer.pid").write_text("4242")
    monkeypatch.setattr(bsc, "_pid_is_a_live_healer", lambda pid: None)

    assert bsc.consume(max_rows=10, dry_run=False)["resolved"] == []
    assert (world / "healer.pid").exists()


def test_a_healer_row_that_is_not_the_lock_condition_is_left_open(world):
    world.append(_routed("healer-pro:arsenal-seat-dead", NOW))
    assert bsc.consume(max_rows=10, dry_run=False)["resolved"] == []


# ------------------------------------------------------------------ boundaries
def test_a_row_from_another_machine_is_never_cured_here(world):
    world.append(_routed("cron-fail:alpha", NOW - 3600, machine="SomeOtherHost"))
    _run_state(world, "alpha", "ok", NOW)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert report["left"][0]["why"] == bsc.FOREIGN


def test_dry_run_mutates_neither_the_board_nor_the_filesystem(world, monkeypatch):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW)
    world.append(_routed("healer-pro:stale-lock", NOW - 3600))
    (world / "healer.pid").write_text("4242")
    monkeypatch.setattr(bsc, "_pid_is_a_live_healer", lambda pid: False)
    before = world.rows()

    report = bsc.consume(max_rows=10, dry_run=True)

    assert len(report["resolved"]) == 2
    assert world.rows() == before
    assert (world / "healer.pid").exists()


def test_the_cap_bounds_the_run_and_reports_what_it_skipped(world):
    for i in range(5):
        world.append(_routed(f"cron-fail:job{i}", NOW - 3600))
        _run_state(world, f"job{i}", "ok", NOW)

    report = bsc.consume(max_rows=2, dry_run=False)

    assert len(report["resolved"]) == 2
    assert report["skipped_by_cap"] == 3, "a silent truncation is superscar #2"


def test_the_kill_switch_stops_the_run(world, monkeypatch, capsys):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW)
    monkeypatch.setenv("BOARD_SEAT_CONSUMER_ENABLED", "false")

    assert bsc.main(["--json"]) == 0
    assert not [r for r in world.rows() if r.get("status") == "resolved"]


def test_a_broken_row_does_not_take_the_run_down(world, monkeypatch):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    monkeypatch.setattr(bsc, "consume", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad row")))
    assert bsc.main([]) == 0, "a launchd organ that dies stops draining and nobody notices"


# ---- the council's findings, each pinned by the case that motivated it -------
def test_a_job_name_that_is_a_path_never_becomes_one(world):
    """`cron-fail:<name>` becomes a filesystem path. The key arrives from ~204
    callers, so the name is validated instead of trusted."""
    (world / "state").mkdir(exist_ok=True)
    outside = world / "elsewhere.last.json"
    outside.write_text(json.dumps({"job": "x", "ts": NOW + 10, "status": "ok"}), encoding="utf-8")
    world.append(_routed("cron-fail:../elsewhere", NOW))

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert "refusing to build a path" in report["left"][0]["detail"]


def test_a_state_ts_that_is_not_epoch_seconds_is_refused(world):
    """ts_epoch reads a naive ISO string as UTC. In WITA that is 8h in the
    future — enough to close a row whose run PRECEDED the alarm."""
    world.append(_routed("cron-fail:alpha", NOW))
    (world / "state" / "alpha.last.json").write_text(
        json.dumps({"job": "alpha", "ts": "2026-09-21T12:00:00", "status": "ok"}), encoding="utf-8"
    )

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert "not epoch seconds" in report["left"][0]["detail"]


def test_a_pidfile_rewritten_between_the_probe_and_the_cure_is_left_alone(world, monkeypatch):
    """TOCTOU: a healer that starts after the liveness probe owns this lock."""
    world.append(_routed("healer-pro:stale-lock", NOW - 3600))
    pidfile = world / "healer.pid"
    pidfile.write_text("4242")

    def probe_then_a_healer_starts(pid):
        pidfile.write_text("9999")
        return False

    monkeypatch.setattr(bsc, "_pid_is_a_live_healer", probe_then_a_healer_starts)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert pidfile.exists() and pidfile.read_text() == "9999"


def test_a_row_a_peer_closed_first_is_not_claimed_as_this_run_s_work(world, monkeypatch):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW)
    monkeypatch.setattr(bsc, "mark_resolved", lambda job: 0)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert report["left"][0]["why"] == "already_closed_by_a_peer"


def test_the_healer_probe_reads_its_command_line_case_insensitively(monkeypatch):
    """A live healer re-exec'd through the trampoline carries HEALER_TRAMPOLINED."""
    monkeypatch.setattr(bsc.os, "kill", lambda pid, sig: None)

    class _Out:
        returncode = 0
        stdout = "ssh ... HEALER_TRAMPOLINED=1 bash /Users/nuzantara/scripts/run.sh"

    monkeypatch.setattr(bsc.subprocess, "run", lambda *a, **k: _Out())
    assert bsc._pid_is_a_live_healer(4242) is True


def test_uncurable_rows_do_not_starve_the_curable_ones_behind_them(world):
    """The oldest rows are the ones with no cure — they never leave the board.
    A cap applied before the filter spends itself on them forever."""
    for i in range(3):
        world.append(_routed(f"imigrasi-diff:{i}", NOW - 9000 + i))
    world.append(_routed("cron-fail:alpha", NOW - 100))
    _run_state(world, "alpha", "ok", NOW)

    report = bsc.consume(max_rows=1, dry_run=False)

    assert [r["job"] for r in report["resolved"]] == ["cron-fail:alpha"]
    assert report["attempted"] == 1 and report["skipped_by_cap"] == 0


def test_a_condition_that_re_fired_since_the_probe_is_not_closed(world, monkeypatch):
    """The probe proved the OLD alarm was over. A resolution written now would
    carry a newer ts and collapse the FRESH one into silence."""
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW - 60)
    real = bsc.cure_cron_fail

    def cure_then_it_fails_again(row):
        verdict = real(row)
        world.append(_routed("cron-fail:alpha", NOW + 30))
        return verdict

    monkeypatch.setitem(bsc.CURES, "cron-fail", lambda row, dry: cure_then_it_fails_again(row))

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert report["left"][0]["why"] == "re_fired_since_the_probe"
    assert not [r for r in world.rows() if r.get("status") == "resolved"]


def test_each_healer_family_probes_its_OWN_lock(world, monkeypatch, tmp_path):
    """healer-run.sh (Mini) and pro-healer.sh hold different pidfiles. One shared
    default reads 'already gone' on the machine that does not own that path."""
    monkeypatch.delenv("BOARD_CONSUMER_HEALER_PIDFILE", raising=False)
    mini_lock = tmp_path / "nuzantara-healer.pid"
    pro_lock = tmp_path / "nuzantara-pro-healer.pid"
    monkeypatch.setitem(bsc._HEALER_PIDFILES, "healer-mini", str(mini_lock))
    monkeypatch.setitem(bsc._HEALER_PIDFILES, "healer-pro", str(pro_lock))
    pro_lock.write_text("4242")  # Pro's healer IS stuck; Mini's lock does not exist
    monkeypatch.setattr(bsc, "_pid_is_a_live_healer", lambda pid: True)

    world.append(_routed("healer-pro:stale-lock", NOW - 3600))
    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == [], \
        "the row must be judged against PRO's lock, not against Mini's absent one"
    assert pro_lock.exists()


@pytest.mark.parametrize("bad_ts", ["not-a-number", True, None, ""])
def test_an_unreadable_alert_ts_is_not_a_recovery(world, bad_ts):
    """ts_epoch orders junk as 0.0 on purpose — a bad ts must hide a line's age,
    never the line. But 0.0 is smaller than every state ts, so without this the
    whole class of malformed rows reads as 'recovered'."""
    row = _routed("cron-fail:alpha", NOW)
    row["ts"] = bad_ts
    world.append(row)
    _run_state(world, "alpha", "ok", NOW)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert "nothing to compare against" in report["left"][0]["detail"]


def test_a_state_file_written_by_another_host_is_a_strangers_witness(world):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    (world / "state" / "alpha.last.json").write_text(
        json.dumps({"job": "alpha", "ts": NOW, "status": "ok", "host": "SomeOtherHost"}),
        encoding="utf-8",
    )

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert "not this host" in report["left"][0]["detail"]


def test_a_state_file_naming_another_job_is_a_strangers_witness(world):
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    (world / "state" / "alpha.last.json").write_text(
        json.dumps({"job": "beta", "ts": NOW, "status": "ok"}), encoding="utf-8"
    )

    assert bsc.consume(max_rows=10, dry_run=False)["resolved"] == []


def test_a_run_state_dated_in_the_future_is_a_clock_not_a_recovery(world):
    """It beats every alert ts there will ever be — it would close this row and
    each of its successors forever."""
    world.append(_routed("cron-fail:alpha", NOW))
    _run_state(world, "alpha", "ok", NOW + 86400)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert "in the future" in report["left"][0]["detail"]


def test_innocence_a_well_formed_witness_on_this_host_still_closes_the_row(world):
    """The four refusals above must fail for the WITNESS, not for the cure."""
    import socket as _socket
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    (world / "state" / "alpha.last.json").write_text(
        json.dumps({"job": "alpha", "ts": NOW - 60, "status": "ok",
                    "host": _socket.gethostname(), "exit_code": 0}),
        encoding="utf-8",
    )

    assert [r["job"] for r in bsc.consume(max_rows=10, dry_run=False)["resolved"]] == ["cron-fail:alpha"]


def test_a_job_still_pending_on_another_machine_is_not_closed_from_here(world):
    """A resolution is keyed on `job` alone and every reader collapses by job,
    so closing Pro's row would silence Mini's pending row of the same name."""
    world.append(_routed("cron-fail:fly-pg-backup", NOW - 3000, machine="MiniBox"))
    world.append(_routed("cron-fail:fly-pg-backup", NOW - 1800))
    _run_state(world, "fly-pg-backup", "ok", NOW)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert report["resolved"] == []
    assert any(i["why"] == "pending_on_another_machine" for i in report["left"])


def test_an_empty_but_successful_ps_is_undecidable_not_innocent(monkeypatch):
    monkeypatch.setattr(bsc.os, "kill", lambda pid, sig: None)

    class _Out:
        returncode = 0
        stdout = "   \n"

    monkeypatch.setattr(bsc.subprocess, "run", lambda *a, **k: _Out())
    assert bsc._pid_is_a_live_healer(4242) is None


def test_the_machine_name_is_normalised_the_way_the_gateway_writes_it(world, monkeypatch):
    """tg_notify stamps socket.gethostname().split(".")[0]. If this consumer
    compares against the unsplit name, a host that starts reporting
    `Nuzantara.local` turns every row foreign — hourly, green, closing nothing."""
    monkeypatch.setenv("BOARD_CONSUMER_MACHINE", f"{MACHINE}.local")
    world.append(_routed("cron-fail:alpha", NOW - 3600))
    _run_state(world, "alpha", "ok", NOW)

    report = bsc.consume(max_rows=10, dry_run=False)

    assert [r["job"] for r in report["resolved"]] == ["cron-fail:alpha"], \
        "the row was written by the same host — a domain suffix must not orphan it"
