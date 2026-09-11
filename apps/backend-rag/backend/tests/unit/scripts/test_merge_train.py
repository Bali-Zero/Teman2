"""Unit tests for the merge-train coordinator decision logic (pure functions)."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "merge_train.py"
    spec = importlib.util.spec_from_file_location("merge_train_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


train = _load_module()


def _pr(number: int, labels: list[str] | None = None, automerge: bool = True) -> dict:
    return {
        "number": number,
        "labels": [{"name": lbl} for lbl in (labels or [])],
        "autoMergeRequest": {"enabledAt": "x"} if automerge else None,
    }


class TestOrderQueue:
    """`in_queue_numbers` is a required kwarg (2026-08-30 fix): every call
    below passes it explicitly, never relies on a default — the whole point
    of the fix is that there IS no default a caller could silently fall
    back to (see `order_queue`'s own docstring)."""

    def test_fifo_by_number(self):
        q = train.order_queue([_pr(30), _pr(10), _pr(20)], in_queue_numbers=set())
        assert [p["number"] for p in q] == [10, 20, 30]

    def test_auto_revert_priority_lane(self):
        # Spec §10.1: the revert-PR (highest number) jumps to the head.
        q = train.order_queue(
            [_pr(10), _pr(20), _pr(99, labels=["auto-revert"])], in_queue_numbers=set()
        )
        assert [p["number"] for p in q] == [99, 10, 20]

    def test_no_train_label_excluded_and_never_armed_excluded(self):
        """A PR opted out (no-train label) and a PR genuinely never armed
        (autoMergeRequest null AND not in the queue snapshot) are both
        excluded — the correct, narrower half of the old test's name.
        `test_queue_accepted_pr_with_null_automerge_is_still_eligible` below
        is the half the old test got backwards: null alone is NOT "unarmed",
        it is also what a queue-accepted PR reads."""
        q = train.order_queue(
            [_pr(10, labels=["no-train"]), _pr(20, automerge=False), _pr(30)],
            in_queue_numbers=set(),
        )
        assert [p["number"] for p in q] == [30]

    def test_queue_accepted_pr_with_null_automerge_is_still_eligible(self):
        """2026-08-30 fix — the PR #5275 shape: GitHub's queue has ACCEPTED
        this PR (autoMergeRequest reads null because the request was
        CONSUMED on entry, not because it was disarmed), and the queue
        snapshot (`in_queue_numbers`, GraphQL `mergeQueueEntry`'s positive
        probe) proves it. Pre-fix, `order_queue` read the null field alone
        and silently dropped this PR from `eligible` — exactly the bug this
        test exists to catch (verified against the pre-fix source: this
        assertion fails there, asserting `[30]` instead of `[20, 30]` —
        the corrected test does not merely pass, it discriminates). The
        test above proves this fix does not also flip a genuinely
        never-armed PR (null AND absent from the snapshot) to eligible."""
        q = train.order_queue(
            [_pr(20, automerge=False), _pr(30)], in_queue_numbers={20},
        )
        assert [p["number"] for p in q] == [20, 30]


class TestSkiplist:
    def test_keyed_by_pr_and_sha(self):
        skiplist = {"10:abc:conflicts": {"ts": time.time()}}
        assert train.skiplist_active(skiplist, 10, "abc") is True
        # New push (new sha) clears it.
        assert train.skiplist_active(skiplist, 10, "def") is False
        assert train.skiplist_active(skiplist, 11, "abc") is False

    def test_api_error_entries_expire_on_ttl(self):
        fresh = {"10:abc:api_error": {"ts": time.time()}}
        stale = {"10:abc:api_error": {"ts": time.time() - 7200}}
        assert train.skiplist_active(fresh, 10, "abc") is True
        assert train.skiplist_active(stale, 10, "abc") is False

    def test_non_api_error_entries_do_not_expire(self):
        old = {"10:abc:red_checks": {"ts": time.time() - 999999}}
        assert train.skiplist_active(old, 10, "abc") is True


class TestDecideHead:
    def _head(self, state: str = "BEHIND", sha: str = "abc") -> dict:
        return {"number": 42, "mergeStateStatus": state, "headRefOid": sha}

    def test_red_main_pauses_normal_prs(self):
        d = train.decide_head(
            self._head(), main_green=False, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert (d.action, d.reason) == ("pause", "main_red")

    def test_red_main_does_not_pause_revert_lane(self):
        d = train.decide_head(
            self._head(), main_green=False, deploy_in_flight=False,
            is_revert=True, blocking_required={}, rerolled_already=False,
        )
        assert d.action == "update_branch"

    def test_deploy_in_flight_pauses(self):
        d = train.decide_head(
            self._head(), main_green=True, deploy_in_flight=True,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert (d.action, d.reason) == ("pause", "fly_deploy_in_flight")

    def test_conflicts_comment_and_skip(self):
        d = train.decide_head(
            self._head("DIRTY"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert d.action == "comment_and_skip"
        assert "conflicts" in d.details["comment"]

    def test_red_checks_reroll_once_then_skip(self):
        first = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={"Backend Tests (Python)": "FAILURE"},
            rerolled_already=False,
        )
        assert first.action == "reroll_failed"
        second = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={"Backend Tests (Python)": "FAILURE"},
            rerolled_already=True,
        )
        assert second.action == "comment_and_skip"
        assert second.reason == "red_checks"
        # task #40: the comment must name the LITERAL state, not assume
        # "failed" — this is what lets a human/session act on a CANCELLED
        # or unrecognized blocker instead of a generic "checks failed".
        assert "Backend Tests (Python): FAILURE" in second.details["comment"]

    def test_red_checks_reroll_once_then_skip_names_a_non_failure_state(self):
        """The PR #3146 shape: a required context stuck CANCELLED (not
        FAILURE) must still reroll-then-skip, and the skip comment must
        name CANCELLED literally so nobody reads it as a generic failure."""
        first = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False,
            blocking_required={"P6 parallelize-hypothesis falsifiable gates": "CANCELLED"},
            rerolled_already=False,
        )
        assert first.action == "reroll_failed"
        second = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False,
            blocking_required={"P6 parallelize-hypothesis falsifiable gates": "CANCELLED"},
            rerolled_already=True,
        )
        assert second.action == "comment_and_skip"
        assert "P6 parallelize-hypothesis falsifiable gates: CANCELLED" in second.details["comment"]

    def test_behind_updates_branch(self):
        d = train.decide_head(
            self._head("BEHIND"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert d.action == "update_branch"

    def test_unknown_state_waits_never_mutates(self):
        d = train.decide_head(
            self._head("UNKNOWN"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert d.action == "wait"

    def test_blocked_with_green_checks_waits(self):
        d = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert d.action == "wait"

    def test_clean_is_none_github_automerge_finishes(self):
        d = train.decide_head(
            self._head("CLEAN"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
        )
        assert d.action == "none"


class TestMissingRequiredContexts:
    """Head-of-line trap seen live on #994: protection gained new required
    workflows after the PR's last push → BLOCKED forever with zero failures."""

    def _head(self, state: str = "BLOCKED") -> dict:
        return {"number": 994, "mergeStateStatus": state, "headRefOid": "abc"}

    def test_helper_returns_required_minus_present(self):
        detail = {"statusCheckRollup": [{"name": "Backend Tests (Python)", "conclusion": "SUCCESS"}]}
        assert train.missing_required_contexts(
            detail, {"Backend Tests (Python)", "verify-the-verifiers"}
        ) == ["verify-the-verifiers"]

    def test_blocked_with_missing_required_updates_branch_once(self):
        d = train.decide_head(
            self._head(), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
            missing_required=["verify-the-verifiers"], update_for_missing_already=False,
        )
        assert (d.action, d.reason) == ("update_branch", "missing_required_contexts")

    def test_missing_persists_after_update_comments_and_skips(self):
        d = train.decide_head(
            self._head(), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
            missing_required=["verify-the-verifiers"], update_for_missing_already=True,
        )
        assert (d.action, d.reason) == ("comment_and_skip", "missing_required_persistent")

    def test_missing_ignored_when_not_blocked(self):
        d = train.decide_head(
            self._head("CLEAN"), main_green=True, deploy_in_flight=False,
            is_revert=False, blocking_required={}, rerolled_already=False,
            missing_required=["verify-the-verifiers"], update_for_missing_already=False,
        )
        assert d.action == "none"


class TestRollupState:
    """`_rollup_state` — the type-branch that must run BEFORE `.conclusion`
    is ever read. Fixtures are the REAL shapes verified live on this repo's
    open PRs 2026-07-26 (`gh pr view <N> --json statusCheckRollup`), not
    guessed ones."""

    def test_status_context_reads_state_not_conclusion(self):
        # Real Vercel StatusContext shape: no "status"/"conclusion" keys
        # at all, only "state".
        entry = {
            "__typename": "StatusContext", "context": "Vercel",
            "state": "SUCCESS", "startedAt": "2026-07-26T04:30:11Z",
            "targetUrl": "https://vercel.com/x",
        }
        assert train._rollup_state(entry) == "SUCCESS"

    def test_running_checkrun_reads_status_not_empty_conclusion(self):
        # Real in-flight CheckRun shape: conclusion is "" (empty string,
        # NOT null/absent) — the jq/`or`-fallback trap this function must
        # not fall into.
        entry = {"status": "QUEUED", "conclusion": "", "name": "x"}
        assert train._rollup_state(entry) == "QUEUED"
        entry2 = {"status": "IN_PROGRESS", "conclusion": "", "name": "x"}
        assert train._rollup_state(entry2) == "IN_PROGRESS"

    def test_completed_checkrun_reads_conclusion(self):
        entry = {"status": "COMPLETED", "conclusion": "CANCELLED", "name": "x"}
        assert train._rollup_state(entry) == "CANCELLED"

    def test_completed_checkrun_missing_conclusion_key_is_empty_not_crash(self):
        entry = {"status": "COMPLETED", "name": "x"}
        assert train._rollup_state(entry) == ""


class TestBlockingRequiredChecks:
    """task #40 (2026-07-26): stop enumerating bad states — enumerate the
    required contexts and demand SUCCESS/NEUTRAL/SKIPPED, treat
    QUEUED/IN_PROGRESS/PENDING as progressing, and everything else (named
    or not) as blocking. This is the fix for PR #3146 sitting armed 12h on
    a CANCELLED required context that the old FAILURE-only check ignored."""

    def test_only_required_contexts_count(self):
        detail = {
            "statusCheckRollup": [
                {"status": "COMPLETED", "conclusion": "FAILURE", "name": "Backend Tests (Python)"},
                {"status": "COMPLETED", "conclusion": "FAILURE", "name": "SonarQube Code Analysis"},
                {"status": "COMPLETED", "conclusion": "SUCCESS", "name": "E2E Tests (Playwright)"},
            ]
        }
        required = {"Backend Tests (Python)", "E2E Tests (Playwright)"}
        assert train.blocking_required_checks(detail, required) == {
            "Backend Tests (Python)": "FAILURE"
        }

    def test_empty_rollup_is_clean(self):
        assert train.blocking_required_checks({}, {"X"}) == {}

    # --- GUILT: every state that must be caught -----------------------

    def test_guilt_failure_still_blocks(self):
        """Regression guard: the original, narrower behavior must survive
        the inversion unchanged."""
        detail = {"statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "FAILURE", "name": "X"}
        ]}
        assert train.blocking_required_checks(detail, {"X"}) == {"X": "FAILURE"}

    def test_guilt_cancelled_blocks_the_pr3146_shape(self):
        """The actual live incident: a required context stuck CANCELLED,
        which the pre-#40 code silently treated as clean."""
        detail = {"statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "CANCELLED",
             "name": "P6 parallelize-hypothesis falsifiable gates"},
        ]}
        assert train.blocking_required_checks(
            detail, {"P6 parallelize-hypothesis falsifiable gates"}
        ) == {"P6 parallelize-hypothesis falsifiable gates": "CANCELLED"}

    def test_guilt_timed_out_and_action_required_and_stale_block(self):
        detail = {"statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "TIMED_OUT", "name": "A"},
            {"status": "COMPLETED", "conclusion": "ACTION_REQUIRED", "name": "B"},
            {"status": "COMPLETED", "conclusion": "STALE", "name": "C"},
        ]}
        assert train.blocking_required_checks(detail, {"A", "B", "C"}) == {
            "A": "TIMED_OUT", "B": "ACTION_REQUIRED", "C": "STALE",
        }

    def test_guilt_unrecognized_future_state_blocks_fail_closed(self):
        """The whole point of the inversion: a state nobody has named yet
        must still block, not slide through as clean. This is what makes
        the fourth blocking state (whatever it turns out to be) visible
        without another 12-hour incident to discover it."""
        detail = {"statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "SOME_FUTURE_GITHUB_STATE", "name": "X"}
        ]}
        assert train.blocking_required_checks(detail, {"X"}) == {
            "X": "SOME_FUTURE_GITHUB_STATE"
        }

    def test_guilt_status_context_error_state_blocks(self):
        detail = {"statusCheckRollup": [
            {"__typename": "StatusContext", "context": "some-external-ci", "state": "ERROR"}
        ]}
        assert train.blocking_required_checks(detail, {"some-external-ci"}) == {
            "some-external-ci": "ERROR"
        }

    # --- INNOCENCE: every state that must NOT block --------------------

    def test_innocence_success_neutral_skipped_do_not_block(self):
        detail = {"statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "SUCCESS", "name": "A"},
            {"status": "COMPLETED", "conclusion": "NEUTRAL", "name": "B"},
            {"status": "COMPLETED", "conclusion": "SKIPPED", "name": "C"},
        ]}
        assert train.blocking_required_checks(detail, {"A", "B", "C"}) == {}

    def test_innocence_queued_in_progress_pending_are_progressing_not_blocking(self):
        detail = {"statusCheckRollup": [
            {"status": "QUEUED", "conclusion": "", "name": "A"},
            {"status": "IN_PROGRESS", "conclusion": "", "name": "B"},
            {"__typename": "StatusContext", "context": "C", "state": "PENDING"},
        ]}
        assert train.blocking_required_checks(detail, {"A", "B", "C"}) == {}

    def test_innocence_real_vercel_status_context_success_does_not_block(self):
        # Exact shape captured live from `gh pr view --json statusCheckRollup`.
        detail = {"statusCheckRollup": [
            {"__typename": "StatusContext", "context": "Vercel", "state": "SUCCESS",
             "startedAt": "2026-07-26T04:48:38Z", "targetUrl": "https://vercel.com/x"},
        ]}
        assert train.blocking_required_checks(detail, {"Vercel"}) == {}

    def test_innocence_non_required_context_never_counted_regardless_of_state(self):
        detail = {"statusCheckRollup": [
            {"status": "COMPLETED", "conclusion": "FAILURE", "name": "not-required-here"},
        ]}
        assert train.blocking_required_checks(detail, {"required-instead"}) == {}


