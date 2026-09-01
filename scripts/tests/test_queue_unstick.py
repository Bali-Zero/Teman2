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


def test_plan_actions_no_longer_dedups_on_head_sha_alone():
    """The dedup MOVED to main(), keyed on head_sha AND the conflict set.

    Deduping here on head_sha alone was blind to the case that matters:
    `main` advances, the conflicting files change, the PR head does not.
    plan_actions is pure/network-free and cannot compute a conflict
    fingerprint, so it now proposes every DIRTY candidate and main() decides.
    """
    pr = make_pr(7, merge_state_status="DIRTY", minutes_since_commit=30, head_sha="c" * 40)
    first = qu.plan_actions([pr], NOW)
    assert first["signal_dirty"] == [{"number": 7, "sha": "c" * 40}]

    second = qu.plan_actions([pr], NOW, seen_dirty={"7": "c" * 40})
    assert second["signal_dirty"] == [{"number": 7, "sha": "c" * 40}]


# ── (b) the dedup key itself: head_sha AND conflict set ─────────────────────


def test_fingerprint_GUILT_same_head_different_conflict_set_is_a_DIFFERENT_key():
    """The bug this fix exists for: main moved, the conflict set changed, the
    head did not — and the old key could not tell the two apart."""
    sha = "c" * 40
    before = qu._dirty_fingerprint(sha, "evidence/pack.yml")
    after = qu._dirty_fingerprint(sha, "evidence/pack.yml, scripts/queue_unstick.py")
    assert before != after, "a changed conflict set on an unchanged head must re-signal"


def test_fingerprint_INNOCENCE_unchanged_state_still_dedups_against_stored_key():
    """The dedup must still dedup — the fix must not turn this cron into a
    per-tick spammer (the failure mode in the other direction).

    Asserted against a SEPARATELY-CONSTRUCTED stored key and a non-degenerate
    shape, not `f(x) == f(x)`: a function returning a constant would satisfy
    determinism while destroying the dedup's ability to discriminate at all.
    """
    sha = "c" * 40
    files = "evidence/pack.yml"

    stored = qu._dirty_fingerprint(sha, files)          # tick N wrote this
    recomputed = qu._dirty_fingerprint(sha, files)      # tick N+1, nothing changed

    assert recomputed == stored, "an unchanged head + unchanged conflict set must not re-signal"
    # …and the key must actually carry the state it claims to key on, so that
    # equality above means "same state", not "constant function".
    assert stored.startswith(sha + ":")
    assert stored != qu._dirty_fingerprint(sha, files + ", scripts/queue_unstick.py")
    assert stored != qu._dirty_fingerprint("d" * 40, files)


def test_fingerprint_INNOCENCE_different_head_same_conflict_set_is_a_DIFFERENT_key():
    same_files = "evidence/pack.yml"
    assert qu._dirty_fingerprint("c" * 40, same_files) != qu._dirty_fingerprint(
        "d" * 40, same_files
    )


def test_fingerprint_is_bounded_regardless_of_conflict_set_size():
    """State-file hygiene: twenty conflicting paths must not write twenty
    paths into the dedup file."""
    huge = ", ".join(f"path/number/{i}.yml" for i in range(200))
    key = qu._dirty_fingerprint("c" * 40, huge)
    assert len(key) == 40 + 1 + 16


# ── (a) the TOCTOU guard on do_update_branch ────────────────────────────────


def test_toctou_GUILT_pr_that_entered_the_queue_after_planning_is_NOT_updated():
    """The eviction race, reproduced. classify() saw `queued: False` from the
    bulk read; by mutation time the PR is in the queue. Updating it now would
    EVICT it — the most destructive action this script can take.

    This test FAILS against the pre-2026-08-25 do_update_branch, which called
    `gh pr update-branch` with no re-check at all.
    """
    calls = []

    def _never_called(cmd, timeout=30):
        calls.append(cmd)
        return 0, "", ""

    original_run = qu._run
    qu._run = _never_called
    try:
        outcome, detail = qu.do_update_branch(
            4242,
            dry_run=False,
            queue_recheck=lambda number, repo=None: (True, "in merge queue (state=AWAITING_CHECKS)"),
        )
    finally:
        qu._run = original_run

    assert outcome == "aborted", f"expected abort, got {outcome}: {detail}"
    assert "EVICT" in detail
    assert calls == [], f"no gh command may run once the PR is known queued; ran {calls}"


