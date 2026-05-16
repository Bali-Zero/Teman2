"""NLM Source Snapshot + Rollback System (ARCH-8).

Provides snapshot/diff/rollback for NotebookLM notebook sources.
Protects against pipeline failures injecting garbage sources at night.

Usage:
    from apps.evaluator.nlm_deep_research.source_snapshot import (
        take_snapshot,
        diff_snapshots,
        rollback_to_snapshot,
        cleanup_old_snapshots,
        pipeline_snapshot_guard,
    )
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# NLM CLI binary — same as nlm_bridge.py
NLM_CLI = "nlm"

# Default timeout for source list operations (seconds)
SOURCE_LIST_TIMEOUT = 60

# Default timeout for source delete operations (seconds)
SOURCE_DELETE_TIMEOUT = 30

# WITA offset
WITA_OFFSET = timedelta(hours=8)

# Snapshot directory
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"

# Rollback log
ROLLBACK_LOG = SNAPSHOTS_DIR / "rollback_log.jsonl"

# Heartbeat state directory
HEARTBEAT_DIR = Path.home() / ".agent" / "decisions" / "state"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_wita() -> datetime:
    """Current time in WITA (UTC+8)."""
    return datetime.now(timezone(WITA_OFFSET))


def _run_nlm_command(
    args: List[str],
    timeout: int = SOURCE_LIST_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Run an nlm CLI command and return the result.

    Args:
        args: Command arguments (without the leading 'nlm').
        timeout: Subprocess timeout in seconds.

    Returns:
        CompletedProcess with stdout/stderr.

    Raises:
        subprocess.TimeoutExpired: If command exceeds timeout.
        FileNotFoundError: If nlm CLI is not installed.
        RuntimeError: If nlm CLI returns non-zero exit code.
    """
    cmd = [NLM_CLI] + args
    logger.debug("Running: %s", " ".join(cmd))

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


def _parse_source_list(raw_output: str) -> List[Dict[str, str]]:
    """Parse nlm source list JSON output into a list of source dicts.

    Each source dict contains: source_id, title, type.

    Args:
        raw_output: Raw JSON string from nlm source list.

    Returns:
        List of dicts with source_id, title, type keys.
    """
    if not raw_output.strip():
        return []

    data = json.loads(raw_output)

    # nlm CLI may wrap in {"value": [...]} or return a list directly
    sources_raw: List[Dict[str, Any]]
    if isinstance(data, list):
        sources_raw = data
    elif isinstance(data, dict) and "value" in data:
        sources_raw = data["value"] if isinstance(data["value"], list) else []
    elif isinstance(data, dict) and "sources" in data:
        sources_raw = data["sources"] if isinstance(data["sources"], list) else []
    else:
        logger.warning("Unexpected nlm source list format: %s", type(data))
        sources_raw = []

    sources: List[Dict[str, str]] = []
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


def _get_current_sources(notebook_id: str) -> List[Dict[str, str]]:
    """Fetch current sources from a notebook via nlm CLI.

    Args:
        notebook_id: NLM notebook UUID.

    Returns:
        List of source dicts with source_id, title, type.
    """
    result = _run_nlm_command(
        ["source", "list", notebook_id],
        timeout=SOURCE_LIST_TIMEOUT,
    )
    return _parse_source_list(result.stdout)


