#!/usr/bin/env python3
"""Guilt + innocence corpus for security_gate_flags.py.

Companion to test_change_map.py. Fixtures build minimal domain dicts
directly (not via change_map.classify()) — this test is about the FLAG
MATH, not the path classifier, and should not regress if change_map.py's
own PREFIX_RULES change shape.
"""

from __future__ import annotations

import unittest

import security_gate_flags as sgf

ALL_DOMAINS = (
    "backend_python",
    "mouth",
    "admin_dashboard",
    "wa_mirror",
    "mcp",
    "evaluator",
    "packages_core",
    "infra_workflows",
    "docs_content_data",
    "security_sensitive",
)


def _map(run_all: bool = False, **true_domains: bool) -> dict:
    domains = dict.fromkeys(ALL_DOMAINS, False)
    for name in true_domains:
        assert name in ALL_DOMAINS, f"unknown domain in fixture: {name}"
        domains[name] = True
    return {"run_all": run_all, "domains": domains}


ALL_FLAGS = (
    "run_codeql_python",
    "run_codeql_js",
    "run_bandit",
    "run_snyk_python",
    "run_safety",
    "run_snyk_docker",
    "run_snyk_node",
)


class SecurityGateFlagsTests(unittest.TestCase):
    # --- run_all / fail-open ------------------------------------------------

    def test_guilt_run_all_forces_every_flag_true(self) -> None:
        flags = sgf.compute_flags(_map(run_all=True), js_manifest=False)
        for name in ALL_FLAGS:
            self.assertTrue(flags[name], f"{name} should be true under run_all")

    def test_innocence_no_domains_no_run_all_skips_everything_but_node(self) -> None:
        # snyk-node has a THIRD trigger (js_manifest) independent of domains
        # — this case pins that it does NOT fire spuriously when that flag
        # is also false.
        flags = sgf.compute_flags(_map(), js_manifest=False)
        for name in ALL_FLAGS:
            self.assertFalse(flags[name], f"{name} should be false on an empty map")

    # --- docs-only innocence (the mandate's required proof) -----------------

    def test_innocence_docs_content_data_only_skips_every_scanner(self) -> None:
        flags = sgf.compute_flags(_map(docs_content_data=True), js_manifest=False)
        for name in ALL_FLAGS:
            self.assertFalse(flags[name], f"{name} should be false for docs-only")

    # --- security_sensitive is the universal override -----------------------

    def test_guilt_security_sensitive_forces_every_flag_true(self) -> None:
        flags = sgf.compute_flags(_map(security_sensitive=True), js_manifest=False)
        for name in ALL_FLAGS:
            self.assertTrue(flags[name], f"{name} should be true under security_sensitive")

    # --- codeql-python -------------------------------------------------------

    def test_guilt_backend_python_runs_codeql_python_only(self) -> None:
        flags = sgf.compute_flags(_map(backend_python=True), js_manifest=False)
        self.assertTrue(flags["run_codeql_python"])
        self.assertTrue(flags["run_bandit"])
        self.assertTrue(flags["run_snyk_docker"])
        self.assertFalse(flags["run_codeql_js"])
        self.assertFalse(flags["run_snyk_python"])
        self.assertFalse(flags["run_safety"])
        self.assertFalse(flags["run_snyk_node"])

    def test_guilt_mcp_and_evaluator_run_codeql_python_only(self) -> None:
        for domain in ("mcp", "evaluator"):
            with self.subTest(domain=domain):
                flags = sgf.compute_flags(_map(**{domain: True}), js_manifest=False)
                self.assertTrue(flags["run_codeql_python"])
                self.assertFalse(flags["run_codeql_js"])
                # mcp/evaluator do NOT gate bandit (fixed target dir) or the
                # dependency scanners (no manifest coupling of their own).
                self.assertFalse(flags["run_bandit"])
                self.assertFalse(flags["run_snyk_python"])
                self.assertFalse(flags["run_snyk_docker"])

    # --- codeql-js -------------------------------------------------------

    def test_guilt_mouth_runs_codeql_js_only(self) -> None:
        flags = sgf.compute_flags(_map(mouth=True), js_manifest=False)
        self.assertTrue(flags["run_codeql_js"])
        self.assertFalse(flags["run_codeql_python"])
        self.assertFalse(flags["run_bandit"])

    def test_guilt_admin_wa_packages_core_run_codeql_js_only(self) -> None:
        for domain in ("admin_dashboard", "wa_mirror", "packages_core"):
            with self.subTest(domain=domain):
                flags = sgf.compute_flags(_map(**{domain: True}), js_manifest=False)
                self.assertTrue(flags["run_codeql_js"])
                self.assertFalse(flags["run_codeql_python"])

    # --- bandit --------------------------------------------------------------

    def test_innocence_bandit_not_triggered_by_frontend_domains(self) -> None:
        for domain in ("mouth", "admin_dashboard", "wa_mirror", "packages_core"):
            with self.subTest(domain=domain):
                flags = sgf.compute_flags(_map(**{domain: True}), js_manifest=False)
                self.assertFalse(flags["run_bandit"])

    # --- snyk-python / safety: manifest-gated only, NOT by backend_python ---

    def test_innocence_snyk_python_and_safety_not_triggered_by_code_only(self) -> None:
        # The mandate's central finding: a backend_python-only change (no
        # requirements.txt/pyproject.toml/uv.lock edit) cannot alter the
        # dependency set these two evaluate.
        flags = sgf.compute_flags(_map(backend_python=True), js_manifest=False)
        self.assertFalse(flags["run_snyk_python"])
        self.assertFalse(flags["run_safety"])

    def test_guilt_security_sensitive_runs_snyk_python_and_safety(self) -> None:
        # change_map.py's PYTHON_MANIFEST_NAMES rule tags any
        # requirements*.txt/pyproject.toml/uv.lock change as
        # security_sensitive globally — this is the shape that reaches here.
        flags = sgf.compute_flags(_map(security_sensitive=True), js_manifest=False)
        self.assertTrue(flags["run_snyk_python"])
        self.assertTrue(flags["run_safety"])

    # --- snyk-docker: backend_python is a DELIBERATE extra trigger ----------

    def test_guilt_snyk_docker_also_triggered_by_backend_python(self) -> None:
        # Unlike snyk-python/safety, snyk-docker also validates the
        # production Dockerfile still BUILDS — application code alone can
        # break that build.
        flags = sgf.compute_flags(_map(backend_python=True), js_manifest=False)
        self.assertTrue(flags["run_snyk_docker"])

    # --- snyk-node: JS-manifest predicate is independent of domains --------

    def test_guilt_js_manifest_touched_runs_snyk_node_even_with_empty_map(self) -> None:
        # The whole point of this predicate: change_map.py itself may not
        # have tagged security_sensitive (nested-lockfile gap) but snyk-node
        # must still run.
        flags = sgf.compute_flags(_map(), js_manifest=True)
        self.assertTrue(flags["run_snyk_node"])
        # Nothing else should be pulled in by this predicate alone.
        for name in ALL_FLAGS:
            if name != "run_snyk_node":
                self.assertFalse(flags[name], f"{name} should stay false")

    def test_innocence_no_js_manifest_and_no_domains_skips_snyk_node(self) -> None:
        flags = sgf.compute_flags(_map(wa_mirror=True), js_manifest=False)
        # wa_mirror alone (e.g. a .ts source edit, no manifest touched)
        # does NOT need a dependency re-scan.
        self.assertFalse(flags["run_snyk_node"])


