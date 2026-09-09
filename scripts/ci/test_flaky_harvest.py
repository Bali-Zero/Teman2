#!/usr/bin/env python3
"""Unit tests for scripts/ci/flaky_harvest.py — pure functions only, zero network. Same style as
scripts/ci/test_change_map.py (unittest.TestCase, `import flaky_harvest as fh`)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import flaky_harvest as fh


class TestExtractPrNumber(unittest.TestCase):
    def test_matches_queue_ref(self):
        ref = "gh-readonly-queue/main/pr-6058-603f1f76b4e1606dc5ba5037b7adabdd1fd1cf93"
        self.assertEqual(fh.extract_pr_number_from_queue_ref(ref), 6058)

    def test_non_queue_ref_returns_none(self):
        self.assertIsNone(fh.extract_pr_number_from_queue_ref("agent/air-m5/infra/foo"))

    def test_malformed_queue_ref_returns_none(self):
        self.assertIsNone(fh.extract_pr_number_from_queue_ref("gh-readonly-queue/main/not-a-pr"))


class TestExtractFailedTestIds(unittest.TestCase):
    def test_pytest_failed_line(self):
        log = (
            "some setup noise\n"
            "FAILED tests/test_foo.py::test_bar - AssertionError: boom\n"
            "more noise\n"
            "FAILED tests/test_baz.py::test_qux\n"
        )
        self.assertEqual(
            fh.extract_failed_test_ids(log),
            ["tests/test_foo.py::test_bar", "tests/test_baz.py::test_qux"],
        )

    def test_no_failed_lines(self):
        self.assertEqual(fh.extract_failed_test_ids("all green\nnothing here\n"), [])

    def test_failed_must_be_line_start(self):
        # a line merely containing "FAILED" mid-line (e.g. a summary sentence) must not match —
        # only pytest's own `FAILED <nodeid>` line-start form counts as a real signal.
        log = "3 tests FAILED overall\n"
        self.assertEqual(fh.extract_failed_test_ids(log), [])


class TestFilterRuns(unittest.TestCase):
    def _run(self, event, status, created_at, **extra):
        return {"event": event, "status": status, "createdAt": created_at, "headSha": "x", "headBranch": "b", **extra}

    def test_keeps_recent_completed_pr_and_merge_group(self):
        now = datetime(2026, 9, 10, tzinfo=timezone.utc)
        runs = [
            self._run("pull_request", "completed", "2026-09-09T12:00:00Z"),
            self._run("merge_group", "completed", "2026-09-08T12:00:00Z"),
            self._run("push", "completed", "2026-09-09T12:00:00Z"),  # wrong event
            self._run("pull_request", "in_progress", "2026-09-09T12:00:00Z"),  # not completed
            self._run("pull_request", "completed", "2026-08-01T12:00:00Z"),  # too old
        ]
        kept = fh.filter_runs(runs, days=7, now=now)
        self.assertEqual(len(kept), 2)
        self.assertEqual({r["event"] for r in kept}, {"pull_request", "merge_group"})


class TestIndexAndGroup(unittest.TestCase):
    def test_index_pr_runs_by_sha(self):
        runs = [
            {"event": "pull_request", "headSha": "aaa", "databaseId": 1, "createdAt": "t1"},
            {"event": "pull_request", "headSha": "aaa", "databaseId": 2, "createdAt": "t2"},
            {"event": "merge_group", "headSha": "bbb", "databaseId": 3, "createdAt": "t3"},
        ]
        idx = fh.index_pr_runs_by_sha(runs)
        self.assertEqual(len(idx["aaa"]), 2)
        self.assertNotIn("bbb", idx)

    def test_group_merge_group_runs_by_pr_sorted(self):
        runs = [
            {
                "event": "merge_group",
                "headBranch": "gh-readonly-queue/main/pr-100-shaZ",
                "createdAt": "2026-09-09T10:00:00Z",
                "databaseId": 2,
            },
            {
                "event": "merge_group",
                "headBranch": "gh-readonly-queue/main/pr-100-shaY",
                "createdAt": "2026-09-09T09:00:00Z",
                "databaseId": 1,
            },
            {
                "event": "pull_request",
                "headBranch": "agent/foo",
                "createdAt": "2026-09-09T09:00:00Z",
                "databaseId": 3,
            },
        ]
        by_pr = fh.group_merge_group_runs_by_pr(runs)
        self.assertEqual(list(by_pr.keys()), [100])
        self.assertEqual([r["databaseId"] for r in by_pr[100]], [1, 2])  # sorted by createdAt


class TestFindMatchingPrRun(unittest.TestCase):
    def test_returns_latest_by_created_at(self):
        by_sha = {
            "abc": [
                {"databaseId": 1, "createdAt": "2026-09-09T09:00:00Z"},
                {"databaseId": 2, "createdAt": "2026-09-09T10:00:00Z"},
            ]
        }
        run = fh.find_matching_pr_run(by_sha, "abc")
        self.assertEqual(run["databaseId"], 2)

    def test_none_sha_returns_none(self):
        self.assertIsNone(fh.find_matching_pr_run({"abc": [{}]}, None))

    def test_missing_sha_returns_none(self):
        self.assertIsNone(fh.find_matching_pr_run({"abc": [{}]}, "zzz"))


class TestClassifyJobPair(unittest.TestCase):
    def test_flake_candidate_success_then_failure(self):
        job_a = {"conclusion": "success", "databaseId": 10}
        job_b = {"conclusion": "failure", "databaseId": 20}
        p = fh.classify_job_pair("Backend Tests", job_a, job_b, 111, 222, "pr_vs_queue")
        self.assertEqual(p.category, "flake_candidate")
        self.assertEqual(p.failing_run_id, 222)
        self.assertEqual(p.failing_job_id, 20)

    def test_flake_candidate_failure_then_success(self):
        job_a = {"conclusion": "failure", "databaseId": 10}
        job_b = {"conclusion": "success", "databaseId": 20}
        p = fh.classify_job_pair("Backend Tests", job_a, job_b, 111, 222, "queue_reentry")
        self.assertEqual(p.category, "flake_candidate")
        self.assertEqual(p.failing_run_id, 111)
        self.assertEqual(p.failing_job_id, 10)

    def test_real_red_both_failed(self):
        job_a = {"conclusion": "failure", "databaseId": 10}
        job_b = {"conclusion": "failure", "databaseId": 20}
        p = fh.classify_job_pair("Backend Tests", job_a, job_b, 111, 222, "pr_vs_queue")
        self.assertEqual(p.category, "real_red")
        self.assertIsNone(p.failing_run_id)

    def test_both_success(self):
        job_a = {"conclusion": "success", "databaseId": 10}
        job_b = {"conclusion": "success", "databaseId": 20}
        p = fh.classify_job_pair("X", job_a, job_b, 1, 2, "pr_vs_queue")
        self.assertEqual(p.category, "both_success")

    def test_not_comparable_skipped(self):
        job_a = {"conclusion": "skipped", "databaseId": 10}
        job_b = {"conclusion": "success", "databaseId": 20}
        p = fh.classify_job_pair("X", job_a, job_b, 1, 2, "pr_vs_queue")
        self.assertEqual(p.category, "not_comparable")


class TestPairJobs(unittest.TestCase):
    def test_matches_by_name_only(self):
        jobs_a = [
            {"name": "Backend Tests", "conclusion": "success", "databaseId": 1},
            {"name": "Only in A", "conclusion": "success", "databaseId": 2},
        ]
        jobs_b = [
            {"name": "Backend Tests", "conclusion": "failure", "databaseId": 3},
            {"name": "Only in B", "conclusion": "failure", "databaseId": 4},
        ]
        results = fh.pair_jobs(jobs_a, jobs_b, 100, 200, "pr_vs_queue")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].job_name, "Backend Tests")
        self.assertEqual(results[0].category, "flake_candidate")


class TestAggregate(unittest.TestCase):
    def test_counts_candidates_and_observations(self):
        pairs = [
            fh.PairResult("Job A", "pr_vs_queue", 1, 2, "success", "failure", "flake_candidate", 2, 20),
            fh.PairResult("Job A", "pr_vs_queue", 3, 4, "failure", "failure", "real_red"),
            fh.PairResult("Job A", "pr_vs_queue", 5, 6, "success", "success", "both_success"),
            fh.PairResult("Job B", "queue_reentry", 7, 8, "skipped", "success", "not_comparable"),
        ]
        stats = fh.aggregate(pairs)
        self.assertEqual(stats["Job A"].candidates, 1)
        self.assertEqual(stats["Job A"].observations, 3)
        self.assertEqual(stats["Job A"].real_red, 1)
        self.assertEqual(stats["Job A"].run_ids, [1, 2])
        self.assertNotIn("Job B", stats)  # only not_comparable observations -> never inserted


class TestRenderMarkdown(unittest.TestCase):
    def test_header_states_thresholds_not_applied(self):
        result = fh.HarvestResult(
            repo="Bali-Zero/Teman2",
            workflow="tests.yml",
            days=7,
            generated_at="2026-09-10T00:00:00+00:00",
            total_runs_scanned=10,
            pr_runs=6,
            merge_group_runs=4,
            unique_prs_in_queue=4,
            prs_unreadable=0,
            prs_no_matching_pr_run=1,
            pairs=[],
            stats={},
            failed_test_counts=fh.Counter(),
            gh_errors=0,
        )
        md = fh.render_markdown(result)
        self.assertIn("NOT applied", md)
        self.assertIn("owner ruling pending", md)
        self.assertIn("Bali-Zero/Teman2", md)
        self.assertIn("Finding:", md)  # prs_no_matching_pr_run > 0 triggers the coverage note

    def test_empty_stats_renders_without_crash(self):
        result = fh.HarvestResult(
            repo="r", workflow="w", days=7, generated_at="t",
            total_runs_scanned=0, pr_runs=0, merge_group_runs=0,
            unique_prs_in_queue=0, prs_unreadable=0, prs_no_matching_pr_run=0,
            pairs=[], stats={}, failed_test_counts=fh.Counter(), gh_errors=0,
        )
        md = fh.render_markdown(result)
        self.assertIn("No comparable job pairs found", md)
        self.assertIn("No test ids extracted", md)
        self.assertIn("JOB-level failures", md)


class TestBuildMailboxSummary(unittest.TestCase):
    def test_mentions_thresholds_pending(self):
        result = fh.HarvestResult(
            repo="r", workflow="w", days=7, generated_at="t",
            total_runs_scanned=20, pr_runs=10, merge_group_runs=10,
            unique_prs_in_queue=10, prs_unreadable=0, prs_no_matching_pr_run=0,
            pairs=[], stats={"Job A": fh.JobStats(candidates=2, observations=5)},
            failed_test_counts=fh.Counter(), gh_errors=0,
        )
        summary = fh.build_mailbox_summary(result)
        self.assertIn("NOT applied", summary)
        self.assertIn("2 flake candidates", summary)
        self.assertIn("Job A", summary)


if __name__ == "__main__":
    unittest.main()
