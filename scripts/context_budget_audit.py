"""
Context-budget audit: measures the ALWAYS-INJECTED context surface of this
repo — the bytes Claude Code loads into every session and every subagent
before the first user turn, regardless of what the task is about.

Context-diet (2026-09-04, mandate "B6: an audit script that measures the
always-injected context surface + a CI test that caps it"). Sibling guards
already exist for individual pieces of this surface —
`test_superscar_budget.py` caps `cicatrix-superscar.md`, `test_claude_md_budget.py`
caps `CLAUDE.md` (root + per-folder) and flags a `.claude/rules/*.md` file
that forgot its `paths:` scoping frontmatter. This script is the ROLLUP: it
adds up everything Claude Code boots with, so a change that stays under each
individual cap can still be caught if it pushes the TOTAL over budget —
exactly the superscar-family-#2 failure mode ("Esiste ≠ Armato" applied to a
budget: five individually-compliant files can still add up to a boot tax
nobody measured).

What gets counted, and why (verified empirically against a fresh Claude Code
session boot on 2026-09-04, not assumed from documentation):

  - `root_claude_md`  — `CLAUDE.md` at the repo root, loaded in FULL.
  - `unscoped_rules`  — every `.claude/rules/*.md` file WHOSE FRONTMATTER HAS
    NO `paths:` KEY, loaded in FULL (a `paths:`-scoped rule only loads when
    a file matching its glob is touched — that's the entire point of the
    scoping mechanism `test_claude_md_budget.py`'s guard #4 protects).
  - `agents_frontmatter` — every `.claude/agents/*.md` file contributes only
    its frontmatter `name` + `description` + `tools` fields (the body is
    read lazily, only if that agent is actually dispatched).
  - `skills_listing` — every `.claude/skills/*/SKILL.md` and
    `.claude/commands/*.md` file contributes only its frontmatter `name` +
    `description` (same lazy-body reasoning as agents).

`--live` adds four more categories that are machine-local (they read
`Path.home()`, i.e. `~/.claude/...`, not anything in this repo) and are
NEVER identical across two machines or two worktrees on the same machine:
`global_claude_md` (`~/.claude/CLAUDE.md`), `auto_memory` (the per-project
auto-loaded `MEMORY.md` under `~/.claude/projects/<cwd-slug>/memory/`, where
`<cwd-slug>` is the current working directory's absolute path with every
`/` replaced by `-` — e.g. `/Users/balizero/nuzantara` becomes
`-Users-balizero-nuzantara`, which is why the `--live` table must never be
pasted anywhere outside this machine: the slug alone identifies the
operator's home directory), `home_agents_frontmatter` and
`home_skills_listing` (the `~/.claude/agents` and `~/.claude/skills` +
`~/.claude/commands` mirrors of the two repo categories above). Because
`--live` output is machine-identifying, only the four REPO categories are
asserted on in CI (`scripts/tests/test_context_budget_audit.py`) — `--live`
is a human-operated diagnostic, not a gate.

The byte→token ratio (default 2.04 bytes/token) was measured empirically on
this repo's actual injected-context mix (Italian prose + emoji + markdown
tables skew heavier per-token than English ASCII prose) — it is a ballpark,
not a tokenizer. Every "est_tokens" figure in this script's output is
labelled "est." for exactly that reason: the only ground truth for the real
number is running `/context` in a fresh Claude Code session.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BYTES_PER_TOKEN = 2.04

# Repo-scope categories, in table/report order. Deterministic, CI-safe —
# nothing here reads outside the repo checkout.
REPO_CATEGORIES = (
    "root_claude_md",
    "unscoped_rules",
    "agents_frontmatter",
    "skills_listing",
)

# Machine-local categories, only measured under --live. Every one of these
# reads Path.home() — never paste this table anywhere, it identifies the
# operator's machine (see module docstring on `auto_memory`'s slug).
LIVE_CATEGORIES = (
    "global_claude_md",
    "auto_memory",
    "home_agents_frontmatter",
    "home_skills_listing",
)

_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")


def frontmatter_block(text: str) -> list[str] | None:
    """The raw lines strictly between the opening `---` and the closing
    `---` of a YAML frontmatter block at the very top of `text`. `None` if
    `text` does not open with `---` on its first line, or the block is
    never closed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return body
        body.append(line)
    return None  # opened but never closed — not a valid frontmatter block


def has_paths_frontmatter(text: str) -> bool:
    """True if `text` opens with a YAML frontmatter block that declares a
    `paths:` key (single-line list or a multi-line list continued on the
    lines below it — either shape only needs the KEY line itself, its value
    shape does not matter here)."""
    body = frontmatter_block(text)
    if body is None:
        return False
    return any(line.strip().startswith("paths:") for line in body)


def frontmatter_fields(text: str) -> dict[str, str]:
    """Top-level scalar frontmatter fields as raw strings — surrounding
    quotes stripped, multi-line continuations (an indented list under a bare
    `key:`) joined with spaces into the same field. Returns `{}` when `text`
    has no frontmatter block at all (the "skip files without frontmatter"
    case: such a file contributes nothing, deliberately not an error — a
    body-only `.md` file under `.claude/agents/` etc. is never auto-injected
    at boot, so it costs zero context budget)."""
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


def _measure_frontmatter_file(path: Path, *, include_tools: bool) -> tuple[int, int]:
    """(files, chars) contributed by one agent/skill/command file: the sum
    of its frontmatter `name` + `description` (+ `tools` when
    `include_tools`) field lengths — NOT the file's on-disk byte size, since
    only the frontmatter is loaded at boot, the body is read lazily. Files
    without a frontmatter block contribute (0, 0)."""
    fields = frontmatter_fields(_read(path))
    if not fields:
        return (0, 0)
    total = len(fields.get("name", "")) + len(fields.get("description", ""))
    if include_tools:
        total += len(fields.get("tools", ""))
    return (1, total)


