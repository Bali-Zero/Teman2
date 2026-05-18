#!/usr/bin/env python3
"""WR3 Lint — Law 2 (OSINT blindato).

Symbiosis Law 2: NotebookLM source_ids NEVER leak to downstream artifacts
(brief.json, script.json, episode_manifest.json). The ONLY agent allowed to
read NB is `wr3-brief-interpreter` — its contract YAML must declare it
and no other agent's contract.

Checks:
  1. Only wr3-brief-interpreter.yaml has `inputs[]` of kind "in_memory_obj" with
     source containing "NotebookLM" / "notebooklm" / "mcp__notebooklm" / "nlm".
  2. scripts/wr3_nlm_subprocess.py is imported ONLY by:
       - scripts/wr3_supervisor.py (does NOT use NLM directly)
       - scripts/wr3_dispatch_agent.py (does NOT use NLM directly)
       - external orchestration (~/.claude/agents/wr3-brief-interpreter.md only)
     For now we just check no OTHER wr3_*.py file imports it directly.
  3. No `source_ids` field appears in brief.json / manifest schema definitions
     in docs/wr3/contracts/*.yaml.
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

LAW_NUMBER = 2
LAW_NAME = "OSINT blindato"

NB_PATTERNS = re.compile(r"NotebookLM|notebooklm|mcp__notebooklm|\bnlm\b", re.IGNORECASE)
SOURCE_IDS_LEAK = re.compile(r"\bsource_ids\b")


def check(repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    contracts_dir = repo_root / "docs" / "wr3" / "contracts"
    if not contracts_dir.exists():
        return findings

    # 1. NB access declared ONLY in brief-interpreter contract
    for yaml_path in sorted(contracts_dir.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        try:
            text = yaml_path.read_text()
        except Exception:
            continue

        has_nb_reference = bool(NB_PATTERNS.search(text))
        is_brief_interpreter = yaml_path.name == "brief-interpreter.yaml"

        if has_nb_reference and not is_brief_interpreter:
            findings.append(LintFinding(
                severity="ERROR",
                law=LAW_NUMBER,
                file=str(yaml_path.relative_to(repo_root)),
                line=None,
                message=f"NB reference found in {yaml_path.name} — only brief-interpreter may read NotebookLM",
            ))

    # 2. wr3_nlm_subprocess.py imported only by allowed scripts
    scripts_dir = repo_root / "scripts"
    if scripts_dir.exists():
        allowed_importers = {"wr3_supervisor.py", "wr3_dispatch_agent.py"}
        for py_path in sorted(scripts_dir.glob("wr3_*.py")):
            if py_path.name in allowed_importers or py_path.name == "wr3_nlm_subprocess.py":
                continue
            try:
                text = py_path.read_text()
            except Exception:
                continue
            if "wr3_nlm_subprocess" in text or "from wr3_nlm" in text:
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(py_path.relative_to(repo_root)),
                    line=None,
                    message=f"{py_path.name} imports wr3_nlm_subprocess — only brief-interpreter path allowed",
                ))

    # 3. `source_ids` field must NOT appear in any output schema declarations
    #    (it should ONLY appear in nb_source_ids.private.json which is Pro-side)
    for yaml_path in sorted(contracts_dir.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        try:
            text = yaml_path.read_text()
        except Exception:
            continue

        for line_no, line in enumerate(text.splitlines(), 1):
            # Allow inside a comment OR if it's nb_source_ids.private.json sink
            if "nb_source_ids.private.json" in line:
                continue
            stripped = line.split("#", 1)[0]
            if SOURCE_IDS_LEAK.search(stripped):
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(yaml_path.relative_to(repo_root)),
                    line=line_no,
                    message=f"source_ids field declared outside private sink: {line.strip()[:80]}",
                ))

    return findings


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    findings = check(repo_root)
    for f in findings:
        print(f.fmt())
    sys.exit(1 if any(f.severity == "ERROR" for f in findings) else 0)
