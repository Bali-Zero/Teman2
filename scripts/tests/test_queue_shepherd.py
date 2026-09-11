"""test_queue_shepherd.py — pure-function + monkeypatched-I/O tests, no network.

Covers the four cases the mandate named explicitly:
  1. budget enforcement: the 4th INFRA re-arm in a rolling 24h window is refused.
  2. CODE-classified ejections are never re-armed, regardless of budget.
  3. UNKNOWN (no readable ejection reason) fails closed: never re-armed.
  4. the janitor never cancels a run whose head/branch is still live, verified via the
     cancel-time RECHECK path (a fresh fetch that can disagree with the discovery fetch).

Plus superscar #3 discipline (guard-over-match): every guard gets an innocence test on the
same entity, never inferred from a single guilt case.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue_shepherd as qs  # noqa: E402

NOW = _dt.datetime(2026, 8, 27, 12, 0, 0, tzinfo=_dt.timezone.utc)


@pytest.fixture(autouse=True)
def _isolate_state_files(monkeypatch, tmp_path):
    """W96-class leak fix (Dux review, 2026-09-11): every test in this module — even one that
    never mentions a state file by name — must be structurally unable to touch the REAL
    ~/logs or ~/.organism. Two real leaks were measured before this fixture existed: the kill-
    switch path writes an unconditional heartbeat regardless of which test triggers it, and a
    dry-run/tick path can read/write red-causes state without every caller naming it explicitly.
    Fixed by class (one autouse fixture), not per test. A test that ALSO does its own
    `monkeypatch.setattr(qs, "X", ...)` still works unchanged — monkeypatch tracks the ORIGINAL
    real value for teardown, so the later setattr in the test body simply wins for that test's
    duration, exactly like reassigning any other variable twice."""
    monkeypatch.setattr(qs, "ORGANISM_DIR", tmp_path / "organism")
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "rearm-budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted-unknown.json")
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red-causes.json")
    monkeypatch.setattr(qs, "REARM_FAIL_FILE", tmp_path / "rearm-write-failures.json")
    monkeypatch.setattr(qs, "LOG_FILE", tmp_path / "queue-shepherd.log")


def _iso(dt: _dt.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── classify_ejection_reason ────────────────────────────────────────────────


def test_classify_failed_checks_with_infra_hint_true_is_INFRA():
    assert qs.classify_ejection_reason("failed_checks", True) == "INFRA"


def test_classify_failed_checks_with_infra_hint_false_is_CODE():
    assert qs.classify_ejection_reason("failed_checks", False) == "CODE"


def test_classify_failed_checks_with_infra_hint_unresolved_defaults_to_CODE_never_invents_INFRA():
    assert qs.classify_ejection_reason("failed_checks", None) == "CODE"


def test_classify_manual_is_MANUAL():
    assert qs.classify_ejection_reason("manual", None) == "MANUAL"


def test_classify_merge_conflict_is_CONFLICT():
    assert qs.classify_ejection_reason("merge_conflict", None) == "CONFLICT"


def test_classify_no_event_found_is_UNKNOWN_not_CODE():
    assert qs.classify_ejection_reason(None, None) == "UNKNOWN"


def test_classify_unrecognized_reason_string_is_UNKNOWN_fail_visible():
    assert qs.classify_ejection_reason("some_new_github_reason_2027", None) == "UNKNOWN"


# ── budget: the 4th INFRA re-arm in 24h is refused (mandate case 1) ─────────


def test_budget_allows_first_three_infra_rearms_and_refuses_the_fourth():
    state: dict = {}
    for i in range(3):
        allowed, why = qs.decide_rearm("INFRA", state, 100, "sha1", NOW)
        assert allowed, f"rearm {i + 1} should be allowed, got {why}"
        state = qs.record_infra_rearm(state, 100, "sha1", NOW + _dt.timedelta(minutes=i))
    # 4th attempt, same (pr, sha), still inside the 24h window
    allowed, why = qs.decide_rearm("INFRA", state, 100, "sha1", NOW + _dt.timedelta(hours=1))
    assert not allowed
    assert "infra_budget_exhausted" in why


def test_budget_innocence_a_different_head_sha_is_a_fresh_budget_head_moved_resets():
    state: dict = {}
    for i in range(3):
        state = qs.record_infra_rearm(state, 100, "sha_old", NOW + _dt.timedelta(minutes=i))
    # exhausted on sha_old
    allowed, _why = qs.decide_rearm("INFRA", state, 100, "sha_old", NOW)
    assert not allowed
    # but a NEW head sha for the same PR number is a fresh key — allowed again
    allowed_new, why_new = qs.decide_rearm("INFRA", state, 100, "sha_new", NOW)
    assert allowed_new, why_new


def test_budget_window_innocence_a_rearm_older_than_24h_does_not_count_against_the_cap():
    state: dict = {}
    old_ts = NOW - _dt.timedelta(hours=25)
    state = qs.record_infra_rearm(state, 100, "sha1", old_ts)
    state = qs.record_infra_rearm(state, 100, "sha1", old_ts)
    state = qs.record_infra_rearm(state, 100, "sha1", old_ts)
    # all three are >24h old — a 4th NOW should still be allowed
    allowed, why = qs.decide_rearm("INFRA", state, 100, "sha1", NOW)
    assert allowed, why


def test_gc_budget_state_prunes_entries_with_no_timestamp_inside_the_gc_window():
    state: dict = {}
    ancient = NOW - _dt.timedelta(days=30)
    state = qs.record_infra_rearm(state, 100, "sha_ancient", ancient)
    state = qs.record_infra_rearm(state, 200, "sha_recent", NOW)
    gced = qs.gc_budget_state(state, NOW)
    assert "200:sha_recent" in gced
    assert "100:sha_ancient" not in gced


# ── CODE never re-arms regardless of budget (mandate case 2) ────────────────


def test_code_class_never_rearms_even_with_an_empty_untouched_budget():
    allowed, why = qs.decide_rearm("CODE", {}, 999, "shaX", NOW)
    assert not allowed
    assert why == "code_never_rearm"


def test_code_class_never_rearms_even_after_many_infra_rearms_recorded_for_a_different_class_slot():
    # a saturated budget must not accidentally make CODE look "extra refused" for the wrong
    # reason, and an empty budget must not make it look allowed — CODE is refused unconditionally
    state: dict = {}
    for i in range(3):
        state = qs.record_infra_rearm(state, 999, "shaX", NOW + _dt.timedelta(minutes=i))
    allowed, why = qs.decide_rearm("CODE", state, 999, "shaX", NOW)
    assert not allowed
    assert why == "code_never_rearm"


def test_conflict_and_manual_never_rearm():
    for klass in ("CONFLICT", "MANUAL"):
        allowed, why = qs.decide_rearm(klass, {}, 1, "s", NOW)
        assert not allowed
        assert why == f"{klass.lower()}_no_auto_rearm"


# ── UNKNOWN fails closed (mandate case 3) ───────────────────────────────────


def test_unknown_class_fails_closed_never_rearms():
    allowed, why = qs.decide_rearm("UNKNOWN", {}, 1, "s", NOW)
    assert not allowed
    assert why == "unknown_fail_closed"


def test_unknown_from_unrecognized_future_reason_string_also_fails_closed():
    klass = qs.classify_ejection_reason("a_reason_this_repo_has_never_seen", None)
    allowed, why = qs.decide_rearm(klass, {}, 1, "s", NOW)
    assert klass == "UNKNOWN"
    assert not allowed


# ── is_rearm_candidate (guard-over-match discipline: guilt + innocence) ─────


def _pr(**overrides):
    base = {
        "is_draft": False,
        "head_ref_name": "agent/nuzantara/infra/x",
        "has_fable_gate_status": False,
        "in_queue": False,
        "auto_merge_enabled": False,
        "merge_state_status": "CLEAN",
        "status_rollup_state": None,
    }
    base.update(overrides)
    return base


def test_candidate_innocence_clean_disarmed_agent_branch_is_selected():
    assert qs.is_rearm_candidate(_pr()) is True


def test_candidate_innocence_blocked_with_green_rollup_is_selected():
    assert qs.is_rearm_candidate(_pr(merge_state_status="BLOCKED", status_rollup_state="SUCCESS")) is True


def test_candidate_guilt_draft_pr_is_never_selected():
    assert qs.is_rearm_candidate(_pr(is_draft=True)) is False


def test_candidate_guilt_already_queued_is_never_selected():
    assert qs.is_rearm_candidate(_pr(in_queue=True)) is False


def test_candidate_guilt_already_armed_is_never_selected_W111():
    # armed-but-not-yet-queued (autoMergeRequest set, mergeQueueEntry null) — W111's second case
    assert qs.is_rearm_candidate(_pr(auto_merge_enabled=True)) is False


def test_candidate_guilt_not_our_convention_branch_and_no_gate_status_is_never_selected():
    assert qs.is_rearm_candidate(_pr(head_ref_name="feature/some-human-branch")) is False


def test_candidate_innocence_fable_gate_status_without_agent_branch_is_still_selected():
    assert (
        qs.is_rearm_candidate(
            _pr(head_ref_name="feature/some-human-branch", has_fable_gate_status=True)
        )
        is True
    )


def test_candidate_guilt_blocked_with_red_rollup_is_never_selected():
    assert (
        qs.is_rearm_candidate(_pr(merge_state_status="BLOCKED", status_rollup_state="FAILURE"))
        is False
    )


def test_candidate_guilt_dirty_state_is_never_selected():
    assert qs.is_rearm_candidate(_pr(merge_state_status="DIRTY")) is False


# ── janitor: never cancels a live head/branch (mandate case 4) ──────────────


def test_select_stale_pull_request_runs_guilt_and_innocence():
    runs = [
        {"id": 1, "event": "pull_request", "head_sha": "dead_sha", "head_branch": "b1"},
        {"id": 2, "event": "pull_request", "head_sha": "live_sha", "head_branch": "b2"},
    ]
    live = {"live_sha"}
    stale = qs.select_stale_pull_request_runs(runs, live)
    assert [r["id"] for r in stale] == [1]


def test_select_stale_merge_group_runs_guilt_and_innocence():
    runs = [
        {"id": 3, "event": "merge_group", "head_sha": "x", "head_branch": "gh-readonly-queue/main/pr-1-aaa"},
        {"id": 4, "event": "merge_group", "head_sha": "y", "head_branch": "gh-readonly-queue/main/pr-2-bbb"},
    ]
    live_branches = {"gh-readonly-queue/main/pr-2-bbb"}
    stale = qs.select_stale_merge_group_runs(runs, live_branches)
    assert [r["id"] for r in stale] == [3]


def test_select_functions_ignore_the_other_events_event_isolation():
    runs = [
        {"id": 5, "event": "pull_request", "head_sha": "dead", "head_branch": "gh-readonly-queue/main/pr-1-aaa"},
    ]
    # even though its head_branch also looks like a dead queue branch, a pull_request run is
    # never selected by select_stale_merge_group_runs (wrong event) — guard on the right field
    assert qs.select_stale_merge_group_runs(runs, set()) == []
    assert qs.select_stale_pull_request_runs(runs, {"dead"}) == []  # innocence: live head


def test_janitor_recheck_at_cancel_time_never_cancels_a_run_that_became_live(monkeypatch, tmp_path):
    """End-to-end of run_janitor_pass with every gh call monkeypatched: a run discovered stale
    on the FIRST fetch but reported live on the RECHECK fetch (the fresh call immediately
    before cancel) must never be cancelled. This is the literal 'not from a stale list' mandate."""
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    calls = {"cancel": []}

    discovery_heads = {"other_live_sha"}  # run's head_sha="flaky_sha" is stale here...
    recheck_heads = {"flaky_sha"}  # ...but became live by the time of the cancel-time recheck

    head_fetch_calls = {"n": 0}

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        head_fetch_calls["n"] += 1
        # first call = discovery (used to build the candidate list), second = cancel-time recheck
        return discovery_heads if head_fetch_calls["n"] == 1 else recheck_heads

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 42, "event": "pull_request", "head_sha": "flaky_sha", "head_branch": None, "name": "CI"}]

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    def fake_cancel_run(repo, run_id):
        calls["cancel"].append(run_id)
        return True, "cancelled"

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", fake_cancel_run)

    cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]

    assert cancelled == 0
    assert calls["cancel"] == []


def test_janitor_recheck_still_cancels_a_run_that_stays_stale_on_recheck(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    calls = {"cancel": []}

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 43, "event": "pull_request", "head_sha": "truly_dead", "head_branch": None, "name": "CI"}]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return {"some_other_live_sha"}  # stale on discovery AND on recheck

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    def fake_cancel_run(repo, run_id):
        calls["cancel"].append(run_id)
        return True, "cancelled"

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", fake_cancel_run)

    cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]

    assert cancelled == 1
    assert calls["cancel"] == [43]


# ── cancel_run: 409 "not queued yet" force-cancel fallback ─────────────────


def test_cancel_run_409_falls_back_to_force_cancel_and_counts_as_cancelled(monkeypatch):
    """Guilt: a plain-cancel HTTP 409 ('Cannot cancel a workflow run that has not been queued
    yet') must trigger exactly one force-cancel attempt, and a SUCCESSFUL force-cancel must be
    reported as cancelled (cancel_run returns True) — the shape measured live post-outage on Pro
    (~20 phantom runs retried every tick forever before this fix)."""
    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        if cmd[-1].endswith("/force-cancel"):
            return 0, "", ""
        return (
            1,
            "",
            "gh: Cannot cancel a workflow run that has not been queued yet. (HTTP 409)",
        )

    monkeypatch.setattr(qs, "_run", fake_run)
    ok, outcome = qs.cancel_run("Bali-Zero/Teman2", 3221000123)

    assert ok is True
    assert outcome == "cancelled"
    assert len(calls) == 2
    assert calls[0][-1].endswith("/actions/runs/3221000123/cancel")
    assert calls[1][-1].endswith("/actions/runs/3221000123/force-cancel")


def test_cancel_run_409_then_force_cancel_also_fails_is_warning_not_crash(monkeypatch, caplog):
    """Guilt (part 2): when the force-cancel fallback ALSO fails (e.g. the HTTP 500s seen on
    very old 3221xxxx runs), cancel_run must return False — a single warning, not an exception,
    and not counted as cancelled — so the caller's per-run loop simply continues to the next run."""

    def fake_run(cmd, timeout=30):
        if cmd[-1].endswith("/force-cancel"):
            return 1, "", "gh: Internal Server Error (HTTP 500)"
        return (
            1,
            "",
            "gh: Cannot cancel a workflow run that has not been queued yet. (HTTP 409)",
        )

    monkeypatch.setattr(qs, "_run", fake_run)
    with caplog.at_level("WARNING"):
        ok, outcome = qs.cancel_run("Bali-Zero/Teman2", 3221000456)

    assert ok is False
    assert outcome == "failed"  # a 500, not a 409 -> must NOT classify as uncancellable_409
    assert "force-cancel fallback also failed" in caplog.text


def test_cancel_run_non_409_failure_never_attempts_force_cancel(monkeypatch):
    """Innocence: a failure that is NOT the 409 'not queued yet' class (e.g. a plain HTTP 500 on
    the first cancel attempt, or a network error) must never trigger force-cancel — force-cancel
    is deliberately not the default path, only the 409 fallback."""
    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        return 1, "", "gh: Internal Server Error (HTTP 500)"

    monkeypatch.setattr(qs, "_run", fake_run)
    ok, outcome = qs.cancel_run("Bali-Zero/Teman2", 999)

    assert ok is False
    assert outcome == "failed"
    assert len(calls) == 1  # only the plain cancel — no force-cancel call made
    assert calls[0][-1].endswith("/actions/runs/999/cancel")


def test_cancel_run_409_on_force_cancel_is_uncancellable_409_class(monkeypatch):
    """Both endpoints answer 409 -> GitHub cannot resolve this run's state through either one.
    This is the ONLY class run_janitor_pass should ever persist to the skip-list."""

    def fake_run(cmd, timeout=30):
        return (
            1,
            "",
            "gh: Cannot cancel a workflow run that has not been queued yet. (HTTP 409)",
        )

    monkeypatch.setattr(qs, "_run", fake_run)
    ok, outcome = qs.cancel_run("Bali-Zero/Teman2", 32217208723)

    assert ok is False
    assert outcome == "uncancellable_409"


# ── janitor uncancellable skip-list ─────────────────────────────────────────


def test_janitor_uncancellable_409_persisted_and_skipped_next_tick(monkeypatch, tmp_path, caplog):
    """(a) Guilt: 409-on-force-cancel -> id persisted, and the VERY NEXT tick skips it (no
    cancel_run call at all for that id) with a one-line INFO summary naming the skip count."""
    uncancellable_path = tmp_path / "uncancellable.json"
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", uncancellable_path)

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [
            {"id": 32217208723, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}
        ]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()  # stale on discovery AND on every recheck

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)

    # Tick 1: cancel_run reports the both-endpoints-409 class.
    monkeypatch.setattr(qs, "cancel_run", lambda repo, run_id: (False, "uncancellable_409"))
    cancelled_1 = qs.run_janitor_pass(dry_run=False)["cancelled"]
    assert cancelled_1 == 0
    saved = qs._load_json(uncancellable_path)
    assert "32217208723" in saved

    # Tick 2: cancel_run must NEVER be invoked again for this id.
    def never_called(repo, run_id):
        raise AssertionError(f"cancel_run must not be re-invoked for known-uncancellable id {run_id}")

    monkeypatch.setattr(qs, "cancel_run", never_called)
    with caplog.at_level("INFO"):
        cancelled_2 = qs.run_janitor_pass(dry_run=False)["cancelled"]

    assert cancelled_2 == 0
    assert "skipping 1 known-uncancellable runs" in caplog.text


