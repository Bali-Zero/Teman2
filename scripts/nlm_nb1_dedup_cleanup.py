#!/usr/bin/env python3
"""
NB-1 Duplicate Source Cleanup (ARCH-1).

One-shot script to remove duplicate sources from NB-1 (Codebase & Architecture).
For each group of sources sharing the same title, keeps the NEWEST one
(highest positional index in the source list — NLM adds sequentially)
and deletes all older duplicates.

Safety:
    - Always use --dry-run first to preview deletions
    - Pre-cleanup snapshot is saved at apps/evaluator/nlm_deep_research/snapshots/
    - 1-second sleep between delete calls to avoid rate limiting

Usage:
    python3 scripts/nlm_nb1_dedup_cleanup.py --dry-run
    python3 scripts/nlm_nb1_dedup_cleanup.py --dry-run --snapshot-file path/to/snapshot.json
    python3 scripts/nlm_nb1_dedup_cleanup.py   # LIVE — actually deletes duplicates
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# ── Config ──────────────────────────────────────────────
NB1_ID = "f6ecd115-dd89-4c9b-b3dd-071e0e2f1876"
NLM_CLI = "nlm"
SOURCE_LIST_TIMEOUT = 60
SOURCE_DELETE_TIMEOUT = 30

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = PROJECT_ROOT / "apps" / "evaluator" / "nlm_deep_research" / "snapshots"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [NB1-Dedup] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nb1-dedup")


# ── Helpers ─────────────────────────────────────────────


def _run_nlm(args: list[str], timeout: int = SOURCE_LIST_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """Run an nlm CLI command and return the result."""
    cmd = [NLM_CLI] + args
    log.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"nlm exited with code {result.returncode}"
        raise RuntimeError(f"nlm CLI error: {error_msg}")
    return result


def _parse_source_list(raw_output: str) -> list[dict[str, str]]:
    """Parse nlm source list JSON output into a list of source dicts.

    Each dict contains: source_id, title, type.
    """
    if not raw_output.strip():
        return []

    data = json.loads(raw_output)

    # nlm CLI may wrap in {"value": [...]} or return a list directly
    sources_raw: list[dict[str, Any]]
    if isinstance(data, list):
        sources_raw = data
    elif isinstance(data, dict) and "value" in data:
        sources_raw = data["value"] if isinstance(data["value"], list) else []
    elif isinstance(data, dict) and "sources" in data:
        sources_raw = data["sources"] if isinstance(data["sources"], list) else []
    else:
        log.warning("Unexpected nlm source list format: %s", type(data))
        sources_raw = []

    sources: list[dict[str, str]] = []
    for s in sources_raw:
        source_id = s.get("source_id") or s.get("id") or s.get("sourceId", "")
        title = s.get("title") or s.get("name", "")
        source_type = s.get("type") or s.get("source_type", "unknown")
        if source_id:
            sources.append({
                "source_id": str(source_id),
                "title": str(title),
                "type": str(source_type),
            })

    return sources


def get_sources_from_snapshot(snapshot_path: Path) -> list[dict[str, str]]:
    """Load sources from a snapshot JSON file.

    Args:
        snapshot_path: Path to the snapshot JSON.

    Returns:
        List of source dicts with source_id, title, type.

    Raises:
        FileNotFoundError: If file does not exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    log.info("Loading snapshot: %s", snapshot_path)
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    sources = data.get("sources", [])
    log.info("Loaded %d sources from snapshot", len(sources))
    return sources


def get_sources_live() -> list[dict[str, str]]:
    """Fetch current NB-1 sources live via nlm CLI.

    Returns:
        List of source dicts with source_id, title, type.
    """
    log.info("Fetching live sources for NB-1 (%s)...", NB1_ID)
    result = _run_nlm(["source", "list", NB1_ID], timeout=SOURCE_LIST_TIMEOUT)
    sources = _parse_source_list(result.stdout)
    log.info("Fetched %d live sources", len(sources))
    return sources


