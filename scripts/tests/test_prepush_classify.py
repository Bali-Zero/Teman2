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
    suffix scoping) was REMOVED entirely. Directory rules remain suffix-
    scoped; exact files use equality in ALLOWLIST_EXACT_PATHS. This test
    asserts that no leftover bare-prefix list can reintroduce extension-
    blindness, plus the original directory prefix/suffix hygiene checks."""
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


def test_innocence_scripts_tests_shell_script_now_skips_v7() -> None:
    """v7: scripts/tests/ widened from .py-only (v3) to .py AND .sh. This is
    the same real file the pre-v7 guilt test used
    (test_guilt_scripts_tests_shell_script_suffix_mismatch), now moved to
    innocence because the rule it demonstrated changed — a basename-only
    grep for all 17 real .sh files in this directory across
    apps/backend-rag/backend/ found zero hits, same structurally-unreachable
    argument v3 already established for the .py files here."""
    verdict, unknown = pc.classify(["scripts/tests/test_prepush_failclosed.sh"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


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


# ===========================================================================
# v6 — the root `.gitignore` (exact) and infra/home-fork (.json)
#
# Found by REPLAY rather than by being bitten: all 3458 non-merge commits of
# the last 90 days had their file lists classified twice, once against v5 and
# once against v5+these two entries, counting only verdict FLIPS full->skip.
# 813 already skipped, 2465 correctly stay full, exactly 24 flip — 15 of them
# on `.gitignore`, 10 on infra/home-fork, one commit (2b5d2b915e) on both.
#
# The lists asserted below are the REAL file lists of flipped commits, not
# hand-authored plausible ones. `f1254477cb` is the extreme case: 19 files of
# pure launchd config plus one JSON declaration, paying a full ~17k-test
# backend suite.
#
# The `.gitignore` entry is deliberately root-EXACT, never by basename: 22
# `.gitignore` files are tracked repo-wide and one of them lives at
# `apps/backend-rag/backend/data/.gitignore`, INSIDE the tree whose tests the
# skip would spare. Guilt+innocence for exactly that distinction below —
# without the guilt half, a "tidying" edit to a basename rule would look
# green.
# ===========================================================================


def test_innocence_root_gitignore_skips() -> None:
    """10 of the 24 replayed flips are literally this one-file diff."""
    verdict, unknown = pc.classify([".gitignore"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_root_gitignore_descendant_forces_full() -> None:
    """A file-shaped exact rule must not become a directory-prefix rule."""
    path = ".gitignore/probe.gitignore"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_innocence_home_fork_declared_pairs_skips() -> None:
    """The HOME-fork guard's pair registry (superscar #1) — the only tracked
    file under infra/home-fork/ today, 31 commits in its lifetime."""
    verdict, unknown = pc.classify(["infra/home-fork/declared-pairs.json"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_real_v6_replay_flips_skip() -> None:
    """Four REAL flipped commits from the 90-day replay, verbatim file lists.

    Each of these paid a full backend suite for a diff containing zero
    Python and zero backend files.
    """
    real_flips = {
        # f1254477cb — 19 files: launchd canon reconcile.
        "f1254477cb": [
            "infra/home-fork/declared-pairs.json",
            "infra/launchagents/com.balizero.codex-spalla-calibrate.plist",
            "infra/launchagents/com.nuzantara.merge-train.plist",
            "infra/launchagents/wrappers/fly-pg-proxy-wrapper.sh",
            "infra/launchagents/wrappers/wa-media-pull-run.sh",
        ],
        # 17eed8ebbd — .gitignore riding along with a research capture.
        "17eed8ebbd": [
            ".gitignore",
            "research/visa/2026-06-01-c5a-local-ban-sources.md",
        ],
        # b2f7264824 — .gitignore plus one LaunchAgent plist.
        "b2f7264824": [
            ".gitignore",
            "infra/launchagents/com.balizero.wr2.html-apply.plist",
        ],
        # 70db573245 — the ledger plus the pair declaration.
        "70db573245": [
            ".claude/skills/modus/PENDING-ARMS.md",
            "infra/home-fork/declared-pairs.json",
        ],
    }
    for sha, files in real_flips.items():
        verdict, unknown = pc.classify(files)
        assert verdict == pc.VERDICT_SKIP, f"{sha} should skip, got {verdict} ({unknown})"
        assert unknown == []


def test_innocence_both_v6_entries_in_one_diff_skip() -> None:
    """COMPOSITION, not just each entry alone.

    Ported from the stranded `99-allowlist-v6-gitignore-homefork` branch,
    which reached the same two-entry design independently — this was the one
    case its corpus had that the replay-driven corpus here did not. W94's
    lesson: a corpus that tests each rule in isolation misses the shape where
    two of them have to agree, and commit 2b5d2b915e is exactly that shape
    (both entries in one diff).
    """
    verdict, unknown = pc.classify([".gitignore", "infra/home-fork/declared-pairs.json"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_nested_gitignore_under_backend_forces_full() -> None:
    """THE load-bearing guilt test for v6.

    `apps/backend-rag/backend/data/.gitignore` is a real tracked file
    (verified on disk). A basename-shaped rule would have admitted it — i.e.
    a file inside the backend tree would have authorised skipping the backend
    tests. The root-exact entry must not.
    """
    path = "apps/backend-rag/backend/data/.gitignore"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL, "a .gitignore INSIDE the backend tree must force full"
    assert unknown == [path]


def test_guilt_non_root_gitignore_anywhere_forces_full() -> None:
    """The same rule outside the backend tree: nested `.gitignore` files are
    not admitted either. 22 are tracked; only the root one is allowlisted, so
    this is the general case and the test above is its worst instance."""
    for path in (
        "apps/mouth/.gitignore",
        "apps/backend-rag/.gitignore",
        "packages/core/.gitignore",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_gitignore_lookalike_names_force_full() -> None:
    """The `(".gitignore", (".gitignore",))` shape must match the FILE, not
    names that merely start with it — the prefix test admits only equality or
    a `.gitignore/` DIRECTORY, and the suffix test only the exact name."""
    for path in (
        ".gitignore.bak",
        ".gitignore-old",
        ".gitignoreignore",
        ".gitignore.save/.gitignore",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_home_fork_non_json_forces_full() -> None:
    """Suffix scoping is the mechanism: a future .py helper or .md note in
    infra/home-fork/ must not inherit a blessing measured on a JSON data
    file."""
    for path in (
        "infra/home-fork/sync.py",
        "infra/home-fork/README.md",
        "infra/home-fork/realign.sh",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_home_fork_lookalike_prefix_forces_full() -> None:
    """Directory-boundary anchoring: `infra/home-fork-legacy/x.json` starts
    with the prefix as a STRING but is a different directory."""
    for path in (
        "infra/home-fork-legacy/old.json",
        "infra/home-forked/pairs.json",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_v6_entries_mixed_with_backend_force_full() -> None:
    """Unanimity is unchanged: one backend file in the diff still forces the
    full suite, alongside either new entry."""
    backend = "apps/backend-rag/backend/services/rag/reasoning.py"
    for extra in (".gitignore", "infra/home-fork/declared-pairs.json"):
        verdict, unknown = pc.classify([extra, backend])
        assert verdict == pc.VERDICT_FULL
        assert unknown == [backend]


def test_allowlist_version_bumped_to_6_for_the_v6_entries() -> None:
    """The skip-banner logs the version that approved a skip; a rules change
    without a bump makes the log line unattributable."""
    assert pc.ALLOWLIST_VERSION >= 6
    assert ".gitignore" in pc.ALLOWLIST_EXACT_PATHS
    assert (".gitignore", (".gitignore",)) not in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    assert ("infra/home-fork", (".json",)) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS


def test_edge_exact_file_rules_use_dedicated_exact_path_set() -> None:
    """File-shaped rules must never share directory-prefix semantics."""
    expected = {
        ".gitignore",
        "apps/wa-mirror/package.json",
        "apps/wa-mirror/package-lock.json",
        "apps/organism/organism/organs_registry.yaml",
    }
    assert pc.ALLOWLIST_EXACT_PATHS == expected
    assert expected.isdisjoint(prefix for prefix, _ in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS)


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


# ---------------------------------------------------------------------------
# The REASON LABEL (added 2026-07-27, then separated by rule shape in v8).
#
# The old shared matcher covered both exact files and directory descendants.
# Its reason string originally rendered `<prefix>/**` for BOTH — so the v6
# root-exact entry printed `.gitignore/** (.gitignore)`, naming a directory
# rule the allowlist did not intend. v8 makes the model explicit: exact files
# live in ALLOWLIST_EXACT_PATHS and directory rules live in
# ALLOWLIST_PREFIX_SUFFIX_PAIRS.
#
# Why this is worth pinning rather than shrugging at: the message is the
# only thing a human reads when asking "why was my suite skipped / why was
# it NOT skipped?". A reader who takes `.gitignore/**` at face value
# concludes the rule is directory-shaped and reasons wrongly about whether
# `apps/backend-rag/backend/data/.gitignore` skips (it must NOT — that
# guilt case is what makes root-exact the safe shape). Same defect class as
# W106: the verdict was right and the DIAGNOSIS was anchored to the wrong
# thing, and the diagnosis is what the next reader acts on.
#
# The label tests below ensure diagnostics still identify the rule shape;
# the descendant guilt tests separately pin the v8 path-boundary verdict.
# ---------------------------------------------------------------------------


def test_label_exact_match_entry_does_not_invent_a_directory() -> None:
    """GUILT on the old label: the root `.gitignore` entry must NOT render as
    `.gitignore/**`, which describes a directory rule this table has never
    had."""
    reason = pc._innocent_reason(".gitignore")
    assert reason is not None, "root .gitignore must still be innocent"
    assert "/**" not in reason, (
        f"exact-match entry rendered a directory glob: {reason!r} — this is the "
        "misleading form the label fix exists to remove"
    )
    assert reason == ".gitignore (exact match)"


def test_label_directory_entry_still_renders_the_glob() -> None:
    """INNOCENCE: the fix must not swing the other way and strip `/**` from
    entries that genuinely ARE directory-scoped."""
    reason = pc._innocent_reason("infra/home-fork/declared-pairs.json")
    assert reason is not None
    assert reason == "infra/home-fork/** (.json)"


def test_label_change_moved_no_verdict_for_either_v6_class() -> None:
    """The label branch must be provably cosmetic: both v6 classes still SKIP,
    alone and together, and the load-bearing nested-.gitignore guilt case
    still forces FULL. If a label edit ever changes one of these, the edit
    was not cosmetic."""
    for files in (
        [".gitignore"],
        ["infra/home-fork/declared-pairs.json"],
        [".gitignore", "infra/home-fork/declared-pairs.json"],
    ):
        verdict, unknown = pc.classify(files)
        assert verdict == pc.VERDICT_SKIP, f"{files} should skip, got {verdict}"
        assert unknown == []

    for files in (
        ["apps/backend-rag/backend/data/.gitignore"],
        ["apps/mouth/.gitignore"],
        ["x.gitignore"],
        ["infra/home-fork/README.md"],
        ["infra/home-fork-extra/declared-pairs.json"],
    ):
        verdict, _ = pc.classify(files)
        assert verdict == pc.VERDICT_FULL, f"{files} should force full, got {verdict}"


def test_label_every_allowlist_entry_gets_a_reason_naming_its_own_prefix() -> None:
    """Sweep the WHOLE directory table rather than only one entry (the
    SYMMETRY clause from the fly-backup scar: a fix that covers only the case
    that bit you is half a fix). For each entry, a representative matching
    descendant must produce a reason that names that entry's prefix."""
    for prefix, suffixes in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS:
        suffix = suffixes[0]
        sample = f"{prefix}/probe{suffix}"
        reason = pc._innocent_reason(sample)
        if reason is None:
            # A NEVER_INNOCENT_* net legitimately outranks the table for some
            # samples; that is a different rule, not a label defect.
            continue
        assert prefix in reason, f"reason {reason!r} does not name its prefix {prefix!r}"
        assert "/**" in reason, f"directory entry {prefix!r} lost its glob: {reason!r}"


