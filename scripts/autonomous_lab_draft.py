#!/usr/bin/env python3
"""Draft an autonomous lab run receipt from a source-agnostic JSON input."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend-rag"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from backend.services.autonomous_lab import (  # noqa: E402
    AutonomousLabPlanner,
    MaterialSourceType,
    ReceiptStore,
    ResearchMaterial,
)

DEFAULT_RECEIPT_DIR = REPO_ROOT / "research" / "operations" / "autonomous-lab" / "receipts"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the autonomous lab draft input JSON.",
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=DEFAULT_RECEIPT_DIR,
        help="Directory where the receipt JSON is written.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return 0 even if blocker gates fail. The blocked receipt is still written.",
    )
    return parser.parse_args(argv)


def load_input(path: Path) -> dict[str, Any]:
    """Load and validate the top-level input JSON object."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def material_from_payload(payload: dict[str, Any]) -> ResearchMaterial:
    """Build a ResearchMaterial from one input material object."""
    required = ("material_id", "source_type", "source_uri", "title", "text")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"material missing required keys: {', '.join(missing)}")

    source_type = MaterialSourceType(str(payload["source_type"]))
    metadata_raw = payload.get("metadata", {})
    if not isinstance(metadata_raw, dict):
        raise ValueError("material metadata must be an object when provided")
    metadata = {str(key): str(value) for key, value in metadata_raw.items()}

    captured_at = _parse_datetime(payload.get("captured_at"))
    return ResearchMaterial(
        material_id=str(payload["material_id"]),
        source_type=source_type,
        source_uri=str(payload["source_uri"]),
        title=str(payload["title"]),
        text=str(payload["text"]),
        captured_at=captured_at,
        metadata=metadata,
    )


def build_run(payload: dict[str, Any]) -> tuple[AutonomousLabPlanner, Any]:
    """Build the lab run from input payload."""
    objective = str(payload.get("objective", "")).strip()
    task_id = str(payload.get("task_id", "")).strip()
    if not objective:
        raise ValueError("objective is required")
    if not task_id:
        raise ValueError("task_id is required")

    materials_raw = payload.get("materials", [])
    if not isinstance(materials_raw, list):
        raise ValueError("materials must be a list")
    materials = [material_from_payload(item) for item in materials_raw]

    target_paths_raw = payload.get("target_paths", [])
    if not isinstance(target_paths_raw, list):
        raise ValueError("target_paths must be a list")
    target_paths = [str(path) for path in target_paths_raw]

    worktree_lane = str(payload.get("worktree_lane", "ops")).strip() or "ops"
    planner = AutonomousLabPlanner(worktree_lane=worktree_lane)
    run = planner.draft_run(
        objective=objective,
        materials=materials,
        target_paths=target_paths,
        task_id=task_id,
        created_at=_parse_datetime(payload.get("created_at")),
    )
    return planner, run


def summarize_result(receipt_path: Path, run: Any) -> dict[str, Any]:
    """Return a small JSON summary for stdout."""
    failed_blockers = [
        gate.name
        for gate in run.safety_gates
        if gate.severity.value == "blocker" and not gate.passed
    ]
    return {
        "ok": not failed_blockers,
        "blocked": bool(failed_blockers),
        "failed_blockers": failed_blockers,
        "receipt_path": str(receipt_path),
        "run_id": run.run_id,
        "verification_commands": run.simulation_plan.verification_commands,
        "worktree_command": run.simulation_plan.worktree_command,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    payload = load_input(args.input)
    _, run = build_run(payload)
    record = ReceiptStore(args.receipt_dir).write_run(run)
    receipt_path = record.receipt_path
    summary = summarize_result(receipt_path, run)
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if summary["blocked"] and not args.allow_blocked:
        return 2
    return 0


def _parse_datetime(value: Any) -> datetime:
    if value is None:
        return datetime.now().astimezone()
    if not isinstance(value, str):
        raise ValueError("datetime fields must be ISO-8601 strings")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
