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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue_shepherd as qs  # noqa: E402

NOW = _dt.datetime(2026, 8, 27, 12, 0, 0, tzinfo=_dt.timezone.utc)


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

    cancelled = qs.run_janitor_pass(dry_run=False)

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

    cancelled = qs.run_janitor_pass(dry_run=False)

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
    cancelled_1 = qs.run_janitor_pass(dry_run=False)
    assert cancelled_1 == 0
    saved = qs._load_json(uncancellable_path)
    assert "32217208723" in saved

    # Tick 2: cancel_run must NEVER be invoked again for this id.
    def never_called(repo, run_id):
        raise AssertionError(f"cancel_run must not be re-invoked for known-uncancellable id {run_id}")

    monkeypatch.setattr(qs, "cancel_run", never_called)
    with caplog.at_level("INFO"):
        cancelled_2 = qs.run_janitor_pass(dry_run=False)

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

    cancelled = qs.run_janitor_pass(dry_run=False)

    assert cancelled == 0
    assert uncancellable_path.read_text(encoding="utf-8") == "{not json"


def test_janitor_dry_run_never_calls_cancel_run(monkeypatch):
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

    cancelled = qs.run_janitor_pass(dry_run=True)
    assert cancelled == 1  # counted as "would cancel"


def test_janitor_fetch_failure_is_cannot_verify_never_reads_as_nothing_to_do(monkeypatch):
    def boom(repo=qs.REPO):
        raise RuntimeError("gh api failed rc=1")

    monkeypatch.setattr(qs, "fetch_queued_runs", boom)
    cancelled = qs.run_janitor_pass(dry_run=False)
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

    def fake_candidates(repo=qs.REPO):
        return [{"number": 501, "head_sha": "shaINFRA", "head_ref_name": "agent/x/y/z"}]

    def fake_ejection(repo, number):
        return {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaINFRA"}

    def fake_infra_hint(repo, number, removed_at):
        return True

    rearm_calls = []

    def fake_rearm_pr(repo, number):
        rearm_calls.append(number)
        return True

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "fetch_infra_hint", fake_infra_hint)
    monkeypatch.setattr(qs, "rearm_pr", fake_rearm_pr)

    rearmed = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert rearmed == 1
    assert rearm_calls == [501]
    saved = qs._load_json(qs.BUDGET_FILE)
    assert "501:shaINFRA" in saved


def test_rearm_pass_unknown_ejection_alerts_once_then_dedups(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")

    def fake_candidates(repo=qs.REPO):
        return [{"number": 502, "head_sha": "shaUNK", "head_ref_name": "agent/x/y/z"}]

    def fake_ejection(repo, number):
        return None  # no timeline event found at all

    alerts = []

    def fake_send_telegram(message, dedup_key=""):
        alerts.append(dedup_key)
        return True  # simulates a successful delivery

    def never_rearm(repo, number):
        raise AssertionError("must never rearm an UNKNOWN ejection")

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "send_telegram", fake_send_telegram)
    monkeypatch.setattr(qs, "rearm_pr", never_rearm)

    rearmed_1 = qs.run_rearm_pass(dry_run=False, now=NOW)
    rearmed_2 = qs.run_rearm_pass(dry_run=False, now=NOW + _dt.timedelta(minutes=10))

    assert rearmed_1 == 0
    assert rearmed_2 == 0
    assert len(alerts) == 1  # deduped on the second tick — same (pr, head sha)