def test_toctou_GUILT_unverifiable_queue_state_does_NOT_authorise_an_update():
    """CANNOT-VERIFY must fail CLOSED here. 'I could not check' is not
    'it is safe' when the downstream action is an eviction."""
    calls = []

    def _never_called(cmd, timeout=30):
        calls.append(cmd)
        return 0, "", ""

    original_run = qu._run
    qu._run = _never_called
    try:
        outcome, detail = qu.do_update_branch(
            4242, dry_run=False, queue_recheck=lambda number, repo=None: (None, "network flap")
        )
    finally:
        qu._run = original_run

    assert outcome == "aborted"
    assert "UNVERIFIABLE" in detail
    assert calls == []


def test_toctou_INNOCENCE_pr_still_not_queued_IS_updated():
    """The guard must not block the whole point of the script."""
    calls = []

    def _fake_run(cmd, timeout=30):
        calls.append(cmd)
        return 0, "updated", ""

    original_run = qu._run
    qu._run = _fake_run
    try:
        outcome, detail = qu.do_update_branch(
            4242, dry_run=False, queue_recheck=lambda number, repo=None: (False, "not in merge queue")
        )
    finally:
        qu._run = original_run

    assert outcome == "ok", detail
    assert any("update-branch" in " ".join(c) for c in calls), f"expected the real call; got {calls}"


def test_toctou_INNOCENCE_dry_run_never_rechecks_and_never_mutates():
    """--dry-run must stay free of BOTH the mutation and the extra API call."""
    rechecked = []
    calls = []

    original_run = qu._run
    qu._run = lambda cmd, timeout=30: (calls.append(cmd), (0, "", ""))[1]
    try:
        outcome, detail = qu.do_update_branch(
            4242,
            dry_run=True,
            queue_recheck=lambda number, repo=None: (rechecked.append(number), (False, ""))[1],
        )
    finally:
        qu._run = original_run

    assert outcome == "ok"
    assert detail.startswith("[dry-run]")
    assert rechecked == [], "dry-run must not spend an API call on the re-check"
    assert calls == []


def test_is_queued_now_parses_null_as_not_queued_and_garbage_as_unverifiable():
    """The re-check's own guilt/innocence, on the entity (mergeQueueEntry),
    never on a substring."""
    original_run = qu._run
    try:
        qu._run = lambda cmd, timeout=30: (0, "null\n", "")
        assert qu.is_queued_now(1)[0] is False

        qu._run = lambda cmd, timeout=30: (0, '{"state":"AWAITING_CHECKS"}', "")
        assert qu.is_queued_now(1)[0] is True

        qu._run = lambda cmd, timeout=30: (0, "", "")
        assert qu.is_queued_now(1)[0] is None, "empty output is UNVERIFIABLE, not 'not queued'"

        qu._run = lambda cmd, timeout=30: (1, "", "boom")
        assert qu.is_queued_now(1)[0] is None, "rc!=0 is UNVERIFIABLE, not 'not queued'"

        qu._run = lambda cmd, timeout=30: (0, "<html>500</html>", "")
        assert qu.is_queued_now(1)[0] is None, "unparseable output is UNVERIFIABLE"
    finally:
        qu._run = original_run


# ── (c) the cap ─────────────────────────────────────────────────────────────


def test_cap_default_is_one_and_is_a_placeholder_not_a_tuned_number():
    assert qu.UPDATE_CAP == 1
    src = Path(qu.__file__).read_text()
    assert "PLACEHOLDER, NOT A TUNED NUMBER" in src, (
        "the cap must stay labelled as underived — a bare 1 reads as a measured value"
    )


def test_cap_of_one_updates_exactly_one_behind_pr_and_defers_the_rest():
    prs = [make_pr(n, merge_state_status="BEHIND", minutes_since_commit=30) for n in (1, 2, 3, 4, 5)]
    plan = qu.plan_actions(prs, NOW, cap=1)
    assert plan["update_branch"] == [1]
    assert [plan["skipped"][n] for n in (2, 3, 4, 5)] == ["cap_reached"] * 4


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


