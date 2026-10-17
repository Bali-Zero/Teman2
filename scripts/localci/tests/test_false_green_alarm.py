"""Owner ruling 2026-10-17: with phase F armed a FALSE_GREEN raises an alarm and blocks nothing; READY (FALSE_GREEN 0) stays the entry exam
for the flip; the phase_f_halt file still halts. The cache carries ``phase_e_ready_ex_false_green`` and ``false_green_keys``."""
from __future__ import annotations

import json
import os

import pytest

from .test_hosted_aborted import WORKFLOW, incident
from .test_merger import REPO, mg, world  # noqa: F401 — `world` is a fixture
from .test_merger_phase_f import _halt, _spy_report, armed_by_cache, assert_nothing_merged, fw, write_ready  # noqa: F401 — `fw` is a fixture
from .test_merger_report import CTX, run_report
from .test_ready_cache import REAL_DUE, age_cache, refresh_on, cache

FG_CACHE = {"phase_e_ready": False, "phase_e_ready_ex_false_green": True, "false_green": 1, "false_green_keys": ["#9@aaaaaaaaaaaa"]}


@pytest.fixture
def board(tmp_path, monkeypatch):
    path = tmp_path / "escalations_pro.jsonl"
    monkeypatch.setenv(mg.ESCALATIONS_ENV, str(path))
    return path


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def alarms(w):
    return [r for r in w.journal() if r.get("kind") == "false_green_alarm"]


def fake_report(monkeypatch, keys, ex_fg=True):
    rep = {"phase_e_ready": not keys and ex_fg, "phase_e_ready_ex_false_green": ex_fg, "false_green_keys": keys,
           "window": {"compared_merges": 50, "compared_days": 5.0}, "counts": {"FALSE_GREEN": len(keys)}}
    monkeypatch.setattr(mg, "report", lambda *a, **kw: (0, rep))


# ------------------------------------------------------------------ the read: what is an alarm and what still refuses
def test_phase_f_a_false_green_only_cache_lets_the_merge_through(fw):
    write_ready(fw.state, **FG_CACHE)
    assert fw.tick() == 0
    assert armed_by_cache(fw.wm()["phase_f"]) and fw.kinds()[-1] == "pushed"


def test_before_the_flip_a_false_green_cache_is_still_the_refusal(fw, monkeypatch):
    write_ready(fw.state, **FG_CACHE)
    monkeypatch.delenv(mg.PHASE_F_ENV)
    assert mg.read_ready(fw.state)[0] == "READY false (cache)"
    assert fw.tick() == 0
    assert_nothing_merged(fw, f"{mg.PHASE_F_ENV} unset")


def test_the_halt_file_still_halts_over_a_false_green_only_cache(fw):
    write_ready(fw.state, **FG_CACHE)
    _halt(fw)
    assert fw.tick() == 0
    assert_nothing_merged(fw, f"{mg.HALT_FILE} present")


@pytest.mark.parametrize("over", [{"phase_e_ready_ex_false_green": False}, {"phase_e_ready_ex_false_green": "yes"},
                                  {"phase_e_ready_ex_false_green": None}, {"refused": "CompareError: boom"}, {"computed_at": 1.0}],
                         ids=["other-term-false", "not-a-bool", "legacy-cache", "unreadable", "stale"])
def test_any_other_false_term_still_refuses_with_a_false_green_cache(fw, over):
    write_ready(fw.state, **{**FG_CACHE, **over})
    reason, _ = mg.read_ready(fw.state)
    assert reason and reason.startswith(("READY false (cache)", "READY unreadable", "READY stale"))
    assert fw.tick() == 0
    assert_nothing_merged(fw)


# ------------------------------------------------------------------ the alarm: once per new key, escalation board plus journal
def test_one_alarm_per_new_key_and_none_again_for_a_seen_one(fw, board):
    mg.alarm_false_green(fw.state, ["#9@aaaaaaaaaaaa", "#10@bbbbbbbbbbbb"])
    mg.alarm_false_green(fw.state, ["#9@aaaaaaaaaaaa", "#10@bbbbbbbbbbbb"])
    mg.alarm_false_green(fw.state, ["#9@aaaaaaaaaaaa", "#11@cccccccccccc"])
    assert [r["key"] for r in alarms(fw)] == ["#9@aaaaaaaaaaaa", "#10@bbbbbbbbbbbb", "#11@cccccccccccc"] and all(r["escalated"] for r in alarms(fw))
    got = lines(board)
    assert [x["job"] for x in got] == [f"localci:false-green:{k}" for k in ("#9@aaaaaaaaaaaa", "#10@bbbbbbbbbbbb", "#11@cccccccccccc")]
    assert all(x["priority"] == "HIGH" and x["status"] == "pending" and isinstance(x["ts"], float) and x["type"] == "localci_false_green" for x in got)


def test_an_unwritable_board_is_said_in_the_journal_row_and_never_raises(fw, tmp_path, monkeypatch):
    monkeypatch.setenv(mg.ESCALATIONS_ENV, str(tmp_path / "no-such-dir" / "board.jsonl"))
    mg.alarm_false_green(fw.state, ["#9@aaaaaaaaaaaa"])
    (row,) = alarms(fw)
    assert row["escalated"] is False and row["key"] == "#9@aaaaaaaaaaaa"


