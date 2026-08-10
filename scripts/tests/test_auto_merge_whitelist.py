"""Regression tests for the auto-merge workflow's exact author allowlist."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "auto-merge-whitelist.yml"


def _author_check_script() -> str:
    """Extract the workflow's author-check run block without a YAML dependency."""
    text = WORKFLOW.read_text(encoding="utf-8")
    step_marker = "      - name: Check author allowlist\n"
    step = text.split(step_marker, 1)[1]
    run_marker = "        run: |\n"
    run_block = step.split(run_marker, 1)[1]

    body: list[str] = []
    for line in run_block.splitlines():
        if line.startswith("      - name: "):
            break
        assert line.startswith("          ") or not line, (
            f"unexpected indentation in author-check run block: {line!r}"
        )
        body.append(line[10:] if line else "")

    assert body, "author-check run block was not extracted"
    return "\n".join(body) + "\n"


def _evaluate_author(author: str, tmp_path: Path) -> str:
    github_output = tmp_path / "github-output"
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _author_check_script()],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "AUTHOR": author, "GITHUB_OUTPUT": str(github_output)},
    )
    assert result.stderr == ""
    return github_output.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("author", ["dependabot[bot]", "github-actions[bot]"])
def test_literal_bot_authors_are_allowlisted(author: str, tmp_path: Path) -> None:
    assert _evaluate_author(author, tmp_path) == "match=true"


@pytest.mark.parametrize(
    "author",
    [
        "dependabotb",
        "dependaboto",
        "dependabott",
        "github-actionsb",
        "github-actionso",
        "github-actionst",
        "github-actions[bot]extra",
    ],
)
def test_glob_near_misses_are_not_allowlisted(author: str, tmp_path: Path) -> None:
    assert _evaluate_author(author, tmp_path) == "match=false"
