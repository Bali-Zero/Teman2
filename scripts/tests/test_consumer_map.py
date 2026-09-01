"""Tests for scripts/consumer_map.py — enumerate live consumers of DELETED
or RENAMED files by BASENAME.

WHY (2026-08-21, PR #4459): deleting `apps/backend-rag/tests/` (an orphan
tree) went CI-red TWICE because two consumers were invisible to a search
anchored on the deleted PATH: `.github/workflows/sonarqube.yml` named the
files as `tests/...` AFTER a `cd apps/backend-rag` step, and
`apps/backend-rag/scripts/backend_stability_gate.py:41` listed
`tests/test_migrations.py` inside a Python list literal. Both guilt cases
below reproduce those exact two shapes.

Every case operates on a REAL, throwaway git repo (`tmp_path` fixture) with
REAL commits and a REAL `git diff -M` — never a synthetic/mocked target
list — per cicatrix-superscar.md #6 ("anti-hallucination blindness": build
on what you actually executed, not on a re-typed mirror of what you assume
the code does).

Run:
    cd <worktree> && python3 -m pytest scripts/tests/test_consumer_map.py -q
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "consumer_map.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed in {repo}: {result.stderr}"
    )
    return result


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    return repo


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# GUILT — the two real #4459 shapes.
# ---------------------------------------------------------------------------


def test_guilt_workflow_cd_relative_reference_is_live(tmp_path: Path) -> None:
    """A deleted file referenced by a workflow via a cd-relative path (the
    #4459 sonarqube.yml shape) must be found — LIVE, exit 1."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_migrations.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / ".github" / "workflows" / "sonarqube.yml",
        "jobs:\n  test:\n    steps:\n"
        "      - run: cd apps/backend-rag && pytest tests/test_migrations.py\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan tests tree")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "sonarqube.yml" in result.stdout
    assert "| workflow |" in result.stdout
    assert "| LIVE" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


def test_guilt_python_list_literal_reference_is_live(tmp_path: Path) -> None:
    """A deleted file listed as a bare string inside a Python list literal
    (the #4459 backend_stability_gate.py:41 shape) must be found — LIVE,
    exit 1."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_migrations.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "scripts" / "backend_stability_gate.py",
        'REQUIRED = [\n    "tests/test_migrations.py",\n]\n',
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan tests tree")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "backend_stability_gate.py" in result.stdout
    assert "| python |" in result.stdout
    assert "| LIVE" in result.stdout


def test_guilt_two_targets_one_live_one_clean_reports_only_the_live_one(
    tmp_path: Path,
) -> None:
    """Sanity check on multi-target aggregation: deleting two files where
    only one has a real consumer must still exit 1, and the count must
    reflect exactly the live one."""
    repo = _init_repo(tmp_path)
    referenced = repo / "apps" / "backend-rag" / "tests" / "test_ref.py"
    orphan = repo / "apps" / "backend-rag" / "tests" / "test_orphan_clean.py"
    _write(referenced, "def test_x(): pass\n")
    _write(orphan, "def test_y(): pass\n")
    _write(
        repo / "Makefile",
        "test:\n\tpytest apps/backend-rag/tests/test_ref.py\n",
    )
    base = _commit_all(repo, "base")

    referenced.unlink()
    orphan.unlink()
    _commit_all(repo, "delete both")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "test_ref.py" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


# ---------------------------------------------------------------------------
# INNOCENCE
# ---------------------------------------------------------------------------


def test_innocence_rename_consumer_already_repointed(tmp_path: Path) -> None:
    """A RENAME whose only consumer already references the NEW path must
    exit 0 — the consumer is not stale, it never pointed at the old path in
    the surviving diff."""
    repo = _init_repo(tmp_path)
    old_dir = repo / "apps" / "backend-rag" / "tests"
    new_dir = repo / "apps" / "backend-rag" / "backend" / "tests"
    old_file = old_dir / "test_migrations.py"
    _write(old_file, "def test_x(): pass\n")
    _write(
        repo / ".github" / "workflows" / "tests.yml",
        "jobs:\n  test:\n    steps:\n"
        "      - run: pytest apps/backend-rag/backend/tests/test_migrations.py\n",
    )
    base = _commit_all(repo, "base")

    new_dir.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", str(old_file.relative_to(repo)), str((new_dir / "test_migrations.py").relative_to(repo)))
    _git(repo, "commit", "-q", "-m", "move test into backend/tests")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_docs_only_mention_is_not_a_finding(tmp_path: Path) -> None:
    """A hit that lives only in a `.md` file is reported as docs-mention,
    never counted as LIVE, and must not fail the push."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_orphan.py"
    _write(target, "def test_x(): pass\n")
    _write(repo / "docs" / "notes.md", "See test_orphan.py for context.\n")
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "docs-mention" in result.stdout
    assert "| LIVE" not in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


