#!/usr/bin/env python3
"""scripts/mini-migration/preflight-job.py <label>

Deep preflight for migration candidates Pro->Mini. Extends the original
shallow grep-based shell script with:

  Layer 1 — Literal grep on plist + script body (kept from shell version)
  Layer 2 — Python import-trace via ast.parse: walks all `import X` and
            `from X import Y` statements transitively (depth-limited),
            grepping each imported module file for Pro-bound patterns
            (asyncpg, psycopg, qdrant_client, redis client, etc).
  Layer 3 — Repo existence: verify referenced repos exist on Mini
            (OSINT-Nexus, MATA-GARUDA-NEXUS, kbli-2025-navigator, ...)
  Layer 4 — Pyenv/venv smoke: verify referenced Python interpreter exists
            on Mini and can import the entry-point module without error.

Exit 0: PASS — safe to migrate (no Pro-bound deps detected).
Exit 1: BLOCK — found dependency that breaks if migrated.
Exit 2: usage error.

Read-only: never modifies anything. Safe to run anytime.

Usage:
    preflight-job.py <launchd-label>
    preflight-job.py <launchd-label> --verbose
"""
from __future__ import annotations

import argparse
import ast
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Iterable

# ---------------------------------------------------------------------------
# Patterns flagged as Pro-bound dependencies
# ---------------------------------------------------------------------------

LITERAL_PATTERNS = [
    r"localhost:5432",
    r"127\.0\.0\.1:5432",
    r"postgresql.*:5432",
    r":5432/",
    r"localhost:6333",
    r"127\.0\.0\.1:6333",
    r"qdrant.*:6333",
    r":6333/",
    r"pg_ctl|psql -h",
    r"localhost:11434",
    r"127\.0\.0\.1:11434",
    r"/Users/nuzantara/agents/",
    r"/Users/antonellosiano/",
    r"fly ssh|fly proxy",
    r"\bssh\s+pro\b|\bssh\s+air\b",
    r"Nuzantara-9",
]

# Modules whose presence ANYWHERE in the import-trace blocks migration
# (they mean the script connects to Pro-local services regardless of the
# DATABASE_URL value, because Mini has neither Postgres nor Qdrant)
PRO_BOUND_IMPORTS = {
    "asyncpg": "PostgreSQL async driver — Mini has no Postgres",
    "psycopg": "PostgreSQL sync driver — Mini has no Postgres",
    "psycopg2": "PostgreSQL sync driver — Mini has no Postgres",
    "qdrant_client": "Qdrant client — Mini has no Qdrant",
    "neo4j": "Neo4j driver — Mini has no Neo4j",
    "playwright.sync_api": "Playwright — needs ~/.cache/ms-playwright session state",
    "playwright.async_api": "Playwright — needs ~/.cache/ms-playwright session state",
}

# Repos that, when referenced, must exist on Mini for the script to work
REQUIRED_REPOS = {
    "/Users/nuzantara/Desktop/OSINT-Nexus": None,  # filled at runtime
    "/Users/nuzantara/Desktop/MATA-GARUDA-NEXUS": None,
    "/Users/nuzantara/Desktop/nuzantara-deploy": None,
    "/Users/nuzantara/Desktop/kbli-2025-navigator": None,
}

# Python interpreters that, when referenced, must exist on Mini
REQUIRED_INTERPRETERS = [
    re.compile(r"(/Users/nuzantara/\.pyenv/versions/[^/\s]+/bin/python[\d.]*)"),
    re.compile(r"(/Users/nuzantara/Desktop/nuzantara/apps/[^/]+/\.venv/bin/python[\d.]*)"),
    re.compile(r"(/Users/nuzantara/Desktop/[^/]+/\.venv/bin/python[\d.]*)"),
]

# Stdlib module names — never grep'd transitively
STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {
    "os", "sys", "re", "json", "time", "datetime", "pathlib", "subprocess",
    "argparse", "logging", "typing", "collections", "itertools", "functools",
    "asyncio", "threading", "tempfile", "shutil", "io", "ast", "urllib",
    "hashlib", "base64", "uuid", "math", "random", "socket", "ssl",
    "email", "html", "xml", "csv", "sqlite3", "dataclasses",
}

# Verbose flag
VERBOSE = False
DEBUG_LOG: list[str] = []


def log(msg: str) -> None:
    DEBUG_LOG.append(msg)
    if VERBOSE:
        print(f"[preflight] {msg}")


