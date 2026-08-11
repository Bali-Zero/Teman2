"""Behavioral regression tests for the auto-merge eligibility workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "auto-merge-whitelist.yml"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"


def _workflow_step_script(step_name: str) -> str:
    """Extract one workflow run block without adding a YAML dependency."""
    text = WORKFLOW.read_text(encoding="utf-8")
    step_marker = f"      - name: {step_name}\n"
    step = text.split(step_marker, 1)[1]
    run_marker = "        run: |\n"
    run_block = step.split(run_marker, 1)[1]

    body: list[str] = []
    for line in run_block.splitlines():
        if line.startswith("      - name: "):
            break
        assert line.startswith("          ") or not line, (
            f"unexpected indentation in {step_name!r} run block: {line!r}"
        )
        body.append(line[10:] if line else "")

    assert body, f"{step_name!r} run block was not extracted"
    return "\n".join(body) + "\n"


def _evaluate_author(author: str, tmp_path: Path) -> str:
    github_output = tmp_path / "github-output"
    result = subprocess.run(
        [
            "bash",
            "-euo",
            "pipefail",
            "-c",
            _workflow_step_script("Check author allowlist"),
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "AUTHOR": author, "GITHUB_OUTPUT": str(github_output)},
    )
    assert result.stderr == ""
    return github_output.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize(
    "author", ["dependabot[bot]", "github-actions[bot]", "Balizero1987"]
)
def test_exact_allowlisted_authors_are_allowlisted(author: str, tmp_path: Path) -> None:
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
        "Balizero1987extra",
        "dependabot",
        "github-actions",
    ],
)
def test_glob_near_misses_are_not_allowlisted(author: str, tmp_path: Path) -> None:
    assert _evaluate_author(author, tmp_path) == "match=false"


def _install_fake_gh(tmp_path: Path) -> Path:
    """Install a deterministic GitHub CLI boundary double for the workflow."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
repo = os.environ["REPO"]
pr = os.environ["PR"]

if args[:2] == ["pr", "view"]:
    sys.stdout.write(os.environ.get("GH_LEGACY_FILES_OUTPUT", ""))
    raise SystemExit(int(os.environ.get("GH_LEGACY_FILES_EXIT", "0")))

if args[:2] == ["pr", "merge"]:
    with open(os.environ["GH_CALLS_FILE"], "w", encoding="utf-8") as stream:
        json.dump(args, stream)
    raise SystemExit(int(os.environ.get("GH_MERGE_EXIT", "0")))

if args == ["api", f"repos/{repo}/pulls/{pr}", "--jq", ".changed_files"]:
    sys.stdout.write(os.environ.get("GH_EXPECTED_COUNT", "0") + "\\n")
    raise SystemExit(int(os.environ.get("GH_METADATA_EXIT", "0")))

if args == [
    "api",
    "--paginate",
    f"repos/{repo}/pulls/{pr}/files?per_page=100",
    "--jq",
    ".[].filename",
]:
    sys.stdout.write(os.environ.get("GH_FILES_OUTPUT", ""))
    raise SystemExit(int(os.environ.get("GH_FILES_EXIT", "0")))

print(f"unexpected gh invocation: {args!r}", file=sys.stderr)
raise SystemExit(97)
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return bin_dir


def _evaluate_paths(
    tmp_path: Path,
    *,
    expected_count: int,
    files: list[str],
    legacy_files: list[str] | None = None,
    files_exit: int = 0,
    metadata_exit: int = 0,
) -> tuple[subprocess.CompletedProcess[str], str]:
    github_output = tmp_path / "github-output"
    bin_dir = _install_fake_gh(tmp_path)
    script = _workflow_step_script("Check diff does not touch protected paths")
    # Model the expression interpolation Actions performs before invoking Bash.
    script = script.replace("${{ steps.pr.outputs.number }}", "123")
    script = script.replace("${{ github.repository }}", "test/repo")
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(github_output),
            "PR": "123",
            "REPO": "test/repo",
            "GH_EXPECTED_COUNT": str(expected_count),
            "GH_FILES_OUTPUT": "\n".join(files),
            "GH_FILES_EXIT": str(files_exit),
            "GH_METADATA_EXIT": str(metadata_exit),
            "GH_LEGACY_FILES_OUTPUT": "\n".join(
                files if legacy_files is None else legacy_files
            ),
        },
    )
    output = (
        github_output.read_text(encoding="utf-8").strip()
        if github_output.exists()
        else ""
    )
    return result, output