def test_janitor_transient_failure_not_persisted_retried_next_tick(monkeypatch, tmp_path):
    """(b) Innocence: a transient failure (e.g. HTTP 500 on force-cancel) must NOT enter the
    skip-list — the run is re-attempted (cancel_run called again) on the very next tick."""
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 555, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    calls = []

    def fake_cancel_run(repo, run_id):
        calls.append(run_id)
        return False, "failed"  # a transient 500 — never the 409-on-both-endpoints class

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", fake_cancel_run)

    qs.run_janitor_pass(dry_run=False)
    qs.run_janitor_pass(dry_run=False)

    assert calls == [555, 555]  # retried on both ticks — never skip-listed


def test_janitor_gc_drops_uncancellable_id_no_longer_a_candidate(monkeypatch, tmp_path):
    """(c) Self-cleaning: an id sitting in the skip-list from a past tick that no longer appears
    among THIS tick's stale candidates (its queued run aged out, its PR closed, GitHub finally
    resolved it, ...) must be dropped — the file cannot grow unbounded."""
    uncancellable_path = tmp_path / "uncancellable.json"
    qs._save_json(uncancellable_path, {"999999": {"recorded_at": "2026-08-01T00:00:00Z"}})
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", uncancellable_path)

    def fake_fetch_queued_runs(repo=qs.REPO):
        return []  # 999999 no longer shows up as a queued run at all

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)

    qs.run_janitor_pass(dry_run=False)

    assert qs._load_json(uncancellable_path) == {}


def test_janitor_corrupt_uncancellable_file_fails_closed_no_cancel(monkeypatch, tmp_path):
    """(d) A torn/corrupt skip-list file must fail closed — same posture as
    test_rearm_pass_corrupt_budget_file_fails_closed_no_rearm: CANNOT-VERIFY, zero action this
    tick, and the corrupt file is left exactly as-is (never silently overwritten with a fresh
    empty state, which would just as silently re-open every known-uncancellable id)."""
    uncancellable_path = tmp_path / "uncancellable.json"
    uncancellable_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", uncancellable_path)

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 777, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    def never_called(repo, run_id):
        raise AssertionError("cancel_run must never be called when skip-list state is unreadable")

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", never_called)

    cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]

    assert cancelled == 0
    assert uncancellable_path.read_text(encoding="utf-8") == "{not json"


def test_janitor_dry_run_never_calls_cancel_run(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 44, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    def never_called(*_args, **_kwargs):
        raise AssertionError("cancel_run must never be called in --dry-run")

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", never_called)

    cancelled = qs.run_janitor_pass(dry_run=True)["cancelled"]
    assert cancelled == 1  # counted as "would cancel"


# ── S1 letter G: dry-run fidelity — reads state, never writes it ────────────────────────────


def test_janitor_dry_run_reads_uncancellable_state_and_skips_a_quarantined_run(monkeypatch, tmp_path):
    """A run already quarantined (from a past LIVE tick) must be skipped in a dry-run tick too —
    before letter G, dry-run substituted {} for uncancellable_state, so a dry-run preview
    over-reported "would cancel" for runs the live janitor actually skips."""
    uncancellable_path = tmp_path / "uncancellable.json"
    qs._save_json(
        uncancellable_path,
        {"44": {"consecutive_failures": 5, "quarantined_at": qs._now().strftime("%Y-%m-%dT%H:%M:%SZ")}},
    )
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", uncancellable_path)

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 44, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", lambda repo=qs.REPO: set())
    monkeypatch.setattr(qs, "fetch_live_queue_branches", lambda repo=qs.REPO: set())

    def never_called(*_args, **_kwargs):
        raise AssertionError("cancel_run must never be called in --dry-run")

    monkeypatch.setattr(qs, "cancel_run", never_called)

    result = qs.run_janitor_pass(dry_run=True)

    assert result["cancelled"] == 0  # the quarantined id is skipped, not counted as "would cancel"
    # never written: the file must be byte-identical to what _save_json produced above
    assert "44" in qs._load_json(uncancellable_path)


def test_rearm_pass_dry_run_reads_budget_state_and_respects_the_infra_cap(monkeypatch, tmp_path):
    """A budget already exhausted (from past LIVE rearms) must be respected in a dry-run tick
    too — before letter G, dry-run substituted {} for budget_state, so a dry-run preview could
    show "would rearm" for a PR the live pass would actually refuse under budget."""
    budget_path = tmp_path / "budget.json"
    state: dict = {}
    for i in range(qs.INFRA_BUDGET_MAX):
        state = qs.record_infra_rearm(state, 801, "shaCap", NOW + _dt.timedelta(minutes=i))
    qs._save_json(budget_path, state)
    monkeypatch.setattr(qs, "BUDGET_FILE", budget_path)
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=801, head_sha="shaCap", head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaCap"},
    )
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", lambda repo, number, removed_at: (True, None))

    def never_called(*_a, **_k):
        raise AssertionError("dry-run must never call gh pr merge")

    monkeypatch.setattr(qs, "rearm_pr", never_called)

    result = qs.run_rearm_pass(dry_run=True, now=NOW + _dt.timedelta(hours=1))

    assert result["rearmed"] == 0  # budget already exhausted -> dry-run must show 0, not 1
    assert not budget_path.exists() or qs._load_json(budget_path) == state  # never written


def test_janitor_fetch_failure_is_cannot_verify_never_reads_as_nothing_to_do(monkeypatch):
    def boom(repo=qs.REPO):
        raise RuntimeError("gh api failed rc=1")

    monkeypatch.setattr(qs, "fetch_queued_runs", boom)
    cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]
    assert cancelled == 0  # CANNOT-VERIFY -> zero action, not zero-because-nothing-stale


# ── kill switch ──────────────────────────────────────────────────────────────


def test_kill_switch_env_var_makes_tick_a_noop(monkeypatch):
    monkeypatch.setenv("QUEUE_SHEPHERD_ENABLED", "false")

    def never_called(*_a, **_k):
        raise AssertionError("must not fetch anything when disabled")

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", never_called)
    monkeypatch.setattr(qs, "fetch_queued_runs", never_called)
    rc = qs.tick(dry_run=False)
    assert rc == 0


def test_kill_switch_writes_a_disabled_heartbeat_not_silence(monkeypatch, tmp_path):
    # G5: alive-but-idle must be observable as "disabled", never indistinguishable
    # from a dead organ (agy cross-family review, PR #5071).
    monkeypatch.setenv("QUEUE_SHEPHERD_ENABLED", "false")
    monkeypatch.setattr(qs, "ORGANISM_DIR", tmp_path)
    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(qs, "fetch_queued_runs", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError))

    rc = qs.tick(dry_run=False)

    assert rc == 0
    hb = json.loads((tmp_path / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "disabled"
    assert "QUEUE_SHEPHERD_ENABLED" in hb["metadata"]["reason"]


# ── rearm pass: end-to-end with monkeypatched I/O ───────────────────────────


def test_rearm_pass_infra_ejection_rearms_and_records_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_candidates(repo=qs.REPO):
        return [_pr(number=501, head_sha="shaINFRA", head_ref_name="agent/x/y/z")]

    def fake_ejection(repo, number):
        return {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaINFRA"}

    def fake_infra_hint_and_fingerprint(repo, number, removed_at):
        return True, None

    rearm_calls = []

    def fake_rearm_pr(repo, number):
        rearm_calls.append(number)
        return True

    monkeypatch.setattr(qs, "fetch_open_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", fake_infra_hint_and_fingerprint)
    monkeypatch.setattr(qs, "rearm_pr", fake_rearm_pr)

    rearmed = qs.run_rearm_pass(dry_run=False, now=NOW)["rearmed"]

    assert rearmed == 1
    assert rearm_calls == [501]
    saved = qs._load_json(qs.BUDGET_FILE)
    assert "501:shaINFRA" in saved


def test_rearm_pass_unknown_ejection_alerts_once_then_dedups(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_candidates(repo=qs.REPO):
        return [_pr(number=502, head_sha="shaUNK", head_ref_name="agent/x/y/z")]

    def fake_ejection(repo, number):
        return None  # last timeline item is Added (queued, then vanished) — UNKNOWN, alerts

    alerts = []

    def fake_send_telegram(message, dedup_key=""):
        alerts.append(dedup_key)
        return True  # simulates a successful delivery

    def never_rearm(repo, number):
        raise AssertionError("must never rearm an UNKNOWN ejection")

    monkeypatch.setattr(qs, "fetch_open_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)
    monkeypatch.setattr(qs, "rearm_pr", never_rearm)

    rearmed_1 = qs.run_rearm_pass(dry_run=False, now=NOW)["rearmed"]
    rearmed_2 = qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=10))["rearmed"]

    assert rearmed_1 == 0
    assert rearmed_2 == 0
    assert len(alerts) == 1  # deduped on the second tick — same (pr, head sha)


# ── MEDIUM (Codex review, 2026-09-11): first-tick alert volume — batch, don't spam ──────────


def test_rearm_pass_batches_three_unknown_prs_into_one_send_then_zero_next_tick(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_open_prs(repo=qs.REPO):
        return [
            _pr(number=1, head_sha="s1", head_ref_name="agent/a/b"),
            _pr(number=2, head_sha="s2", head_ref_name="agent/a/c"),
            _pr(number=3, head_sha="s3", head_ref_name="agent/a/d"),
        ]

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(qs, "fetch_last_ejection", lambda repo, number: None)  # UNKNOWN for all

    sends = []

    def fake_send_telegram(message, dedup_key=""):
        sends.append(dedup_key)
        return True

    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: (_ for _ in ()).throw(AssertionError()))

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert len(sends) == 1  # ONE batched send, not three
    assert sends[0] == "queue-shepherd-unknown-1:s1+2:s2+3:s3"
    saved = qs._load_json(qs.ALERTED_FILE)
    assert set(saved.keys()) == {"1:s1", "2:s2", "3:s3"}  # all three recorded on the one send
    assert result["rearmed"] == 0

    # next tick: same PRs, still UNKNOWN, already alerted -> zero sends
    sends.clear()
    qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=10))
    assert sends == []


def test_rearm_pass_dry_run_never_writes_state_files(monkeypatch, tmp_path):
    budget_path = tmp_path / "budget.json"
    alerted_path = tmp_path / "alerted.json"
    red_path = tmp_path / "red.json"
    monkeypatch.setattr(qs, "BUDGET_FILE", budget_path)
    monkeypatch.setattr(qs, "ALERTED_FILE", alerted_path)
    monkeypatch.setattr(qs, "RED_FILE", red_path)

    def fake_candidates(repo=qs.REPO):
        return [_pr(number=503, head_sha="shaX", head_ref_name="agent/x/y/z")]

    def fake_ejection(repo, number):
        return {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaX"}

    def fake_infra_hint_and_fingerprint(repo, number, removed_at):
        return True, None

    def never_rearm(repo, number):
        raise AssertionError("--dry-run must never call gh pr merge")

    monkeypatch.setattr(qs, "fetch_open_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", fake_infra_hint_and_fingerprint)
    monkeypatch.setattr(qs, "rearm_pr", never_rearm)

    rearmed = qs.run_rearm_pass(dry_run=True, now=NOW)["rearmed"]

    assert rearmed == 1  # counted as "would rearm"
    assert not budget_path.exists()
    assert not alerted_path.exists()
    assert not red_path.exists()


def test_rearm_pass_fetch_failure_is_cannot_verify_never_reads_as_nothing_to_do(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def boom(repo=qs.REPO):
        raise RuntimeError("gh api graphql failed rc=1")

    monkeypatch.setattr(qs, "fetch_open_prs", boom)
    rearmed = qs.run_rearm_pass(dry_run=False, now=NOW)["rearmed"]
    assert rearmed == 0


# ── refuter round (agy pass, 2026-08-27): 6 findings, verified against real code ────────────


# 1. _run_has_infra_signature: CODE wins over fail-fast-cancelled siblings.


def test_infra_signature_guilt_run_conclusion_cancelled_with_no_jobs_is_infra():
    # No job ran at all (a run cancelled before any job started legitimately has zero jobs — a
    # FAILED jobs fetch is a different case entirely and now raises, see B1) but the run's OWN
    # conclusion is cancelled/timed_out -> still INFRA, nothing here contradicts it.
    assert qs._run_has_infra_signature({"conclusion": "cancelled"}, []) is True


def test_infra_signature_innocence_a_real_code_failure_wins_even_with_a_cancelled_sibling():
    # Fail-fast: one job fails for a real reason, the matrix cancels its siblings. The run must
    # classify as CODE, not INFRA — a cancelled sibling is a SYMPTOM of the real failure here,
    # not an infra signal of its own.
    run = {"conclusion": "failure"}
    jobs = [
        {"name": "Backend Shard 1", "conclusion": "failure"},  # real code failure
        {"name": "Backend Shard 2", "conclusion": "cancelled"},  # fail-fast cascade victim
    ]
    assert qs._run_has_infra_signature(run, jobs) is False


def test_infra_signature_guilt_cancelled_only_with_no_real_failure_stays_infra():
    run = {"conclusion": "failure"}
    jobs = [
        {"name": "Backend Shard 1", "conclusion": "cancelled"},
        {"name": "Backend Shard 2", "conclusion": "cancelled"},
    ]
    assert qs._run_has_infra_signature(run, jobs) is True


def test_infra_signature_guilt_infra_named_job_failure_is_still_infra():
    run = {"conclusion": "failure"}
    jobs = [{"name": "Set up job", "conclusion": "failure"}]
    assert qs._run_has_infra_signature(run, jobs) is True


# 2. fetch_infra_hint: merge_group head_branch matching (gh-readonly-queue prefix, not bare pr-N-).


# ── B1 (Codex review, 2026-09-11): a failed read must never become INFRA ────────────────────


def test_fetch_infra_hint_and_fingerprint_runs_fetch_failure_raises(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 1, "", "gh: HTTP 502"

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, None)


def test_fetch_infra_hint_and_fingerprint_jobs_fetch_failure_raises_never_defaults_to_infra(monkeypatch):
    sha = "a" * 40
    runs_payload = {
        "workflow_runs": [
            {
                "id": 999,
                "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
                "conclusion": "cancelled",
                "created_at": _iso(NOW),
            }
        ]
    }

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 1, "", "gh: HTTP 500"
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))


def test_fetch_infra_hint_and_fingerprint_innocence_no_correlated_run_stays_none_none(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, '{"workflow_runs": []}', ""

    monkeypatch.setattr(qs, "_run", fake_run)
    assert qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, None) == (None, None)


# ── H1 (S1 spec R2): runs list wrong-shape raises, {"workflow_runs": []} stays legitimate ──────


def test_fetch_infra_hint_and_fingerprint_runs_wrong_shape_raises_H1(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, "{}", ""  # no "workflow_runs" key at all — the read contract's guilt case

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, None)


def test_fetch_infra_hint_and_fingerprint_runs_not_a_list_raises_H1(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, '{"workflow_runs": {}}', ""  # a dict, not a list

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, None)


# ── H2 (S1 spec R2): jobs list wrong-shape raises, {"jobs": []} stays legitimate ────────────────


def test_fetch_infra_hint_and_fingerprint_jobs_null_raises_H2(monkeypatch):
    sha = "e" * 40
    runs_payload = {
        "workflow_runs": [
            {
                "id": 1000,
                "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
                "conclusion": "cancelled",
                "created_at": _iso(NOW),
            }
        ]
    }

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 0, '{"jobs": null}', ""
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))


