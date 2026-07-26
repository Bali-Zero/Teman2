"""Tests for scripts/check_adversarial_review.py — the R1 generator!=grader gate.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package (mirrors scripts/tests/test_pending_arms_report.py convention).

Superscar #3 discipline: every guard needs both a GUILT suite (it fires on the
genuine violation) and an INNOCENCE suite (it stays quiet on every legitimate
neighbor). Both are represented below, plus the --diff subprocess-mocked mode
and the git-failure exit(2) contract (a blind scan must never look like a
clean pass — W84).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "check_adversarial_review.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_adversarial_review", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


car = _load_module()


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


VALID_FRONTMATTER = "---\ndate: 2026-07-06\nadversarial_review: kimi-k3\n---\n"
VALID_SECTION = "\n# Title\n\n## Adversarial review\n\nnone survived, 2 raised\n"


# ---------------------------------------------------------------------------
# --selftest is the built-in contract; re-run it under pytest for a clear
# per-test failure signal instead of one opaque bash-exit-code.
# ---------------------------------------------------------------------------


def test_builtin_selftest_passes():
    assert car.run_selftest() == 0


# ---------------------------------------------------------------------------
# GUILT — must FAIL
# ---------------------------------------------------------------------------


def test_guilt_missing_frontmatter_key(tmp_path):
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "---\ndate: 2026-07-06\n---\n\n# Title\n\nBody.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is False
    assert "adversarial_review" in v.reason


def test_guilt_empty_value(tmp_path):
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "---\ndate: 2026-07-06\nadversarial_review:\n---\n\n# Title\n\nBody.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is False
    assert "empty" in v.reason


def test_guilt_unknown_seat(tmp_path):
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "---\ndate: 2026-07-06\nadversarial_review: my-cousin\n---\n\n"
        "# Title\n\n## Adversarial review\n\nnone survived.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is False
    assert "not a known seat" in v.reason


def test_guilt_retired_deepseek_seat(tmp_path):
    # DeepSeek API retired 2026-07-19 (Zero's order) — the seat was removed from
    # KNOWN_SEATS and must now fail like any unknown seat.
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "---\ndate: 2026-07-06\nadversarial_review: deepseek-v4-pro\n---\n\n"
        "# Title\n\n## Adversarial review\n\nnone survived.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is False
    assert "not a known seat" in v.reason


def test_guilt_known_seat_but_no_section(tmp_path):
    p = _write(
        tmp_path,
        "research/operations/x.md",
        VALID_FRONTMATTER + "\n# Title\n\nBody, no adversarial section anywhere.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is False
    assert "Adversarial review" in v.reason


def test_guilt_no_frontmatter_at_all(tmp_path):
    p = _write(tmp_path, "research/operations/x.md", "# Title\n\nJust a body.\n")
    v = car.evaluate_file(p)
    assert v.ok is False
    assert "frontmatter" in v.reason


def test_guilt_frontmatter_does_not_open_on_line_one(tmp_path):
    # A leading blank line before the '---' is NOT a supported frontmatter open
    # (matches the live research/*.md convention verified in this session).
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "\n---\nadversarial_review: codex\n---\n\n## Adversarial review\n\nnone.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is False


def test_guilt_end_to_end_run_check_exits_1(tmp_path):
    bad = _write(tmp_path, "research/operations/bad.md", "# No frontmatter\n")
    assert car.run_check([bad]) == 1


# ---------------------------------------------------------------------------
# INNOCENCE — must PASS
# ---------------------------------------------------------------------------


def test_innocence_valid_seat_and_section(tmp_path):
    p = _write(tmp_path, "research/operations/x.md", VALID_FRONTMATTER + VALID_SECTION)
    v = car.evaluate_file(p)
    assert v.ok is True


def test_innocence_human_seat_accepted(tmp_path):
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "---\ndate: 2026-07-06\nadversarial_review: human-zero\n---\n\n"
        "# Title\n\n## Adversarial review\n\nZero reviewed and found no issue.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is True


def test_innocence_seat_token_case_insensitive(tmp_path):
    p = _write(
        tmp_path,
        "research/operations/x.md",
        "---\ndate: 2026-07-06\nadversarial_review: Kimi-K3\n---\n\n"
        "# Title\n\n## ADVERSARIAL REVIEW\n\nnone survived.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is True


def test_innocence_heading_level_three_also_matches(tmp_path):
    # SECTION_HEADING_RE uses #{2,} so a deeper heading level still counts.
    p = _write(
        tmp_path,
        "research/operations/x.md",
        VALID_FRONTMATTER + "\n# Title\n\n### Adversarial review\n\nnone survived.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is True


def test_innocence_exempt_prefix_skips_section_requirement(tmp_path):
    p = _write(
        tmp_path,
        "research/regulatory/2026-07-06-delta.md",
        "---\ndate: 2026-07-06\nadversarial_review: exempt-machine-generated\n---\n\n"
        "# Delta\n\nNo adversarial review section anywhere in this body.\n",
    )
    v = car.evaluate_file(p)
    assert v.ok is True


def test_innocence_exempt_notice_is_visible(tmp_path, capsys):
    p = _write(
        tmp_path,
        "research/regulatory/2026-07-06-delta.md",
        "---\ndate: 2026-07-06\nadversarial_review: exempt-machine-generated\n---\n\nBody.\n",
    )
    assert car.run_check([p]) == 0
    out = capsys.readouterr().out
    assert "NOTICE" in out
    assert "exempt-machine-generated" in out


def test_innocence_file_outside_research_ignored_even_with_bad_frontmatter(tmp_path):
    p = _write(tmp_path, "docs/specs/some-spec.md", "# No frontmatter, not research\n")
    assert car.is_in_scope(p) is False
    # end-to-end: run_check on a list containing ONLY this file must still exit 0.
    assert car.run_check([p]) == 0


def test_innocence_non_markdown_file_under_research_ignored(tmp_path):
    p = _write(tmp_path, "research/operations/data.json", "{}")
    assert car.is_in_scope(p) is False


def test_innocence_zero_in_scope_prints_message_and_exits_0(tmp_path, capsys):
    p = _write(tmp_path, "docs/other.md", "# Not research\n")
    code = car.run_check([p])
    out = capsys.readouterr().out
    assert code == 0
    assert "no research files in scope" in out


def test_innocence_end_to_end_run_check_exits_0(tmp_path):
    good = _write(tmp_path, "research/operations/good.md", VALID_FRONTMATTER + VALID_SECTION)
    assert car.run_check([good]) == 0


# ---------------------------------------------------------------------------
# --diff mode: subprocess mocked, plus the git-failure -> exit(2) contract
# ---------------------------------------------------------------------------


def test_diff_mode_returns_files_from_git_output(tmp_path):
    fake_result = subprocess.CompletedProcess(
        args=["git", "diff"],
        returncode=0,
        stdout="research/operations/a.md\nresearch/tax/b.md\n",
        stderr="",
    )
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        files = car.run_diff_mode("origin/main", repo_root=tmp_path)
    assert files == [tmp_path / "research/operations/a.md", tmp_path / "research/tax/b.md"]
    called_args = mock_run.call_args.args[0]
    assert called_args[:3] == ["git", "diff", "--name-only"]
    assert "origin/main...HEAD" in called_args


def test_diff_mode_empty_output_returns_empty_list(tmp_path):
    fake_result = subprocess.CompletedProcess(args=["git", "diff"], returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=fake_result):
        files = car.run_diff_mode("origin/main", repo_root=tmp_path)
    assert files == []


def test_diff_mode_git_failure_propagates_as_called_process_error(tmp_path):
    with patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(128, ["git", "diff"], stderr="fatal: bad revision"),
    ):
        with pytest.raises(subprocess.CalledProcessError):
            car.run_diff_mode("origin/main", repo_root=tmp_path)


def test_cli_diff_mode_git_failure_exits_2(capsys):
    with patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(128, ["git", "diff"], stderr="fatal: bad revision 'nope'"),
    ):
        code = car.main(["--diff", "nope"])
    assert code == 2
    err = capsys.readouterr().err
    assert "git diff failed" in err


def test_cli_diff_mode_git_not_found_exits_2():
    with patch("subprocess.run", side_effect=FileNotFoundError("git")):
        code = car.main(["--diff", "origin/main"])
    assert code == 2


def test_cli_diff_mode_success_end_to_end(tmp_path, monkeypatch):
    good = _write(tmp_path, "research/operations/good.md", VALID_FRONTMATTER + VALID_SECTION)
    fake_result = subprocess.CompletedProcess(
        args=["git", "diff"], returncode=0, stdout="research/operations/good.md\n", stderr=""
    )
    monkeypatch.chdir(tmp_path)
    with patch("subprocess.run", return_value=fake_result):
        code = car.main(["--diff", "origin/main"])
    assert code == 0
    assert good.exists()  # sanity: fixture actually landed where run_diff_mode expects it


# ---------------------------------------------------------------------------
# CLI: --files mode
# ---------------------------------------------------------------------------


def test_cli_files_mode_pass(tmp_path):
    good = _write(tmp_path, "research/operations/good.md", VALID_FRONTMATTER + VALID_SECTION)
    code = car.main(["--files", str(good)])
    assert code == 0


def test_cli_files_mode_fail(tmp_path):
    bad = _write(tmp_path, "research/operations/bad.md", "# no frontmatter\n")
    code = car.main(["--files", str(bad)])
    assert code == 1


def test_cli_no_mode_selected_exits_2(capsys):
    code = car.main([])
    assert code == 2
    err = capsys.readouterr().err
    assert "no mode selected" in err


def test_cli_selftest_flag_runs_and_exits_0():
    assert car.main(["--selftest"]) == 0


# ---------------------------------------------------------------------------
# is_in_scope: path-shape edge cases
# ---------------------------------------------------------------------------


def test_is_in_scope_relative_research_path():
    assert car.is_in_scope(Path("research/operations/foo.md")) is True


def test_is_in_scope_absolute_research_path(tmp_path):
    assert car.is_in_scope(tmp_path / "research" / "tax" / "foo.md") is True


def test_is_in_scope_research_substring_in_other_dir_not_matched():
    # "research" must be a full path SEGMENT, not a substring of another dir
    # name (e.g. "myresearcharchive/foo.md" must NOT match).
    assert car.is_in_scope(Path("myresearcharchive/foo.md")) is False
