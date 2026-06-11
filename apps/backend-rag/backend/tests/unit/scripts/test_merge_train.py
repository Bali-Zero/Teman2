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
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert (d.action, d.reason) == ("pause", "main_red")

    def test_red_main_does_not_pause_revert_lane(self):
        d = train.decide_head(
            self._head(), main_green=False, deploy_in_flight=False,
            is_revert=True, failed_required=[], rerolled_already=False,
        )
        assert d.action == "update_branch"

    def test_deploy_in_flight_pauses(self):
        d = train.decide_head(
            self._head(), main_green=True, deploy_in_flight=True,
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert (d.action, d.reason) == ("pause", "fly_deploy_in_flight")

    def test_conflicts_comment_and_skip(self):
        d = train.decide_head(
            self._head("DIRTY"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert d.action == "comment_and_skip"
        assert "conflicts" in d.details["comment"]

    def test_red_checks_reroll_once_then_skip(self):
        first = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=["Backend Tests (Python)"],
            rerolled_already=False,
        )
        assert first.action == "reroll_failed"
        second = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=["Backend Tests (Python)"],
            rerolled_already=True,
        )
        assert second.action == "comment_and_skip"
        assert second.reason == "red_checks"

    def test_behind_updates_branch(self):
        d = train.decide_head(
            self._head("BEHIND"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert d.action == "update_branch"

    def test_unknown_state_waits_never_mutates(self):
        d = train.decide_head(
            self._head("UNKNOWN"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert d.action == "wait"

    def test_blocked_with_green_checks_waits(self):
        d = train.decide_head(
            self._head("BLOCKED"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert d.action == "wait"

    def test_clean_is_none_github_automerge_finishes(self):
        d = train.decide_head(
            self._head("CLEAN"), main_green=True, deploy_in_flight=False,
            is_revert=False, failed_required=[], rerolled_already=False,
        )
        assert d.action == "none"


class TestFailedRequiredChecks:
    def test_only_required_contexts_count(self):
        detail = {
            "statusCheckRollup": [
                {"name": "Backend Tests (Python)", "conclusion": "FAILURE"},
                {"name": "SonarQube Code Analysis", "conclusion": "FAILURE"},
                {"name": "E2E Tests (Playwright)", "conclusion": "SUCCESS"},
            ]
        }
        required = {"Backend Tests (Python)", "E2E Tests (Playwright)"}
        assert train.failed_required_checks(detail, required) == [
            "Backend Tests (Python)"
        ]

    def test_empty_rollup_is_clean(self):
        assert train.failed_required_checks({}, {"X"}) == []
