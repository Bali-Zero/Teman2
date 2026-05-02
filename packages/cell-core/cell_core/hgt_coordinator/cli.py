"""CLI entry point for the HGT coordinator — used by OpenClaw Kimi K2.6.

Three subcommands::

    python -m cell_core.hgt_coordinator.cli observe [--window-days N]
    python -m cell_core.hgt_coordinator.cli list-pending [--limit N]
    python -m cell_core.hgt_coordinator.cli resolve --id N --status accepted|rejected --by <human>

All log output goes to **stderr** via :mod:`logging`. The structured
JSON dump for ``observe`` and ``list-pending`` is written to **stdout**
via :func:`sys.stdout.write` so the OpenClaw agent can pipe it cleanly.

Exit codes::

    0  success
    1  user error (bad args)
    2  transient error (Redis / SQLite down)
    3  unexpected exception

Environment::

    REDIS_URL                  default redis://localhost:6379/0
    HGT_COORDINATOR_AUDIT_LOG  optional override for SQLite audit log
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import timedelta
from typing import Any

from cell_core.hgt_coordinator.audit_log import (
    audit_log_path,
    list_pending,
    mark_resolved,
)
from cell_core.hgt_coordinator.coordinator import HGTCoordinator
from cell_core.hgt_coordinator.proposal import Proposal

logger = logging.getLogger("cell_core.hgt_coordinator.cli")

DEFAULT_REDIS_URL = "redis://localhost:6379/0"

# Exit codes — kept tight so OpenClaw can branch on them.
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_TRANSIENT = 2
EXIT_UNEXPECTED = 3


def _setup_logging() -> None:
    """Configure root logger to write to stderr (stdout is JSON channel)."""
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger()
    # Only configure if not already configured.
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(os.environ.get("HGT_COORDINATOR_LOG_LEVEL", "INFO").upper())


def _emit_json(payload: dict[str, Any]) -> None:
    """Write a JSON object to stdout (single-line)."""
    sys.stdout.write(json.dumps(payload, sort_keys=True, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()


async def _connect_redis(redis_url: str) -> Any | None:
    """Best-effort connect to Redis; returns ``None`` on failure.

    Tries ``redis.asyncio`` first (preferred for our async coordinator);
    falls back to ``None`` (graceful degradation — coordinator returns
    [] in that case). Sync ``redis-py`` is NOT acceptable here because
    ``HGTCoordinator.propose_transfers`` awaits ``xrange``.
    """
    try:
        import redis.asyncio as redis_async  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover — redis is a hard dep
        logger.warning(
            "redis.asyncio not importable — coordinator will degrade to []"
        )
        return None
    try:
        client = redis_async.from_url(redis_url, decode_responses=False)
        # Eager ping so we surface connection errors before the coordinator
        # call (clearer Telegram alerts for Zero).
        await client.ping()
        return client
    except Exception as exc:  # noqa: BLE001 — RedisError + transport
        logger.warning(
            "redis connect failed at %s (%s) — coordinator will degrade to []",
            redis_url,
            exc.__class__.__name__,
        )
        return None


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cell_core.hgt_coordinator.cli",
        description=(
            "HGT coordinator — propose-only cross-cell skill transfer. "
            "Reads Redis Stream cell:skills, writes SQLite audit log, "
            "outputs JSON for OpenClaw Kimi K2.6 review. NEVER auto-merges."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    obs = sub.add_parser(
        "observe",
        help="Run propose_transfers and dump JSON to stdout.",
    )
    obs.add_argument(
        "--window-days",
        type=int,
        default=7,
        help="Observation window in days (default: 7).",
    )
    obs.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        help="Redis URL (default: $REDIS_URL or redis://localhost:6379/0).",
    )

    lp = sub.add_parser(
        "list-pending",
        help="List pending proposals from the SQLite audit log.",
    )
    lp.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max rows to return (default: 50).",
    )

    res = sub.add_parser(
        "resolve",
        help="Mark a proposal as accepted/rejected/deferred.",
    )
    res.add_argument(
        "--id",
        dest="proposal_id",
        type=int,
        required=True,
        help="Proposal row id (from list-pending).",
    )
    res.add_argument(
        "--status",
        choices=["accepted", "rejected", "deferred"],
        required=True,
        help="New status.",
    )
    res.add_argument(
        "--by",
        required=True,
        help="Resolver ID (e.g. 'human:zero', 'kimi-k2.6').",
    )

    return parser


# === Subcommand handlers ===================================================


async def _cmd_observe(args: argparse.Namespace) -> int:
    redis_client = await _connect_redis(args.redis_url)
    coordinator = HGTCoordinator(redis_client=redis_client)
    try:
        proposals: list[Proposal] = await coordinator.propose_transfers(
            observation_window=timedelta(days=int(args.window_days))
        )
    except Exception as exc:  # noqa: BLE001 — defensive last line
        logger.exception("observe failed: %s", exc)
        return EXIT_UNEXPECTED
    finally:
        if redis_client is not None and hasattr(redis_client, "aclose"):
            try:
                await redis_client.aclose()
            except Exception:  # noqa: BLE001
                pass

    by_action: dict[str, list[dict[str, object]]] = {
        "proposals": [],
        "deferred": [],
        "rejected": [],
    }
    for p in proposals:
        bucket = {
            "propose": "proposals",
            "defer": "deferred",
            "reject": "rejected",
        }[p.recommended_action]
        by_action[bucket].append(p.to_dict())

    summary = (
        f"observe: {len(by_action['proposals'])} propose, "
        f"{len(by_action['deferred'])} defer, "
        f"{len(by_action['rejected'])} reject "
        f"(window={args.window_days}d)"
    )
    logger.info(summary)
    _emit_json(
        {
            "proposals": by_action["proposals"],
            "deferred": by_action["deferred"],
            "rejected": by_action["rejected"],
            "summary": summary,
            "window_days": int(args.window_days),
            "audit_log_path": str(audit_log_path()),
        }
    )
    return EXIT_OK


def _cmd_list_pending(args: argparse.Namespace) -> int:
    try:
        rows = list_pending(limit=int(args.limit))
    except Exception as exc:  # noqa: BLE001 — SQLite I/O
        logger.exception("list-pending failed: %s", exc)
        return EXIT_TRANSIENT
    summary = f"list-pending: {len(rows)} pending row(s)"
    logger.info(summary)
    _emit_json(
        {
            "pending": rows,
            "count": len(rows),
            "summary": summary,
            "audit_log_path": str(audit_log_path()),
        }
    )
    return EXIT_OK


def _cmd_resolve(args: argparse.Namespace) -> int:
    # Map "accepted" → audit-log canonical "approved" so the SQLite layer
    # stays consistent with mark_resolved's allowlist.
    new_status = "approved" if args.status == "accepted" else args.status
    try:
        ok = mark_resolved(
            int(args.proposal_id),
            new_status=new_status,
            resolved_by=str(args.by),
        )
    except ValueError as exc:
        logger.error("resolve: bad arguments — %s", exc)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 — SQLite I/O
        logger.exception("resolve failed: %s", exc)
        return EXIT_TRANSIENT
    payload = {
        "proposal_id": int(args.proposal_id),
        "new_status": new_status,
        "resolved_by": str(args.by),
        "updated": bool(ok),
    }
    summary = (
        f"resolve: id={args.proposal_id} → {new_status} by {args.by}: "
        f"updated={ok}"
    )
    logger.info(summary)
    _emit_json({**payload, "summary": summary})
    return EXIT_OK if ok else EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    """Entry point — return process exit code."""
    _setup_logging()
    parser = _make_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already wrote to stderr
        # argparse exits 2 for usage; normalise to 1 for our contract.
        code = exc.code if isinstance(exc.code, int) else 1
        return EXIT_USAGE if code != 0 else EXIT_OK

    try:
        if args.cmd == "observe":
            return asyncio.run(_cmd_observe(args))
        if args.cmd == "list-pending":
            return _cmd_list_pending(args)
        if args.cmd == "resolve":
            return _cmd_resolve(args)
    except KeyboardInterrupt:  # pragma: no cover — operator interrupt
        logger.warning("interrupted by user")
        return EXIT_UNEXPECTED
    except Exception as exc:  # noqa: BLE001 — defensive last line
        logger.exception("unexpected error: %s", exc)
        return EXIT_UNEXPECTED
    # parser.required=True guarantees args.cmd is set; mypy unreachable.
    return EXIT_USAGE  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