def test_fetch_infra_hint_and_fingerprint_jobs_empty_list_is_legitimate_H2(monkeypatch):
    sha = "e" * 40
    runs_payload = {
        "workflow_runs": [
            {
                "id": 1001,
                "head_branch": f"gh-readonly-queue/main/pr-502-{sha}",
                "conclusion": "cancelled",
                "created_at": _iso(NOW),
            }
        ]
    }

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 0, '{"jobs": [], "total_count": 0}', ""
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    infra, fp = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 502, _iso(NOW))
    assert infra is True  # legitimately empty jobs on a cancelled run -> still infra, never raises


def test_fetch_infra_hint_propagates_the_raise(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 1, "", "gh: HTTP 502"

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint("Bali-Zero/Teman2", 501, None)


def test_fetch_infra_hint_matches_full_gh_readonly_queue_branch_name(monkeypatch):
    sha = "a" * 40
    runs_payload = {
        "workflow_runs": [
            {
                "id": 999,
                "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
                "conclusion": "failure",
                "created_at": _iso(NOW),
            }
        ]
    }

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 0, '{"jobs": [{"name": "Backend Shard 1", "conclusion": "failure"}], "total_count": 1}', ""
        return 0, __import__("json").dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    result = qs.fetch_infra_hint("Bali-Zero/Teman2", 501, _iso(NOW))
    assert result is False  # real code failure, not infra-flavoured -> resolved, not None


def test_fetch_infra_hint_innocence_a_different_pr_number_is_not_matched(monkeypatch):
    sha = "a" * 40
    runs_payload = {
        "workflow_runs": [
            {
                "id": 999,
                "head_branch": f"gh-readonly-queue/main/pr-45-{sha}",  # PR #45, not #4 or #451
                "conclusion": "failure",
                "created_at": _iso(NOW),
            }
        ]
    }

    def fake_run(cmd, timeout=30):
        return 0, __import__("json").dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    assert qs.fetch_infra_hint("Bali-Zero/Teman2", 4, _iso(NOW)) is None
    assert qs.fetch_infra_hint("Bali-Zero/Teman2", 451, _iso(NOW)) is None


# ── _expect_list / _expect_pull_requests_page (H, S1 spec R2): the read-contract helpers ───────


def test_expect_list_guilt_non_dict_raises():
    with pytest.raises(RuntimeError):
        qs._expect_list([], "workflow_runs", "where")


def test_expect_list_guilt_key_not_a_list_raises():
    with pytest.raises(RuntimeError):
        qs._expect_list({"workflow_runs": {}}, "workflow_runs", "where")


def test_expect_list_innocence_empty_list_is_legitimate():
    assert qs._expect_list({"workflow_runs": []}, "workflow_runs", "where") == []


def test_expect_pull_requests_page_guilt_missing_pageinfo_raises_H3():
    data = {"data": {"repository": {"pullRequests": {"nodes": []}}}}
    with pytest.raises(RuntimeError):
        qs._expect_pull_requests_page(data, "where")


def test_expect_pull_requests_page_guilt_has_next_page_without_end_cursor_raises_H3():
    data = {
        "data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": True, "endCursor": None}, "nodes": [],
        }}}
    }
    with pytest.raises(RuntimeError):
        qs._expect_pull_requests_page(data, "where")


def test_expect_pull_requests_page_innocence_empty_nodes_is_legitimate_H3():
    data = {
        "data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [],
        }}}
    }
    page = qs._expect_pull_requests_page(data, "where")
    assert page["nodes"] == []


def test_fetch_open_pr_heads_wrong_shape_raises_no_retry_H4(monkeypatch):
    calls = {"n": 0}

    def fake_gh_graphql(query, variables, timeout=45):
        calls["n"] += 1
        return {"data": {"repository": {"pullRequests": {"nodes": []}}}}  # missing pageInfo

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    with pytest.raises(RuntimeError):
        qs.fetch_open_pr_heads("Bali-Zero/Teman2")
    assert calls["n"] == 1  # no retry added at this site (unlike _fetch_candidates_page)


def test_fetch_open_pr_heads_innocence_empty_nodes_is_legitimate_H4(monkeypatch):
    payload = {
        "data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [],
        }}}
    }
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)
    assert qs.fetch_open_pr_heads("Bali-Zero/Teman2") == set()


# ── H6: fetch_queued_runs / fetch_live_queue_branches wrong-shape raises ────────────────────────


def test_fetch_queued_runs_wrong_shape_raises_H6(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, "{}", ""  # no "workflow_runs" key

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_queued_runs("Bali-Zero/Teman2")


def test_fetch_queued_runs_empty_list_is_legitimate_H6(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, '{"workflow_runs": []}', ""

    monkeypatch.setattr(qs, "_run", fake_run)
    assert qs.fetch_queued_runs("Bali-Zero/Teman2") == []


def test_fetch_live_queue_branches_wrong_shape_raises_H6(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, "{}", ""  # a dict, not the bare list this endpoint actually returns

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_live_queue_branches("Bali-Zero/Teman2")


def test_fetch_live_queue_branches_empty_list_is_legitimate_H6(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, "[]", ""

    monkeypatch.setattr(qs, "_run", fake_run)
    assert qs.fetch_live_queue_branches("Bali-Zero/Teman2") == set()


# ── H5: fetch_last_ejection timeline nodes wrong-shape raises ──────────────────────────────────


def test_fetch_last_ejection_timeline_nodes_null_raises_H5(monkeypatch):
    payload = {"data": {"repository": {"pullRequest": {"timelineItems": {"nodes": None}}}}}
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)
    with pytest.raises(RuntimeError):
        qs.fetch_last_ejection("Bali-Zero/Teman2", 5838)


# ── I (S1 spec R2): one queue attempt correlation ───────────────────────────────────────────────


def test_fetch_infra_hint_and_fingerprint_removed_at_none_omits_created_param_If(monkeypatch):
    urls = []

    def fake_run(cmd, timeout=30):
        urls.append(cmd[-1])
        return 0, '{"workflow_runs": []}', ""

    monkeypatch.setattr(qs, "_run", fake_run)
    qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, None)
    assert "created=" not in urls[0]
    assert "per_page=100" in urls[0]


def test_fetch_infra_hint_and_fingerprint_finds_correlated_run_behind_25_other_pr_runs_Ia(monkeypatch):
    sha = "f" * 40
    other_runs = [
        {
            "id": 9000 + i,
            "head_branch": f"gh-readonly-queue/main/pr-{9000 + i}-{'0' * 40}",
            "conclusion": "failure",
            "created_at": _iso(NOW + _dt.timedelta(seconds=i)),
        }
        for i in range(25)
    ]
    correlated = {
        "id": 501501,
        "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "failure",
        "created_at": _iso(NOW),
        "head_sha": sha,
    }
    runs_payload = {"workflow_runs": other_runs + [correlated], "total_count": len(other_runs) + 1}

    urls = []

    def fake_run(cmd, timeout=30):
        urls.append(cmd[-1])
        if "jobs" in cmd[-1]:
            return 0, '{"jobs": [{"name": "pytest", "conclusion": "failure"}], "total_count": 1}', ""
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    infra, fp = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))

    assert infra is False  # real pytest failure -> CODE, the correlated run WAS found
    runs_url = urls[0]
    assert "per_page=100" in runs_url
    assert f"created=<={_iso(NOW)}" in runs_url


def test_fetch_infra_hint_and_fingerprint_attempt_two_runs_code_wins_both_orders_Ib(monkeypatch):
    sha = "1" * 40
    run_a = {
        "id": 111, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "failure", "created_at": _iso(NOW), "head_sha": sha,
    }
    run_b = {
        "id": 112, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }

    def make_fake_run(order):
        runs_payload = {"workflow_runs": order, "total_count": len(order)}

        def fake_run(cmd, timeout=30):
            if "runs/111/jobs" in cmd[-1]:
                return 0, '{"jobs": [{"name": "pytest", "conclusion": "failure"}], "total_count": 1}', ""
            if "runs/112/jobs" in cmd[-1]:
                return 0, '{"jobs": [], "total_count": 0}', ""
            return 0, json.dumps(runs_payload), ""

        return fake_run

    monkeypatch.setattr(qs, "_run", make_fake_run([run_a, run_b]))
    infra1, fp1 = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))

    monkeypatch.setattr(qs, "_run", make_fake_run([run_b, run_a]))
    infra2, fp2 = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))

    assert infra1 is False and infra2 is False
    assert fp1 == fp2
    assert fp1 is not None


def test_fetch_infra_hint_and_fingerprint_attempt_all_cancelled_is_infra_true_Ic(monkeypatch):
    sha = "2" * 40
    run_a = {
        "id": 201, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    run_b = {
        "id": 202, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    runs_payload = {"workflow_runs": [run_a, run_b], "total_count": 2}

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 0, '{"jobs": [], "total_count": 0}', ""
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    infra, fp = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))
    assert infra is True


def test_fetch_infra_hint_and_fingerprint_second_run_jobs_failure_raises_Id(monkeypatch):
    sha = "3" * 40
    run_a = {
        "id": 301, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    run_b = {
        "id": 302, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    runs_payload = {"workflow_runs": [run_a, run_b], "total_count": 2}

    def fake_run(cmd, timeout=30):
        if "runs/301/jobs" in cmd[-1]:
            return 0, '{"jobs": [], "total_count": 0}', ""
        if "runs/302/jobs" in cmd[-1]:
            return 1, "", "gh: HTTP 500"
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))


def test_fetch_infra_hint_and_fingerprint_older_attempt_not_mixed_in_Ie(monkeypatch):
    sha_new = "4" * 40
    sha_old = "5" * 40
    newer = {
        "id": 401, "head_branch": f"gh-readonly-queue/main/pr-501-{sha_new}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha_new,
        "name": "attempt-newer",
    }
    older_failure = {
        "id": 400, "head_branch": f"gh-readonly-queue/main/pr-501-{sha_old}",
        "conclusion": "failure", "created_at": _iso(NOW - _dt.timedelta(minutes=30)),
        "head_sha": sha_old, "name": "attempt-older",
    }
    older_cancelled = {  # J3 (S1 spec R3, Kimi finding 6): a second older-attempt run
        "id": 402, "head_branch": f"gh-readonly-queue/main/pr-501-{sha_old}",
        "conclusion": "cancelled", "created_at": _iso(NOW - _dt.timedelta(minutes=30)),
        "head_sha": sha_old, "name": "attempt-older",
    }
    all_runs = (older_failure, older_cancelled, newer)
    first_read_payload = {"workflow_runs": list(all_runs)}

    fetched_jobs_urls = []

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        if "jobs" in url:
            fetched_jobs_urls.append(url)
            return 0, '{"jobs": [], "total_count": 0}', ""
        if "head_sha=" in url:
            # J1 per-sha re-read: the real endpoint scopes server-side by head_sha.
            sha = url.split("head_sha=")[1].split("&")[0]
            matched = [r for r in all_runs if r["head_sha"] == sha]
            return 0, json.dumps({"workflow_runs": matched, "total_count": len(matched)}), ""
        return 0, json.dumps(first_read_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    infra, fp = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))

    assert infra is True  # only the newer attempt (cancelled, empty jobs) counts
    assert len(fetched_jobs_urls) == 1
    assert "runs/401/jobs" in fetched_jobs_urls[0]  # the older attempt's runs never fetched
    assert "attempt-newer" in fp
    assert "attempt-older" not in fp  # J3: the fingerprint names only the newer attempt's runs


# ── J (S1 spec R3): re-read the attempt by head_sha (J1) + jobs read-completeness (J2) ──────────


def test_fetch_infra_hint_and_fingerprint_first_read_page_cut_per_sha_finds_failure_J1a(monkeypatch):
    sha = "6" * 40
    cancelled_sibling = {
        "id": 601, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    failure_run = {
        "id": 600, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "failure", "created_at": _iso(NOW), "head_sha": sha,
    }
    # first read: page cut -> only the cancelled sibling survives, the real failure run is
    # "beyond the page" (Kimi F1 BLOCKER, measured live 2026-09-10).
    first_read_payload = {"workflow_runs": [cancelled_sibling]}
    # per-sha re-read: the real attempt, complete.
    per_sha_payload = {"workflow_runs": [cancelled_sibling, failure_run], "total_count": 2}

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        if "runs/600/jobs" in url:
            return 0, '{"jobs": [{"name": "pytest", "conclusion": "failure"}], "total_count": 1}', ""
        if "runs/601/jobs" in url:
            return 0, '{"jobs": [], "total_count": 0}', ""
        if f"head_sha={sha}" in url:
            return 0, json.dumps(per_sha_payload), ""
        return 0, json.dumps(first_read_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    infra, fp = qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))

    assert infra is False  # the real pytest failure surfaces once the per-sha re-read finds it
    assert fp is not None and "pytest" in fp


