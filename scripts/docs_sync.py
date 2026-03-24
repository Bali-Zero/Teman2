#!/usr/bin/env python3
"""
DocSentinel — Deterministic documentation stats synchronizer.

Extracts live metrics from the codebase and injects them into markdown files
between <!-- DOCSYNC:KEY_START --> and <!-- DOCSYNC:KEY_END --> markers.

Usage:
    python scripts/docs_sync.py              # Update all markers in-place
    python scripts/docs_sync.py --check      # Exit 1 if any marker is stale (CI mode)
    python scripts/docs_sync.py --diff       # Show what would change without writing
    python scripts/docs_sync.py --quiet      # Suppress output (for hooks)
    python scripts/docs_sync.py --json       # Output stats as JSON

No LLM dependency. Pure Python. Zero cost. Works offline.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve repo root (script lives in scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "apps" / "backend-rag"
BACKEND_SRC = BACKEND / "backend"

# Marker pattern
MARKER_RE = re.compile(
    r"(<!-- DOCSYNC:(\w+)_START -->\n).*?(\n<!-- DOCSYNC:\2_END -->)",
    re.DOTALL,
)

# ── Extractors ──────────────────────────────────────────────────────────────


def count_routers() -> int:
    """Count FastAPI routers from router_registration.py."""
    reg_file = BACKEND_SRC / "app" / "setup" / "router_registration.py"
    if not reg_file.exists():
        return 0
    content = reg_file.read_text()
    return len(re.findall(r"api\.include_router\(", content))


def count_services() -> int:
    """Count Python service files in backend/services/ (excluding __init__)."""
    services_dir = BACKEND_SRC / "services"
    if not services_dir.exists():
        return 0
    return sum(
        1
        for f in services_dir.rglob("*.py")
        if f.name != "__init__.py" and "test" not in str(f)
    )


def count_test_files() -> int:
    """Count test files in backend/tests/."""
    tests_dir = BACKEND_SRC / "tests"
    if not tests_dir.exists():
        # Try alternative location
        tests_dir = BACKEND / "backend" / "tests"
    if not tests_dir.exists():
        return 0
    return sum(1 for f in tests_dir.rglob("test_*.py"))


def count_apps() -> int:
    """Count app directories in apps/."""
    apps_dir = REPO_ROOT / "apps"
    if not apps_dir.exists():
        return 0
    return sum(1 for d in apps_dir.iterdir() if d.is_dir() and not d.name.startswith("."))


def get_version() -> str:
    """Read version from root package.json."""
    pkg = REPO_ROOT / "package.json"
    if not pkg.exists():
        return "unknown"
    data = json.loads(pkg.read_text())
    return data.get("version", "unknown")


def get_qdrant_stats() -> dict:
    """Get Qdrant stats from production health endpoint or cache."""
    cache_file = REPO_ROOT / ".docs_sync_cache.json"

    # Try production health endpoint
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://nuzantara-rag.fly.dev/health",
            headers={"User-Agent": "DocSentinel/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            result = {
                "collections": data.get("database", {}).get("collections", 0),
                "documents": data.get("database", {}).get("total_documents", 0),
                "embedding_model": data.get("embeddings", {}).get("model", "unknown"),
            }
            # Cache for offline use
            cache_data = {}
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text())
            cache_data["qdrant"] = result
            cache_data["qdrant_updated"] = datetime.now(timezone.utc).isoformat()
            cache_file.write_text(json.dumps(cache_data, indent=2))
            return result
    except Exception:
        pass

    # Fallback to cache
    if cache_file.exists():
        cache_data = json.loads(cache_file.read_text())
        if "qdrant" in cache_data:
            return cache_data["qdrant"]

    # Last resort: hardcoded fallback
    return {"collections": 10, "documents": 93283, "embedding_model": "text-embedding-3-small"}


def count_channels() -> int:
    """Count communication channel directories."""
    channels_dir = BACKEND_SRC / "channels"
    if not channels_dir.exists():
        return 0
    return sum(1 for d in channels_dir.iterdir() if d.is_dir() and not d.name.startswith("_"))


def get_kg_stats() -> dict:
    """Get Knowledge Graph stats (cached, changes rarely)."""
    # KG stats change rarely — use hardcoded values that we update manually
    return {"nodes": 56113, "edges": 161173}


# ── Stats Assembly ──────────────────────────────────────────────────────────


def collect_all_stats() -> dict:
    """Collect all stats from the codebase."""
    qdrant = get_qdrant_stats()
    kg = get_kg_stats()

    return {
        "routers": count_routers(),
        "services": count_services(),
        "test_files": count_test_files(),
        "apps": count_apps(),
        "version": get_version(),
        "collections": qdrant["collections"],
        "documents": qdrant["documents"],
        "embedding_model": qdrant["embedding_model"],
        "channels": count_channels(),
        "kg_nodes": kg["nodes"],
        "kg_edges": kg["edges"],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── Marker Templates ───────────────────────────────────────────────────────

TEMPLATES = {
    "TECH_STATS": lambda s: f"""| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, {s['routers']} routers, {s['services']} services |
