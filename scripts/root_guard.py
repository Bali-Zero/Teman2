#!/usr/bin/env python3
"""root_guard — deny-by-default guard for the repo root.

Prevents scratch/dump/one-off files from accumulating at the repo root by
enforcing a whitelist. Any addition of a file directly at the root that is
not in WHITELIST_FILES, does not match WHITELIST_GLOBS, and is not inside
a known top-level directory (apps/, docs/, scripts/, etc.) is rejected.

Modes:
  - Pre-commit hook:  `python scripts/root_guard.py <file1> <file2> ...`
                       pre-commit passes only the staged root-level file paths
  - CI / standalone:  `python scripts/root_guard.py --check`
                       scans `git ls-files .` vs whitelist; exits 1 if any
                       tracked root file is not whitelisted
  - Local workspace:  `python scripts/root_guard.py --workspace`
                       scans the physical repo root, including ignored and
                       untracked entries, while allowing documented local
                       development dependencies and tool state

Rationale: historical reactive gitignore (which requires listing every new
junk pattern) misses new one-off names like `debug_20260425.py` or
`mynotes.md`. Whitelist-at-root inverts the default: only explicitly
allowed files live here.

To add a new legitimate root file: extend WHITELIST_FILES in this script
in the same commit that introduces the file.
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# --- Whitelist ---------------------------------------------------------------

# Exact filenames allowed at repo root.
WHITELIST_FILES: set[str] = {
    # AI agent markers (read automatically by respective CLI in this dir)
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    "codex.md",
    # Standard project files
    "README.md",
    "LICENSE",
    "LICENSE.md",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "yarn.lock",
    "tsconfig.json",
    "vercel.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "Makefile",
    # Governance / contracts (project-specific)
    "SYMBIOSIS.md",
    "VADEMECUM.md",
    "INDEX.md",
    "AUTONOMOUS_OPS.md",
    "FOLLOWUPS.md",
    # SSOT config
    "MODEL_TOPOLOGY.json",
    # Entry launcher
    "sentinel",
    # Symlinks (organizational)
    "POSTGRESQL",
    "monitoring",
    "prompts",
    "source_documents",
    "storage",
}

# Glob patterns allowed at repo root (dotfiles, common config extensions).
WHITELIST_GLOBS: tuple[str, ...] = (
    # Config dotfiles
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".prettierignore",
    ".geminiignore",
    ".stignore",
    ".cursorrules",
    ".clinerules",
    ".env.example",
    ".pre-commit-config.yaml",
    ".pre-commit-config.yml",
    ".secrets.baseline",
    ".eslintrc*",
    ".prettierrc*",
    ".editorconfig",
    ".nvmrc",
    ".node-version",
    ".python-version",
    ".ruff.toml",
    ".python-version",
    # docsync internal cache (written by scripts/docs_sync.py)
    ".docs_sync_cache.json",
)

# Top-level directories that are allowed to be tracked (anything inside is OK).
# Dotfiles directories listed separately below.
WHITELIST_DIRS: set[str] = {
    "apps",
    "packages",
    "config",
    "data",
    "docs",
    "infra",
    "integrations",
    "public",
    "scripts",
    "shared",
    "skills",
    "tests",
    "tools",
    "research",
    # Curated personal library: 01-inventory.md generated artifact + future
    # 02-patterns.md, 03-lessons.md (manual). Separate from research/ (raw
    # capture) and scripts/ (build/utility). See agent-library/README.md.
    "agent-library",
    # Vendored third-party source (Apache 2.0 + similar permissive licenses
    # only). Each vendor/<pkg>/UPSTREAM.md documents the upstream SHA + the
    # diff list. Currently: vendor/evoskill/ — EvoSkill v1.1.0 stripped of
    # Anthropic deps per CLAUDE.md hard rule. See PR #721.
    "vendor",
}

# Allowed tracked dotfiles directories.
WHITELIST_DOTDIRS: set[str] = {
    ".agents",
    ".claude",
    ".github",
    ".husky",
    ".vscode",
    ".security",
    ".Jules",
    # Quarantine dir for abandoned attempts kept for audit only. Subdirectories
    # are dated/contextual (e.g. atlas-attempt-pre-2026-04-26/) and contain a
    # README.md explaining why each block is parked + cicatrix-scars pointer.
    # Outside every active CI matcher (`paths:` filters), see PR #363.
    ".disabled",
    # kimi-code project scope: skills under .kimi-code/skills/ are auto-
    # discovered by the Kimi CLI from the git root (Kimi arsenal entry
    # 2026-07-19, PR #2798). Same class as .claude/ and .agents/.
    ".kimi-code",
}

# Local-only entries that may exist in a developer checkout. These are not
# candidates for Git: they are dependencies, isolated worktrees, secrets, or
# project-scoped state used by an installed development tool. Keep this list
# narrow. Generated deliverables, handoff notes, archives, and ad-hoc drafts do
# not belong here; see docs/operations/REPOSITORY_STORAGE_POLICY.md.
LOCAL_WORKSPACE_DIRS: set[str] = {
    ".agent",
    ".agent-receipts",
    ".antigravity",
    ".clawhub",
    ".codex",
    ".cursor",
    ".gemini",
    ".idea",
    ".mcp-servers",
    ".openclaw",
    ".opencode",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    ".secrets",
    ".serena",
    ".superpowers",
    ".venv",
    ".venv-wr2-html",
    ".vercel",
    ".windsurf",
    ".worktrees",
    "node_modules",
    "venv",
}

LOCAL_WORKSPACE_FILES: set[str] = {
    ".agent-task.json",
    ".env.worktree",
    ".mcp.json",
    "opencode.json",
}


def is_whitelisted(rel_path: str) -> bool:
    """Return True if `rel_path` is allowed at repo root (or inside an allowed dir)."""
    if "/" in rel_path:
        top = rel_path.split("/", 1)[0]
        return top in WHITELIST_DIRS or top in WHITELIST_DOTDIRS
    # Root-level file (no slash)
    if rel_path in WHITELIST_FILES:
        return True
    for pat in WHITELIST_GLOBS:
        if fnmatch.fnmatchcase(rel_path, pat):
            return True
    return False


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(f"git {' '.join(args)} failed: {result.stderr}")
        return ""
    return result.stdout


def find_repo_root(start: Path) -> Path:
    out = run_git(["rev-parse", "--show-toplevel"], start)
    if out:
        return Path(out.strip())
    return start.resolve()


def check_all_tracked(repo_root: Path) -> list[str]:
    """List every tracked root-level file/dir NOT whitelisted.

    Uses `git ls-files -z` (NUL-separated) to avoid C-quoting on paths that
    contain special characters; some historical commits have odd filenames
    that would otherwise appear as `"apps/...\"import"` when ls-files quotes
    them for human consumption.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(f"git ls-files -z failed: {result.stderr.decode('utf-8', 'replace')}\n")
        return []
    raw = result.stdout.decode("utf-8", errors="replace")
    offenders: list[str] = []
    seen_top: set[str] = set()
    for line in raw.split("\0"):
        line = line.strip()
        if not line:
            continue
        top = line.split("/", 1)[0]
        if "/" not in line:
            # root-level file
            if not is_whitelisted(line):
                offenders.append(line)
        else:
            # inside a dir
            if top in seen_top:
                continue
            seen_top.add(top)
            if top not in WHITELIST_DIRS and top not in WHITELIST_DOTDIRS:
                offenders.append(top + "/")
    return sorted(set(offenders))


