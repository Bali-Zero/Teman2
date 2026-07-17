"""Tests for scripts/prepush_classify.py (path-aware `.husky/pre-push` gate).

Mandate (2026-07-17, Zero GO, ALLOWLIST inversion same day per 3-LLM panel
verdict — GPT-5.6-Sol ultra + GLM 5.2 + Gemini 3.1 Pro): a PR that does not
touch the backend should not pay for the full Python suite (17,384 tests,
11-32min) on every push. `prepush_classify.py` is the SSOT for the
full/skip-backend decision — this file is its guilt+innocence proof
(cicatrix-superscar.md #3 antidote: "nessuna guardia mergiata senza un test
di innocenza E di colpevolezza").

DESIGN: this is an ALLOWLIST — a path is skip-worthy ONLY if it provably
matches a narrow, individually-verified innocent-path rule. Anything the
allowlist does not recognize defaults to `full`. Every GUILT case here
proves a path that is NOT on the allowlist still forces `full` — including
several paths that a naive denylist-shaped test suite would have called
"obviously safe" (frontend apps, other CI workflows, bali-intel-scraper
migrations) but which are, under this design, intentionally conservative:
the allowlist inversion accepts a higher false-positive (unnecessary full
run) rate to structurally eliminate false negatives (a dangerous skip).
Every INNOCENCE case proves a path that DOES match an allowlist rule
correctly skips — plus the lookalike/word-boundary traps on the allowlist
side itself (cicatrix-superscar.md #3's recurring disease: a prefix check
without a boundary anchor over-matches "docsarchive" as "docs").

The module under test is imported directly (no subprocess) for the pure
`classify()` logic — fast and exhaustive. A handful of CLI-level smoke
tests drive the real `python3 scripts/prepush_classify.py` entrypoint via
subprocess to prove the stdin/argv/stdout contract itself actually holds.

Run:  python3 -m pytest scripts/tests/test_prepush_classify.py -q
"""
from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "prepush_classify.py"
_spec = importlib.util.spec_from_file_location("prepush_classify", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Sanity on the SSOT lists themselves.
# ---------------------------------------------------------------------------


def test_edge_allowlist_prefixes_have_no_trailing_slash() -> None:
    for prefix in pc.ALLOWLIST_INNOCENT_PREFIXES:
        assert not prefix.endswith("/"), f"prefix {prefix!r} must not end with '/'"
        assert prefix.strip() == prefix, f"prefix {prefix!r} must not have stray whitespace"
    for prefix, _suffixes in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS:
        assert not prefix.endswith("/"), f"prefix {prefix!r} must not end with '/'"


def test_edge_never_innocent_exact_paths_are_not_on_the_allowlist() -> None:
    """Belt-and-suspenders self-check: the exact-path override set must not
    accidentally ALSO be coverable by an allowlist entry (that would make
    the override a no-op, silently)."""
    for path in pc.NEVER_INNOCENT_EXACT_PATHS:
        assert pc._innocent_reason(path) is None


# ---------------------------------------------------------------------------
# GUILT — paths NOT provably on the allowlist must force FULL, even ones
# that look intuitively harmless (the accepted cost of the inversion).
# ---------------------------------------------------------------------------


def test_guilt_backend_rag_source_file() -> None:
    verdict, unknown = pc.classify(["apps/backend-rag/backend/app/main.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/app/main.py"]


def test_guilt_requirements_txt_bump() -> None:
    verdict, _ = pc.classify(["apps/backend-rag/requirements.txt"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_crm_cell_file() -> None:
    verdict, _ = pc.classify(["apps/crm-cell/crm_cell/models.py"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_cell_core_package_file() -> None:
    """packages/** is never allowlisted -> unknown -> full, for free, no
    special-cased rule needed (unlike the pre-inversion denylist draft,
    which needed an explicit discovery addition for this exact path)."""
    verdict, unknown = pc.classify(["packages/cell-core/cell_core/genome.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["packages/cell-core/cell_core/genome.py"]


def test_guilt_hook_self_edit() -> None:
    """.husky/pre-push editing ITSELF must force full — mandate 'paranoia',
    enforced via NEVER_INNOCENT_EXACT_PATHS (belt) even though it is also
    structurally unknown-by-omission (suspenders)."""
    verdict, unknown = pc.classify([".husky/pre-push"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".husky/pre-push"]


def test_guilt_classifier_self_edit() -> None:
    verdict, unknown = pc.classify(["scripts/prepush_classify.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/prepush_classify.py"]


def test_guilt_tests_workflow_file() -> None:
    verdict, _ = pc.classify([".github/workflows/tests.yml"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_other_github_workflow_file() -> None:
    """Under the allowlist inversion, ALL of .github/** forces full — not
    just tests.yml (the original mandate's narrower rule). No .github/**
    path is ever allowlisted (panel point 4: 'reusable Actions' is an
    easily-forgotten path), so this is strictly MORE conservative than the
    pre-inversion design, in the safe direction."""
    verdict, _ = pc.classify([".github/workflows/immune-enforcement.yml"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_frontend_app_file() -> None:
    """Under the pre-inversion denylist this correctly skipped. Under the
    allowlist it does NOT (apps/** is never allowlisted) — an accepted,
    intentional over-conservative cost of the inversion, not a bug."""
    verdict, _ = pc.classify(["apps/mouth/app/page.tsx"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_bali_intel_scraper_migrations_now_forces_full() -> None:
    """Same inversion cost as above: apps/bali-intel-scraper/migrations runs
    LOCALLY on Pro only (CLAUDE.md) and is not part of the suite this gate
    protects, but apps/** is never allowlisted, so it is treated as unknown
    -> full. Accepted: false-positive-into-full, never false-negative."""
    verdict, _ = pc.classify(["apps/bali-intel-scraper/migrations/0001_init.sql"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_conftest_anywhere_forces_full_even_under_docs() -> None:
    """NEVER_INNOCENT_BASENAMES belt-and-suspenders: even a hypothetical
    conftest.py placed under an otherwise-allowlisted directory must not
    slip through (panel point 4: 'conftest.py ... A QUALSIASI livello')."""
    verdict, unknown = pc.classify(["docs/conftest.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/conftest.py"]


def test_guilt_pytest_ini_anywhere_forces_full() -> None:
    verdict, _ = pc.classify(["research/pytest.ini"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_pyproject_toml_anywhere_forces_full() -> None:
    verdict, _ = pc.classify(["apps/backend-rag/pyproject.toml"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_dockerfile_forces_full() -> None:
    verdict, _ = pc.classify(["apps/backend-rag/Dockerfile"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_env_example_forces_full() -> None:
    verdict, _ = pc.classify(["apps/backend-rag/.env.example"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_claude_hooks_dir_is_not_allowlisted() -> None:
    """.claude/hooks/ is verified on disk (contains codex-spalla-trigger.sh)
    and is deliberately excluded from the .claude/ allowlist entries —
    control-plane, not content."""
    verdict, unknown = pc.classify([".claude/hooks/codex-spalla-trigger.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".claude/hooks/codex-spalla-trigger.sh"]


def test_guilt_claude_settings_json_is_not_allowlisted() -> None:
    verdict, _ = pc.classify([".claude/settings.local.json"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_claude_scripts_dir_is_not_allowlisted() -> None:
    verdict, _ = pc.classify([".claude/scripts/whatever.py"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_claude_worktrees_dir_is_not_allowlisted() -> None:
    verdict, _ = pc.classify([".claude/worktrees/some-state-file"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_launchagents_python_script_suffix_mismatch() -> None:
    """infra/launchagents/ is scoped to .plist/.sh ONLY — the 2 real .py
    utility scripts verified living in that directory must NOT be swept in
    by a directory-only rule."""
    verdict, unknown = pc.classify(["infra/launchagents/chronic_failure_digest.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["infra/launchagents/chronic_failure_digest.py"]


def test_guilt_non_root_markdown_file_forces_full() -> None:
    """Only ROOT-level *.md is allowlisted — a nested one is not covered by
    that rule (though it may separately be covered by docs/** etc. if it
    happens to live there; this one deliberately does not)."""
    verdict, _ = pc.classify(["apps/backend-rag/README.md"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_mixed_list_any_unknown_wins() -> None:
    """A single non-allowlisted file among many allowlisted ones still
    forces full — the classifier requires unanimous innocence, not a
    majority vote."""
    verdict, unknown = pc.classify(
        [
            "docs/README.md",
            "research/tax/2026-07-17-note.md",
            "apps/backend-rag/backend/services/rag/reasoning.py",
            ".claude/skills/modus/SKILL.md",
        ]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/services/rag/reasoning.py"]


def test_guilt_sentinel_alone_forces_full() -> None:
    verdict, unknown = pc.classify([pc.ERROR_SENTINEL])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [pc.ERROR_SENTINEL]


def test_guilt_sentinel_mixed_with_allowlisted_files_still_forces_full() -> None:
    """The sentinel means 'upstream computation is untrustworthy' — even if
    every OTHER line is on the allowlist, we cannot trust the file list is
    complete, so this must fail closed regardless."""
    verdict, unknown = pc.classify(["docs/README.md", pc.ERROR_SENTINEL, "research/foo.md"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [pc.ERROR_SENTINEL]


# ---------------------------------------------------------------------------
# INNOCENCE — paths that DO provably match an allowlist rule must skip.
# ---------------------------------------------------------------------------


def test_innocence_docs_only() -> None:
    verdict, unknown = pc.classify(["docs/runbooks/some-runbook.md"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_research_only() -> None:
    verdict, _ = pc.classify(["research/operations/2026-07-17-note.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_claude_skills() -> None:
    verdict, _ = pc.classify([".claude/skills/modus/SKILL.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_claude_rules() -> None:
    verdict, _ = pc.classify([".claude/rules/cicatrix-superscar.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_claude_commands() -> None:
    verdict, _ = pc.classify([".claude/commands/some-command.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_claude_agents() -> None:
    verdict, _ = pc.classify([".claude/agents/some-persona.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_infra_launchagents_plist() -> None:
    verdict, _ = pc.classify(["infra/launchagents/com.nuzantara.repomap.15min.plist"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_infra_launchagents_wrapper_sh() -> None:
    verdict, _ = pc.classify(["infra/launchagents/some_wrapper.sh"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_root_level_markdown() -> None:
    verdict, _ = pc.classify(["README.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_root_level_claude_md() -> None:
    verdict, _ = pc.classify(["CLAUDE.md"])
    assert verdict == pc.VERDICT_SKIP


def test_innocence_multiple_allowlisted_entries_together() -> None:
    verdict, unknown = pc.classify(
        [
            "docs/foo.md",
            "research/bar.md",
            ".claude/skills/baz/SKILL.md",
            "infra/launchagents/qux.plist",
            "README.md",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_prefix_trap_docs_lookalike() -> None:
    """cicatrix-superscar.md #3 (guard over-match), now on the ALLOWLIST
    side: a longer sibling directory name that merely STARTS WITH 'docs'
    must NOT match — matching requires the next char to be '/' (or
    end-of-string), never an arbitrary continuation."""
    verdict, unknown = pc.classify(["docsarchive/experiment/foo.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docsarchive/experiment/foo.py"]


def test_innocence_prefix_trap_research_lookalike() -> None:
    verdict, _ = pc.classify(["researching/unrelated/x.py"])
    assert verdict == pc.VERDICT_FULL


def test_innocence_prefix_trap_claude_skills_lookalike() -> None:
    verdict, _ = pc.classify([".claude/skillsdeprecated/x.md"])
    assert verdict == pc.VERDICT_FULL


def test_innocence_prefix_not_at_path_start() -> None:
    """The prefix must anchor the START of the path — a path that merely
    CONTAINS 'docs' deeper in its tree must not match."""
    verdict, _ = pc.classify(["vendor/mirror/docs/foo.md"])
    assert verdict == pc.VERDICT_FULL


def test_innocence_launchagents_prefix_but_wrong_extension_in_sibling_dir() -> None:
    """A .plist file OUTSIDE infra/launchagents/ must not match — the rule
    is prefix AND suffix, not suffix alone."""
    verdict, _ = pc.classify(["infra/other/foo.plist"])
    assert verdict == pc.VERDICT_FULL


# ---------------------------------------------------------------------------
# EDGE — fail-closed contract + normalization + CLI plumbing.
# ---------------------------------------------------------------------------


def test_edge_empty_list_skips_logged(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    verdict, unknown = pc.classify([])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []
    # main() must LOG this (loud, per mandate), not silently pass. argv=[] is
    # falsy in Python, so main() falls through to reading stdin (matching
    # real CLI usage where zero positional args means "read the pipe") —
    # monkeypatch stdin to an explicit empty stream rather than relying on
    # pytest's own ambient stdin capture state (which raises on .read() by
    # default and would otherwise exercise the UNRELATED fail-closed
    # exception path instead of the genuine-empty-input path this test
    # means to cover).
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc = pc.main([])
    assert rc == 0
    out, err = capsys.readouterr()
    assert out.strip() == pc.VERDICT_SKIP
    assert "SKIPPED" in err


def test_edge_blank_lines_only_skip() -> None:
    verdict, unknown = pc.classify(["", "   ", "\n", "\t"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_edge_leading_dot_slash_normalized() -> None:
    verdict, _ = pc.classify(["./docs/foo.md"])
    assert verdict == pc.VERDICT_SKIP


def test_edge_leading_dot_slash_normalized_on_unknown_path() -> None:
    verdict, unknown = pc.classify(["./apps/backend-rag/backend/foo.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/foo.py"]


def test_edge_git_quoted_path_normalized() -> None:
    """git's C-style quoting (core.quotepath=true, the default) wraps the
    WHOLE token in double quotes when a filename needs escaping (e.g.
    non-ASCII bytes) — verify the outer-quote-strip still resolves the
    leading ASCII prefix correctly, on the unknown (full) side."""
    verdict, unknown = pc.classify(['"apps/backend-rag/backend/w\\303\\251ird.py"'])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/w\\303\\251ird.py"]


def test_edge_duplicate_paths_do_not_break_verdict() -> None:
    verdict, unknown = pc.classify(
        ["apps/backend-rag/x.py", "apps/backend-rag/x.py", "apps/backend-rag/x.py"]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/x.py"] * 3  # union-of-unknowns, dedup not required


def test_edge_main_never_raises_on_normal_input(capsys: pytest.CaptureFixture[str]) -> None:
    rc = pc.main(["docs/README.md"])
    assert rc == 0
    out, _ = capsys.readouterr()
    assert out.strip() == pc.VERDICT_SKIP


def test_edge_stdout_contract_is_exactly_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    """The stdout machine contract: exactly one line, exactly the verdict
    string, nothing else — all diagnostics must go to stderr."""
    pc.main(["apps/backend-rag/backend/foo.py"])
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines == [pc.VERDICT_FULL]
    assert "🧭" in err  # the human-readable reasoning lives on stderr, not stdout


def test_edge_skip_banner_names_the_approving_allowlist_entry(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Mandate point 5: the loud skip log must list the files AND the
    allowlist rule that approved each one."""
    pc.main(["docs/foo.md"])
    _out, err = capsys.readouterr()
    assert "docs/foo.md" in err
    assert "docs/**" in err
    assert f"allowlist v{pc.ALLOWLIST_VERSION}" in err


# ---------------------------------------------------------------------------
# EDGE — real subprocess smoke tests (CLI wiring, not just the function).
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_edge_cli_stdin_mode_end_to_end() -> None:
    proc = _run_cli([], stdin_text="apps/backend-rag/backend/foo.py\ndocs/README.md\n")
    assert proc.returncode == 0
    assert proc.stdout.strip() == pc.VERDICT_FULL
    assert proc.stdout.count("\n") <= 1  # exactly one stdout line (trailing newline ok)


def test_edge_cli_stdin_mode_innocent_end_to_end() -> None:
    proc = _run_cli([], stdin_text="docs/README.md\nresearch/foo.md\n")
    assert proc.returncode == 0
    assert proc.stdout.strip() == pc.VERDICT_SKIP


def test_edge_cli_argv_mode_end_to_end() -> None:
    proc = _run_cli(["apps/crm-cell/foo.py"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == pc.VERDICT_FULL


def test_edge_cli_empty_stdin_end_to_end() -> None:
    proc = _run_cli([], stdin_text="")
    assert proc.returncode == 0
    assert proc.stdout.strip() == pc.VERDICT_SKIP


def test_edge_cli_sentinel_via_stdin_end_to_end() -> None:
    proc = _run_cli([], stdin_text=f"{pc.ERROR_SENTINEL}\n")
    assert proc.returncode == 0
    assert proc.stdout.strip() == pc.VERDICT_FULL