def _write_heartbeat(
    pipeline_name: str,
    status: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write heartbeat state file for a pipeline.

    Args:
        pipeline_name: Pipeline identifier (used as filename base).
        status: Status string (ok, failed, etc.).
        extra: Optional additional fields to include.
    """
    HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)
    state_file = HEARTBEAT_DIR / f"{pipeline_name}.last.json"

    payload: Dict[str, Any] = {
        "job": pipeline_name,
        "ts": int(time.time()),
        "status": status,
        "host": _get_hostname(),
    }
    if extra:
        payload.update(extra)

    state_file.write_text(json.dumps(payload), encoding="utf-8")
    logger.debug("Heartbeat written: %s → %s", state_file.name, status)


def _get_hostname() -> str:
    """Get machine hostname, with fallback."""
    import socket
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def _append_rollback_log(entry: Dict[str, Any]) -> None:
    """Append an entry to the rollback JSONL log.

    Args:
        entry: Dict to serialize as one JSON line.
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ROLLBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def take_snapshot(notebook_id: str, label: str) -> Path:
    """Take a snapshot of current notebook sources.

    Fetches source list from NLM and saves it to a timestamped JSON file.

    Args:
        notebook_id: NLM notebook UUID.
        label: Notebook name label for the snapshot filename.

    Returns:
        Path to the saved snapshot file.

    Raises:
        RuntimeError: If nlm CLI fails.
        FileNotFoundError: If nlm CLI is not installed.
    """
    logger.info("Taking snapshot for notebook %s (label=%s)", notebook_id, label)

    sources = _get_current_sources(notebook_id)
    timestamp = _now_wita().strftime("%Y-%m-%d_%H-%M")

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{label}_pre_{timestamp}.json"
    snapshot_path = SNAPSHOTS_DIR / filename

    snapshot_data = {
        "notebook_id": notebook_id,
        "label": label,
        "timestamp": _now_wita().isoformat(),
        "source_count": len(sources),
        "sources": sources,
    }

    snapshot_path.write_text(
        json.dumps(snapshot_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(
        "Snapshot saved: %s (%d sources)",
        snapshot_path.name,
        len(sources),
    )
    return snapshot_path


def diff_snapshots(before_path: Path, after_notebook_id: str) -> Dict[str, Any]:
    """Compare a snapshot file against the current notebook state.

    Args:
        before_path: Path to the pre-pipeline snapshot JSON.
        after_notebook_id: NLM notebook UUID for the current state.

    Returns:
        Dict with keys:
            added: list of source dicts present now but not in snapshot.
            removed: list of source dicts in snapshot but not present now.
            unchanged_count: number of sources present in both.

    Raises:
        FileNotFoundError: If snapshot file does not exist.
        RuntimeError: If nlm CLI fails.
    """
    logger.info("Computing diff: %s vs notebook %s", before_path.name, after_notebook_id)

    # Load the before snapshot
    snapshot_data = json.loads(before_path.read_text(encoding="utf-8"))
    before_sources = snapshot_data.get("sources", [])

    # Fetch current state
    after_sources = _get_current_sources(after_notebook_id)

    # Build ID sets
    before_ids = {s["source_id"] for s in before_sources}
    after_ids = {s["source_id"] for s in after_sources}

    # Build lookup maps
    before_map = {s["source_id"]: s for s in before_sources}
    after_map = {s["source_id"]: s for s in after_sources}

    added = [after_map[sid] for sid in (after_ids - before_ids)]
    removed = [before_map[sid] for sid in (before_ids - after_ids)]
    unchanged_count = len(before_ids & after_ids)

    logger.info(
        "Diff result: +%d added, -%d removed, %d unchanged",
        len(added),
        len(removed),
        unchanged_count,
    )

    return {
        "added": added,
        "removed": removed,
        "unchanged_count": unchanged_count,
    }


def rollback_to_snapshot(
    notebook_id: str,
    snapshot_path: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Rollback a notebook to a previous snapshot state.

    Deletes sources that were added after the snapshot was taken.
    Does NOT re-add sources that were removed (NLM limitation).

    Args:
        notebook_id: NLM notebook UUID.
        snapshot_path: Path to the target snapshot JSON.
        dry_run: If True, only calculate what would be deleted.

    Returns:
        Dict with keys:
            rolled_back: number of sources deleted.
            details: list of dicts describing each deletion.
            dry_run: whether this was a dry run.

    Raises:
        FileNotFoundError: If snapshot file does not exist.
        RuntimeError: If nlm CLI fails during source list or delete.
    """
    mode_str = "DRY RUN" if dry_run else "LIVE"
    logger.info(
        "Rollback [%s] notebook %s to snapshot %s",
        mode_str,
        notebook_id,
        snapshot_path.name,
    )

    # Load snapshot
    snapshot_data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_ids = {s["source_id"] for s in snapshot_data.get("sources", [])}

    # Get current sources
    current_sources = _get_current_sources(notebook_id)
    current_map = {s["source_id"]: s for s in current_sources}

    # Sources to remove: present now but absent in snapshot
    to_remove = [
        current_map[sid]
        for sid in current_map
        if sid not in snapshot_ids
    ]

    details: List[Dict[str, Any]] = []
    rolled_back = 0

    for source in to_remove:
        entry: Dict[str, Any] = {
            "source_id": source["source_id"],
            "title": source["title"],
            "type": source["type"],
            "action": "delete",
        }

        if dry_run:
            entry["status"] = "would_delete"
            logger.info(
                "[DRY RUN] Would delete: %s (%s)",
                source["title"],
                source["source_id"],
            )
        else:
            try:
                _run_nlm_command(
                    ["source", "delete", notebook_id, source["source_id"]],
                    timeout=SOURCE_DELETE_TIMEOUT,
                )
                entry["status"] = "deleted"
                rolled_back += 1
                logger.info(
                    "Deleted source: %s (%s)",
                    source["title"],
                    source["source_id"],
                )
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)
                logger.error(
                    "Failed to delete source %s: %s",
                    source["source_id"],
                    e,
                )

        details.append(entry)

    # Log rollback action
    log_entry = {
        "timestamp": _now_wita().isoformat(),
        "notebook_id": notebook_id,
        "snapshot": str(snapshot_path),
        "dry_run": dry_run,
        "sources_targeted": len(to_remove),
        "sources_deleted": rolled_back,
        "details": details,
    }
    _append_rollback_log(log_entry)

    logger.info(
        "Rollback %s complete: %d/%d sources removed",
        mode_str,
        rolled_back,
        len(to_remove),
    )

    return {
        "rolled_back": rolled_back,
        "details": details,
        "dry_run": dry_run,
    }


def cleanup_old_snapshots(max_per_notebook: int = 7) -> Dict[str, Any]:
    """Remove old snapshot files, keeping only the N most recent per notebook.

    Snapshots are grouped by label (the text before '_pre_' in the filename).
    Within each group, only the most recent max_per_notebook files are kept.

    Args:
        max_per_notebook: Maximum snapshots to retain per notebook label.

    Returns:
        Dict with keys:
            deleted: list of deleted file paths (as strings).
            kept: total number of files retained.
    """
    logger.info("Cleaning up snapshots (max %d per notebook)", max_per_notebook)

    if not SNAPSHOTS_DIR.exists():
        return {"deleted": [], "kept": 0}

    # Group snapshot files by notebook label
    groups: Dict[str, List[Path]] = {}
    for f in SNAPSHOTS_DIR.glob("*_pre_*.json"):
        # Extract label: everything before "_pre_"
        parts = f.stem.split("_pre_")
        if len(parts) >= 2:
            label = parts[0]
            groups.setdefault(label, []).append(f)

    deleted: List[str] = []
    kept = 0

    for _, files in groups.items():
        # Sort by modification time (newest first)
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Keep the newest, delete the rest
        to_keep = files[:max_per_notebook]
        to_delete = files[max_per_notebook:]

        kept += len(to_keep)

        for old_file in to_delete:
            try:
                old_file.unlink()
                deleted.append(str(old_file))
                logger.info("Deleted old snapshot: %s", old_file.name)
            except OSError as e:
                logger.error("Failed to delete snapshot %s: %s", old_file.name, e)

    logger.info("Cleanup complete: deleted %d, kept %d", len(deleted), kept)
    return {"deleted": deleted, "kept": kept}


@contextmanager
def pipeline_snapshot_guard(
    notebook_id: str,
    notebook_name: str,
    pipeline_name: str,
) -> Generator[Dict[str, Any], None, None]:
    """Context manager that wraps a pipeline run with snapshot protection.

    Takes a snapshot before the pipeline runs. On failure with new sources
    added, automatically rolls back. On success, saves a change record.
    Always writes a heartbeat state file.

    Args:
        notebook_id: NLM notebook UUID.
        notebook_name: Human-readable notebook name (used in snapshot label).
        pipeline_name: Pipeline identifier for heartbeat files.

    Yields:
        Dict that the pipeline can populate with run metadata.
        Includes 'snapshot_path' key with the pre-run snapshot path.

    Example:
        with pipeline_snapshot_guard(NB_ID, "immigration", "nlm_nb2") as ctx:
            # run pipeline logic here
            ctx["result"] = "some data"
    """
    context: Dict[str, Any] = {}
    snapshot_path: Optional[Path] = None
    start_ts = time.time()

    # --- Pre-pipeline: take snapshot ---
    try:
        snapshot_path = take_snapshot(notebook_id, notebook_name)
        context["snapshot_path"] = snapshot_path
        logger.info("Guard: pre-pipeline snapshot saved at %s", snapshot_path)
    except Exception as e:
        logger.error("Guard: failed to take pre-snapshot: %s", e)
        # Write heartbeat as failed and re-raise — no snapshot means no guard
        _write_heartbeat(pipeline_name, "failed", {
            "error": f"snapshot_failed: {e}",
            "duration_ms": int((time.time() - start_ts) * 1000),
        })
        raise

    # --- Yield control to pipeline ---
    pipeline_error: Optional[BaseException] = None
    try:
        yield context
    except BaseException as e:
        pipeline_error = e
        logger.error("Guard: pipeline raised %s: %s", type(e).__name__, e)

    duration_ms = int((time.time() - start_ts) * 1000)

    # --- Post-pipeline: diff and decide ---
    try:
        diff = diff_snapshots(snapshot_path, notebook_id)
        added_count = len(diff["added"])
        removed_count = len(diff["removed"])

        if pipeline_error is not None and added_count > 0:
            # Pipeline failed AND new sources were injected → auto-rollback
            logger.warning(
                "Guard: pipeline failed with %d new sources — rolling back",
                added_count,
            )
            rollback_result = rollback_to_snapshot(
                notebook_id,
                snapshot_path,
                dry_run=False,
            )
            _write_heartbeat(pipeline_name, "failed_rollback", {
                "error": str(pipeline_error),
                "sources_rolled_back": rollback_result["rolled_back"],
                "duration_ms": duration_ms,
            })
        elif pipeline_error is not None:
            # Pipeline failed but no sources were added — just log
            logger.info("Guard: pipeline failed but no new sources — no rollback needed")
            _write_heartbeat(pipeline_name, "failed", {
                "error": str(pipeline_error),
                "duration_ms": duration_ms,
            })
        else:
            # Pipeline succeeded — record the change
            change_record = {
                "timestamp": _now_wita().isoformat(),
                "notebook_id": notebook_id,
                "pipeline": pipeline_name,
                "snapshot": str(snapshot_path),
                "added": added_count,
                "removed": removed_count,
                "unchanged": diff["unchanged_count"],
                "status": "success",
            }
            # Save change record alongside snapshot
            change_path = snapshot_path.with_suffix(".changes.json")
            change_path.write_text(
                json.dumps(change_record, indent=2),
                encoding="utf-8",
            )
            logger.info(
                "Guard: pipeline succeeded (+%d/-%d sources), change record at %s",
                added_count,
                removed_count,
                change_path.name,
            )
            _write_heartbeat(pipeline_name, "ok", {
                "sources_added": added_count,
                "sources_removed": removed_count,
                "duration_ms": duration_ms,
            })

    except Exception as diff_err:
        # Diff itself failed — log but don't mask original error
        logger.error("Guard: post-pipeline diff/rollback failed: %s", diff_err)
        _write_heartbeat(pipeline_name, "failed", {
            "error": f"post_guard_error: {diff_err}",
            "duration_ms": duration_ms,
        })

    # Re-raise the original pipeline error if any
    if pipeline_error is not None:
        raise pipeline_error
