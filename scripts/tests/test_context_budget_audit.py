"""Tests for scripts/context_budget_audit.py (B6 always-injected context
rollup). Module loaded via importlib (scripts/ is a flat bag, not a
package — mirrors test_adversarial_review_gate.py's convention).

REPO_SCOPE_TOKEN_CEILING is a RATCHET, not the diet's eventual 15,000-token
target: measured 2026-09-04 (ratio 2.04) the real total was ~15,553 est.
tokens. Tighten toward 15,000 once the superscar 8KB PR (#5639) and the
root CLAUDE.md trim land — the assertion message always prints the
measured breakdown, so tightening is a one-line, evidence-backed edit.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parent.parent / "context_budget_audit.py"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("context_budget_audit", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cba = _load_module()

REPO_SCOPE_TOKEN_CEILING = 16_000
# Matches test_superscar_budget.py's BYTE_BUDGET on cicatrix-superscar.md.
UNSCOPED_RULES_BYTE_CEILING = 14_000


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestMeasureOnFixtures:
    def test_a_multiline_paths_rule_is_excluded_an_unscoped_one_is_included(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        _write(
            tmp_path / ".claude" / "rules" / "scoped.md",
            '---\npaths:\n  [\n    "**/*.ts",\n  ]\n---\n\nscoped\n',
        )
        unscoped_text = "---\nname: always\n---\n\nalways body\n"
        _write(tmp_path / ".claude" / "rules" / "unscoped.md", unscoped_text)
        result = cba.measure(tmp_path)
        assert result["unscoped_rules"] == {
            "files": 1,
            "bytes": len(unscoped_text.encode("utf-8")),
        }

    def test_agent_files_with_and_without_frontmatter_classify_correctly(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        _write(
            tmp_path / ".claude" / "agents" / "no-frontmatter.md",
            "# just a body, no frontmatter block\n",
        )
        _write(
            tmp_path / ".claude" / "agents" / "verifier.md",
            "---\nname: verifier\ndescription: checks things\ntools: Bash, Read\n---\n\nbody\n",
        )
        result = cba.measure(tmp_path)
        expected = len("verifier") + len("checks things") + len("Bash, Read")
        assert result["agents_frontmatter"] == {"files": 1, "bytes": expected}

    def test_commands_are_counted_into_skills_listing(self, tmp_path: Path) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        _write(
            tmp_path / ".claude" / "skills" / "bot" / "SKILL.md",
            "---\nname: bot\ndescription: wa bot corner\n---\n\nbody\n",
        )
        _write(
            tmp_path / ".claude" / "commands" / "verify.md",
            "---\nname: verify\ndescription: empirical verification\n---\n\nbody\n",
        )
        result = cba.measure(tmp_path)
        expected = (
            len("bot") + len("wa bot corner")
            + len("verify") + len("empirical verification")
        )
        assert result["skills_listing"] == {"files": 2, "bytes": expected}


class TestTheRealRepoScopeStaysUnderBudget:
    def test_total_repo_scope_estimated_tokens_stays_under_the_ratchet(self) -> None:
        measurement = cba.measure(REPO_ROOT, live=False)
        assert set(measurement) == set(cba.REPO_CATEGORIES)
        total_bytes = sum(stats["bytes"] for stats in measurement.values())
        total_tokens = cba._est_tokens(total_bytes, cba.DEFAULT_BYTES_PER_TOKEN)
        breakdown = ", ".join(f"{cat}={stats['bytes']}B" for cat, stats in measurement.items())
        assert total_tokens <= REPO_SCOPE_TOKEN_CEILING, (
            f"always-injected repo-scope context surface is now ~{total_tokens:,} "
            f"est. tokens ({total_bytes:,} bytes), over the "
            f"{REPO_SCOPE_TOKEN_CEILING:,}-token ratchet. Per-category: {breakdown}. "
            "Confirm any addition is truly always-injected (not `paths:`-scopable "
            "or a lazily-read agent/skill body) before raising the ceiling."
        )

    def test_unscoped_rules_stays_under_its_byte_ceiling(self) -> None:
        measurement = cba.measure(REPO_ROOT, live=False)
        size = measurement["unscoped_rules"]["bytes"]
        assert size <= UNSCOPED_RULES_BYTE_CEILING, (
            f".claude/rules/ files without `paths:` frontmatter total {size} bytes, "
            f"over the {UNSCOPED_RULES_BYTE_CEILING}-byte ceiling shared with "
            "cicatrix-superscar.md's own budget test. Give a new unscoped rule "
            "`paths:` scoping, or the existing one grew."
        )
