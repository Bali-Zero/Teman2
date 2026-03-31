"""
Dead Code & Hardcoded Values Audit — Core Guardian Check

Finds:
1. Dead query params: frontend appending query params the backend ignores
   (e.g., `?created_by=`, `?updated_by=` when backend reads from JWT)
2. Hardcoded team member/admin email lists in frontend
3. Hardcoded ID arrays (leave types, status values) instead of API calls
4. `as any` type assertions in TypeScript (indicates type mismatch)

Usage:
    from apps.evaluator.core_guardian.checks.dead_code_audit import run_audit
    findings = run_audit(project_root)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORE_PATHS = {"__pycache__", ".venv", "venv", "node_modules", ".next", "dist", ".git", "tests"}


@dataclass
class DeadCodeFinding:
    file: str
    line: int
    category: str  # "hardcoded_list" | "as_any" | "dead_param" | "hardcoded_ids"
    snippet: str
    severity: str = "warning"

    def __str__(self) -> str:
        return (
            f"⚠️ {self.file}:{self.line} [{self.category}] — {self.snippet.strip()[:100]}"
        )


@dataclass
class AuditResult:
    findings: list[DeadCodeFinding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def total(self) -> int:
        return len(self.findings)

    def summary(self) -> str:
        by_cat = {}
        for f in self.findings:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
        cats = ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items()))
        return f"DeadCodeAudit: {self.total} findings ({cats}) in {self.files_scanned} files"


# --- Patterns ---

# Hardcoded email/admin arrays in TypeScript
HARDCODED_EMAILS = re.compile(
    r"(?:ADMIN_EMAILS|ALL_TEAM_MEMBERS|TEAM_MEMBERS)\s*(?::\s*\w+(?:\[\])?)?\s*=\s*\[",
    re.MULTILINE,
)

# `as any` type assertions
AS_ANY = re.compile(r"\bas\s+any\b")

# Hardcoded numeric IDs in <option value={N}> patterns
HARDCODED_OPTION_IDS = re.compile(
    r"<option\s+value=\{(\d+)\}>"
)

# queryParams.append with known dead params
DEAD_QUERY_PARAMS = re.compile(
    r"queryParams\.append\([\"'](created_by|updated_by)[\"']",
    re.MULTILINE,
)


def _should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & IGNORE_PATHS) or any(
        p.lower().startswith("test_") or p.lower().endswith(".test.ts")
        or p.lower().endswith(".test.tsx") or p.lower().endswith(".spec.ts")
        for p in path.parts
    )


def _find_line(content: str, pos: int) -> int:
    return content[:pos].count("\n") + 1


def _scan_file(filepath: Path, result: AuditResult) -> None:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    result.files_scanned += 1
    fname = str(filepath)

    # Hardcoded email/admin lists
    for m in HARDCODED_EMAILS.finditer(content):
        result.findings.append(DeadCodeFinding(
            file=fname,
            line=_find_line(content, m.start()),
            category="hardcoded_list",
            snippet=m.group(0),
        ))

    # `as any` — high noise, so only flag in app code (not lib/config)
    if "/app/" in fname or "/components/" in fname or "/hooks/" in fname:
        for m in AS_ANY.finditer(content):
            # Skip comments
            line_start = content.rfind("\n", 0, m.start()) + 1
            line_text = content[line_start:content.find("\n", m.start())]
            if line_text.strip().startswith("//") or line_text.strip().startswith("*"):
                continue
            result.findings.append(DeadCodeFinding(
                file=fname,
                line=_find_line(content, m.start()),
                category="as_any",
                snippet=line_text.strip(),
                severity="info",
            ))

    # Hardcoded option IDs (>3 consecutive)
    option_matches = list(HARDCODED_OPTION_IDS.finditer(content))
    if len(option_matches) >= 4:
        result.findings.append(DeadCodeFinding(
            file=fname,
            line=_find_line(content, option_matches[0].start()),
            category="hardcoded_ids",
            snippet=f"{len(option_matches)} hardcoded <option value={{N}}> — should fetch from API",
        ))

    # Dead query params
    for m in DEAD_QUERY_PARAMS.finditer(content):
        result.findings.append(DeadCodeFinding(
            file=fname,
            line=_find_line(content, m.start()),
            category="dead_param",
            snippet=m.group(0),
        ))


def run_audit(project_root: str | Path) -> AuditResult:
    """Run dead code / hardcoded values audit."""
    root = Path(project_root)
    result = AuditResult()

    # Scan TypeScript/JavaScript
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for filepath in root.rglob(ext):
            if not _should_skip(filepath):
                _scan_file(filepath, result)

    logger.info(result.summary())
    return result


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    res = run_audit(root)
    for f in res.findings:
        print(f)
    print(f"\n{res.summary()}")
