#!/usr/bin/env python3
"""Audit tracked WhatsApp corpus reports for obvious privacy leaks.

The scanner intentionally reports only repo-relative paths and pattern labels.
It never emits matching lines or surrounding content.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_TARGET = Path("research/personal/wa-corpus")
IGNORED_SUFFIXES = {".sqlite", ".db"}
IGNORED_DIRS = {"__pycache__"}


@dataclass(frozen=True)
class LeakPattern:
    label: str
    regex: re.Pattern[str]


LEAK_PATTERNS: tuple[LeakPattern, ...] = (
    LeakPattern("wa_chats_path", re.compile(re.escape("/Users/nuzantara/Desktop/wa-chats"))),
    LeakPattern("phone_prefix_62", re.compile(re.escape("+62"))),
    LeakPattern("name_bebe", re.compile(r"(?<![A-Za-z0-9_])Bebe(?![A-Za-z0-9_])")),
    LeakPattern("name_adit", re.compile(r"(?<![A-Za-z0-9_])Adit(?![A-Za-z0-9_])")),
    LeakPattern("name_ari", re.compile(r"(?<![A-Za-z0-9_])Ari(?![A-Za-z0-9_])")),
    LeakPattern("name_krisna", re.compile(r"(?<![A-Za-z0-9_])Krisna(?![A-Za-z0-9_])")),
    LeakPattern("name_sahira", re.compile(r"(?<![A-Za-z0-9_])Sahira(?![A-Za-z0-9_])")),
    LeakPattern("name_surya", re.compile(r"(?<![A-Za-z0-9_])Surya(?![A-Za-z0-9_])")),
    LeakPattern("google_drive", re.compile(r"(?<![A-Za-z0-9_])GoogleDrive(?![A-Za-z0-9_])")),
    LeakPattern("name_papa", re.compile(r"(?<![A-Za-z0-9_])Papa(?![A-Za-z0-9_])")),
    LeakPattern("name_antonello", re.compile(r"(?<![A-Za-z0-9_])Antonello(?![A-Za-z0-9_])")),
    LeakPattern("name_siano", re.compile(r"(?<![A-Za-z0-9_])Siano(?![A-Za-z0-9_])")),
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    label: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Repo root. Default: current directory.")
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help=f"Repo-relative directory to audit. Default: {DEFAULT_TARGET}",
    )
    return parser.parse_args(argv)


def repo_relative(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def is_ignored_path(path: Path) -> bool:
    if any(part in IGNORED_DIRS for part in path.parts):
        return True
    if path.suffix in IGNORED_SUFFIXES:
        return True
    return path.name.startswith(".local.") or ".local." in path.name


def _git_ls_files(repo: Path, target: str) -> list[Path] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", target],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return [repo / line for line in result.stdout.splitlines() if line.strip()]


def _filesystem_files(repo: Path, target: str) -> list[Path]:
    root = repo / target
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def candidate_files(repo: Path, target: str) -> list[Path]:
    paths = _git_ls_files(repo, target)
    if paths is None:
        paths = _filesystem_files(repo, target)
    return sorted(path for path in paths if path.is_file() and not is_ignored_path(path))


def audit_file(repo: Path, path: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    rel_path = repo_relative(repo, path)
    return [
        Finding(path=rel_path, label=pattern.label)
        for pattern in LEAK_PATTERNS
        if pattern.regex.search(content)
    ]


def audit(repo: Path, target: str) -> list[Finding]:
    findings: list[Finding] = []
    for path in candidate_files(repo, target):
        findings.extend(audit_file(repo, path))
    return findings


def format_findings(findings: Iterable[Finding]) -> str:
    return "\n".join(f"{finding.path}\t{finding.label}" for finding in findings)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    findings = audit(repo, args.target)
    if findings:
        print(format_findings(findings))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
