"""CLI for the fixed-map Magazine operations executor."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import signal

from zantara_media.magazine.operations_runtime import (
    OperationsRuntimeConfigError,
    create_operations_runtime,
)
from zantara_media.magazine.research_runtime import PollSettings, run_poll_loop

logger = logging.getLogger(__name__)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magazine-operations-worker")
    parser.add_argument("--min-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--max-backoff-seconds", type=float, default=30.0)
    return parser


async def _run(args: argparse.Namespace) -> None:
    runtime = create_operations_runtime()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop_event.set)
    try:
        logger.info("magazine operations worker started")
        await run_poll_loop(
            runtime.worker,
            settings=PollSettings(
                min_backoff_seconds=args.min_backoff_seconds,
                max_backoff_seconds=args.max_backoff_seconds,
            ),
            stop_event=stop_event,
        )
    finally:
        await runtime.aclose()
        logger.info("magazine operations worker stopped")


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    args = _parser().parse_args(argv)
    try:
        asyncio.run(_run(args))
    except (OperationsRuntimeConfigError, ValueError):
        logger.error("magazine operations worker configuration rejected")
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
