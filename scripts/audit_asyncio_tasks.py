#!/usr/bin/env python3
"""Audit asyncio.create_task / loop.create_task fire-and-forget usage.

Classifies each production call site as:
  SAFE     — result assigned (var = asyncio.create_task(...)) or stored on
             self/module-level set.
  DROPPED  — call statement with no binding, no awaiting pattern in immediate
             scope. Potential "lost task" → strong-ref missing.
  UNCLEAR  — requires manual inspection (nested expression, passed as arg, etc.)

Heuristic is lexical (line-level), not AST — fine as first pass; manual triage
follows. Tests dir excluded.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1] / "apps/backend-rag/backend"
CREATE_TASK_RE = re.compile(r"(asyncio|loop)\.create_task\s*\(")

# Lexical hints per line content
ASSIGN_LHS_RE = re.compile(r"^\s*([a-zA-Z_][\w\.]*)\s*=\s*(asyncio|loop)\.create_task\b")
ASSIGN_WALRUS_RE = re.compile(r":=\s*(asyncio|loop)\.create_task\b")
# "self._foo = asyncio.create_task(..." → SAFE (stored on instance)
SELF_STORE_RE = re.compile(r"^\s*self\.[\w_]+\s*=\s*(asyncio|loop)\.create_task\b")
# Bare statement: whitespace + asyncio.create_task(
BARE_CALL_RE = re.compile(r"^\s*(asyncio|loop)\.create_task\s*\(")
# Inside append/add/set-literal
APPEND_HINT_RE = re.compile(r"\.(append|add)\s*\(\s*(asyncio|loop)\.create_task\b")
# await asyncio.create_task(...) or await asyncio.gather(asyncio.create_task(...))
AWAITED_HINT_RE = re.compile(r"await\s+(asyncio\.(gather|wait)\s*\(|\s*(asyncio|loop)\.create_task\b)")


def classify(file_path: Path, lineno: int, line: str, context_before: list[str]) -> tuple[str, str]:
    """Return (category, reason)."""
    if SELF_STORE_RE.search(line):
        return "SAFE", "stored on self.*"
    if ASSIGN_LHS_RE.search(line):
        return "SAFE", "assigned to local/module var"
    if ASSIGN_WALRUS_RE.search(line):
        return "SAFE", "walrus assignment"
    if APPEND_HINT_RE.search(line):
        return "SAFE", "appended to collection"
    if AWAITED_HINT_RE.search(line):
        return "SAFE", "awaited inline"

    # Multi-line: the call may continue onto next line. If the *previous* line
    # ends with `=` or `.append(`, treat as assigned.
    prev_nonblank = ""
    for prev in reversed(context_before[-3:]):
        s = prev.rstrip()
        if s:
            prev_nonblank = s
            break
    if prev_nonblank.endswith("=") or prev_nonblank.endswith("(") and re.search(r"(\.append|\.add|=)\s*\($", prev_nonblank):
        return "SAFE", f"continuation of '{prev_nonblank.strip()[-30:]}'"
    # Line begins with `=` continuation? rare
    if BARE_CALL_RE.search(line):
        return "DROPPED", "bare call, no binding"
    return "UNCLEAR", "expression context"


def main() -> int:
    entries = []
    for py in ROOT.rglob("*.py"):
        if "/tests/" in str(py) or py.name.startswith("test_"):
            continue
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, start=1):
            if not CREATE_TASK_RE.search(line):
                continue
            # Skip comments & docstrings (quick lexical check)
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # crude: skip lines that are inside """..."""; we can't track state
            # perfectly, but a line whose first non-ws char is `#` or that looks
            # like prose ("— called via asyncio.create_task from...") gets
            # caught by the RE. Filter out obvious doc mentions: require '(' and
            # either '=' on this line or parent.
            context_before = lines[max(0, i - 4) : i - 1]
            category, reason = classify(py, i, line, context_before)
            # Further filter: if line has no `(` after create_task (pure mention
            # in docstring), skip.
            if "create_task(" not in line:
                continue
            rel = py.relative_to(ROOT)
            entries.append(
                {
                    "file": f"backend/{rel.as_posix()}",
                    "line": i,
                    "category": category,
                    "reason": reason,
                    "snippet": line.rstrip()[:180],
                }
            )

    by_cat: dict[str, int] = {"SAFE": 0, "DROPPED": 0, "UNCLEAR": 0}
    by_file_dropped: dict[str, int] = {}
    for e in entries:
        by_cat[e["category"]] += 1
        if e["category"] == "DROPPED":
            by_file_dropped[e["file"]] = by_file_dropped.get(e["file"], 0) + 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "apps/backend-rag/backend (production, tests excluded)",
        "total_sites": len(entries),
        "by_category": by_cat,
        "dropped_by_file": dict(sorted(by_file_dropped.items(), key=lambda kv: -kv[1])),
        "entries": entries,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
