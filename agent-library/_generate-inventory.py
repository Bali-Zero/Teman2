#!/usr/bin/env python3
"""Generate agent-library/01-inventory.md — operational snapshot of all agents.

Usage:
    python3 agent-library/_generate-inventory.py [--dry-run]

--dry-run: print to stdout instead of writing the file.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml  # pip install pyyaml

REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = Path.home() / ".claude" / "agents"
SKILLS_DIR = Path.home() / ".claude" / "skills"
LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
CURSOR_RULES_DIR = REPO_ROOT / ".cursor" / "rules"
GEMINI_SKILLS_DIR = Path.home() / ".gemini" / "skills"
OUTPUT_FILE = Path(__file__).parent / "01-inventory.md"

AGENTIC_KEYWORDS = re.compile(
    r"\b(claude|gemini|nlm|codex|deepseek|ollama)\b", re.IGNORECASE
)


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown file. Returns {} on failure."""
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        end = text.index("---", 3)
        return yaml.safe_load(text[3:end]) or {}
    except Exception as e:
        print(f"  WARN: {path.name} frontmatter parse failed: {e}", file=sys.stderr)
        return {}


def scan_subagents() -> list[dict[str, Any]]:
    """Scan ~/.claude/agents/*.md (skip *.pre-T2 and non-.md files)."""
    results = []
    for p in sorted(AGENTS_DIR.glob("*.md")):
        if ".pre-T2" in p.name or p.suffix != ".md":
            continue
        fm = parse_frontmatter(p)
        results.append({
            "name": fm.get("name", p.stem),
            "description": (fm.get("description") or "")[:120],
            "model": fm.get("model", ""),
            "tools": fm.get("tools", []),
            "path": str(p),
            "mtime": p.stat().st_mtime,
            "frontmatter_ok": bool(fm),
        })
    return results


def main(dry_run: bool = False) -> int:
    subagents = scan_subagents()
    for a in subagents:
        print(f"  {a['name']:40s} model={a['model']}")
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry_run))