def test_fetch_infra_hint_and_fingerprint_per_sha_total_count_exceeds_len_raises_J1b(monkeypatch):
    sha = "7" * 40
    run = {
        "id": 700, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    first_read_payload = {"workflow_runs": [run]}
    per_sha_payload = {"workflow_runs": [run], "total_count": 5}  # more than the 1 run returned

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        if "jobs" in url:  # a legit answer here, so a pre-fix "no raise" is a genuine red
            return 0, '{"jobs": [], "total_count": 0}', ""
        if f"head_sha={sha}" in url:
            return 0, json.dumps(per_sha_payload), ""
        return 0, json.dumps(first_read_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))


def test_fetch_infra_hint_and_fingerprint_per_sha_read_failure_raises_J1c(monkeypatch):
    sha = "8" * 40
    run = {
        "id": 800, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    first_read_payload = {"workflow_runs": [run]}

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        if "jobs" in url:  # a legit answer here, so a pre-fix "no raise" is a genuine red
            return 0, '{"jobs": [], "total_count": 0}', ""
        if f"head_sha={sha}" in url:
            return 1, "", "gh: HTTP 502"
        return 0, json.dumps(first_read_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))


def test_fetch_infra_hint_and_fingerprint_per_sha_url_shape_J1e(monkeypatch):
    sha = "9" * 40
    run = {
        "id": 900, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    first_read_payload = {"workflow_runs": [run]}
    per_sha_payload = {"workflow_runs": [run], "total_count": 1}
    urls = []

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        urls.append(url)
        if "jobs" in url:
            return 0, '{"jobs": [], "total_count": 0}', ""
        if "head_sha=" in url:
            return 0, json.dumps(per_sha_payload), ""
        return 0, json.dumps(first_read_payload), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    qs.fetch_infra_hint_and_fingerprint("Bali-Zero/Teman2", 501, _iso(NOW))

    per_sha_url = urls[1]  # urls[0] is the first (unscoped) read
    assert "event=merge_group" in per_sha_url
    assert f"head_sha={sha}" in per_sha_url
    assert "per_page=100" in per_sha_url


def test_tick_scenario_a_classifies_code_rearmed_zero_no_cannot_verify_J1d(monkeypatch, tmp_path):
    """J1(d): tick level, scenario (a) — the page-cut first read would have misread this PR's
    ejection as INFRA (a re-arm on a fabricated verdict); the per-sha re-read must classify it
    CODE instead, so run_rearm_pass never re-arms it and never CANNOT-VERIFYs the tick."""
    sha = "b" * 40
    cancelled_sibling = {
        "id": 1001, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "cancelled", "created_at": _iso(NOW), "head_sha": sha,
    }
    failure_run = {
        "id": 1000, "head_branch": f"gh-readonly-queue/main/pr-501-{sha}",
        "conclusion": "failure", "created_at": _iso(NOW), "head_sha": sha,
    }
    first_read_payload = {"workflow_runs": [cancelled_sibling]}
    per_sha_payload = {"workflow_runs": [cancelled_sibling, failure_run], "total_count": 2}

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        if "runs/1000/jobs" in url:
            return 0, '{"jobs": [{"name": "pytest", "conclusion": "failure"}], "total_count": 1}', ""
        if "runs/1001/jobs" in url:
            return 0, '{"jobs": [], "total_count": 0}', ""
        if f"head_sha={sha}" in url:
            return 0, json.dumps(per_sha_payload), ""
        return 0, json.dumps(first_read_payload), ""

    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=501, head_sha=sha, head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {
            "reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": sha
        },
    )
    monkeypatch.setattr(qs, "_run", fake_run)
    alerts = []
    monkeypatch.setattr(qs, "send_telegram", lambda message, dedup_key="": alerts.append(dedup_key) or True)

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["cannot_verify"] is None
    assert result["rearmed"] == 0
    assert alerts == []


def test_fetch_run_jobs_total_count_exceeds_len_raises_J2a(monkeypatch):
    def fake_run(cmd, timeout=30):
        jobs = [{"name": f"job{i}", "conclusion": "success"} for i in range(50)]
        return 0, json.dumps({"jobs": jobs, "total_count": 60}), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs._fetch_run_jobs("Bali-Zero", "Teman2", 123)


def test_fetch_run_jobs_total_count_missing_raises_J2b(monkeypatch):
    def fake_run(cmd, timeout=30):
        return 0, '{"jobs": []}', ""

    monkeypatch.setattr(qs, "_run", fake_run)
    with pytest.raises(RuntimeError):
        qs._fetch_run_jobs("Bali-Zero", "Teman2", 123)


def test_fetch_run_jobs_total_count_equals_len_is_fine_J2c(monkeypatch):
    urls = []

    def fake_run(cmd, timeout=30):
        urls.append(cmd[-1])
        jobs = [{"name": f"job{i}", "conclusion": "success"} for i in range(60)]
        return 0, json.dumps({"jobs": jobs, "total_count": 60}), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    result = qs._fetch_run_jobs("Bali-Zero", "Teman2", 123)
    assert len(result) == 60
    assert "per_page=100" in urls[0]


# 3. _save_json atomic write + _load_json fail-closed on a corrupt (not merely absent) file.


def test_save_json_leaves_no_tmp_file_behind_and_content_is_correct(tmp_path):
    path = tmp_path / "state" / "budget.json"
    qs._save_json(path, {"a": 1})
    assert qs._load_json(path) == {"a": 1}
    leftovers = list(path.parent.glob("*.tmp*"))
    assert leftovers == []


def test_load_json_missing_file_is_empty_dict_normal_first_run(tmp_path):
    assert qs._load_json(tmp_path / "does-not-exist.json") == {}


def test_load_json_corrupt_file_raises_never_silently_returns_empty(tmp_path):
    path = tmp_path / "budget.json"
    path.write_text('{"501": {"infra_rearm_timestamps": [', encoding="utf-8")  # torn write
    import pytest as _pytest

    with _pytest.raises(RuntimeError):
        qs._load_json(path)


def test_rearm_pass_corrupt_budget_file_fails_closed_no_rearm(monkeypatch, tmp_path):
    budget_path = tmp_path / "budget.json"
    budget_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(qs, "BUDGET_FILE", budget_path)
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")

    def never_called(*a, **k):
        raise AssertionError("must never fetch candidates when state is unreadable")

    monkeypatch.setattr(qs, "fetch_open_prs", never_called)

    rearmed = qs.run_rearm_pass(dry_run=False, now=NOW)["rearmed"]

    assert rearmed == 0
    # the corrupt file must be left as-is (never overwritten with a fresh empty state)
    assert budget_path.read_text(encoding="utf-8") == "{not json"


# 4. send_telegram: alerted_state recorded only on a successful send.


def test_rearm_pass_unknown_alert_not_recorded_when_send_telegram_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    alerted_path = tmp_path / "alerted.json"
    monkeypatch.setattr(qs, "ALERTED_FILE", alerted_path)
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_candidates(repo=qs.REPO):
        return [_pr(number=601, head_sha="shaUNK2", head_ref_name="agent/x/y/z")]

    def fake_ejection(repo, number):
        return None

    send_attempts = []

    def failing_send_telegram(message, dedup_key=""):
        send_attempts.append(dedup_key)
        return False  # transient gateway/network failure

    def never_rearm(repo, number):
        raise AssertionError("must never rearm an UNKNOWN ejection")

    monkeypatch.setattr(qs, "fetch_open_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "send_telegram", failing_send_telegram)
    monkeypatch.setattr(qs, "rearm_pr", never_rearm)

    qs.run_rearm_pass(dry_run=False, now=NOW)
    qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=10))

    # a failed send must NEVER be recorded as delivered -> retried on every subsequent tick,
    # never permanently swallowed.
    assert len(send_attempts) == 2
    saved_alerted = qs._load_json(alerted_path)
    assert saved_alerted == {}


# 5. fetch_live_queue_branches: pagination beyond the API's 30/100-per-page default.


def test_fetch_live_queue_branches_paginates_past_first_page(monkeypatch):
    page1_refs = [{"ref": f"refs/heads/gh-readonly-queue/main/pr-{i}-{'a' * 40}"} for i in range(100)]
    page2_refs = [{"ref": f"refs/heads/gh-readonly-queue/main/pr-{200 + i}-{'b' * 40}"} for i in range(5)]

    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        url = cmd[-1]
        if "page=2" in url:
            return 0, __import__("json").dumps(page2_refs), ""
        return 0, __import__("json").dumps(page1_refs), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    branches = qs.fetch_live_queue_branches("Bali-Zero/Teman2")

    assert len(branches) == 105  # 100 from page 1 + 5 from page 2 — nothing dropped past page 1
    assert len(calls) == 2
    assert any(b.startswith("gh-readonly-queue/main/pr-204-") for b in branches)  # page-2 survived


def test_fetch_live_queue_branches_innocence_single_short_page_makes_one_call(monkeypatch):
    refs = [{"ref": f"refs/heads/gh-readonly-queue/main/pr-1-{'c' * 40}"}]
    calls = []

    def fake_run(cmd, timeout=30):
        calls.append(cmd)
        return 0, __import__("json").dumps(refs), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    branches = qs.fetch_live_queue_branches("Bali-Zero/Teman2")
    assert len(branches) == 1
    assert len(calls) == 1  # under 100 results -> no second page fetched


# 6. _parse_iso: always returns an aware datetime (or None), never a naive one that would crash
#    on comparison against an aware cutoff.


def test_parse_iso_z_suffix_is_aware():
    parsed = qs._parse_iso("2026-08-27T10:00:00Z")
    assert parsed.tzinfo is not None


def test_parse_iso_naive_input_is_coerced_to_aware_utc_never_crashes_on_compare():
    parsed = qs._parse_iso("2026-08-27T10:00:00")  # no Z, no offset
    assert parsed is not None
    assert parsed.tzinfo is not None
    # this comparison used to raise TypeError: can't compare offset-naive and offset-aware
    assert parsed <= NOW


def test_parse_iso_invalid_string_is_none_not_a_crash():
    assert qs._parse_iso("not-a-timestamp") is None


def test_parse_iso_none_and_empty_are_none():
    assert qs._parse_iso(None) is None
    assert qs._parse_iso("") is None


# ── quarantine (2026-08-31, squad-S / issue #5316): consecutive-failure threshold ───────────
# See queue_shepherd.py's module docstring QUARANTINE section for the live incident this
# responds to: 4 real run ids failing `cancel_run` with an identical HTTP 500 forever, because
# a "failed" outcome was never persisted anywhere.


def test_record_cancel_failure_innocence_two_consecutive_failed_is_not_quarantined():
    state: dict = {}
    state = qs.record_cancel_failure(state, "999", "failed", NOW)
    state = qs.record_cancel_failure(state, "999", "failed", NOW + _dt.timedelta(minutes=10))
    assert state["999"]["consecutive_failures"] == 2
    assert "quarantined_at" not in state["999"]
    assert qs.is_quarantined(state["999"], NOW + _dt.timedelta(minutes=20)) is False


def test_record_cancel_failure_guilt_third_consecutive_failed_quarantines():
    state: dict = {}
    for i in range(2):
        state = qs.record_cancel_failure(state, "999", "failed", NOW + _dt.timedelta(minutes=i))
    state = qs.record_cancel_failure(state, "999", "failed", NOW + _dt.timedelta(minutes=2))
    assert state["999"]["consecutive_failures"] == 3 == qs.UNCANCELLABLE_FAILURE_THRESHOLD
    assert state["999"]["quarantined_at"] == _iso(NOW + _dt.timedelta(minutes=2))
    assert qs.is_quarantined(state["999"], NOW + _dt.timedelta(minutes=3)) is True


def test_record_cancel_failure_guilt_single_uncancellable_409_quarantines_immediately():
    state = qs.record_cancel_failure({}, "42", "uncancellable_409", NOW)
    assert state["42"]["consecutive_failures"] == qs.UNCANCELLABLE_FAILURE_THRESHOLD
    assert state["42"]["quarantined_at"] == _iso(NOW)
    assert qs.is_quarantined(state["42"], NOW) is True


def test_record_cancel_failure_records_a_real_last_error_label_and_timestamp():
    failed_state = qs.record_cancel_failure({}, "1", "failed", NOW)
    assert failed_state["1"]["last_error"] == qs._UNCANCELLABLE_ERROR_LABELS["failed"]
    assert failed_state["1"]["last_attempt_at"] == _iso(NOW)
    conflict_state = qs.record_cancel_failure({}, "2", "uncancellable_409", NOW)
    assert conflict_state["2"]["last_error"] == qs._UNCANCELLABLE_ERROR_LABELS["uncancellable_409"]


def test_record_cancel_failure_uncancellable_409_never_lowers_an_already_higher_count():
    # 3 "failed" already recorded (count=3, already quarantined); a LATER uncancellable_409 on
    # the SAME id must never reset/lower the counter — max(existing, THRESHOLD), not overwrite.
    state: dict = {}
    for i in range(3):
        state = qs.record_cancel_failure(state, "7", "failed", NOW + _dt.timedelta(minutes=i))
    assert state["7"]["consecutive_failures"] == 3
    state = qs.record_cancel_failure(state, "7", "uncancellable_409", NOW + _dt.timedelta(hours=1))
    assert state["7"]["consecutive_failures"] == 3


def test_record_cancel_failure_never_mutates_the_input_dict():
    original: dict = {}
    result = qs.record_cancel_failure(original, "1", "failed", NOW)
    assert original == {}  # pure — mirrors record_infra_rearm's own no-mutation contract
    assert result != original


# ── clear_cancel_entry ───────────────────────────────────────────────────────


def test_clear_cancel_entry_guilt_removes_a_tracked_id():
    state = {"5": {"consecutive_failures": 2}}
    cleared = qs.clear_cancel_entry(state, "5")
    assert "5" not in cleared


def test_clear_cancel_entry_innocence_absent_id_is_a_harmless_noop():
    state = {"5": {"consecutive_failures": 2}}
    result = qs.clear_cancel_entry(state, "999")
    assert result == state
    assert "5" in result


# ── is_quarantined ────────────────────────────────────────────────────────────


def test_is_quarantined_innocence_no_entry_is_false():
    assert qs.is_quarantined(None, NOW) is False
    assert qs.is_quarantined({}, NOW) is False


def test_is_quarantined_innocence_below_threshold_no_quarantined_at_is_false():
    entry = {"consecutive_failures": 2}
    assert qs.is_quarantined(entry, NOW) is False


def test_is_quarantined_guilt_within_cooldown_is_true():
    entry = {"consecutive_failures": 3, "quarantined_at": _iso(NOW)}
    assert qs.is_quarantined(entry, NOW + _dt.timedelta(hours=1)) is True


def test_is_quarantined_innocence_past_cooldown_expires_and_allows_retry():
    entry = {"consecutive_failures": 3, "quarantined_at": _iso(NOW)}
    assert qs.is_quarantined(entry, NOW + _dt.timedelta(hours=25)) is False


def test_is_quarantined_malformed_timestamp_fails_open_to_retry_never_permanent_skip():
    # A quarantined_at this module cannot parse must never turn into a run skipped FOREVER
    # with no path back — fail toward "retry" (harmless: cancel_run just fails and re-quarantines
    # fresh), never toward "permanent silent skip" (the exact esiste!=armato failure mode).
    entry = {"consecutive_failures": 3, "quarantined_at": "not-a-timestamp"}
    assert qs.is_quarantined(entry, NOW) is False


