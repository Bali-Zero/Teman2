"""Executable outbound-only Pro worker for Bali Zero Magazine research jobs."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal

from zantara_media.magazine.research_runtime import (
    PollSettings,
    ResearchRuntimeConfigError,
    create_research_runtime,
    run_poll_loop,
)

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
    parser = argparse.ArgumentParser(prog="magazine-research-worker")
    parser.add_argument("--min-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--max-backoff-seconds", type=float, default=30.0)
    return parser


async def _run(args: argparse.Namespace) -> None:
    runtime = create_research_runtime()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except NotImplementedError:
            pass
    try:
        logger.info("magazine research worker started")
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
        logger.info("magazine research worker stopped")


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    args = _parser().parse_args(argv)
    try:
        asyncio.run(_run(args))
    except (ResearchRuntimeConfigError, ValueError):
        logger.error("magazine research worker configuration rejected")
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
