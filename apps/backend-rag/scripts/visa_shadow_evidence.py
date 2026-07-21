#!/usr/bin/env python3
"""Emit a re-runnable, aggregate-only Visa Oracle SHADOW gate report."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

import asyncpg

from backend.services.visa_engine.shadow_evidence import collect_shadow_evidence


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure Visa Oracle SHADOW G-a/G-c from the PII-free audit projection; "
            "the report can never mark ENFORCE ready without independent G-b/G-d evidence."
        )
    )
    parser.add_argument("--start", required=True, type=_parse_datetime)
    parser.add_argument("--end", required=True, type=_parse_datetime)
    parser.add_argument(
        "--environment",
        choices=("TEST", "STAGING", "PRODUCTION"),
        default="PRODUCTION",
    )
    parser.add_argument(
        "--database-url-env",
        default="DATABASE_URL",
        help="name of the environment variable holding a read-only PostgreSQL URL",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict[str, object]:
    database_url = os.environ.get(args.database_url_env)
    if not database_url:
        raise RuntimeError(f"missing database URL environment variable: {args.database_url_env}")

    pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=2,
        server_settings={"default_transaction_read_only": "on"},
    )
    try:
        return await collect_shadow_evidence(
            pool,
            window_start=args.start,
            window_end=args.end,
            environment=args.environment,
        )
    finally:
        await pool.close()


def _collect_report(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> dict[str, object]:
    try:
        return asyncio.run(_run(args))
    except (
        RuntimeError,
        asyncpg.PostgresError,
        asyncpg.InterfaceError,  # sibling of PostgresError, NOT subclass
        OSError,
        asyncio.TimeoutError,
    ) as exc:
        parser.error(str(exc))


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    report = _collect_report(parser, args)
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
