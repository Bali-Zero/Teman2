"""test_queue_unstick.py — pure-function tests over FIXTURE PR data (no network).

Covers superscar #3 (guard-over-match): every guard here has a guilt AND
an innocence test, on the entity (mergeQueueEntry / label set / commit
timestamp), never on a bare substring.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue_unstick as qu  # noqa: E402

NOW = _dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=_dt.timezone.utc)


def _iso(dt: _dt.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_pr(
    number: int,
    *,
    is_draft: bool = False,
    merge_state_status: str = "BEHIND",
    labels: list[str] | None = None,
    minutes_since_commit: int = 30,
    head_sha: str = "a" * 40,
    base_ref: str = "main",
    queued: bool = False,
) -> dict:
    commit_ts = NOW - _dt.timedelta(minutes=minutes_since_commit)
    return {
        "number": number,
        "is_draft": is_draft,
        "merge_state_status": merge_state_status,
        "labels": labels or [],
        "last_commit_date": _iso(commit_ts),
        "head_sha": head_sha,
        "base_ref": base_ref,
        "queued": queued,
    }


# ── innocence ────────────────────────────────────────────────────────────


def test_behind_non_draft_unlabelled_old_pr_is_selected_for_update():
    pr = make_pr(1, merge_state_status="BEHIND", minutes_since_commit=30)
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == [1]
    assert plan["signal_dirty"] == []
    assert 1 not in plan["skipped"]


# ── guilt: each its own reason ──────────────────────────────────────────


def test_queued_pr_is_not_selected_even_if_behind():
    pr = make_pr(2, merge_state_status="BEHIND", minutes_since_commit=30, queued=True)
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["skipped"][2] == "queued"


def test_recent_commit_pr_is_not_selected():
    pr = make_pr(3, merge_state_status="BEHIND", minutes_since_commit=2)
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["skipped"][3] == "recent_commit"


def test_hold_labelled_pr_is_not_selected():
    pr = make_pr(4, merge_state_status="BEHIND", minutes_since_commit=30, labels=["hold"])
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["skipped"][4] == "hold_label"


def test_suspended_labelled_pr_is_also_not_selected():
    pr = make_pr(41, merge_state_status="BEHIND", minutes_since_commit=30, labels=["suspended"])
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["skipped"][41] == "hold_label"


def test_unrelated_label_does_not_trigger_hold_guard():
    # Guard-over-match guilt/innocence pairing (superscar #3): a label that
    # merely CONTAINS "hold" as a substring must not match.
    pr = make_pr(42, merge_state_status="BEHIND", minutes_since_commit=30, labels=["on-hold-review-later"])
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == [42]


def test_draft_pr_is_not_selected():
    pr = make_pr(5, merge_state_status="BEHIND", minutes_since_commit=30, is_draft=True)
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["skipped"][5] == "draft"


def test_dirty_pr_is_never_selected_for_update_and_produces_exactly_one_signal():
    pr = make_pr(6, merge_state_status="DIRTY", minutes_since_commit=30, head_sha="b" * 40)
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["signal_dirty"] == [{"number": 6, "sha": "b" * 40}]


def test_second_run_same_dirty_pr_and_sha_produces_zero_additional_signals():
    pr = make_pr(7, merge_state_status="DIRTY", minutes_since_commit=30, head_sha="c" * 40)
    first = qu.plan_actions([pr], NOW)
    assert first["signal_dirty"] == [{"number": 7, "sha": "c" * 40}]

    seen_dirty = {"7": "c" * 40}
    second = qu.plan_actions([pr], NOW, seen_dirty=seen_dirty)
    assert second["signal_dirty"] == []
    assert second["skipped"][7] == "dirty_already_signalled"


def test_dirty_pr_new_sha_after_previous_signal_signals_again():
    # A new head SHA (force-push / conflict re-resolve attempt) must not be
    # swallowed by the dedup — dedup keys on (PR, sha), not PR alone.
    pr = make_pr(71, merge_state_status="DIRTY", minutes_since_commit=30, head_sha="d" * 40)
    seen_dirty = {"71": "c" * 40}
    plan = qu.plan_actions([pr], NOW, seen_dirty=seen_dirty)
    assert plan["signal_dirty"] == [{"number": 71, "sha": "d" * 40}]


def test_sixth_behind_pr_in_one_tick_is_not_updated_cap():
    prs = [make_pr(100 + i, merge_state_status="BEHIND", minutes_since_commit=30) for i in range(6)]
    plan = qu.plan_actions(prs, NOW, cap=5)
    assert plan["update_branch"] == [100, 101, 102, 103, 104]
    assert plan["skipped"][105] == "cap_reached"


# ── extra coverage: clean/other statuses, mixed batch, edge timestamps ───


def test_clean_pr_is_no_action():
    pr = make_pr(8, merge_state_status="CLEAN", minutes_since_commit=30)
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["signal_dirty"] == []
    assert plan["skipped"][8] == "status_CLEAN"


def test_missing_commit_timestamp_is_treated_as_recent_cannot_verify_safe():
    pr = make_pr(9, merge_state_status="BEHIND", minutes_since_commit=30)
    pr["last_commit_date"] = None
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == []
    assert plan["skipped"][9] == "recent_commit"


def test_exactly_at_threshold_boundary_is_still_recent():
    # age == threshold_seconds -> "< threshold" is False at exactly the
    # boundary only if age computed precisely; use a hair under threshold.
    pr = make_pr(10, merge_state_status="BEHIND", minutes_since_commit=5)
    pr["last_commit_date"] = (NOW - _dt.timedelta(seconds=299)).strftime("%Y-%m-%dT%H:%M:%SZ")
    plan = qu.plan_actions([pr], NOW)
    assert plan["skipped"][10] == "recent_commit"


def test_just_past_threshold_is_no_longer_recent():
    pr = make_pr(11, merge_state_status="BEHIND", minutes_since_commit=5)
    pr["last_commit_date"] = (NOW - _dt.timedelta(seconds=301)).strftime("%Y-%m-%dT%H:%M:%SZ")
    plan = qu.plan_actions([pr], NOW)
    assert plan["update_branch"] == [11]


def test_mixed_batch_examined_count_and_independent_classification():
    prs = [
        make_pr(20, merge_state_status="BEHIND", minutes_since_commit=30),         # update
        make_pr(21, merge_state_status="DIRTY", minutes_since_commit=30, head_sha="e" * 40),  # signal
        make_pr(22, merge_state_status="BEHIND", minutes_since_commit=30, queued=True),        # skip: queued
        make_pr(23, merge_state_status="BEHIND", minutes_since_commit=2),                       # skip: recent
        make_pr(24, merge_state_status="BEHIND", minutes_since_commit=30, labels=["hold"]),     # skip: hold
        make_pr(25, merge_state_status="BEHIND", minutes_since_commit=30, is_draft=True),       # skip: draft
        make_pr(26, merge_state_status="CLEAN", minutes_since_commit=30),                       # skip: status
    ]
    plan = qu.plan_actions(prs, NOW)
    assert plan["examined"] == 7
    assert plan["update_branch"] == [20]
    assert plan["signal_dirty"] == [{"number": 21, "sha": "e" * 40}]
    assert plan["skipped"] == {
        22: "queued",
        23: "recent_commit",
        24: "hold_label",
        25: "draft",
        26: "status_CLEAN",
    }


def test_kill_switch_env_var_makes_main_a_noop(monkeypatch, capsys):
    monkeypatch.setenv("QUEUE_UNSTICK_ENABLED", "false")
    rc = qu.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "disabled=true" in captured.out


def test_fetch_failure_returns_cannot_verify_exit_4_never_reads_as_empty(monkeypatch, capsys):
    monkeypatch.delenv("QUEUE_UNSTICK_ENABLED", raising=False)

    def boom(repo):
        raise RuntimeError("gh api graphql failed rc=1: simulated network failure")

    monkeypatch.setattr(qu, "fetch_open_prs", boom)
    rc = qu.main([])
    captured = capsys.readouterr()
    assert rc == 4
    assert "cannot_verify=true" in captured.out


def test_dry_run_main_performs_zero_gh_or_fleet_mail_calls(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("QUEUE_UNSTICK_ENABLED", raising=False)
    monkeypatch.setattr(qu, "STATE_DIR", tmp_path)
    monkeypatch.setattr(qu, "DIRTY_SEEN_FILE", tmp_path / "queue_unstick_dirty_seen.json")

    # main() computes its own real-wall-clock `now` internally (it has no
    # `now` override param — by design, this is the one function allowed to
    # touch the clock). So PR commit timestamps here must be relative to the
    # ACTUAL current time, not the fixed NOW used by the plan_actions() unit
    # tests above, or this integration test would be wall-clock-dependent.
    real_now = _dt.datetime.now(_dt.timezone.utc)
    old_commit = _iso(real_now - _dt.timedelta(minutes=30))
    prs = [
        make_pr(30, merge_state_status="BEHIND", minutes_since_commit=30),
        make_pr(31, merge_state_status="DIRTY", minutes_since_commit=30, head_sha="f" * 40),
    ]
    prs[0]["last_commit_date"] = old_commit
    prs[1]["last_commit_date"] = old_commit
    monkeypatch.setattr(qu, "fetch_open_prs", lambda repo: prs)

    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("should not run subprocess calls during --dry-run")

    monkeypatch.setattr(qu, "_run", fail_if_called)

    rc = qu.main(["--dry-run"])
    captured = capsys.readouterr()
    assert rc == 0
    assert calls == []
    assert "dry-run" in captured.out
    assert not (tmp_path / "queue_unstick_dirty_seen.json").exists()


def test_hold_labels_are_case_insensitive():
    pr = make_pr(50, merge_state_status="BEHIND", minutes_since_commit=30, labels=["Hold"])
    plan = qu.plan_actions([pr], NOW)
    assert plan["skipped"][50] == "hold_label"
