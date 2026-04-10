#!/usr/bin/env python3
"""Compute a fragility score per file from git churn + current Ruff violations.

Formula:
    raw_score = (mod_count * 2) + violation_count
    fragility = min(100, (raw_score / max_raw_score) * 100)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

COMMIT_LINE_RE = re.compile(r"^[0-9a-f]{40}\s+\d{4}-\d{2}-\d{2}\s+")


def _run_text(
    cmd: list[str],
    cwd: Path,
    ok_returncodes: set[int] | None = None,
) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    allowed = {0} if ok_returncodes is None else ok_returncodes
    if proc.returncode not in allowed:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc.returncode, proc.stdout, proc.stderr


def _git_repo_root(cwd: Path) -> Path:
    _, out, _ = _run_text(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(out.strip()).resolve()


def _normalize_path(raw_path: str, cwd: Path, repo_root: Path) -> str:
    raw = Path(raw_path)
    if raw.is_absolute():
        abs_path = raw.resolve()
    else:
        abs_path = (cwd / raw).resolve()

    try:
        return abs_path.relative_to(repo_root).as_posix()
    except ValueError:
        return abs_path.as_posix()


def parse_git_log(
    git_log_text: str,
    repo_root: Path,
    git_cwd: Path,
    python_only: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in git_log_text.splitlines():
        entry = line.strip()
        if not entry or COMMIT_LINE_RE.match(entry):
            continue
        normalized = _normalize_path(entry, cwd=git_cwd, repo_root=repo_root)
        if python_only and not normalized.endswith(".py"):
            continue
        counts[normalized] += 1
    return counts


def parse_ruff_json(
    ruff_json_text: str,
    repo_root: Path,
    ruff_cwd: Path,
    python_only: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not ruff_json_text.strip():
        return counts

    findings = json.loads(ruff_json_text)
    if not isinstance(findings, list):
        raise ValueError("Ruff JSON output is not a list.")

    for item in findings:
        if not isinstance(item, dict):
            continue
        filename = item.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            continue
        normalized = _normalize_path(filename, cwd=ruff_cwd, repo_root=repo_root)
        if python_only and not normalized.endswith(".py"):
            continue
        counts[normalized] += 1
    return counts


def compute_fragility(
    mod_counts: Counter[str],
    violation_counts: Counter[str],
) -> list[dict[str, float | int | str]]:
    files = set(mod_counts) | set(violation_counts)
    raw_scores: dict[str, int] = {
        file_path: (mod_counts.get(file_path, 0) * 2) + violation_counts.get(file_path, 0)
        for file_path in files
    }
    max_raw = max(raw_scores.values(), default=0)

    rows: list[dict[str, float | int | str]] = []
    for file_path in files:
        mod_count = int(mod_counts.get(file_path, 0))
        violation_count = int(violation_counts.get(file_path, 0))
        raw = int(raw_scores[file_path])
        if max_raw == 0:
            fragility = 0.0
        else:
            fragility = min(100.0, (raw / max_raw) * 100.0)
        rows.append(
            {
                "file": file_path,
                "mod_count": mod_count,
                "violation_count": violation_count,
                "raw": raw,
                "fragility": fragility,
            }
        )

    rows.sort(
        key=lambda item: (
            float(item["fragility"]),
            int(item["raw"]),
            int(item["mod_count"]),
            int(item["violation_count"]),
            str(item["file"]),
        ),
        reverse=True,
    )
    return rows


def print_table(
    rows: Iterable[dict[str, float | int | str]],
    top: int,
    days: int,
    scope: str,
    synthetic: bool,
) -> None:
    rows_list = list(rows)
    print(
        f"Fragility Top {top} | days={days} | scope={scope} | "
        f"mode={'synthetic' if synthetic else 'real'}"
    )
    print(f"{'rk':>2} {'fragility':>9} {'raw':>5} {'mods':>5} {'ruff':>5} file")

    for idx, row in enumerate(rows_list[:top], start=1):
        print(
            f"{idx:>2} "
            f"{float(row['fragility']):>9.2f} "
            f"{int(row['raw']):>5} "
            f"{int(row['mod_count']):>5} "
            f"{int(row['violation_count']):>5} "
            f"{row['file']}"
        )

    if not rows_list:
        print("(no files found)")


SYNTHETIC_GIT_LOG = """\
1111111111111111111111111111111111111111 2026-04-07 10:00:00 +0800
apps/backend-rag/backend/app/routers/a.py
apps/backend-rag/backend/app/routers/a.py