# ── end-to-end: the LIVE incident (2026-08-31) — 4 real run ids, real HTTP 500 text ─────────

REAL_STUCK_RUN_IDS = (32217208723, 32217208752, 32217399769, 32212086540)


def test_janitor_quarantines_the_real_stuck_run_ids_after_three_ticks_no_more_log_spam(
    monkeypatch, tmp_path, caplog
):
    """BITE: reproduces the LIVE incident measured on Pro 2026-08-30/31
    (~/logs/queue-shepherd.log) verbatim — only `_run` (the subprocess boundary) is faked, so
    the REAL cancel_run() code path runs and produces the exact observed
    'gh: Failed to cancel workflow run (HTTP 500)' text for 4 real run ids, every tick, forever
    (this is what "failed" never being persisted anywhere actually looked like live). Runs 3
    real ticks (the quarantine threshold) and asserts the real WARNING log line repeats EVERY
    time (innocence: the threshold really is 3, not fewer) — then a 4th tick proves cancel_run
    is never re-invoked for any of the 4 ids and the log carries zero further
    'cancel_run(<id>) failed' lines for them (guilt: quarantine actually silences the repeat,
    which is the entire point of this PR)."""
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [
            {"id": rid, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}
            for rid in REAL_STUCK_RUN_IDS
        ]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()  # stale on discovery AND every recheck — these are genuinely dead runs

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    def fake_run(cmd, timeout=30):
        # cancel_run()'s FIRST (plain-cancel) attempt only — the exact live error text.
        return 1, "", "gh: Failed to cancel workflow run (HTTP 500)"

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "_run", fake_run)

    for tick_num in range(1, 4):  # ticks 1-3: every id still gets a real cancel_run attempt
        caplog.clear()
        with caplog.at_level("WARNING"):
            cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]
        assert cancelled == 0
        for rid in REAL_STUCK_RUN_IDS:
            assert (
                f"cancel_run({rid}) failed rc=1 err=gh: Failed to cancel workflow run (HTTP 500)"
                in caplog.text
            ), f"tick {tick_num} lost the real warning for {rid}"

    # Tick 4: all 4 ids are now quarantined.
    caplog.clear()
    with caplog.at_level("INFO"):
        cancelled_4 = qs.run_janitor_pass(dry_run=False)["cancelled"]

    assert cancelled_4 == 0
    assert "skipping 4 known-uncancellable runs" in caplog.text
    for rid in REAL_STUCK_RUN_IDS:
        assert f"cancel_run({rid}) failed" not in caplog.text

    saved = qs._load_json(qs.UNCANCELLABLE_FILE)
    assert len(saved) == 4
    for rid in REAL_STUCK_RUN_IDS:
        entry = saved[str(rid)]
        assert entry["consecutive_failures"] == qs.UNCANCELLABLE_FAILURE_THRESHOLD
        assert "quarantined_at" in entry
        assert entry["last_error"] == qs._UNCANCELLABLE_ERROR_LABELS["failed"]


def test_janitor_quarantine_expires_after_cooldown_and_a_successful_retry_clears_it(
    monkeypatch, tmp_path
):
    """Guilt+success: a quarantined id whose quarantined_at is more than
    UNCANCELLABLE_RETRY_COOLDOWN_HOURS in the past gets exactly one retry attempt; if it
    succeeds, the entry is cleared entirely — 'reset the counter if a later attempt succeeds'."""
    uncancellable_path = tmp_path / "uncancellable.json"
    old_ts = (
        qs._now() - _dt.timedelta(hours=qs.UNCANCELLABLE_RETRY_COOLDOWN_HOURS + 1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    qs._save_json(
        uncancellable_path,
        {"555": {"consecutive_failures": 5, "quarantined_at": old_ts, "last_error": "x", "last_attempt_at": old_ts}},
    )
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", uncancellable_path)

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 555, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    calls = []

    def fake_cancel_run(repo, run_id):
        calls.append(run_id)
        return True, "cancelled"

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", fake_cancel_run)

    cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]

    assert cancelled == 1
    assert calls == [555]  # the expired quarantine WAS retried, not skipped forever
    saved = qs._load_json(uncancellable_path)
    assert "555" not in saved  # cleared entirely on success


def test_janitor_quarantine_expires_but_a_failing_retry_re_quarantines_and_restarts_cooldown(
    monkeypatch, tmp_path
):
    """Innocence-of-permanence: an expired quarantine's retry that fails AGAIN must not be
    forgotten — it re-quarantines (refreshes quarantined_at to the NEW attempt), so the very
    next tick skips it again instead of retrying every tick from then on."""
    uncancellable_path = tmp_path / "uncancellable.json"
    old_ts = (
        qs._now() - _dt.timedelta(hours=qs.UNCANCELLABLE_RETRY_COOLDOWN_HOURS + 1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    qs._save_json(
        uncancellable_path,
        {"556": {"consecutive_failures": 5, "quarantined_at": old_ts, "last_error": "x", "last_attempt_at": old_ts}},
    )
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", uncancellable_path)

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 556, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    def fake_fetch_open_pr_heads(repo=qs.REPO):
        return set()

    def fake_fetch_live_queue_branches(repo=qs.REPO):
        return set()

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", fake_fetch_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", fake_fetch_live_queue_branches)
    monkeypatch.setattr(qs, "cancel_run", lambda repo, run_id: (False, "failed"))

    cancelled = qs.run_janitor_pass(dry_run=False)["cancelled"]
    assert cancelled == 0
    saved = qs._load_json(uncancellable_path)
    assert saved["556"]["quarantined_at"] != old_ts  # refreshed, not left stale
    assert qs.is_quarantined(saved["556"], qs._now()) is True  # freshly re-quarantined

    def never_called(repo, run_id):
        raise AssertionError("must not retry immediately after a fresh re-quarantine")

    monkeypatch.setattr(qs, "cancel_run", never_called)
    cancelled_2 = qs.run_janitor_pass(dry_run=False)["cancelled"]
    assert cancelled_2 == 0


# ── S1 letter A: dead checkRuns branch dropped, status-context gate detection intact ────────


def test_rearm_candidates_query_no_longer_requests_checksuites():
    assert "checkSuites" not in qs.REARM_CANDIDATES_QUERY


def test_pr_has_fable_gate_status_via_status_context_still_true():
    node = {
        "commits": {
            "nodes": [{"commit": {"status": {"contexts": [{"context": "harness/fable-gate"}]}}}]
        }
    }
    assert qs._pr_has_fable_gate_status(node) is True


def test_pr_has_fable_gate_status_innocence_no_matching_context_is_false():
    node = {
        "commits": {"nodes": [{"commit": {"status": {"contexts": [{"context": "ci/other"}]}}}]}
    }
    assert qs._pr_has_fable_gate_status(node) is False


# ── S1 letter B: one retry per candidate page, through the _sleep seam ──────────────────────


def test_candidate_page_retries_once_then_succeeds(monkeypatch):
    calls = {"n": 0}
    slept = []

    def fake_gh_graphql(query, variables, timeout=45):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("gh api graphql failed rc=1: Resource limits for this query exceeded")
        return {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [],
        }}}}

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    monkeypatch.setattr(qs, "_sleep", lambda s: slept.append(s))

    result = qs._fetch_candidates_page({"owner": "o", "repo": "r"})

    assert calls["n"] == 2
    assert slept == [qs.RETRY_BACKOFF_SECONDS]
    assert result["data"]["repository"]["pullRequests"]["nodes"] == []


def test_candidate_page_second_failure_raises_never_swallowed(monkeypatch):
    calls = {"n": 0}

    def fake_gh_graphql(query, variables, timeout=45):
        calls["n"] += 1
        raise RuntimeError(f"gh api graphql failed rc=1: attempt {calls['n']}")

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    monkeypatch.setattr(qs, "_sleep", lambda s: None)

    import pytest as _pytest

    with _pytest.raises(RuntimeError):
        qs._fetch_candidates_page({"owner": "o", "repo": "r"})
    assert calls["n"] == 2  # exactly one retry, not a loop


# ── S1 letter C: fetch_open_prs (unfiltered) vs fetch_rearm_candidate_prs (filtered) ────────


def _rearm_node(number, merge_state_status="DIRTY", head_ref_name="feature/human"):
    return {
        "number": number,
        "isDraft": False,
        "headRefName": head_ref_name,
        "headRefOid": f"sha{number}",
        "mergeStateStatus": merge_state_status,
        "autoMergeRequest": None,
        "mergeQueueEntry": None,
        "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}, "status": {"contexts": []}}}]},
    }


def test_fetch_open_prs_returns_every_open_pr_unfiltered(monkeypatch):
    payload = {
        "data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [
                _rearm_node(1, merge_state_status="DIRTY"),  # not a candidate
                _rearm_node(2, merge_state_status="CLEAN", head_ref_name="agent/x/y"),  # candidate
            ],
        }}}
    }
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)
    all_prs = qs.fetch_open_prs("Bali-Zero/Teman2")
    assert [pr["number"] for pr in all_prs] == [1, 2]  # the non-candidate DIRTY PR is NOT dropped


# ── S1 letter E: red_cause_fingerprint + red-state pure helpers ─────────────────────────────


def test_red_cause_fingerprint_no_correlated_run_is_none():
    assert qs.red_cause_fingerprint(None, []) is None


def test_red_cause_fingerprint_failed_jobs_sorted_and_joined():
    run = {"name": "CI"}
    jobs = [{"name": "b-job", "conclusion": "failure"}, {"name": "a-job", "conclusion": "timed_out"}]
    assert qs.red_cause_fingerprint(run, jobs) == "CI::a-job|b-job"


def test_red_cause_fingerprint_no_job_failure_but_run_cancelled_uses_run_level():
    run = {"name": "CI", "conclusion": "cancelled"}
    assert qs.red_cause_fingerprint(run, []) == "CI::run:cancelled"


def test_red_cause_fingerprint_innocence_no_job_detail_and_run_not_cancelled_is_none():
    run = {"name": "CI", "conclusion": "failure"}
    assert qs.red_cause_fingerprint(run, []) is None


# ── B3 (Codex review, 2026-09-11): same-cause counting must not lose events ─────────────────


def test_red_cause_fingerprint_cancelled_jobs_only_gives_non_none_fingerprint_before_run_level():
    # No job failed/timed_out for real, but two DID get cancelled (a fail-fast sibling of a red
    # this module never saw the real failure of) -> a job-level cancelled fingerprint, not the
    # coarser run-level fallback.
    run = {"name": "CI", "conclusion": "failure"}
    jobs = [{"name": "b-job", "conclusion": "cancelled"}, {"name": "a-job", "conclusion": "cancelled"}]
    assert qs.red_cause_fingerprint(run, jobs) == "CI::cancelled:a-job|b-job"


def test_record_red_dedups_by_removed_at():
    state: dict = {}
    state = qs.record_red(state, 42, "2026-09-10T00:00:00Z", "CI::a", "sha1")
    state = qs.record_red(state, 42, "2026-09-10T00:00:00Z", "CI::a", "sha1")  # same event again
    assert len(state["42"]["reds"]) == 1


def test_record_red_resolves_a_none_cause_to_a_real_cause_on_the_same_removed_at():
    state: dict = {}
    state = qs.record_red(state, 42, "2026-09-10T00:00:00Z", None, "sha1")  # tick N: unresolved
    state = qs.record_red(state, 42, "2026-09-10T00:00:00Z", "CI::a", "sha1")  # tick N+1: resolved
    reds = state["42"]["reds"]
    assert len(reds) == 1  # still one event, never a duplicate
    assert reds[0]["cause"] == "CI::a"


def test_record_red_never_downgrades_a_resolved_cause_back_to_none():
    state: dict = {}
    state = qs.record_red(state, 42, "2026-09-10T00:00:00Z", "CI::a", "sha1")
    state = qs.record_red(state, 42, "2026-09-10T00:00:00Z", None, "sha1")
    assert state["42"]["reds"][0]["cause"] == "CI::a"


def test_record_red_no_history_cap_keeps_more_than_the_old_ten_limit():
    state: dict = {}
    for i in range(15):
        state = qs.record_red(state, 42, f"2026-09-10T00:{i:02d}:00Z", f"cause-{i}", "sha1")
    assert len(state["42"]["reds"]) == 15  # nothing evicted


def test_count_same_cause_reds_none_cause_never_counts():
    reds = [{"cause": None}, {"cause": None}, {"cause": None}]
    assert qs.count_same_cause_reds(reds, None) == 0


def test_count_same_cause_reds_guilt_and_innocence():
    reds = [{"cause": "A"}, {"cause": "B"}, {"cause": "A"}]
    assert qs.count_same_cause_reds(reds, "A") == 2
    assert qs.count_same_cause_reds(reds, "B") == 1
    assert qs.count_same_cause_reds(reds, "C") == 0


def test_gc_red_state_drops_closed_pr_keeps_open():
    state = {"42": {"reds": []}, "99": {"reds": []}}
    gced = qs.gc_red_state(state, {42})
    assert "42" in gced
    assert "99" not in gced


# ── S1 letter E: run_rearm_pass end-to-end — same-cause suspension ──────────────────────────


def test_rearm_pass_three_A_reds_interleaved_with_ten_other_causes_suspend_on_third(monkeypatch, tmp_path):
    """B3(a) end-to-end: under the OLD RED_HISTORY_MAX=10 cap, 10 other-cause reds recorded
    BEFORE the 2 earlier "A" reds would have evicted them, losing the count. With no cap, the
    3rd live "A" red must still suspend."""
    red_path = tmp_path / "red.json"
    state: dict = {}
    for i in range(10):
        state = qs.record_red(state, 705, f"2026-09-10T00:{i:02d}:00Z", f"other-{i}", "shaI")
    state = qs.record_red(state, 705, "2026-09-10T00:20:00Z", "A", "shaI")
    state = qs.record_red(state, 705, "2026-09-10T00:21:00Z", "A", "shaI")
    qs._save_json(red_path, state)
    monkeypatch.setattr(qs, "RED_FILE", red_path)

    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=705, head_sha="shaI", head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {
            "reason": "failed_checks", "removed_at": "2026-09-10T00:22:00Z", "before_commit": "shaI"
        },
    )
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", lambda repo, number, removed_at: (True, "A"))

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["suspended"] == 1


def test_rearm_pass_three_cancelled_jobs_only_reds_suspend_on_third(monkeypatch, tmp_path):
    """B3(c) end-to-end: a run whose OWN conclusion isn't cancelled/timed_out but whose jobs are
    ALL cancelled still resolves a non-None fingerprint, and three of them still suspend."""
    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=706, head_sha="shaJ", head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)
    run = {"name": "CI", "conclusion": "failure"}
    jobs = [{"name": "b-job", "conclusion": "cancelled"}, {"name": "a-job", "conclusion": "cancelled"}]
    fp = qs.red_cause_fingerprint(run, jobs)
    assert fp is not None
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", lambda repo, number, removed_at: (False, fp))

    times = [NOW + _dt.timedelta(minutes=i) for i in range(3)]
    results = []
    for i in range(3):
        monkeypatch.setattr(
            qs, "fetch_last_ejection",
            lambda repo, number, i=i: {
                "reason": "failed_checks", "removed_at": _iso(times[i]), "before_commit": "shaJ"
            },
        )
        results.append(qs.run_rearm_pass(dry_run=False, now=times[i]))

    assert results[2]["suspended"] == 1


