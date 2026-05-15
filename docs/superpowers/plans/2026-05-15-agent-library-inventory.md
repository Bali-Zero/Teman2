# Agent Library Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `agent-library/_generate-inventory.py` that auto-generates `agent-library/01-inventory.md` — a complete operational snapshot of every agent in the Nuzantara stack.

**Architecture:** Pure Python I/O script (no network, no LLM, no secrets) that reads `.claude/agents/*.md`, LaunchAgent plists via `plutil`, skill frontmatter, and cross-tool configs; classifies crons as agentic/infra; emits flat sectioned markdown with a Quick index and Drift warnings. The output file is committed to git; humans regenerate it on demand via `make inventory` or a pre-commit hook.

**Tech Stack:** Python 3.11, PyYAML, `subprocess` (plutil/launchctl), `pathlib`, `re`, `datetime`

**Design spec:** `docs/superpowers/specs/2026-05-14-agent-library-inventory-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `agent-library/_generate-inventory.py` | Create | Generator script — reads stack, writes 01-inventory.md |
| `agent-library/01-inventory.md` | Create (generated) | Output artifact — never hand-edited |
| `Makefile` | Modify | Add `inventory` target |

---

## Task 1: Bootstrap directory + smoke skeleton

**Files:**
- Create: `agent-library/_generate-inventory.py`
- Create: `agent-library/01-inventory.md` (empty placeholder, overwritten in Task 5)

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/agent-library
```

- [ ] **Step 2: Write the skeleton script** (exits 0, writes nothing yet — just imports + constants)

Create `agent-library/_generate-inventory.py`:

```python
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


def main(dry_run: bool = False) -> int:
    subagents = scan_subagents()
    cross_tool = scan_cross_tool()
    crons = scan_crons()
    skills = scan_skills()
    drift = compute_drift(subagents, crons)
    content = render(subagents, cross_tool, crons, skills, drift)
    if dry_run:
        print(content)
    else:
        OUTPUT_FILE.write_text(content, encoding="utf-8")
        print(f"Written: {OUTPUT_FILE} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry_run))
```

- [ ] **Step 3: Run smoke — exits 0**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 agent-library/_generate-inventory.py --dry-run
```

Expected: `NameError: name 'scan_subagents' is not defined` (stubs missing) — that's fine. We verify Python can parse the file:

```bash
python3 -c "import ast; ast.parse(open('agent-library/_generate-inventory.py').read()); print('parse OK')"
```

Expected: `parse OK`

- [ ] **Step 4: Commit skeleton**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add agent-library/_generate-inventory.py
git commit -m "feat(agent-library): add generator script skeleton"
```

---

## Task 2: Implement scan_subagents()

**Files:**
- Modify: `agent-library/_generate-inventory.py` — add `scan_subagents()`

- [ ] **Step 1: Write a quick manual test**

```bash
# Verify the agents dir has the expected files
ls ~/.claude/agents/*.md | wc -l
# Expected: ~19 (14 agent .md + some .md.pre-T2 variants)
ls ~/.claude/agents/*.md | grep -v pre-T2 | wc -l
# Expected: ~14 clean agent files
```

- [ ] **Step 2: Add `scan_subagents()` to the script**

Insert after the constants block, before `main()`:

```python
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
```

- [ ] **Step 3: Add a debug call to `main()` temporarily**

Replace the `main()` body temporarily:

```python
def main(dry_run: bool = False) -> int:
    subagents = scan_subagents()
    for a in subagents:
        print(f"  {a['name']:40s} model={a['model']}")
    return 0
```

- [ ] **Step 4: Run and verify output**

```bash
python3 agent-library/_generate-inventory.py --dry-run
```

Expected: 10-16 lines, each showing an agent name and model. No traceback.

- [ ] **Step 5: Commit**

```bash
git add agent-library/_generate-inventory.py
git commit -m "feat(agent-library): implement scan_subagents()"
```

---

## Task 3: Implement scan_crons()

**Files:**
- Modify: `agent-library/_generate-inventory.py` — add `scan_crons()`

This is the most complex step — reads plists via `plutil -convert json`.

- [ ] **Step 1: Manual smoke for plutil**

```bash
plutil -convert json -o - ~/Library/LaunchAgents/com.balizero.regulatory-watcher.daily.plist | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('StartCalendarInterval'), d.get('Program','')[:60])"
```

