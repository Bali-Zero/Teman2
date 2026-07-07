"""Tests for the atlas extractors added to scripts/docs_sync.py.

These run against the real repo tree on purpose: the extractors' contract is
"deterministic over git-tracked files" (local ↔ CI parity), so the repo itself
is the fixture. Structural assertions only — no exact counts, or every new
runbook/skill would break the suite.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "docs_sync", REPO_ROOT / "scripts" / "docs_sync.py"
)
docs_sync = importlib.util.module_from_spec(_spec)
sys.modules["docs_sync"] = docs_sync
_spec.loader.exec_module(docs_sync)


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def test_list_runbooks_excludes_readme_and_has_titles():
    rows = docs_sync.list_runbooks()
    assert rows, "repo has runbooks; extractor returned none"
    names = [r["file"] for r in rows]
    assert "README.md" not in names, "the generated index must not index itself"
    assert all(r["title"] for r in rows), "every runbook row needs a title fallback"
    assert names == sorted(names), "output must be sorted (deterministic)"


def test_list_workflows_parses_export_const_meta():
    rows = docs_sync.list_workflows()
    by_name = {r["name"]: r for r in rows}
    # verify-template.js is a durable, citable artifact (CLAUDE.md §6) — if it
    # ever disappears this test SHOULD fail and force a doc decision.
    assert "verify-template" in by_name
    assert by_name["verify-template"]["description"], (
        "meta.description not parsed — the meta block sits below header "
        "comments; the extractor must anchor to `export const meta`"
    )


def test_list_skills_parses_folded_frontmatter_description():
    rows = docs_sync.list_skills()
    by_name = {r["name"]: r for r in rows}
    assert "modus" in by_name, "repo-tracked skill modus not enumerated"
    # modus uses `description: >` (YAML folded scalar) — the regression this
    # test pins is returning '>' or '' instead of the folded text.
    desc = by_name["modus"]["description"]
    assert desc and desc != ">", f"folded description not joined: {desc!r}"
    assert len(desc) <= 160


def test_automation_coverage_bounds():
    cov = docs_sync.automation_coverage()
    assert cov["plists"] > 0, "infra/launchagents has tracked plists"
    assert 0 <= cov["documented"] <= cov["plists"]


def test_extractors_deterministic():
    assert docs_sync.list_runbooks() == docs_sync.list_runbooks()
    assert docs_sync.list_workflows() == docs_sync.list_workflows()
    assert docs_sync.list_skills() == docs_sync.list_skills()
    assert docs_sync.automation_coverage() == docs_sync.automation_coverage()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def _stats():
    return {
        "runbooks": [{"file": "a.md", "title": "A | pipe"}],
        "workflows": [{"file": "w.js", "name": "w", "description": "d | pipe"}],
        "skills": [{"name": "s", "description": "sd"}],
        "automation_coverage": {"plists": 4, "documented": 1},
    }


def test_templates_registered_and_render():
    for key in (
        "RUNBOOKS_INDEX",
        "WORKFLOWS_INDEX",
        "SKILLS_INDEX",
        "AUTOMATION_COVERAGE",
    ):
        assert key in docs_sync.TEMPLATES
        body = docs_sync.TEMPLATES[key](_stats())
        assert body.strip(), f"{key} rendered empty"


def test_table_cells_escape_pipes():
    body = docs_sync.TEMPLATES["RUNBOOKS_INDEX"](_stats())
    assert "A \\| pipe" in body
    body = docs_sync.TEMPLATES["WORKFLOWS_INDEX"](_stats())
    assert "d \\| pipe" in body


def test_automation_coverage_render_pct():
    body = docs_sync.TEMPLATES["AUTOMATION_COVERAGE"](_stats())
    assert "4 plist" in body and "(25% coverage)" in body


def test_coverage_zero_plists_no_division_error():
    body = docs_sync.TEMPLATES["AUTOMATION_COVERAGE"](
        {"automation_coverage": {"plists": 0, "documented": 0}}
    )
    assert "(0% coverage)" in body


# ---------------------------------------------------------------------------
# Target wiring
# ---------------------------------------------------------------------------

def test_target_files_wiring():
    targets = [p.name for p in docs_sync.TARGET_FILES]
    assert "INDEX.md" in targets
    assert "CLAUDE.md" not in targets, (
        "CLAUDE.md markers were removed in F44 — a dead target misleads"
    )
    rels = [str(p.relative_to(docs_sync.REPO_ROOT)) for p in docs_sync.TARGET_FILES]
    assert "docs/runbooks/README.md" in rels
