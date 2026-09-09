"""Context-budget audit: measures the ALWAYS-INJECTED context surface of
this repo — bytes Claude Code loads into every session/subagent before the
first user turn. Rolls up test_superscar_budget.py + test_claude_md_budget.py's
individual caps into one TOTAL. `--live` adds machine-local `~/.claude`
categories for human diagnosis only — never paste that output, the
`auto_memory` slug identifies the operator's home directory. Ratio is an
empirical ballpark, not a tokenizer; ground truth is `/context`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BYTES_PER_TOKEN = 2.04

# root CLAUDE.md (full) · unscoped .claude/rules/*.md (full) · agents/skills/
# commands frontmatter only (body is lazy-loaded on dispatch).
REPO_CATEGORIES = ("root_claude_md", "unscoped_rules", "agents_frontmatter", "skills_listing")

# Machine-local mirrors, read Path.home() — --live only, never paste.
LIVE_CATEGORIES = (
    "global_claude_md", "auto_memory", "home_agents_frontmatter", "home_skills_listing",
)

_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")

def frontmatter_block(text: str) -> list[str] | None:
    """Lines between the opening/closing `---` of a leading YAML block, or
    `None` if `text` doesn't open with `---` or the block never closes."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return body
        body.append(line)
    return None

def has_paths_frontmatter(text: str) -> bool:
    """True if the frontmatter declares a `paths:` key (single- or
    multi-line list — only the key line matters)."""
    body = frontmatter_block(text)
    if body is None:
        return False
    return any(line.strip().startswith("paths:") for line in body)

def frontmatter_fields(text: str) -> dict[str, str]:
    """Top-level scalar frontmatter fields, quotes stripped, multi-line
    continuations joined with spaces. `{}` if there's no frontmatter."""
    body = frontmatter_block(text)
    if body is None:
        return {}
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in body:
        if line and not line[0].isspace():
            m = _FRONTMATTER_KEY_RE.match(line)
            if m:
                current_key = m.group(1)
                value = m.group(2).strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                fields[current_key] = value
                continue
        if current_key is not None:
            fields[current_key] = (fields[current_key] + " " + line.strip()).strip()
    return fields

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def _measure_frontmatter_glob(root: Path, pattern: str, *, include_tools: bool) -> tuple[int, int]:
    # (files, chars) contributed by frontmatter `name`+`description` (+
    # `tools`) only — the body is read lazily on dispatch, not at boot.
    files = 0
    total = 0
    if not root.is_dir():
        return (0, 0)
    for p in sorted(root.glob(pattern)):
        if not p.is_file():
            continue
        fields = frontmatter_fields(_read(p))
        if not fields:
            continue
        files += 1
        total += len(fields.get("name", "")) + len(fields.get("description", ""))
        if include_tools:
            total += len(fields.get("tools", ""))
    return (files, total)

def _measure_unscoped_rules(repo_root: Path) -> tuple[int, int]:
    rules_dir = repo_root / ".claude" / "rules"
    files = 0
    total = 0
    if not rules_dir.is_dir():
        return (0, 0)
    for p in sorted(rules_dir.glob("*.md")):
        if not p.is_file():
            continue
        text = _read(p)
        if not has_paths_frontmatter(text):
            files += 1
            total += p.stat().st_size
    return (files, total)

