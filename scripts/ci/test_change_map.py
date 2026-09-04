#!/usr/bin/env python3
"""Guilt + innocence corpus for the CI change-map."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import change_map as cm
import security_gate_flags as sgf


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

    def test_guilt_kb_corpus_files_run_the_backend_suite_that_guards_them(
        self,
    ) -> None:
        # kb/ landed 2026-08-25 (#4907/#4974) and was never wired into the
        # routing tables, so every kb/-only PR fell into `unknown_paths` ->
        # run_all=true. Measured on PR #5662 (one file, kb/inventory/
        # immigration.yaml): CodeQL-python 14m01s, plus ~9m of Snyk/Bandit/
        # Safety, against a YAML data file.
        #
        # The obvious cure is wrong. Routing kb/ to docs_content_data ALONE
        # would switch off the tests that protect these very files:
        # apps/backend-rag/backend/tests/unit/kb/ holds nine suites that read
        # kb/inventory/*.yaml directly (test_kb_inventory_contract,
        # test_kb_topic_contract, test_kb_inventory_probe_topic, ...), and
        # _suggested_jobs() never grants docs_content_data any of the six
        # jobs. The precedent is data/ -- both backend_python and
        # docs_content_data -- so the corpus keeps its own guard.
        for path in (
            "kb/inventory/immigration.yaml",
            "kb/topics/immigration.yaml",
            "kb/ops/probe_retrieval.py",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertEqual(result["unknown_paths"], [])
                self.assertTrue(result["domains"]["backend_python"])
                self.assertIn("backend-tests", result["suggested_jobs"])

    def test_innocence_kb_does_not_drag_in_the_frontend_or_e2e_suites(
        self,
    ) -> None:
        # The other half: kb/ is backend data, so widening it to the FRONTEND
        # would trade one kind of waste for another. data/ reaches mouth only
        # through an explicit filename rule (the KBLI canonical pins); nothing
        # under kb/ is read by a frontend suite.
        #
        # e2e-tests is deliberately NOT asserted absent. It is granted by
        # `backend_python` at _suggested_jobs()'s own last rule
        # (`domains.intersection({"backend_python", "mouth", "packages_core"})`),
        # so demanding the backend suite that guards this corpus necessarily
        # brings e2e with it. This test's first draft asserted otherwise and
        # was wrong about the code, not the other way round — recorded here so
        # nobody "fixes" the rule to satisfy a mistaken expectation.
        result = cm.classify(["kb/inventory/immigration.yaml"])
        self.assertFalse(result["domains"]["mouth"])
        self.assertFalse(result["domains"]["packages_core"])
        self.assertNotIn("frontend-tests", result["suggested_jobs"])
        self.assertNotIn("packages-core-tests", result["suggested_jobs"])
        self.assertNotIn("mcp-tests", result["suggested_jobs"])

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

    def test_innocence_evidence_pack_alone_skips_product_test_jobs(self) -> None:
        # Zero's order 2026-08-27: docs-only PRs must stop paying the 5 heavy
        # required checks. BEFORE the "evidence/" DOC_PREFIXES entry, these
        # two exact paths matched no rule at all and fell through to
        # `unknown_paths`, which forces run_all=True — so the mandatory
        # evidence-pack ceremony (evidence_pack_lint.py / harness-floor.yml,
        # written by every agent-produced PR) silently defeated L5's own
        # docs-lane fast path for the single most common PR shape. This is
        # the guilt case that motivated the fix: revert the "evidence/" line
        # in change_map.py's DOC_PREFIXES and this test goes red with
        # unknown_paths == ["evidence/brief.yml", "evidence/pack.yml"].
        result = cm.classify(["evidence/pack.yml", "evidence/brief.yml"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["unknown_paths"], [])
        self.assertTrue(result["domains"]["docs_content_data"])
        self.assertEqual(result["suggested_jobs"], [])
        self.assertEqual(result["would_skip"], list(cm.TEST_JOBS))

    def test_innocence_nested_evidence_archive_paths_also_route_to_docs(self) -> None:
        # evidence/<YYYY-MM>/<task-slug>/{pack,brief}.yml is the archived
        # form (see the repo's own evidence/2026-08/ tree) — a prefix match,
        # not just the two root-level paths above.
        result = cm.classify(
            [
                "evidence/2026-08/agent-x-ops-docs-fastlane-abc12345/pack.yml",
                "evidence/2026-08/agent-x-ops-docs-fastlane-abc12345/brief.yml",
            ]
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(result["unknown_paths"], [])
        self.assertTrue(result["domains"]["docs_content_data"])
        self.assertEqual(result["suggested_jobs"], [])

    def test_innocence_docs_pr_with_its_mandatory_evidence_pack_still_fast_paths(
        self,
    ) -> None:
        # The realistic shape: a genuinely docs-only PR that also carries
        # the evidence pack every agent-produced PR writes. This is the
        # actual mandate proof — not the synthetic evidence-only case above.
        result = cm.classify(
            [
                "docs/runbooks/ci.md",
                "research/operations/2026-08-27-note.md",
                "evidence/pack.yml",
                "evidence/brief.yml",
            ]
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(result["unknown_paths"], [])
        self.assertEqual(result["suggested_jobs"], [])
        self.assertEqual(result["would_skip"], list(cm.TEST_JOBS))
        # End-to-end with security.yml's flag math too — this is the full
        # mandate proof: a docs-only PR with its mandatory evidence pack
        # pays for none of the 5 heavy required checks (3 in tests.yml via
        # suggested_jobs above, 2 CodeQL legs in security.yml via these
        # flags), through the SAME classifier both workflows already share.
        flags = sgf.compute_flags(result, js_manifest=False)
        self.assertFalse(flags["run_codeql_python"])
        self.assertFalse(flags["run_codeql_js"])

    def test_guilt_evidence_pack_never_masks_a_real_code_domain(self) -> None:
        # The evidence pack routing to docs_content_data must be additive,
        # never a way to launder a real change past the classifier: a PR
        # that also touches product code keeps exactly the job set that
        # code earns, union'd with (never narrowed by) evidence/*.yml.
        result = cm.classify(
            [
                "evidence/pack.yml",
                "evidence/brief.yml",
                "apps/backend-rag/backend/app/main.py",
            ]
        )
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertTrue(result["domains"]["docs_content_data"])
        self.assertIn("backend-tests", result["suggested_jobs"])
        self.assertNotEqual(result["suggested_jobs"], [])

    def test_guilt_one_code_file_among_fifty_docs_still_forces_its_suite(
        self,
    ) -> None:
        # Pins the L5 docs-lane mandate's own literal guilt case
        # (research/operations/2026-08-21-token-ceremony-ci-system-audit.md
        # §7 row L5, §13.5): "a PR whose diff is 100% documentation" must
        # get the fast path (test_innocence_docs_only_skips_product_test_jobs
        # above), but the instant even ONE file in a large docs-heavy diff
        # is code, the fast path must not fire — test_guilt_mixed_domains_
        # union_their_jobs below already proves the 2-file union case; this
        # is the mandate's own 50:1 ratio, kept as its own case so a future
        # change to that test's file count can't silently stop covering the
        # docs-lane's actual acceptance bar.
        docs_paths = [f"docs/runbooks/note-{i}.md" for i in range(50)]
        result = cm.classify(
            [*docs_paths, "apps/backend-rag/backend/app/main.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["docs_content_data"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertIn("backend-tests", result["suggested_jobs"])
        self.assertNotEqual(result["suggested_jobs"], [])

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

    def test_innocence_fleet_ops_directories_skip_every_test_job(self) -> None:
        # 2026-08-20: PR #4428 touched only scripts/mini/*.sh (a Mini-machine
        # git-pull wrapper) and still paid the full ~28min backend suite,
        # because top-level scripts/ (outside scripts/ci/) has no domain rule
        # at all and unclassified paths fail closed to run_all=true — correct
        # by design, but this specific directory is provably safe (see the
        # fleet_ops block in change_map.py for the two-sided proof: zero .py
        # files anywhere in the tree, so nothing can import it; zero
        # references anywhere in the six gated jobs' own code trees or in
        # tests.yml, so nothing subprocess-invokes it either). This is the
        # exact PR #4428 diff shape.
        result = cm.classify(
            [
                "scripts/mini/mini-git-pull.sh",
                "scripts/mini/test-mini-git-pull-self-update-atomic.sh",
                "scripts/mini/test-mini-git-pull-symlink-typechange-clean.sh",
            ]
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "classified")
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertEqual(result["suggested_jobs"], [])
        self.assertEqual(result["would_skip"], list(cm.TEST_JOBS))

    def test_innocence_every_fleet_ops_directory_skips_every_test_job(self) -> None:
        # One representative path per mapped directory — guards against a
        # future edit narrowing one prefix's trailing slash or typo-ing a
        # directory name in a way a single spot-check on scripts/mini/ alone
        # would not catch.
        for path in (
            "scripts/cli/nz",
            "scripts/codex/codex-nightly-autofix-ci.sh",
            "scripts/damar-node/install.sh",
            "scripts/data/nb_decomm_audit_2026-05-07.json",
            "scripts/krisna-node/install.sh",
            "scripts/launchd/com.nuzantara.fly-pg-tunnel.plist",
            "scripts/mini/mini-git-pull.sh",
            "scripts/pro/pro-git-pull.sh",
            "scripts/review_routes/worker-plane-council-v3.json",
            "scripts/ruslana-node/install.sh",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertTrue(result["domains"]["fleet_ops"])
                self.assertEqual(result["suggested_jobs"], [])

    def test_guilt_hidden_backend_test_coupled_scripts_now_route_via_census(
        self,
    ) -> None:
        # Closes the tripwire this test used to pin (2026-08-20): these
        # top-level scripts/*.py files were silently imported by
        # apps/backend-rag/backend/tests/{scripts,unit/scripts}/ via that
        # tree's own sys.path shim, with no naming pattern in common, so
        # they fell through to unknown_paths and forced run_all=True. The
        # census now embeds each in SCRIPTS_COUPLING directly.
        for path in (
            "scripts/wr2_html_render_apply.py",  # forced run_all=true on PR #4431, same day
            "scripts/drive_token_watchdog.py",
            "scripts/sentinel_lib/alerter.py",  # imported by PRODUCTION backend code, not just tests
            "scripts/bot/wa_blind_bench.py",  # scripts/bot/ is pytest-collected directly by tests.yml
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertEqual(result["reason"], "classified")
                self.assertTrue(result["domains"]["backend_python"])
                self.assertEqual(
                    result["suggested_jobs"], ["backend-tests", "e2e-tests"]
                )

    def test_innocence_relocated_script_no_longer_couples_from_repo_root(
        self,
    ) -> None:
        # This file was one of the five the 2026-08-20 comment listed as
        # coupled — it has since moved to apps/backend-rag/scripts/ (verified:
        # `git ls-files scripts/fix_lkpm_q1_2026_client_ids.py` is empty
        # today). The census reflects what is coupled TODAY, not history.
        result = cm.classify(["scripts/fix_lkpm_q1_2026_client_ids.py"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "classified")
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertEqual(result["suggested_jobs"], [])

    def test_innocence_loose_top_level_script_outside_mapped_dirs_routes_to_fleet_ops(
        self,
    ) -> None:
        # Not under a PREFIX_RULES fleet_ops directory and not in
        # SCRIPTS_COUPLING — now fleet_ops via the census fallback instead
        # of unknown_paths/run_all=True: scripts/ has no unmapped remainder.
        result = cm.classify(["scripts/pro-mini-healthcheck.sh"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "classified")
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertEqual(result["suggested_jobs"], [])

    def test_guilt_uncoupled_script_mixed_with_frontend_change_has_no_backend_tests(
        self,
    ) -> None:
        # fleet_ops must contribute nothing but must not suppress the job
        # set a real co-changed mouth path already earns (symmetric with
        # the existing scripts/pro/ + backend_python case above).
        result = cm.classify(
            ["scripts/pro-mini-healthcheck.sh", "apps/mouth/src/app.tsx"]
        )
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertTrue(result["domains"]["mouth"])
        self.assertFalse(result["domains"]["backend_python"])
        self.assertNotIn("backend-tests", result["suggested_jobs"])
        self.assertEqual(result["suggested_jobs"], ["frontend-tests", "e2e-tests"])

    def test_innocence_scripts_ci_self_edit_is_unaffected_by_the_census_rule(
        self,
    ) -> None:
        # Stays on EXACT_RULES (all jobs via the infra_workflows/
        # security_sensitive escape hatch) — SCRIPTS_COUPLING sits after
        # EXACT_RULES/PREFIX_RULES and never runs for this path.
        result = cm.classify(["scripts/ci/change_map.py"])
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["infra_workflows"])
        self.assertTrue(result["domains"]["security_sensitive"])
        self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_innocence_uncoupled_scripts_pairs_skip_every_test_job(self) -> None:
        # The mandate proof (PR body `Bites:`): a script plus its own test,
        # neither referenced by the six jobs' trees, classifies cleanly
        # (no unknown_paths) with zero suggested jobs.
        for pair in (
            (
                "scripts/memory/mos_recall_sessionstart.py",
                "scripts/tests/test_memory_layers.py",
            ),
            (
                "scripts/home_surface_suite.sh",
                "scripts/tests/test_home_surface_suite.py",
            ),
        ):
            with self.subTest(pair=pair):
                result = cm.classify(list(pair))
                self.assertFalse(result["run_all"])
                self.assertEqual(result["reason"], "classified")
                self.assertEqual(result["unknown_paths"], [])
                self.assertTrue(result["domains"]["fleet_ops"])
                self.assertEqual(result["suggested_jobs"], [])

    def test_scripts_coupling_census_is_not_stale(self) -> None:
        # Runs the census via subprocess, not import — an import would need
        # scripts_coupling_census.py added to tests.yml's trusted-classifier
        # extraction list, and it has no business there (it shells out to
        # `git grep` and writes files). --check re-derives SCRIPTS_COUPLING
        # live and exits 1 on drift (cicatrix #9).
        repo_root = Path(__file__).resolve().parents[2]
        census = repo_root / "scripts" / "ci" / "scripts_coupling_census.py"
        completed = subprocess.run(
            [sys.executable, str(census), "--check"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 and "git" in completed.stderr.lower() and (
            "FileNotFoundError" in completed.stderr
            or "not found" in completed.stderr.lower()
        ):
            self.skipTest(
                f"git unavailable in this sandbox: {completed.stderr.strip()[-200:]}"
            )
        self.assertEqual(
            completed.returncode,
            0,
            "SCRIPTS_COUPLING is stale or the census failed — run "
            "`python3 scripts/ci/scripts_coupling_census.py --write`.\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}",
        )

    def test_guilt_fleet_ops_combined_with_backend_change_still_runs_backend(
        self,
    ) -> None:
        # fleet_ops must contribute nothing to the job set, but must not
        # SUPPRESS what a co-changed backend_python path already earns.
        result = cm.classify(
            ["scripts/pro/pro-git-pull.sh", "apps/backend-rag/backend/app/main.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(result["suggested_jobs"], ["backend-tests", "e2e-tests"])

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
