"""B20: phase F reads READY from a cache keyed on the journal's decision rows, so a retried merge does not replay the report's
~1000 GitHub reads. The real report runs against the seeded journal of test_merger_phase_f; the counting spy sits on ``report``."""
from __future__ import annotations

import argparse
import json
import stat
import time

import pytest

from .test_merger import REPO, mg, world  # noqa: F401 — `world` is a fixture
from .test_merger_phase_f import _spy_report, fw, full_pull  # noqa: F401 — `fw` is a fixture


def arm(w, monkeypatch):
    """phase_f_arming with every local condition true, so READY is the only thing evaluated; returns a callable that runs it."""
    monkeypatch.setattr(mg, "judged_tree", lambda repo_dir, enq: "t" * 40)
    monkeypatch.setattr(mg, "pr_view", lambda a, n: full_pull(w))
    enq = {"kind": "would_enqueue", "pr": 1, "head_sha": w.head1, "base_sha": w.base, "candidate_sha": "9" * 40,
           "criterion": {k: True for k in mg.CRITERION}, "ok": True}
    line = {"base_sha": w.base, "mirror_main": w.base, "base_current": True, "clean": True, "merge_tree": "t" * 40}
    a = argparse.Namespace(repo=REPO, base="main")
    return lambda: mg.phase_f_arming(a, w.state, w.mirror, enq, line, "main")[1]


def cache(w):
    return json.loads((w.state / mg.READY_CACHE_FILE).read_text())


