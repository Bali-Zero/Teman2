"""WR3 lint enforcers — Symbiosis 8-leggi conformance checks.

Each module in this package implements one Law's conformance check against
the wr3_*.py modules + ~/.claude/agents/wr3-*.md + docs/wr3/contracts/*.yaml.

Designed to be runnable both individually (CI per-law) and as a single sweep
via `wr3_lint_runner.py`.

Each linter exports:
  - `check(repo_root: Path) -> list[LintFinding]`
  - `LAW_NUMBER: int`
  - `LAW_NAME: str`
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LintFinding:
    severity: str  # "ERROR" | "WARN" | "INFO"
    law: int
    file: str
    line: int | None
    message: str

    def fmt(self) -> str:
        loc = f"{self.file}:{self.line}" if self.line else self.file
        return f"[Law {self.law}][{self.severity}] {loc}: {self.message}"
