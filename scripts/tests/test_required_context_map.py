"""Tests for scripts/ci/required_context_map.py — the context-name -> workflow
file/job resolver shared by scripts/ci/snapshot_required_contexts.py and
scripts/ci/check_required_workflow_conformance.py.

Resolver regressions include GitHub's lowercase rendering of matrix booleans.
This file also guards the required mouth compiler step in tests.yml and
rejects workflow variants that remove or disarm it. The required antidotes
job runs these checks from the candidate checkout.

Run:  python3 -m pytest scripts/tests/test_required_context_map.py -q
"""
from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "required_context_map.py"
_spec = importlib.util.spec_from_file_location("required_context_map", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _assert_required_mouth_typecheck(workflow: dict[str, Any]) -> None:
    """Pin the compiler in the required leg, not a separately green advisory job."""
    job = workflow["jobs"]["frontend-tests"]
    assert "Frontend Tests (Next.js) (mouth, true)" in mod._context_names_for_job(
        "frontend-tests", job
    )
    assert job["needs"] == ["changes"]
    assert job["if"] == "${{ !cancelled() }}"
    assert job.get("continue-on-error", False) is False
    assert job.get("timeout-minutes") == 16
    steps = job["steps"]
    matches = [step for step in steps if step.get("id") == "mouth-typecheck"]
    assert len(matches) == 1
    step = matches[0]
    assert step["if"] == "matrix.app == 'mouth' && steps.decide.outputs.run == 'true'"
    assert step["working-directory"] == "apps/mouth"
    assert step["run"].strip() == "../../node_modules/.bin/tsc --noEmit"
    assert step.get("continue-on-error", False) is False
    names = [entry.get("name") for entry in steps]
    assert names.index("Check GARUDA generated contract") < steps.index(step)
    assert steps.index(step) < names.index("Run tests (with coverage)")


def test_required_mouth_job_compiles_contract_consumers() -> None:
    # immune-enforcement.yml's required antidotes job runs this file from the
    # candidate checkout. change_map's base-ref self-tests cannot provide that pin.
    workflow = mod.load_workflow(REPO_ROOT / ".github/workflows/tests.yml")
    assert workflow is not None
    _assert_required_mouth_typecheck(workflow)


FRESHNESS_STEP_NAME = "Check API schema.d.ts freshness (regenerate + diff)"
FRESHNESS_GATE = "matrix.app == 'mouth' && steps.decide.outputs.run == 'true'"


def _assert_mouth_schema_freshness(workflow: dict[str, Any]) -> None:
    """Pin the schema.d.ts freshness gate in the required mouth leg
    (PENDING-ARMS row 2026-08-24 part b) — same W69 reasoning as the
    typecheck pin above: the check only gates merges as long as it stays a
    non-advisory step of the already-required leg, between its three setup
    steps and the neighbouring mouth-only contract checks."""
    job = workflow["jobs"]["frontend-tests"]
    steps = job["steps"]
    matches = [
        i
        for i, entry in enumerate(steps)
        if entry.get("name") == FRESHNESS_STEP_NAME
    ]
    assert len(matches) == 1, "freshness step missing or duplicated"
    idx = matches[0]
    step = steps[idx]
    assert step["if"] == FRESHNESS_GATE
    assert step.get("continue-on-error", False) is False
    names = [entry.get("name") for entry in steps]
    assert names.index("Check GARUDA generated contract") < idx
    assert idx < names.index("Typecheck mouth contract consumers")
    run = step["run"]
    # The executable chain, pinned as a whole — substrings, not vibes: the
    # council (codex-gpt-5.6-sol round 3) killed an earlier version of this
    # pin by deleting the generator line alone, and by neutering the
    # failure branch's `exit 1` alone, both while every other substring
    # still matched.
    assert "python -m scripts.generate_openapi" in run
    assert "./node_modules/.bin/openapi-typescript" in run
    assert "apps/backend-rag/openapi.json" in run
    assert "--output apps/mouth/src/lib/api/schema.d.ts" in run
    # Fixed diff targets and the delete-before-render guard: without the rm,
    # a no-op or repointed renderer leaves the stale committed file in
    # place and the diff goes green against itself (council findings,
    # codex-gpt-5.6-sol rounds 2-3, of the arming PR).
    assert "rm -f apps/mouth/src/lib/api/schema.d.ts" in run
    assert "apps/mouth/src/lib/api/schema.d.ts" in run
    assert "apps/mouth/src/lib/api/schema.d.ts.openapi-sha256" in run
    assert "git diff --exit-code" in run
    assert "|| true" not in run
    assert "exit 1" in run
    # The degraded-mode env the generation imports under (mirrors the
    # backend shard's bootstrap-step env trio). `.get` throughout so a
    # popped/missing env block reads as an assertion failure, never a
    # KeyError escaping the pin.
    env = step.get("env") or {}
    assert env.get("DATABASE_URL") == "sqlite:///:memory:"
    assert str(env.get("JWT_SECRET_KEY", "")).strip()
    assert str(env.get("API_KEYS", "")).strip()
    # Its three setup steps carry the identical gate — a Python setup that
    # ran on a different matrix leg would leave the freshness step without
    # its toolchain, reading as a skip, never as a red.
    for setup_name in (
        "Setup Python (API schema freshness)",
        "Restore backend uv cache (API schema freshness)",
        "Install backend deps (uv, API schema freshness)",
    ):
        setup_matches = [s for s in steps if s.get("name") == setup_name]
        assert len(setup_matches) == 1, f"{setup_name} missing or duplicated"
        assert setup_matches[0]["if"] == FRESHNESS_GATE


def test_mouth_schema_freshness_gate_pinned() -> None:
    workflow = mod.load_workflow(REPO_ROOT / ".github/workflows/tests.yml")
    assert workflow is not None
    _assert_mouth_schema_freshness(workflow)


@pytest.mark.parametrize(
    "mutation",
    [
        "remove",
        "advisory",
        "wrong-gate",
        "swallow-error",
        "drop-rm-guard",
        "move-after-typecheck",
        "drop-env",
        "drop-generator",
        "neuter-exit",
    ],
)
def test_mouth_schema_freshness_rejects_disarmed_mutations(mutation: str) -> None:
    workflow = deepcopy(mod.load_workflow(REPO_ROOT / ".github/workflows/tests.yml"))
    assert workflow is not None
    job = workflow["jobs"]["frontend-tests"]
    steps = job["steps"]
    step = next(s for s in steps if s.get("name") == FRESHNESS_STEP_NAME)
    if mutation == "remove":
        steps.remove(step)
    elif mutation == "advisory":
        step["continue-on-error"] = True
    elif mutation == "wrong-gate":
        step["if"] = "matrix.app == 'admin-dashboard'"
    elif mutation == "swallow-error":
        step["run"] += " || true"
    elif mutation == "drop-rm-guard":
        step["run"] = step["run"].replace(
            "rm -f apps/mouth/src/lib/api/schema.d.ts", "true"
        )
    elif mutation == "move-after-typecheck":
        steps.remove(step)
        typecheck_idx = next(
            i for i, s in enumerate(steps) if s.get("id") == "mouth-typecheck"
        )
        steps.insert(typecheck_idx + 1, step)
    elif mutation == "drop-env":
        step.pop("env", None)
    elif mutation == "drop-generator":
        # Council kill (codex-gpt-5.6-sol round 3): an earlier pin matched
        # on rendering substrings only, so deleting the OpenAPI generation
        # line entirely — the check diffing a render of a STALE
        # openapi.json — still passed every assertion.
        step["run"] = step["run"].replace(
            "PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python -m scripts.generate_openapi",
            "true",
        )
    elif mutation == "neuter-exit":
        # Same council kill on the failure branch: `exit 1` -> no-op colon
        # makes any drift green while every benign substring still matches.
        step["run"] = step["run"].replace("exit 1", ":")
    with pytest.raises(AssertionError):
        _assert_mouth_schema_freshness(workflow)


@pytest.mark.parametrize(
    "mutation",
    [
        "remove", "move-to-advisory", "after-tests", "wrong-matrix",
        "wrong-condition", "wrong-cwd", "step-advisory", "job-advisory",
        "swallow-error", "missing-needs", "success-only-job",
        "missing-timeout", "widened-timeout",
    ],
)
def test_required_mouth_typecheck_rejects_disarmed_mutations(mutation: str) -> None:
    workflow = deepcopy(mod.load_workflow(REPO_ROOT / ".github/workflows/tests.yml"))
    assert workflow is not None
    job = workflow["jobs"]["frontend-tests"]
    steps = job["steps"]
    step = next(entry for entry in steps if entry.get("id") == "mouth-typecheck")
    if mutation in {"remove", "move-to-advisory", "after-tests"}:
        steps.remove(step)
        if mutation == "move-to-advisory":
            workflow["jobs"]["advisory-typecheck"] = {
                "continue-on-error": True, "steps": [step]
            }
        elif mutation == "after-tests":
            steps.append(step)
    elif mutation == "wrong-matrix":
        job["strategy"]["matrix"]["include"][0]["coverage"] = False
    elif mutation == "wrong-condition":
        step["if"] = "matrix.app == 'admin-dashboard'"
    elif mutation == "wrong-cwd":
        step["working-directory"] = "apps/admin-dashboard"
    elif mutation == "step-advisory":
        step["continue-on-error"] = True
    elif mutation == "job-advisory":
        job["continue-on-error"] = True
    elif mutation == "swallow-error":
        step["run"] += " || true"
    elif mutation == "missing-needs":
        job["needs"] = []
    elif mutation == "success-only-job":
        job["if"] = "${{ success() }}"
    elif mutation == "missing-timeout":
        job.pop("timeout-minutes", None)
    elif mutation == "widened-timeout":
        job["timeout-minutes"] = 30
    with pytest.raises(AssertionError):
        _assert_required_mouth_typecheck(workflow)


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
