"""B10 guilt + innocence: a hosted verdict given on an older main than the local run judged is HOSTED_STALE, only on evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from . import stale_fixture as sf

_MODULE = Path(__file__).resolve().parent.parent / "merger.py"
_spec = importlib.util.spec_from_file_location("merger_stale_under_test", _MODULE)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)
hc = mg.hc

BEFORE_LOCK = "2026-10-06T02:54:00Z"     # hosted ran before main took the lock file (the pr7961 shape)
AFTER_LOCK = "2026-10-06T05:00:00Z"      # after the lock file, before the doc and the mouth source
AFTER_DOC = "2026-10-07T12:00:00Z"       # after the doc, before the mouth source
AFTER_BASE = "2026-10-09T00:00:00Z"


@pytest.fixture
def main(tmp_path):
    m = sf.make_main(tmp_path / "mirror")
    m["repo"] = tmp_path / "mirror"
    m["judge"] = mg.StaleJudge(m["repo"], m["base"])
    return m


# ------------------------------------------------------------------ the judge: the evidence
def test_main_moved_a_selected_path_after_hosted_ran_is_stale_with_the_commit_and_the_selected_path_only(main):
    got = main["judge"](sf.CTX_BACKEND, BEFORE_LOCK)
    assert got == {"stale": True, "hosted_main": main["c0"], "main_moved_paths": [sf.LOCK], "main_moved_count": 1}   # the doc and the tsx are not selected


def test_main_moved_only_in_unselected_paths_is_fresh(main):
    got = main["judge"](sf.CTX_BACKEND, AFTER_LOCK)
    assert got["stale"] is False and got["hosted_main"] == main["c1"] and got["main_moved_paths"] == []


def test_the_same_move_is_stale_for_the_context_it_selects(main):
    assert main["judge"](sf.CTX_FRONTEND, AFTER_DOC)["stale"] is True and main["judge"](sf.CTX_BACKEND, AFTER_DOC)["stale"] is False


def test_a_hosted_run_completed_after_the_base_is_fresh_and_its_main_is_the_base(main):
    assert main["judge"](sf.CTX_BACKEND, AFTER_BASE) == {"stale": False, "hosted_main": main["base"]}


@pytest.mark.parametrize("name,when,why", [(sf.CTX_ALWAYS, BEFORE_LOCK, "no runs_when"), ("Nothing Here", BEFORE_LOCK, "not a context"),
                                           (sf.CTX_BACKEND, "2026-10-01T00:00:00Z", "dated at or before")])
def test_a_judge_that_cannot_find_its_evidence_raises(main, name, when, why):
    with pytest.raises(mg.MergerError, match=why):
        main["judge"](name, when)


def test_an_unreadable_mirror_raises(tmp_path):
    with pytest.raises(mg.MergerError):
        mg.StaleJudge(tmp_path / "nowhere.git", "a" * 40)(sf.CTX_BACKEND, BEFORE_LOCK)


def test_the_base_change_map_decides_not_the_working_tree(main, tmp_path):
    # a base whose classifier selects nothing: the same move is then fresh, so the verdict follows the BASE copy of change_map.py
    path = tmp_path / "other"
    sf.git(Path(main["repo"]), "worktree", "add", "-q", "--detach", str(path), main["c3"])
    (path / "scripts/ci/change_map.py").write_text(
        "def classify(paths):\n    return {'mode': 'enforcing', 'reason': 'classified', 'run_all': False, 'suggested_jobs': []}\n")
    sf.git(path, "add", "-A")
    sf.git(path, "commit", "-qm", "blind classifier", when="2026-10-08T13:00:00Z")
    new_base = sf.git(path, "rev-parse", "HEAD")
    assert mg.StaleJudge(Path(main["repo"]), new_base)(sf.CTX_BACKEND, BEFORE_LOCK)["stale"] is False


# ------------------------------------------------------------------ hosted_compare: the class
CTX = "Backend Tests (Python)"
STATUS = {"candidate_sha": "c" * 40, "contexts": {"status": "ok", "results": {CTX: {"verdict": "OK", "coverage": "full", "mapping": "executed"}}}}


def runs(conclusion, at, name=CTX):
    return [{"name": name, "status": "completed", "conclusion": conclusion, "completed_at": at, "app": {"id": 15368, "slug": "github-actions"}}]


def compare(conclusion="failure", at=BEFORE_LOCK, judge=None, status=STATUS, check_runs=None):
    return hc.compare(status, [{"context": CTX, "app_id": 15368}], runs(conclusion, at) if check_runs is None else check_runs, [], stale_judge=judge)


def stale(name, at):
    return {"stale": True, "hosted_main": "a" * 40, "main_moved_paths": ["p"] * 25, "main_moved_count": 25}


@pytest.mark.parametrize("conclusion,before", [("failure", "FALSE_GREEN"), ("success", "AGREE")])
def test_a_stale_hosted_verdict_beside_a_local_green_is_neither_a_false_green_nor_an_agree(conclusion, before):
    rep = compare(conclusion, judge=stale)
    (row,) = rep["rows"]
    assert (row["class"], row["class_before"], row["stale_check"], row["hosted_completed_at"]) == ("HOSTED_STALE", before, "stale", BEFORE_LOCK)
    assert rep["counts"]["HOSTED_STALE"] == 1 and rep["counts"]["FALSE_GREEN"] == rep["counts"]["AGREE"] == 0
    assert len(row["main_moved_paths"]) == 20 and row["main_moved_count"] == 25 and row["hosted_main"] == "a" * 40
    assert rep["coverage"]["compared_full"] == 0 and hc.exit_code(rep) == 0   # never a compared context


def test_a_stale_local_red_beside_a_hosted_green_is_stale_too():
    red = {**STATUS, "contexts": {"status": "ok", "results": {CTX: {"verdict": "FAIL", "coverage": "full"}}}}
    assert compare("success", judge=stale, status=red)["rows"][0]["class_before"] == "FALSE_RED"


def test_a_fresh_hosted_verdict_keeps_its_class_and_says_fresh():
    (row,) = compare(judge=lambda n, t: {"stale": False, "hosted_main": "b" * 40})["rows"]
    assert (row["class"], row["stale_check"], "class_before" in row) == ("FALSE_GREEN", "fresh", False)


@pytest.mark.parametrize("judge,why", [(lambda n, t: {"stale": None, "why": "no mirror"}, "no mirror"),
                                       (lambda n, t: (_ for _ in ()).throw(OSError("mirror gone")), "OSError: mirror gone"),
                                       (lambda n, t: {"stale": "yes"}, "stale='yes'"), (lambda n, t: None, "AttributeError")])
def test_a_judge_without_evidence_leaves_the_class_and_says_unknown(judge, why):
    (row,) = compare(judge=judge)["rows"]
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith("unknown (") and why in row["stale_check"]


@pytest.mark.parametrize("at", [None, "yesterday", "2026-10-06 02:54"])
def test_a_hosted_verdict_with_no_readable_completed_at_is_unknown_and_the_judge_is_not_asked(at):
    asked = []
    (row,) = compare(judge=lambda n, t: asked.append(t), check_runs=runs("failure", at))["rows"]
    assert row["class"] == "FALSE_GREEN" and "completed_at" in row["stale_check"] and asked == []


def test_without_a_judge_the_rows_carry_no_stale_keys_and_the_class_is_what_it_was():
    (row,) = compare()["rows"]
    assert row["class"] == "FALSE_GREEN" and not [k for k in row if k.startswith(("stale", "hosted_main", "main_moved", "class_before"))]


def test_only_a_compared_row_is_judged():
    asked = []
    pending = [{"name": CTX, "status": "in_progress", "conclusion": None, "completed_at": None, "app": {"id": 15368}}]
    blind = {**STATUS, "contexts": {"status": "ok", "results": {CTX: {"verdict": "BLOCKED"}}}}
    assert compare(judge=lambda n, t: asked.append(t), check_runs=pending)["rows"][0]["class"] == "HOSTED_PENDING"
    assert compare(judge=lambda n, t: asked.append(t), status=blind)["rows"][0]["class"] == "LOCAL_BLIND" and asked == []


def test_the_time_of_a_red_verdict_is_the_time_of_the_red_entry():
    both = runs("failure", BEFORE_LOCK) + runs("success", AFTER_BASE)   # red-dominant: the old red decides, not the newer green
    seen = []
    compare(judge=lambda n, t: seen.append(t) or {"stale": False}, check_runs=both)
    assert seen == [BEFORE_LOCK]
    seen.clear()
    compare(judge=lambda n, t: seen.append(t) or {"stale": False}, check_runs=runs("failure", BEFORE_LOCK) + runs("failure", AFTER_LOCK))
    assert seen == [AFTER_LOCK]   # two reds: the verdict stands on the newest run of them


# ------------------------------------------------------------------ the tick's summary
def _live(conclusion="failure", at=BEFORE_LOCK):
    return {"required_checks": [{"context": CTX, "app_id": 15368}], "check_runs": runs(conclusion, at), "statuses": []}


def test_the_tick_journals_the_stale_row_and_the_run_dir_keeps_its_evidence(main, tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "fetch_live", lambda *a: _live())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    summary, live = mg.hosted_summary("o/r", "main", STATUS, "h" * 40, run_dir, main["judge"])
    assert summary["counts"]["HOSTED_STALE"] == 1 and summary["counts"]["FALSE_GREEN"] == 0 and summary["exit"] == 0 and live is not None
    assert summary["stale"] == [{"context": CTX, "class_before": "FALSE_GREEN", "hosted_completed_at": BEFORE_LOCK, "hosted_main": main["c0"],
                                 "main_moved_paths": [sf.LOCK], "main_moved_count": 1}]
    (row,) = json.loads((run_dir / "hosted_compare.json").read_text())["rows"]
    assert row["class"] == "HOSTED_STALE" and row["stale_check"] == "stale"
    assert mg.recorded_false_green({"hosted_compare": summary}) == 0


def test_the_tick_with_an_unreadable_mirror_keeps_the_false_green_and_names_why(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "fetch_live", lambda *a: _live())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    summary, _ = mg.hosted_summary("o/r", "main", STATUS, "h" * 40, run_dir, mg.StaleJudge(tmp_path / "nowhere.git", "a" * 40))
    assert summary["counts"]["FALSE_GREEN"] == 1 and summary["exit"] == 1 and "stale" not in summary
    assert summary["stale_unknown"][CTX].startswith("unknown (")
