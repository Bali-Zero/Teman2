#!/usr/bin/env python3
"""WR3 Lint — Law 1 (CLI-only LLM).

Symbiosis Law 1: All LLM calls go through CLI subprocess (`claude --print`,
`gemini --print`, `notebooklm-mcp`), NEVER via direct API SDK import like
`from anthropic import Anthropic`. DeepSeek API is the lone exception (Chinese
stack, no OAuth alternative).

This linter scans all `scripts/wr3_*.py` files for:
  - `from anthropic import` / `import anthropic`   → ERROR
  - `from openai import` / `import openai`         → ERROR (we don't ship paid OpenAI either)
  - `import google.generativeai`                   → ERROR (use gemini CLI)
  - `ANTHROPIC_API_KEY` env var read               → ERROR

Allowed:
  - `claude_agent_sdk` import (it's a CLI subprocess wrapper, Law 1 compliant)
  - `subprocess` / `asyncio.create_subprocess_*` for CLI invocations
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

LAW_NUMBER = 1
LAW_NAME = "CLI-only LLM"

BANNED_PATTERNS = [
    (re.compile(r"^\s*from\s+anthropic\s+import|^\s*import\s+anthropic\b"),
     "anthropic SDK direct import — use claude CLI subprocess instead"),
    (re.compile(r"^\s*from\s+openai\s+import|^\s*import\s+openai\b"),
     "openai SDK direct import — paid API banned per CLAUDE.md"),
    (re.compile(r"^\s*import\s+google\.generativeai|^\s*from\s+google\.generativeai\s+import"),
     "google.generativeai SDK — use gemini CLI subprocess instead"),
    (re.compile(r"ANTHROPIC_API_KEY"),
     "ANTHROPIC_API_KEY referenced — paid Anthropic API forbidden"),
]

# Imports that LOOK like SDK but are allowed (CLI wrappers)
ALLOWED_OVERRIDE = re.compile(r"claude_agent_sdk")


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
            stripped = raw_line.split("#", 1)[0]
            if ALLOWED_OVERRIDE.search(stripped):
                continue
            for pat, msg in BANNED_PATTERNS:
                if pat.search(stripped):
                    findings.append(LintFinding(
                        severity="ERROR",
                        law=LAW_NUMBER,
                        file=str(py_path.relative_to(repo_root)),
                        line=line_no,
                        message=msg,
                    ))

    return findings


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    findings = check(repo_root)
    for f in findings:
        print(f.fmt())
    sys.exit(1 if any(f.severity == "ERROR" for f in findings) else 0)