def test_rearm_pass_dry_run_never_writes_state_files(monkeypatch, tmp_path):
    budget_path = tmp_path / "budget.json"
    alerted_path = tmp_path / "alerted.json"
    monkeypatch.setattr(qs, "BUDGET_FILE", budget_path)
    monkeypatch.setattr(qs, "ALERTED_FILE", alerted_path)

    def fake_candidates(repo=qs.REPO):
        return [{"number": 503, "head_sha": "shaX", "head_ref_name": "agent/x/y/z"}]

    def fake_ejection(repo, number):
        return {"reason": "failed_checks", "removed_at": _iso(NOW), "before_commit": "shaX"}

    def fake_infra_hint(repo, number, removed_at):
        return True

    def never_rearm(repo, number):
        raise AssertionError("--dry-run must never call gh pr merge")

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", fake_candidates)
    monkeypatch.setattr(qs, "fetch_last_ejection", fake_ejection)
    monkeypatch.setattr(qs, "fetch_infra_hint", fake_infra_hint)
    monkeypatch.setattr(qs, "rearm_pr", never_rearm)

    rearmed = qs.run_rearm_pass(dry_run=True, now=NOW)

    assert rearmed == 1  # counted as "would rearm"
    assert not budget_path.exists()
    assert not alerted_path.exists()


def test_rearm_pass_fetch_failure_is_cannot_verify_never_reads_as_nothing_to_do(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(qs, "ALERTED_FILE", tmp_path / "alerted.json")

    def boom(repo=qs.REPO):
        raise RuntimeError("gh api graphql failed rc=1")

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", boom)
    rearmed = qs.run_rearm_pass(dry_run=False, now=NOW)
    assert rearmed == 0


# ── refuter round (agy pass, 2026-08-27): 6 findings, verified against real code ────────────


# 1. _run_has_infra_signature: CODE wins over fail-fast-cancelled siblings.


def test_infra_signature_guilt_run_conclusion_cancelled_with_no_jobs_is_infra():
    # No job data at all (jobs fetch failed) but the run's OWN conclusion is cancelled/timed_out
    # -> still INFRA, nothing here contradicts it.
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
            return 0, '{"jobs": [{"name": "Backend Shard 1", "conclusion": "failure"}]}', ""
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

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", never_called)

    rearmed = qs.run_rearm_pass(dry_run=False, now=NOW)

    assert rearmed == 0
    # the corrupt file must be left as-is (never overwritten with a fresh empty state)
    assert budget_path.read_text(encoding="utf-8") == "{not json"


# 4. send_telegram: alerted_state recorded only on a successful send.


def test_rearm_pass_unknown_alert_not_recorded_when_send_telegram_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(qs, "BUDGET_FILE", tmp_path / "budget.json")
    alerted_path = tmp_path / "alerted.json"
    monkeypatch.setattr(qs, "ALERTED_FILE", alerted_path)

    def fake_candidates(repo=qs.REPO):
        return [{"number": 601, "head_sha": "shaUNK2", "head_ref_name": "agent/x/y/z"}]

    def fake_ejection(repo, number):
        return None

    send_attempts = []

    def failing_send_telegram(message, dedup_key=""):
        send_attempts.append(dedup_key)
        return False  # transient gateway/network failure

    def never_rearm(repo, number):
        raise AssertionError("must never rearm an UNKNOWN ejection")

    monkeypatch.setattr(qs, "fetch_rearm_candidate_prs", fake_candidates)
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
            cancelled = qs.run_janitor_pass(dry_run=False)
        assert cancelled == 0
        for rid in REAL_STUCK_RUN_IDS:
            assert (
                f"cancel_run({rid}) failed rc=1 err=gh: Failed to cancel workflow run (HTTP 500)"
                in caplog.text
            ), f"tick {tick_num} lost the real warning for {rid}"

    # Tick 4: all 4 ids are now quarantined.
    caplog.clear()
    with caplog.at_level("INFO"):
        cancelled_4 = qs.run_janitor_pass(dry_run=False)

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

    cancelled = qs.run_janitor_pass(dry_run=False)

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

    cancelled = qs.run_janitor_pass(dry_run=False)
    assert cancelled == 0
    saved = qs._load_json(uncancellable_path)
    assert saved["556"]["quarantined_at"] != old_ts  # refreshed, not left stale
    assert qs.is_quarantined(saved["556"], qs._now()) is True  # freshly re-quarantined

    def never_called(repo, run_id):
        raise AssertionError("must not retry immediately after a fresh re-quarantine")

    monkeypatch.setattr(qs, "cancel_run", never_called)
    cancelled_2 = qs.run_janitor_pass(dry_run=False)
    assert cancelled_2 == 0