def check_paths(paths: Iterable[str]) -> list[str]:
    """Return the subset of `paths` that are NOT whitelisted."""
    offenders: list[str] = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        # Normalize: strip leading "./" if present
        if p.startswith("./"):
            p = p[2:]
        if not is_whitelisted(p):
            offenders.append(p)
    return offenders


def tracked_root_entries(repo_root: Path) -> set[str]:
    """Return the first path component of every tracked file."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"git ls-files -z failed: {result.stderr.decode('utf-8', 'replace')}\n"
        )
        return set()
    raw = result.stdout.decode("utf-8", errors="replace")
    return {item.split("/", 1)[0] for item in raw.split("\0") if item}


def check_workspace(repo_root: Path) -> list[str]:
    """List undocumented physical entries at the repository root.

    Unlike ``check_all_tracked``, this intentionally sees ignored and
    untracked paths. It remains root-scoped: generated files nested under an
    application are governed by that application's runtime contract.
    """
    tracked = tracked_root_entries(repo_root)
    allowed_local = LOCAL_WORKSPACE_DIRS | LOCAL_WORKSPACE_FILES
    offenders: list[str] = []
    for entry in repo_root.iterdir():
        name = entry.name
        if name == ".git" or name in tracked or name in allowed_local:
            continue
        offenders.append(name + "/" if entry.is_dir() else name)
    return sorted(offenders)


def render_error(offenders: list[str]) -> str:
    lines = ["", "\033[31m✘ root_guard: blocked files at repo root\033[0m", ""]
    for o in offenders:
        lines.append(f"  - {o}")
    lines += [
        "",
        "The repo root is whitelist-only to prevent scratch/dump accumulation.",
        "",
        "To fix:",
        "  • Documentation    → move into  docs/",
        "  • One-off script   → move into  scripts/  (or delete)",
        "  • App/service code → move into  apps/ or packages/",
        "  • Generated/local  → move outside the repo per",
        "    docs/operations/REPOSITORY_STORAGE_POLICY.md",
        "  • Genuinely root-level? → add the name to WHITELIST_FILES in",
        "    scripts/root_guard.py in the same commit.",
        "",
        "Bypass (discouraged): git commit --no-verify",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    argv = sys.argv[1:]
    repo_root = find_repo_root(Path.cwd())

    if argv and argv[0] == "--check":
        # Audit mode: scan all tracked root-level entries
        offenders = check_all_tracked(repo_root)
    elif argv and argv[0] == "--workspace":
        # Local audit mode: include ignored and untracked root entries.
        offenders = check_workspace(repo_root)
    else:
        # Hook mode: pre-commit passes file paths as argv
        offenders = check_paths(argv)

    if offenders:
        sys.stderr.write(render_error(offenders))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
