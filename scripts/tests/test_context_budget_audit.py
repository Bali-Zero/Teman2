"""Tests for scripts/context_budget_audit.py — the B6 always-injected
context-surface rollup.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package (mirrors scripts/tests/test_adversarial_review_gate.py /
scripts/tests/test_pending_arms_report.py convention).

Three things, deliberately kept together:

1. Self-tests of the two frontmatter helpers (`has_paths_frontmatter`,
   `frontmatter_fields`) and of `measure()` itself, on fixtures built in
   `tmp_path` — never against the real repo, so these stay green regardless
   of what any other in-flight PR does to `.claude/`.
2. A RATCHET on the real repo's four repo-scope categories
   (`root_claude_md`, `unscoped_rules`, `agents_frontmatter`,
   `skills_listing`): total estimated tokens must stay at or under
   `REPO_SCOPE_TOKEN_CEILING`. This is deliberately NOT the diet's eventual
   target of 15,000 tokens — measured at write time (2026-09-04, ratio
   2.04 bytes/token) the real total was ~15,553 est. tokens, almost
   entirely `root_claude_md` (~5,182) + `unscoped_rules`
   (~6,120, i.e. `cicatrix-superscar.md` sitting near its own independent
   14KB cap) with `agents_frontmatter`/`skills_listing` a smaller remainder
   (~2,293 + ~1,959). Two sibling mandates in flight the same day
   (`b1-superscar`, shrinking `cicatrix-superscar.md`; `b3-claude-md`,
   shrinking the root `CLAUDE.md`) are expected to pull the real number
   down — when they land, TIGHTEN `REPO_SCOPE_TOKEN_CEILING` toward 15,000
   rather than leaving headroom that only masks the next regression. The
   assertion message always prints the number this run actually measured,
   so tightening it is a one-line, evidence-backed edit, never a guess.
3. A per-category guard: `unscoped_rules` stays at or under 14,000 BYTES —
   the exact `BYTE_BUDGET` `test_superscar_budget.py` already enforces on
   `cicatrix-superscar.md` (currently the sole unscoped-rules contributor).
   Deliberately not lowered here: another PR (`b1-superscar`) owns lowering
   that cap: this guard exists only to catch a NEW unscoped `.claude/rules/`
   file (one that forgot its `paths:` frontmatter) pushing the category over
   budget, not to police the existing superscar diet.
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

# Ratchet, not the diet's eventual target — see module docstring point 2.
# Current measured (2026-09-04, ratio 2.04): ~15,553 est. tokens.
REPO_SCOPE_TOKEN_CEILING = 16_000

# Matches test_superscar_budget.py's BYTE_BUDGET exactly (see point 3 above).
UNSCOPED_RULES_BYTE_CEILING = 14_000


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Self-tests: frontmatter helpers
# ---------------------------------------------------------------------------


class TestHasPathsFrontmatter:
    def test_no_frontmatter_at_all_is_false(self) -> None:
        assert cba.has_paths_frontmatter("# just a heading\n\nsome prose\n") is False

    def test_frontmatter_without_a_paths_key_is_false(self) -> None:
        text = "---\nname: infra\ndescription: some rule\n---\n\nbody\n"
        assert cba.has_paths_frontmatter(text) is False

    def test_single_line_paths_list_is_true(self) -> None:
        text = '---\npaths: ["scripts/generate_*.py"]\n---\n\nbody\n'
        assert cba.has_paths_frontmatter(text) is True

    def test_multiline_paths_list_is_true(self) -> None:
        text = (
            "---\n"
            "paths:\n"
            "  [\n"
            '    "apps/mouth/**/*.{ts,tsx,js,jsx}",\n'
            '    "apps/webapp/**/*.{ts,tsx}",\n'
            "  ]\n"
            "---\n\n"
            "body\n"
        )
        assert cba.has_paths_frontmatter(text) is True

    def test_unclosed_frontmatter_is_false(self) -> None:
        assert cba.has_paths_frontmatter("---\npaths: [x]\nno closing marker\n") is False


class TestFrontmatterFields:
    def test_file_without_frontmatter_yields_empty_dict(self) -> None:
        assert cba.frontmatter_fields("# body only, no frontmatter\n") == {}

    def test_simple_scalar_fields_are_extracted(self) -> None:
        text = "---\nname: backend-verifier\ndescription: verify backend health\n---\n\nbody\n"
        fields = cba.frontmatter_fields(text)
        assert fields["name"] == "backend-verifier"
        assert fields["description"] == "verify backend health"

    def test_quoted_values_have_quotes_stripped(self) -> None:
        text = '---\nname: bot\ndescription: "Zantara WA bot corner"\n---\n\nbody\n'
        fields = cba.frontmatter_fields(text)
        assert fields["description"] == "Zantara WA bot corner"

    def test_tools_field_is_the_raw_comma_list(self) -> None:
        text = "---\nname: x\ntools: Bash, Read, Grep, Glob\n---\n\nbody\n"
        assert cba.frontmatter_fields(text)["tools"] == "Bash, Read, Grep, Glob"


# ---------------------------------------------------------------------------
# Self-tests: measure() on fixtures — never on the real repo
# ---------------------------------------------------------------------------


class TestMeasureOnFixtures:
    def test_a_rule_with_a_multiline_paths_list_is_excluded(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "CLAUDE.md",
            "root claude md\n" * 5,
        )
        _write(
            tmp_path / ".claude" / "rules" / "scoped.md",
            "---\npaths:\n  [\n"
            '    "apps/mouth/**/*.ts",\n'
            "  ]\n---\n\nscoped body, must not be counted\n",
        )
        result = cba.measure(tmp_path)
        assert result["unscoped_rules"] == {"files": 0, "bytes": 0}

    def test_a_rule_without_paths_frontmatter_is_included(self, tmp_path: Path) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        rule_text = "---\nname: infra\n---\n\nalways-injected body\n"
        _write(tmp_path / ".claude" / "rules" / "unscoped.md", rule_text)
        result = cba.measure(tmp_path)
        assert result["unscoped_rules"] == {
            "files": 1,
            "bytes": len(rule_text.encode("utf-8")),
        }

    def test_mixed_scoped_and_unscoped_rules_counts_only_the_unscoped_one(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        _write(
            tmp_path / ".claude" / "rules" / "scoped.md",
            '---\npaths: ["**/*.py"]\n---\n\nscoped\n',
        )
        unscoped_text = "---\nname: always\n---\n\nalways body\n"
        _write(tmp_path / ".claude" / "rules" / "unscoped.md", unscoped_text)
        result = cba.measure(tmp_path)
        assert result["unscoped_rules"]["files"] == 1
        assert result["unscoped_rules"]["bytes"] == len(unscoped_text.encode("utf-8"))

    def test_an_agent_file_without_frontmatter_contributes_zero(self, tmp_path: Path) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        _write(
            tmp_path / ".claude" / "agents" / "no-frontmatter.md",
            "# just an agent body, no frontmatter block at all\n",
        )
        result = cba.measure(tmp_path)
        assert result["agents_frontmatter"] == {"files": 0, "bytes": 0}

    def test_an_agent_file_with_frontmatter_contributes_name_description_tools_length(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        _write(
            tmp_path / ".claude" / "agents" / "verifier.md",
            "---\nname: verifier\ndescription: checks things\ntools: Bash, Read\n---\n\nbody\n",
        )
        result = cba.measure(tmp_path)
        expected = len("verifier") + len("checks things") + len("Bash, Read")
        assert result["agents_frontmatter"] == {"files": 1, "bytes": expected}

    def test_skill_and_command_files_are_summed_into_one_category(
        self, tmp_path: Path
    ) -> None:
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
            len("bot")
            + len("wa bot corner")
            + len("verify")
            + len("empirical verification")
        )
        assert result["skills_listing"] == {"files": 2, "bytes": expected}

    def test_a_missing_repo_root_claude_md_is_zero_not_a_crash(self, tmp_path: Path) -> None:
        result = cba.measure(tmp_path)
        assert result["root_claude_md"] == {"files": 0, "bytes": 0}

    def test_live_categories_are_absent_unless_requested(self, tmp_path: Path) -> None:
        _write(tmp_path / "CLAUDE.md", "root\n")
        result = cba.measure(tmp_path, live=False)
        for key in cba.LIVE_CATEGORIES:
            assert key not in result
        for key in cba.REPO_CATEGORIES:
            assert key in result


# ---------------------------------------------------------------------------
# The real repo: the actual guard
# ---------------------------------------------------------------------------


class TestTheRealRepoScopeStaysUnderBudget:
    def test_total_repo_scope_estimated_tokens_stays_under_the_ratchet(self) -> None:
        measurement = cba.measure(REPO_ROOT, live=False)
        assert set(measurement) == set(cba.REPO_CATEGORIES)
        total_bytes = sum(stats["bytes"] for stats in measurement.values())
        total_tokens = cba._est_tokens(total_bytes, cba.DEFAULT_BYTES_PER_TOKEN)
        breakdown = ", ".join(
            f"{cat}={stats['bytes']}B" for cat, stats in measurement.items()
        )
        assert total_tokens <= REPO_SCOPE_TOKEN_CEILING, (
            f"always-injected repo-scope context surface is now ~{total_tokens:,} "
            f"est. tokens ({total_bytes:,} bytes), over the "
            f"{REPO_SCOPE_TOKEN_CEILING:,}-token ratchet. Per-category: {breakdown}. "
            "If this is a deliberate addition, confirm it is truly always-injected "
            "(not something that belongs behind a `paths:` scope or a lazily-read "
            "agent/skill body) before raising the ceiling."
        )

    def test_unscoped_rules_stays_under_its_byte_ceiling(self) -> None:
        measurement = cba.measure(REPO_ROOT, live=False)
        size = measurement["unscoped_rules"]["bytes"]
        assert size <= UNSCOPED_RULES_BYTE_CEILING, (
            f".claude/rules/ files without `paths:` frontmatter total {size} bytes, "
            f"over the {UNSCOPED_RULES_BYTE_CEILING}-byte ceiling shared with "
            "cicatrix-superscar.md's own budget test. Either a new unscoped rule "
            "file appeared (give it `paths:` scoping if it doesn't need to be "
            "always-injected) or the existing one grew."
        )
