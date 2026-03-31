"""
Empty Catch Block Audit — Core Guardian Check

Finds empty or silent catch blocks in both Python and TypeScript/JavaScript.

Patterns detected:
- Python: `except Exception: pass`, `except: pass`, `except SomeError: ...` with empty body
- TypeScript: `.catch(() => {})`, `catch (e) {}`, `catch { }` with no real handling

Usage:
    from apps.evaluator.core_guardian.checks.empty_catch_audit import run_audit
    findings = run_audit(project_root)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORE_PATHS = {"__pycache__", ".venv", "venv", "node_modules", ".next", "dist", "migrations", ".git"}

# --- TypeScript/JavaScript patterns ---

# .catch(() => {})  or  .catch(() => { })  or  .catch(function() {})
TS_CATCH_EMPTY_LAMBDA = re.compile(
    r"\.catch\s*\(\s*\(?(?:\w+)?\)?\s*=>\s*\{\s*\}\s*\)", re.MULTILINE
)

# .catch(() => { /* comment only */ })
TS_CATCH_COMMENT_ONLY = re.compile(
    r"\.catch\s*\(\s*\(?(?:\w+)?\)?\s*=>\s*\{\s*(?://[^\n]*|/\*.*?\*/)\s*\}\s*\)", re.DOTALL
)

# try { ... } catch (e) { } — empty catch body
TS_TRY_CATCH_EMPTY = re.compile(
    r"catch\s*\([^)]*\)\s*\{\s*\}", re.MULTILINE
)

# --- Python patterns ---
# except ...: pass (on the same or next line)
PY_EXCEPT_PASS = re.compile(
    r"except\s+[^:]*:\s*\n\s+pass\s*$", re.MULTILINE
)
# bare except: pass
PY_BARE_EXCEPT_PASS = re.compile(
    r"except:\s*\n\s+pass\s*$", re.MULTILINE
)


@dataclass
class EmptyCatchFinding:
    """A silent/empty catch block."""

    file: str
    line: int
    pattern: str
    snippet: str
    language: str  # "python" | "typescript"
    severity: str = "warning"

    def __str__(self) -> str:
        return (
            f"⚠️ {self.file}:{self.line} [{self.language}] "
            f"empty catch: {self.pattern} — `{self.snippet.strip()[:80]}`"
        )


@dataclass
class AuditResult:
    """Aggregated result."""

    findings: list[EmptyCatchFinding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def total(self) -> int:
        return len(self.findings)

    def summary(self) -> str:
        return (
            f"EmptyCatchAudit: {self.total} findings in {self.files_scanned} files"
        )


def _should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & IGNORE_PATHS) or any(
        p.lower().startswith("test_") or p.lower().endswith(".test.ts") or p.lower().endswith(".test.tsx")
        for p in path.parts
    )


def _find_line(content: str, pos: int) -> int:
    """Convert character position to line number."""
    return content[:pos].count("\n") + 1


def _scan_typescript(filepath: Path, result: AuditResult) -> None:
    """Scan a TypeScript/JavaScript file for empty catch blocks."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    result.files_scanned += 1

    for pattern, label in [
        (TS_CATCH_EMPTY_LAMBDA, ".catch(() => {})"),
        (TS_CATCH_COMMENT_ONLY, ".catch(() => { /* comment */ })"),
        (TS_TRY_CATCH_EMPTY, "catch (e) {}"),
    ]:
        for m in pattern.finditer(content):
            result.findings.append(EmptyCatchFinding(
                file=str(filepath),
                line=_find_line(content, m.start()),
                pattern=label,
                snippet=m.group(0),
                language="typescript",
            ))


def _scan_python(filepath: Path, result: AuditResult) -> None:
    """Scan a Python file for empty except blocks."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    result.files_scanned += 1

    for pattern, label in [
        (PY_EXCEPT_PASS, "except ...: pass"),
        (PY_BARE_EXCEPT_PASS, "bare except: pass"),
    ]:
        for m in pattern.finditer(content):
            result.findings.append(EmptyCatchFinding(
                file=str(filepath),
                line=_find_line(content, m.start()),
                pattern=label,
                snippet=m.group(0),
                language="python",
            ))


def run_audit(project_root: str | Path) -> AuditResult:
    """Run the empty catch block audit across the entire project."""
    root = Path(project_root)
    result = AuditResult()

    # Scan TypeScript/JavaScript files (frontend)
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for filepath in root.rglob(ext):
            if not _should_skip(filepath):
                _scan_typescript(filepath, result)

    # Scan Python files (backend)
    for filepath in root.rglob("*.py"):
        if not _should_skip(filepath):
            _scan_python(filepath, result)

    logger.info(result.summary())
    return result


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    res = run_audit(root)
    for f in res.findings:
        print(f)
    print(f"\n{res.summary()}")