def append(w, rec):
    with (w.state / "decisions.jsonl").open("a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def clock(monkeypatch, plus_s):
    real = time.time
    monkeypatch.setattr(mg.time, "time", lambda: real() + plus_s)


def test_two_arming_attempts_on_an_unchanged_journal_run_the_report_once(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    first, second = go(), go()
    assert len(calls) == 1 and first["armed"] and second["armed"]
    assert first["ready_source"] == "computed" and "ready_cache_age_s" not in first
    assert second["ready_source"] == "cache" and 0 <= second["ready_cache_age_s"] < 60


def test_a_new_decision_row_means_recompute(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    go()
    append(fw, {"kind": "decision", "ts": mg.now(), "pr": 7, "head_sha": "a" * 40, "base_sha": "f" * 40, "overall": "BLOCKED"})
    assert go()["ready_source"] == "computed" and len(calls) == 2


def test_a_replay_decision_row_and_a_changed_decision_row_recompute_too(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    go()
    append(fw, {"kind": "decision", "ts": mg.now(), "pr": 8, "head_sha": "b" * 40, "base_sha": "f" * 40, "replay": True, "merge_commit": "1" * 40})
    go()
    assert len(calls) == 2
    p = fw.state / "decisions.jsonl"
    p.write_text(p.read_text().replace('"overall": "BLOCKED"', '"overall": "PASS"', 1))
    go()
    assert len(calls) == 3


@pytest.mark.parametrize("kind", ["prune", "would_merge", "would_enqueue", "evicted", "skipped", "error"])
def test_a_row_the_ready_computation_ignores_does_not_change_the_key(fw, monkeypatch, kind):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    go()
    append(fw, {"kind": kind, "ts": mg.now(), "pr": 1, "why": "x"})
    assert go()["ready_source"] == "cache" and len(calls) == 1


def test_the_key_depends_on_the_repo_and_base_it_was_asked_about(fw):
    a = argparse.Namespace(repo=REPO, base="main")
    first, again = mg.ready_key(a, fw.state), mg.ready_key(argparse.Namespace(repo=REPO.upper(), base="main"), fw.state)
    assert first == again   # the repo is compared lowercased, as the report does
    assert first != mg.ready_key(argparse.Namespace(repo=REPO, base="release"), fw.state)


def test_after_the_ttl_the_result_is_recomputed(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    go()
    clock(monkeypatch, mg.READY_TTL_S - 5)
    assert go()["ready_source"] == "cache" and len(calls) == 1
    clock(monkeypatch, mg.READY_TTL_S + 5)
    assert go()["ready_source"] == "computed" and len(calls) == 2


def test_a_refused_result_is_not_cached(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    real = mg.hc.gh_get
    monkeypatch.setattr(mg.hc, "gh_get", lambda path: (_ for _ in ()).throw(mg.hc.CompareError("unexpected end of JSON input")))
    pf = go()
    assert not pf["armed"] and any(x.startswith("READY unreadable: ") for x in pf["why"]) and not (fw.state / mg.READY_CACHE_FILE).exists()
    monkeypatch.setattr(mg.hc, "gh_get", real)
    assert go()["armed"] and len(calls) == 2


def test_an_exception_from_the_report_is_not_cached_either(fw, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(mg, "report", boom)
    pf = arm(fw, monkeypatch)()
    assert not pf["armed"] and any(x.startswith("READY unreadable: RuntimeError") for x in pf["why"]) and not (fw.state / mg.READY_CACHE_FILE).exists()


@pytest.mark.parametrize("junk", ["{torn", "[]", "null", '{"key": 1}', ""])
def test_a_corrupt_cache_file_is_a_miss_never_an_error(fw, monkeypatch, junk):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    (fw.state / mg.READY_CACHE_FILE).write_text(junk)
    pf = go()
    assert pf["armed"] and pf["ready_source"] == "computed" and len(calls) == 1
    assert cache(fw)["phase_e_ready"] is True   # the miss repaired the file


def test_a_cached_refusal_or_future_dated_or_unboolean_file_is_a_miss(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    go()
    good = cache(fw)
    for bad in ({**good, "refused": "boom"}, {**good, "computed_at": time.time() + 5000}, {**good, "phase_e_ready": "yes"}):
        (fw.state / mg.READY_CACHE_FILE).write_text(json.dumps(bad))
        assert go()["ready_source"] == "computed"
    assert len(calls) == 4


def test_a_cached_ready_false_is_still_a_refusal(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    fw.hub.seed(fw.state, n=50, days=4)   # a 4-day span of compared merges: the precheck cannot rule it out, the report says false
    first = go()
    assert "READY false" in first["why"] and not first["armed"] and cache(fw)["phase_e_ready"] is False
    second = go()
    assert "READY false" in second["why"] and not second["armed"] and second["ready_source"] == "cache" and len(calls) == 1


def test_the_cache_holds_the_documented_fields_with_mode_0600_and_leaves_no_temp_file(fw, monkeypatch):
    arm(fw, monkeypatch)()
    f = fw.state / mg.READY_CACHE_FILE
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert set(cache(fw)) == {"key", "computed_at", "phase_e_ready", "refused", "compared_merges", "false_green", "compared_days"}
    assert cache(fw)["refused"] is None and cache(fw)["compared_merges"] >= mg.READY_MIN_MERGES and cache(fw)["false_green"] == 0
    assert [p.name for p in fw.state.iterdir() if p.name.startswith(mg.READY_CACHE_FILE)] == [mg.READY_CACHE_FILE]


def test_the_write_is_an_atomic_replace_of_a_temp_file_in_the_same_directory(fw, monkeypatch):
    seen = []
    real = mg.os.replace
    monkeypatch.setattr(mg.os, "replace", lambda src, dst: seen.append((str(src), str(dst))) or real(src, dst))
    arm(fw, monkeypatch)()
    (src, dst), = [x for x in seen if x[1].endswith(mg.READY_CACHE_FILE)]
    assert src != dst and src.rsplit("/", 1)[0] == dst.rsplit("/", 1)[0] and src.endswith(".tmp")


def test_an_unwritable_cache_costs_a_recompute_not_the_tick(fw, monkeypatch):
    calls, go = _spy_report(monkeypatch), arm(fw, monkeypatch)
    (fw.state / mg.READY_CACHE_FILE).mkdir()
    assert go()["armed"] and go()["armed"] and len(calls) == 2