Expected: something like `{'Hour': 7, 'Minute': 0} /Users/nuzantara/scripts/...`

- [ ] **Step 2: Add `scan_crons()` to the script**

```python
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
    prog = plist_dict.get("Program", "")
    if not prog:
        args = plist_dict.get("ProgramArguments", [])
        prog = args[0] if args else ""
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
```

- [ ] **Step 3: Update `main()` debug block**

```python
def main(dry_run: bool = False) -> int:
    crons = scan_crons()
    agentic = [c for c in crons if c["agentic"]]
    infra = [c for c in crons if not c["agentic"]]
    print(f"Agentic crons: {len(agentic)}, Infra crons: {len(infra)}")
    for c in crons[:5]:
        print(f"  {c['label']:50s} {c['schedule']:15s} agentic={c['agentic']}")
    return 0
```

- [ ] **Step 4: Run and verify**

```bash
python3 agent-library/_generate-inventory.py --dry-run
```

Expected:
```
Agentic crons: <N>, Infra crons: <M>
  com.balizero.bz-daily-visual-pipeline        ...
```

No traceback. Counts should be plausible (~10-15 agentic, ~50+ total).

- [ ] **Step 5: Commit**

```bash
git add agent-library/_generate-inventory.py
git commit -m "feat(agent-library): implement scan_crons() with agentic/infra split"
```

---

## Task 4: Implement scan_cross_tool() and scan_skills()

**Files:**
- Modify: `agent-library/_generate-inventory.py`

- [ ] **Step 1: Add both scanners**

```python
def scan_cross_tool() -> list[dict[str, Any]]:
    """Scan Cursor rules and Gemini skills."""
    results = []
    for p in sorted(CURSOR_RULES_DIR.glob("**/*.mdc")):
        fm = parse_frontmatter(p)
        results.append({
            "name": fm.get("description", p.stem)[:60],
            "type": "cursor-rule",
            "path": str(p.relative_to(REPO_ROOT)),
        })
    for p in sorted(GEMINI_SKILLS_DIR.glob("**/*.md")):
        fm = parse_frontmatter(p)
        results.append({
            "name": fm.get("name", p.stem),
            "type": "gemini-skill",
            "path": str(p),
        })
    return results


def scan_skills() -> list[dict[str, Any]]:
    """Scan ~/.claude/skills/**/*.md for skill frontmatter."""
    results = []
    for p in sorted(SKILLS_DIR.glob("**/*.md")):
        fm = parse_frontmatter(p)
        if not fm:
            continue
        results.append({
            "name": fm.get("name", p.stem),
            "description": (fm.get("description") or "")[:100],
            "path": str(p),
        })
    return results
```

- [ ] **Step 2: Update `main()` debug block**

```python
def main(dry_run: bool = False) -> int:
    subagents = scan_subagents()
    cross_tool = scan_cross_tool()
    crons = scan_crons()
    skills = scan_skills()
    print(f"subagents={len(subagents)} cross_tool={len(cross_tool)} crons={len(crons)} skills={len(skills)}")
    return 0
```

- [ ] **Step 3: Run and verify**

```bash
python3 agent-library/_generate-inventory.py --dry-run
```

Expected: `subagents=N cross_tool=M crons=P skills=Q` — all > 0. No traceback.

- [ ] **Step 4: Commit**

```bash
git add agent-library/_generate-inventory.py
git commit -m "feat(agent-library): implement scan_cross_tool() and scan_skills()"
```

---

## Task 5: Implement compute_drift() and render()

**Files:**
- Modify: `agent-library/_generate-inventory.py` — add `compute_drift()` + `render()`
- Create: `agent-library/01-inventory.md` (first real output)

- [ ] **Step 1: Add `compute_drift()`**

```python
import time as _time

STALE_DAYS = 90


def compute_drift(
    subagents: list[dict[str, Any]],
    crons: list[dict[str, Any]],
) -> dict[str, list[str]]:
    now = _time.time()
    stale_cutoff = now - STALE_DAYS * 86400
    missing_frontmatter = [a["path"] for a in subagents if not a["frontmatter_ok"]]
    orphaned_plists = [c["label"] for c in crons if c["script"] and not c["script_exists"]]
    stale_agents = [a["name"] for a in subagents if a["mtime"] < stale_cutoff]
    return {
        "missing_frontmatter": missing_frontmatter,
        "orphaned_plists": orphaned_plists,
        "stale_agents": stale_agents,
    }
```