# ── re-warm: the first read after a base-branch merge is the warm-up ─────
#
# Measured 2026-08-25 (main frozen at b5b1be8e3, HEAD checked before AND
# after): 37 UNKNOWN -> 1 -> 1 -> 3 across three minutes of repeated
# querying, no merges in between. Asking is what fixes it, so a tick that
# asks ONCE classifies on the blind answer and silently acts on nothing.


def _blind(n_unknown: int, n_other: int, *, other_status: str = "BLOCKED") -> list[dict]:
    prs = [make_pr(100 + i, merge_state_status="UNKNOWN") for i in range(n_unknown)]
    prs += [make_pr(900 + i, merge_state_status=other_status) for i in range(n_other)]
    return prs


def test_rewarm_GUILT_a_blind_read_is_refetched_and_the_FRESH_values_are_returned():
    """Delete the re-warm and this goes red: the blind list would come back."""
    blind = _blind(30, 9)
    fresh = [make_pr(100, merge_state_status="BEHIND")] + _blind(1, 8)
    slept: list[int] = []
    out, info = qu.rewarm_if_blind(
        blind, "o/r", fetch=lambda repo: fresh, sleep=slept.append, wait_seconds=45
    )
    assert out is fresh, "must classify on the refetched values, not the blind ones"
    assert info["rewarmed"] is True
    assert info["unknown_before"] == 30
    assert info["unknown_after"] == 1
    assert slept == [45], "must actually wait — refetching instantly re-reads the same cache"


def test_rewarm_GUILT_main_acts_on_the_refetched_values_not_the_blind_ones(
    monkeypatch, tmp_path, capsys
):
    """End-to-end: a PR that is really BEHIND is invisible on the blind read."""
    monkeypatch.delenv("QUEUE_UNSTICK_ENABLED", raising=False)
    monkeypatch.delenv("QUEUE_UNSTICK_REWARM", raising=False)
    monkeypatch.setattr(qu, "STATE_DIR", tmp_path)
    monkeypatch.setattr(qu, "DIRTY_SEEN_FILE", tmp_path / "seen.json")
    monkeypatch.setattr(qu, "REWARM_WAIT_SECONDS", 0)

    real_now = _dt.datetime.now(_dt.timezone.utc)
    old = _iso(real_now - _dt.timedelta(minutes=30))

    def stamp(prs):
        for pr in prs:
            pr["last_commit_date"] = old
        return prs

    blind = stamp(_blind(30, 9))
    fresh = stamp([make_pr(100, merge_state_status="BEHIND")] + _blind(1, 8))

    calls = {"n": 0}

    def fetch(repo):
        calls["n"] += 1
        return blind if calls["n"] == 1 else fresh

    monkeypatch.setattr(qu, "fetch_open_prs", fetch)

    rc = qu.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert calls["n"] == 2, "the blind read must have been followed by exactly one refetch"
    assert "updated=1" in out, "the BEHIND PR is only visible on the refetched read"


def test_rewarm_GUILT_the_summary_line_reports_it(monkeypatch, tmp_path, capsys):
    """A behaviour that changes what the tick acts on must not be silent (#2)."""
    monkeypatch.delenv("QUEUE_UNSTICK_ENABLED", raising=False)
    monkeypatch.delenv("QUEUE_UNSTICK_REWARM", raising=False)
    monkeypatch.setattr(qu, "STATE_DIR", tmp_path)
    monkeypatch.setattr(qu, "DIRTY_SEEN_FILE", tmp_path / "seen.json")
    monkeypatch.setattr(qu, "REWARM_WAIT_SECONDS", 0)
    monkeypatch.setattr(qu, "fetch_open_prs", lambda repo: _blind(30, 9))

    qu.main(["--dry-run"])
    out = capsys.readouterr().out
    assert "rewarmed=true" in out
    assert "rewarm_reason=" in out
    assert "rewarm:" in out, "the human-readable line must name why the read was blind"


# ── innocence ────────────────────────────────────────────────────────────


