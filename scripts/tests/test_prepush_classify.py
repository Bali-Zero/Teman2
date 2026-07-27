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
    """v2 (round-1 red-team): ALLOWLIST_INNOCENT_PREFIXES (bare-prefix, no
    suffix scoping) was REMOVED entirely — ALLOWLIST_PREFIX_SUFFIX_PAIRS is
    now the ONLY allowlist mechanism in the module. This test asserts that
    single-mechanism invariant directly (no leftover bare-prefix list to
    accidentally reintroduce), plus the original prefix/suffix hygiene
    checks."""
    assert not hasattr(pc, "ALLOWLIST_INNOCENT_PREFIXES"), (
        "the bare-prefix allowlist was removed in v2 (round-1 MUST-FIX) — "
        "its reappearance would reintroduce the extension-blindness bug"
    )
    seen_prefixes: set[str] = set()
    for prefix, suffixes in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS:
        assert not prefix.endswith("/"), f"prefix {prefix!r} must not end with '/'"
        assert prefix.strip() == prefix, f"prefix {prefix!r} must not have stray whitespace"
        assert prefix not in seen_prefixes, f"duplicate prefix {prefix!r}"
        seen_prefixes.add(prefix)
        assert suffixes, f"prefix {prefix!r} must declare at least one allowed suffix"
        for suffix in suffixes:
            assert suffix.startswith("."), f"suffix {suffix!r} for prefix {prefix!r} must start with '.'"


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
    """v3 (task #43) makes this the LOAD-BEARING proof, not a redundant one:
    .github/workflows is now a broadly-allowlisted prefix (.yml suffix), so
    this specifically proves the NEVER_INNOCENT_EXACT_PATHS exact-path
    override for tests.yml — the workflow that DEFINES the required test
    run — still wins over the broader rule (checked first in
    _innocent_reason, before the allowlist loop is ever reached)."""
    verdict, _ = pc.classify([".github/workflows/tests.yml"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_github_workflows_non_yml_file() -> None:
    """.github/workflows/ is scoped to .yml ONLY (v3) — the 1 real .txt file
    verified living in that directory must not be swept in by a
    directory-only rule."""
    verdict, unknown = pc.classify([".github/workflows/catE-paid-anthropic-baseline.txt"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".github/workflows/catE-paid-anthropic-baseline.txt"]


def test_guilt_github_dir_outside_workflows() -> None:
    """The v3 rule's prefix is .github/workflows specifically, not .github
    wholesale — a path elsewhere under .github/ (CODEOWNERS, actions/**)
    must still force full."""
    verdict, unknown = pc.classify([".github/CODEOWNERS"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".github/CODEOWNERS"]


def test_guilt_github_workflows_lookalike_prefix() -> None:
    """cicatrix-superscar.md #3 (guard over-match) on the new rule: a longer
    sibling directory name that merely STARTS WITH '.github/workflows' must
    not match."""
    verdict, unknown = pc.classify([".github/workflows-archive/old.yml"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".github/workflows-archive/old.yml"]


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


def test_guilt_scripts_tests_shell_script_suffix_mismatch() -> None:
    """scripts/tests/ is scoped to .py ONLY (v3) — the 1 real .sh file
    verified living in that directory must not be swept in by a
    directory-only rule."""
    verdict, unknown = pc.classify(["scripts/tests/test_prepush_failclosed.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/tests/test_prepush_failclosed.sh"]


def test_guilt_scripts_tests_conftest_still_forced_full() -> None:
    """Directly-scoped proof (not just 'anywhere' via
    test_guilt_conftest_anywhere_forces_full_even_under_docs) that the v3
    scripts/tests/ allowlist entry does not swallow the one file it must
    never swallow: scripts/tests/conftest.py, a REAL file on disk, stays
    forced full via NEVER_INNOCENT_BASENAMES, checked before the allowlist
    loop."""
    verdict, unknown = pc.classify(["scripts/tests/conftest.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/tests/conftest.py"]


def test_guilt_scripts_tests_lookalike_prefix() -> None:
    """cicatrix-superscar.md #3 (guard over-match) on the new rule: a longer
    sibling directory name that merely STARTS WITH 'scripts/tests' must not
    match."""
    verdict, unknown = pc.classify(["scripts/testsuite/foo.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/testsuite/foo.py"]


def test_guilt_scripts_tests_prefix_not_at_path_start() -> None:
    verdict, _ = pc.classify(["vendor/mirror/scripts/tests/foo.py"])
    assert verdict == pc.VERDICT_FULL


def test_guilt_scripts_non_tests_python_file_still_forces_full() -> None:
    """task #43 mandate, verbatim: 'a .py under scripts/ that is NOT
    scripts/tests/ still escalates to full'. The prefix is scripts/tests
    specifically, not scripts/ wholesale — a sibling script one directory up
    must not be swept in. Real file, verified on disk."""
    verdict, unknown = pc.classify(["scripts/agent_start.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/agent_start.py"]


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
# ROUND-1 RED-TEAM MUST-FIX — extension-blindness on the (now-removed)
# bare-prefix allowlist. Two independent seats (Codex Sol xhigh diff review
# + a live-execution tester with 33 adversarial inputs) converged on this
# finding 2026-07-18 against PR #2642: docs/**, research/**, and the 4
# .claude/{skills,rules,commands,agents}/** entries used to be bare
# directory prefixes admitting ANY extension underneath, including .sh/.py.
# Verified LIVE against the actual repo tree (not hypothetical): docs/ has 7
# real .sh + 8 real .py files today; research/ has 14 real .py files today.
# Every vector explicitly named by the red-team is locked here.
# ---------------------------------------------------------------------------


def test_guilt_claude_skills_shell_script_must_force_full() -> None:
    """Exact vector named by the red-team: a .sh file nested under an
    allowlisted .claude/skills/ directory must NOT read as innocent on
    pathname alone."""
    verdict, unknown = pc.classify([".claude/skills/x/run.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".claude/skills/x/run.sh"]


def test_guilt_claude_skills_python_script_must_force_full() -> None:
    """Exact vector named by the red-team."""
    verdict, unknown = pc.classify([".claude/skills/x/deploy.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".claude/skills/x/deploy.py"]


def test_guilt_docs_shell_script_must_force_full() -> None:
    """Exact vector named by the red-team: docs/** is content-only (.md),
    not a free pass for executables placed underneath."""
    verdict, unknown = pc.classify(["docs/a/b.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/a/b.sh"]


def test_guilt_docs_nested_launchagents_lookalike_shell_script() -> None:
    """Sol's exact example: a .sh file living UNDER docs/ (not under the
    real infra/launchagents/ prefix) must still force full — the
    infra/launchagents/ .sh allowance is prefix-scoped, it does not leak
    into other directories that merely happen to contain a similarly-named
    subpath."""
    verdict, unknown = pc.classify(["docs/infra/launchagents/nuz-sync/nuz-sync.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/infra/launchagents/nuz-sync/nuz-sync.sh"]


def test_guilt_research_python_script_must_force_full() -> None:
    """research/ has 14 real .py files today (verified) — none of them may
    read as innocent; research/** is scoped to .md only, symmetric with
    docs/**."""
    verdict, unknown = pc.classify(["research/operations/some_script.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["research/operations/some_script.py"]


def test_guilt_claude_rules_non_markdown_must_force_full() -> None:
    """Symmetric coverage: all 4 .claude/{skills,rules,commands,agents}/**
    entries share the same suffix-scoping mechanism — prove each
    independently rather than assuming the loop covers them uniformly."""
    verdict, unknown = pc.classify([".claude/rules/generator.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".claude/rules/generator.py"]


def test_guilt_claude_commands_non_markdown_must_force_full() -> None:
    verdict, unknown = pc.classify([".claude/commands/install.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".claude/commands/install.sh"]


def test_guilt_claude_agents_non_markdown_must_force_full() -> None:
    verdict, unknown = pc.classify([".claude/agents/loader.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".claude/agents/loader.py"]


def test_innocence_infra_launchagents_wrapper_regression_check() -> None:
    """Regression check named explicitly by the red-team: the real,
    on-disk-shaped wrapper infra/launchagents/wrappers/wa-mirror-runner.sh
    must STILL correctly skip after the v1->v2 refactor unified the
    allowlist mechanism — infra/launchagents/ keeps .sh as a DECLARED
    choice (see module docstring), this is not collateral damage from the
    MUST-FIX, it is the mechanism working as designed for the one prefix
    that legitimately needs a non-.md suffix."""
    verdict, unknown = pc.classify(["infra/launchagents/wrappers/wa-mirror-runner.sh"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


# ---------------------------------------------------------------------------
# ROUND-1 RED-TEAM HARDENING-2 — path-traversal segments and embedded
# newlines. Found by the live-execution tester (not reachable via the real
# git-diff caller today, since `--no-renames`-diffed paths never contain
# `..` or embedded newlines in practice) but this module is a reusable pure
# SSOT and its input contract must hold regardless of caller.
# ---------------------------------------------------------------------------


def test_guilt_path_traversal_segment_escapes_allowlist_directory() -> None:
    """Without the `..`-segment rejection, this path would STRING-match
    both the docs/ prefix and the .md suffix and read as innocent, despite
    not actually resolving to anywhere under docs/. Proves the fix is
    load-bearing, not decorative."""
    verdict, unknown = pc.classify(["docs/../apps/backend-rag/x.md"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/../apps/backend-rag/x.md"]


def test_guilt_path_traversal_segment_in_the_middle() -> None:
    verdict, unknown = pc.classify(["docs/subdir/../../apps/backend-rag/evil.md"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/subdir/../../apps/backend-rag/evil.md"]


def test_guilt_double_dot_as_a_whole_segment_not_a_substring_false_positive() -> None:
    """Word-boundary sanity (cicatrix-superscar.md #3 discipline applied to
    the traversal check itself): a directory literally named '..foo' or
    'bar..' is NOT a traversal segment and must not be confused with one —
    the check is `".." in path.split("/")` (exact segment equality), never
    a bare substring test. This directory does not exist and is not
    allowlisted anyway, so the expected verdict is FULL for the mundane
    unknown-path reason, not because of a traversal false-positive."""
    verdict, unknown = pc.classify(["weird..dir/apps/x.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["weird..dir/apps/x.py"]


def test_guilt_embedded_newline_in_a_single_classify_entry() -> None:
    """Belt-and-suspenders at the classify()/_innocent_reason() layer
    itself: even if a caller bypasses _read_input() entirely and hands
    classify() a pre-split list where one entry still carries an embedded
    newline (a caller contract violation), that entry must never read as
    innocent."""
    verdict, unknown = pc.classify(["docs/a.md\napps/backend-rag/evil.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/a.md\napps/backend-rag/evil.py"]


def test_guilt_embedded_carriage_return_in_a_single_classify_entry() -> None:
    verdict, unknown = pc.classify(["docs/a.md\rapps/backend-rag/evil.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["docs/a.md\rapps/backend-rag/evil.py"]


def test_edge_argv_entry_with_embedded_newline_is_split_before_classification(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real fix lives in _read_input(): an argv entry containing an
    embedded newline is split into its constituent paths BEFORE reaching
    classify(), exactly like stdin mode already does — so the backend file
    is classified on its own merits (unknown -> full) rather than the
    whole blob being rejected as one malformed string. Verdict is the same
    (full) either way here, but the `unknown` list proves WHICH mechanism
    fired: the split-then-evaluate path, not the embedded-newline guard."""
    rc = pc.main(["docs/a.md\napps/backend-rag/evil.py"])
    assert rc == 0
    out, _err = capsys.readouterr()
    assert out.strip() == pc.VERDICT_FULL
    # Confirm the split actually happened (not the raw blob) by checking
    # the pure function directly with the same pre-split input _read_input
    # would have produced.
    verdict, unknown = pc.classify(["docs/a.md", "apps/backend-rag/evil.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/evil.py"]


def test_edge_argv_entry_with_embedded_newline_both_halves_innocent_still_skips() -> None:
    """Positive-path proof that the argv split is a genuine parse, not just
    a blunt 'newline present -> full' shortcut: TWO separately-innocent
    paths smuggled into one argv entry via an embedded newline must BOTH
    be recognized and the overall verdict must be skip-backend."""
    verdict, unknown = pc.classify(
        pc._read_input(["docs/a.md\ndocs/b.md"])
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_edge_read_input_argv_splits_on_embedded_newline() -> None:
    """Direct unit test of _read_input()'s contract: argv and stdin must
    split identically on '\\n' — this was the exact HARDENING-2 gap (argv
    mode used to treat one arg as exactly one path)."""
    assert pc._read_input(["a.md\nb.md"]) == ["a.md", "b.md"]
    assert pc._read_input(["a.md", "b.md"]) == ["a.md", "b.md"]


def test_edge_read_input_empty_argv_falls_through_to_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity on the OTHER branch: empty argv (falsy in Python, same trap
    documented at test_edge_empty_list_skips_logged) must take the stdin
    path, not silently return []  without ever consulting stdin. Explicit
    stdin monkeypatch — calling _read_input([]) with pytest's ambient
    captured stdin raises, which is a test-harness artifact, not a
    property of this function (same lesson as test_edge_empty_list_skips_logged
    above)."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("a.md\nb.md\n"))
    assert pc._read_input([]) == ["a.md", "b.md"]


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


def test_innocence_github_workflows_yml() -> None:
    """v3 (task #43): a .yml file under .github/workflows/, OTHER than
    tests.yml (see test_guilt_tests_workflow_file for that exempted case),
    now skips — measured 2026-07-26 to be structurally incapable of
    affecting `pytest backend/tests/`'s outcome (module docstring, 'v3
    EXTENSION'). This is the same real file the pre-v3 guilt test used,
    now moved to innocence because the rule it demonstrated changed."""
    verdict, unknown = pc.classify([".github/workflows/immune-enforcement.yml"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_scripts_tests_test_file() -> None:
    """v3 (task #43): a scripts/tests/test_*.py file — the 235-file suite
    audited in task #16 — now skips. Real file, verified on disk."""
    verdict, unknown = pc.classify(["scripts/tests/test_guardrail_liveness.py"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_workflow_only_diff_skips() -> None:
    """task #43 mandate, verbatim: 'a workflow-only diff ... skip[s]'. A
    real multi-file diff touching only .github/workflows/*.yml files (not
    tests.yml) must skip as a whole, not just file-by-file."""
    verdict, unknown = pc.classify(
        [
            ".github/workflows/scripts-tests-sweep.yml",
            ".github/workflows/immune-enforcement.yml",
            ".github/workflows/actionlint.yml",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_scripts_tests_only_diff_skips() -> None:
    """task #43 mandate, verbatim: 'a scripts/tests-only diff ... skip[s]'.
    A real multi-file diff touching only scripts/tests/test_*.py files must
    skip as a whole."""
    verdict, unknown = pc.classify(
        [
            "scripts/tests/test_guardrail_liveness.py",
            "scripts/tests/test_prepush_classify.py",
            "scripts/tests/test_modus_green_gate.py",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_scripts_tests_init_py() -> None:
    """scripts/tests/__init__.py is admitted by the same .py suffix rule as
    any other file in the directory — deliberate, not an oversight: verified
    empty on disk, and additionally unreachable from `pytest backend/tests/`
    by the same import-chain argument as the test_*.py files (module
    docstring, 'v3 EXTENSION')."""
    verdict, unknown = pc.classify(["scripts/tests/__init__.py"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


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


# ===========================================================================
# v4 — apps/mouth/src (.ts/.tsx/.css)
#
# Why this entry exists: it is the last high-traffic tree with no rule, so
# every frontend-only PR paid the full ~43min backend suite. On 2026-07-27
# that cost FOUR consecutive pushes of a single frontend-only branch — the
# suite simply outlives the background task's budget.
#
# Why it is safe: measured on disk, no backend test opens a file under
# apps/mouth (10 mention it, all as string literals fed to a path->command
# mapper). The dangerous suffix is `.mdx`, which has a REAL reader
# (backend/scripts/index_mdx_to_balizero_news.py does rglob("*.mdx") +
# read_text) — hence excluded, and pinned as GUILT below.
# ===========================================================================


def test_innocence_mouth_src_ts_and_tsx_skip() -> None:
    """The shapes this entry exists for: a lib module, a component, a page."""
    for path in (
        "apps/mouth/src/lib/kbli-bali-block.ts",
        "apps/mouth/src/lib/kbli-bali-block.test.ts",
        "apps/mouth/src/components/kbli/LicensingSection.tsx",
        "apps/mouth/src/app/kbli/[code]/page.tsx",
        "apps/mouth/src/app/globals.css",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_SKIP, f"{path} should skip, got {verdict}"
        assert unknown == []


def test_innocence_real_frontend_only_pr_skips() -> None:
    """The actual file list of PR #3262 (frontend files only) — the diff
    whose four pushes died paying for a suite that could not see it."""
    verdict, unknown = pc.classify(
        [
            "apps/mouth/src/lib/kbli-bali-block.ts",
            "apps/mouth/src/lib/kbli-bali-block.test.ts",
            "apps/mouth/src/components/kbli/LicensingSection.tsx",
            "apps/mouth/src/app/kbli/[code]/page.tsx",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_mouth_mdx_still_forces_full() -> None:
    """`.mdx` is excluded because a real backend reader exists:
    backend/scripts/index_mdx_to_balizero_news.py rglob()s and read_text()s
    the articles tree. 3360 of the 3835 tracked files under src/ are .mdx —
    admitting them would be the single largest hole this entry could open."""
    verdict, unknown = pc.classify(
        ["apps/mouth/src/content/articles/business/kbli-2025-great-transition.mdx"]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == [
        "apps/mouth/src/content/articles/business/kbli-2025-great-transition.mdx"
    ]


def test_guilt_mouth_dataset_outside_src_forces_full() -> None:
    """Scoped to src/ specifically, NOT apps/mouth wholesale: the KBLI
    dataset copies live in apps/mouth/data/ and are data-plane artifacts."""
    for path in (
        "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",
        "apps/mouth/data/kbli-gold-all.json",
        "apps/mouth/next.config.ts",
        "apps/mouth/package.json",
    ):
        verdict, _ = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"


def test_guilt_mouth_src_wrong_suffix_forces_full() -> None:
    """Suffix scoping is the mechanism — a .json or .yaml under src/ is not
    admitted just because its directory is."""
    for path in (
        "apps/mouth/src/data/services_data.json",
        "apps/mouth/src/i18n/messages.json",
        "apps/mouth/src/app/opengraph.png",
    ):
        verdict, _ = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"


def test_guilt_mouth_src_lookalike_prefix_forces_full() -> None:
    """#3's recurring disease: a prefix check without a boundary anchor
    over-matches. `srcarchive` is not `src`."""
    for path in (
        "apps/mouth/srcarchive/old.ts",
        "apps/mouth/src-backup/old.tsx",
        "apps/mouth-legacy/src/old.ts",
    ):
        verdict, _ = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"


def test_guilt_mouth_src_mixed_with_backend_forces_full() -> None:
    """One backend file anywhere in the diff still forces the full suite."""
    verdict, unknown = pc.classify(
        [
            "apps/mouth/src/lib/kbli-bali-block.ts",
            "apps/backend-rag/backend/services/rag/reasoning.py",
        ]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/services/rag/reasoning.py"]


def test_guilt_mouth_src_traversal_escape_forces_full() -> None:
    """HARDENING-2 still holds for the new entry: `..` must not let a path
    suffix-match its way out of the allowlisted directory."""
    verdict, _ = pc.classify(
        ["apps/mouth/src/../../backend-rag/backend/services/rag/reasoning.ts"]
    )
    assert verdict == pc.VERDICT_FULL


def test_allowlist_version_bumped_for_the_new_entry() -> None:
    """The skip-banner logs the allowlist version that approved a skip, so a
    rules change that does not bump it makes the log line unattributable."""
    assert pc.ALLOWLIST_VERSION >= 4
    assert ("apps/mouth/src", (".ts", ".tsx", ".css")) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS


# ===========================================================================
# v5 — .agents/skills (.md) and scripts/ci (.sh)
#
# Why these entries exist: measured live 2026-07-27 on M5, load average 41,
# 9 concurrent full `pytest backend/tests/` suites (one 1h21m in). Tracing
# each running suite to its worktree/merge-base diff found 7 of the 9
# guarded diffs contained ZERO backend files — two were pure markdown-only
# diffs whose ONLY changed file sits under `.agents/skills/`, a third was
# blocked solely by `scripts/ci/setup_merge_queue_ruleset.sh`.
#
# Why .agents/skills is safe: `.agents/skills/README.md` (verified on disk)
# states this tree is the CANONICAL cross-agent skill store (established
# 2026-07-23) — `.claude/skills/<name>` is a SYMLINK to it for 4 of 8
# corners (bot/kbli-navigator/visaoracle/wr2, `git ls-tree` mode 120000
# verified), so a SKILL.md edit through either path lands its `git diff` on
# the `.agents/skills/**` blob, which the pre-v5 `.claude/skills` rule never
# covered. Innocence measured on disk: zero matches for the DIRECTORY-
# ANCHORED string `.agents/` anywhere under apps/backend-rag/backend/
# (tests or modules) — a bare `\.agents` grep instead false-positives on
# Python dotted-module paths like `backend.app.agents.graph`.
#
# Why scripts/ci is safe: mirrors the DECLARED .sh precedent already
# accepted for infra/launchagents. Innocence measured on disk: zero matches
# for the DIRECTORY-ANCHORED string `scripts/ci/` under
# apps/backend-rag/backend/ — a bare `scripts/ci` grep instead
# false-positives on the unrelated `apps/backend-rag/scripts/ci_bootstrap_
# schema.py`. Also zero basename-only hits for each of the 3 real .sh
# files, in case a test subprocess-invokes one without the dir prefix.
# ===========================================================================


def test_innocence_agents_skills_md_skips() -> None:
    """The two live-worktree shapes the v5 measurement actually caught:
    one-file SKILL.md-only diffs under the canonical .agents/skills store."""
    for path in (
        ".agents/skills/bot/SKILL.md",
        ".agents/skills/kbli-navigator/SKILL.md",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_SKIP, f"{path} should skip, got {verdict}"
        assert unknown == []


def test_innocence_scripts_ci_setup_merge_queue_ruleset_skips() -> None:
    """The third v5-measurement diff: blocked solely by this one .sh file."""
    verdict, unknown = pc.classify(["scripts/ci/setup_merge_queue_ruleset.sh"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_real_agents_one_file_diffs_skip() -> None:
    """The two REAL one-file diffs measured live 2026-07-27
    (docs-kbli-night-findings, ops-bot-corner-refresh worktrees) — each
    changed exactly one .agents/skills/**/SKILL.md file and each had been
    paying a full backend suite before this entry existed."""
    for path in (
        ".agents/skills/kbli-navigator/SKILL.md",
        ".agents/skills/bot/SKILL.md",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_SKIP
        assert unknown == []


def test_innocence_real_pr_c_three_file_list_skips() -> None:
    """PR-C's real 3-file diff — a workflow + a runbook + this PR's new
    scripts/ci .sh entry, all three now provably innocent together."""
    verdict, unknown = pc.classify(
        [
            ".github/workflows/merge-queue-watch.yml",
            "docs/runbooks/merge-queue-discipline.md",
            "scripts/ci/setup_merge_queue_ruleset.sh",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_agents_non_md_forces_full() -> None:
    """Suffix scoping is the mechanism — the one real non-.md file that
    lives under .agents/skills/ today must NOT be admitted just because its
    directory is."""
    path = ".agents/skills/wr2/_research/2026-07-21-ir-phase1-replay-metrics.json"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_scripts_ci_py_forces_full() -> None:
    """Suffix scoping again — the 2 real .py utilities in scripts/ci/ stay
    OUT, same shape as the infra/launchagents .py exclusion above."""
    for path in (
        "scripts/ci/l5_2_phase2b_auto_analyzer.py",
        "scripts/ci/redis_lease_check.py",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_agents_mixed_with_backend_forces_full() -> None:
    """One backend file anywhere in the diff still forces the full suite,
    even alongside an otherwise-innocent .agents/skills edit."""
    verdict, unknown = pc.classify(
        [
            ".agents/skills/bot/SKILL.md",
            "apps/backend-rag/backend/services/rag/reasoning.py",
        ]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/services/rag/reasoning.py"]


def test_guilt_prepush_classify_itself_forces_full() -> None:
    """This very PR's own diff touches scripts/prepush_classify.py, a
    NEVER_INNOCENT_EXACT_PATHS entry — correct by design, so this PR's own
    push pays the full suite it is trying to spare OTHER diffs from."""
    verdict, unknown = pc.classify(["scripts/prepush_classify.py"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/prepush_classify.py"]


def test_allowlist_version_bumped_to_5_for_the_v5_entries() -> None:
    """The skip-banner logs the allowlist version that approved a skip, so a
    rules change that does not bump it makes the log line unattributable."""
    assert pc.ALLOWLIST_VERSION >= 5
    assert (".agents/skills", (".md",)) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    assert ("scripts/ci", (".sh",)) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS


# ---------------------------------------------------------------------------
# The gate's INPUT, not its rules: `.husky/pre-push` must enumerate changed
# files against the MERGE-BASE with origin/main, never against $remote_sha.
#
# The hook used to branch: merge-base for a brand-new branch, `$remote_sha`
# ("only the NEW commits") for one already on the remote. That asymmetry meant
# a branch that merged origin/main in — the normal way to resolve a conflict —
# handed this classifier every file MAIN had gained since the last push, and
# the verdict came back `full` on files already merged and already tested.
# Measured 2026-07-26: a two-file diff whose files are BOTH on the allowlist
# was reported as "11/20 changed file(s) are NOT on the innocent allowlist",
# naming .gitignore, published_articles.json, escalations_pro.jsonl … Three
# ~40-minute full-suite runs; the same delta re-cut from main passed in
# seconds. The RULES were right — the INPUT lied. W102's shape, in the
# pre-push gate rather than in CI.
#
# These live here (and not in test_prepush_failclosed.sh, the other pre-push
# test) because `.github/workflows/immune-enforcement.yml` names THIS file on a
# real pytest line, and names that one nowhere: a guard no workflow runs is
# written, not armed (superscar #2).
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).resolve().parents[2] / ".husky" / "pre-push"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _hook_source() -> str:
    """Fails loudly if the hook is missing rather than vacuously passing on ''."""
    assert HOOK_PATH.is_file(), f"{HOOK_PATH} not found — re-anchor this pin, do not delete it"
    return HOOK_PATH.read_text(encoding="utf-8")


def test_hook_anchors_the_diff_range_to_the_merge_base() -> None:
    """INNOCENCE: the live hook computes RANGE_FROM from `git merge-base origin/main`."""
    src = _hook_source()
    assert 'RANGE_FROM="$(git merge-base origin/main "$local_sha"' in src, (
        "the pre-push diff range is no longer anchored to the merge-base with "
        "origin/main; a branch that merges main in will hand the classifier "
        "MAIN's files and force the full suite on already-tested work"
    )


def test_hook_never_anchors_the_range_to_remote_sha() -> None:
    """GUILT: the exact form that caused the defect must not come back.

    Without this half, the innocence test above would still pass if someone
    re-added the `$remote_sha` branch alongside the merge-base one.
    """
    src = _hook_source()
    assert 'RANGE_FROM="$remote_sha"' not in src, (
        "RANGE_FROM=$remote_sha is back: for a branch that merged origin/main, "
        "$remote_sha..$local_sha spans every commit main gained since the last "
        "push, so MAIN's files get attributed to this push"
    )


def test_merge_base_range_excludes_mains_files_while_remote_sha_range_does_not(
    tmp_path: Path,
) -> None:
    """The git-level REASON, proved on a real repo rather than asserted in prose.

    Reproduces the exact shape: branch forks from main, main moves on, branch
    merges main in, then a push computes its range. `$remote_sha..HEAD` sees
    main's file; the merge-base range sees only the branch's own.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    # The branch forks here, and this is also what the remote already has.
    _git(repo, "branch", "feature")
    remote_sha = _git(repo, "rev-parse", "HEAD")

    # main moves on with a file that has nothing to do with the branch.
    (repo / "mains_file.txt").write_text("main moved on\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "main moves")

    # The branch adds its own file, then merges main in (conflict resolution).
    _git(repo, "checkout", "-q", "feature")
    (repo / "branch_file.txt").write_text("mine\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "branch work")
    _git(repo, "merge", "-q", "--no-edit", "main")
    local_sha = _git(repo, "rev-parse", "HEAD")

    def changed(range_from: str) -> set[str]:
        out = _git(
            repo, "diff", "--no-ext-diff", "--no-renames", "--name-only",
            range_from, local_sha,
        )
        return set(out.splitlines()) - {""}

    merge_base = _git(repo, "merge-base", "main", local_sha)

    # GUILT: the old anchor attributes main's file to this push.
    assert "mains_file.txt" in changed(remote_sha)
    # INNOCENCE: the merge-base anchor sees only what the branch contributes.
    assert changed(merge_base) == {"branch_file.txt"}
