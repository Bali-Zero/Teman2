#!/usr/bin/env python3
"""Docs Audit — generate DOCS_INVENTORY.md from a walk of docs/**/*.md.

Rules (first match wins):
  1. ARCHIVED if path starts with docs/archive/
  2. ARCHIVED (orphan) if mtime > --orphan-days AND refs_in == 0 AND not in whitelist
  3. STALE if broken_links > 0 OR DOCSYNC drift OR member of a duplicate cluster
  4. LIVE otherwise

Mtime is derived from `git log` (last commit touching the file), not from
`os.stat().st_mtime`, because filesystem mtime is reset by git checkout and
CI `actions/checkout`. Untracked files fall back to stat.

See docs/superpowers/specs/2026-04-24-docs-hygiene-design.md for the full spec.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DOCSYNC_BLOCK_RE = re.compile(
    r"<!--\s*DOCSYNC:([A-Z_]+)_START\s*-->(.*?)<!--\s*DOCSYNC:\1_END\s*-->",
    re.DOTALL,
)


@dataclass
class DocRow:
    path: str
    status: str = "LIVE"
    mtime_days: int = 0
    refs_in: int = 0
    broken: int = 0
    drift: bool = False
    cluster: Optional[str] = None
    action: str = "—"


@dataclass
class ClusterDef:
    key: str
    members: List[str]
    canonical: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".", help="Repo root (default: .)")
    p.add_argument(
        "--orphan-days",
        type=int,
        default=90,
        help="Orphan threshold in days (default 90).",
    )
    p.add_argument(
        "--whitelist",
        action="append",
        default=[],
        help="Repo-relative path exempt from orphan archival. Repeatable.",
    )
    p.add_argument(
        "--cluster",
        action="append",
        default=[],
        help="Cluster definition: key:member1,member2,...:canonical. Repeatable.",
    )
    p.add_argument(
        "--docsync-key",
        action="append",
        default=[],
        help="Override DOCSYNC key expected value: KEY:value. Repeatable.",
    )
    p.add_argument("--check", action="store_true", help="Compare with committed inventory; exit 1 on drift.")
    p.add_argument("--apply", action="store_true", help="Physically git mv orphans to docs/archive/. Default: dry-run.")
    p.add_argument("--quiet", action="store_true", help="No stdout on success.")
    p.add_argument("--json", action="store_true", help="Emit stats JSON on stdout.")
    return p.parse_args()


def parse_clusters(raw: List[str]) -> List[ClusterDef]:
    clusters: List[ClusterDef] = []
    for r in raw:
        parts = r.split(":")
        if len(parts) != 3:
            raise SystemExit(f"Invalid --cluster spec (need key:members:canonical): {r}")
        key, members_csv, canonical = parts
        members = [m.strip() for m in members_csv.split(",") if m.strip()]
        if canonical not in members:
            raise SystemExit(f"Cluster {key}: canonical {canonical} not in members {members}")
        clusters.append(ClusterDef(key=key, members=members, canonical=canonical))
    return clusters


def parse_docsync_keys(raw: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for r in raw:
        if ":" not in r:
            raise SystemExit(f"Invalid --docsync-key (need KEY:value): {r}")
        k, v = r.split(":", 1)
        out[k] = v
    return out


def walk_docs(repo: Path) -> List[Path]:
    """Return docs/**/*.md files visible to git, excluding DOCS_INVENTORY.md.

    "Visible to git" = tracked OR untracked-but-not-gitignored. Files matched
    by .gitignore are excluded so that local dev machines (which may carry
    historical .md leftovers from pre-current-gitignore eras) match CI's
    fresh clone exactly. Falls back to filesystem rglob when git is missing.
    """
    docs_root = repo / "docs"
    if not docs_root.is_dir():
        return []
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "docs/"],
            cwd=repo, check=True, capture_output=True, text=True,
        ).stdout
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "docs/"],
            cwd=repo, check=True, capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(p for p in docs_root.rglob("*.md") if p.name != "DOCS_INVENTORY.md")
    seen: set[str] = set()
    paths: List[Path] = []
    for line in (tracked + untracked).splitlines():
        rel = line.strip()
        if not rel or not rel.endswith(".md") or rel.endswith("DOCS_INVENTORY.md") or rel in seen:
            continue
        seen.add(rel)
        paths.append(repo / rel)
    return sorted(paths)


def compute_refs_in(repo: Path, target: Path) -> int:
    """Count other .md files (in docs/ + reference root files) that contain target's basename."""
    basename = target.name
    # Scan roots: docs/** and a handful of root files. Skip the file itself + archive dest.
    # Use walk_docs() (git-aware) so candidates match local↔CI exactly.
    candidates: List[Path] = [p for p in walk_docs(repo) if p != target]
    for root_name in ("CLAUDE.md", "INDEX.md", "SYMBIOSIS.md", "VADEMECUM.md", "AGENTS.md", "GEMINI.md", "AUTONOMOUS_OPS.md"):
        rp = repo / root_name
        if rp.is_file() and rp != target:
            candidates.append(rp)
    apps_root = repo / "apps"
    if apps_root.is_dir():
        for p in apps_root.glob("*/README.md"):
            if p != target:
                candidates.append(p)
    count = 0
    for c in candidates:
        try:
            if basename in c.read_text(encoding="utf-8", errors="ignore"):
                count += 1
        except OSError:
            continue
    return count


INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code_regions(content: str) -> str:
    """Remove fenced code blocks (```...```) and inline backtick spans
    (`...`) so example links inside code samples are not treated as real
    markdown links. Cheap and good-enough for our audit — not a full parser.
    """
    out: List[str] = []
    in_fence = False
    for line in content.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            # Strip inline `code` spans within the line.
            out.append(INLINE_CODE_RE.sub("", line))
    return "\n".join(out)


def compute_broken_links(repo: Path, doc: Path) -> int:
    """Count markdown links to local files that do not exist. URLs/anchors skipped.
    Links inside fenced code blocks are ignored (they are examples, not real).
    """
    try:
        raw = doc.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    content = _strip_code_regions(raw)
    broken = 0
    for match in LINK_RE.finditer(content):
        target = match.group(1).strip()
        # Skip URLs and pure anchors
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # Strip anchor part
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        resolved = (doc.parent / target_path).resolve()
        try:
            resolved.relative_to(repo.resolve())
        except ValueError:
            # Outside repo → skip
            continue
        if not resolved.exists():
            broken += 1
    return broken


def compute_mtime_days(repo: Path, doc: Path) -> int:
    """Age of `doc` in days, preferring git history over os.stat().

    Filesystem mtime is reset by `git checkout`, `git worktree add`, and CI
    `actions/checkout` — so `os.stat().st_mtime` lies inside a worktree. Use
    `git log -1 --format=%ct` on the file for the true semantic age. Fall back
    to `os.stat()` when the file is untracked (new, uncommitted) or git is
    absent.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%ct", "--", str(doc.relative_to(repo))],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            commit_ts = int(stdout)
            return (
                datetime.now(tz=timezone.utc).date()
                - datetime.fromtimestamp(commit_ts, tz=timezone.utc).date()
            ).days
    except (subprocess.SubprocessError, ValueError, OSError):
        pass
    # Fallback for untracked files or when git is unavailable.
    return (
        datetime.now(tz=timezone.utc).date()
        - datetime.fromtimestamp(doc.stat().st_mtime, tz=timezone.utc).date()
    ).days


def compute_drift(doc: Path, expected_keys: Dict[str, str]) -> bool:
    """True if doc contains a DOCSYNC block whose enclosed value != expected_keys[key]."""
    if not expected_keys:
        return False
    try:
        content = doc.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for match in DOCSYNC_BLOCK_RE.finditer(content):
        key = match.group(1)
        body = match.group(2).strip()
        if key in expected_keys and expected_keys[key] not in body:
            return True
    return False


def classify(
    doc: Path,
    repo: Path,
    orphan_days: int,
    whitelist: List[str],
    clusters: List[ClusterDef],
    expected_keys: Dict[str, str],
) -> DocRow:
    rel = str(doc.relative_to(repo))
    row = DocRow(path=rel)

    # Rule 1: already archived
    if rel.startswith("docs/archive/"):
        row.status = "ARCHIVED"
        return row

    row.mtime_days = compute_mtime_days(repo, doc)
    row.refs_in = compute_refs_in(repo, doc)
    row.broken = compute_broken_links(repo, doc)
    row.drift = compute_drift(doc, expected_keys)

    # Cluster membership
    for cl in clusters:
        if rel in cl.members:
            row.cluster = cl.key
            if rel == cl.canonical:
                row.action = f"keep (canonical of {cl.key})"
            else:
                row.action = f"archive (superseded by {cl.canonical})"
            row.status = "STALE"
            # Cluster membership always wins over LIVE — short-circuit after setting
            return row

    # Rule 2: orphan
    if (
        row.mtime_days > orphan_days
        and row.refs_in == 0
        and rel not in whitelist
    ):
        row.status = "ARCHIVED"
        row.action = f"archive: orphan, mtime={row.mtime_days}d, refs=0"
        return row

    # Rule 3: stale (broken links OR drift)
    if row.broken > 0 or row.drift:
        row.status = "STALE"
        reasons = []
        if row.broken > 0:
            reasons.append(f"{row.broken} broken link(s)")
        if row.drift:
            reasons.append("DOCSYNC drift")
        row.action = "fix: " + "; ".join(reasons)
        return row

    # Rule 4: LIVE
    if rel in whitelist:
        row.action = "whitelist"
    return row


def render_inventory(rows: List[DocRow], clusters: List[ClusterDef]) -> str:
    """Produce DOCS_INVENTORY.md content."""
    total = len(rows)
    by_status: Dict[str, int] = {"LIVE": 0, "STALE": 0, "ARCHIVED": 0}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    drift_n = sum(1 for r in rows if r.drift)
    broken_n = sum(1 for r in rows if r.broken > 0)
    orphan_n = sum(1 for r in rows if r.action.startswith("archive: orphan"))

    ts = time.strftime("%Y-%m-%d %H:%M %Z")

    out: List[str] = []
    out.append("# Documentation Inventory")
    out.append("")
    out.append(f"_Auto-generated by `scripts/docs_audit.py`. Last run: {ts}_")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append("| Status   | Count | % |")
    out.append("|----------|-------|---|")
    for st in ("LIVE", "STALE", "ARCHIVED"):
        cnt = by_status.get(st, 0)
        pct = (100 * cnt / total) if total else 0
        out.append(f"| {st:<8} | {cnt:>5} | {pct:.0f}% |")
    out.append("")
    out.append(f"**Drift:** {drift_n} · **Broken links:** {broken_n} · **Orphans:** {orphan_n}")
    out.append("")
    out.append("## Files")
    out.append("")
    out.append("| File | Status | mtime_days | refs_in | broken | drift | cluster | action |")
    out.append("|------|--------|-----------:|--------:|-------:|-------|---------|--------|")
    for r in rows:
        drift_s = "yes" if r.drift else "no"
        cluster_s = r.cluster or "—"
        action_s = r.action
        out.append(
            f"| {r.path} | {r.status} | {r.mtime_days} | {r.refs_in} | {r.broken} | {drift_s} | {cluster_s} | {action_s} |"
        )
    out.append("")

    # Details sections (only if relevant)
    stale_by_cluster: Dict[str, List[DocRow]] = {}
    for r in rows:
        if r.cluster:
            stale_by_cluster.setdefault(r.cluster, []).append(r)
    if stale_by_cluster:
        out.append("## STALE details")
        out.append("")
        for cl in clusters:
            members_in_cluster = stale_by_cluster.get(cl.key, [])
            if not members_in_cluster:
                continue
            out.append(f"### `{cl.key}` cluster")
            out.append(f"Canonical: `{cl.canonical}`")
            archive_candidates = [m for m in cl.members if m != cl.canonical]
            if archive_candidates:
                out.append(f"Archive candidates: {', '.join('`' + a + '`' for a in archive_candidates)}")
            out.append("")

    broken_rows = [r for r in rows if r.broken > 0]
    if broken_rows:
        out.append("### Broken links")
        for r in broken_rows:
            out.append(f"- `{r.path}`: {r.broken} broken link(s)")
        out.append("")

    orphan_rows = [r for r in rows if r.action.startswith("archive: orphan")]
    if orphan_rows:
        out.append("### Orphans (mtime>{}d AND refs_in==0)".format(0))
        for r in orphan_rows:
            out.append(f"- `{r.path}` (mtime={r.mtime_days}d, zero inbound refs)")
        out.append("")

    return "\n".join(out) + "\n"


def apply_moves(repo: Path, rows: List[DocRow], use_git: bool = True) -> int:
    """Move files whose action starts with 'archive' into docs/archive/YYYY-MM-<slug>/. Return moved count."""
    moved = 0
    slug = time.strftime("%Y-%m-orphans")
    dest = repo / "docs" / "archive" / slug
    dest.mkdir(parents=True, exist_ok=True)
    for r in rows:
        if not r.action.startswith("archive: orphan"):
            continue
        src = repo / r.path
        if not src.exists():
            continue
        target = dest / src.name
        if use_git:
            subprocess.run(["git", "-C", str(repo), "mv", str(src), str(target)], check=True)
        else:
            src.rename(target)
        moved += 1
    return moved


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    whitelist = args.whitelist
    clusters = parse_clusters(args.cluster)
    expected_keys = parse_docsync_keys(args.docsync_key)

    docs = walk_docs(repo)
    rows = [classify(d, repo, args.orphan_days, whitelist, clusters, expected_keys) for d in docs]

    new_content = render_inventory(rows, clusters)
    inventory_path = repo / "docs" / "DOCS_INVENTORY.md"
    old_content = inventory_path.read_text(encoding="utf-8") if inventory_path.exists() else ""

    # Strip "Last run:" line for comparison (timestamp changes every run)
    def strip_ts(s: str) -> str:
        return "\n".join(l for l in s.splitlines() if "Last run:" not in l)

    stale_delta = strip_ts(new_content) != strip_ts(old_content)

    if args.json:
        payload = {
            "total": len(rows),
            "live": sum(1 for r in rows if r.status == "LIVE"),
            "stale": sum(1 for r in rows if r.status == "STALE"),
            "archived": sum(1 for r in rows if r.status == "ARCHIVED"),
            "drift": sum(1 for r in rows if r.drift),
            "broken": sum(1 for r in rows if r.broken > 0),
            "orphans": sum(1 for r in rows if r.action.startswith("archive: orphan")),
            "files": [
                {
                    "path": r.path,
                    "status": r.status,
                    "mtime_days": r.mtime_days,
                    "refs_in": r.refs_in,
                    "broken": r.broken,
                    "drift": r.drift,
                    "cluster": r.cluster,
                    "action": r.action,
                }
                for r in rows
            ],
        }
        print(json.dumps(payload, indent=2))

    if args.check:
        return 1 if stale_delta else 0

    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(new_content, encoding="utf-8")

    if args.apply:
        moved = apply_moves(repo, rows)
        if not args.quiet:
            print(f"Moved {moved} orphan files to docs/archive/", file=sys.stderr)

    if not args.quiet and stale_delta:
        print(f"Inventory updated: {inventory_path}", file=sys.stderr)

    return 1 if stale_delta else 0


if __name__ == "__main__":
    sys.exit(main())