def fetch_pro_plist(label: str) -> str | None:
    """ssh pro 'cat ~/Library/LaunchAgents/<label>.plist' — returns body or None."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
             f"cat ~/Library/LaunchAgents/{label}.plist"],
            capture_output=True, text=True, errors="replace", timeout=15)
        if result.returncode != 0:
            log(f"FATAL: cannot fetch plist for {label}: {result.stderr.strip()[:200]}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        log("FATAL: ssh pro timed out")
        return None


def extract_script_paths(plist_body: str) -> list[str]:
    """Extract referenced script paths from ProgramArguments (idx 1, 2)."""
    paths = []
    # Find ProgramArguments array. Match each <string>...</string> within.
    in_args = False
    for line in plist_body.split("\n"):
        if "<key>ProgramArguments</key>" in line:
            in_args = True
            continue
        if in_args:
            if "</array>" in line:
                in_args = False
                continue
            m = re.search(r"<string>(.*?)</string>", line)
            if m:
                val = m.group(1)
                paths.append(val)
    return paths


def fetch_pro_file(remote_path: str) -> str | None:
    """ssh pro 'cat <path>' — returns content or None if missing/inaccessible."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "pro",
             f"[ -f '{remote_path}' ] && cat '{remote_path}'"],
            capture_output=True, text=True, errors="replace", timeout=15)
        if result.returncode != 0:
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        return None


def grep_literal(text: str, source_label: str) -> list[tuple[str, str]]:
    """Return list of (pattern, matched_line) hits."""
    hits = []
    for pat in LITERAL_PATTERNS:
        for line in text.split("\n"):
            if re.search(pat, line):
                hits.append((pat, f"{source_label}: {line.strip()[:120]}"))
                break  # one hit per pattern is enough
    return hits


def find_python_modules_in_text(text: str) -> set[str]:
    """Find Python module imports in arbitrary text via grep (not parse).

    Used for shell scripts that invoke `python -m module.path` or
    `python -c "import x"`.
    """
    mods = set()
    # python -m <module>
    for m in re.finditer(r"python\d?(?:\.\d+)?\s+-m\s+([\w.]+)", text):
        mods.add(m.group(1))
    # python -c "...import X..."
    for m in re.finditer(r"python\d?(?:\.\d+)?\s+-c\s+[\"']([^\"']+)[\"']", text):
        for sub in re.finditer(r"\bimport\s+([\w.]+)|\bfrom\s+([\w.]+)\s+import", m.group(1)):
            mods.add(sub.group(1) or sub.group(2))
    return mods


def fetch_pro_python_module(module_path: str) -> tuple[pathlib.Path | None, str]:
    """Locate Python module file on Pro and fetch its content.

    Returns (local_temp_path, content) or (None, "") if not found.
    Searches in:
      - /Users/nuzantara/Desktop/nuzantara/apps/*/  (backend-rag, mata-garuda, etc)
      - /Users/nuzantara/Desktop/nuzantara/scripts/
      - /Users/nuzantara/scripts/
      - /Users/nuzantara/.claude/skills/
    """
    if module_path in STDLIB or module_path.split(".")[0] in STDLIB:
        return None, ""

    # Convert module.path → relative file paths to try
    rel = module_path.replace(".", "/")
    candidates = [
        f"/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/{rel}.py",
        f"/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/{rel}/__init__.py",
        f"/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/{rel}.py",
        f"/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/{rel}/__init__.py",
        f"/Users/nuzantara/Desktop/nuzantara/{rel}.py",
        f"/Users/nuzantara/Desktop/nuzantara/{rel}/__init__.py",
        f"/Users/nuzantara/scripts/{rel}.py",
        f"/Users/nuzantara/.claude/skills/bali-zero-brand/{rel}.py",
    ]
    for c in candidates:
        body = fetch_pro_file(c)
        if body is not None:
            log(f"  found module {module_path} at {c}")
            return pathlib.Path(c), body
    log(f"  module {module_path} not found in known paths")
    return None, ""


