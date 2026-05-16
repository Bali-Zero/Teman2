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
AUTOMATION_CATALOG = REPO_ROOT / "scripts" / "automation_catalog.json"
OUTPUT_FILE = Path(__file__).parent / "01-inventory.md"

LAUNCHAGENT_PREFIXES = ("com.balizero.", "com.nuzantara.", "com.cell.", "com.matagaruda.")

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
    """Scan Cursor rules and Gemini skills."""
    results = []
    if CURSOR_RULES_DIR.is_dir():
        for p in sorted(CURSOR_RULES_DIR.glob("**/*.mdc")):
            if not p.is_file():
                continue
            fm = parse_frontmatter(p)
            name = (fm.get("description") or p.stem)[:60]
            results.append({
                "name": name,
                "type": "cursor-rule",
                "path": str(p.relative_to(REPO_ROOT)),
            })
    if GEMINI_SKILLS_DIR.is_dir():
        for p in sorted(GEMINI_SKILLS_DIR.glob("**/*.md")):
            if not p.is_file():
                continue
            fm = parse_frontmatter(p)
            if not fm:
                continue
            results.append({
                "name": fm.get("name", p.stem),
                "type": "gemini-skill",
                "path": str(p),
            })
    return results


_SCRIPT_SUFFIXES = (".sh", ".py", ".zsh", ".bash")
_INTERPRETERS = {"/bin/sh", "/bin/bash", "/bin/zsh", "/usr/bin/env", "/usr/bin/python3"}
_INTERPRETER_BASENAMES = {
    "python", "python3", "python3.11", "bash", "zsh", "sh", "env", "exec",
    "uvicorn", "uv", "node",
}


def _is_interpreter(path: str) -> bool:
    if path in _INTERPRETERS:
        return True
    name = Path(path).name
    return name in _INTERPRETER_BASENAMES