- [ ] **Step 2: Add `render()`**

```python
def _tools_str(tools: list[str] | str | None) -> str:
    if not tools:
        return ""
    if isinstance(tools, str):
        return tools
    return ", ".join(tools[:4]) + ("…" if len(tools) > 4 else "")


def render(
    subagents: list[dict[str, Any]],
    cross_tool: list[dict[str, Any]],
    crons: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    drift: dict[str, list[str]],
) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M WITA")
    lines: list[str] = []

    lines += [
        f"# Agent Library — Inventory (auto-generated {ts})",
        "",
        "<!-- regenerate: python3 agent-library/_generate-inventory.py -->",
        "<!-- DO NOT hand-edit — changes will be overwritten -->",
        "",
    ]

    # Quick index (all agents flat)
    lines += ["## Quick index", ""]
    lines += ["| Name | Type | Model | Tools |", "|---|---|---|---|"]
    for a in subagents:
        lines.append(f"| {a['name']} | subagent | {a['model']} | {_tools_str(a['tools'])} |")
    for c in cross_tool:
        lines.append(f"| {c['name']} | {c['type']} | — | — |")
    for s in skills:
        lines.append(f"| {s['name']} | skill | — | — |")
    lines.append("")

    # Claude Code subagents
    lines += ["## Claude Code subagents", ""]
    for a in subagents:
        lines += [
            f"### {a['name']}",
            f"- **Model**: {a['model'] or '(not set)'}",
            f"- **Tools**: {_tools_str(a['tools']) or '(not set)'}",
            f"- **Description**: {a['description'] or '(missing)'}",
            f"- **File**: `{a['path']}`",
            "",
        ]

    # Cross-tool agents
    lines += ["## Cross-tool agents", ""]
    if cross_tool:
        for c in cross_tool:
            lines.append(f"- **{c['name']}** ({c['type']}) — `{c['path']}`")
    else:
        lines.append("_(none found)_")
    lines.append("")

    # Cron-agents
    agentic_crons = [c for c in crons if c["agentic"]]
    infra_crons = [c for c in crons if not c["agentic"]]

    lines += ["## Cron-agents", "", "### Agentic crons _(call an LLM)_", ""]
    lines += ["| Label | Schedule | Script |", "|---|---|---|"]
    for c in agentic_crons:
        script_short = Path(c["script"]).name if c["script"] else "—"
        lines.append(f"| {c['label']} | {c['schedule']} | `{script_short}` |")
    lines += ["", "### Infrastructure crons _(no LLM)_", ""]
    lines += ["| Label | Schedule | Script |", "|---|---|---|"]
    for c in infra_crons:
        script_short = Path(c["script"]).name if c["script"] else "—"
        lines.append(f"| {c['label']} | {c['schedule']} | `{script_short}` |")
    lines.append("")

    # Skills
    lines += ["## Skills", ""]
    for s in skills:
        lines.append(f"- **{s['name']}** — {s['description']} (`{Path(s['path']).name}`)")
    lines.append("")

    # Drift warnings
    lines += ["## Drift warnings", ""]
    total_issues = sum(len(v) for v in drift.values())
    if total_issues == 0:
        lines.append("_No drift detected._")
    else:
        if drift["missing_frontmatter"]:
            lines.append("**Missing YAML frontmatter:**")
            for p in drift["missing_frontmatter"]:
                lines.append(f"- `{p}`")
        if drift["orphaned_plists"]:
            lines.append("**Orphaned plists (script not on disk):**")
            for label in drift["orphaned_plists"]:
                lines.append(f"- `{label}`")
        if drift["stale_agents"]:
            lines.append(f"**Stale agents (mtime >{STALE_DAYS}d):**")
            for name in drift["stale_agents"]:
                lines.append(f"- {name}")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: Restore final `main()` body**

```python
def main(dry_run: bool = False) -> int:
    subagents = scan_subagents()
    cross_tool = scan_cross_tool()
    crons = scan_crons()
    skills = scan_skills()
    drift = compute_drift(subagents, crons)
    content = render(subagents, cross_tool, crons, skills, drift)
    if dry_run:
        print(content)
    else:
        OUTPUT_FILE.write_text(content, encoding="utf-8")
        print(f"Written: {OUTPUT_FILE} ({len(content)} bytes)")
    return 0