def test_rewarm_INNOCENCE_a_warm_read_never_refetches_and_never_sleeps():
    """A warm read must cost nothing.

    Uses 6/100 rather than the measured 3/38 baseline on purpose: 3 is below
    REWARM_UNKNOWN_MIN, so it would exit on the absolute floor and never reach
    the ratio branch this test exists to cover. 6 clears the floor and still
    sits far under the ratio.
    """
    warm = _blind(6, 94)
    extra: list[str] = []
    slept: list[int] = []
    out, info = qu.rewarm_if_blind(
        warm,
        "o/r",
        fetch=lambda repo: extra.append(repo) or [],
        sleep=slept.append,
        wait_seconds=45,
    )
    assert out is warm
    assert info["rewarmed"] is False
    assert extra == [], "a warm tick must not spend a second API call"
    assert slept == [], "a warm tick must not add 45s of wall clock"
    assert "already_warm" in info["reason"]


def test_rewarm_BOUNDED_at_most_one_extra_fetch_even_if_still_blind():
    """If the base keeps moving the honest outcome is 'still blind', not a loop."""
    fetches: list[str] = []

    def fetch(repo):
        fetches.append(repo)
        return _blind(30, 9)

    out, info = qu.rewarm_if_blind(
        _blind(30, 9), "o/r", fetch=fetch, sleep=lambda s: None, wait_seconds=45
    )
    assert len(fetches) == 1, "exactly one extra fetch, never a retry loop inside a cron"
    assert info["rewarmed"] is True
    assert info["unknown_after"] == 30, "must report honestly that it is still blind"


def test_rewarm_INNOCENCE_kill_switch_disables_it(monkeypatch):
    monkeypatch.setenv("QUEUE_UNSTICK_REWARM", "false")
    extra: list[str] = []
    blind = _blind(30, 9)
    out, info = qu.rewarm_if_blind(
        blind, "o/r", fetch=lambda repo: extra.append(repo) or [], sleep=lambda s: None
    )
    assert out is blind
    assert info["rewarmed"] is False
    assert info["reason"] == "disabled"
    assert extra == []


def test_rewarm_INNOCENCE_empty_pr_list_does_not_divide_by_zero_or_refetch():
    extra: list[str] = []
    out, info = qu.rewarm_if_blind(
        [], "o/r", fetch=lambda repo: extra.append(repo) or [], sleep=lambda s: None
    )
    assert out == []
    assert info["reason"] == "no_open_prs"
    assert extra == []


def test_rewarm_DEGRADES_refetch_failure_falls_back_to_the_first_read():
    """Blind was the old normal — degrading back to it must not raise or redden."""
    blind = _blind(30, 9)

    def boom(repo):
        raise RuntimeError("gh api graphql failed rc=1: simulated flap")

    out, info = qu.rewarm_if_blind(blind, "o/r", fetch=boom, sleep=lambda s: None)
    assert out is blind
    assert info["rewarmed"] is False
    assert "refetch_failed" in info["reason"]


def test_rewarm_threshold_separates_the_two_MEASURED_populations():
    """Pins the derivation, so a later tweak has to argue with the data.

    Warm baseline measured 1-3 of ~38 (3-8%); blind measured 29-37 of 38-39
    (75-95%). The default separator must sit strictly between them.
    """
    quiet = lambda s: None  # noqa: E731
    never = lambda repo: (_ for _ in ()).throw(AssertionError("must not refetch"))

    for unknown, other in ((1, 37), (3, 35)):
        _, info = qu.rewarm_if_blind(
            _blind(unknown, other), "o/r", fetch=never, sleep=quiet
        )
        assert info["rewarmed"] is False, f"{unknown}/{unknown + other} is a WARM baseline"

    for unknown, other in ((29, 10), (37, 2)):
        _, info = qu.rewarm_if_blind(
            _blind(unknown, other), "o/r", fetch=lambda repo: [], sleep=quiet
        )
        assert info["rewarmed"] is True, f"{unknown}/{unknown + other} is BLIND"