def _measure_whole_file(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (0, 0)
    return (1, path.stat().st_size)

def _memory_slug(repo_root: Path) -> str:
    # ~/.claude/projects/<slug>/memory/MEMORY.md's <slug>: resolved cwd with
    # every "/" -> "-". Keyed on repo_root so a worktree checkout reports
    # its own (usually absent) memory file, not the main checkout's.
    return str(repo_root.resolve()).replace("/", "-")

def _measure_agents_skills(claude_dir: Path) -> tuple[dict[str, int], dict[str, int]]:
    # Shared by the repo-scope pair (agents_frontmatter/skills_listing) and
    # the --live home_* mirrors — same glob shape under a different base.
    files, total = _measure_frontmatter_glob(claude_dir / "agents", "*.md", include_tools=True)
    agents = {"files": files, "bytes": total}
    skill_files, skill_total = _measure_frontmatter_glob(claude_dir / "skills", "*/SKILL.md", include_tools=False)
    cmd_files, cmd_total = _measure_frontmatter_glob(claude_dir / "commands", "*.md", include_tools=False)
    skills = {"files": skill_files + cmd_files, "bytes": skill_total + cmd_total}
    return agents, skills

def measure(repo_root: Path, live: bool = False) -> dict[str, dict[str, int]]:
    """Measure the always-injected context surface: `REPO_CATEGORIES`, then
    `LIVE_CATEGORIES` if `live`."""
    repo_root = Path(repo_root)
    result: dict[str, dict[str, int]] = {}

    files, total = _measure_whole_file(repo_root / "CLAUDE.md")
    result["root_claude_md"] = {"files": files, "bytes": total}

    files, total = _measure_unscoped_rules(repo_root)
    result["unscoped_rules"] = {"files": files, "bytes": total}

    result["agents_frontmatter"], result["skills_listing"] = _measure_agents_skills(repo_root / ".claude")

    if live:
        home = Path.home()

        files, total = _measure_whole_file(home / ".claude" / "CLAUDE.md")
        result["global_claude_md"] = {"files": files, "bytes": total}

        slug = _memory_slug(repo_root)
        mem_path = home / ".claude" / "projects" / slug / "memory" / "MEMORY.md"
        files, total = _measure_whole_file(mem_path)
        result["auto_memory"] = {"files": files, "bytes": total}

        result["home_agents_frontmatter"], result["home_skills_listing"] = _measure_agents_skills(home / ".claude")

    return result

def _est_tokens(num_bytes: int, bytes_per_token: float) -> int:
    return round(num_bytes / bytes_per_token)

def render_table(measurement: dict[str, dict[str, int]], bytes_per_token: float) -> str:
    lines: list[str] = []
    header = f"{'category':<26}{'files':>8}{'bytes':>12}{'est_tokens':>14}"
    lines.append(header)
    lines.append("-" * len(header))
    total_bytes = 0
    for category, stats in measurement.items():
        b = stats["bytes"]
        total_bytes += b
        lines.append(f"{category:<26}{stats['files']:>8}{b:>12,}{_est_tokens(b, bytes_per_token):>14,}")
    lines.append("-" * len(header))
    lines.append(f"{'TOTAL':<26}{'':>8}{total_bytes:>12,}{_est_tokens(total_bytes, bytes_per_token):>14,}")
    lines.append("")
    lines.append(f"ratio: {bytes_per_token} bytes/token (est. — true count via /context in a fresh session)")
    return "\n".join(lines)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure the always-injected context surface of this repo.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="checkout to measure")
    parser.add_argument("--live", action="store_true", help="also measure ~/.claude (never paste)")
    parser.add_argument("--bytes-per-token", type=float, default=DEFAULT_BYTES_PER_TOKEN)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--max-tokens", type=int, default=None, help="exit 1 if over this many")
    args = parser.parse_args(argv)

    measurement = measure(args.repo_root, live=args.live)
    total_bytes = sum(stats["bytes"] for stats in measurement.values())
    total_tokens = _est_tokens(total_bytes, args.bytes_per_token)

    if args.json:
        payload = {
            "categories": measurement,
            "total_bytes": total_bytes,
            "total_est_tokens": total_tokens,
            "bytes_per_token": args.bytes_per_token,
            "live": args.live,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_table(measurement, args.bytes_per_token))

    if args.max_tokens is not None and total_tokens > args.max_tokens:
        print(f"\nOVER BUDGET: est. {total_tokens:,} tokens > --max-tokens {args.max_tokens:,}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
