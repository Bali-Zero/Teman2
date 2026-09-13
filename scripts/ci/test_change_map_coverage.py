#!/usr/bin/env python3
"""Unit tests for change_map_coverage.py's pure analysis/render layer.

Deliberately never calls `gh` or the network: every test builds fixture
"batch records" in the exact shape build_batch_record() produces, and feeds
them straight into the analyze_*/render_* functions. fetch_* (the only
side-effecting code in the module under test) is exercised only by the
real invocation this PR's Bites observation performs, not here.
"""

from __future__ import annotations

import unittest

import change_map_coverage as cmc


def _classifier(reason, domains=None, unknown_paths=None):
    return {
        "reason": reason,
        "domains": {d: True for d in (domains or [])},
        "unknown_paths": unknown_paths or [],
    }


def _record(
    run_id,
    *,
    pr_number=None,
    jobs_ok=True,
    job_conclusions=None,
    classifier_ok=True,
    classifier=None,
):
    conclusions = dict.fromkeys(cmc.HEAVY_JOBS, "skipped")
    if job_conclusions:
        conclusions.update(job_conclusions)
    return {
        "run_id": run_id,
        "conclusion": "success",
        "created_at": "2026-09-09T00:00:00Z",
        "pr_number": pr_number,
        "jobs_ok": jobs_ok,
        "job_conclusions": conclusions if jobs_ok else {},
        "classifier_ok": classifier_ok,
        "classifier": classifier,
    }


class TestPrNumberFromBranch(unittest.TestCase):
    def test_matches_merge_queue_branch(self):
        branch = "gh-readonly-queue/main/pr-5618-4eed90f149f58ab161e766259c0886b682ecefd2"
        self.assertEqual(cmc._pr_number_from_branch(branch), 5618)

    def test_none_for_other_branches(self):
        self.assertIsNone(cmc._pr_number_from_branch("main"))
        self.assertIsNone(cmc._pr_number_from_branch(None))


class TestJobTriggerDomains(unittest.TestCase):
    def test_derived_from_real_suggested_jobs(self):
        # Mirrors scripts/ci/change_map.py::_suggested_jobs by construction —
        # this test fails the moment that module's routing changes without
        # this module's derivation changing with it.
        self.assertEqual(
            cmc.JOB_TRIGGER_DOMAINS["Backend Tests (Python)"], frozenset({"backend_python"})
        )
        self.assertEqual(cmc.JOB_TRIGGER_DOMAINS["MCP Server Tests"], frozenset({"mcp"}))
        self.assertEqual(
            cmc.JOB_TRIGGER_DOMAINS["Shared Core Package Tests"], frozenset({"packages_core"})
        )
        self.assertEqual(
            cmc.JOB_TRIGGER_DOMAINS["E2E Tests (Playwright)"],
            frozenset({"backend_python", "mouth", "packages_core"}),
        )
        self.assertEqual(
            cmc.JOB_TRIGGER_DOMAINS["Frontend Tests (Next.js) (mouth, true)"],
            frozenset({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}),
        )
        # infra_workflows is deliberately excluded from every per-job set.
        for domains in cmc.JOB_TRIGGER_DOMAINS.values():
            self.assertNotIn("infra_workflows", domains)


class TestReasonCounts(unittest.TestCase):
    def test_counts_known_and_unreadable(self):
        records = [
            _record(1, classifier=_classifier("classified", ["backend_python"])),
            _record(2, classifier=_classifier("unclassified_paths")),
            _record(3, classifier_ok=False, classifier=None),
        ]
        counts = cmc.reason_counts(records)
        self.assertEqual(counts["classified"], 1)
        self.assertEqual(counts["unclassified_paths"], 1)
        self.assertEqual(counts["unreadable"], 1)


class TestJobStats(unittest.TestCase):
    def test_skip_rate_excludes_absent_jobs(self):
        records = [
            _record(1, job_conclusions={"Backend Tests (Python)": "success"}),
            _record(2, job_conclusions={"Backend Tests (Python)": "skipped"}),
            _record(3, jobs_ok=False),  # unreadable jobs: excluded entirely
        ]
        stats = cmc.job_stats(records)
        backend = stats["Backend Tests (Python)"]
        self.assertEqual(backend["runs"], 2)
        self.assertEqual(backend["skipped"], 1)
        self.assertAlmostEqual(backend["skip_pct"], 50.0)

    def test_zero_present_is_zero_percent_not_a_crash(self):
        records = [_record(1, jobs_ok=False)]
        stats = cmc.job_stats(records)
        self.assertEqual(stats["Backend Tests (Python)"]["runs"], 0)
        self.assertEqual(stats["Backend Tests (Python)"]["skip_pct"], 0.0)


