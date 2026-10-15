"""B17 in the report: a recorded FALSE_GREEN whose only reds were check runs cancelled by concurrency, now answered by a later run on the
judged sha, is reclassified (``stale_why: cancelled_superseded``); a row that journals no ``hosted_red``, any other red, or a run the sha
does not answer stays a false green."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

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


# ------------------------------------------------------------------ R2: a re-read that can CLEAR a false green reads the decision's own base
BASEX = "b" * 40
CLEARING = {"required_checks": REQ, "check_runs": [*LIVE["check_runs"], OTHER_OK], "statuses": []}
HOLDING = {"required_checks": REQ, "check_runs": [LIVE["check_runs"][0], OTHER_OK], "statuses": []}   # the cancelled run is never answered


class _AS:
    repo, base, state_dir = "o/r", "main", "/nonexistent-state"


def _by_ref(seen):
    """A GitHub whose answer depends on the BASE ref asked: the clearing evidence only for any ref but the decision's own."""
    def fetch(repo, branch, sha, base=None):
        seen.append(base[0] if base else None)
        return HOLDING if base and base[0] == BASEX else CLEARING
    return fetch


def test_the_b17b_reread_reads_at_the_decisions_own_base_so_another_ref_cannot_clear_a_false_green(monkeypatch):
    seen = []
    monkeypatch.setattr(mg.hc, "fetch_live", _by_ref(seen))
    assert mg.reclassify_by_reread(_AS, _row(base_sha=BASEX), {}, 1) == [] and seen == [BASEX]


def test_the_b10_reread_reads_at_the_decisions_own_base_so_another_ref_cannot_clear_a_false_green(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(mg.hc, "fetch_live", _by_ref(seen))
    out, kept = mg.reclassify_recorded(_AS, {**_d(tmp_path, RED1), "base_sha": BASEX}, lambda name, at: {"stale": False})
    assert out == [] and len(kept) == 1 and seen == [BASEX]


# ------------------------------------------------------------------ B17b: the context's FULL history (filter=all), and a timeout is no concurrency cancel
TIMEOUT = "The job has exceeded the maximum execution time of 15m0s"


class _H:
    """GET fake: the failure annotations of a check run, and the context's every attempt (``filter=all``)."""
    def __init__(self, attempts=(), notes=None):
        self.attempts, self.notes, self.paths = list(attempts), notes or {}, []

    def __call__(self, path):
        self.paths.append(path)
        if "/annotations" in path:
            rid = int(path.split("/check-runs/")[1].split("/")[0])
            return [{"annotation_level": "failure", "message": m} for m in self.notes.get(rid, [])]
        if "filter=all" in path:
            return {"check_runs": self.attempts}
        raise AssertionError(path)


@pytest.fixture(autouse=True)
def _no_live_github(monkeypatch):
    """Nothing here may reach GitHub: an unmocked read is a failure, and a bare annotation read answers none."""
    monkeypatch.setattr(mg.hc, "gh_get", _H())


def _recorded(tmp_path, monkeypatch, attempts, notes=None, red=None):
    hub = _H(attempts, notes)
    monkeypatch.setattr(mg.hc, "gh_get", hub)
    monkeypatch.setattr(mg.hc, "fetch_live", lambda *a, **k: _live(_run(2, "success", "2026-10-10T15:31:00Z"), OTHER_OK))
    out, kept = mg.reclassify_recorded(_AS, _d(tmp_path, RED1 if red is None else red), lambda name, at: {"stale": False})
    return out, kept, hub


def test_a_concurrency_cancel_answered_by_a_rerun_in_the_same_check_suite_is_reclassified(tmp_path, monkeypatch):
    out, kept, hub = _recorded(tmp_path, monkeypatch, [_run(1, "cancelled", "2026-10-10T15:29:12Z"), _run(2, "success", "2026-10-10T15:31:00Z")],
                               {1: ["Canceling since a higher priority waiting request exists"]})
    assert [(x["stale_why"], x["superseded_cancelled"]) for x in out] == [("cancelled_superseded", [1])] and kept == []
    assert any("filter=all" in p for p in hub.paths)


def test_a_job_timeout_cancel_is_never_droppable_whatever_re_run_follows(tmp_path, monkeypatch):
    out, kept, _ = _recorded(tmp_path, monkeypatch, [_run(1, "cancelled", "2026-10-10T15:29:12Z"), _run(2, "success", "2026-10-10T15:31:00Z")], {1: [TIMEOUT]})
    assert out == [] and "now GREEN" in kept[0]["why"]


def test_a_failed_attempt_followed_by_a_green_re_run_stays_red_and_kept(tmp_path, monkeypatch):
    attempts = [_run(1, "cancelled", "2026-10-10T15:29:12Z"), _run(3, "failure", "2026-10-10T15:30:00Z"), _run(2, "success", "2026-10-10T15:31:00Z")]
    out, kept, _ = _recorded(tmp_path, monkeypatch, attempts)
    assert out == [] and len(kept) == 1
    out, kept, _ = _recorded(tmp_path, monkeypatch, attempts[1:], red=[{"id": 3, "conclusion": "failure", "completed_at": "2026-10-10T15:30:00Z"}])
    assert out == [] and len(kept) == 1


def test_an_unreadable_history_keeps_the_row(tmp_path, monkeypatch):
    monkeypatch.setattr(mg.hc, "fetch_live", lambda *a, **k: _live(_run(2, "success", "2026-10-10T15:31:00Z"), OTHER_OK))
    monkeypatch.setattr(mg.hc, "gh_get", lambda path: (_ for _ in ()).throw(OSError("gh down")))
    out, kept = mg.reclassify_recorded(_AS, _d(tmp_path, RED1), lambda name, at: {"stale": False})
    assert out == [] and len(kept) == 1


def test_a_row_without_entry_data_whose_cancelled_attempt_was_a_timeout_stays_a_false_green(monkeypatch):
    monkeypatch.setattr(mg.hc, "gh_get", _H(notes={1: [TIMEOUT]}))
    lives = {(SHA, None): _live(*LIVE["check_runs"], OTHER_OK)}
    assert mg.reclassify_by_reread(_A, _row(), lives, 1) == []


def test_a_row_without_entry_data_is_cleared_by_the_full_history_when_the_listing_hid_attempt_one(monkeypatch):
    monkeypatch.setattr(mg.hc, "gh_get", _H([_run(1, "cancelled", "2026-10-10T15:29:12Z"), _run(2, "success", "2026-10-10T15:31:00Z")]))
    lives = {(SHA, None): _live(_run(2, "success", "2026-10-10T15:31:00Z"), OTHER_OK)}   # the default listing shows only the re-run
    (x,) = mg.reclassify_by_reread(_A, _row(), lives, 1)
    assert (x["context"], x["stale_why"], x["superseded_cancelled"]) == (CTX, "cancelled_superseded", [1])
