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

    def test_guilt_visa_engine_models_edit_also_runs_frontend(self) -> None:
        # Red-team HIGH-8, 2026-08-14: apps/mouth/src/app/(visa-oracle)/
        # visa-oracle/_lib/fact-mapper.test.ts reads this exact backend file
        # directly (extracts every dotted alias="a.b" on ApplicantFactsData
        # as the backend contract via extractApplicantFactPathsFromModelsPy())
        # and fails if the frontend mapper drifts from it.
        result = cm.classify(
            ["apps/backend-rag/backend/services/visa_engine/models.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertTrue(result["domains"]["mouth"])
        self.assertEqual(
            result["suggested_jobs"],
            ["backend-tests", "frontend-tests", "e2e-tests"],
        )

    def test_innocence_sibling_visa_engine_files_do_not_couple_to_frontend(
        self,
    ) -> None:
        # Only models.py itself is the verified contract source — a sibling
        # file in the same package must not inherit the coupling just for
        # living next to it.
        result = cm.classify(
            ["apps/backend-rag/backend/services/visa_engine/engine.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertFalse(result["domains"]["mouth"])
        self.assertNotIn("frontend-tests", result["suggested_jobs"])

    def test_guilt_rulepack_family_edit_also_runs_frontend(self) -> None:
        # Red-team HIGH-8: apps/mouth/.../engine-adapter.test.ts globs every
        # file matching rulepack-prod-\d+.source.json under this exact
        # directory (productionPackFiles()) and fails if a pack introduces a
        # SUPPORT reason code with no frontend copy. A NEW pack is authored
        # before it is activated, so the coupling must match the FAMILY, not
        # one pinned filename.
        for path in (
            "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-008.source.json",
            "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-9.source.json",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertTrue(result["domains"]["mouth"])
                self.assertEqual(
                    result["suggested_jobs"],
                    ["backend-tests", "frontend-tests", "e2e-tests"],
                )

    def test_innocence_non_rulepack_pack_file_does_not_couple_to_frontend(
        self,
    ) -> None:
        # A file in the SAME directory that does not match the test's own
        # basename pattern (e.g. a draft/staging file, or a differently
        # named pack) must not be swept in by an over-broad directory rule —
        # this is deliberately a filename-pattern rule, not a prefix rule.
        for path in (
            "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-staging.json",
            "apps/backend-rag/backend/services/visa_engine/contracts/packs/README.md",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertFalse(result["domains"]["mouth"])
                self.assertNotIn("frontend-tests", result["suggested_jobs"])

    def test_guilt_kbli_canonical_pin_inputs_also_run_frontend(self) -> None:
        # Red-team HIGH-9, 2026-08-14: apps/mouth/src/lib/
        # kbli-canonical-pins.test.ts is a REQUIRED frontend-tests suite (no
        # path filter) that reads these two repo-root data/ files directly
        # and fails on a stale/mismatched sha256 pin.
        for path in (
            "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
            "data/kbli-filiera/membership/batch-a-members.json",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertTrue(result["domains"]["backend_python"])
                self.assertTrue(result["domains"]["mouth"])
                self.assertEqual(
                    result["suggested_jobs"],
                    ["backend-tests", "frontend-tests", "e2e-tests"],
                )

    def test_innocence_other_data_files_do_not_couple_to_kbli_pin_test(
        self,
    ) -> None:
        # Most of data/ (analysis/, competitor/, kb_sources/, ...) has no
        # frontend reader — the coupling above is two EXACT paths, not a
        # directory/prefix widening of the whole data/ tree.
        for path in (
            "data/source_documents/KBLI_2017_TO_2025_MAPPING.json",
            "data/analysis/some_report.json",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertFalse(result["domains"]["mouth"])
                self.assertNotIn("frontend-tests", result["suggested_jobs"])

    def test_guilt_funnel_taxonomy_edit_also_runs_backend(self) -> None:
        # Red-team HIGH-10, 2026-08-14:
        # apps/backend-rag/backend/tests/app/routers/
        # test_analytics_funnel_parity.py reads these two exact
        # packages/core files directly (regex-extracts the FUNNEL_EVENTS /
        # APP_EVENTS `as const` arrays) and pins the backend allowlist as
        # their exact union — editing either without the backend allowlist
        # fails a backend-tests test, on top of the existing
        # packages_core+mouth coupling from the "packages/core/" prefix.
        for path in (
            "packages/core/analytics/funnel-view.ts",
            "packages/core/analytics/funnel-app.ts",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertTrue(result["domains"]["packages_core"])
                self.assertTrue(result["domains"]["mouth"])
                self.assertTrue(result["domains"]["backend_python"])
                self.assertEqual(
                    result["suggested_jobs"],
                    [
                        "backend-tests",
                        "frontend-tests",
                        "packages-core-tests",
                        "e2e-tests",
                    ],
                )

    def test_innocence_other_packages_core_files_do_not_couple_to_backend(
        self,
    ) -> None:
        # Sibling files in the SAME directory (index.ts, useFunnelApp.ts, the
        # *.test.ts files) that test_analytics_funnel_parity.py does not
        # read must not inherit backend_python just for living next door —
        # the coupling above is two EXACT paths, not a directory/prefix rule.
        for path in (
            "packages/core/analytics/index.ts",
            "packages/core/analytics/useFunnelApp.ts",
            "packages/core/analytics/funnel-view.test.ts",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertTrue(result["domains"]["packages_core"])
                self.assertTrue(result["domains"]["mouth"])
                self.assertFalse(result["domains"]["backend_python"])
                self.assertNotIn("backend-tests", result["suggested_jobs"])

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
