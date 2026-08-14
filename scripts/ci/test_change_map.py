#!/usr/bin/env python3
"""Guilt + innocence corpus for the CI change-map."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import change_map as cm


class ChangeMapTests(unittest.TestCase):
    def test_guilt_backend_change_runs_backend_and_e2e(self) -> None:
        result = cm.classify(["apps/backend-rag/backend/app/main.py"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "classified")
        self.assertEqual(result["suggested_jobs"], ["backend-tests", "e2e-tests"])

    def test_guilt_pricing_canonical_edit_also_runs_frontend(self) -> None:
        # 57-run shadow audit, 2026-08-14, run 31648287902: a PR edited only
        # this backend file, and would have skipped frontend-tests under a
        # naive path-domain map — but two mouth vitest suites
        # (pricing-snapshot.test.ts, bali-zero-prices.test.ts) read this
        # exact path directly for drift detection and FAILED. This is the
        # coupling rule's guilt case: the exact canonical path must route to
        # frontend-tests even though nothing under apps/mouth/ changed.
        result = cm.classify(
            ["apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"]
        )
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertTrue(result["domains"]["mouth"])
        self.assertEqual(
            result["suggested_jobs"],
            ["backend-tests", "frontend-tests", "e2e-tests"],
        )

    def test_innocence_other_backend_data_files_do_not_couple_to_frontend(
        self,
    ) -> None:
        # The coupling rule above is an EXACT path, not a directory/prefix on
        # apps/backend-rag/backend/data/ — a sibling data file (including the
        # deprecated 2025 catalog PricingService no longer reads) must NOT
        # pull in frontend-tests just for living next to the canonical one.
        for path in (
            "apps/backend-rag/backend/data/bali_zero_official_prices_2025.json",
            "apps/backend-rag/backend/data/some_other_dataset.json",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertFalse(result["domains"]["mouth"])
                self.assertNotIn("frontend-tests", result["suggested_jobs"])
                self.assertEqual(
                    result["suggested_jobs"], ["backend-tests", "e2e-tests"]
                )

    def test_innocence_docs_only_skips_product_test_jobs(self) -> None:
        result = cm.classify(["docs/runbooks/ci.md", "research/operations/note.json"])
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["docs_content_data"])
        self.assertEqual(result["suggested_jobs"], [])
        self.assertEqual(result["would_skip"], list(cm.TEST_JOBS))

    def test_guilt_each_live_suite_has_a_domain_route(self) -> None:
        cases = {
            "apps/nuzantara-mcp/server.py": "mcp-tests",
            "apps/evaluator/cep/run_cep.py": "evaluator-critical-tests",
            "apps/admin-dashboard/src/app.tsx": "frontend-tests",
            "apps/wa-mirror/src/index.ts": "frontend-tests",
            "packages/core/src/index.ts": "packages-core-tests",
        }
        for path, expected_job in cases.items():
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertIn(expected_job, result["suggested_jobs"])

    def test_guilt_mixed_domains_union_their_jobs(self) -> None:
        result = cm.classify(
            ["apps/backend-rag/backend/app/main.py", "apps/mouth/src/app.tsx"]
        )
        self.assertEqual(
            result["suggested_jobs"],
            ["backend-tests", "frontend-tests", "e2e-tests"],
        )

    def test_guilt_tests_workflow_self_edit_runs_everything(self) -> None:
        result = cm.classify([".github/workflows/tests.yml"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))
        self.assertTrue(result["domains"]["security_sensitive"])

    def test_guilt_shared_ci_infrastructure_runs_everything(self) -> None:
        for path in (".github/actions/setup/action.yml", "scripts/ci/new_guard.py"):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_guilt_unclassified_path_falls_back_to_everything(self) -> None:
        result = cm.classify(["apps/new-product/runtime.rs"])
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "unclassified_paths")
        self.assertEqual(result["unknown_paths"], ["apps/new-product/runtime.rs"])
        self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_guilt_mixed_known_and_unknown_still_runs_everything(self) -> None:
        result = cm.classify(["docs/known.md", "vendor/new-tool/bin.go"])
        self.assertTrue(result["run_all"])
        self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_guilt_executable_hidden_under_docs_is_not_innocent(self) -> None:
        result = cm.classify(["docs/tools/deploy.py"])
        self.assertTrue(result["run_all"])
        self.assertEqual(result["unknown_paths"], ["docs/tools/deploy.py"])

    def test_guilt_enumerator_failure_runs_everything(self) -> None:
        result = cm.classify([cm.ENUMERATION_ERROR])
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "enumeration_failed")
        self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_guilt_empty_set_runs_everything(self) -> None:
        result = cm.classify([])
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "empty_changed_set")

    def test_guilt_traversal_and_absolute_paths_run_everything(self) -> None:
        for path in (
            "docs/../apps/backend-rag/evil.md",
            "/tmp/evil.py",
            " docs/looks-innocent.md",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertTrue(result["run_all"])
                self.assertEqual(result["reason"], "unclassified_paths")

    def test_innocence_leading_dot_slash_is_normalized(self) -> None:
        result = cm.classify(["./apps/mouth/src/app.tsx"])
        self.assertFalse(result["run_all"])
        self.assertIn("frontend-tests", result["suggested_jobs"])

    def test_guilt_root_manifests_fan_out_to_their_runtimes(self) -> None:
        node = cm.classify(["package-lock.json"])
        self.assertIn("frontend-tests", node["suggested_jobs"])
        self.assertIn("packages-core-tests", node["suggested_jobs"])
        python = cm.classify(["apps/backend-rag/requirements.lock.txt"])
        self.assertIn("backend-tests", python["suggested_jobs"])
        self.assertIn("mcp-tests", python["suggested_jobs"])
        self.assertIn("evaluator-critical-tests", python["suggested_jobs"])

    def test_guilt_mdx_reaches_frontend_backend_and_e2e(self) -> None:
        result = cm.classify(["apps/mouth/src/content/example.mdx"])
        self.assertTrue(result["domains"]["mouth"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertEqual(
            result["suggested_jobs"],
            ["backend-tests", "frontend-tests", "e2e-tests"],
        )

    def test_cli_stdout_is_one_compact_json_line(self) -> None:
        script = Path(__file__).with_name("change_map.py")
        completed = subprocess.run(
            [sys.executable, str(script)],
            input="docs/readme.md\n",
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        parsed = json.loads(completed.stdout)
        self.assertEqual(parsed["mode"], "enforcing")
        self.assertFalse(parsed["run_all"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