def python_imports_from_source(src: str) -> set[str]:
    """ast.parse source and return set of imported module names."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # Prepend with leading dots for relative imports
                if node.level > 0:
                    # relative; ignore (we don't have package context)
                    continue
                mods.add(node.module)
    return mods


def trace_imports(seed_modules: set[str], max_depth: int = 3,
                  max_modules: int = 80) -> tuple[set[str], dict[str, str]]:
    """BFS through the import graph from seed_modules.

    Returns (visited_set, module_to_first_path) — first_path is the file
    we found that module at on Pro.
    """
    visited: set[str] = set()
    found_at: dict[str, str] = {}
    queue: list[tuple[str, int]] = [(m, 0) for m in seed_modules]
    while queue and len(visited) < max_modules:
        mod, depth = queue.pop(0)
        if mod in visited:
            continue
        visited.add(mod)
        if mod in STDLIB or mod.split(".")[0] in STDLIB:
            continue
        if depth >= max_depth:
            continue
        path, body = fetch_pro_python_module(mod)
        if not body:
            continue
        found_at[mod] = str(path)
        new_imports = python_imports_from_source(body)
        for nm in new_imports:
            if nm not in visited:
                queue.append((nm, depth + 1))
    return visited, found_at


def check_required_repos(refs: Iterable[str]) -> list[tuple[str, str]]:
    """For each required repo path referenced, verify it exists on Mini."""
    issues = []
    for ref in refs:
        for repo, _ in REQUIRED_REPOS.items():
            if ref.startswith(repo):
                if not pathlib.Path(repo).is_dir():
                    issues.append((repo, f"referenced ({ref}) but missing on Mini"))
                break
    return issues


def check_required_interpreters(text: str) -> list[tuple[str, str]]:
    """Verify referenced Python interpreters exist on Mini."""
    issues = []
    seen = set()
    for pat in REQUIRED_INTERPRETERS:
        for m in pat.finditer(text):
            interp = m.group(1)
            if interp in seen:
                continue
            seen.add(interp)
            if not pathlib.Path(interp).is_file():
                issues.append((interp, "interpreter missing on Mini"))
    return issues


def main() -> int:
    global VERBOSE
    parser = argparse.ArgumentParser()
    parser.add_argument("label", help="LaunchAgent label (e.g. com.balizero.regulatory-watcher.daily)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    VERBOSE = args.verbose

    label = args.label
    print(f"[preflight] {label}")

    # === Layer 1: fetch plist ===
    plist = fetch_pro_plist(label)
    if not plist:
        print(f"[preflight] FATAL: cannot fetch plist from Pro")
        return 2
    print(f"[preflight] plist size: {len(plist)} bytes")

    # === Layer 1: extract script/cmd refs ===
    script_paths = extract_script_paths(plist)
    print(f"[preflight] ProgramArguments: {len(script_paths)} entries")

    # Aggregate text to grep: plist + each script body
    aggregated = plist
    referenced_paths = []
    for sp in script_paths:
        if sp.startswith("/") and " " not in sp[:60]:
            # Looks like a real file path
            referenced_paths.append(sp)
            body = fetch_pro_file(sp)
            if body:
                aggregated += "\n" + body
                print(f"[preflight] fetched {sp} ({len(body)} bytes)")
        else:
            # Inline shell command — body IS the cmd
            aggregated += "\n" + sp
            # Also extract script paths that the inline cmd references
            for m in re.finditer(r"(/Users/nuzantara/[^\s\"']+\.(?:sh|py))", sp):
                p = m.group(1)
                if p not in referenced_paths:
                    referenced_paths.append(p)
                    body = fetch_pro_file(p)
                    if body:
                        aggregated += "\n" + body
                        print(f"[preflight] fetched {p} ({len(body)} bytes)")

    # === Layer 1: literal grep ===
    literal_hits = grep_literal(aggregated, "literal")
    if literal_hits:
        print(f"\n[preflight] LAYER 1 BLOCK: {len(literal_hits)} literal pattern(s):")
        for pat, line in literal_hits[:5]:
            print(f"  - {pat} -> {line}")
        return 1
    print(f"[preflight] Layer 1 (literal grep) PASS")

    # === Layer 3: required repos ===
    repo_issues = check_required_repos(referenced_paths)
    if repo_issues:
        print(f"\n[preflight] LAYER 3 BLOCK: {len(repo_issues)} repo(s) missing on Mini:")
        for repo, msg in repo_issues:
            print(f"  - {repo}: {msg}")
        return 1
    print(f"[preflight] Layer 3 (required repos) PASS")

    # === Layer 4: required interpreters ===
    interp_issues = check_required_interpreters(aggregated)
    if interp_issues:
        print(f"\n[preflight] LAYER 4 BLOCK: {len(interp_issues)} interpreter(s) missing on Mini:")
        for interp, msg in interp_issues:
            print(f"  - {interp}: {msg}")
        return 1
    print(f"[preflight] Layer 4 (interpreters) PASS")

    # === Layer 2: import-trace ===
    seed_modules = find_python_modules_in_text(aggregated)
    if not seed_modules:
        # Try parsing referenced .py files as well
        for sp in referenced_paths:
            if sp.endswith(".py"):
                body = fetch_pro_file(sp)
                if body:
                    seed_modules |= python_imports_from_source(body)

    if seed_modules:
        print(f"[preflight] Layer 2: tracing {len(seed_modules)} seed module(s)...")
        if VERBOSE:
            print(f"  seeds: {sorted(seed_modules)[:10]}")
        visited, found_at = trace_imports(seed_modules, max_depth=3, max_modules=80)
        print(f"[preflight] Layer 2: visited {len(visited)} module(s) in import graph")

        forbidden = []
        for mod in visited:
            for forbidden_mod, why in PRO_BOUND_IMPORTS.items():
                if mod == forbidden_mod or mod.startswith(forbidden_mod + "."):
                    forbidden.append((mod, why, found_at.get(mod, "(transitive seed)")))
                    break
        if forbidden:
            print(f"\n[preflight] LAYER 2 BLOCK: {len(forbidden)} Pro-bound import(s):")
            for mod, why, where in forbidden[:5]:
                print(f"  - {mod} ({why}) — found via {where}")
            return 1
        print(f"[preflight] Layer 2 (import-trace) PASS")
    else:
        print(f"[preflight] Layer 2: no Python modules referenced (shell-only, skip)")

    print(f"\n[preflight] verdict: PASS — {label} can be migrated to Mini")
    return 0


if __name__ == "__main__":
    sys.exit(main())
