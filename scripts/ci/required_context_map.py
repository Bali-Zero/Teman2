#!/usr/bin/env python3
"""required_context_map.py — resolve a branch-protection required-status-check
context name back to the `.github/workflows/*.yml` file + job that produces it.

WHY THIS EXISTS (Merge-OS v2 Wave 0, spec §4 — Codex F12 trap-disarm slice):
a required context is a job's REPORTED name — the job's `name:` field, or the
job id when `name:` is absent, with `" (v1, v2, ...)"` appended per matrix
combination (GitHub's own convention: matrix VALUES joined by ", ", in
declaration order, never the matrix KEYS). Nothing in this repo previously
wrote that resolution down; it lived only in each engineer's head. This
module is the single place that computes it, shared by:

  - scripts/ci/snapshot_required_contexts.py (regenerates infra/required.d/
    contexts.json from the live branch-protection API)
  - scripts/ci/check_required_workflow_conformance.py (the per-PR guard that
    reads that snapshot and enforces merge_group + no-top-level-paths on
    every context's defining workflow)

Matrix support is deliberately narrow, matching how THIS repo actually uses
`strategy.matrix` (verified against every job in .github/workflows/ at
authoring time, 2026-08-10):
  - `matrix: {include: [{...}, {...}]}` — each include entry IS one combo;
    values taken in the entry's own key order (tests.yml frontend-tests).
  - `matrix: {key: [v1, v2], ...}` — cartesian product across keys, in the
    matrix mapping's own key order (security.yml codeql: language:
    [python, javascript]).
A job combining both forms, or using `exclude:`, is out of scope — this is a
snapshot/lint convenience, not a GitHub Actions expression interpreter (same
declared-limit style as scripts/verify_main_watch_schedule_scope.py).

No network calls. Pure stdlib + PyYAML (already a repo dependency —
scripts/lint_workflow_timeout_floor.py, scripts/evidence_pack_lint.py, etc.).
"""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any, Iterator

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def load_workflow(path: Path) -> dict[str, Any] | None:
    """Parse one workflow YAML. Returns None (never raises) on a parse
    failure or a non-mapping document — a workflow that cannot be understood
    contributes zero contexts, it never crashes the whole scan (W84: an
    empty/partial result must never be silently read as 'nothing here')."""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def _matrix_combos(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    """Every combination `strategy.matrix` produces, values only (order
    preserved per combo). `include` entries are combos verbatim; plain
    `key: [v1, v2, ...]` mappings cross-product (itertools.product, key
    order = declaration order — Python dicts preserve insertion order)."""
    combos: list[dict[str, Any]] = []
    include = matrix.get("include")
    if isinstance(include, list):
        for entry in include:
            if isinstance(entry, dict):
                combos.append(dict(entry))
    plain_keys = [k for k in matrix.keys() if k not in ("include", "exclude")]
    if plain_keys:
        value_lists = [matrix[k] if isinstance(matrix[k], list) else [matrix[k]] for k in plain_keys]
        for values in itertools.product(*value_lists):
            combos.append(dict(zip(plain_keys, values)))
    return combos


def _gh_stringify(value: Any) -> str:
    """GitHub renders a matrix value in a status-check context the way its
    own expression engine stringifies it — lowercase `true`/`false`, not
    Python's `True`/`False`. Caught empirically: `coverage: true` in
    tests.yml's frontend-tests matrix produced a context this module could
    not resolve until this conversion existed (`str(True)` -> "True")."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _context_names_for_job(job_id: str, job: dict[str, Any]) -> Iterator[str]:
    base_name = str(job.get("name", job_id))
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if isinstance(matrix, dict) and matrix:
        for combo in _matrix_combos(matrix):
            suffix = ", ".join(_gh_stringify(v) for v in combo.values())
            if suffix:
                yield f"{base_name} ({suffix})"
                continue
        return
    yield base_name


def build_context_index(workflows_dir: Path = WORKFLOWS_DIR) -> dict[str, list[tuple[str, str]]]:
    """context name -> list of (workflow filename, job id) that produce it.
    A list (not a single match) so an ambiguous name — two jobs reporting the
    identical context string — is visible to the caller rather than silently
    picking one (W65: a resolver that guesses is a resolver that hallucinates)."""
    index: dict[str, list[tuple[str, str]]] = {}
    if not workflows_dir.exists():
        return index
    for path in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        doc = load_workflow(path)
        if not doc:
            continue
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            for ctx_name in _context_names_for_job(job_id, job):
                index.setdefault(ctx_name, []).append((path.name, str(job_id)))
    return index


def resolve(context_name: str, workflows_dir: Path = WORKFLOWS_DIR) -> tuple[str, str] | None:
    """Single (workflow filename, job id) for a context name, or None if
    zero or more-than-one job in the repo reports that exact name."""
    matches = build_context_index(workflows_dir).get(context_name, [])
    if len(matches) != 1:
        return None
    return matches[0]