def test_the_refresh_alarms_once_under_phase_f_and_the_merge_goes_on(fw, board, monkeypatch):
    refresh_on(monkeypatch)
    fake_report(monkeypatch, ["#9@aaaaaaaaaaaa"])
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    assert cache(fw)["false_green_keys"] == ["#9@aaaaaaaaaaaa"] and cache(fw)["phase_e_ready_ex_false_green"] is True and cache(fw)["phase_e_ready"] is False
    assert len(alarms(fw)) == 1 and len(lines(board)) == 1
    assert fw.tick() == 0 and fw.kinds()[-1] == "pushed"   # the merge proceeds on the very cache that carries the false green
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0 and len(alarms(fw)) == 1 and len(lines(board)) == 1   # a second refresh sees the same key: no repeat


def test_without_phase_f_the_refresh_raises_no_alarm(fw, board, monkeypatch):
    monkeypatch.delenv(mg.PHASE_F_ENV)
    refresh_on(monkeypatch)
    fake_report(monkeypatch, ["#9@aaaaaaaaaaaa"])
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    assert alarms(fw) == [] and lines(board) == []


# ------------------------------------------------------------------ the report: the keys and the term apart from FALSE_GREEN
def test_the_report_names_the_decision_behind_a_false_green_and_keeps_ready_false(tmp_path, monkeypatch):
    steps = [("Set up job", "success"), ("Checkout code", "success"), ("Set up Python", "success"), ("Run unit tests", "cancelled")]
    d, gh = incident(tmp_path, monkeypatch, WORKFLOW.replace("Backend Tests (Python)", CTX[0]), steps=steps)
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rep["false_green_keys"] == [f"#1@{d['head_sha'][:12]}"] and rep["phase_e_ready"] is False
    assert rep["phase_e_ready_ex_false_green"] is False   # one decision: the merges and days terms are short too


def test_a_clean_report_over_the_threshold_has_both_ready_flags_true_and_no_keys(fw, monkeypatch):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    doc = cache(fw)
    assert doc["phase_e_ready"] is True and doc["phase_e_ready_ex_false_green"] is True and doc["false_green_keys"] == []


def test_a_short_span_is_false_on_the_term_apart_from_false_green_too(fw, monkeypatch):
    refresh_on(monkeypatch)
    fw.hub.seed(fw.state, n=50, days=4)   # 50 compared merges over 4 days: the days term is the one that is short
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    doc = cache(fw)
    assert doc["phase_e_ready"] is False and doc["phase_e_ready_ex_false_green"] is False and doc["false_green_keys"] == []


def test_a_real_false_green_over_the_threshold_keeps_ready_false_and_the_term_apart_true(fw, board, monkeypatch):
    refresh_on(monkeypatch)
    head = "e" * 40
    hub, real = fw.hub, fw.hub.__class__.__call__
    hub.pulls[2000] = {"merged": False, "state": "open", "head": {"sha": head}, "merge_commit_sha": None, "merged_at": None}
    monkeypatch.setattr(hub.__class__, "__call__", lambda self, path: (
        {"check_runs": [{"name": c, "status": "completed", "conclusion": "failure", "head_sha": head, "app": {"id": 15368, "slug": "github-actions"},
                         "completed_at": None} for c in self.required]} if path.startswith(f"repos/{REPO}/commits/{head}/check-runs") else real(self, path)))
    row = {"kind": "decision", "ts": "2026-10-16T00:00:00Z", "pr": 2000, "head_sha": head, "base_sha": "f" * 40, "candidate_sha": "9" * 40, "overall": "PASS"}
    with (fw.state / "decisions.jsonl").open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    doc = cache(fw)
    assert doc["phase_e_ready"] is False and doc["phase_e_ready_ex_false_green"] is True and doc["false_green_keys"] == [f"#2000@{head[:12]}"]
    assert [x["job"] for x in lines(board)] == [f"localci:false-green:#2000@{head[:12]}"]


# ------------------------------------------------------------------ isolation: no test reaches the real escalation board
def test_a_test_without_its_own_board_alarms_into_the_session_temp_not_a_checkout(fw, tmp_path_factory):
    path = tmp_path_factory.getbasetemp() / "escalations_pro.jsonl"   # conftest's autouse board_off_the_checkout, not requested here
    assert os.environ.get(mg.ESCALATIONS_ENV) == str(path)
    before = len(lines(path))
    mg.alarm_false_green(fw.state, ["#7@dddddddddddd"])
    assert alarms(fw)[-1]["escalated"] is True and len(lines(path)) == before + 1


def test_the_default_board_is_the_checkout_under_home_never_the_desktop_symlink(fw, tmp_path, monkeypatch):
    monkeypatch.delenv(mg.ESCALATIONS_ENV)
    monkeypatch.setenv("HOME", str(tmp_path))   # Path.home(); the Pro merger runs under launchd, and TCC denies it ~/Desktop (W84)
    (tmp_path / "nuzantara" / "shared").mkdir(parents=True)
    mg.alarm_false_green(fw.state, ["#8@cccccccccccc"])
    assert [x["job"] for x in lines(tmp_path / "nuzantara" / "shared" / "escalations_pro.jsonl")] == ["localci:false-green:#8@cccccccccccc"]
    assert not (tmp_path / "Desktop").exists() and alarms(fw)[-1]["escalated"] is True
