#!/usr/bin/env python3
"""docs-history-analyzer — monthly analytics on docs/** evolution.

Mines git log over the last N months (default 6) to surface evolutionary
patterns in the documentation corpus: birth rate, death rate (archive/delete),
rename/move activity, inbound-ref decay, orphan prediction.

Output: docs/DOCS_TRENDS.md (auto-generated, gitignored from manual edits).

Use: run once a month as cron (or manually) to see how the corpus is
evolving and spot corrections the weekly guardian missed.

Pure stdlib. No network. ~2-5s on a 570-file corpus with 1-year history.

Usage:
    python scripts/docs_history_analyzer.py            # write DOCS_TRENDS.md
    python scripts/docs_history_analyzer.py --months 12
    python scripts/docs_history_analyzer.py --json     # stats JSON to stdout
    python scripts/docs_history_analyzer.py --quiet    # no stdout
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class DocEvent:
    """One git-log event touching a doc file."""
    sha: str
    ts: int          # unix epoch
    path: str
    change: str      # A / M / D / R (added / modified / deleted / renamed)
    renamed_from: Optional[str] = None


@dataclass
class DocBiography:
    """Cumulative history of one doc (keyed by its *current* path)."""
    path: str
    first_seen: int = 0       # unix epoch of first commit touching it
    last_touch: int = 0       # unix epoch of latest commit
    commits: int = 0          # count of commits that modified it
    renamed_history: List[str] = field(default_factory=list)  # previous paths
    alive: bool = True        # not deleted
    archived: bool = False    # lives under docs/archive/


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".", help="Repo root")
    p.add_argument("--months", type=int, default=6,
                   help="How many months back to analyze (default 6)")
    p.add_argument("--json", action="store_true",
                   help="Emit stats JSON on stdout instead of writing MD")
    p.add_argument("--quiet", action="store_true",
                   help="No stdout on success")
    return p.parse_args()


def git_log_events(repo: Path, since_days: int) -> List[DocEvent]:
    """Walk git log over the last N days, collect A/M/D/R events for docs/**/*.md."""
    cmd = [
        "git", "-C", str(repo), "log",
        f"--since={since_days}.days.ago",
        "--no-merges",
        "--name-status",
        "--pretty=format:__COMMIT__%H%x00%ct",
        "--",
        "docs/",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (subprocess.SubprocessError, OSError) as e:
        sys.stderr.write(f"git log failed: {e}\n")
        return []
    if result.returncode != 0:
        sys.stderr.write(f"git log exit {result.returncode}: {result.stderr[:200]}\n")
        return []

    events: List[DocEvent] = []
    current_sha = ""
    current_ts = 0
    for raw in result.stdout.splitlines():
        if raw.startswith("__COMMIT__"):
            body = raw[len("__COMMIT__"):]
            parts = body.split("\0", 1)
            if len(parts) != 2:
                continue
            current_sha = parts[0]
            try:
                current_ts = int(parts[1])
            except ValueError:
                current_ts = 0
            continue
        if not raw.strip() or not current_sha:
            continue
        # Parse status + path(s). For R (rename): "R100\told\tnew"
        parts = raw.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            old_p, new_p = parts[1], parts[2]
            if new_p.endswith(".md"):
                events.append(DocEvent(
                    sha=current_sha, ts=current_ts,
                    path=new_p, change="R", renamed_from=old_p,
                ))
        elif status in ("A", "M", "D") and len(parts) >= 2:
            path = parts[1]
            if path.endswith(".md"):
                events.append(DocEvent(
                    sha=current_sha, ts=current_ts,
                    path=path, change=status,
                ))
    return events


def build_biographies(events: List[DocEvent]) -> Dict[str, DocBiography]:
    """Collapse events into per-doc biographies, following renames."""
    # Sort oldest first for forward construction
    events_sorted = sorted(events, key=lambda e: e.ts)

    # alias map: original path → current path (updated on rename)
    alias: Dict[str, str] = {}
    bios: Dict[str, DocBiography] = {}

    def resolve(path: str) -> str:
        # Walk alias chain
        seen = set()
        while path in alias and path not in seen:
            seen.add(path)
            path = alias[path]
        return path

    for ev in events_sorted:
        if ev.change == "R" and ev.renamed_from:
            # Redirect old path → new path
            old_resolved = resolve(ev.renamed_from)
            alias[old_resolved] = ev.path
            # Migrate the biography if it existed under the old name
            if old_resolved in bios:
                old_bio = bios.pop(old_resolved)
                old_bio.renamed_history.append(old_resolved)
                old_bio.path = ev.path
                old_bio.last_touch = ev.ts
                old_bio.commits += 1
                bios[ev.path] = old_bio
            else:
                # Rename of a doc we didn't see born in the window
                bios[ev.path] = DocBiography(
                    path=ev.path, first_seen=ev.ts, last_touch=ev.ts,
                    commits=1, renamed_history=[ev.renamed_from],
                )
            continue

        resolved = resolve(ev.path)
        bio = bios.get(resolved)
        if bio is None:
            bio = DocBiography(path=resolved, first_seen=ev.ts, last_touch=ev.ts, commits=0)
            bios[resolved] = bio
        bio.last_touch = ev.ts
        bio.commits += 1
        if ev.change == "D":
            bio.alive = False

    # Post: mark archived status from current path
    for bio in bios.values():
        if bio.path.startswith("docs/archive/"):
            bio.archived = True
    return bios


def compute_stats(bios: Dict[str, DocBiography], since_ts: int) -> Dict:
    """Derive aggregate stats for the report."""
    total = len(bios)
    alive = sum(1 for b in bios.values() if b.alive)
    archived = sum(1 for b in bios.values() if b.archived)
    deleted = sum(1 for b in bios.values() if not b.alive)
    renamed = sum(1 for b in bios.values() if b.renamed_history)

    # Birth rate: files whose first_seen falls inside the window
    born_in_window = sum(1 for b in bios.values() if b.first_seen >= since_ts)

    # Death rate: files that moved to archive/ OR were deleted inside window.
    # Approximation: a doc is "died in window" if alive=False OR archived=True
    # AND last_touch >= since_ts. This overcounts if the doc was archived long
    # ago and then touched by DOCSYNC — acceptable noise.
    died_in_window = sum(
        1 for b in bios.values()
        if (not b.alive or b.archived) and b.last_touch >= since_ts
    )

    # Activity percentiles
    commit_counts = sorted(b.commits for b in bios.values()) or [0]
    def pct(lst, p):
        if not lst:
            return 0
        k = max(0, min(len(lst) - 1, int(len(lst) * p / 100)))
        return lst[k]
    p50 = pct(commit_counts, 50)
    p90 = pct(commit_counts, 90)

    # Top 10 most-touched
    top_touched = sorted(bios.values(), key=lambda b: -b.commits)[:10]
    # Top 10 oldest-inactive (first_seen old, last_touch old, alive)
    now = int(time.time())
    quiet_live = sorted(
        (b for b in bios.values() if b.alive and not b.archived),
        key=lambda b: b.last_touch,
    )[:10]

    return {
        "total_docs_touched_in_window": total,
        "currently_alive": alive,
        "currently_archived": archived,
        "deleted_outright": deleted,
        "renamed_at_least_once": renamed,
        "born_in_window": born_in_window,
        "died_in_window": died_in_window,
        "commits_per_doc_p50": p50,
        "commits_per_doc_p90": p90,
        "top_10_most_touched": [
            {"path": b.path, "commits": b.commits} for b in top_touched
        ],
        "top_10_quiet_live": [
            {
                "path": b.path,
                "last_touch_days_ago": int((now - b.last_touch) / 86400) if b.last_touch else None,
            }
            for b in quiet_live
        ],
    }


def render_report(stats: Dict, months: int) -> str:
    ts = time.strftime("%Y-%m-%d %H:%M %Z")
    out: List[str] = []
    out.append("# Documentation Trends")
    out.append("")
    out.append(f"_Auto-generated by `scripts/docs_history_analyzer.py`. Last run: {ts}_")
    out.append("")
    out.append(f"Window analyzed: last **{months} months** of git log on `docs/**/*.md`.")
    out.append("")
    out.append("## Corpus activity")
    out.append("")
    out.append("| Metric | Value |")
    out.append("|---|---|")
    out.append(f"| Docs touched in window | {stats['total_docs_touched_in_window']} |")
    out.append(f"| Currently alive | {stats['currently_alive']} |")
    out.append(f"| Currently archived | {stats['currently_archived']} |")
    out.append(f"| Deleted outright | {stats['deleted_outright']} |")
    out.append(f"| Renamed at least once | {stats['renamed_at_least_once']} |")
    out.append(f"| Born in window | {stats['born_in_window']} |")
    out.append(f"| Died in window (archived or deleted) | {stats['died_in_window']} |")
    out.append(f"| Commits/doc p50 | {stats['commits_per_doc_p50']} |")
    out.append(f"| Commits/doc p90 | {stats['commits_per_doc_p90']} |")
    out.append("")

    out.append("## Top 10 most-touched docs (in window)")
    out.append("")
    out.append("High activity suggests central / evolving docs. Rapid changes here are")
    out.append("expected; low changes might suggest they became stable or stale.")
    out.append("")
    out.append("| Doc | Commits |")
    out.append("|---|---:|")
    for item in stats["top_10_most_touched"]:
        out.append(f"| `{item['path']}` | {item['commits']} |")
    out.append("")

    out.append("## Top 10 quiet-but-alive docs")
    out.append("")
    out.append("Alive (not archived, not deleted) but untouched the longest. These are")
    out.append("candidate future orphans — inspect before they decay.")
    out.append("")
    out.append("| Doc | Days since last touch |")
    out.append("|---|---:|")
    for item in stats["top_10_quiet_live"]:
        days = item["last_touch_days_ago"]
        days_str = str(days) if days is not None else "—"
        out.append(f"| `{item['path']}` | {days_str} |")
    out.append("")

    out.append("## How to read this")
    out.append("")
    out.append("- **High died-in-window** vs **born-in-window** → corpus shrinking (healthy for hygiene).")
    out.append("- **Rename count high** → directory restructuring phase.")
    out.append("- **Quiet-live list matches** `DOCS_INVENTORY.md` orphan candidates → weekly guardian is catching them.")
    out.append("- **Quiet-live list contains surprises** → the audit thresholds (90d, whitelist) may need tuning.")
    out.append("")
    out.append("## References")
    out.append("")
    out.append("- Weekly inventory: [DOCS_INVENTORY.md](DOCS_INVENTORY.md)")
    out.append("- Design: `docs/superpowers/specs/2026-04-24-docs-hygiene-design.md`")
    out.append("- Generator: `scripts/docs_history_analyzer.py` (monthly cron)")
    out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    months = args.months
    since_days = months * 30  # approximation is fine

    events = git_log_events(repo, since_days)
    bios = build_biographies(events)
    since_ts = int(time.time()) - since_days * 86400
    stats = compute_stats(bios, since_ts)

    if args.json:
        print(json.dumps(stats, indent=2))
        return 0

    report = render_report(stats, months)
    out_path = repo / "docs" / "DOCS_TRENDS.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    if not args.quiet:
        print(f"Trends report written: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