```

- [ ] **Step 4: Run dry-run smoke**

```bash
python3 agent-library/_generate-inventory.py --dry-run 2>&1 | head -40
```

Expected: header line, blank, `<!-- regenerate -->`, Quick index table. No traceback.

- [ ] **Step 5: Run for real + verify output**

```bash
python3 agent-library/_generate-inventory.py
wc -l agent-library/01-inventory.md
grep -c "Drift" agent-library/01-inventory.md
```

Expected:
- `wc -l`: ≥ 80 lines
- `grep -c "Drift"`: ≥ 1

- [ ] **Step 6: Commit both script and generated artifact**

```bash
git add agent-library/_generate-inventory.py agent-library/01-inventory.md
git commit -m "feat(agent-library): implement render pipeline + generate 01-inventory.md"
```

---

## Task 6: Add Makefile target + pre-commit hook (optional)

**Files:**
- Modify: `Makefile` (root)

- [ ] **Step 1: Check if Makefile exists and look at its structure**

```bash
head -20 /Users/nuzantara/Desktop/nuzantara/Makefile 2>/dev/null || echo "NO_MAKEFILE"
```

- [ ] **Step 2: Add `inventory` target**

If Makefile exists, append:

```makefile
.PHONY: inventory
inventory:
	python3 agent-library/_generate-inventory.py
```

If no Makefile, create it with just this target.

- [ ] **Step 3: Test the target**

```bash
cd /Users/nuzantara/Desktop/nuzantara && make inventory
```

Expected: `Written: .../agent-library/01-inventory.md (NNNN bytes)`

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "chore(agent-library): add make inventory target"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run full smoke suite**

```bash
cd /Users/nuzantara/Desktop/nuzantara

# Smoke 1: dry-run exits 0
python3 agent-library/_generate-inventory.py --dry-run > /dev/null && echo "DRY_RUN OK"

# Smoke 2: real run produces file
python3 agent-library/_generate-inventory.py && echo "WRITE OK"
wc -l agent-library/01-inventory.md

# Smoke 3: required sections present
for section in "Quick index" "Claude Code subagents" "Cross-tool" "Cron-agents" "Skills" "Drift warnings"; do
  grep -q "$section" agent-library/01-inventory.md && echo "SECTION OK: $section" || echo "MISSING: $section"
done

# Smoke 4: make target
make inventory && echo "MAKE OK"
```

Expected: all lines end with `OK`.

- [ ] **Step 2: Sanity-check the generated file manually**

```bash
cat agent-library/01-inventory.md
```

Read through and confirm:
- Header has today's date
- Quick index has ≥ 10 rows
- Agentic crons include crons with `claude`/`nlm`/`gemini` in their script
- Infra crons are plausible (pg-proxy, deploy-puller, etc.)
- Drift warnings section is present (even if "_No drift detected._")

- [ ] **Step 3: Commit any final fixes, then push**

```bash
git push origin fix/wa-mirror-reconnect-loop-2026-05-14
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Covered by |
|---|---|
| Scan 16 Claude subagents | Task 2 `scan_subagents()` |
| Scan cross-tool agents (Cursor/Gemini) | Task 4 `scan_cross_tool()` |
| Scan crons with agentic/infra split | Task 3 `scan_crons()` |
| Scan skills | Task 4 `scan_skills()` |
| Quick index flat table | Task 5 `render()` |
| Drift warnings (3 types) | Task 5 `compute_drift()` + `render()` |
| `make inventory` target | Task 6 |
| No network/LLM/secrets | All tasks — `_is_agentic()` reads only first 30 lines from disk |
| `--dry-run` flag | Task 1 skeleton, fully wired in Task 5 |
| Regenerate timestamp in header | Task 5 `render()` |

**Placeholder scan:** No TBDs, no "add appropriate error handling" — all error handling is explicit (parse failures → warn + return `{}`; subprocess failures → return `{}`; file not found → `False`).

**Type consistency:** `subagents` is `list[dict]` throughout; `crons` same; `drift` is `dict[str, list[str]]` from `compute_drift()` → consumed verbatim in `render()`. No name mismatches.
