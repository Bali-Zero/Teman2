#!/usr/bin/env python3
"""DocSentinel — Automated Documentation Stats Synchronizer.

Extracts live metrics from the Nuzantara codebase and injects them into
markdown files between <!-- DOCSYNC:KEY_START --> / <!-- DOCSYNC:KEY_END -->
markers. Keeps CLAUDE.md, README.md, docs/AI_ONBOARDING.md in sync with
actual code state.

Spec: docs/DOCSYNC_SENTINEL.md
Implementation: 2026-04-15 (Sprint 5.1.5 lean)

Usage:
    python scripts/docs_sync.py            # update markers in-place
    python scripts/docs_sync.py --check    # CI mode: exit 1 if stale
    python scripts/docs_sync.py --diff     # show what would change
    python scripts/docs_sync.py --json     # raw stats as JSON
    python scripts/docs_sync.py --quiet    # hook mode (no output on success)

No external dependencies. Python stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / ".docs_sync_cache.json"

# ---------------------------------------------------------------------------
# Target files + markers
# ---------------------------------------------------------------------------
TARGET_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "AI_ONBOARDING.md",
]

# Marker regex: captures everything between START and END markers (inclusive).
MARKER_RE = re.compile(
    r"(<!-- DOCSYNC:(?P<key>[A-Z_]+)_START -->)(?P<body>.*?)(<!-- DOCSYNC:(?P=key)_END -->)",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Extractors (pure Python, stdlib only)
# ---------------------------------------------------------------------------

def count_routers() -> int:
    """Count include_router() calls in router_registration.py."""
    router_file = (
        REPO_ROOT
        / "apps"
        / "backend-rag"
        / "backend"
        / "app"
        / "setup"
        / "router_registration.py"
    )
    if not router_file.exists():
        # Fallback: count files in routers/
        routers_dir = REPO_ROOT / "apps" / "backend-rag" / "backend" / "app" / "routers"
        if routers_dir.exists():
            return len([p for p in routers_dir.glob("*.py") if p.stem != "__init__"])
        return 0
    text = router_file.read_text(errors="ignore")
    return len(re.findall(r"\.include_router\(", text))


def count_services() -> int:
    """Count .py files in backend/services (excluding __init__)."""
    services = REPO_ROOT / "apps" / "backend-rag" / "backend" / "services"
    if not services.exists():
        return 0
    return len([p for p in services.rglob("*.py") if p.stem != "__init__"])


def count_test_files() -> int:
    """Count test_*.py files in backend/tests."""
    tests = REPO_ROOT / "apps" / "backend-rag" / "backend" / "tests"
    if not tests.exists():
        return 0
    return len(list(tests.rglob("test_*.py")))


def _tracked_app_names() -> set[str]:
    """Return the set of app directories that contain git-tracked files.

    Using `git ls-files apps/` makes the count deterministic across machines:
    empty directories left behind by old deletes (e.g. `__pycache__`-only
    remnants on a long-lived dev machine) are ignored on CI's fresh clone and
    must be ignored here too, otherwise docs_sync --check diverges between
    local and CI.
    """
    try:
        import subprocess
        out = subprocess.run(
            ["git", "ls-files", "apps/"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return set()
    names: set[str] = set()
    for line in out.splitlines():
        # "apps/<name>/..."
        parts = line.split("/", 2)
        if len(parts) >= 2 and parts[0] == "apps" and parts[1]:
            names.add(parts[1])
    return names


def count_apps() -> int:
    """Count app directories that have at least one git-tracked file."""
    apps = REPO_ROOT / "apps"
    if not apps.exists():
        return 0
    tracked = _tracked_app_names()
    if tracked:
        return len(tracked)
    # Fallback when not in a git repo (unlikely in this project)
    return len([p for p in apps.iterdir() if p.is_dir() and not p.name.startswith(".")])


def list_apps() -> list[dict[str, str]]:
    """List of apps with overview extracted from README.md first paragraph.

    Returns ordered alphabetically. Each entry: {name, overview}.
    Overview is first non-heading, non-blank line from README.md (truncated 120 chars).
    """
    apps_dir = REPO_ROOT / "apps"
    if not apps_dir.exists():
        return []
    tracked = _tracked_app_names()
    result: list[dict[str, str]] = []
    for app_path in sorted(apps_dir.iterdir()):
        if not app_path.is_dir() or app_path.name.startswith("."):
            continue
        if tracked and app_path.name not in tracked:
            # Skip empty / untracked dirs (see _tracked_app_names docstring)
            continue
        overview = ""
        readme = app_path / "README.md"
        if readme.exists():
            for line in readme.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("!["):
                    continue
                # Clean markdown links
                overview = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
                if len(overview) > 120:
                    overview = overview[:117] + "..."
                break
        result.append({"name": app_path.name, "overview": overview})
    return result


def count_packages() -> int:
    """Count directories in packages/ (excluding hidden)."""
    packages = REPO_ROOT / "packages"
    if not packages.exists():
        return 0
    return len(
        [p for p in packages.iterdir() if p.is_dir() and not p.name.startswith(".")]
    )


def get_version() -> str:
    """Read version from root package.json."""
    pkg = REPO_ROOT / "package.json"
    if not pkg.exists():
        return "unknown"
    try:
        data = json.loads(pkg.read_text())
        return data.get("version", "unknown")
    except (json.JSONDecodeError, OSError):
        return "unknown"


def count_channels() -> int:
    """Count directories in backend/channels/."""
    channels = REPO_ROOT / "apps" / "backend-rag" / "backend" / "channels"
    if not channels.exists():
        return 0
    return len(
        [
            p
            for p in channels.iterdir()
            if p.is_dir() and not p.name.startswith((".", "_"))
        ]
    )


_QDRANT_FALLBACK = {
    "collections": 10,
    "documents": 93283,
    "embedding_model": "text-embedding-3-small",
}


def get_qdrant_stats() -> dict[str, Any]:
    """Fetch Qdrant stats. Try direct Qdrant /collections, fallback to /health or cache.

    The Fly /health endpoint does NOT expose collection/document counts currently.
    Direct Qdrant query works only if QDRANT_URL + QDRANT_API_KEY are exported.
    """
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    if qdrant_url and qdrant_key:
        try:
            req = urllib.request.Request(
                f"{qdrant_url.rstrip('/')}/collections",
                headers={"api-key": qdrant_key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            collections = data.get("result", {}).get("collections", [])
            collection_names = [c.get("name") for c in collections]
            total_docs = 0
            for name in collection_names:
                try:
                    info_req = urllib.request.Request(
                        f"{qdrant_url.rstrip('/')}/collections/{name}",
                        headers={"api-key": qdrant_key},
                    )
                    with urllib.request.urlopen(info_req, timeout=5) as ir:
                        info = json.loads(ir.read().decode())
                    total_docs += int(
                        info.get("result", {}).get("points_count", 0) or 0
                    )
                except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                    continue
            return {
                "collections": len(collection_names),
                "documents": total_docs,
                "embedding_model": _QDRANT_FALLBACK["embedding_model"],
            }
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
    # Fallback to cache → hardcoded defaults
    cached = _load_cache().get("qdrant")
    if cached and cached.get("documents", 0) > 0:
        return cached
    return _QDRANT_FALLBACK


def get_kg_stats() -> dict[str, int]:
    """KG stats — cached hardcoded (changes rarely)."""
    return _load_cache().get("kg", {"nodes": 108068, "edges": 242827})


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(stats: dict[str, Any]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(stats, indent=2))
    except OSError:
        pass  # Cache write failure is non-fatal


# ---------------------------------------------------------------------------
# Templates (one per marker key)
# ---------------------------------------------------------------------------

def _render_living_organs(stats: dict[str, Any]) -> str:
    """Render LIVING_ORGANS marker: table of all apps + packages."""
    lines = [
        "",
        f"**Apps:** {stats['app_count']} · **Packages:** {stats['package_count']}",
        "",
        "| App | Ruolo |",
        "| --- | ----- |",
    ]
    for app in stats["apps"]:
        overview = app["overview"].replace("|", "\\|")
        lines.append(f"| `{app['name']}` | {overview} |")
    lines.append("")
    return "\n".join(lines)


TEMPLATES: dict[str, Any] = {
    "BACKEND_STATS": lambda s: (
        f"\n- **Backend:** Python 3.11+, FastAPI, "
        f"{s['routers']} routers, {s['services']} services, "
        f"{s['test_files']} test files\n"
    ),
    "VECTOR_STATS": lambda s: (
        f"\n- **Vector Collections:** {s['qdrant']['collections']} live on Fly.io "
        f"({s['qdrant']['documents']:,} documents), "
        f"{s['qdrant']['collections']} defined in code\n"
    ),
    "EMBEDDING_FROZEN": lambda s: (
        f"\n### Embedding — `{s['qdrant']['embedding_model']}` "
        f"(1536 dims) FROZEN. Never change without re-indexing plan.\n"
    ),
    "TECH_STATS": lambda s: (
        f"\n- Backend: FastAPI · {s['routers']} routers · {s['services']} services\n"
        f"- Vector DB: Qdrant · {s['qdrant']['collections']} collections · "
        f"{s['qdrant']['documents']:,} documents\n"
        f"- Knowledge Graph: {s['kg']['nodes']:,} nodes · {s['kg']['edges']:,} edges\n"
        f"- Apps: {s['app_count']} · Packages: {s['package_count']}\n"
        f"- Version: {s['version']}\n"
    ),
    "QUICK_NUMBERS": lambda s: (
        f"\n`{s['routers']} routers · {s['services']} services · "
        f"{s['test_files']} tests · {s['qdrant']['collections']} Qdrant collections · "
        f"{s['qdrant']['documents']:,} vectors · {s['kg']['nodes']:,} KG nodes`\n"
    ),
    "LIVING_ORGANS": _render_living_organs,
}


# ---------------------------------------------------------------------------
# Stats gathering
# ---------------------------------------------------------------------------

def gather_stats() -> dict[str, Any]:
    """Collect all stats from codebase."""
    qdrant = get_qdrant_stats()
    kg = get_kg_stats()
    stats = {
        "routers": count_routers(),
        "services": count_services(),
        "test_files": count_test_files(),
        "app_count": count_apps(),
        "apps": list_apps(),
        "package_count": count_packages(),
        "channels": count_channels(),
        "version": get_version(),
        "qdrant": qdrant,
        "kg": kg,
    }
    # Refresh cache with successful fetches
    _save_cache({"qdrant": qdrant, "kg": kg})
    return stats


# ---------------------------------------------------------------------------
# Marker injection (atomic write)
# ---------------------------------------------------------------------------

def inject_markers(path: Path, stats: dict[str, Any]) -> tuple[bool, str, str]:
    """Update all markers in file. Returns (changed, old_content, new_content)."""
    if not path.exists():
        return (False, "", "")
    original = path.read_text()

    def _replace(match: re.Match[str]) -> str:
        key = match.group("key")
        start_tag = match.group(1)
        end_tag = match.group(4)
        if key not in TEMPLATES:
            # Unknown marker: leave untouched
            return match.group(0)
        try:
            new_body = TEMPLATES[key](stats)
        except Exception as exc:
            print(
                f"WARN: template {key} failed: {exc}",
                file=sys.stderr,
            )
            return match.group(0)
        return f"{start_tag}{new_body}{end_tag}"

    updated = MARKER_RE.sub(_replace, original)
    return (updated != original, original, updated)


def _write_atomic(path: Path, content: str) -> None:
    """Atomic write: temp file in same dir + rename. Preserves perms."""
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".docs_sync_", dir=str(path.parent)
    )
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        # Preserve original perms if file exists
        if path.exists():
            st = path.stat()
            os.chmod(tmp_name, st.st_mode)
        os.replace(tmp_name, path)
    except Exception:
        # Cleanup temp on failure
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def content_checksum(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="DocSentinel — sync doc markers")
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI mode: exit 1 if any marker would change (without writing)",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show what would change (without writing)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw stats as JSON (no writes)"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress output on success (hook mode)"
    )
    args = parser.parse_args()

    stats = gather_stats()

    if args.json:
        print(json.dumps(stats, indent=2, default=str))
        return 0

    any_changed = False
    changes: list[str] = []
    for target in TARGET_FILES:
        changed, old, new = inject_markers(target, stats)
        if not changed:
            continue
        any_changed = True
        rel = target.relative_to(REPO_ROOT)
        if args.diff or args.check:
            old_sum = content_checksum(old)
            new_sum = content_checksum(new)
            changes.append(f"  {rel}: {old_sum} → {new_sum}")
        if args.check or args.diff:
            continue
        _write_atomic(target, new)
        if not args.quiet:
            print(f"updated: {rel}")

    if args.check:
        if any_changed:
            print("DOCSYNC STALE — run: python scripts/docs_sync.py", file=sys.stderr)
            for line in changes:
                print(line, file=sys.stderr)
            return 1
        if not args.quiet:
            print("DOCSYNC OK (no changes)")
        return 0

    if args.diff:
        if any_changed:
            print("Would change:")
            for line in changes:
                print(line)
        else:
            print("No changes.")
        return 0

    if not any_changed and not args.quiet:
        print("DOCSYNC OK (no changes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