| **Frontend** | Next.js, TypeScript, Tailwind CSS |
| **Databases** | PostgreSQL (relational), Qdrant v1.17.0 (vector), Redis (cache) |
| **Infrastructure** | Fly.io (backend, Singapore), Vercel (frontend) |
| **LLM** | Gemini 2.5 Flash (primary), Gemini 2.0 Flash (fallback), OpenRouter |
| **Embedding** | `{s['embedding_model']}` (1536 dims) — FROZEN |
| **Knowledge Graph** | {s['kg_nodes']:,} nodes, {s['kg_edges']:,} edges, LangGraph orchestrator |
| **Vector Store** | {s['collections']} collections, {s['documents']:,} documents |""",
    "BACKEND_STATS": lambda s: (
        f"- **Backend:** Python 3.11+, FastAPI, {s['routers']} routers, "
        f"{s['services']} services, {s['test_files']} test files"
    ),
    "VECTOR_STATS": lambda s: (
        f"- **Vector Collections:** {s['collections']} live on Fly.io "
        f"({s['documents']:,} documents), 11 defined in code"
    ),
    "EMBEDDING_FROZEN": lambda s: (
        f"**CRITICAL:** This model is FROZEN. Changing it would invalidate "
        f"{s['documents']:,} existing vectors."
    ),
    "QUICK_NUMBERS": lambda s: (
        f"**Quick Numbers:** {s['routers']} routers · {s['services']} services · "
        f"{s['test_files']} tests · 131 MCP tools · {s['collections']} Qdrant collections "
        f"({s['documents']:,} docs) · {s['channels']} channels · "
        f"{s['kg_nodes']//1000}K KG nodes"
    ),
    "FEATURE_FLAGS": lambda s: """| Flag | Value | Effect |
|------|-------|--------|
| `ENABLE_HYBRID_SEARCH` | `true` | BM25+Dense+RRF in VectorSearchTool |
| `ENABLE_RERANKER` | `true` | CrossEncoder local reranking |
| `ENABLE_BM25` | `true` | Sparse vectors for hybrid search |
| `ENABLE_QUERY_EXPANSION` | `true` | LLM multi-query expansion + RRF |
| `ENABLE_KG_LANGGRAPH` | `true` | Knowledge Graph LangGraph orchestrator |""",
    "DOCSYNC_TIMESTAMP": lambda s: f"_Auto-synced by DocSentinel on {s['timestamp']}_",
}


# ── Marker Injection ───────────────────────────────────────────────────────


def inject_markers(filepath: Path, stats: dict, dry_run: bool = False) -> list[str]:
    """
    Replace content between DOCSYNC markers with fresh values.

    Returns list of marker names that were updated.
    """
    if not filepath.exists():
        return []

    content = filepath.read_text()
    updated_markers = []

    def replace_marker(match: re.Match) -> str:
        prefix = match.group(1)  # <!-- DOCSYNC:KEY_START -->\n
        key = match.group(2)  # KEY
        suffix = match.group(3)  # \n<!-- DOCSYNC:KEY_END -->

        if key in TEMPLATES:
            new_content = TEMPLATES[key](stats)
            updated_markers.append(key)
            return f"{prefix}{new_content}{suffix}"
        return match.group(0)

    new_content = MARKER_RE.sub(replace_marker, content)

    if new_content != content and not dry_run:
        filepath.write_text(new_content)

    return updated_markers


# ── Main ───────────────────────────────────────────────────────────────────

# Files to process
TARGET_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs" / "AI_ONBOARDING.md",
]


def main() -> int:
    args = set(sys.argv[1:])
    check_mode = "--check" in args
    diff_mode = "--diff" in args
    quiet = "--quiet" in args
    json_mode = "--json" in args

    # Collect stats
    stats = collect_all_stats()

    if json_mode:
        print(json.dumps(stats, indent=2))
        return 0

    if not quiet:
        print(f"DocSentinel — {stats['timestamp']}")
        print(f"  Routers: {stats['routers']}, Services: {stats['services']}, Tests: {stats['test_files']}")
        print(f"  Qdrant: {stats['collections']} collections, {stats['documents']:,} docs")
        print(f"  Apps: {stats['apps']}, Channels: {stats['channels']}, Version: {stats['version']}")

    # Process each target file
    total_updated = 0
    stale_files = []

    for filepath in TARGET_FILES:
        if not filepath.exists():
            if not quiet:
                print(f"  SKIP {filepath.relative_to(REPO_ROOT)} (not found)")
            continue

        if check_mode or diff_mode:
            # Read current content and check if markers would change
            content_before = filepath.read_text()
            markers = inject_markers(filepath, stats, dry_run=True)

            # Actually generate to compare
            test_content = content_before
            for key in markers:
                if key in TEMPLATES:
                    new_val = TEMPLATES[key](stats)
                    pattern = re.compile(
                        rf"(<!-- DOCSYNC:{key}_START -->\n).*?(\n<!-- DOCSYNC:{key}_END -->)",
                        re.DOTALL,
                    )
                    test_content = pattern.sub(rf"\g<1>{new_val}\g<2>", test_content)

            if test_content != content_before:
                stale_files.append(str(filepath.relative_to(REPO_ROOT)))
                if diff_mode and not quiet:
                    print(f"\n  STALE {filepath.relative_to(REPO_ROOT)}:")
                    for key in markers:
                        print(f"    - {key} needs update")
            elif not quiet:
                print(f"  OK    {filepath.relative_to(REPO_ROOT)} ({len(markers)} markers)")
        else:
            # Update in-place
            markers = inject_markers(filepath, stats)
            total_updated += len(markers)
            if not quiet:
                rel = filepath.relative_to(REPO_ROOT)
                if markers:
                    print(f"  UPDATED {rel}: {', '.join(markers)}")
                else:
                    print(f"  OK      {rel} (no markers found)")

    if check_mode:
        if stale_files:
            if not quiet:
                print(f"\n❌ STALE: {len(stale_files)} file(s) need docs-sync:")
                for f in stale_files:
                    print(f"  - {f}")
                print("\nRun: python scripts/docs_sync.py")
            return 1
        if not quiet:
            print("\n✅ All docs are in sync")
        return 0

    if not check_mode and not diff_mode and not quiet:
        print(f"\n✅ Updated {total_updated} markers across {len(TARGET_FILES)} files")

    return 0


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    sys.exit(main())
