"""Tests for scripts/lint_zantara_core_edit_declared.py.

Guilt + innocence per the 2026-08-20 lesson (verifying one axis of a guard
does not license a claim about the guard): every branch below is exercised
both ways — the disease IS caught, and every adjacent legitimate shape is
NOT flagged.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_zantara_core_edit_declared.py"
_spec = importlib.util.spec_from_file_location("lint_zce", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lzce = importlib.util.module_from_spec(_spec)
# The @dataclass decorator does sys.modules[cls.__module__] in 3.11 — register
# before exec_module or the decorator crashes on a module not yet registered.
sys.modules[_spec.name] = lzce
_spec.loader.exec_module(lzce)

TARGET = lzce.TARGET_PATH


# ---------------------------------------------------------------- innocence


def test_innocence_file_not_touched_no_body():
    """Most PRs: file untouched, no PR body at all — must pass."""
    verdict = lzce.check(changed_files=["README.md", "scripts/foo.py"], pr_body=None)
    assert verdict.ok


def test_innocence_file_not_touched_hostile_body():
    """File untouched — even a PR body carrying a WELL-FORMED, line-start
    declaration (the exact shape that WOULD match if the file were touched)
    must not matter, because the guard's first predicate is the changed-file
    set, not the body. A weaker version of this test used a mid-line mention
    that would never have matched the regex regardless of predicate order —
    that proved nothing about precedence (Kimi K3 adversarial review,
    2026-08-21); this one actually exercises it."""
    verdict = lzce.check(
        changed_files=["docs/some-review.md"],
        pr_body="Zantara-Core-Edit: this PR does not touch the target file at all",
    )
    assert verdict.ok


def test_innocence_same_basename_different_path():
    """W105/W107 lesson: a same-named file living elsewhere (test fixture,
    vendored copy) must never trip an exact-path guard."""
    verdict = lzce.check(
        changed_files=["apps/backend-rag/backend/tests/fixtures/prompts/zantara_core.py"],
        pr_body=None,
    )
    assert verdict.ok


def test_innocence_declared_with_reason():
    """File touched, declaration present with a real reason — passes."""
    verdict = lzce.check(
        changed_files=[TARGET],
        pr_body="Tightens the jailbreak wording.\n\nZantara-Core-Edit: narrow overly broad override phrasing\n",
    )
    assert verdict.ok


def test_innocence_declaration_case_insensitive_and_anywhere_in_body():
    verdict = lzce.check(
        changed_files=[TARGET],
        pr_body="Some preamble.\nzantara-core-edit: lowercase still counts\nmore text after",
    )
    assert verdict.ok


def test_innocence_declaration_among_other_frontmatter_style_lines():
    """Mirrors how this repo's R1 `adversarial_review:` token sits among
    other frontmatter-style lines — must still match."""
    verdict = lzce.check(
        changed_files=[TARGET],
        pr_body="adversarial_review: kimi-k3\nZantara-Core-Edit: add non-English jailbreak phrase\nsources:\n  - internal",
    )
    assert verdict.ok


# -------------------------------------------------------------------- guilt


def test_guilt_file_touched_no_body():
    verdict = lzce.check(changed_files=[TARGET], pr_body=None)
    assert not verdict.ok
    assert TARGET in verdict.reason


def test_guilt_file_touched_empty_body():
    verdict = lzce.check(changed_files=[TARGET], pr_body="")
    assert not verdict.ok


def test_guilt_file_touched_unrelated_body():
    verdict = lzce.check(
        changed_files=[TARGET],
        pr_body="Refactors prompt sections for clarity, no functional change.",
    )
    assert not verdict.ok


def test_guilt_token_present_but_no_reason():
    """A bare token with nothing after the colon is not a declaration — it
    is indistinguishable from someone pasting the label without content."""
    verdict = lzce.check(changed_files=[TARGET], pr_body="Zantara-Core-Edit:\n")
    assert not verdict.ok


def test_guilt_token_present_but_only_whitespace_after_colon():
    verdict = lzce.check(changed_files=[TARGET], pr_body="Zantara-Core-Edit:    \n")
    assert not verdict.ok


def test_guilt_token_misspelled_does_not_count():
    verdict = lzce.check(changed_files=[TARGET], pr_body="Zantara-Core-Edited: fixed a typo")
    assert not verdict.ok


def test_guilt_literal_placeholder_copy_pasted_from_error_message():
    """Kimi K3 adversarial review, 2026-08-21: the error message itself
    suggests 'Zantara-Core-Edit: <reason>' — a lazy author who copy-pastes
    that literally satisfies a bare \\S-after-colon check without declaring
    anything. Must still fail."""
    verdict = lzce.check(changed_files=[TARGET], pr_body="Zantara-Core-Edit: <reason>")
    assert not verdict.ok


@pytest.mark.parametrize("placeholder", ["TODO", "tbd", "N/A", "...", "reason"])
def test_guilt_other_placeholder_values(placeholder):
    verdict = lzce.check(changed_files=[TARGET], pr_body=f"Zantara-Core-Edit: {placeholder}")
    assert not verdict.ok


def test_guilt_multiple_files_including_target():
    verdict = lzce.check(
        changed_files=["README.md", TARGET, "apps/backend-rag/backend/llm/prompt_manager.py"],
        pr_body="Just a docs update.",
    )
    assert not verdict.ok


# --------------------------------------------------------- env-var plumbing


def test_read_changed_files_prefers_env_over_stdin(monkeypatch):
    monkeypatch.setenv("CHANGED_FILES", f"README.md\n{TARGET}\n\n")
    files = lzce._read_changed_files()
    assert files == ["README.md", TARGET]


def test_main_exit_code_guilty(monkeypatch, capsys):
    monkeypatch.setenv("CHANGED_FILES", TARGET)
    monkeypatch.delenv("PR_BODY", raising=False)
    rc = lzce.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert TARGET in out


def test_main_exit_code_innocent(monkeypatch, capsys):
    monkeypatch.setenv("CHANGED_FILES", "README.md")
    monkeypatch.delenv("PR_BODY", raising=False)
    rc = lzce.main()
    assert rc == 0
