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
    assert "status_UNKNOWN" not in out or "updated=1" in out


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
    """3/38 UNKNOWN is the MEASURED warm baseline — it must cost nothing."""
    warm = _blind(3, 35)
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
