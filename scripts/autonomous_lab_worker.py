#!/usr/bin/env python3
"""Run one bounded Pro-only Autonomous Lab worker tick."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend-rag"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from backend.services.autonomous_lab import (
    AutonomousLabStateStore,
    LabWorkerConfig,
    LabWorkerStatus,
    current_runtime_placement,
    default_worker_id,
    run_worker_once,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--worker-id",
        default=default_worker_id(),
        help="Stable worker id used for owner-scoped run transitions.",
    )
    parser.add_argument(
        "--execute-verification",
        action="store_true",
        help="Execute allowlisted verification commands. Required for DB mutation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print placement/configuration only. Does not connect to Postgres.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of bounded worker ticks to run. Default 1.",
    )
    parser.add_argument(
        "--poll-interval-sec",
        type=float,
        default=5.0,
        help="Sleep interval between idle iterations.",
    )
    parser.add_argument(
        "--command-timeout-sec",
        type=int,
        default=120,
        help="Per-command timeout for allowlisted verification commands.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        _dump({"ok": False, "status": "interrupted"})
        return 130
    except Exception as exc:
        _dump({"ok": False, "status": "crashed", "error_type": type(exc).__name__})
        return 1


async def _main_async(args: argparse.Namespace) -> int:
    placement = current_runtime_placement()
    base_payload: dict[str, Any] = {
        "placement": placement.to_receipt(),
        "worker_id": args.worker_id,
        "execute_verification": bool(args.execute_verification),
        "iterations": max(args.iterations, 1),
    }
    if args.dry_run:
        _dump({"ok": True, "status": "dry_run", **base_payload})
        return 0
    if not placement.can_claim_runs:
        _dump(
            {
                "ok": False,
                "status": "placement_refused",
                "reason": "Autonomous Lab run workers must execute on Pro runtime",
                **base_payload,
            }
        )
        return 2
    if not args.execute_verification:
        _dump(
            {
                "ok": False,
                "status": "verification_disabled",
                "reason": "--execute-verification is required for worker DB mutation",
                **base_payload,
            }
        )
        return 2
    if not args.database_url:
        _dump({"ok": False, "status": "missing_database_url", **base_payload})
        return 2

    asyncpg = _import_asyncpg()
    conn = await asyncpg.connect(args.database_url)
    results: list[dict[str, Any]] = []
    try:
        store = AutonomousLabStateStore()
        config = LabWorkerConfig(
            worker_id=args.worker_id,
            repo_root=REPO_ROOT,
            backend_root=BACKEND_ROOT,
            execute_verification=True,
            command_timeout_seconds=args.command_timeout_sec,
        )
        for index in range(max(args.iterations, 1)):
            result = await run_worker_once(conn, config=config, store=store)
            results.append(result.to_receipt())
            if result.status != LabWorkerStatus.IDLE or index == args.iterations - 1:
                continue
            await asyncio.sleep(max(args.poll_interval_sec, 0.0))
    finally:
        await conn.close()

    ok = all(result.get("ok") is True for result in results)
    _dump({"ok": ok, "status": "complete" if ok else "failed", **base_payload, "results": results})
    return _exit_code(results)


def _import_asyncpg() -> Any:
    try:
        import asyncpg  # type: ignore

        return asyncpg
    except ImportError as exc:
        raise RuntimeError(
            "asyncpg not installed in active venv. Activate apps/backend-rag/.venv."
        ) from exc


def _exit_code(results: list[dict[str, Any]]) -> int:
    statuses = {str(result.get("status")) for result in results}
    if not results or statuses <= {LabWorkerStatus.IDLE.value, LabWorkerStatus.SUCCEEDED.value}:
        return 0
    if LabWorkerStatus.REFUSED.value in statuses:
        return 3
    if LabWorkerStatus.MARK_FAILED.value in statuses:
        return 4
    return 1


def _dump(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
