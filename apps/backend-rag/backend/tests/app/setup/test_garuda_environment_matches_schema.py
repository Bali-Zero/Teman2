"""Tripwire: the `garuda_environment` workflow_dispatch choice list must be a
SUBSET of what the database's `environment` CHECK constraints actually accept.

WHY THIS EXISTS (2026-08-26). `.github/workflows/garuda-arm.yml` used to offer
`SANDBOX`/`PRODUCTION` (default `SANDBOX`) for `garuda_environment`, whose
value is written straight through (no remapping) into
`GARUDA_ENVIRONMENT`, which `service_initializer.py` hands to
`PostgresMagicLinkStore`/`PostgresCheckStore`/`GarudaOrderRepository`, which
persist it verbatim into an `environment` column. Every migration that
defines such a column constrains it to `CHECK (environment IN ('TEST',
'STAGING', 'PRODUCTION'))` — `SANDBOX` is not a member. Arming with the
workflow's own DEFAULT would therefore violate that CHECK constraint on the
very first magic-link insert or eligibility-check write. `/health` only
polls the app-wide health endpoint (see garuda-arm.yml's own verification
step), so the app comes back up green and the break is discovered one failed
INSERT at a time — cicatrix-superscar.md family #2 ("esiste != armato"): the
probe reads something other than the thing that is broken.

This test parses BOTH sides live, every run — it does not hardcode either
one, because the whole failure mode this guards against is the two DRIFTING
APART:

  1. every `CHECK (environment IN (...))` clause under
     `apps/backend-rag/backend/db/migrations_v2/*.sql` (repo-wide — not
     scoped to a specific migration number, because the specific GARUDA
     migrations that will eventually carry this constraint on `main` are, as
     of this test's authorship, still on feature branches and get
     renumbered on landing; a filename-scoped test would go stale silently
     exactly the way the workflow's own header warns migration authors
     about); and
  2. the `options:` list of the `garuda_environment` workflow_dispatch input
     in `.github/workflows/garuda-arm.yml`.

If a future migration widens or narrows the accepted set, this test's
computed `_environment_check_intersection()` follows it automatically —
nothing here needs to change. If NO migration anywhere defines an
`environment` CHECK, the test fails closed (does not silently pass on an
empty sweep — cicatrix W84: "an empty sweep is not a pass").

Cost: <100ms locally — pure file reads + regex/yaml parsing, no DB, no app
import.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# tests/app/setup/test_garuda_environment_matches_schema.py
#   parents[0] = setup
#   parents[1] = app
#   parents[2] = tests
#   parents[3] = backend
#   parents[4] = apps/backend-rag
#   parents[5] = apps
#   parents[6] = repo root
REPO_ROOT = Path(__file__).resolve().parents[6]
MIGRATIONS_DIR = REPO_ROOT / "apps" / "backend-rag" / "backend" / "db" / "migrations_v2"
GARUDA_ARM_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "garuda-arm.yml"

# Matches e.g.  CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION'))
# across the (possibly multi-line) column-definition CHECK clauses this repo
# uses for every `environment` column (250, 252, 264, and the not-yet-landed
# GARUDA 285/286). Deliberately anchored on the column name `environment` so
# an unrelated `CHECK (... IN (...))` on a different column is not swept in.
_ENV_CHECK_RE = re.compile(
    r"CHECK\s*\(\s*environment\s+IN\s*\(([^)]*)\)\s*\)",
    re.IGNORECASE,
)
_QUOTED_LITERAL_RE = re.compile(r"'([^']*)'")


def _environment_check_sets() -> list[frozenset[str]]:
    """One frozenset of accepted values per `CHECK (environment IN (...))`
    clause found anywhere under migrations_v2/."""
    sets: list[frozenset[str]] = []
    for sql_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = sql_path.read_text(encoding="utf-8")
        for match in _ENV_CHECK_RE.finditer(text):
            literals = frozenset(_QUOTED_LITERAL_RE.findall(match.group(1)))
            if literals:
                sets.append(literals)
    return sets


def _environment_check_intersection() -> frozenset[str]:
    sets = _environment_check_sets()
    if not sets:
        # Fail closed (W84): no CHECK clause found anywhere is a broken
        # sweep, not "anything goes". If this ever fires because the last
        # `environment` CHECK column was legitimately dropped, that is the
        # moment to delete this test, not to make it pass silently.
        pytest.fail(
            "No `CHECK (environment IN (...))` clause found under "
            f"{MIGRATIONS_DIR} — cannot verify garuda-arm.yml's "
            "garuda_environment options against anything. Either the sweep "
            "regex broke, or every environment-tagged table was removed "
            "(update/delete this test deliberately if so)."
        )
    intersection = sets[0]
    for s in sets[1:]:
        intersection &= s
    return intersection


def _workflow_dispatch_inputs(workflow: dict) -> dict:
    # PyYAML's default (non-1.2) resolver parses the bare `on:` mapping key
    # as the boolean `True`, not the string "on" — GitHub Actions workflow
    # YAML hits this on every file. Read whichever key actually landed.
    on_block = workflow.get("on", workflow.get(True))
    assert on_block is not None, "workflow has neither an 'on' nor a True key"
    return on_block["workflow_dispatch"]["inputs"]


def _garuda_environment_options() -> list[str]:
    workflow = yaml.safe_load(GARUDA_ARM_WORKFLOW.read_text(encoding="utf-8"))
    inputs = _workflow_dispatch_inputs(workflow)
    garuda_env_input = inputs.get("garuda_environment")
    assert garuda_env_input is not None, (
        f"{GARUDA_ARM_WORKFLOW} no longer declares a `garuda_environment` "
        "workflow_dispatch input — update this test if the input was "
        "intentionally renamed/removed."
    )
    assert garuda_env_input.get("type") == "choice", (
        "garuda_environment stopped being a `type: choice` input — this "
        "test only knows how to validate a closed choice list, not free "
        "text."
    )
    options = garuda_env_input.get("options")
    assert options, "garuda_environment has no `options:` list."
    return list(options)


def test_garuda_arm_workflow_and_migrations_files_exist():
    """Guard the guard: if either input path silently disappears, every
    other assertion below would vacuously pass on nothing (W84)."""
    assert GARUDA_ARM_WORKFLOW.is_file(), f"missing: {GARUDA_ARM_WORKFLOW}"
    assert MIGRATIONS_DIR.is_dir(), f"missing: {MIGRATIONS_DIR}"
    assert list(MIGRATIONS_DIR.glob("*.sql")), f"no .sql files under {MIGRATIONS_DIR}"


def test_environment_check_clauses_are_internally_consistent():
    """Every `environment` CHECK clause in this repo is expected to define
    the SAME domain vocabulary (TEST/STAGING/PRODUCTION) — if a future
    migration deliberately narrows or widens it, the workflow test below
    will catch the mismatch, but this asserts the premise (a non-empty
    intersection) is even meaningful to compute."""
    sets = _environment_check_sets()
    assert sets, "no environment CHECK clauses found — see the intersection helper"
    intersection = _environment_check_intersection()
    assert intersection, (
        f"the {len(sets)} `environment` CHECK clauses found under "
        f"{MIGRATIONS_DIR} share NO common accepted value — "
        f"per-clause sets: {sets}"
    )


def test_garuda_environment_workflow_options_are_schema_legal():
    """The actual regression: every option the workflow lets an operator
    pick for `garuda_environment` must be a value the database's own
    `environment` CHECK constraints accept. This is what would have failed
    on the merged `SANDBOX`/`PRODUCTION` options (SANDBOX is schema-illegal)."""
    options = _garuda_environment_options()
    allowed = _environment_check_intersection()
    illegal = set(options) - allowed
    assert not illegal, (
        f"garuda-arm.yml's garuda_environment options include values the "
        f"database's `environment` CHECK constraints reject: {sorted(illegal)}. "
        f"Schema-legal values (intersection across all CHECK clauses found): "
        f"{sorted(allowed)}. Arming with an illegal value violates the CHECK "
        f"constraint on the first write while /health stays green "
        f"(cicatrix-superscar.md family #2)."
    )


def test_garuda_environment_default_is_schema_legal():
    """The DEFAULT is the most dangerous slot — it is what an operator gets
    by just accepting the form, so it must never be the illegal one."""
    workflow = yaml.safe_load(GARUDA_ARM_WORKFLOW.read_text(encoding="utf-8"))
    default = _workflow_dispatch_inputs(workflow)["garuda_environment"]["default"]
    allowed = _environment_check_intersection()
    assert default in allowed, (
        f"garuda_environment default={default!r} is not in the schema-legal "
        f"set {sorted(allowed)} — the default is the value an operator gets "
        f"by accepting the workflow_dispatch form as-is, so it must never be "
        f"the illegal one."
    )
