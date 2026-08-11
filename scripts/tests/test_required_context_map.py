"""Tests for scripts/ci/required_context_map.py — the context-name -> workflow
file/job resolver shared by scripts/ci/snapshot_required_contexts.py and
scripts/ci/check_required_workflow_conformance.py.

Not a superscar #3 "guard" (it doesn't accept/reject anything — it resolves a
name to a location), so it is not registered in
infra/guard-conformance/registry.json; this is plain regression coverage,
pinning the one real bug found while writing it (matrix boolean values
stringify as Python `True`/`False`, not GitHub's lowercase `true`/`false`) so
it cannot silently return.

Run:  python3 -m pytest scripts/tests/test_required_context_map.py -q
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "required_context_map.py"
_spec = importlib.util.spec_from_file_location("required_context_map", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write(wf_dir: Path, name: str, content: str) -> None:
    (wf_dir / name).write_text(content, encoding="utf-8")


def test_simple_job_no_matrix_resolves_by_name(tmp_path):
    wf_dir = tmp_path
    _write(
        wf_dir,
        "a.yml",
        "on:\n  pull_request:\njobs:\n  root-guard:\n    runs-on: ubuntu-latest\n",
    )
    # No `name:` -> context name defaults to the job id.
    assert mod.resolve("root-guard", wf_dir) == ("a.yml", "root-guard")


def test_named_job_resolves_by_declared_name(tmp_path):
    wf_dir = tmp_path
    _write(
        wf_dir,
        "a.yml",
        "on:\n  pull_request:\njobs:\n  lint:\n    name: Lint\n    runs-on: ubuntu-latest\n",
    )
    assert mod.resolve("Lint", wf_dir) == ("a.yml", "lint")
    assert mod.resolve("lint", wf_dir) is None  # job id alone is not the context once name: is set


def test_matrix_include_boolean_value_lowercases_like_github(tmp_path):
    """Regression pin: the bug this module shipped with while being written —
    `str(True)` -> "True", but GitHub's own context-name rendering of a
    matrix boolean value is lowercase "true". Reproduces tests.yml's real
    frontend-tests job shape (matrix.include with a `coverage: true` field)."""
    wf_dir = tmp_path
    _write(
        wf_dir,
        "a.yml",
        "on:\n  pull_request:\n"
        "jobs:\n"
        "  frontend-tests:\n"
        "    name: Frontend Tests (Next.js)\n"
        "    runs-on: ubuntu-latest\n"
        "    strategy:\n"
        "      matrix:\n"
        "        include:\n"
        "          - app: mouth\n"
        "            coverage: true\n"
        "          - app: admin-dashboard\n"
        "            coverage: false\n",
    )
    assert mod.resolve("Frontend Tests (Next.js) (mouth, true)", wf_dir) == ("a.yml", "frontend-tests")
    assert mod.resolve("Frontend Tests (Next.js) (admin-dashboard, false)", wf_dir) == ("a.yml", "frontend-tests")
    # Never the Python-str spelling.
    assert mod.resolve("Frontend Tests (Next.js) (mouth, True)", wf_dir) is None


def test_matrix_cross_product_single_key(tmp_path):
    """security.yml's real codeql job shape: matrix.language: [python, javascript]
    (no `include:`) cross-products into 2 distinct contexts."""
    wf_dir = tmp_path
    _write(
        wf_dir,
        "a.yml",
        "on:\n  pull_request:\n"
        "jobs:\n"
        "  codeql:\n"
        "    name: CodeQL Analysis\n"
        "    runs-on: ubuntu-latest\n"
        "    strategy:\n"
        "      matrix:\n"
        "        language: [python, javascript]\n",
    )
    assert mod.resolve("CodeQL Analysis (python)", wf_dir) == ("a.yml", "codeql")
    assert mod.resolve("CodeQL Analysis (javascript)", wf_dir) == ("a.yml", "codeql")


def test_ambiguous_name_across_two_jobs_resolves_to_none(tmp_path):
    """Two jobs reporting the identical context string is a resolver
    ambiguity, not a coin flip (W65: a resolver that guesses hallucinates)."""
    wf_dir = tmp_path
    _write(
        wf_dir,
        "a.yml",
        "on:\n  pull_request:\njobs:\n  x:\n    name: Same Name\n    runs-on: ubuntu-latest\n",
    )
    _write(
        wf_dir,
        "b.yml",
        "on:\n  pull_request:\njobs:\n  y:\n    name: Same Name\n    runs-on: ubuntu-latest\n",
    )
    assert mod.resolve("Same Name", wf_dir) is None


def test_unparseable_workflow_contributes_nothing_not_a_crash(tmp_path):
    wf_dir = tmp_path
    _write(wf_dir, "broken.yml", "not: valid: yaml: [unterminated")
    _write(
        wf_dir,
        "a.yml",
        "on:\n  pull_request:\njobs:\n  x:\n    name: Fine\n    runs-on: ubuntu-latest\n",
    )
    assert mod.resolve("Fine", wf_dir) == ("a.yml", "x")


def test_the_real_repo_workflows_resolve_every_live_required_context():
    """Guilt-adjacent live proof: every context this repo's actual branch
    protection requires (frozen list, 2026-08-11 — see
    infra/required.d/contexts.json) resolves against the REAL
    .github/workflows/ tree. A future job rename that silently breaks this
    resolver is exactly the failure mode snapshot regen would then blind-
    allowlist without anyone noticing."""
    live_contexts = [
        "E2E Tests (Playwright)", "MCP Server Tests", "Detect Secrets",
        "Backend Tests (Python)", "Bandit Python Security",
        "CodeQL Analysis (python)", "CodeQL Analysis (javascript)", "root-guard",
        "Frontend Tests (Next.js) (mouth, true)",
        "Canary self-test + incremental mutation", "verify-the-verifiers",
        "Hot-zone enforcement", "asyncpg-lint", "P3 static validation (enforcing)",
        "lesson-harvester-gate", "brand-api-gate", "cost-breaker-tests",
        "P6 parallelize-hypothesis falsifiable gates",
        "Every organ is born with its genes", "R1 gate — adversarial review present",
        "antidotes", "npm lock honors manifest",
        "actionlint — workflow schema + expression gate",
        "Every guard proves guilt AND innocence", "Prove hooks bite only the guilty",
        "prepush-guards", "Harness floor recompute",
    ]
    unresolved = [name for name in live_contexts if mod.resolve(name) is None]
    assert unresolved == [], f"could not resolve: {unresolved}"