def _run(
    id_: int,
    workflow_id: int,
    run_number: int,
    status: str,
    conclusion: str | None,
    run_attempt: int = 1,
) -> dict:
    """A workflow-run object shaped exactly like the live API response
    (verified 2026-07-26 against a real head_sha: `id`, `workflow_id`,
    `run_number`, `run_attempt`, `status`, `conclusion` are all real
    fields, not assumed ones)."""
    return {
        "id": id_,
        "workflow_id": workflow_id,
        "run_number": run_number,
        "run_attempt": run_attempt,
        "status": status,
        "conclusion": conclusion,
    }


class TestRerollFailedRuns:
    """`reroll_failed_runs` is a side-effect function — mock `gh_json` (the
    fetch) and `gh` (the rerun call) rather than hitting the network. Task
    #40 follow-up (team-lead review, 2026-07-26): the PREVIOUS version
    reran every non-OK run it saw, with no defense against rerunning a run
    already superseded by a newer one for the same workflow — main alone
    showed 15/20 push-runs cancelled the same night, nearly all of them
    supersede-cancels, not stuck ones. These tests prove guard 1
    (supersede-vs-stuck) and guard 2 (attempt cap) independently."""

    def _wire(self, monkeypatch, runs: list[dict]):
        monkeypatch.setattr(train, "gh_json", lambda args, **kw: {"workflow_runs": runs})
        reran: list[list[str]] = []

        def fake_gh(cmd, **kw):
            reran.append(cmd)
            return ""

        monkeypatch.setattr(train, "gh", fake_gh)
        return reran

    # --- INNOCENCE: the shape that must still work -----------------------

    def test_innocence_pr3146_shape_cancelled_with_no_successor_gets_rerun(self, monkeypatch):
        """The exact PR #3146 shape: one run, one workflow, CANCELLED,
        nothing newer behind it — must still be rerun (full rerun, no
        `--failed`, since a fully-cancelled run has no failed jobs)."""
        reran = self._wire(monkeypatch, [
            _run(30166697962, 555, 100, "completed", "cancelled"),
        ])
        ids = train.reroll_failed_runs(3146, "deadbeef")
        assert ids == [30166697962]
        assert reran == [["run", "rerun", "30166697962", "--repo", train.REPO]]

    def test_innocence_failure_conclusion_still_uses_failed_flag(self, monkeypatch):
        reran = self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "failure"),
        ])
        ids = train.reroll_failed_runs(1, "sha")
        assert ids == [1]
        assert reran == [["run", "rerun", "1", "--repo", train.REPO, "--failed"]]

    def test_innocence_ok_conclusions_never_rerun(self, monkeypatch):
        reran = self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "success"),
            _run(2, 556, 100, "completed", "neutral"),
            _run(3, 557, 100, "completed", "skipped"),
        ])
        assert train.reroll_failed_runs(1, "sha") == []
        assert reran == []

    # --- GUILT: guard 1, supersede-vs-stuck -------------------------------

    def test_guilt_supersede_cancelled_run_with_successful_successor_not_rerun(self, monkeypatch):
        """Same workflow_id, two runs at the same head_sha: an OLDER
        cancelled one and a NEWER (higher run_number) successful one. The
        older is presumed superseded — rerunning it is pure waste and the
        newer one already carries the real verdict."""
        reran = self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "cancelled"),
            _run(2, 555, 101, "completed", "success"),
        ])
        assert train.reroll_failed_runs(1, "sha") == []
        assert reran == []

    def test_guilt_supersede_cancelled_run_with_in_progress_successor_not_rerun(self, monkeypatch):
        """The newer sibling hasn't finished yet — still not our job to
        touch either run: the newer one is progressing, the older one is
        superseded."""
        reran = self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "cancelled"),
            _run(2, 555, 101, "in_progress", None),
        ])
        assert train.reroll_failed_runs(1, "sha") == []
        assert reran == []

    def test_guilt_multiple_workflows_each_judged_independently(self, monkeypatch):
        """Guard 1 groups by workflow_id — a stuck run on workflow A must
        still be rerun even while workflow B has a legitimate supersede
        pending, and vice versa. Proves the grouping doesn't over-suppress
        across unrelated workflows."""
        reran = self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "cancelled"),        # A: stuck, alone
            _run(2, 556, 100, "completed", "cancelled"),        # B: superseded...
            _run(3, 556, 101, "completed", "success"),          # ...by this
        ])
        assert train.reroll_failed_runs(1, "sha") == [1]
        assert reran == [["run", "rerun", "1", "--repo", train.REPO]]

    # --- GUILT: guard 2, attempt cap ---------------------------------------

    def test_guilt_attempt_cap_stops_rerolling_past_the_limit(self, monkeypatch):
        reran = self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "cancelled",
                 run_attempt=train.MAX_RERUN_ATTEMPTS + 1),
        ])
        assert train.reroll_failed_runs(1, "sha") == []
        assert reran == []

    def test_innocence_attempt_at_the_cap_still_rerolls(self, monkeypatch):
        """Off-by-one check: exactly at the cap is still allowed — the cap
        blocks the attempt AFTER the limit, not the limit itself."""
        self._wire(monkeypatch, [
            _run(1, 555, 100, "completed", "cancelled",
                 run_attempt=train.MAX_RERUN_ATTEMPTS),
        ])
        assert train.reroll_failed_runs(1, "sha") == [1]
