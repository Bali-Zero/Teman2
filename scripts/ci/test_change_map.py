#!/usr/bin/env python3
"""Guilt + innocence corpus for the CI change-map."""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import change_map as cm
import security_gate_flags as sgf


def _locate_repo_root(rel: Path) -> Path | None:
    """Find the checkout that contains ``rel``, or None.

    Never resolve the checkout relative to ``__file__`` alone: tests.yml
    extracts this file FLAT into $RUNNER_TEMP/trusted-classifier/ (no
    scripts/ci/ above it), where parents[2] is /home/runner/work and every
    path built from it 404s. That mis-resolution turned the census staleness
    assertion red on EVERY PR from #5679 (2026-09-04) until #5692, and the
    classify step fell to run_all=true meanwhile. Any test here that touches
    the checkout goes through this function and SKIPS when it is absent —
    the assertion is made where the checkout exists, never faked where it
    does not.
    """

    workspace = os.environ.get("GITHUB_WORKSPACE")
    file_root = Path(__file__).resolve()
    candidates = [Path.cwd()]
    if workspace:
        candidates.append(Path(workspace))
    if len(file_root.parents) > 2:
        candidates.append(file_root.parents[2])
    return next((c for c in candidates if (c / rel).is_file()), None)


def _is_flat_extraction_copy(repo_root: Path, *, this_file: Path | None = None) -> bool:
    """True when the file actually EXECUTING this test is a flat-extracted
    copy of itself (tests.yml's trusted-classifier corpus dumps this exact
    file into ``$RUNNER_TEMP/trusted-classifier/`` with no ``scripts/ci/``
    ancestry — see this module's other flat-layout note above), rather than
    the real nested ``scripts/ci/test_change_map.py`` the checkout carries
    under ``repo_root``.

    Distinct from ``_locate_repo_root``'s own concern: the checkout can be
    FOUND (via cwd/GITHUB_WORKSPACE) even while THIS FILE is executing from a
    flat copy dumped elsewhere by the extraction step — reachability of the
    census and the identity of the currently-running test file are two
    different questions, and #5679→#5692 only ever fixed the first one.

    ``this_file`` is injectable (defaults to the real ``__file__``) purely so
    the guilt/innocence tests below can exercise both branches deterministically
    without needing to actually BECOME a flat copy mid-process.
    """
    this_file = this_file if this_file is not None else Path(__file__)
    canonical = (repo_root / "scripts" / "ci" / "test_change_map.py").resolve()
    return this_file.resolve() != canonical


def _staleness_verdict(
    completed: subprocess.CompletedProcess[str], *, is_flat: bool
) -> tuple[bool, str]:
    """Pure decision logic for a completed ``scripts_coupling_census.py
    --check`` run: (should_pass, message_to_print_or_fail_with).

    A stale FLEET-WIDE census (drifted because some OTHER merged PR touched
    scripts/**, unrelated to whatever diff THIS run is judging) must never
    force every PR's trusted-classifier corpus to distrust itself and fall
    back to run_all=true — diagnosed 2026-09-05, the fleet-wide outage from
    18:46Z the same day #5679/#5692 already fixed a DIFFERENT flat-layout
    trap for. So a stale census WARNS (still passes) inside the flat
    extraction, and still FAILS in the real repo layout (local dev, the
    nightly scripts/tests/ sweep, scripts/tests/test_scripts_coupling_fresh.py)
    where staleness is exactly the fact those tools exist to catch.
    """
    if completed.returncode == 0:
        return True, ""
    message = (
        "SCRIPTS_COUPLING is stale or the census failed — run "
        "`python3 scripts/ci/scripts_coupling_census.py --write`.\n"
        f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
    )
    if is_flat:
        return True, (
            "WARNING: SCRIPTS_COUPLING stale on this base — classification "
            "may under-match new scripts until regenerated (run "
            "scripts_coupling_census.py --write)"
        )
    return False, message