def _measure_frontmatter_glob(root: Path, pattern: str, *, include_tools: bool) -> tuple[int, int]:
    files = 0
    total = 0
    if not root.is_dir():
        return (0, 0)
    for p in sorted(root.glob(pattern)):
        if not p.is_file():
            continue
        f, b = _measure_frontmatter_file(p, include_tools=include_tools)
        files += f
        total += b
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
    """`~/.claude/projects/<slug>/memory/MEMORY.md`'s `<slug>`: the current
    working directory's resolved absolute path with every `/` replaced by
    `-` (e.g. `/Users/balizero/nuzantara` -> `-Users-balizero-nuzantara`).
    Deliberately keyed on `repo_root` (the audit's own notion of "cwd"), NOT
    a hardcoded canonical checkout path — running this from a worktree
    checkout correctly reports that worktree's (usually absent) memory
    file, not the main checkout's."""
    return str(repo_root.resolve()).replace("/", "-")


def measure(repo_root: Path, live: bool = False) -> dict[str, dict[str, int]]:
    """Measure the always-injected context surface. Returns an ordered dict
    (`REPO_CATEGORIES`, then `LIVE_CATEGORIES` if `live`) of
    `{"files": int, "bytes": int}`. `bytes` is on-disk file size for the two
    whole-file categories (`root_claude_md`, `unscoped_rules`,
    `global_claude_md`, `auto_memory`) and frontmatter-field character count
    for the two frontmatter-only categories (`agents_frontmatter`,
    `skills_listing`, and their `home_*` live counterparts) — see the
    per-category docstrings above for why the two are measured differently."""
    repo_root = Path(repo_root)
    result: dict[str, dict[str, int]] = {}

    files, total = _measure_whole_file(repo_root / "CLAUDE.md")
    result["root_claude_md"] = {"files": files, "bytes": total}

    files, total = _measure_unscoped_rules(repo_root)
    result["unscoped_rules"] = {"files": files, "bytes": total}

    files, total = _measure_frontmatter_glob(
        repo_root / ".claude" / "agents", "*.md", include_tools=True
    )
    result["agents_frontmatter"] = {"files": files, "bytes": total}

    skill_files, skill_total = _measure_frontmatter_glob(
        repo_root / ".claude" / "skills", "*/SKILL.md", include_tools=False
    )
    cmd_files, cmd_total = _measure_frontmatter_glob(
        repo_root / ".claude" / "commands", "*.md", include_tools=False
    )
    result["skills_listing"] = {
        "files": skill_files + cmd_files,
        "bytes": skill_total + cmd_total,
    }

    if live:
        home = Path.home()

        files, total = _measure_whole_file(home / ".claude" / "CLAUDE.md")
        result["global_claude_md"] = {"files": files, "bytes": total}

        slug = _memory_slug(repo_root)
        mem_path = home / ".claude" / "projects" / slug / "memory" / "MEMORY.md"
        files, total = _measure_whole_file(mem_path)
        result["auto_memory"] = {"files": files, "bytes": total}

        files, total = _measure_frontmatter_glob(
            home / ".claude" / "agents", "*.md", include_tools=True
        )
        result["home_agents_frontmatter"] = {"files": files, "bytes": total}

        skill_files, skill_total = _measure_frontmatter_glob(
            home / ".claude" / "skills", "*/SKILL.md", include_tools=False
        )
        cmd_files, cmd_total = _measure_frontmatter_glob(
            home / ".claude" / "commands", "*.md", include_tools=False
        )
        result["home_skills_listing"] = {
            "files": skill_files + cmd_files,
            "bytes": skill_total + cmd_total,
        }

    return result


def _est_tokens(num_bytes: int, bytes_per_token: float) -> int:
    return round(num_bytes / bytes_per_token)


def render_table(
    measurement: dict[str, dict[str, int]], bytes_per_token: float
) -> str:
    lines: list[str] = []
    header = f"{'category':<26}{'files':>8}{'bytes':>12}{'est_tokens':>14}"
    lines.append(header)
    lines.append("-" * len(header))
    total_bytes = 0
    for category, stats in measurement.items():
        b = stats["bytes"]
        total_bytes += b
        lines.append(
            f"{category:<26}{stats['files']:>8}{b:>12,}{_est_tokens(b, bytes_per_token):>14,}"
        )
    lines.append("-" * len(header))
    lines.append(
        f"{'TOTAL':<26}{'':>8}{total_bytes:>12,}{_est_tokens(total_bytes, bytes_per_token):>14,}"
    )
    lines.append("")
    lines.append(
        f"ratio: {bytes_per_token} bytes/token (est. — true count via /context in a fresh session)"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the always-injected context surface of this repo."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repo checkout to measure (default: this script's own repo)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="also measure machine-local ~/.claude categories (never paste this output)",
    )
    parser.add_argument(
        "--bytes-per-token",
        type=float,
        default=DEFAULT_BYTES_PER_TOKEN,
        help=f"bytes-per-token ratio for the est_tokens column (default: {DEFAULT_BYTES_PER_TOKEN})",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="exit 1 if the estimated total exceeds this many tokens",
    )
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
        print(
            f"\nOVER BUDGET: est. {total_tokens:,} tokens > --max-tokens {args.max_tokens:,}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
