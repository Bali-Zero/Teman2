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


def _plist_to_json(plist_path: Path) -> dict[str, Any]:
    """Convert plist to dict via plutil. Returns {} on failure."""
    try:
        result = subprocess.run(
            ["plutil", "-convert", "json", "-o", "-", str(plist_path)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except Exception:
        return {}


def _schedule_str(plist_dict: dict[str, Any]) -> str:
    """Human-readable schedule from plist dict."""
    if "StartCalendarInterval" in plist_dict:
        sci = plist_dict["StartCalendarInterval"]
        if isinstance(sci, list):
            return f"calendar×{len(sci)}"
        h = sci.get("Hour", "*")
        m = sci.get("Minute", 0)
        return f"daily@{h:02}:{m:02}"
    if "StartInterval" in plist_dict:
        s = int(plist_dict["StartInterval"])
        if s < 120:
            return f"every {s}s"
        if s < 3600:
            return f"every {s//60}min"
        return f"every {s//3600}h"
    return "on-demand"


def _script_path(plist_dict: dict[str, Any]) -> str:
    """Extract the actual script path from Program or ProgramArguments.

    Handles patterns:
    - Program: /path/to/script.sh
    - ProgramArguments: ['/path/to/script.sh', ...]
    - ProgramArguments: ['/bin/zsh', '-lc', '/path/to/script.sh >> ...']
    """
    prog = plist_dict.get("Program", "")
    args = plist_dict.get("ProgramArguments", [])
    if not prog and args:
        # Check for shell wrapper pattern: ['/bin/zsh', '-lc', '<script> ...']
        if len(args) >= 3 and args[0] in ("/bin/zsh", "/bin/bash", "zsh", "bash") and "-lc" in args:
            # The command string may be '<script> >> log 2>&1' — extract first token
            cmd = args[-1].split()[0] if args[-1] else ""
            prog = cmd if cmd else args[0]
        else:
            prog = args[0]
    return prog


def _is_agentic(script_path_str: str) -> bool:
    """Check if a cron script calls an LLM. Reads first 30 lines only."""
    p = Path(script_path_str)
    if not p.exists():
        return False
    try:
        lines = []
        with p.open(encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 30:
                    break
                lines.append(line)
        header = "".join(lines)
        return bool(AGENTIC_KEYWORDS.search(header))
    except Exception:
        return False


def scan_crons() -> list[dict[str, Any]]:
    """Scan all com.balizero.* plists in ~/Library/LaunchAgents."""
    results = []
    for p in sorted(LAUNCHAGENTS_DIR.glob("com.balizero.*.plist")):
        pdict = _plist_to_json(p)
        if not pdict:
            continue
        label = pdict.get("Label", p.stem)
        script = _script_path(pdict)
        agentic = _is_agentic(script)
        results.append({
            "label": label,
            "schedule": _schedule_str(pdict),
            "script": script,
            "agentic": agentic,
            "script_exists": Path(script).exists() if script else False,
        })
    return results


def main(dry_run: bool = False) -> int:
    crons = scan_crons()
    agentic = [c for c in crons if c["agentic"]]
    infra = [c for c in crons if not c["agentic"]]
    print(f"Agentic crons: {len(agentic)}, Infra crons: {len(infra)}")
    for c in crons[:5]:
        print(f"  {c['label']:50s} {c['schedule']:15s} agentic={c['agentic']}")
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry_run))