class ChangeMapTests(unittest.TestCase):
    def test_guilt_e33_backend_vocabulary_runs_its_article_ratchet(self) -> None:
        result = cm.classify(
            ["apps/backend-rag/backend/services/visa_check/e33_claim_guard.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(result["unknown_paths"], [])
        self.assertEqual(result["reason"], "classified")
        self.assertEqual(
            result["suggested_jobs"], ["backend-tests", "frontend-tests", "e2e-tests"]
        )

    def test_innocence_sibling_e33_files_do_not_select_the_article_ratchet(self) -> None:
        for path in ("e33_lifecycle.py", "e33_claim_guard_notes.py"):
            result = cm.classify(
                ["apps/backend-rag/backend/services/visa_check/" + path]
            )
            self.assertFalse(result["run_all"])
            self.assertFalse(result["domains"]["mouth"])
            self.assertEqual(result["suggested_jobs"], ["backend-tests", "e2e-tests"])

    def test_garuda_contract_explicitly_selects_both_consumers(self) -> None:
        for path in (
            "products/garuda-voa/contracts/openapi.yaml",
            "products/garuda-voa/contracts/README.md",
            "products/garuda-voa/contracts/nested/future-schema.yaml",
        ):
            for files in ([path], [path, "docs/contract-notes.md"]):
                with self.subTest(files=files):
                    result = cm.classify(files)
                    self.assertFalse(result["run_all"])
                    self.assertEqual(result["reason"], "classified")
                    self.assertEqual(result["unknown_paths"], [])
                    self.assertTrue(result["domains"]["backend_python"])
                    self.assertTrue(result["domains"]["mouth"])
                    self.assertEqual(
                        result["suggested_jobs"],
                        ["backend-tests", "frontend-tests", "e2e-tests"],
                    )

    def test_garuda_contract_prefix_keeps_unknown_siblings_fail_open(self) -> None:
        for path in (
            "products/garuda-voa/contracts-extra/openapi.yaml",
            "products/other-product/contracts/openapi.yaml",
            "products/README.md",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertTrue(result["run_all"])
                self.assertEqual(result["reason"], "unclassified_paths")
                self.assertEqual(result["unknown_paths"], [path])
                self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_unrelated_docs_do_not_select_garuda_consumers(self) -> None:
        result = cm.classify(["docs/contract-notes.md"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "classified")
        self.assertEqual(result["suggested_jobs"], [])

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
        # Locate the census in the CHECKOUT, never relative to __file__ —
        # see _locate_repo_root's docstring for the flat-extraction trap and
        # the #5679→#5692 outage it caused.
        rel = Path("scripts") / "ci" / "scripts_coupling_census.py"
        repo_root = _locate_repo_root(rel)
        if repo_root is None:
            self.skipTest(
                "scripts_coupling_census.py not reachable from cwd, GITHUB_WORKSPACE "
                "or __file__ — staleness is asserted where the checkout is present"
            )
        census = repo_root / rel
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
        should_pass, message = _staleness_verdict(
            completed, is_flat=_is_flat_extraction_copy(repo_root)
        )
        if message.startswith("WARNING"):
            print(message)
        self.assertTrue(should_pass, message)

    def test_census_trees_cover_every_app_tests_yml_runs(self) -> None:
        """``TREES`` is the census's INPUT corpus, and it was hand-written.

        ``apps/admin-dashboard-local`` runs ``npx vitest run`` inside the
        REQUIRED ``(mouth, true)`` leg of frontend-tests, yet was absent
        from ``TREES`` for as long as the census existed — so any repo-root
        ``scripts/`` file that tree imports or invokes was invisible to the
        coupling census. That is the UNDER-match direction (superscar #3):
        it SKIPS a suite that should have run, which is the expensive
        mistake, not the cheap one.

        Note the trap the fix had to avoid: ``apps/admin-dashboard`` is a
        PREFIX of ``apps/admin-dashboard-local`` and covers none of it.
        Coverage is asserted by tree ENTITY, never by substring.

        This re-derives the requirement from ``tests.yml`` on every run
        rather than trusting the one-off audit that found the gap — the
        next app added to a job leg has to be declared, or this goes red.
        """

        rel = Path("scripts") / "ci" / "scripts_coupling_census.py"
        repo_root = _locate_repo_root(rel)
        if repo_root is None:
            self.skipTest(
                "scripts_coupling_census.py not reachable from cwd, GITHUB_WORKSPACE "
                "or __file__ — TREES coverage is asserted where the checkout is present"
            )
        workflow = repo_root / ".github" / "workflows" / "tests.yml"
        if not workflow.is_file():
            self.skipTest("tests.yml absent from this checkout")
        text = workflow.read_text(encoding="utf-8")

        # TREES is read as a LITERAL from the source: importing the census
        # would pull it into tests.yml's trusted-extraction closure, and it
        # has no business there (it shells out to `git grep` and writes).
        tree_node = next(
            (
                node.value
                for node in ast.parse(
                    (repo_root / rel).read_text(encoding="utf-8")
                ).body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "TREES" for t in node.targets
                )
            ),
            None,
        )
        self.assertIsNotNone(tree_node, "TREES assignment not found in the census")
        trees = ast.literal_eval(tree_node)

        entered = set(
            re.findall(r"(?:cd|working-directory:)\s+apps/([A-Za-z0-9._-]+)", text)
        )
        # `cd apps/${{ matrix.app }}` — resolve it, never skip it. A form
        # this guard cannot resolve must FAIL, not pass quietly: a guard
        # that fail-opens on the case it does not understand is the whole
        # family #2 pattern in miniature.
        expressions = []
        for match in re.finditer(r"apps/\$\{\{([^}]*)\}\}", text):
            expr = match.group(1).strip()
            expressions.append(expr)
            # Name the LINE, not just the expression: the next person to hit
            # this is reading a red CI log, not this file, and "an expression
            # I cannot resolve" without a location is a hunt.
            line_no = text.count("\n", 0, match.start()) + 1
            self.assertEqual(
                expr,
                "matrix.app",
                f".github/workflows/tests.yml:{line_no} enters apps/ through an "
                f"expression this guard cannot resolve: {match.group(0)!r}\n"
                f"    {text.splitlines()[line_no - 1].strip()}\n"
                "Teach this test the form (see the `- app:` matrix handling just "
                "below) — do not let it through, or the tree it names goes "
                "unchecked against the census TREES list.",
            )
        if expressions:
            matrix_apps = set(
                re.findall(r"^\s*-\s*app:\s*([A-Za-z0-9._-]+)\s*$", text, re.MULTILINE)
            )
            self.assertTrue(
                matrix_apps,
                "tests.yml uses `apps/${{ matrix.app }}` but declares no `- app:` "
                "matrix values this guard can read",
            )
            entered |= matrix_apps

        uncovered = sorted(
            tree
            for tree in (f"apps/{name}" for name in entered)
            if not any(tree == t or tree.startswith(f"{t}/") for t in trees)
        )
        self.assertEqual(
            uncovered,
            [],
            "tests.yml executes code from these trees, but the coupling census "
            f"does not read them: {uncovered}. Any repo-root scripts/ file they "
            "import or invoke is invisible to SCRIPTS_COUPLING — the UNDER-match "
            "direction. Add each to TREES in scripts_coupling_census.py and re-run "
            "--write.",
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

    def test_innocence_claude_settings_and_hooks_skip_every_test_job(self) -> None:
        # Before this PR, .claude/settings.json, .claude/settings.local.json
        # and .claude/hooks/*.py fell into unknown_paths (unmapped) and
        # forced run_all=True — none of the six tests.yml jobs read the
        # harness config or hook scripts; they are verified by
        # immune-enforcement.yml and scripts/tests/ instead. (a) in the PR
        # body's numbering.
        for path in (
            ".claude/settings.json",
            ".claude/settings.local.json",
            ".claude/hooks/x.py",
        ):
            with self.subTest(path=path):
                result = cm.classify([path])
                self.assertFalse(result["run_all"])
                self.assertEqual(result["reason"], "classified")
                self.assertEqual(result["unknown_paths"], [])
                self.assertTrue(result["domains"]["fleet_ops"])
                self.assertEqual(result["suggested_jobs"], [])

    def test_guilt_claude_settings_does_not_suppress_a_real_backend_change(
        self,
    ) -> None:
        # (b) in the PR body's numbering: fleet_ops must not suppress the
        # job set a co-changed backend_python path already earns.
        result = cm.classify(
            [".claude/settings.json", "apps/backend-rag/backend/app/main.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertIn("backend-tests", result["suggested_jobs"])

    def test_innocence_guard_conformance_registry_skips_every_test_job(self) -> None:
        # infra/guard-conformance/ is more specific than the "infra/"
        # catch-all and must win — before this entry the registry inherited
        # infra_workflows/security_sensitive and forced all six jobs, though
        # guard-conformance.yml's own guilt+innocence run is what actually
        # verifies it (cicatrix #3's ESEGUIBILE).
        result = cm.classify(["infra/guard-conformance/registry.json"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["unknown_paths"], [])
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertFalse(result["domains"]["infra_workflows"])
        self.assertEqual(result["suggested_jobs"], [])

    def test_innocence_a_hooks_settings_only_pr_shape_skips_every_test_job(
        self,
    ) -> None:
        # (c) in the PR body's numbering: the realistic PR #5681 shape (a
        # per-prompt recall hook touching scripts/memory, scripts/hooks,
        # scripts/tests, the guard-conformance registry, and the harness
        # settings file) must classify cleanly with zero suggested jobs.
        result = cm.classify(
            [
                "scripts/memory/mos_recall_sessionstart.py",
                "scripts/hooks/organism_alert_sessionstart.sh",
                "scripts/tests/test_memory_layers.py",
                "infra/guard-conformance/registry.json",
                ".claude/settings.json",
            ]
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(result["unknown_paths"], [])
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertEqual(result["suggested_jobs"], [])

    def test_innocence_infra_fleet_payload_skips_every_test_job(self) -> None:
        # The measurement that opened this cure (PR #5697, 2026-09-05): a diff
        # of ONE file under infra/ classified perfectly — run_all false,
        # reason `classified`, no frontend domain lit — and still ran all six
        # heavy jobs, Frontend Tests included (16 of its 18 steps executed),
        # because both domains the "infra/" catch-all handed out were in
        # _suggested_jobs()'s multiplier set. Third recidive of cicatrix #3's
        # over-match half in two days (scripts/ #5679, .claude/ #5685, this),
        # and the cure's own precedent was already in this file: the
        # infra/guard-conformance/ carve-out above.
        result = cm.classify(["infra/ghostty/machines/m5.ghostty"])
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "classified")
        self.assertEqual(result["unknown_paths"], [])
        self.assertTrue(result["domains"]["fleet_ops"])
        self.assertFalse(result["domains"]["infra_workflows"])
        self.assertEqual(result["suggested_jobs"], [])
        self.assertEqual(result["would_skip"], list(cm.TEST_JOBS))

    def test_guilt_infra_still_buys_the_security_scanners(self) -> None:
        # The UNDER-match twin, pinned so a later "simplification" cannot
        # take it: .github/codeql-config.yml declares NO paths-ignore, so
        # CodeQL analyses infra/'s Python and shell like any other tree.
        # infra/ therefore keeps `security_sensitive` — the domain
        # security_gate_flags.py reads — even though it no longer buys a
        # single product test suite. `CodeQL Analysis (python)` and
        # `(javascript)` are both required contexts on main.
        #
        # The path is deliberately a real .py file reached by the CATCH-ALL
        # rule, not by the infra/eventbus/ carve-out — the carve-out carries
        # security_sensitive of its own, so an eventbus path would stay green
        # while the catch-all silently lost the domain.
        result = cm.classify(["infra/claude-hooks/host_boundary.py"])
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["security_sensitive"])
        self.assertEqual(result["suggested_jobs"], [])
        flags = sgf.compute_flags(result, js_manifest=False)
        self.assertTrue(flags["run_codeql_python"])
        self.assertTrue(flags["run_codeql_js"])

    def test_guilt_infra_eventbus_runs_the_backend_suite_that_reads_it(
        self,
    ) -> None:
        # The one real coupling the 2026-09-05 census found across all 38
        # infra/ sub-trees, and it is a literal-path read, not an import:
        # test_ingest_target_registry.py opens this exact file and asserts on
        # its contents, and scripts/ci/ingest_target_lint.py names it in
        # DECLARED_ENTRYPOINTS. Both are checked here so a rename of either
        # side fails this test instead of silently un-coupling the rule.
        runner = "infra/eventbus/regulatory_ingest_runner.py"
        result = cm.classify([runner])
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["backend_python"])
        self.assertIn("backend-tests", result["suggested_jobs"])
        self.assertNotIn("frontend-tests", result["suggested_jobs"])

        rel = Path("apps/backend-rag/backend/tests/unit/core/test_ingest_target_registry.py")
        repo_root = _locate_repo_root(rel)
        if repo_root is None:
            self.skipTest(
                "the coupled backend test is not reachable from cwd, GITHUB_WORKSPACE "
                "or __file__ — the coupling is asserted where the checkout is present"
            )
        self.assertIn(runner, (repo_root / rel).read_text(encoding="utf-8"))

    def test_guilt_infra_does_not_suppress_a_real_backend_change(self) -> None:
        # fleet_ops maps to zero jobs, so a co-changed product path must keep
        # every job it earns on its own — the union, never the minimum.
        result = cm.classify(
            ["infra/launchagents/com.example.plist", "apps/backend-rag/backend/app/main.py"]
        )
        self.assertFalse(result["run_all"])
        self.assertIn("backend-tests", result["suggested_jobs"])

    def test_guilt_workflow_definitions_still_force_every_suite(self) -> None:
        # infra_workflows stays in _suggested_jobs()'s multiplier set and
        # .github/ keeps it: editing what RUNS the suites still buys them all.
        result = cm.classify([".github/workflows/some-workflow.yml"])
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["infra_workflows"])
        self.assertEqual(result["suggested_jobs"], list(cm.TEST_JOBS))

    def test_innocence_manifests_reach_their_own_runtimes_and_no_others(
        self,
    ) -> None:
        # The other half of dropping `security_sensitive` from the multiplier:
        # it must not become an UNDER-match. Every manifest still fans out to
        # the runtimes it can actually break — via its OWN domains, which is
        # why the drop is safe — and stops paying for the ones it cannot.
        python = cm.classify(["pyproject.toml"])
        self.assertTrue(python["domains"]["security_sensitive"])
        for job in ("backend-tests", "mcp-tests", "evaluator-critical-tests", "e2e-tests"):
            self.assertIn(job, python["suggested_jobs"])
        self.assertNotIn("frontend-tests", python["suggested_jobs"])
        self.assertNotIn("packages-core-tests", python["suggested_jobs"])

        node = cm.classify(["package-lock.json"])
        self.assertTrue(node["domains"]["security_sensitive"])
        for job in ("frontend-tests", "packages-core-tests"):
            self.assertIn(job, node["suggested_jobs"])
        self.assertNotIn("backend-tests", node["suggested_jobs"])
        self.assertNotIn("mcp-tests", node["suggested_jobs"])

    def test_innocence_a_security_sensitive_path_part_no_longer_buys_all_six(
        self,
    ) -> None:
        # The additive `auth|security|migrations|deploy` rule tags a path
        # security_sensitive ON TOP of its prefix domains. Before the split
        # that tag alone forced all six suites onto a frontend-only file.
        result = cm.classify(["apps/mouth/src/app/auth/page.tsx"])
        self.assertFalse(result["run_all"])
        self.assertTrue(result["domains"]["security_sensitive"])
        self.assertTrue(result["domains"]["mouth"])
        self.assertIn("frontend-tests", result["suggested_jobs"])
        self.assertNotIn("backend-tests", result["suggested_jobs"])
        self.assertNotIn("mcp-tests", result["suggested_jobs"])

    def test_infra_coupling_census_is_not_stale(self) -> None:
        # The RATCHET, and the reason it exists: before the `infra/` catch-all
        # stopped buying all six suites, a new coupling from a suite into
        # infra/ was harmless — the over-match ran the suite anyway. Removing
        # the over-match removes that accidental safety net, so the census
        # that justified the carve-out has to be re-derived on every run
        # instead of trusted as a one-off (the same reasoning that turned the
        # scripts/ audit into scripts_coupling_census.py --check, cicatrix #9:
        # a rule whose evidence was measured once and never again).
        #
        # This pins the FULL reference profile — file -> segment -> count —
        # not just the set of segments, so adding a reference to an
        # already-listed sub-tree trips it too. Every entry below was read by
        # hand on 2026-09-05. The `infra/eventbus` ones are the carved-out
        # coupling (PREFIX_RULES, pinned by its own test above) — and only ONE
        # of them is a real read: test_ingest_target_registry.py opens the
        # runner; ingest_paths.py and outbox_handlers.py merely name it in a
        # docstring. Every NON-eventbus entry is PROSE: a docstring naming the
        # plist that invokes the module, a README paragraph, a comment, a
        # branch-name string in a fixture, a data-note inside a corpus JSON.
        # None of them opens, imports or subprocesses anything under infra/.
        #
        # When this goes red: read the new reference. Prose -> update the pin.
        # A real read/import -> add a PREFIX_RULES carve-out mapping that
        # sub-tree to the domain of the suite that reads it, THEN update the
        # pin. Do not update the pin to make the test quiet.
        expected: dict[str, dict[str, int]] = {
            "apps/backend-rag/backend/app/utils/ingest_paths.py": {"infra/eventbus": 1},
            "apps/backend-rag/backend/scripts/federation_alert_daemon.py": {"infra/launchagents": 1},
            "apps/backend-rag/backend/scripts/kg_fix_68112_node.py": {"infra/kg-68112-licenses": 1},
            "apps/backend-rag/backend/services/federation_alerts/__init__.py": {"infra/launchd": 1},
            "apps/backend-rag/backend/services/garuda_orders/outbox_handlers.py": {"infra/eventbus": 1},
            "apps/backend-rag/backend/services/sota_loop/__init__.py": {"infra/launchagents": 1},
            "apps/backend-rag/backend/services/sota_loop/_promote.py": {"infra/launchagents": 1},
            "apps/backend-rag/backend/services/sota_loop/m13_weekly.py": {"infra/claude-hooks": 1},
            "apps/backend-rag/backend/tests/unit/core/test_ingest_target_registry.py": {"infra/eventbus": 1},
            "apps/backend-rag/backend/tests/unit/response/test_w119c_outbound_marker_newline_bleed.py": {"infra/claude-hooks": 1},
            "apps/backend-rag/backend/tests/unit/routers/test_ingest_path_confinement.py": {"infra/eventbus": 1},
            "apps/backend-rag/backend/tests/unit/scripts/test_codex_tri_llm_review_script.py": {"infra/y": 1},
            "apps/backend-rag/backend/tests/unit/services/ingestion/test_ingest_success_is_reported_honestly.py": {"infra/eventbus": 1},
            "apps/backend-rag/backend/tests/unit/services/sota_loop/test_m13_weekly_repo_root.py": {"infra/claude-hooks": 1},
            "apps/evaluator/nlm_deep_research/scripts/run_nb5_t4_monitor.sh": {"infra/launchagents": 1},
            "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json": {"infra/workflows": 1},
            "apps/wa-mirror/README.md": {"infra/home-fork": 2},
        }
        # The trees the six heavy jobs actually execute. scripts/ci/ is
        # DELIBERATELY absent: it is mapped to infra_workflows (all six jobs)
        # and it contains this very file, so including it would make the pin
        # count its own prose and change on every edit to it.
        trees = (
            "apps/backend-rag",
            "apps/nuzantara-mcp",
            "apps/evaluator",
            "apps/mouth",
            "apps/admin-dashboard",
            "apps/admin-dashboard-local",
            "apps/wa-mirror",
            "packages/core",
        )
        repo_root = _locate_repo_root(Path("scripts") / "ci" / "change_map.py")
        if repo_root is None:
            self.skipTest(
                "no checkout reachable from cwd, GITHUB_WORKSPACE or __file__ — the "
                "infra/ census is re-derived where the checkout is present"
            )
        present = [t for t in trees if (repo_root / t).is_dir()]
        completed = subprocess.run(
            ["git", "grep", "-nIE", r"infra/[a-z0-9_-]+", "--", *present],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        # git grep exits 1 on "no matches", which is a legitimate (if
        # surprising) outcome; anything else is a broken invocation.
        self.assertIn(completed.returncode, (0, 1), completed.stderr)
        found: dict[str, dict[str, int]] = {}
        for line in completed.stdout.splitlines():
            path, _, rest = line.partition(":")
            for token in re.findall(r"infra/[a-z0-9_-]+", rest):
                found.setdefault(path, {}).setdefault(token, 0)
                found[path][token] += 1
        self.assertEqual(
            found,
            expected,
            "the infra/ reference profile moved — a suite's tree gained or lost a "
            "reference into infra/. Read it before touching this pin: prose -> update "
            "the pin; a real read/import -> carve the sub-tree out in PREFIX_RULES first.",
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


class CensusCheckDiagnosticTests(unittest.TestCase):
    """The census's --check diagnostic must name what actually moved.

    It did not. ``_render_block`` packs many paths per line, and ``_check``
    read one path per LINE, so every line collapsed into a single bogus
    token with ``", "`` inside it — identical on both sides. On 2026-09-05 a
    genuine one-path delta printed ~100 items "newly coupled" AND ~100 "no
    longer coupled", and an earlier session read that as a total reshuffle.
    A diagnostic that lies is worse than none: this is what the red on
    `Classifier corpus trust (visibility only)` shows a human.
    """

    def _census_module(self):
        rel = Path("scripts") / "ci" / "scripts_coupling_census.py"
        repo_root = _locate_repo_root(rel)
        if repo_root is None:
            self.skipTest(
                "scripts_coupling_census.py not reachable from cwd, GITHUB_WORKSPACE "
                "or __file__ — the diagnostic is asserted where the checkout is present"
            )
        # Load by path, never by name: tests.yml's trusted extraction copies
        # a FIXED six-file list flat, and the census is deliberately not in
        # it (it shells out to `git grep` and writes files). Its own
        # `import change_map` resolves from sys.modules, already imported
        # at the top of this file.
        spec = importlib.util.spec_from_file_location(
            "scripts_coupling_census_under_test", repo_root / rel
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run_check(self, census, on_disk_block: str, embedded: set[str]):
        """Point the census at a synthetic block and return (rc, stderr)."""

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "change_map.py"
            target.write_text(
                "# header\n" + on_disk_block + "\n# trailer\n", encoding="utf-8"
            )
            original = census.CHANGE_MAP_PATH
            census.CHANGE_MAP_PATH = target
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(
                    io.StringIO()
                ):
                    rc = census._check(embedded)
            finally:
                census.CHANGE_MAP_PATH = original
        return rc, err.getvalue()

    def test_guilt_one_added_path_is_named_and_nothing_else_is(self) -> None:
        census = self._census_module()
        base = {"scripts/a.py", "scripts/b.py", "scripts/c.py"}
        rc, stderr = self._run_check(
            census, census._render_block(base), base | {"scripts/zz_new.py"}
        )
        self.assertEqual(rc, 1)
        self.assertIn("+ newly coupled (1): scripts/zz_new.py", stderr)
        self.assertNotIn("- no longer coupled", stderr)
        # The signature of the old line-per-path reading: a "path" carrying
        # the separator of the packed line it was cut from.
        self.assertNotIn('", "', stderr)

    def test_guilt_one_removed_path_is_named_and_nothing_else_is(self) -> None:
        census = self._census_module()
        base = {"scripts/a.py", "scripts/b.py", "scripts/c.py"}
        rc, stderr = self._run_check(
            census, census._render_block(base | {"scripts/zz_gone.py"}), base
        )
        self.assertEqual(rc, 1)
        self.assertIn("- no longer coupled (1): scripts/zz_gone.py", stderr)
        self.assertNotIn("+ newly coupled", stderr)
        self.assertNotIn('", "', stderr)

    def test_guilt_a_rewrapped_block_says_the_set_is_identical(self) -> None:
        # Same paths, one per line instead of packed. The verdict stays
        # STALE — the block must be byte-identical to what --write emits —
        # but the old code answered that with an EMPTY diagnostic or with
        # garbage, which reads like "everything changed".
        census = self._census_module()
        paths = {"scripts/a.py", "scripts/b.py", "scripts/c.py"}
        rewrapped = "\n".join(
            [
                census.BEGIN_MARKER,
                "SCRIPTS_COUPLING: frozenset[str] = frozenset(",
                "    (",
                *[f'        "{p}",' for p in sorted(paths)],
                "    )",
                ")",
                census.END_MARKER,
            ]
        )
        rc, stderr = self._run_check(census, rewrapped, paths)
        self.assertEqual(rc, 1)
        self.assertIn("the coupled SET is identical (3 paths)", stderr)
        self.assertNotIn("+ newly coupled", stderr)
        self.assertNotIn("- no longer coupled", stderr)

    def test_innocence_an_up_to_date_block_exits_zero_and_says_nothing(self) -> None:
        census = self._census_module()
        paths = {"scripts/a.py", "scripts/b.py", "scripts/c.py"}
        rc, stderr = self._run_check(census, census._render_block(paths), paths)
        self.assertEqual(rc, 0)
        self.assertEqual(stderr, "")

    def test_innocence_block_paths_reads_a_packed_line_as_many_paths(self) -> None:
        # The unit fact the three guilt cases rest on: one rendered line
        # carries several paths, and every one of them must come back.
        census = self._census_module()
        paths = {f"scripts/pack_{i}.py" for i in range(12)}
        block = census._render_block(paths)
        self.assertEqual(census._block_paths(block), paths)


class StalenessVerdictTests(unittest.TestCase):
    """Guilt + innocence for _staleness_verdict, added 2026-09-05: a stale
    SCRIPTS_COUPLING must WARN+PASS in the flat trusted-classifier layout and
    still FAIL in the real repo layout. Pure-logic, hermetic — no subprocess,
    no real census invocation; a synthetic CompletedProcess stands in for a
    deliberately stale (or fresh) census run, matching this repo's
    established mocked-subprocess pattern for GH-Actions-adjacent decision
    functions (see scripts/ci/test_codeql_merge_group_carryover.py)."""

    @staticmethod
    def _completed(returncode: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout="", stderr="stale" if returncode else ""
        )

    def test_innocence_fresh_always_passes_silently_either_layout(self) -> None:
        for is_flat in (True, False):
            with self.subTest(is_flat=is_flat):
                should_pass, message = _staleness_verdict(self._completed(0), is_flat=is_flat)
                self.assertTrue(should_pass)
                self.assertEqual(message, "")

    def test_guilt_stale_in_the_repo_layout_fails(self) -> None:
        should_pass, message = _staleness_verdict(self._completed(1), is_flat=False)
        self.assertFalse(should_pass)
        self.assertIn("SCRIPTS_COUPLING is stale or the census failed", message)

    def test_innocence_stale_in_the_flat_layout_warns_and_passes(self) -> None:
        should_pass, message = _staleness_verdict(self._completed(1), is_flat=True)
        self.assertTrue(should_pass)
        self.assertTrue(message.startswith("WARNING: SCRIPTS_COUPLING stale on this base"))


class FlatExtractionDetectionTests(unittest.TestCase):
    """Guilt + innocence for _is_flat_extraction_copy against the REAL
    tests.yml extraction shape (not a hand-picked path), reusing
    test_trusted_extraction_layout.py's own flat-copy helper — the same
    corpus list, the same copy mechanics tests.yml's "Extract trusted
    classifier (base ref)" step actually runs.

    Both tests below construct the ``this_file`` value explicitly rather
    than trusting the ambient ``__file__`` of whatever process is currently
    executing this class. That is NOT paranoia: test_trusted_extraction_
    layout.py's own innocence test flat-copies this entire file (this class
    included) and re-runs it as a subprocess, so these tests routinely
    execute AS the flat copy too — asserting against the real, ambient
    execution context would make the innocence case fail exactly when
    that sibling's own exercise sweeps this file up, and the guilt case
    would need test_trusted_extraction_layout itself importable, which is
    not guaranteed inside a flat copy that never includes it."""

    def setUp(self) -> None:
        rel = Path("scripts") / "ci" / "test_change_map.py"
        repo_root = _locate_repo_root(rel)
        if repo_root is None:
            self.skipTest(
                "checkout not reachable via cwd/GITHUB_WORKSPACE/__file__ — "
                "see _locate_repo_root's docstring"
            )
        self.repo_root = repo_root

    def test_innocence_the_canonical_nested_path_is_not_flat(self) -> None:
        canonical = self.repo_root / "scripts" / "ci" / "test_change_map.py"
        self.assertFalse(_is_flat_extraction_copy(self.repo_root, this_file=canonical))

    def test_guilt_a_real_flat_copy_of_this_file_is_detected(self) -> None:
        # importlib, not a static `import test_trusted_extraction_layout`
        # statement: this repo's own scripts/tests/test_classifier_extraction_
        # closure.py walks the AST of every trusted-corpus file for exactly
        # that shape and fails the corpus closed if a sibling it names is not
        # ALSO in tests.yml's/security.yml's extraction list (the #5070
        # class of bug this PR's whole mandate traces back to) —
        # test_trusted_extraction_layout.py is deliberately NOT in that list
        # (it is not part of the trusted-classifier corpus itself), and this
        # dependency is genuinely optional here (see the except clause
        # below), not a hard requirement a static import would declare it as.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            tel = importlib.import_module("test_trusted_extraction_layout")
        except ImportError:
            self.skipTest(
                "test_trusted_extraction_layout.py not importable from this "
                "file's own directory — this test is itself executing from a "
                "flat-extracted copy (a sibling's own flat-copy exercise "
                "reached this file too), where that helper module is not "
                "part of the corpus. The guilt case runs wherever the real "
                "nested checkout executes this test instead."
            )
        files = tel._tests_yml_extraction_list()
        with tempfile.TemporaryDirectory(prefix="staleness-gating-flat-") as tmp:
            dest = Path(tmp)
            tel._extract_flat(files, dest)
            flat_copy = dest / "test_change_map.py"
            self.assertTrue(
                flat_copy.is_file(),
                "tests.yml's extraction list no longer carries test_change_map.py — "
                "update the corpus this guilt fixture depends on.",
            )
            self.assertTrue(_is_flat_extraction_copy(self.repo_root, this_file=flat_copy))


if __name__ == "__main__":
    unittest.main(verbosity=2)