# ===========================================================================
# v7 (2026-08-10) — round-3 queue-acceleration replay of 60 recently-merged
# PRs found ~28 avoidable FULL suites/week from paths that are innocent but
# not yet listed. Four new allowlist entries + one NEVER_INNOCENT_EXACT_PATHS
# addition, each independently innocence-verified against
# apps/backend-rag/backend/ (see the module docstring's "v7" section for the
# full method per entry). Also: `scripts` (.md), `apps/wa-mirror/package.json`,
# `apps/wa-mirror/package-lock.json`, `apps/organism/organism/
# organs_registry.yaml`, and the scripts/tests widening to `.sh` above.
# ===========================================================================


def test_innocence_scripts_md_root_and_nested_skip() -> None:
    """The shapes this entry exists for: a root-level scripts/*.md doc and a
    nested one (including scripts/tests/fixtures/, verified to contain only
    .md — the same directory this PR also widened for .sh)."""
    for path in (
        "scripts/AGENTS.md",
        "scripts/nuzantara_system_context.md",
        "scripts/harness/README.md",
        "scripts/tests/fixtures/docs_audit/README.md",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_SKIP, f"{path} should skip, got {verdict}"
        assert unknown == []


def test_guilt_scripts_md_lookalike_prefix_forces_full() -> None:
    """#3's recurring disease: a prefix check without a boundary anchor
    over-matches. `scriptsarchive` is not `scripts`."""
    verdict, unknown = pc.classify(["scriptsarchive/experiment/foo.md"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scriptsarchive/experiment/foo.md"]


def test_guilt_scripts_non_md_suffix_still_forces_full() -> None:
    """Suffix scoping is the mechanism — a .json or .py under scripts/ is not
    admitted just because its directory now has an .md rule."""
    for path in (
        "scripts/agent_start.py",
        "scripts/ci/telegram_verdict.sh",  # already innocent via scripts/ci, unaffected
    ):
        verdict, unknown = pc.classify([path])
        # scripts/ci/telegram_verdict.sh is innocent via the PRE-EXISTING
        # scripts/ci (.sh) rule, not the new .md one — sanity that the new
        # entry did not somehow break the old one.
        if path.endswith(".sh"):
            assert verdict == pc.VERDICT_SKIP
        else:
            assert verdict == pc.VERDICT_FULL
            assert unknown == [path]


def test_guilt_root_scripts_shell_script_still_forces_full_v7() -> None:
    """v7 investigated widening to a blanket scripts (.sh) entry covering
    root-level scripts/*.sh, and REJECTED it: a real backend test reads a
    root-level script's content and asserts on it —
    test_openclaw_whatsapp_bridge_script.py::test_run_script_uses_installed_bridge_app_dir
    read_text()s scripts/run_openclaw_whatsapp_bridge.sh and checks two
    substrings. Root-level scripts/*.sh (outside scripts/ci/ and
    scripts/tests/, both separately allowlisted) must keep forcing full."""
    verdict, unknown = pc.classify(["scripts/run_openclaw_whatsapp_bridge.sh"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["scripts/run_openclaw_whatsapp_bridge.sh"]

    verdict2, unknown2 = pc.classify(["scripts/pg.sh"])
    assert verdict2 == pc.VERDICT_FULL
    assert unknown2 == ["scripts/pg.sh"]


def test_innocence_wa_mirror_package_files_skip() -> None:
    verdict, unknown = pc.classify(["apps/wa-mirror/package.json"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []

    verdict, unknown = pc.classify(["apps/wa-mirror/package-lock.json"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []

    verdict, unknown = pc.classify(
        ["apps/wa-mirror/package.json", "apps/wa-mirror/package-lock.json"]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_wa_mirror_package_json_descendant_forces_full() -> None:
    """The exact package manifest rule must not bless descendants."""
    path = "apps/wa-mirror/package.json/probe.json"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_wa_mirror_package_lock_json_descendant_forces_full() -> None:
    """The exact lockfile rule must not bless descendants."""
    path = "apps/wa-mirror/package-lock.json/probe.json"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_wa_mirror_tree_outside_the_two_exact_files_forces_full() -> None:
    """The wa-mirror allowlist is TWO exact files, not the tree. Any other
    file under apps/wa-mirror/ — including a same-directory sibling that
    merely shares the .json suffix — must still force full."""
    for path in (
        "apps/wa-mirror/src/bridge/index.ts",
        "apps/wa-mirror/tsconfig.json",
        "apps/wa-mirror/other-package.json",
        "apps/wa-mirror/package.json.bak",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_wa_mirror_mixed_with_backend_forces_full() -> None:
    verdict, unknown = pc.classify(
        [
            "apps/wa-mirror/package.json",
            "apps/backend-rag/backend/services/rag/reasoning.py",
        ]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/services/rag/reasoning.py"]


def test_innocence_organs_registry_yaml_skips() -> None:
    verdict, unknown = pc.classify(["apps/organism/organism/organs_registry.yaml"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_organs_registry_yaml_descendant_forces_full() -> None:
    """The exact registry rule must not bless a file-shaped directory."""
    path = "apps/organism/organism/organs_registry.yaml/probe.yaml"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_organs_registry_lookalikes_force_full() -> None:
    """Root-EXACT: a sibling file in the SAME directory, a wrong extension on
    the SAME basename, and a shallower nesting of the SAME basename must all
    still force full — the rule matches one literal path, not a directory or
    a basename."""
    for path in (
        "apps/organism/organism/other_registry.yaml",
        "apps/organism/organism/organs_registry.yml",
        "apps/organism/organs_registry.yaml",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must force full"
        assert unknown == [path]


def test_guilt_organs_registry_mixed_with_backend_forces_full() -> None:
    verdict, unknown = pc.classify(
        [
            "apps/organism/organism/organs_registry.yaml",
            "apps/backend-rag/backend/services/rag/reasoning.py",
        ]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/services/rag/reasoning.py"]


def test_guilt_pre_commit_hook_self_edit() -> None:
    """.husky/pre-commit is the sibling hook to .husky/pre-push — same class
    (mandate 'paranoia'): a git hook whose own logic must never silently skip
    the local verification it enforces."""
    verdict, unknown = pc.classify([".husky/pre-commit"])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [".husky/pre-commit"]


def test_label_exact_match_wa_mirror_and_organs_registry_do_not_invent_a_directory() -> None:
    """Same label discipline as the v6 .gitignore fix: a root-EXACT entry
    must render '(exact match)', never a directory glob."""
    for path in (
        "apps/wa-mirror/package.json",
        "apps/wa-mirror/package-lock.json",
        "apps/organism/organism/organs_registry.yaml",
    ):
        reason = pc._innocent_reason(path)
        assert reason is not None
        assert reason == f"{path} (exact match)"


def test_allowlist_version_bumped_to_8_for_the_exact_path_fix() -> None:
    """The skip-banner logs the version that approved a skip; a rules change
    without a bump makes the log line unattributable."""
    assert pc.ALLOWLIST_VERSION >= 8
    assert ("scripts/tests", (".py", ".sh")) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    assert ("scripts", (".md",)) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    assert "apps/wa-mirror/package.json" in pc.ALLOWLIST_EXACT_PATHS
    assert "apps/wa-mirror/package-lock.json" in pc.ALLOWLIST_EXACT_PATHS
    assert "apps/organism/organism/organs_registry.yaml" in pc.ALLOWLIST_EXACT_PATHS
    assert ".husky/pre-commit" in pc.NEVER_INNOCENT_EXACT_PATHS


# ===========================================================================
# v9 (2026-08-11) — `.txt` under docs/** and research/**, plus the
# requirements-family basename net.
#
# The trigger was measured, not imagined: PR #4002's three files (one
# research `.md`, two verbatim refutation transcripts `.txt`) forced `full`
# and then lost TWO 75-minute lock waits to timeout before landing on a
# third attempt. Innocence for the suffix was measured on disk — 11 tracked
# `.txt` under research/, 25 under docs/, none mode-100755, and no test in
# apps/backend-rag/backend/tests/ opens one.
#
# The guilt half is deliberately HYPOTHETICAL where it matters. No allowlist
# prefix reaches apps/backend-rag/ today, so a guilt test written against
# today's tree would pass with the basename net deleted. The one below puts
# a requirements manifest INSIDE an allowlisted prefix — the exact shape a
# future broadening would create — so it fails if the net is removed.
# ===========================================================================


def test_innocence_research_txt_transcript_skips() -> None:
    """The literal file that started v9 — a verbatim refuter transcript."""
    verdict, unknown = pc.classify(
        ["research/operations/refutations/2026-08-10-mergeos-v2-codex-sol.txt"]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_pr_4002_real_diff_skips() -> None:
    """PR #4002's ACTUAL three-file diff, verbatim.

    Under v8 this returned `full` and paid two 75-minute lock timeouts. The
    regression this pins is the whole reason v9 exists — assert the real
    file list, not a hand-made stand-in.
    """
    verdict, unknown = pc.classify(
        [
            "research/operations/2026-08-10-merge-os-v2-submission-system.md",
            "research/operations/refutations/2026-08-10-mergeos-v2-agy-gemini.txt",
            "research/operations/refutations/2026-08-10-mergeos-v2-codex-sol.txt",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_innocence_docs_txt_skips() -> None:
    """SYMMETRY (W101-recidiva): docs/** and research/** are one class. A
    fix that only covers the tree that bit us is half a fix."""
    verdict, unknown = pc.classify(["docs/notes/scratch.txt"])
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_requirements_family_under_an_allowlisted_prefix_forces_full() -> None:
    """THE load-bearing guilt test for v9.

    Delete the requirements entries from NEVER_INNOCENT_BASENAMES and this
    is the only BEHAVIOURAL test that goes red — measured, not asserted:
    the mutation kills exactly this test plus
    test_allowlist_version_bumped_to_9, and that one asserts the constant
    rather than the behaviour. The paths are hypothetical ON PURPOSE — the
    real manifests live at apps/backend-rag/, which no prefix reaches
    today, so asserting the real tree would prove nothing about the net
    (W98 is the scar that makes the net worth having).
    """
    for path in (
        "docs/requirements.txt",
        "research/requirements.txt",
        "docs/requirements.lock.txt",
        "research/requirements-prod.txt",
        "docs/requirements-prod.lock.txt",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must never read as innocent"
        assert unknown == [path]


def test_guilt_real_requirements_manifests_still_force_full() -> None:
    """The manifests as they actually live today (read by the W98 tripwire
    test_lock_honors_requirements.py) — unchanged by v9."""
    for path in (
        "apps/backend-rag/requirements.txt",
        "apps/backend-rag/requirements.lock.txt",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL
        assert unknown == [path]


def test_guilt_txt_outside_docs_and_research_forces_full() -> None:
    """v9 widened exactly two prefixes. `.txt` is not innocent by extension
    anywhere else — least of all inside the tree whose tests get skipped."""
    for path in (
        "apps/backend-rag/backend/data/seed.txt",
        "scripts/notes.txt",
        "notes.txt",
        ".claude/skills/modus/notes.txt",
    ):
        verdict, unknown = pc.classify([path])
        assert verdict == pc.VERDICT_FULL, f"{path} must not be innocent"
        assert unknown == [path]


def test_guilt_research_txt_mixed_with_backend_forces_full() -> None:
    """Composition: one innocent transcript does not launder a backend file."""
    verdict, unknown = pc.classify(
        [
            "research/operations/refutations/2026-08-10-mergeos-v2-codex-sol.txt",
            "apps/backend-rag/backend/services/rag/reasoning.py",
        ]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/services/rag/reasoning.py"]


def test_guilt_traversal_out_of_research_with_txt_forces_full() -> None:
    """HARDENING-2 still holds for the newly-admitted suffix."""
    path = "research/../apps/backend-rag/backend/x.txt"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_allowlist_version_bumped_to_9_for_the_txt_entries() -> None:
    """The skip-banner logs the version that approved a skip; a rules change
    without a bump makes the log line unattributable."""
    assert pc.ALLOWLIST_VERSION >= 9
    assert ("docs", (".md", ".txt")) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    assert ("research", (".md", ".txt")) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    for name in (
        "requirements.txt",
        "requirements.lock.txt",
        "requirements-prod.txt",
        "requirements-prod.lock.txt",
    ):
        assert name in pc.NEVER_INNOCENT_BASENAMES


def test_edge_v9_added_no_second_allowlist_mechanism() -> None:
    """v9 widened existing entries and one basename set. It must not have
    introduced a third matching path (the v1 bare-prefix mistake)."""
    for _prefix, suffixes in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS:
        assert suffixes, "no bare-prefix (suffix-less) entry may exist"
        assert all(s.startswith(".") for s in suffixes)


# ===========================================================================
# v10 (2026-08-12) — infra/claude-hooks (.py) + infra/guard-conformance
# (.json), two new directory entries.
#
# Trigger: PR #4125-shaped diffs — touching only the claude-hooks
# test/guard corpus and its conformance registry — forced `full` under v9
# despite zero runtime coupling to `pytest backend/tests/` (measured: the
# only two `apps/`-tree hits for "claude-hooks" are prose, not imports; no
# conftest adds `infra/` to sys.path) and despite three CI workflows
# (guard-conformance.yml, hook-innocence-gate.yml,
# kbli-filiera-vault-compilers.yml) already running that corpus
# independently of this classifier. See the module docstring's
# "v10 EXTENSION" section for the full measurement.
# ===========================================================================


def test_innocence_real_pr_4125_file_set_skips() -> None:
    """PR #4125's actual file set, verbatim.

    Under v9 this returned `full`. `.github/workflows/guard-conformance.yml`
    and `infra/home-fork/declared-pairs.json` were ALREADY allowlisted (the
    `.github/workflows` and `infra/home-fork` entries predate v10) — the two
    new `infra/claude-hooks` (.py) and `infra/guard-conformance` (.json)
    pairs are the whole delta that flips this set to skip-backend.
    """
    verdict, unknown = pc.classify(
        [
            ".claude/skills/modus/PENDING-ARMS.md",
            ".github/workflows/guard-conformance.yml",
            "infra/claude-hooks/orchestrate_gate.py",
            "infra/claude-hooks/test_hook_innocence.py",
            "infra/claude-hooks/test_orchestrate_gate_disarm_notice.py",
            "infra/claude-hooks/test_orchestrate_gate_vocab.py",
            "infra/guard-conformance/registry.json",
            "infra/home-fork/declared-pairs.json",
        ]
    )
    assert verdict == pc.VERDICT_SKIP
    assert unknown == []


def test_guilt_claude_hooks_mixed_with_backend_forces_full() -> None:
    """Composition: one innocent claude-hooks file does not launder a real
    backend file riding along in the same push."""
    verdict, unknown = pc.classify(
        ["infra/claude-hooks/x.py", "apps/backend-rag/backend/main.py"]
    )
    assert verdict == pc.VERDICT_FULL
    assert unknown == ["apps/backend-rag/backend/main.py"]


def test_guilt_scripts_root_py_still_forces_full() -> None:
    """The v10 REJECTED widening (blanket scripts/**/*.py) stays rejected —
    infra/claude-hooks admitting .py must not spill onto root scripts/*.py,
    which the backend suite provably imports from
    (scripts.curated_qa_harvest, scripts.drive_token_watchdog, ...)."""
    path = "scripts/curated_qa_harvest.py"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_claude_hooks_wrong_suffix_forces_full() -> None:
    """Suffix scoping holds: infra/claude-hooks admits `.py` only, not
    `.sh`."""
    path = "infra/claude-hooks/run.sh"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_guard_conformance_wrong_suffix_forces_full() -> None:
    """Suffix scoping holds: infra/guard-conformance admits `.json` only,
    not `.py`."""
    path = "infra/guard-conformance/check.py"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_guilt_claude_hooks_traversal_escape_forces_full() -> None:
    """HARDENING-2 still holds for the two new v10 prefixes: `..` cannot
    escape infra/claude-hooks back onto a real backend file."""
    path = "infra/claude-hooks/../../apps/backend-rag/backend/main.py"
    verdict, unknown = pc.classify([path])
    assert verdict == pc.VERDICT_FULL
    assert unknown == [path]


def test_allowlist_version_bumped_to_10_for_the_claude_hooks_entries() -> None:
    """The skip-banner logs the version that approved a skip; a rules change
    without a bump makes the log line unattributable."""
    assert pc.ALLOWLIST_VERSION >= 10
    assert ("infra/claude-hooks", (".py",)) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS
    assert ("infra/guard-conformance", (".json",)) in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS


def test_edge_v10_added_no_second_allowlist_mechanism() -> None:
    """v10 added two suffix-scoped directory entries. It must not have
    introduced a third matching path (the v1 bare-prefix mistake)."""
    for _prefix, suffixes in pc.ALLOWLIST_PREFIX_SUFFIX_PAIRS:
        assert suffixes, "no bare-prefix (suffix-less) entry may exist"
        assert all(s.startswith(".") for s in suffixes)