class TestEligibleForSkipButRan(unittest.TestCase):
    def test_flags_domain_mismatch_under_fail_open_reason(self):
        # backend_python is NOT in Backend Tests' trigger set here (domains
        # only carries mouth), and reason is fail-open -> eligible.
        rec = _record(
            1,
            pr_number=42,
            job_conclusions={"Backend Tests (Python)": "success"},
            classifier=_classifier(
                "unclassified_paths", domains=["mouth"], unknown_paths=["weird/path.bin"]
            ),
        )
        eligible = cmc.eligible_for_skip_but_ran([rec])
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["job"], "Backend Tests (Python)")
        self.assertEqual(eligible[0]["pr_number"], 42)
        self.assertEqual(eligible[0]["unknown_paths"], ["weird/path.bin"])

    def test_not_eligible_cases(self):
        cases = {
            "domain_matches": _record(
                1,
                job_conclusions={"Backend Tests (Python)": "success"},
                classifier=_classifier("unclassified_paths", domains=["backend_python"]),
            ),
            "reason_classified": _record(
                1,
                job_conclusions={"Backend Tests (Python)": "success"},
                classifier=_classifier("classified", domains=[]),
            ),
            "job_skipped": _record(
                1,
                job_conclusions={"Backend Tests (Python)": "skipped"},
                classifier=_classifier("unclassified_paths", domains=[]),
            ),
        }
        for name, rec in cases.items():
            with self.subTest(name):
                self.assertEqual(cmc.eligible_for_skip_but_ran([rec]), [])


class TestUnknownPathFrequency(unittest.TestCase):
    def test_ranks_and_dedupes_prs(self):
        eligible = [
            {"pr_number": 1, "unknown_paths": ["a.bin", "b.bin"]},
            {"pr_number": 2, "unknown_paths": ["a.bin"]},
            {"pr_number": 1, "unknown_paths": ["a.bin"]},  # same PR twice: dedup in output
        ]
        table = cmc.unknown_path_frequency(eligible, top_n=5)
        by_path = {path: (count, prs) for path, count, prs in table}
        self.assertEqual(by_path["a.bin"], (3, [1, 2]))
        self.assertEqual(by_path["b.bin"], (1, [1]))

    def test_top_n_caps_output(self):
        eligible = [{"pr_number": None, "unknown_paths": [f"p{i}.bin"]} for i in range(30)]
        table = cmc.unknown_path_frequency(eligible, top_n=25)
        self.assertEqual(len(table), 25)


class TestLegitimateDomainCounts(unittest.TestCase):
    def test_infra_workflows_counts_against_every_ran_job(self):
        rec = _record(
            1,
            job_conclusions=dict.fromkeys(cmc.HEAVY_JOBS, "success"),
            classifier=_classifier("classified", domains=["infra_workflows"]),
        )
        counts = cmc.legitimate_domain_counts([rec])
        for job in cmc.HEAVY_JOBS:
            self.assertEqual(counts[(job, "infra_workflows")], 1)

    def test_own_domain_counts_once_per_job(self):
        rec = _record(
            1,
            job_conclusions={"Backend Tests (Python)": "success"},
            classifier=_classifier("classified", domains=["backend_python"]),
        )
        counts = cmc.legitimate_domain_counts([rec])
        self.assertEqual(counts[("Backend Tests (Python)", "backend_python")], 1)

    def test_fail_open_reason_never_counted_as_legitimate(self):
        rec = _record(
            1,
            job_conclusions={"Backend Tests (Python)": "success"},
            classifier=_classifier("unclassified_paths", domains=["backend_python"]),
        )
        self.assertEqual(cmc.legitimate_domain_counts([rec]), {})


class TestRenderReport(unittest.TestCase):
    def test_render_report_is_deterministic_markdown(self):
        records = [
            _record(
                1,
                pr_number=10,
                job_conclusions={"Backend Tests (Python)": "success"},
                classifier=_classifier("classified", domains=["backend_python"]),
            )
        ]
        stats = {"runs_total": 1, "list_err": None, "jobs_unreadable": 0, "classifier_unreadable": 0}
        all_data = {
            "merge_group": (records, stats),
            "pull_request": ([], {"runs_total": 0, "list_err": None, "jobs_unreadable": 0, "classifier_unreadable": 0}),
        }
        report = cmc.render_report(all_data, days=7)
        self.assertIn("measure-only", report)
        self.assertIn("merge_group", report)
        self.assertIn("pull_request", report)
        self.assertIn("Backend Tests (Python)", report)
        # Rendering the same input twice must be byte-identical (pure).
        self.assertEqual(report, cmc.render_report(all_data, days=7))

    def test_render_mail_summary_mentions_report_path(self):
        empty_stats = {"runs_total": 0, "list_err": None, "jobs_unreadable": 0, "classifier_unreadable": 0}
        all_data = {"merge_group": ([], empty_stats), "pull_request": ([], empty_stats)}
        summary = cmc.render_mail_summary(all_data, "docs/reports/change-map-coverage/2026-09-10.md")
        self.assertIn("2026-09-10.md", summary)
        self.assertIn("merge_group", summary)
        self.assertIn("pull_request", summary)


class TestSendMailDryRun(unittest.TestCase):
    def test_dry_run_never_shells_out(self):
        ok, detail = cmc.send_mail("hello", dry_run=True)
        self.assertTrue(ok)
        self.assertIn("dry-run", detail)
        self.assertIn(cmc.MAIL_KEY, detail)


if __name__ == "__main__":
    unittest.main()