def find_duplicates(sources: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Group sources by title and return only groups with duplicates.

    Within each group, sources retain their original list order (positional index).
    NLM adds sources sequentially, so later positions = newer sources.

    Args:
        sources: List of source dicts.

    Returns:
        Dict mapping title -> list of source dicts (only titles with 2+ sources).
    """
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for source in sources:
        groups[source["title"]].append(source)

    # Return only groups with duplicates
    return {title: items for title, items in groups.items() if len(items) > 1}


def plan_deletions(
    duplicates: dict[str, list[dict[str, str]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """For each duplicate group, keep the NEWEST (last in list), mark others for deletion.

    Args:
        duplicates: Dict mapping title -> list of source dicts (ordered by position).

    Returns:
        Tuple of (to_delete, to_keep) lists.
    """
    to_delete: list[dict[str, str]] = []
    to_keep: list[dict[str, str]] = []

    for title, items in sorted(duplicates.items()):
        # Last item in the list is the newest (NLM adds sequentially)
        newest = items[-1]
        older = items[:-1]
        to_keep.append(newest)
        to_delete.extend(older)

    return to_delete, to_keep


def execute_deletions(
    to_delete: list[dict[str, str]],
    dry_run: bool = True,
) -> dict[str, Any]:
    """Delete duplicate sources from NB-1.

    Args:
        to_delete: List of source dicts to delete.
        dry_run: If True, only print what would be deleted.

    Returns:
        Summary dict with counts and details.
    """
    deleted = 0
    errors = 0
    details: list[dict[str, str]] = []

    for i, source in enumerate(to_delete, 1):
        title = source["title"]
        sid = source["source_id"]

        if dry_run:
            log.info(
                "[DRY RUN] %d/%d Would delete: %s (id=%s)",
                i, len(to_delete), title, sid,
            )
            details.append({"source_id": sid, "title": title, "status": "would_delete"})
        else:
            try:
                log.info(
                    "%d/%d Deleting: %s (id=%s)",
                    i, len(to_delete), title, sid,
                )
                _run_nlm(
                    ["source", "delete", sid, "--confirm"],
                    timeout=SOURCE_DELETE_TIMEOUT,
                )
                deleted += 1
                details.append({"source_id": sid, "title": title, "status": "deleted"})
                log.info("  Deleted OK")
            except Exception as e:
                errors += 1
                details.append({"source_id": sid, "title": title, "status": "error", "error": str(e)})
                log.error("  Failed to delete %s: %s", sid, e)

            # Rate limiting: 1-second sleep between delete calls
            if i < len(to_delete):
                time.sleep(1.0)

    return {
        "total_targeted": len(to_delete),
        "deleted": deleted,
        "errors": errors,
        "dry_run": dry_run,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NB-1 Duplicate Source Cleanup (ARCH-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be deleted, do not actually delete",
    )
    parser.add_argument(
        "--snapshot-file",
        type=Path,
        default=None,
        help="Path to an existing snapshot JSON file (skips live fetch)",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("NB-1 Duplicate Source Cleanup")
    log.info("Notebook: %s", NB1_ID)
    log.info("Mode: %s", "DRY RUN" if args.dry_run else "LIVE DELETE")
    log.info("=" * 60)

    # Step 1: Get sources
    if args.snapshot_file:
        if not args.snapshot_file.exists():
            log.error("Snapshot file not found: %s", args.snapshot_file)
            sys.exit(1)
        sources = get_sources_from_snapshot(args.snapshot_file)
    else:
        sources = get_sources_live()

    total_before = len(sources)
    log.info("Total sources: %d", total_before)

    # Step 2: Find duplicates
    duplicates = find_duplicates(sources)
    if not duplicates:
        log.info("No duplicates found. Nothing to clean up.")
        return

    log.info("Found %d titles with duplicates:", len(duplicates))
    for title, items in sorted(duplicates.items(), key=lambda x: -len(x[1])):
        log.info("  %dx %s", len(items), title)

    # Step 3: Plan deletions
    to_delete, to_keep = plan_deletions(duplicates)
    total_to_delete = len(to_delete)
    remaining = total_before - total_to_delete

    log.info("")
    log.info("Deletion plan:")
    log.info("  Sources before:  %d", total_before)
    log.info("  To delete:       %d", total_to_delete)
    log.info("  Remaining after: %d", remaining)
    log.info("")

    # Step 4: Show which source is kept per group
    log.info("Kept (newest) per group:")
    for source in to_keep:
        log.info("  KEEP: %s (id=%s)", source["title"], source["source_id"])

    log.info("")

    # Step 5: Execute
    result = execute_deletions(to_delete, dry_run=args.dry_run)

    # Step 6: Summary
    log.info("")
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("  Sources before:  %d", total_before)
    log.info("  Targeted:        %d", result["total_targeted"])
    log.info("  Deleted:         %d", result["deleted"])
    log.info("  Errors:          %d", result["errors"])
    log.info("  Remaining:       %d", total_before - result["deleted"])
    log.info("  Mode:            %s", "DRY RUN" if result["dry_run"] else "LIVE")
    log.info("=" * 60)

    if result["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