def _plist_to_json(plist_path: Path) -> dict[str, Any]:
    """Convert plist to dict via plutil. Returns {} on failure."""
    try:
        result = subprocess.run(
            ["plutil", "-convert", "json", "-o", "-", str(plist_path)],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except Exception:
        return {}


def _fmt_calendar_entry(entry: dict[str, Any]) -> str:
    """Format one StartCalendarInterval dict as 'weekly[dN]@HH:MM' or 'daily@HH:MM'."""
    weekday = entry.get("Weekday")
    h = entry.get("Hour")
    m = entry.get("Minute", 0)
    h_s = f"{h:02}" if isinstance(h, int) else "*"
    m_s = f"{m:02}" if isinstance(m, int) else "00"
    if weekday is not None:
        return f"weekly[d{weekday}]@{h_s}:{m_s}"
    return f"daily@{h_s}:{m_s}"


def _schedule_str(plist_dict: dict[str, Any]) -> str:
    """Human-readable schedule from plist dict.

    For multi-interval `StartCalendarInterval` lists, joins each entry with `;`
    up to a cap of 4 (further intervals collapsed to `…+N`) — fixes the
    `calendar×N` data-loss spotted in the review.
    """
    if "StartCalendarInterval" in plist_dict:
        sci = plist_dict["StartCalendarInterval"]
        if isinstance(sci, list):
            parts = [_fmt_calendar_entry(e) for e in sci if isinstance(e, dict)]
            if not parts:
                return f"calendar×{len(sci)}"
            shown, hidden = parts[:4], len(parts) - 4
            return ";".join(shown) + (f"…+{hidden}" if hidden > 0 else "")
        if isinstance(sci, dict):
            return _fmt_calendar_entry(sci)
        return "calendar"
    if "StartInterval" in plist_dict:
        try:
            s = int(plist_dict["StartInterval"])
        except (TypeError, ValueError):
            return "interval"
        if s < 120:
            return f"every {s}s"
        if s < 3600:
            return f"every {s // 60}min"
        return f"every {s // 3600}h"
    if plist_dict.get("RunAtLoad"):
        return "run-at-load"
    return "on-demand"


def _collect_script_candidates(plist_dict: dict[str, Any]) -> list[str]:
    """Collect all script-like absolute paths from Program + ProgramArguments,
    including tokens extracted from shell-string args (`-c` payloads).

    Bare ProgramArguments paths are accepted unconditionally (after the
    interpreter filter) — they're positional, the caller intended them as the
    workload. Tokens parsed from shell strings are stricter: only kept if
    they end in a recognized script suffix, otherwise we'd capture redirect
    targets / state files / arbitrary args. See review:
    com.nuzantara.pg-proxy-cluster-recheck-oneshot regressed when the
    `>> /Users/.../state.txt` redirect target was captured as the workload.
    """
    args = list(plist_dict.get("ProgramArguments") or [])
    program = plist_dict.get("Program", "") or ""
    bare = ([program] if program else []) + args
    out: list[str] = []
    seen: set[str] = set()

    def _add(s: str, require_suffix: bool = False) -> None:
        if not s or s in seen:
            return
        if not s.startswith("/") or _is_interpreter(s):
            return
        if require_suffix and not s.endswith(_SCRIPT_SUFFIXES):
            return
        out.append(s)
        seen.add(s)

    for a in bare:
        if not isinstance(a, str) or " " in a:
            continue
        _add(a, require_suffix=False)

    for a in args:
        if not isinstance(a, str) or " " not in a:
            continue
        for tok in a.split():
            t = tok.strip("`'\";|&()<>")
            _add(t, require_suffix=True)
    return out


def _script_matches_agentic(path_str: str) -> bool:
    """Header-only agentic check used to disambiguate ambiguous shell chains."""
    return _is_agentic(path_str)


def _script_path(plist_dict: dict[str, Any]) -> str:
    """Pick the real workload script from Program/ProgramArguments.

    Strategy:
      1. Gather all absolute-path script-like candidates from Program +
         ProgramArguments (including sub-tokens of `-c` shell strings).
      2. Prefer candidates that EXIST on disk; among those, prefer the first
         one whose header matches an agentic keyword (handles `wrapper.sh &&
         real-agent.py` correctly — review HIGH#1).
      3. If no existing candidate, fall back to the first suffix-matching
         path (still useful: surfaces drift via `script_exists=False`).
      4. Last resort: Program or first ProgramArguments arg (interpreter).

    Relative paths are deliberately ignored (review MEDIUM: relative `setup.sh`
    in ProgramArguments used to surface as a false orphan-plist warning).
    """
    candidates = _collect_script_candidates(plist_dict)

    existing = [c for c in candidates if Path(c).exists()]
    if existing:
        # Disambiguate chained shell scripts: if more than one workload exists
        # on disk, prefer the one that actually calls an LLM.
        if len(existing) > 1:
            for c in existing:
                if _script_matches_agentic(c):
                    return c
        return existing[0]

    suffix_match = [c for c in candidates if c.endswith(_SCRIPT_SUFFIXES)]
    if suffix_match:
        return suffix_match[0]

    if candidates:
        return candidates[0]

    args = list(plist_dict.get("ProgramArguments") or [])
    program = plist_dict.get("Program", "") or ""
    if program:
        return program
    return args[0] if args else ""


def _is_agentic(script_path_str: str) -> bool:
    """Check if a cron script calls an LLM. Reads first 30 lines only.

    Privacy: no full-file read, no external lookups.
    """
    if not script_path_str:
        return False
    p = Path(script_path_str)
    if not p.exists() or not p.is_file():
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


def _load_automation_catalog() -> dict[str, dict[str, Any]]:
    """Read the curated launchagents section of scripts/automation_catalog.json.

    Returns label → catalog-entry dict. Missing/malformed file → empty dict.
    """
    if not AUTOMATION_CATALOG.is_file():
        return {}
    try:
        data = json.loads(AUTOMATION_CATALOG.read_text(encoding="utf-8"))
        section = data.get("launchagents", {})
        return section if isinstance(section, dict) else {}
    except Exception as e:
        print(f"  WARN: automation_catalog.json read failed: {e}", file=sys.stderr)
        return {}


def scan_crons() -> list[dict[str, Any]]:
    """Scan all com.{balizero,nuzantara,cell,matagaruda}.*.plist in ~/Library/LaunchAgents.

    Enriches each entry with a `catalog_note` (curated metadata from
    scripts/automation_catalog.json `launchagents` section) and a `prefix`
    field (one of LAUNCHAGENT_PREFIXES, trailing dot stripped).
    """
    results = []
    if not LAUNCHAGENTS_DIR.is_dir():
        return results
    catalog = _load_automation_catalog()
    seen_paths = set()
    for prefix in LAUNCHAGENT_PREFIXES:
        for p in sorted(LAUNCHAGENTS_DIR.glob(f"{prefix}*.plist")):
            # Skip .disabled-* variants (filename does not end in .plist anyway —
            # glob handles that — but guard against future shapes).
            if ".disabled" in p.name:
                continue
            if str(p) in seen_paths:
                continue
            seen_paths.add(str(p))
            pdict = _plist_to_json(p)
            if not pdict:
                continue
            label = pdict.get("Label", p.stem)
            script = _script_path(pdict)
            script_exists = bool(script) and Path(script).exists()
            entry = catalog.get(label, {})
            results.append({
                "label": label,
                "prefix": prefix.rstrip("."),
                "schedule": _schedule_str(pdict),
                "script": script,
                "agentic": _is_agentic(script),
                "script_exists": script_exists,
                "plist_path": str(p),
                "catalog_note": entry.get("description", "") if isinstance(entry, dict) else "",
                "catalog_type": entry.get("type", "") if isinstance(entry, dict) else "",
            })
    results.sort(key=lambda r: r["label"])
    return results


def scan_skills() -> list[dict[str, Any]]:
    """Scan ~/.claude/skills/**/*.md for skill frontmatter."""
    results = []
    if not SKILLS_DIR.is_dir():
        return results
    for p in sorted(SKILLS_DIR.glob("**/*.md")):
        if not p.is_file():
            continue
        if any(suffix in p.name for suffix in (".pre-T1", ".pre-T2", ".bak-", ".disabled")):
            continue
        fm = parse_frontmatter(p)
        if not fm:
            continue
        results.append({
            "name": fm.get("name", p.stem),
            "description": (fm.get("description") or "")[:100],
            "path": str(p),
        })
    return results


def compute_drift(
    subagents: list[dict[str, Any]],
    crons: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Surface three classes of drift for the inventory health-check section.

    Idempotency: `now` is rounded to the start of the current UTC minute so
    that two back-to-back runs within the same minute use the same stale
    cutoff and produce byte-identical output (Gemini Important).
    """
    now = (int(_time.time()) // 60) * 60
    stale_cutoff = now - STALE_DAYS * 86400
    missing_frontmatter = sorted(
        a["path"] for a in subagents if not a["frontmatter_ok"]
    )
    orphaned_plists = sorted(
        c["label"] for c in crons if c["script"] and not c["script_exists"]
    )
    stale_agents = sorted(
        a["name"] for a in subagents if a["mtime"] < stale_cutoff
    )
    return {
        "missing_frontmatter": missing_frontmatter,
        "orphaned_plists": orphaned_plists,
        "stale_agents": stale_agents,
    }


def _tools_str(tools: Any) -> str:
    """Render the agent `tools` frontmatter field defensively.

    Empirically, Claude Code subagent frontmatter ships `tools:` as either a
    comma-separated string OR a YAML list. Defensive against unexpected types
    (bool/dict/int) — DeepSeek CRITICAL: crashed on `tools: true`.
    """
    if tools is None or tools == "":
        return ""
    if isinstance(tools, str):
        return tools
    if isinstance(tools, list):
        text_items = [str(t) for t in tools if t is not None]
        return ", ".join(text_items[:4]) + ("…" if len(text_items) > 4 else "")
    # Unexpected shape (bool, dict, int): stringify, truncate, surface to user.
    return str(tools)[:60]


def _md_escape(text: str) -> str:
    """Pipe-escape for markdown table cells. Compact whitespace."""
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _flatten(text: str) -> str:
    """Flatten newlines into single-space for bullet-list rendering.

    Gemini Minor: subagent descriptions written as YAML block scalars contain
    `\n` which break the markdown bullet layout.
    """
    if not text:
        return ""
    return " ".join(text.split())


def render(
    subagents: list[dict[str, Any]],
    cross_tool: list[dict[str, Any]],
    crons: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    drift: dict[str, list[str]],
) -> str:
    """Render the inventory markdown. Output is deterministic given inputs
    except for the header timestamp (truncated to minute)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M WITA")
    lines: list[str] = [
        f"# Agent Library — Inventory (auto-generated {ts})",
        "",
        "<!-- regenerate: python3 agent-library/_generate-inventory.py -->",
        "<!-- DO NOT hand-edit — changes will be overwritten -->",
        "",
        f"**Snapshot**: {len(subagents)} Claude subagents · "
        f"{len([c for c in crons if c['agentic']])} agentic crons / "
        f"{len([c for c in crons if not c['agentic']])} infra crons "
        f"({len(crons)} total launchd) · "
        f"{len(skills)} skills · {len(cross_tool)} cross-tool entries",
        "",
    ]

    # Quick index — flat table for grep/Cmd-F
    lines += [
        "## Quick index",
        "",
        "| Name | Type | Model | Tools |",
        "|---|---|---|---|",
    ]
    for a in subagents:
        lines.append(
            f"| {_md_escape(a['name'])} | subagent | {_md_escape(a['model'] or '—')} | "
            f"{_md_escape(_tools_str(a['tools']) or '—')} |"
        )
    for c in cross_tool:
        lines.append(f"| {_md_escape(c['name'])} | {c['type']} | — | — |")
    for s in skills:
        lines.append(f"| {_md_escape(s['name'])} | skill | — | — |")
    lines.append("")

    # Claude Code subagents — block per agent
    lines += ["## Claude Code subagents", ""]
    if not subagents:
        lines += ["_(none found)_", ""]
    for a in subagents:
        lines += [
            f"### {a['name']}",
            "",
            f"- **Model**: {a['model'] or '(not set)'}",
            f"- **Tools**: {_tools_str(a['tools']) or '(not set)'}",
            f"- **Description**: {_flatten(a['description']) or '(missing)'}",
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

    # Cron-agents — agentic vs infra
    agentic_crons = [c for c in crons if c["agentic"]]
    infra_crons = [c for c in crons if not c["agentic"]]

    lines += ["## Cron-agents", ""]
    prefix_counts = {pref.rstrip("."): 0 for pref in LAUNCHAGENT_PREFIXES}
    for c in crons:
        prefix_counts[c.get("prefix", "")] = prefix_counts.get(c.get("prefix", ""), 0) + 1
    breakdown = " · ".join(f"{pref}={cnt}" for pref, cnt in prefix_counts.items() if cnt)
    lines += [f"_Prefix breakdown: {breakdown}_", ""]

    lines += [
        f"### Agentic crons ({len(agentic_crons)}) _(call an LLM)_",
        "",
        "| Label | Schedule | Script | Catalog note |",
        "|---|---|---|---|",
    ]
    for c in agentic_crons:
        script_short = Path(c["script"]).name if c["script"] else "—"
        note = _md_escape((c.get("catalog_note") or "")[:80]) or "—"
        lines.append(
            f"| {_md_escape(c['label'])} | {c['schedule']} | "
            f"`{_md_escape(script_short)}` | {note} |"
        )
    lines += [
        "",
        f"### Infrastructure crons ({len(infra_crons)}) _(no LLM)_",
        "",
        "| Label | Schedule | Script | Catalog note |",
        "|---|---|---|---|",
    ]
    for c in infra_crons:
        script_short = Path(c["script"]).name if c["script"] else "—"
        note = _md_escape((c.get("catalog_note") or "")[:80]) or "—"
        lines.append(
            f"| {_md_escape(c['label'])} | {c['schedule']} | "
            f"`{_md_escape(script_short)}` | {note} |"
        )
    lines.append("")

    # Skills
    lines += ["## Skills", ""]
    if skills:
        for s in skills:
            lines.append(
                f"- **{s['name']}** — {_flatten(s['description'])} (`{Path(s['path']).name}`)"
            )
    else:
        lines.append("_(none found)_")
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
            lines.append("")
        if drift["orphaned_plists"]:
            lines.append("**Orphaned plists (script not on disk):**")
            for label in drift["orphaned_plists"]:
                lines.append(f"- `{label}`")
            lines.append("")
        if drift["stale_agents"]:
            lines.append(f"**Stale agents (mtime > {STALE_DAYS}d):**")
            for name in drift["stale_agents"]:
                lines.append(f"- {name}")
            lines.append("")
    lines.append("")

    return "\n".join(lines)


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