def test_rewarm_GUILT_runs_in_PRODUCTION_not_only_in_dry_run(monkeypatch, tmp_path, capsys):
    """The gutting a cross-family refuter found: gate the re-warm on
    `args.dry_run` and every other test here stays green while production goes
    back to reading blind. This is the only test that can see that."""
    monkeypatch.delenv("QUEUE_UNSTICK_ENABLED", raising=False)
    monkeypatch.delenv("QUEUE_UNSTICK_REWARM", raising=False)
    monkeypatch.setattr(qu, "STATE_DIR", tmp_path)
    monkeypatch.setattr(qu, "DIRTY_SEEN_FILE", tmp_path / "seen.json")
    monkeypatch.setattr(qu, "REWARM_WAIT_SECONDS", 0)

    real_now = _dt.datetime.now(_dt.timezone.utc)
    old = _iso(real_now - _dt.timedelta(minutes=30))

    def stamp(prs):
        for pr in prs:
            pr["last_commit_date"] = old
        return prs

    blind = stamp(_blind(30, 9))
    fresh = stamp([make_pr(100, merge_state_status="BEHIND")] + _blind(1, 8))

    fetches = {"n": 0}

    def fetch(repo):
        fetches["n"] += 1
        return blind if fetches["n"] == 1 else fresh

    monkeypatch.setattr(qu, "fetch_open_prs", fetch)

    # Record the real mutation instead of performing it — no network, but this
    # is the PRODUCTION code path, not the --dry-run one.
    updates: list[int] = []

    def fake_update(number, *, repo=qu.REPO, dry_run, queue_recheck=None):
        assert dry_run is False, "this test must exercise the production path"
        updates.append(number)
        return "ok", f"updated #{number}"

    monkeypatch.setattr(qu, "do_update_branch", fake_update)

    rc = qu.main([])  # NO --dry-run
    out = capsys.readouterr().out
    assert rc == 0
    assert fetches["n"] == 2, "production must re-warm too, not just --dry-run"
    assert updates == [100], "the BEHIND PR is visible only on the refetched read"
    assert "rewarmed=true" in out


def test_rewarm_INNOCENCE_small_repo_with_one_stuck_UNKNOWN_never_pays_the_wait():
    """A ratio alone is trivially satisfied on a small repo: 1/1 = 1.0 and
    1/4 = 0.25 both clear the ratio, so without an absolute floor the tick
    would sleep and refetch forever without ever converging."""
    quiet = lambda s: None  # noqa: E731
    never = lambda repo: (_ for _ in ()).throw(AssertionError("must not refetch"))

    for unknown, other in ((1, 0), (1, 3), (2, 2), (4, 8)):
        _, info = qu.rewarm_if_blind(
            _blind(unknown, other), "o/r", fetch=never, sleep=quiet
        )
        assert info["rewarmed"] is False, f"{unknown}/{unknown + other} must not re-warm"
        assert "below_floor" in info["reason"]


def test_rewarm_reports_STILL_BLIND_rather_than_claiming_success():
    """A second read that is still blind must not be reported as a warm one —
    monitoring has to be able to tell the two apart."""
    _, info = qu.rewarm_if_blind(
        _blind(30, 9), "o/r", fetch=lambda repo: _blind(30, 9), sleep=lambda s: None
    )
    assert info["rewarmed"] is True, "a refetch DID happen — that part is honest"
    assert info["still_blind"] is True
    assert "STILL_BLIND" in info["reason"]


def test_rewarm_refetch_failure_does_not_swallow_a_programming_error():
    """`except Exception` would downgrade a GraphQL schema change (KeyError)
    into 'network flap' and hide it behind a successful exit."""
    import pytest

    def schema_change(repo):
        raise KeyError("mergeStateStatus")

    with pytest.raises(KeyError):
        qu.rewarm_if_blind(_blind(30, 9), "o/r", fetch=schema_change, sleep=lambda s: None)


# ---------------------------------------------------------------------------
# _driver_merged_changed_paths — guilt + innocence against a REAL git repo.
#
# These build an actual repository rather than stubbing `_run`, because the
# behaviour under test is entirely `git check-attr`'s and `git diff`'s output
# encoding — a fake would encode my belief about those formats and then agree
# with itself (superscar #9 / W114: a fake and the code it checks share the
# same imagination). Three of the cases below were written FROM defects an
# adversarial reviewer found in the first shipped cut, and each is pinned here
# because it was live in production for ~90 minutes.
# ---------------------------------------------------------------------------

import subprocess as _sp  # noqa: E402


def _git(repo, *args):
    _sp.run(["git", "-C", str(repo), *args], check=True,
            capture_output=True, text=True)


