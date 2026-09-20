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