class JsManifestTouchedTests(unittest.TestCase):
    def test_guilt_root_lockfile(self) -> None:
        self.assertTrue(sgf.js_manifest_touched(["package-lock.json"]))

    def test_guilt_root_manifest(self) -> None:
        self.assertTrue(sgf.js_manifest_touched(["package.json"]))

    def test_guilt_nested_lockfile_outside_workspaces(self) -> None:
        # apps/wa-mirror/package-lock.json is its OWN lockfile, outside the
        # root npm-workspaces tree (verified live 2026-08-20: `workspaces`
        # in the root package.json does not list apps/wa-mirror) — this is
        # the exact gap change_map.py's EXACT_RULES (literal root-path
        # match only) does not close.
        self.assertTrue(
            sgf.js_manifest_touched(["apps/wa-mirror/package-lock.json"])
        )

    def test_guilt_nested_manifest_without_a_lockfile(self) -> None:
        # Several apps/*/package.json in this repo have no lockfile at all
        # (verified live 2026-08-20) — Snyk still reads declared ranges from
        # package.json in that case, so the manifest alone must trigger.
        self.assertTrue(
            sgf.js_manifest_touched(["apps/kbli-navigator/package.json"])
        )

    def test_innocence_js_source_edit_does_not_touch_manifest(self) -> None:
        self.assertFalse(
            sgf.js_manifest_touched(["apps/wa-mirror/src/index.ts"])
        )

    def test_innocence_similarly_named_file_is_not_a_manifest(self) -> None:
        # Entity, not substring (superscar #3) — a file that merely
        # CONTAINS "package.json" in its name must not match.
        self.assertFalse(
            sgf.js_manifest_touched(["docs/research/old-package.json.bak"])
        )

    def test_innocence_empty_and_blank_entries_are_skipped(self) -> None:
        self.assertFalse(sgf.js_manifest_touched(["", "   ", "\n"]))


if __name__ == "__main__":
    unittest.main()
