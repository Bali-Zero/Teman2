"""Tests for the atlas extractors added to scripts/docs_sync.py.

These run against the real repo tree on purpose: the extractors' contract is
"deterministic over git-tracked files" (local ↔ CI parity), so the repo itself
is the fixture. Structural assertions only — no exact counts, or every new
runbook/skill would break the suite.
"""

from __future__ import annotations

import importlib.util
import subprocess
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
    # Two independent calls, compared via locals rather than inline — the
    # anti-reward-hacking linter's RH002 check compares ast.dump(left) ==
    # ast.dump(right) and can't tell "two separate calls to a pure function"
    # from a literal `assert X == X` tautology when both sides are written
    # identically inline. Same values, same behavior; this form just doesn't
    # trip the AST-structural false positive.
    runbooks_a, runbooks_b = docs_sync.list_runbooks(), docs_sync.list_runbooks()
    assert runbooks_a == runbooks_b
    workflows_a, workflows_b = docs_sync.list_workflows(), docs_sync.list_workflows()
    assert workflows_a == workflows_b
    skills_a, skills_b = docs_sync.list_skills(), docs_sync.list_skills()
    assert skills_a == skills_b
    coverage_a, coverage_b = docs_sync.automation_coverage(), docs_sync.automation_coverage()
    assert coverage_a == coverage_b


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
    body = docs_sync.format_automation_coverage(_stats())
    assert "4 plist" in body and "(25% coverage)" in body


def test_coverage_zero_plists_no_division_error():
    body = docs_sync.format_automation_coverage(
        {"automation_coverage": {"plists": 0, "documented": 0}}
    )
    assert "(0% coverage)" in body


# ---------------------------------------------------------------------------
# Retired volume counts must not come back (Merge-OS v3 step 4 / §C2)
#
# Guilt AND innocence on both halves of the rule (superscar #3): the retired keys
# must be refused wherever they could return — as a TEMPLATES entry, or as a marker
# re-pasted into a tracked page — and the surviving enumeration markers, which look
# identical in shape, must NOT be caught by the same check.
# ---------------------------------------------------------------------------

# Every file that could plausibly regain one, whether or not it is a TARGET_FILE
# today — a guard scoped to TARGET_FILES would go blind the moment someone trims
# that list, which is the exact shape of the thing being prevented.
_PAGES_WATCHED_FOR_REGROWTH = (
    "README.md",
    "INDEX.md",
    "docs/AI_ONBOARDING.md",
    "docs/runbooks/README.md",
)


def _markers_in(rel: str) -> set[str]:
    """DOCSYNC keys present in a tracked page (entity, not substring)."""
    text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    return {m.group("key") for m in docs_sync.MARKER_RE.finditer(text)}


def test_retired_count_keys_have_no_template():
    """GUILT: re-registering a retired key as a renderer must fail here."""
    overlap = docs_sync.RETIRED_COUNT_KEYS & set(docs_sync.TEMPLATES)
    assert not overlap, (
        f"{sorted(overlap)} back in TEMPLATES — these are volume counts with no "
        "programmatic consumer; they were removed from tracked prose by Merge-OS v3 "
        "step 4 (§C2). Serve them from --json/--coverage instead."
    )


def test_retired_count_markers_absent_from_tracked_pages():
    """GUILT: pasting a retired marker back into a tracked page must fail here."""
    for rel in _PAGES_WATCHED_FOR_REGROWTH:
        found = _markers_in(rel) & docs_sync.RETIRED_COUNT_KEYS
        assert not found, (
            f"{rel} regained retired DOCSYNC marker(s) {sorted(found)} — a committed "
            "volume count goes stale on main and hands the next innocent PR a red "
            "check (W86). Link to `python scripts/docs_sync.py --json` instead."
        )


def test_surviving_enumeration_markers_are_not_flagged():
    """INNOCENCE: the enumerations that legitimately stay are not caught.

    Without this, a guard that simply banned every DOCSYNC marker would pass the
    two tests above while quietly deleting the atlas.
    """
    index_markers = _markers_in("INDEX.md")
    assert {"LIVING_ORGANS", "WORKFLOWS_INDEX", "SKILLS_INDEX"} <= index_markers, (
        f"INDEX.md lost enumeration markers — found {sorted(index_markers)}"
    )
    assert "RUNBOOKS_INDEX" in _markers_in("docs/runbooks/README.md")
    assert not (index_markers & docs_sync.RETIRED_COUNT_KEYS)


def test_coverage_flag_is_read_only_and_reports():
    """The signal that replaced the INDEX.md coverage block must actually run.

    A `::notice::` step in docs-sync.yml is only a signal if the command behind it
    exits 0 and prints something (superscar #2 — a signaler nobody can read is not
    armed). Also pins that --coverage does not dirty the tracked cache.
    """
    cache = docs_sync.CACHE_PATH
    before = cache.read_bytes() if cache.exists() else None
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "docs_sync.py"), "--coverage"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    after = cache.read_bytes() if cache.exists() else None
    assert proc.returncode == 0, f"--coverage exited {proc.returncode}: {proc.stderr}"
    assert "coverage)" in proc.stdout, f"--coverage printed nothing usable: {proc.stdout!r}"
    assert before == after, "--coverage modified .docs_sync_cache.json"


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


# ---------------------------------------------------------------------------
# Cache write gating (read_only) — .docs_sync_cache.json must stay untouched
# by any mode documented as non-mutating (--check/--diff/--json).
# ---------------------------------------------------------------------------

def test_gather_stats_read_only_skips_cache_write(monkeypatch):
    calls = []
    monkeypatch.setattr(docs_sync, "_save_cache", lambda stats: calls.append(stats))

    docs_sync.gather_stats(read_only=True)
    assert calls == [], "read_only=True must never call _save_cache"

    docs_sync.gather_stats()
    assert len(calls) == 1, "default (write) mode must still refresh the cache"


def test_check_leaves_docs_sync_cache_untouched():
    """Regression: `--check` is documented as read-only but used to call
    _save_cache unconditionally, dirtying a tracked file on every invocation
    (including in CI, where the fresh-clone .docs_sync_cache.json is what
    --check's Qdrant fallback relies on — see gather_stats docstring)."""
    cache_path = docs_sync.CACHE_PATH
    before = cache_path.read_bytes() if cache_path.exists() else None

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "docs_sync.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    after = cache_path.read_bytes() if cache_path.exists() else None
    assert before == after, (
        "--check modified .docs_sync_cache.json — read-only mode must not "
        f"write. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