def test_rearm_pass_three_reds_same_cause_suspends_on_third_stays_suspended_on_fourth(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_open_prs(repo=qs.REPO):
        return [_pr(number=701, head_sha="shaR", head_ref_name="agent/x/y")]

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)
    # Same run+jobs every tick -> the SAME fingerprint each time.
    monkeypatch.setattr(
        qs, "fetch_infra_hint_and_fingerprint",
        lambda repo, number, removed_at: (True, "CI::job-a"),
    )

    times = [NOW + _dt.timedelta(minutes=i) for i in range(4)]

    def run_tick(i):
        monkeypatch.setattr(
            qs, "fetch_last_ejection",
            lambda repo, number, i=i: {
                "reason": "failed_checks", "removed_at": _iso(times[i]), "before_commit": "shaR"
            },
        )
        return qs.run_rearm_pass(dry_run=False, now=times[i])

    r1, r2 = run_tick(0), run_tick(1)
    assert r1["rearmed"] == 1 and r1["suspended"] == 0
    assert r2["rearmed"] == 1 and r2["suspended"] == 0

    r3 = run_tick(2)
    assert r3["rearmed"] == 0
    assert r3["suspended"] == 1
    saved = qs._load_json(qs.RED_FILE)
    assert saved["701"]["suspended"]["cause"] == "CI::job-a"

    # 4th tick: budget for (701, shaR) is only 2/3 used (tick 3 never recorded an infra rearm) —
    # a "fresh" budget by INFRA_BUDGET_MAX's own count — but the sticky suspension still wins.
    r4 = run_tick(3)
    assert r4["rearmed"] == 0
    assert r4["suspended"] == 1


def test_rearm_pass_three_reds_different_causes_never_suspends(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_open_prs(repo=qs.REPO):
        return [_pr(number=702, head_sha="shaD", head_ref_name="agent/x/y")]

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)

    times = [NOW + _dt.timedelta(minutes=i) for i in range(3)]
    causes = ["CI::job-a", "CI::job-b", "CI::job-c"]

    for i in range(3):
        monkeypatch.setattr(
            qs, "fetch_last_ejection",
            lambda repo, number, i=i: {
                "reason": "failed_checks", "removed_at": _iso(times[i]), "before_commit": "shaD"
            },
        )
        monkeypatch.setattr(
            qs, "fetch_infra_hint_and_fingerprint",
            lambda repo, number, removed_at, i=i: (True, causes[i]),
        )
        result = qs.run_rearm_pass(dry_run=False, now=times[i])
        assert result["rearmed"] == 1, f"tick {i} should still rearm, got {result}"
        assert result["suspended"] == 0


def test_rearm_pass_none_cause_reds_never_suspend(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_open_prs(repo=qs.REPO):
        return [_pr(number=703, head_sha="shaN", head_ref_name="agent/x/y")]

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)
    monkeypatch.setattr(
        qs, "fetch_infra_hint_and_fingerprint", lambda repo, number, removed_at: (None, None)
    )

    for i in range(4):
        removed_at = NOW + _dt.timedelta(minutes=i)
        monkeypatch.setattr(
            qs, "fetch_last_ejection",
            lambda repo, number, removed_at=removed_at: {
                "reason": "failed_checks", "removed_at": _iso(removed_at), "before_commit": "shaN"
            },
        )
        result = qs.run_rearm_pass(dry_run=False, now=removed_at)
        assert result["suspended"] == 0


def test_gc_red_state_drops_via_run_rearm_pass_after_a_pr_closes(monkeypatch, tmp_path):
    red_path = tmp_path / "red.json"
    qs._save_json(red_path, {"999": {"reds": [{"removed_at": "x", "cause": "c", "head_sha": "s"}]}})
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", red_path)
    monkeypatch.setattr(qs, "fetch_open_prs", lambda repo=qs.REPO: [])  # PR 999 no longer open

    qs.run_rearm_pass(dry_run=False, now=NOW)

    assert qs._load_json(red_path) == {}


# ── S1 letter F: never-queued is not an ejection ─────────────────────────────────────────────


def test_fetch_last_ejection_empty_timeline_is_never_queued_sentinel(monkeypatch):
    payload = {"data": {"repository": {"pullRequest": {"timelineItems": {"nodes": []}}}}}
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)
    assert qs.fetch_last_ejection("Bali-Zero/Teman2", 5838) == "NEVER_QUEUED"


def test_fetch_last_ejection_innocence_last_item_added_is_none_not_never_queued(monkeypatch):
    payload = {
        "data": {"repository": {"pullRequest": {"timelineItems": {
            "nodes": [{"__typename": "AddedToMergeQueueEvent", "createdAt": _iso(NOW)}]
        }}}}
    }
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)
    assert qs.fetch_last_ejection("Bali-Zero/Teman2", 6054) is None


def test_decide_rearm_never_queued_is_not_our_ejection():
    allowed, why = qs.decide_rearm("NEVER_QUEUED", {}, 1, "s", NOW)
    assert not allowed
    assert why == "never_queued_not_ours"


def test_rearm_pass_never_queued_never_rearms_and_never_alerts(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    def fake_candidates(repo=qs.REPO):
        return [_pr(number=5838, head_sha="shaNQ", head_ref_name="agent/x/y/z")]

    def never_called(*a, **k):
        raise AssertionError("a NEVER_QUEUED PR must never be alerted on or rearmed")

    monkeypatch.setattr(qs, "fetch_open_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", lambda repo, number: "NEVER_QUEUED")
    monkeypatch.setattr(qs, "send_telegram", never_called)
    monkeypatch.setattr(qs, "rearm_pr", never_called)

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["rearmed"] == 0
    assert result["cannot_verify"] is None


def test_rearm_pass_corrupt_red_file_fails_closed_no_rearm(monkeypatch, tmp_path):
    red_path = tmp_path / "red.json"
    red_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", red_path)

    def never_called(*a, **k):
        raise AssertionError("must never fetch candidates when red state is unreadable")

    monkeypatch.setattr(qs, "fetch_open_prs", never_called)

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["rearmed"] == 0
    assert result["cannot_verify"] == "rearm_state"
    assert red_path.read_text(encoding="utf-8") == "{not json"  # left as-is, never overwritten


def _no_op_janitor(monkeypatch):
    monkeypatch.setattr(qs, "fetch_queued_runs", lambda repo=qs.REPO: [])
    monkeypatch.setattr(qs, "fetch_open_pr_heads", lambda repo=qs.REPO: set())
    monkeypatch.setattr(qs, "fetch_live_queue_branches", lambda repo=qs.REPO: set())


# ── S1 letter D: CANNOT-VERIFY is a tick outcome, never a zero ──────────────────────────────


def test_tick_candidate_read_failure_is_cannot_verify_nonzero_rc_and_one_alert(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    monkeypatch.setattr(qs, "ORGANISM_DIR", tmp_path)
    _no_op_janitor(monkeypatch)

    def boom(repo=qs.REPO):
        raise RuntimeError("gh api graphql failed rc=1: Resource limits for this query exceeded")

    monkeypatch.setattr(qs, "fetch_open_prs", boom)

    alerts = []

    def fake_send_telegram(message, dedup_key=""):
        alerts.append(dedup_key)
        return True

    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)

    rc = qs.tick(dry_run=False)

    assert rc != 0
    hb = json.loads((tmp_path / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "error"
    assert "rearm_candidates" in hb["metadata"]["cannot_verify"]
    assert alerts == ["queue-shepherd:cannot-verify"]


def test_tick_candidate_read_failure_dry_run_is_nonzero_and_never_sends(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "ORGANISM_DIR", tmp_path)
    _no_op_janitor(monkeypatch)

    def boom(repo=qs.REPO):
        raise RuntimeError("gh api graphql failed rc=1")

    monkeypatch.setattr(qs, "fetch_open_prs", boom)

    def never_called(*_a, **_k):
        raise AssertionError("dry-run must never send telegram")

    monkeypatch.setattr(qs, "send_telegram", never_called)

    rc = qs.tick(dry_run=True)
    assert rc != 0


def test_tick_success_line_and_heartbeat_carry_examined_and_candidates(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    monkeypatch.setattr(qs, "ORGANISM_DIR", tmp_path)
    _no_op_janitor(monkeypatch)

    def fake_open_prs(repo=qs.REPO):
        return [
            _pr(number=1, head_sha="s1", head_ref_name="agent/a/b"),
            _pr(number=2, head_sha="s2", head_ref_name="feature/x", merge_state_status="DIRTY"),
        ]

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "s1"},
    )
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", lambda repo, number, removed_at: (True, None))
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)

    with caplog.at_level("INFO"):
        rc = qs.tick(dry_run=False)

    assert rc == 0
    assert "examined=2" in caplog.text
    assert "candidates=1" in caplog.text
    hb = json.loads((tmp_path / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "ok"
    assert hb["metadata"]["examined"] == 2
    assert hb["metadata"]["candidates"] == 1


# ── B2 (Codex review, 2026-09-11): every late read failure is CANNOT-VERIFY, never a quiet skip


def test_tick_rearm_pr_reads_failure_is_cannot_verify_rc2_heartbeat_error_one_send(monkeypatch, tmp_path):
    _no_op_janitor(monkeypatch)

    def fake_open_prs(repo=qs.REPO):
        return [_pr(number=9, head_sha="sha9", head_ref_name="agent/a/b")]

    def boom_ejection(repo, number):
        raise RuntimeError("gh api graphql failed rc=1: HTTP 502")

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(qs, "fetch_last_ejection", boom_ejection)
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: (_ for _ in ()).throw(AssertionError()))

    alerts = []

    def fake_send_telegram(message, dedup_key=""):
        alerts.append(dedup_key)
        return True

    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)

    rc = qs.tick(dry_run=False)

    assert rc == 2
    hb = json.loads((qs.ORGANISM_DIR / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "error"
    assert "rearm_pr_reads" in hb["metadata"]["cannot_verify"]
    assert alerts == ["queue-shepherd:cannot-verify"]  # exactly one send


def test_tick_rearm_pr_reads_failure_prints_real_examined_and_candidates(monkeypatch, tmp_path, caplog):
    _no_op_janitor(monkeypatch)

    def fake_open_prs(repo=qs.REPO):
        return [
            _pr(number=9, head_sha="sha9", head_ref_name="agent/a/b"),
            _pr(number=10, head_sha="sha10", head_ref_name="feature/x", merge_state_status="DIRTY"),
        ]

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: (_ for _ in ()).throw(RuntimeError("gh api graphql failed rc=1")),
    )
    monkeypatch.setattr(qs, "send_telegram", lambda message, dedup_key="": True)

    with caplog.at_level("ERROR"):
        rc = qs.tick(dry_run=False)

    assert rc == 2
    # examined/candidates ARE known (the list read itself succeeded) -> must print real numbers,
    # never "-" (that dash is reserved for rearm_candidates/rearm_state, the list-read failures).
    assert "examined=2" in caplog.text
    assert "candidates=1" in caplog.text
    assert "examined=-" not in caplog.text


def test_tick_janitor_recheck_failure_is_cannot_verify_rc2_heartbeat_error_one_send(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "fetch_open_prs", lambda repo=qs.REPO: [])  # rearm pass: clean, no-op

    def fake_fetch_queued_runs(repo=qs.REPO):
        return [{"id": 77, "event": "pull_request", "head_sha": "dead", "head_branch": None, "name": "CI"}]

    call_count = {"n": 0}

    def flaky_open_pr_heads(repo=qs.REPO):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return set()  # discovery: stale
        raise RuntimeError("gh api failed rc=1: HTTP 502")  # cancel-time recheck: fails

    monkeypatch.setattr(qs, "fetch_queued_runs", fake_fetch_queued_runs)
    monkeypatch.setattr(qs, "fetch_open_pr_heads", flaky_open_pr_heads)
    monkeypatch.setattr(qs, "fetch_live_queue_branches", lambda repo=qs.REPO: set())
    monkeypatch.setattr(qs, "cancel_run", lambda repo, run_id: (_ for _ in ()).throw(AssertionError()))

    alerts = []

    def fake_send_telegram(message, dedup_key=""):
        alerts.append(dedup_key)
        return True

    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)

    rc = qs.tick(dry_run=False)

    assert rc == 2
    hb = json.loads((qs.ORGANISM_DIR / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "error"
    assert "janitor_recheck" in hb["metadata"]["cannot_verify"]
    assert alerts == ["queue-shepherd:cannot-verify"]  # exactly one send, zero cancels happened


# ── B4 (Codex review, 2026-09-11): dry-run writes nothing, anywhere ─────────────────────────


def test_tick_dry_run_success_writes_no_heartbeat_and_no_log_file(monkeypatch):
    monkeypatch.setattr(qs, "fetch_open_prs", lambda repo=qs.REPO: [])
    monkeypatch.setattr(qs, "fetch_queued_runs", lambda repo=qs.REPO: [])
    monkeypatch.setattr(qs, "fetch_open_pr_heads", lambda repo=qs.REPO: set())
    monkeypatch.setattr(qs, "fetch_live_queue_branches", lambda repo=qs.REPO: set())

    rc = qs.tick(dry_run=True)

    assert rc == 0
    assert not (qs.ORGANISM_DIR / f"{qs.ORGAN_ID}.json").exists()
    assert not qs.LOG_FILE.exists()


def test_tick_dry_run_cannot_verify_writes_no_heartbeat_and_never_sends(monkeypatch):
    def boom(repo=qs.REPO):
        raise RuntimeError("gh api graphql failed rc=1")

    monkeypatch.setattr(qs, "fetch_open_prs", boom)
    monkeypatch.setattr(qs, "fetch_queued_runs", lambda repo=qs.REPO: [])
    monkeypatch.setattr(qs, "fetch_open_pr_heads", lambda repo=qs.REPO: set())
    monkeypatch.setattr(qs, "fetch_live_queue_branches", lambda repo=qs.REPO: set())

    def never_called(*_a, **_k):
        raise AssertionError("dry-run must never send telegram")

    monkeypatch.setattr(qs, "send_telegram", never_called)

    rc = qs.tick(dry_run=True)

    assert rc == 2
    assert not (qs.ORGANISM_DIR / f"{qs.ORGAN_ID}.json").exists()
    assert not qs.LOG_FILE.exists()


def test_main_dry_run_tick_creates_no_log_file(monkeypatch):
    monkeypatch.setattr(qs.logger, "handlers", [])  # force _configure_logging to actually run
    monkeypatch.setattr(qs, "fetch_open_prs", lambda repo=qs.REPO: [])
    monkeypatch.setattr(qs, "fetch_queued_runs", lambda repo=qs.REPO: [])
    monkeypatch.setattr(qs, "fetch_open_pr_heads", lambda repo=qs.REPO: set())
    monkeypatch.setattr(qs, "fetch_live_queue_branches", lambda repo=qs.REPO: set())

    rc = qs.main(["--tick", "--dry-run"])

    assert rc == 0
    assert not qs.LOG_FILE.exists()


def test_fetch_rearm_candidate_prs_filters_through_is_rearm_candidate(monkeypatch):
    payload = {
        "data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [
                _rearm_node(1, merge_state_status="DIRTY"),
                _rearm_node(2, merge_state_status="CLEAN", head_ref_name="agent/x/y"),
            ],
        }}}
    }
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)
    candidates = qs.fetch_rearm_candidate_prs("Bali-Zero/Teman2")
    assert [pr["number"] for pr in candidates] == [2]  # only the CLEAN agent/ PR survives