2222222222222222222222222222222222222222 2026-04-06 10:00:00 +0800
apps/backend-rag/backend/services/b.py
apps/backend-rag/backend/services/b.py
apps/backend-rag/backend/services/b.py

3333333333333333333333333333333333333333 2026-04-05 10:00:00 +0800
apps/backend-rag/backend/core/c.py
"""

SYNTHETIC_RUFF = json.dumps(
    [
        {"filename": "apps/backend-rag/backend/app/routers/a.py", "code": "F401"},
        {"filename": "apps/backend-rag/backend/app/routers/a.py", "code": "F821"},
        {"filename": "apps/backend-rag/backend/services/b.py", "code": "I001"},
        {"filename": "apps/backend-rag/backend/services/b.py", "code": "E402"},
        {"filename": "apps/backend-rag/backend/services/b.py", "code": "F401"},
        {"filename": "apps/backend-rag/backend/core/c.py", "code": "F401"},
        {"filename": "apps/backend-rag/backend/extra/d.py", "code": "F821"},
    ]
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute per-file fragility from recent git churn and Ruff violations."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback window for git log in days (default: 30).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many files to print (default: 20).",
    )
    parser.add_argument(
        "--scope",
        type=str,
        default="apps/backend-rag/backend",
        help="Scope path for git log and ruff check (default: apps/backend-rag/backend).",
    )
    parser.add_argument(
        "--ruff-config",
        type=str,
        default="apps/backend-rag/pyproject.toml",
        help="Path to pyproject.toml for Ruff (default: apps/backend-rag/pyproject.toml).",
    )
    parser.add_argument(
        "--include-non-python",
        action="store_true",
        help="Include non-.py files (default: false).",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use built-in synthetic git/ruff data instead of shelling out.",
    )
    args = parser.parse_args()

    python_only = not args.include_non_python
    start_cwd = Path.cwd().resolve()
    repo_root = _git_repo_root(start_cwd)

    if args.synthetic:
        git_log_text = SYNTHETIC_GIT_LOG
        ruff_json_text = SYNTHETIC_RUFF
        git_cwd = repo_root
        ruff_cwd = repo_root
    else:
        scope = args.scope
        git_cwd = repo_root
        ruff_cwd = repo_root

        _, git_log_text, _ = _run_text(
            [
                "git",
                "log",
                f"--since={args.days} days ago",
                "--format=%H %ai",
                "--name-only",
                "--",
                scope,
            ],
            cwd=git_cwd,
        )

        _, ruff_json_text, _ = _run_text(
            [
                "ruff",
                "check",
                scope,
                "--config",
                args.ruff_config,
                "--output-format",
                "json",
            ],
            cwd=ruff_cwd,
            ok_returncodes={0, 1},
        )

    mod_counts = parse_git_log(
        git_log_text=git_log_text,
        repo_root=repo_root,
        git_cwd=git_cwd,
        python_only=python_only,
    )
    violation_counts = parse_ruff_json(
        ruff_json_text=ruff_json_text,
        repo_root=repo_root,
        ruff_cwd=ruff_cwd,
        python_only=python_only,
    )
    rows = compute_fragility(mod_counts=mod_counts, violation_counts=violation_counts)
    print_table(rows=rows, top=args.top, days=args.days, scope=args.scope, synthetic=args.synthetic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
