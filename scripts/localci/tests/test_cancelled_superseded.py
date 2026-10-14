"""B17 in the report: a recorded FALSE_GREEN whose only reds were check runs cancelled by concurrency, now answered by a later run on the
judged sha, is reclassified (``stale_why: cancelled_superseded``); a row that journals no ``hosted_red``, any other red, or a run the sha
does not answer stays a false green."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE = Path(__file__).resolve().parent.parent / "merger.py"
_spec = importlib.util.spec_from_file_location("merger_b17_under_test", _MODULE)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

CTX, APP = "catE-sovereignty-lint", 15368


def _run(i, concl, at):
    return {"id": i, "name": CTX, "status": "completed", "conclusion": concl, "completed_at": at, "app": {"id": APP, "slug": "github-actions"}}


LIVE = {"check_runs": [_run(1, "cancelled", "2026-10-10T15:29:12Z"), _run(2, "success", "2026-10-10T15:31:00Z")], "statuses": []}
RED1 = [{"id": 1, "conclusion": "cancelled", "completed_at": "2026-10-10T15:29:12Z"}]


def _d(tmp_path, red, klass="FALSE_GREEN"):
    row = {"context": CTX, "class": klass, "app_id": APP, **({} if red is None else {"hosted_red": red})}
    (tmp_path / "hosted_compare.json").write_text(json.dumps({"rows": [row]}))
    return {"pr": 8231, "head_sha": "d" * 40, "run_dir": str(tmp_path)}


def test_a_recorded_cancelled_red_answered_by_a_later_run_is_reclassified(tmp_path):
    got, kept = mg.reclassify_replay_superseded(_d(tmp_path, RED1), LIVE)
    assert got == [{"pr": 8231, "context": CTX, "head_sha": "d" * 40, "stale_why": "cancelled_superseded", "superseded_cancelled": [1]}]
    assert kept[0]["why"] == mg.REPLAY_KEPT


def test_a_row_that_stays_a_false_green(tmp_path):
    other = {"id": 3, "conclusion": "failure", "completed_at": "2026-10-10T15:29:12Z"}
    for red in (None, [], [other], [*RED1, other], [{"id": 99, "conclusion": "cancelled", "completed_at": "2026-10-10T15:29:12Z"}]):
        got, _ = mg.reclassify_replay_superseded(_d(tmp_path, red), LIVE)
        assert got == [], red


def test_a_sha_that_does_not_answer_the_cancelled_run_keeps_the_row(tmp_path):
    live = {"check_runs": [LIVE["check_runs"][0]], "statuses": []}
    assert mg.reclassify_replay_superseded(_d(tmp_path, RED1), live)[0] == []


def test_an_unreadable_record_keeps_every_row(tmp_path):
    assert mg.reclassify_replay_superseded({"pr": 1, "head_sha": "d" * 40, "run_dir": str(tmp_path / "missing")}, LIVE)[0] == []


class _A:
    repo, base = "o/r", "main"


SHA = "5" * 40
REQ = [{"context": CTX, "app_id": APP}, {"context": "other", "app_id": APP}]


def _live(*runs):
    return {"required_checks": REQ, "check_runs": list(runs), "statuses": []}


def _row(count=1, **kw):
    return {"pr": 8231, "head_sha": "d" * 40, "contexts": {CTX: "OK", "other": "OK"}, "hosted_compare": {"sha": SHA, "counts": {"FALSE_GREEN": count}}, **kw}


OTHER_OK = {**_run(9, "success", "2026-10-10T15:00:00Z"), "name": "other"}


def test_a_row_without_entry_data_is_reclassified_when_the_reread_shows_cancelled_then_success():
    lives = {(SHA, None): _live(*LIVE["check_runs"], OTHER_OK)}
    (x,) = mg.reclassify_by_reread(_A, _row(), lives, 1)
    assert (x["context"], x["stale_why"], x["superseded_cancelled"]) == (CTX, "cancelled_superseded", [1])


def test_a_reread_that_shows_a_later_failure_keeps_the_row():
    lives = {(SHA, None): _live(_run(1, "cancelled", "2026-10-10T15:29:12Z"), _run(2, "failure", "2026-10-10T15:31:00Z"), OTHER_OK)}
    assert mg.reclassify_by_reread(_A, _row(), lives, 1) == []


def test_a_context_red_for_another_reason_keeps_the_row_even_when_one_flipped():
    bad = {**_run(8, "failure", "2026-10-10T15:00:00Z"), "name": "other"}
    assert mg.reclassify_by_reread(_A, _row(), {(SHA, None): _live(*LIVE["check_runs"], bad)}, 1) == []


def test_a_recorded_count_that_is_not_the_number_flipped_keeps_the_row():
    lives = {(SHA, None): _live(*LIVE["check_runs"], OTHER_OK)}
    assert mg.reclassify_by_reread(_A, _row(2), lives, 2) == [] and mg.reclassify_by_reread(_A, _row(0), lives, 0) == []


def test_a_fetch_error_or_an_unreadable_sha_keeps_the_row(monkeypatch):
    def boom(*_a):
        raise OSError("gh down")
    monkeypatch.setattr(mg.hc, "fetch_live", boom)
    assert mg.reclassify_by_reread(_A, _row(), {}, 1) == []
    assert mg.reclassify_by_reread(_A, {**_row(), "hosted_compare": {"sha": "nope"}}, {}, 1) == []