# ── H tick level (S1 spec R2): the Codex repro + candidate-page malformation at tick() level ───


def test_tick_codex_repro_cancelled_run_with_empty_jobs_object_is_cannot_verify_never_infra(
    monkeypatch, tmp_path
):
    """The exact Codex R2 repro this spec exists for: a cancelled correlated run whose jobs
    endpoint returns `{}` (no "jobs" key at all) must CANNOT-VERIFY the whole tick, never read
    as INFRA and never re-arm."""
    monkeypatch.setattr(qs, "UNCANCELLABLE_FILE", tmp_path / "uncancellable.json")
    _no_op_janitor(monkeypatch)

    def fake_open_prs(repo=qs.REPO):
        return [_pr(number=5900, head_sha="shaC", head_ref_name="agent/a/b")]

    def fake_ejection(repo, number):
        return {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaC"}

    sha = "d" * 40
    runs_payload = {
        "workflow_runs": [
            {
                "id": 4242,
                "head_branch": f"gh-readonly-queue/main/pr-5900-{sha}",
                "conclusion": "cancelled",
                "created_at": _iso(NOW),
            }
        ]
    }

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 0, "{}", ""  # the Codex repro: malformed, no "jobs" key
        return 0, json.dumps(runs_payload), ""

    monkeypatch.setattr(qs, "fetch_open_prs", fake_open_prs)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "_run", fake_run)
    monkeypatch.setattr(
        qs, "rearm_pr", lambda repo, number: (_ for _ in ()).throw(AssertionError("must never rearm"))
    )

    alerts = []
    monkeypatch.setattr(qs, "send_telegram", lambda message, dedup_key="": alerts.append(dedup_key) or True)

    rc = qs.tick(dry_run=False)

    assert rc == 2
    hb = json.loads((qs.ORGANISM_DIR / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "error"
    assert hb["metadata"]["cannot_verify"] == ["rearm_pr_reads"]
    assert alerts == ["queue-shepherd:cannot-verify"]


def test_tick_candidate_page_missing_pageinfo_on_both_attempts_is_cannot_verify_one_send(
    monkeypatch, tmp_path
):
    _no_op_janitor(monkeypatch)
    calls = {"n": 0}

    def fake_gh_graphql(query, variables, timeout=45):
        calls["n"] += 1
        return {"data": {"repository": {"pullRequests": {"nodes": []}}}}  # no pageInfo, ever

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    monkeypatch.setattr(qs, "_sleep", lambda s: None)

    alerts = []
    monkeypatch.setattr(qs, "send_telegram", lambda message, dedup_key="": alerts.append(dedup_key) or True)

    rc = qs.tick(dry_run=False)

    assert rc == 2
    assert calls["n"] == 2  # one retry, both malformed, then raise
    assert alerts == ["queue-shepherd:cannot-verify"]


def test_tick_candidate_page_malformed_once_then_good_is_success_no_alert(monkeypatch, tmp_path):
    _no_op_janitor(monkeypatch)
    calls = {"n": 0}

    def fake_gh_graphql(query, variables, timeout=45):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": {"repository": {"pullRequests": {"nodes": []}}}}  # missing pageInfo
        return {
            "data": {"repository": {"pullRequests": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [],
            }}}
        }

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    monkeypatch.setattr(qs, "_sleep", lambda s: None)
    monkeypatch.setattr(
        qs, "send_telegram",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("a successful tick must never alert")),
    )

    rc = qs.tick(dry_run=False)

    assert rc == 0
    assert calls["n"] == 2


# ── PWC conditions C2/C3/C4 of the #6127 final gate (2026-09-11) ────────────────────────────
# Each of these covers a guilt mutation the 159-test suite left GREEN (C2, C3) or a branch that
# is about to become live traffic without an innocence case (C4). See the PENDING-ARMS rows
# "PWC-CONDITIONS C2+C3 for #6127" and "PWC-CONDITIONS C4 for #6127".


def test_rearm_pass_fourth_red_with_a_DIFFERENT_cause_stays_suspended_C2(monkeypatch, tmp_path):
    """C2: the sticky `if existing_suspended:` branch, isolated from the `elif` that hides it.
    The pre-existing 4th-tick test reuses the SAME cause, so the elif re-suspends and the whole
    branch can be deleted with the suite still green. Here the 4th red carries a DIFFERENT
    fingerprint: count_same_cause_reds(new cause) == 1 < RED_SAME_CAUSE_LIMIT, so ONLY the sticky
    branch can keep the PR suspended — remove it and this tick re-arms."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=711, head_sha="shaS", head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: True)

    times = [NOW + _dt.timedelta(minutes=i) for i in range(4)]
    causes = ["CI::job-a", "CI::job-a", "CI::job-a", "CI::job-z"]  # 4th differs

    def run_tick(i):
        monkeypatch.setattr(
            qs, "fetch_last_ejection",
            lambda repo, number, i=i: {
                "reason": "failed_checks", "removed_at": _iso(times[i]), "before_commit": "shaS"
            },
        )
        monkeypatch.setattr(
            qs, "fetch_infra_hint_and_fingerprint",
            lambda repo, number, removed_at, i=i: (True, causes[i]),
        )
        return qs.run_rearm_pass(dry_run=False, now=times[i])

    assert run_tick(0)["rearmed"] == 1
    assert run_tick(1)["rearmed"] == 1
    r3 = run_tick(2)
    assert r3["rearmed"] == 0 and r3["suspended"] == 1

    r4 = run_tick(3)
    assert r4["rearmed"] == 0, "a suspended PR must stay suspended even when the new red differs"
    assert r4["suspended"] == 1
    saved = qs._load_json(qs.RED_FILE)
    assert saved["711"]["suspended"]["cause"] == "CI::job-a"  # the ORIGINAL cause, not the new one


def test_fetch_attempt_runs_by_head_sha_empty_match_raises_C3(monkeypatch):
    """C3, unit half: the per-sha re-read returning nothing that matches this PR must RAISE. The
    guard's absence is invisible at this level too — [] is a perfectly well-formed list."""
    other = {
        "id": 900, "head_branch": "gh-readonly-queue/main/pr-999-" + "3" * 40,
        "conclusion": "failure", "created_at": _iso(NOW), "head_sha": "3" * 40,
    }
    monkeypatch.setattr(
        qs, "_run",
        lambda cmd, timeout=30: (0, json.dumps({"workflow_runs": [other], "total_count": 1}), ""),
    )
    with pytest.raises(RuntimeError):
        qs._fetch_attempt_runs_by_head_sha("Bali-Zero", "Teman2", 501, "3" * 40, None)


def test_rearm_pass_empty_attempt_is_cannot_verify_never_a_fabricated_infra_rearm_C3(
    monkeypatch, tmp_path
):
    """C3, consequence half: `all([])` is True, so an empty attempt would fabricate infra=True
    and re-arm a CODE failure — exactly the class letter J exists to close. With the raise in
    place the tick is CANNOT-VERIFY and re-arms nothing; remove it and rearmed becomes 1."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    sha = "4" * 40
    first_read = {
        "id": 401, "head_branch": f"gh-readonly-queue/main/pr-712-{sha}",
        "conclusion": "failure", "created_at": _iso(NOW), "head_sha": sha,
    }

    def fake_run(cmd, timeout=30):
        url = cmd[-1]
        if "jobs" in url:
            return 0, '{"jobs": [{"name": "pytest", "conclusion": "failure"}], "total_count": 1}', ""
        if f"head_sha={sha}" in url:
            # the attempt's own re-read finds nothing for THIS PR (the run was re-run green, or
            # the ref moved) — a well-formed body that matches no attempt run
            return 0, json.dumps({"workflow_runs": [], "total_count": 0}), ""
        return 0, json.dumps({"workflow_runs": [first_read], "total_count": 1}), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=712, head_sha=sha, head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {
            "reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": sha
        },
    )
    monkeypatch.setattr(
        qs, "rearm_pr",
        lambda repo, number: (_ for _ in ()).throw(
            AssertionError("an unreadable attempt must never re-arm")
        ),
    )

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["rearmed"] == 0
    assert result["unverified"] == 1
    assert result["cannot_verify"] == "rearm_pr_reads"


def test_fetch_open_prs_walks_two_real_pages_C4(monkeypatch):
    """C4: the cursor branch of fetch_open_prs driven across two REAL pages (49 open PRs against
    first:50 makes this live traffic). The suite's only prior hasNextPage:True case was the guilt
    case for a missing endCursor."""
    pages = [
        {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": True, "endCursor": "CURSOR-1"},
            "nodes": [_rearm_node(1), _rearm_node(2, merge_state_status="CLEAN",
                                                 head_ref_name="agent/x/y")],
        }}}},
        {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [_rearm_node(3)],
        }}}},
    ]
    seen_variables = []

    def fake_gh_graphql(query, variables, timeout=45):
        seen_variables.append(dict(variables))
        return pages[len(seen_variables) - 1]

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    all_prs = qs.fetch_open_prs("Bali-Zero/Teman2")

    assert [pr["number"] for pr in all_prs] == [1, 2, 3]  # the union, in page order
    assert len(seen_variables) == 2
    assert "cursor" not in seen_variables[0]
    assert seen_variables[1]["cursor"] == "CURSOR-1"


def test_fetch_open_pr_heads_walks_two_real_pages_C4(monkeypatch):
    """C4, the other paginating reader: same two-page walk, asserting the union of head SHAs and
    the second call's cursor variable."""
    pages = [
        {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": True, "endCursor": "CURSOR-H1"},
            "nodes": [{"headRefOid": "aaa"}, {"headRefOid": "bbb"}],
        }}}},
        {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [{"headRefOid": "ccc"}, {"headRefOid": None}],  # a null head is skipped
        }}}},
    ]
    seen_variables = []

    def fake_gh_graphql(query, variables, timeout=45):
        seen_variables.append(dict(variables))
        return pages[len(seen_variables) - 1]

    monkeypatch.setattr(qs, "_gh_graphql", fake_gh_graphql)
    heads = qs.fetch_open_pr_heads("Bali-Zero/Teman2")

    assert heads == {"aaa", "bbb", "ccc"}
    assert len(seen_variables) == 2
    assert "cursor" not in seen_variables[0]
    assert seen_variables[1]["cursor"] == "CURSOR-H1"


# ── K-5: INFRA job-name signatures matched as ENTITIES, never as substrings ─────────────────
# Kimi council finding K-5, deferred at #6127 and closed here. Superscar #3: a guard that judges
# a substring judges the wrong entity, and OVER-match is as real as UNDER-match.


def test_is_infra_job_name_guilt_whole_name_shapes_are_infra_K5():
    for name in ("Set up job", "complete job", "checkout", "cache", "docker", "runner",
                 "setup-python", "setup-node-20", "Set up Python 3.11", "  SET  UP   JOB  "):
        assert qs._is_infra_job_name(name) is True, name


def test_is_infra_job_name_innocence_real_repo_job_names_are_code_K5():
    """Every one of these is a REAL check name of this repository (measured against PR #6144's
    72 checks) or the ledger row's own example. Under the old bare-substring rule `Snyk Docker
    Security` matched `docker` and a failing security job re-armed as INFRA."""
    for name in ("Snyk Docker Security", "Build Docker image", "Cache dependencies",
                 "docker-build", "Install test runner", "Backend Tests (Python)",
                 "Checkout PR head", "cache-warm-tests"):
        assert qs._is_infra_job_name(name) is False, name


def test_run_has_infra_signature_failing_snyk_docker_job_is_code_K5():
    run = {"name": "CI", "conclusion": "failure"}
    jobs = [{"name": "Snyk Docker Security", "conclusion": "failure"}]
    assert qs._run_has_infra_signature(run, jobs) is False


def test_run_has_infra_signature_failing_setup_job_is_still_infra_K5():
    run = {"name": "CI", "conclusion": "failure"}
    jobs = [{"name": "setup-python", "conclusion": "failure"}]
    assert qs._run_has_infra_signature(run, jobs) is True