def _tier1_codeowners_samples() -> list[str]:
    """Map the current simple Tier-1 CODEOWNERS rules to concrete probe paths."""
    text = CODEOWNERS.read_text(encoding="utf-8")
    tier1 = text.split("# CI / workflows / GitHub config — TIER 1", 1)[1]
    tier1 = tier1.split("# Subhi lane", 1)[0]
    samples: list[str] = []
    for raw_line in tier1.splitlines():
        fields = raw_line.split()
        if not fields or not fields[0].startswith("/"):
            continue
        pattern = fields[0]
        assert not any(char in pattern for char in "*?[]"), (
            f"Tier-1 CODEOWNERS rule needs an explicit test mapper: {pattern}"
        )
        sample = pattern.removeprefix("/")
        if sample.endswith("/"):
            sample += "__auto_merge_probe__"
        samples.append(sample)
    assert samples, "no Tier-1 CODEOWNERS rules found"
    return samples


def _safe_paths(count: int) -> list[str]:
    return [f"docs/generated/safe-{index:03}.md" for index in range(count)]


def test_auto_merge_is_pinned_to_the_evaluated_head(tmp_path: Path) -> None:
    head_sha = "a" * 40
    calls_file = tmp_path / "gh-calls.json"
    bin_dir = _install_fake_gh(tmp_path)
    script = _workflow_step_script("Enable auto-merge")
    script = script.replace("${{ steps.pr.outputs.number }}", "123")
    script = script.replace("${{ github.repository }}", "test/repo")
    script = script.replace("${{ github.event.pull_request.head.sha }}", head_sha)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GH_CALLS_FILE": str(calls_file),
            "PR": "123",
            "REPO": "test/repo",
            "EXPECTED_HEAD": head_sha,
        },
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(calls_file.read_text(encoding="utf-8")) == [
        "pr",
        "merge",
        "123",
        "--repo",
        "test/repo",
        "--auto",
        "--squash",
        "--delete-branch",
        "--match-head-commit",
        head_sha,
    ]


def test_paginated_file_101_cannot_hide_a_protected_path(tmp_path: Path) -> None:
    files = [*_safe_paths(100), ".github/workflows/unsafe.yml"]
    result, output = _evaluate_paths(
        tmp_path,
        expected_count=101,
        files=files,
        legacy_files=files[:100],
    )

    assert result.returncode == 0, result.stderr
    assert output == "match=false"


def test_paginated_file_list_over_100_safe_paths_remains_eligible(
    tmp_path: Path,
) -> None:
    files = _safe_paths(101)
    result, output = _evaluate_paths(
        tmp_path,
        expected_count=101,
        files=files,
        legacy_files=files[:100],
    )

    assert result.returncode == 0, result.stderr
    assert output == "match=true"


def test_file_api_failure_fails_closed(tmp_path: Path) -> None:
    result, output = _evaluate_paths(
        tmp_path,
        expected_count=1,
        files=[],
        legacy_files=["docs/generated/safe.md"],
        files_exit=42,
    )

    assert result.returncode != 0
    assert output != "match=true"


@pytest.mark.parametrize(
    ("expected_count", "files"),
    [(1, []), (101, _safe_paths(100))],
    ids=["blind-empty", "truncated"],
)
def test_file_count_mismatch_fails_closed(
    tmp_path: Path, expected_count: int, files: list[str]
) -> None:
    result, output = _evaluate_paths(
        tmp_path,
        expected_count=expected_count,
        files=files,
        legacy_files=files,
    )

    assert result.returncode != 0
    assert output != "match=true"


@pytest.mark.parametrize("protected_path", _tier1_codeowners_samples())
def test_every_tier1_codeowners_path_blocks_auto_merge(
    tmp_path: Path, protected_path: str
) -> None:
    result, output = _evaluate_paths(
        tmp_path,
        expected_count=1,
        files=[protected_path],
    )

    assert result.returncode == 0, result.stderr
    assert output == "match=false"
