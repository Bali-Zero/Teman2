"""B20: READY is computed apart by the tick (``refresh_ready``) and only read by phase F (``read_ready``). The real report runs against the
seeded journal of test_merger_phase_f; the counting spy sits on ``report``."""
from __future__ import annotations

import json
import stat
import time

import pytest

from .test_merger import mg, world  # noqa: F401 — `world` is a fixture
from .test_merger_phase_f import _spy_report, armed_by_cache, fw, write_ready  # noqa: F401 — `fw` is a fixture

REAL_DUE = mg.ready_refresh_due   # the world fixture switches the refresh off; these tests turn it back on


def cache_path(w):
    return w.state / mg.READY_CACHE_FILE


def cache(w):
    return json.loads(cache_path(w).read_text())


def refresh_on(monkeypatch):
    monkeypatch.setattr(mg, "ready_refresh_due", REAL_DUE)


def age_cache(w, seconds):
    write_ready(w.state, computed_at=time.time() - seconds)


def refusing(monkeypatch, how):
    calls = []

    def fake(*a, **kw):
        calls.append(kw)
        if how == "refuse":
            return 2, {"phase_e_ready": False, "refused": "CompareError: unexpected end of JSON input"}
        raise how
    monkeypatch.setattr(mg, "report", fake)
    return calls


def live_kinds(w):
    return [r["kind"] for r in w.live()]


# ------------------------------------------------------------------ the read: phase F never runs the report
def test_a_fresh_true_cache_arms_the_merge_right_after_the_tick_journalled_its_own_decision_and_the_report_is_never_called(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    assert fw.tick() == 0
    assert live_kinds(fw)[:3] == ["decision", "would_enqueue", "would_merge"] and calls == []   # the gate's scenario: a new decision, still no report
    assert armed_by_cache(fw.wm()["phase_f"]) and live_kinds(fw)[-1] == "pushed"


@pytest.mark.parametrize("over,why", [({"phase_e_ready": False}, "READY false (cache)"),
                                      ({"refused": "CompareError: boom"}, "READY unreadable: CompareError: boom (cache)"),
                                      ({"computed_at": time.time() - mg.READY_MAX_AGE_S - 1}, "READY stale: computed "),
                                      ({"phase_e_ready": "yes"}, "READY false (cache)"),
                                      ({"computed_at": time.time() + 5000}, "READY stale: computed -")])
def test_read_ready_refuses_what_is_not_a_fresh_true_cache(fw, over, why):
    write_ready(fw.state, **over)
    reason, facts = mg.read_ready(fw.state)
    assert reason is not None and reason.startswith(why) and facts["ready_source"] == "cache"


def test_read_ready_accepts_a_cache_just_under_the_max_age_and_refuses_it_at_the_max_age(fw):
    age_cache(fw, mg.READY_MAX_AGE_S - 30)
    assert mg.read_ready(fw.state)[0] is None
    age_cache(fw, mg.READY_MAX_AGE_S + 1)
    assert mg.read_ready(fw.state)[0].startswith("READY stale")


@pytest.mark.parametrize("junk", ["{torn", "[]", "null", '{"phase_e_ready": true}', '{"computed_at": "now", "phase_e_ready": true}', ""])
def test_a_missing_or_corrupt_cache_is_unknown_never_an_error(fw, junk):
    cache_path(fw).write_text(junk)
    assert mg.read_ready(fw.state) == ("READY unknown: no cache", {"ready_source": "cache"})
    cache_path(fw).unlink()
    assert mg.read_ready(fw.state)[0] == "READY unknown: no cache"


# ------------------------------------------------------------------ the refresh: the tick's own work, once an hour
def test_a_tick_with_a_cache_older_than_the_refresh_interval_refreshes_and_decides_nothing_else(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    assert calls == [{"emit": False}] and live_kinds(fw) == [] and fw.pushes == []   # a refresh is its own tick
    doc = cache(fw)
    assert doc["phase_e_ready"] is True and doc["refused"] is None and doc["compared_merges"] >= mg.READY_MIN_MERGES and doc["false_green"] == 0
    assert set(doc) == {"computed_at", "phase_e_ready", "refused", "compared_merges", "false_green", "compared_days", "journal_rows"}
    assert stat.S_IMODE(cache_path(fw).stat().st_mode) == 0o600 and time.time() - doc["computed_at"] < 600
    assert [p.name for p in fw.state.iterdir() if p.name.startswith(mg.READY_CACHE_FILE)] == [mg.READY_CACHE_FILE]


def test_the_tick_after_a_refresh_merges_on_the_cache_it_wrote(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    cache_path(fw).unlink()
    assert fw.tick() == 0 and len(calls) == 1 and live_kinds(fw) == []
    assert fw.tick() == 0 and len(calls) == 1
    assert armed_by_cache(fw.wm()["phase_f"]) and live_kinds(fw)[-1] == "pushed"


def test_a_tick_with_a_cache_younger_than_the_refresh_interval_does_not_refresh(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S - 60)
    assert fw.tick() == 0 and calls == [] and live_kinds(fw)[:1] == ["decision"]


def test_a_false_result_is_stored_and_a_later_merge_is_refused_on_it(fw, monkeypatch):
    refresh_on(monkeypatch)
    fw.hub.seed(fw.state, n=50, days=4)   # a 4-day span of compared merges: the precheck cannot rule it out, the report says false
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0 and cache(fw)["phase_e_ready"] is False
    assert fw.tick() == 0 and "READY false (cache)" in fw.wm()["phase_f"]["why"] and "pushed" not in live_kinds(fw)


@pytest.mark.parametrize("how", ["refuse", RuntimeError("boom")], ids=["refused", "raised"])
def test_a_failed_refresh_keeps_the_old_cache_journals_it_and_the_tick_goes_on(fw, monkeypatch, how):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    before = cache_path(fw).read_text()
    calls = refusing(monkeypatch, how)
    assert fw.tick() == 0
    assert cache_path(fw).read_text() == before and len(calls) == 1
    (failed,) = [r for r in fw.live() if r["kind"] == "ready_refresh_failed"]
    assert failed["error"] and live_kinds(fw)[:2] == ["ready_refresh_failed", "decision"]   # the tick decided as usual
    assert fw.tick() == 0 and len(calls) == 1   # not tried again inside READY_RETRY_S


def test_a_failed_refresh_is_tried_again_once_the_retry_interval_has_passed(fw, monkeypatch):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    calls = refusing(monkeypatch, "refuse")
    fw.tick()
    real = time.time
    monkeypatch.setattr(mg.time, "time", lambda: real() + mg.READY_RETRY_S + 5)
    fw.tick()
    assert len(calls) == 2


@pytest.mark.parametrize("exc", [mg.MergerError("tick exceeded --tick-timeout (signal 14)"), mg.Stopped("stopped (signal 15)")], ids=["watchdog", "stop"])
def test_a_watchdog_or_a_stop_during_a_refresh_ends_the_tick(fw, monkeypatch, exc):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    before = cache_path(fw).read_text()
    refusing(monkeypatch, exc)
    assert fw.tick() == 1
    assert live_kinds(fw) == ["error"] and cache_path(fw).read_text() == before and fw.pushes == []
    assert fw.live()[0]["error"].startswith(str(exc)[:20])
