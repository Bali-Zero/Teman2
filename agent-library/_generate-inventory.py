#!/usr/bin/env python3
"""Generate agent-library/01-inventory.md — operational snapshot of all agents.

Pure I/O: reads .claude/agents/, ~/Library/LaunchAgents/com.balizero.*.plist,
~/.claude/skills/, .cursor/rules/, ~/.gemini/skills/. No network, no LLM,
no secrets, no script-content analysis beyond a header keyword scan.

Usage:
    python3 agent-library/_generate-inventory.py [--dry-run]

--dry-run: print to stdout instead of writing the file.

Design: docs/superpowers/specs/2026-05-14-agent-library-inventory-design.md
Plan:   docs/superpowers/plans/2026-05-15-agent-library-inventory.md
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml  # PyYAML

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

STALE_DAYS = 90


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown file. Returns {} on failure."""
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        end = text.index("---", 3)
        loaded = yaml.safe_load(text[3:end])
        return loaded if isinstance(loaded, dict) else {}
    except Exception as e:
        print(f"  WARN: {path.name} frontmatter parse failed: {e}", file=sys.stderr)
        return {}


def scan_subagents() -> list[dict[str, Any]]:
    """Scan ~/.claude/agents/*.md (skip *.pre-T2 and non-files)."""
    results = []
    if not AGENTS_DIR.is_dir():
        return results
    for p in sorted(AGENTS_DIR.glob("*.md")):
        if ".pre-T2" in p.name or not p.is_file():
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


def scan_cross_tool() -> list[dict[str, Any]]:
    raise NotImplementedError("scan_cross_tool — implemented in Task 4")


def scan_crons() -> list[dict[str, Any]]:
    raise NotImplementedError("scan_crons — implemented in Task 3")


def scan_skills() -> list[dict[str, Any]]:
    raise NotImplementedError("scan_skills — implemented in Task 4")


def compute_drift(
    subagents: list[dict[str, Any]],
    crons: list[dict[str, Any]],
) -> dict[str, list[str]]:
    raise NotImplementedError("compute_drift — implemented in Task 5")


def render(
    subagents: list[dict[str, Any]],
    cross_tool: list[dict[str, Any]],
    crons: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    drift: dict[str, list[str]],
) -> str:
    raise NotImplementedError("render — implemented in Task 5")


def main(dry_run: bool = False) -> int:
    subagents = scan_subagents()
    cross_tool = scan_cross_tool()
    crons = scan_crons()
    skills = scan_skills()
    drift = compute_drift(subagents, crons)
    content = render(subagents, cross_tool, crons, skills, drift)
    if dry_run:
        sys.stdout.write(content)
        return 0
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"Written: {OUTPUT_FILE} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