def _repo_with(tmp_path, gitattributes: str | None, extra: str | None = None):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    if gitattributes is not None:
        (repo / ".gitattributes").write_text(gitattributes)
    (repo / "ledger.md").write_text("base\n")
    (repo / "plain.txt").write_text("base\n")
    if extra:
        (repo / extra).write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "base-ref")
    (repo / "ledger.md").write_text("base\npr row\n")
    (repo / "plain.txt").write_text("base\npr line\n")
    if extra:
        (repo / extra).write_text("base\npr\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "pr")
    _git(repo, "branch", "pr-ref")
    return repo


def _probe(repo, base="base-ref", head="pr-ref"):
    return qu._driver_merged_changed_paths(
        repo_root=repo, base_ref=base, pr_ref=head
    )


def test_a_union_path_is_named_with_its_driver(tmp_path):
    """GUILT: the changed file carries merge=union -> reported, with the driver."""
    repo = _repo_with(tmp_path, "ledger.md merge=union\n")
    assert _probe(repo) == [("ledger.md", "union")]


def test_a_non_union_driver_is_also_caught(tmp_path):
    """GUILT, and the reason this keys on the COMPLEMENT of ordinary values:
    GitHub honours no driver at all, so `merge=ours` diverges exactly as
    `merge=union` does. The first shipped cut compared against the literal
    string "union" and returned [] here — a silent regression to the race
    wording on a file that is permanently, not transiently, DIRTY."""
    repo = _repo_with(tmp_path, "ledger.md merge=ours\n")
    assert _probe(repo) == [("ledger.md", "ours")]


def test_a_non_ascii_path_is_not_lost_to_quotepath(tmp_path):
    """GUILT. `core.quotePath` defaults to true, so `git diff --name-only`
    emits a non-ASCII path as the C-quoted literal "caf\\303\\251.md", which
    check-attr then does not match -> `unspecified` -> a real detection lost
    with no error. Measured against the first shipped cut: it returned []
    where the truth was [('café.md', 'union')]. `-z` is the cure."""
    name = "café.md"
    repo = _repo_with(tmp_path, f"{name} merge=union\n", extra=name)
    assert _probe(repo) == [(name, "union")]


def test_explicit_ordinary_values_are_not_reported(tmp_path):
    """INNOCENCE: `merge=text` and a bare `merge` are the ORDINARY merge, which
    GitHub performs identically. Reporting them would invent a permanent
    divergence where none exists."""
    for i, attrs in enumerate(("ledger.md merge=text\n", "ledger.md merge\n")):
        sub = tmp_path / f"case{i}"
        sub.mkdir()
        assert _probe(_repo_with(sub, attrs)) == [], attrs


def test_non_driver_paths_are_not_named(tmp_path):
    """INNOCENCE: a PR touching only ordinary files reports nothing, so the
    caller keeps its pre-existing 'race' wording."""
    repo = _repo_with(tmp_path, "ledger.md merge=union\n")
    _git(repo, "checkout", "-q", "-b", "plain-only", "base-ref")
    (repo / "plain.txt").write_text("base\nonly this\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "plain only")
    assert _probe(repo, head="plain-only") == []


def test_no_gitattributes_at_all_reports_nothing(tmp_path):
    """INNOCENCE: the same diff with no merge driver declared anywhere."""
    assert _probe(_repo_with(tmp_path, None)) == []


def test_a_path_containing_a_colon_survives(tmp_path):
    """The old parse read `<path>: merge: <value>` and split on ': '. -z removes
    that parse entirely; this pins that the removal actually holds.

    NOTE the DOUBLE quotes: `.gitattributes` rejects a single-quoted pattern
    ("name.md' is not a valid attribute name"), silently yielding `unspecified`,
    which would make this test pass for the wrong reason."""
    name = "weird: name.md"
    repo = _repo_with(tmp_path, f'"{name}" merge=union\n', extra=name)
    assert _probe(repo) == [(name, "union")]


def test_every_path_is_examined_not_just_the_first_batch(tmp_path):
    """GUILT for the silent-truncation bug: the first cut passed `paths[:200]`
    and examined nothing beyond, so a large PR whose driver path sorted late
    read as a race. The union file here is named `zz-...` so it sorts last
    among 250 changed files."""
    repo = tmp_path / "big"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / ".gitattributes").write_text("zz-ledger.md merge=union\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "attrs")
    _git(repo, "branch", "base-ref")
    for i in range(250):
        (repo / f"f{i:04d}.txt").write_text("x\n")
    (repo / "zz-ledger.md").write_text("row\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "many")
    _git(repo, "branch", "pr-ref")
    assert _probe(repo) == [("zz-ledger.md", "union")]


def test_a_broken_repo_returns_empty_rather_than_raising(tmp_path):
    """The probe is fail-quiet by design: an unusable repo must degrade to the
    caller's existing wording, never crash the daemon's tick."""
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    assert qu._driver_merged_changed_paths(
        repo_root=empty, base_ref="base-ref", pr_ref="pr-ref"
    ) == []


# --- the MESSAGE, which is the part that was dangerous ----------------------

#: The EXACT advice the daemon prints when it finds a permanent driver
#: divergence, pinned character for character. This is deliberately a
#: change-detector, not a content-guesser.
#:
#: The first cut of this test asserted that the message CONTAINS "hand-resolve"
#: and "do not" and "origin/main". A cross-family refuter broke it in one line:
#:
#:   "Instead, reset the file to origin/main and manually re-apply your rows"
#:
#: — which IS hand-resolving, means the forbidden thing, and satisfies every one
#: of those assertions. A substring test cannot decide what a sentence means, and
#: one that pretends to is worse than none: it converts an unreviewed reword into
#: a green tick. So the bar is lower and honest — ANY edit to this string fails
#: here, and a human has to look at it and update this constant on purpose.
_EXPECTED_DRIVER_ADVICE = (
    "none locally, but this is NOT a race: {shown} — git honours that "
    "driver, GitHub's merge machinery honours none, so the two disagree "
    "permanently and re-probing will never clear it. DO NOT hand-resolve "
    "the file and DO NOT rebase onto it: the first silently deletes the "
    "other lane's appended row, the second replays the append and "
    "duplicates it. Rebuild your addition on a branch cut from fresh "
    "origin/main, then verify `git diff origin/main -- <file>` is +N/-0."
)


def test_the_driver_advice_is_exactly_what_was_reviewed(tmp_path):
    """The shipped message once told the fleet 'the cure is a hand rebase of
    that file'. Hand-resolving a union file silently deletes the other lane's
    appended row (the loss the driver exists to prevent, caught by
    check-ledger-no-silent-loss on #5355); `git rebase` DOES apply the union
    driver and duplicates the row instead (#4060). Both readings of that
    sentence are documented failure modes, and it is broadcast to a fleet
    mailbox that agents act on.

    So this string is security-relevant text. It is pinned exactly: any reword,
    however well-meant, goes red here and has to be looked at by a person.
    THIS TEST DOES NOT PROVE THE ADVICE IS SAFE — no substring test can. It
    proves only that the advice is the one that was reviewed."""
    import inspect, re
    src = inspect.getsource(qu.get_conflicting_files)
    # Recover the message as source text, then undo the f-string concatenation
    # the same way Python does, so the comparison is against the real template.
    start = src.index('f"none locally, but this is NOT a race')
    end = src.index("return \"none (merge-tree", start)
    literal_src = src[start:end]
    pieces = re.findall(r'f?"((?:[^"\\]|\\.)*)"', literal_src)
    got = "".join(pieces)
    assert got == _EXPECTED_DRIVER_ADVICE, (
        "the driver-divergence advice changed. This is the string that told the "
        "fleet to perform a data-destroying gesture once already. Read the new "
        "wording, satisfy yourself it forbids BOTH hand-resolving and rebasing "
        "and names the rebuild-from-fresh-main cure, then update "
        "_EXPECTED_DRIVER_ADVICE deliberately.\n"
        f"  got:      {got!r}\n  expected: {_EXPECTED_DRIVER_ADVICE!r}"
    )


def test_the_pinned_advice_still_forbids_both_gestures(tmp_path):
    """A second, independent reading of the pinned constant — so that updating
    the pin cannot silently drop the two prohibitions and the cure. Weak by
    construction (see the note above), and kept only because a pin nobody
    sanity-checks is a pin that can be updated to anything."""
    lowered = _EXPECTED_DRIVER_ADVICE.lower()
    assert "do not hand-resolve" in lowered
    assert "do not rebase" in lowered
    assert "origin/main" in lowered
    assert "+n/-0" in lowered