def test_rearm_pass_failing_snyk_docker_job_is_never_rearmed_K5(monkeypatch, tmp_path):
    """The consequence at tick level: the ejection of a PR whose only failing job is the security
    scan must classify CODE and re-arm nothing. Under the substring rule this tick re-armed."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")

    sha = "5" * 40
    run = {
        "id": 501, "head_branch": f"gh-readonly-queue/main/pr-713-{sha}",
        "conclusion": "failure", "created_at": _iso(NOW), "head_sha": sha,
    }

    def fake_run(cmd, timeout=30):
        if "jobs" in cmd[-1]:
            return 0, '{"jobs": [{"name": "Snyk Docker Security", "conclusion": "failure"}], "total_count": 1}', ""
        return 0, json.dumps({"workflow_runs": [run], "total_count": 1}), ""

    monkeypatch.setattr(qs, "_run", fake_run)
    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=713, head_sha=sha, head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {
            "reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": sha
        },
    )
    monkeypatch.setattr(
        qs, "rearm_pr",
        lambda repo, number: (_ for _ in ()).throw(
            AssertionError("a failing security scan is CODE and must never be re-armed")
        ),
    )

    result = qs.run_rearm_pass(dry_run=False, now=NOW)
    assert result["rearmed"] == 0
    assert result["unverified"] == 0


# ── K-3 (Kimi council finding, S1 2026-09-11): consecutive re-arm WRITE failures ────────────
# a persistently failing `gh pr merge --auto` re-arm WRITE must not read as tick-ok forever.


def _k3_setup_infra_candidate(monkeypatch, number, head_sha, rearm_pr_fn):
    """Shared plumbing for the K-3 tests: one candidate PR whose ejection classifies INFRA
    (allowed=True, so the loop actually reaches the `rearm_pr` call), fingerprint None (never
    contributes to the unrelated RED_SAME_CAUSE_LIMIT suspension)."""
    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=number, head_sha=head_sha, head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, num: {
            "reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": head_sha
        },
    )
    monkeypatch.setattr(
        qs, "fetch_infra_hint_and_fingerprint", lambda repo, num, removed_at: (True, None)
    )
    monkeypatch.setattr(qs, "rearm_pr", rearm_pr_fn)


def test_rearm_pass_three_consecutive_rearm_write_failures_alert_once_and_tick_not_ok_K3(
    monkeypatch, tmp_path
):
    _k3_setup_infra_candidate(monkeypatch, 901, "shaW", lambda repo, number: False)

    sends = []

    def fake_send_telegram(message, dedup_key=""):
        sends.append(dedup_key)
        return True

    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)

    r1 = qs.run_rearm_pass(dry_run=False, now=NOW)
    assert sends == []
    assert r1["rearm_write_failed"] == 0

    r2 = qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=10))
    assert sends == []
    assert r2["rearm_write_failed"] == 0

    r3 = qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=20))
    assert len(sends) == 1  # ONE alert, raised on the THIRD consecutive failing write
    assert r3["rearm_write_failed"] == 1

    saved = qs._load_json(qs.REARM_FAIL_FILE)
    assert saved["901:shaW"]["consecutive_failures"] == 3

    # the SAME tick outcome surfaces at tick() level as non-ok, without a SECOND Telegram send —
    # the alert already fired inside run_rearm_pass above (reused, not duplicated). tick() calls
    # the real qs._now() internally (real wall clock) — pinned here to stay within
    # BUDGET_GC_DAYS of the fixed test NOW above, or gc_rearm_fail_state would prune the
    # freshly-recorded 901:shaW entry as if it were weeks stale.
    _no_op_janitor(monkeypatch)
    monkeypatch.setattr(qs, "_now", lambda: NOW + _dt.timedelta(minutes=30))
    rc = qs.tick(dry_run=False)
    assert rc == 3
    assert len(sends) == 1  # still exactly one — tick() must not send a second alert
    hb = json.loads((tmp_path / "organism" / f"{qs.ORGAN_ID}.json").read_text())
    assert hb["status"] == "error"
    assert hb["metadata"]["rearm_write_failed"] == 1


def test_rearm_pass_single_transient_rearm_write_failure_never_alerts_K3_innocence(
    monkeypatch, tmp_path
):
    _k3_setup_infra_candidate(monkeypatch, 902, "shaT", lambda repo, number: False)

    def never_called(*_a, **_k):
        raise AssertionError("a single transient write failure must never alert")

    monkeypatch.setattr(qs, "send_telegram", never_called)

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["rearm_write_failed"] == 0
    saved = qs._load_json(qs.REARM_FAIL_FILE)
    assert saved["902:shaT"]["consecutive_failures"] == 1


def test_rearm_pass_successful_rearm_resets_write_failure_counter_to_zero_K3_innocence(
    monkeypatch, tmp_path
):
    outcomes = iter([False, False, True, False, False])  # fail, fail, SUCCEED, fail, fail
    _k3_setup_infra_candidate(monkeypatch, 903, "shaR2", lambda repo, number: next(outcomes))

    sends = []
    monkeypatch.setattr(
        qs, "send_telegram", lambda message, dedup_key="": (sends.append(dedup_key), True)[1]
    )

    times = [NOW + _dt.timedelta(minutes=i * 10) for i in range(5)]
    results = [qs.run_rearm_pass(dry_run=False, now=t) for t in times]

    # the success on tick 3 resets the counter to zero — the two MORE failures on ticks 4-5 never
    # reach REARM_WRITE_FAIL_LIMIT again on their own, so no alert fires across all five ticks.
    assert [r["rearm_write_failed"] for r in results] == [0, 0, 0, 0, 0]
    assert sends == []
    saved = qs._load_json(qs.REARM_FAIL_FILE)
    assert saved["903:shaR2"]["consecutive_failures"] == 2  # reset, then two MORE fails only


# ── K-7 (Kimi council finding, S1 2026-09-11): malformed-but-JSON data raises RuntimeError,
# never a raw KeyError/ValueError that escapes CANNOT-VERIFY (loud, no Telegram) ──────────────


def test_normalize_rearm_pr_missing_number_raises_runtimeerror_not_keyerror_K7():
    node = _rearm_node(42)
    del node["number"]
    with pytest.raises(RuntimeError):
        qs._normalize_rearm_pr(node)


def test_normalize_rearm_pr_innocence_well_formed_node_still_normalizes_K7():
    node = _rearm_node(42)
    normalized = qs._normalize_rearm_pr(node)
    assert normalized["number"] == 42


def test_run_rearm_pass_malformed_pr_node_missing_number_is_cannot_verify_K7(monkeypatch, tmp_path):
    node = _rearm_node(43)
    del node["number"]
    payload = {
        "data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [node],
        }}}
    }
    monkeypatch.setattr(qs, "_gh_graphql", lambda query, variables, timeout=45: payload)

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["cannot_verify"] == "rearm_candidates"
    assert result["rearmed"] == 0


def test_gc_red_state_hand_edited_garbage_key_raises_runtimeerror_not_valueerror_K7():
    red_state = {"not-a-number": {"reds": []}}
    with pytest.raises(RuntimeError):
        qs.gc_red_state(red_state, {1, 2, 3})


def test_gc_red_state_innocence_well_formed_key_still_gcs_K7():
    red_state = {"5": {"reds": []}, "6": {"reds": []}}
    gced = qs.gc_red_state(red_state, {5})
    assert gced == {"5": {"reds": []}}


def test_run_rearm_pass_hand_edited_red_file_key_is_cannot_verify_K7(monkeypatch, tmp_path):
    red_path = tmp_path / "red.json"
    qs._save_json(red_path, {"garbage-key": {"reds": []}})
    monkeypatch.setattr(qs, "RED_FILE", red_path)
    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=44, head_sha="s", head_ref_name="agent/x/y")],
    )

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["cannot_verify"] == "red_state_gc"
    assert result["rearmed"] == 0


# ── K-8 (Kimi council finding, S1 2026-09-11): alerted_state GC'd like red_state ────────────


def test_gc_alerted_state_guilt_drops_entry_once_its_pr_is_no_longer_open_K8():
    alerted_state = {"701:shaOld": "2026-09-01T00:00:00Z"}
    gced = qs.gc_alerted_state(alerted_state, set())  # PR 701 no longer open
    assert gced == {}


def test_gc_alerted_state_innocence_keeps_entry_while_its_pr_stays_open_K8():
    alerted_state = {"701:shaOld": "2026-09-01T00:00:00Z"}
    gced = qs.gc_alerted_state(alerted_state, {701})
    assert gced == alerted_state


def test_run_rearm_pass_gcs_alerted_state_after_a_pr_closes_K8(monkeypatch, tmp_path):
    alerted_path = tmp_path / "alerted.json"
    qs._save_json(alerted_path, {"999:shaClosed": "2026-09-01T00:00:00Z"})
    monkeypatch.setattr(qs, "ALERTED_FILE", alerted_path)
    monkeypatch.setattr(qs, "fetch_open_prs", lambda repo=qs.REPO: [])  # PR 999 no longer open

    qs.run_rearm_pass(dry_run=False, now=NOW)

    assert qs._load_json(alerted_path) == {}


# ── spalla-review findings on the K-3/K-7/K-8 commit itself (2026-09-11) ────────────────────


def test_run_rearm_pass_red_state_gc_failure_still_reports_real_candidates_count(monkeypatch, tmp_path):
    """The review's finding 1: on a `red_state_gc` CANNOT-VERIFY the pass returns early, and with
    the candidate filter left downstream the tick logged `candidates=0` — the initial value, not
    a measurement, and `list_read_failed` does not mask it to `-`. The count is now taken before
    the GC step, so the failure log tells the truth about how many PRs were waiting."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    qs._save_json(qs.RED_FILE, {"not-a-number": {"reds": []}})  # the hand-edited key K-7 guards

    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [
            _pr(number=801, head_sha="shaA", head_ref_name="agent/x/y"),
            _pr(number=802, head_sha="shaB", head_ref_name="agent/x/y"),
            _pr(number=803, merge_state_status="DIRTY"),  # not a candidate
        ],
    )

    result = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert result["cannot_verify"] == "red_state_gc"
    assert result["examined"] == 3
    assert result["candidates"] == 2, "a real count, never the initial 0 that reads as a measurement"


def test_gc_rearm_fail_state_drops_aged_entries_and_keeps_fresh_ones(tmp_path):
    """The review's finding 2: `gc_rearm_fail_state` shipped with no direct test, so the K-3 state
    file's own 'never grows unbounded' claim was asserted rather than proven. Guilt and innocence
    on the same entity, in one pass."""
    old = (NOW - _dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    state = {
        "901:shaOld": {"consecutive": 2, "last_attempt_at": old},
        "902:shaNew": {"consecutive": 1, "last_attempt_at": fresh},
    }
    kept = qs.gc_rearm_fail_state(state, NOW)
    assert "902:shaNew" in kept, "a fresh entry must survive"
    assert "901:shaOld" not in kept, "an aged entry must be pruned"


def test_gc_alerted_state_keeps_both_key_families_apart(tmp_path):
    """The review's finding 3: K-3 put a second key family (`rearm-write-fail:<pr>:<sha>`) in the
    file K-8's GC prunes, and no test drove a MIXED dict through it. Both families for an open PR
    survive; both for a closed one are dropped; neither is misread as the other."""
    state = {
        "910:shaOpen": {"at": "x"},
        "rearm-write-fail:910:shaOpen": {"at": "x"},
        "911:shaGone": {"at": "x"},
        "rearm-write-fail:911:shaGone": {"at": "x"},
    }
    kept = qs.gc_alerted_state(state, {910})
    assert set(kept) == {"910:shaOpen", "rearm-write-fail:910:shaOpen"}


# ── gate findings on THIS PR: three guards the suite could not see (2026-09-11) ─────────────
# A fresh Opus 5 gate ran 17 guilt mutations against this branch and three left all 184 GREEN.
# Each of the three is the SAME shape as the finding that opened K-3/K-7/K-8: the code is right
# and the suite is blind to it. B1 in particular is the earlier spalla finding surviving one
# level up — gc_rearm_fail_state was tested as a FUNCTION and never as a WIRED STEP.


def test_run_rearm_pass_actually_prunes_the_rearm_fail_file_B1(monkeypatch, tmp_path):
    """B1: removing the `gc_rearm_fail_state(...)` CALL SITE left the whole suite green, because
    the only coverage drove the function directly. This drives the wired step: an aged entry
    present on disk before the pass is gone from the saved file after it."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "REARM_FAIL_FILE", tmp_path / "rearm_fail.json")

    old = (NOW - _dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    qs._save_json(qs.REARM_FAIL_FILE, {
        "950:shaAged": {"consecutive": 2, "last_attempt_at": old},
        "951:shaFresh": {"consecutive": 1, "last_attempt_at": fresh},
    })
    monkeypatch.setattr(qs, "fetch_open_prs", lambda repo=qs.REPO: [])

    qs.run_rearm_pass(dry_run=False, now=NOW)

    saved = qs._load_json(qs.REARM_FAIL_FILE)
    assert "951:shaFresh" in saved, "a fresh entry must survive the wired GC"
    assert "950:shaAged" not in saved, "the wired GC step must actually prune — not just the function"


def test_rearm_pass_second_run_of_failures_alerts_again_after_a_success_B2(monkeypatch, tmp_path):
    """B2: the `alerted_state.pop("rearm-write-fail:...")` on a SUCCESSFUL write had no test.
    Without it a (pr, head) that fails 3x, alerts, then succeeds, then fails 3x again is SILENT
    the second time — the exact K-3 disease (a failure with no alert), reintroduced by the dedup
    cache it was given."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "REARM_FAIL_FILE", tmp_path / "rearm_fail.json")

    sends: list[str] = []
    monkeypatch.setattr(qs, "send_telegram", lambda *a, **k: (sends.append(str(k.get("dedup_key") or a)), True)[1])
    monkeypatch.setattr(
        qs, "fetch_open_prs",
        lambda repo=qs.REPO: [_pr(number=960, head_sha="shaB2", head_ref_name="agent/x/y")],
    )
    monkeypatch.setattr(
        qs, "fetch_last_ejection",
        lambda repo, number: {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaB2"},
    )
    monkeypatch.setattr(qs, "fetch_infra_hint_and_fingerprint", lambda repo, number, removed_at: (True, None))

    write_ok = {"v": False}
    monkeypatch.setattr(qs, "rearm_pr", lambda repo, number: write_ok["v"])

    for i in range(3):  # first run of failures -> one alert
        qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=i))
    assert len(sends) == 1, f"three consecutive failures must alert exactly once, got {sends}"

    write_ok["v"] = True  # the write recovers
    qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=3))

    write_ok["v"] = False  # and fails again, three more times
    for i in range(4, 7):
        qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=i))

    assert len(sends) == 2, (
        f"a SECOND run of three failures after a recovery must alert again, not be swallowed "
        f"by the stale dedup key — got {sends}"
    )


def test_gc_alerted_state_keeps_an_unparseable_key_B3():
    """B3: the docstring's own invariant — 'a key without a parseable leading PR number is KEPT
    rather than dropped' — had zero coverage, so turning it into a silent drop left 184 green.
    This file is a dedup cache, and destroying a key here re-opens the alert it deduplicates."""
    state = {
        "970:shaOpen": {"at": "x"},
        "hand-written-nonsense": {"at": "x"},
        "rearm-write-fail:not-a-number:sha": {"at": "x"},
    }
    kept = qs.gc_alerted_state(state, {970})
    assert "hand-written-nonsense" in kept
    assert "rearm-write-fail:not-a-number:sha" in kept
    assert "970:shaOpen" in kept


# ── C2 + M23/M27: report() had no test at all (gate on #6175, second round) ─────────────────
# `report()` is the ONE command an operator runs to ask what the organ is doing, and nothing
# exercised it — which is why the C2 conflation (write-failure alerts counted and labelled as
# UNKNOWN ones) reached a reviewer instead of a test.


def _run_report(capsys):
    rc = qs.report()
    return rc, capsys.readouterr().out


def test_report_separates_the_two_alert_families_C2(monkeypatch, tmp_path, capsys):
    """Guilt: a write-failure dedup key must NOT be counted or labelled as an UNKNOWN alert.
    Innocence: a genuine UNKNOWN key must still be counted as one, on the same dict."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "REARM_FAIL_FILE", tmp_path / "rearm_fail.json")
    monkeypatch.setattr(qs, "LOG_FILE", tmp_path / "absent.log")
    qs._save_json(qs.ALERTED_FILE, {
        "700:shaUnknown": "2026-09-11T00:00:00Z",
        f"{qs.REARM_FAIL_ALERT_PREFIX}701:shaWrite": "2026-09-11T00:00:00Z",
    })

    _rc, out = _run_report(capsys)

    assert "alerted (UNKNOWN, undelivered-until-resolved) keys: 1" in out
    assert "alerted (re-arm WRITE failure, undelivered-until-resolved) keys: 1" in out


def test_report_lists_the_rearm_fail_file_entries_M23(monkeypatch, tmp_path, capsys):
    """M23: the whole per-key block report() gained for REARM_FAIL_FILE was blind — deleting it
    left every test green, so the file K-3 added was invisible in the operator's own view."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    monkeypatch.setattr(qs, "REARM_FAIL_FILE", tmp_path / "rearm_fail.json")
    monkeypatch.setattr(qs, "LOG_FILE", tmp_path / "absent.log")
    qs._save_json(qs.REARM_FAIL_FILE, {
        "702:shaFail": {"consecutive_failures": 2, "last_attempt_at": "2026-09-11T00:00:00Z"},
    })

    _rc, out = _run_report(capsys)

    assert "702:shaFail" in out
    assert f"2/{qs.REARM_WRITE_FAIL_LIMIT} consecutive write failures" in out


def test_report_says_CORRUPT_when_the_rearm_fail_file_is_unparseable_M27(monkeypatch, tmp_path, capsys):
    """M27: the CORRUPT branch was blind too. A corrupt state file must be NAMED in the report,
    never rendered as an empty-and-therefore-healthy one — the whole family of defect this PR
    exists to close is an organ that looks fine while something is wrong underneath."""
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")
    monkeypatch.setattr(qs, "RED_FILE", tmp_path / "red.json")
    corrupt = tmp_path / "rearm_fail.json"
    corrupt.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(qs, "REARM_FAIL_FILE", corrupt)
    monkeypatch.setattr(qs, "LOG_FILE", tmp_path / "absent.log")

    _rc, out = _run_report(capsys)

    assert "CORRUPT, cannot parse" in out
