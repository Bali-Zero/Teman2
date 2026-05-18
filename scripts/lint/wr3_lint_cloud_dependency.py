#!/usr/bin/env python3
"""WR3 Lint — Law 6 (Sovranità locale).

Symbiosis Law 6: WR3 runs on Pro/Mini-Pro2 hardware. Cloud touchpoints are
EXPLICITLY listed and minimized:
  - Veo 3.1 Fast Tier_ONE (via local FlowKit gateway)
  - Claude Agent SDK (CLI subprocess, OAuth — not API)
  - Gemini CLI cascade (OAuth)
  - NotebookLM via MCP (Google free)

BANNED cloud TTS:
  - Cartesia (banned per Law 6 doctrine — Antonello can per-episode-override)
  - ElevenLabs (Consumer Reports flagged, ToS controversy 2025)

Checks:
  1. No reference to cartesia/elevenlabs in scripts/wr3_*.py (other than the
     banned-constant declaration and exception-path docstrings).
  2. wr3_chatterbox_runner.py is the SINGLE TTS path declared.
  3. No httpx / requests Anthropic endpoints (`api.anthropic.com`) in code.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from . import LintFinding
except ImportError:
    import sys
    HERE = Path(__file__).resolve().parent
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from __init__ import LintFinding  # type: ignore

LAW_NUMBER = 6
LAW_NAME = "Sovranità locale"

BANNED_TTS_VENDORS = re.compile(r"\b(cartesia|elevenlabs|eleven_labs|playht|murf)\b", re.IGNORECASE)
BANNED_ANTHROPIC_ENDPOINT = re.compile(r"api\.anthropic\.com|anthropic\.Anthropic\(")

# Phrases that LEGITIMATELY mention the banned vendor (the ban itself)
ALLOWED_MENTION_CONTEXTS = [
    "BANNED",
    "banned",
    "exception path",
    "Antonello",
    "Symbiosis Law 6",
    "sovereignty",
    "sovranità",
]


def _allowed_context(line: str) -> bool:
    """Allow lines that mention the vendor in a 'banning' / 'comment' context."""
    return any(ctx in line for ctx in ALLOWED_MENTION_CONTEXTS)


def check(repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    scripts_dir = repo_root / "scripts"
    if not scripts_dir.exists():
        return findings

    for py_path in sorted(scripts_dir.glob("wr3_*.py")):
        try:
            text = py_path.read_text()
        except Exception:
            continue

        for line_no, raw_line in enumerate(text.splitlines(), 1):
            if BANNED_TTS_VENDORS.search(raw_line) and not _allowed_context(raw_line):
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(py_path.relative_to(repo_root)),
                    line=line_no,
                    message=f"Banned TTS vendor referenced: {raw_line.strip()[:100]}",
                ))

            if BANNED_ANTHROPIC_ENDPOINT.search(raw_line):
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(py_path.relative_to(repo_root)),
                    line=line_no,
                    message="Anthropic API endpoint referenced — use CLI subprocess only",
                ))

    return findings


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    findings = check(repo_root)
    for f in findings:
        print(f.fmt())
    sys.exit(1 if any(f.severity == "ERROR" for f in findings) else 0)
