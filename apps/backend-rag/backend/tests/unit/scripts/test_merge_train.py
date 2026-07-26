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
    def test_fifo_by_number(self):
        q = train.order_queue([_pr(30), _pr(10), _pr(20)])
        assert [p["number"] for p in q] == [10, 20, 30]

    def test_auto_revert_priority_lane(self):
        # Spec §10.1: the revert-PR (highest number) jumps to the head.
        q = train.order_queue([_pr(10), _pr(20), _pr(99, labels=["auto-revert"])])
        assert [p["number"] for p in q] == [99, 10, 20]

    def test_no_train_label_excluded_and_unarmed_excluded(self):
        q = train.order_queue(
            [_pr(10, labels=["no-train"]), _pr(20, automerge=False), _pr(30)]
        )
        assert [p["number"] for p in q] == [30]


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