# ---------------------------------------------------------------------------
# PROSE-MENTION FILTER (2026-08-21, real-corpus replay finding): a comment
# line or a Python docstring naming the file is not a consumer of it. Real
# shapes found live in apps/backend-rag/backend/tests/integration/zantara/
# test_tier1_fallback.py:32 (comment) and apps/backend-rag/backend/tests/
# test_no_global_cwd_mutation.py:12 + scripts/tests/test_no_import_time_
# chdir_in_tests.py:11 (module docstrings), all narrating the SAME incident
# this tool's own module-docstring #4459 motivation describes.
# ---------------------------------------------------------------------------


def test_innocence_comment_line_mention_is_not_a_finding(tmp_path: Path) -> None:
    """A hit whose line, after lstrip(), starts with '#' is a comment naming
    the file, not a consumer — must be docs-mention, exit 0."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone_orphan.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "backend" / "tests" / "test_other.py",
        "# see also tests/test_gone_orphan.py for the historical incident\n"
        "def test_y(): pass\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "docs-mention" in result.stdout
    assert "| LIVE" not in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_trailing_comment_on_a_code_line_still_counts_as_live(
    tmp_path: Path,
) -> None:
    """The comment filter is WHOLE-LINE only (line must START with '#' after
    lstrip): a real code statement with a trailing end-of-line comment must
    NOT be swallowed — it still carries a real reference."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone_trailing.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "Makefile",
        'test:\n\tpytest apps/backend-rag/tests/test_gone_trailing.py  # noqa\n',
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "| LIVE" in result.stdout


def test_innocence_python_docstring_mention_is_not_a_finding(tmp_path: Path) -> None:
    """A hit that lives only inside a Python module docstring is prose, not
    a consumer — must be docs-mention, exit 0."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone_doc.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "backend" / "tests" / "test_narrator.py",
        '"""This module explains why test_gone_doc.py was retired.\n\n'
        "Historical context in prose only, no import, no string reference\n"
        'outside this docstring.\n"""\n\n'
        "def test_y(): pass\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "docs-mention" in result.stdout
    assert "| LIVE" not in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_guilt_docstring_mention_does_not_swallow_a_real_reference_in_the_same_file(
    tmp_path: Path,
) -> None:
    """Guilt tripwire (team-lead's explicit ask): the SAME file has BOTH a
    docstring mention of the basename AND a real list-literal string
    reference (the #4459 backend_stability_gate.py shape) to it — the
    docstring hit must downgrade to docs-mention, but the list-literal hit
    must stay LIVE. The docstring filter must never swallow a real
    consumer just because it lives near a prose mention in the same file."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone_both.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "scripts" / "gate_and_doc.py",
        '"""Runs REQUIRED, including test_gone_both.py, per the gate below."""\n\n'
        "REQUIRED = [\n"
        '    "tests/test_gone_both.py",\n'
        "]\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "docs-mention" in result.stdout
    assert "| LIVE" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


def test_innocence_unparseable_python_fails_closed_to_live(tmp_path: Path) -> None:
    """A .py consuming file that does not parse (syntax error) must fail
    CLOSED: the docstring filter is skipped for it, the hit stays LIVE, and
    a note is printed — never silently trusted as prose."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone_syntax.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "backend" / "broken.py",
        "def not valid python syntax here test_gone_syntax.py (\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "| LIVE" in result.stdout
    assert "could not read/parse" in result.stderr or "could not read/parse" in result.stdout


def test_innocence_no_deleted_or_renamed_files_is_clean(tmp_path: Path) -> None:
    """A push that only ADDS/MODIFIES files (nothing deleted or renamed)
    must be a trivial clean pass — this is the common case, most pushes."""
    repo = _init_repo(tmp_path)
    _write(repo / "README.md", "hello\n")
    base = _commit_all(repo, "base")
    _write(repo / "README.md", "hello world\n")
    _commit_all(repo, "modify only")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_excluded_tree_research_is_not_reported_even_as_docs_mention(
    tmp_path: Path,
) -> None:
    """research/** is excluded outright — not even surfaced as a
    docs-mention row — per the ad-hoc/non-authoritative status CLAUDE.md
    §15 gives that tree."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone.py"
    _write(target, "def test_x(): pass\n")
    _write(repo / "research" / "ops" / "note.md", "test_gone.py was mentioned here\n")
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "research" not in result.stdout


# ---------------------------------------------------------------------------
# Common-basename skip
# ---------------------------------------------------------------------------


def test_common_basename_skipped_by_default_with_a_note(tmp_path: Path) -> None:
    """conftest.py is common enough that a bare-basename search is noise —
    skipped by default, reported with a note, never blocks the push."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "conftest.py"
    _write(target, "import pytest\n")
    _write(
        repo / "apps" / "other" / "tests" / "runner.sh",
        "#!/bin/sh\ncat conftest.py\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete conftest")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIPPED-common-basename" in result.stdout


def test_common_basename_include_common_forces_the_scan(tmp_path: Path) -> None:
    """--include-common must force the same scenario above to find the real
    (over-matching, by design) hit."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "conftest.py"
    _write(target, "import pytest\n")
    _write(
        repo / "apps" / "other" / "tests" / "runner.sh",
        "#!/bin/sh\ncat conftest.py\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete conftest")

    result = _run(repo, "--base", base, "--include-common")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "runner.sh" in result.stdout


def test_nextjs_convention_basename_skipped_by_default(tmp_path: Path) -> None:
    """page.tsx (2026-08-21, PR #4344): deleting one app's page.tsx must not
    flag every OTHER app's unrelated page.tsx of the same convention name —
    same noise class as conftest.py, just framework convention instead of
    test convention."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "mouth" / "src" / "app" / "visa" / "voa" / "page.tsx"
    _write(target, "export default function Page() { return null }\n")
    _write(
        repo / "apps" / "kbli-navigator" / "src" / "app" / "page.tsx",
        "export default function Page() { return null }\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete voa page.tsx")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIPPED-common-basename" in result.stdout


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_explicit_paths_mode_bypasses_git_diff(tmp_path: Path) -> None:
    """Positional paths are treated as the deleted-file set directly,
    without computing a git diff at all."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_x.py"
    _write(target, "def test_x(): pass\n")
    _write(repo / "Makefile", "test:\n\tpytest apps/backend-rag/tests/test_x.py\n")
    _commit_all(repo, "base")
    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "apps/backend-rag/tests/test_x.py")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Makefile" in result.stdout


def test_usage_error_bad_base_ref_exits_2(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo / "README.md", "hello\n")
    _commit_all(repo, "base")

    result = _run(repo, "--base", "definitely-not-a-real-ref-xyz")
    assert result.returncode == 2, result.stdout + result.stderr


def test_help_exits_0_and_mentions_the_overmatch_proxy_warning() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "over-match" in result.stdout.lower() or "overmatch" in result.stdout.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


# --- RENAME SAFETY by segments (2026-08-31) ---------------------------------
# Measured on PR #5331, the scar-corpus move: the guard reported 72 live
# consumers of the moved files and ALL SIX of the code files among them were
# already correctly repointed — every one of them building the destination from
# path SEGMENTS, so the literal new path appeared nowhere on the line. A guard
# that fires on every correctly-repointed consumer of a MOVE, which is the change
# class it exists to protect, teaches its readers to reach for the kill switch.


def test_innocence_rename_consumer_repointed_with_PATH_SEGMENTS(tmp_path: Path) -> None:
    """`REPO_ROOT / "docs" / "scars" / "name.md"` is a repoint. It never contains
    the literal new path, and almost nothing in this repo writes one."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "archive_scars.py",
        'from pathlib import Path\n'
        'REPO_ROOT = Path(__file__).resolve().parent.parent\n'
        'ACTIVE = REPO_ROOT / "docs" / "scars" / "cicatrix-scars.md"\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_rename_consumer_repointed_with_os_path_join(tmp_path: Path) -> None:
    """The same repoint spelled the other idiomatic way."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "read_scars.py",
        'import os\n'
        'ROOT = os.path.dirname(os.path.dirname(__file__))\n'
        'F = os.path.join(ROOT, "docs", "scars", "cicatrix-scars.md")\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_guilt_a_consumer_still_naming_the_OLD_path_still_blocks(tmp_path: Path) -> None:
    """THE COLLEAGUE TEST. Loosening rename-safety must not stop it catching the
    thing it exists for: a consumer that genuinely still opens the old location.
    Without this, 'segments in order' could be satisfied by any line at all."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "stale_reader.py",
        'from pathlib import Path\n'
        'ACTIVE = Path(".claude") / "rules" / "cicatrix-scars.md"\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "scripts/stale_reader.py" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


def test_guilt_segments_OUT_OF_ORDER_do_not_count_as_a_repoint(tmp_path: Path) -> None:
    """The ordered test is what keeps this from being a bag of words. A line
    holding the right words in the wrong order names no destination, and
    accepting it would be the under-match twin this cure would otherwise create
    (W94: a fix for an over-match births its opposite unless the corpus covers
    composition)."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "wordy.py",
        'NAME = "cicatrix-scars.md"\n'
        'PARTS = ["scars", "docs"]        # right words, wrong order\n'
        'ACTIVE = open(".claude/rules/" + NAME)\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "scripts/wordy.py" in result.stdout


# ---------------------------------------------------------------------------
# BARE-BASENAME FILTER (ledger row opened 2026-08-31, "63 falsi" — the class
# PR #5373 named and deliberately left uncured). Measured on the real
# scar-corpus move (#5331): 73 LIVE before this filter, 24 after (49
# downgraded) — see scripts/consumer_map.py's own module docstring for the
# breakdown of what the remaining 24 are.
# ---------------------------------------------------------------------------


def test_innocence_bare_basename_in_tuple_joined_to_repointed_dir_is_not_live(
    tmp_path: Path,
) -> None:
    """LEDGER row 1747 innocence case, verbatim: 'a basename in a tuple
    joined to a repointed directory constant must not' count as stale. The
    real scripts/scar_query.py `CORPUS_FILES = (...)` shape — the tuple line
    itself names no location, so it cannot be pointing at the OLD one
    either."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "scar_query.py",
        'from pathlib import Path\n'
        'NEW_DIR = Path(__file__).resolve().parent.parent / "docs" / "scars"\n'
        'CORPUS_FILES = ("cicatrix-scars.md", "cicatrix-scars-archive.md")\n'
        'FULL = [NEW_DIR / f for f in CORPUS_FILES]\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout
    assert "bare-basename" in result.stdout


def test_guilt_basename_built_from_an_OLD_dir_constant_on_another_line_still_blocks(
    tmp_path: Path,
) -> None:
    """LEDGER row 1747 guilt case, verbatim: 'a consumer that builds the old
    path across two lines must STILL block.' The directory constant
    (`OLD_DIR`) is defined on an earlier line, but the hit's OWN line still
    carries a `/` operator right before the basename — the bare-basename
    filter must not touch a hit it cannot itself verify as already
    repointed; it stays on the safe (still-LIVE) side."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "stale_reader_two_line.py",
        'from pathlib import Path\n'
        'OLD_DIR = Path(".claude") / "rules"\n'
        'LEGACY = OLD_DIR / "cicatrix-scars.md"\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "scripts/stale_reader_two_line.py" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


def test_guilt_basename_as_tail_of_a_literal_path_string_still_blocks(
    tmp_path: Path,
) -> None:
    """A basename that is the TAIL of one longer literal path string (the
    `/` sits INSIDE the same quotes, not as a separate pathlib operator)
    must still be caught — the real
    scripts/tests/test_injected_surface_attest.py shape
    (`"**/.claude" + "/rules/cicatrix-scars.md"`)."""
    repo = _init_repo(tmp_path)
    _write(repo / ".claude" / "rules" / "cicatrix-scars.md", "# scars\n")
    _write(
        repo / "scripts" / "excluded_globs.py",
        'excluded = "**/.claude" + "/rules/cicatrix-scars.md"\n',
    )
    base = _commit_all(repo, "base")

    (repo / "docs" / "scars").mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", ".claude/rules/cicatrix-scars.md", "docs/scars/cicatrix-scars.md")
    _git(repo, "commit", "-q", "-m", "move the scar corpus")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "scripts/excluded_globs.py" in result.stdout


def test_innocence_bare_basename_as_dict_value_on_delete_target_is_not_live(
    tmp_path: Path,
) -> None:
    """The filter applies to plain DELETEs too, not only renames — a
    mapping value naming a deleted file's bare basename is data, not a
    location."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_orphan.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "scripts" / "registry.py",
        'KNOWN = {"orphan": "test_orphan.py"}\n',
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan test")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout
    assert "bare-basename" in result.stdout


def test_innocence_bare_basename_as_written_header_string_is_not_live(
    tmp_path: Path,
) -> None:
    """The real scripts/archive_cicatrix_scars.py shape: a header string
    being WRITTEN (`f.write("# cicatrix-scars-archive.md\\n\\n")`) names the
    file in the CONTENT it produces, not a location it opens."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_archive.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "scripts" / "archiver.py",
        'def write_header(f):\n'
        '    f.write("# test_archive.py\\n\\n")\n',
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan test")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout
    assert "bare-basename" in result.stdout


def test_innocence_python_bare_stem_import_reference_unaffected_by_bare_basename_filter(
    tmp_path: Path,
) -> None:
    """The bare-basename filter must never apply to a `.py` target's bare
    import-stem search — `import test_migrations` never contains
    `test_migrations.py` at all, so "directory-adjacent" is not a
    meaningful question on that hit and must not downgrade a real import
    dependency."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_migrations.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "importer.py",
        "from apps.backend_rag.tests import test_migrations\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan tests tree")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "importer.py" in result.stdout
    assert "| LIVE" in result.stdout
