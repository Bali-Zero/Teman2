"""Fly process-group worker for CRM Google Drive polling.

The HTTP API owns status and manual control only. This worker owns the periodic
Drive poll loop so Drive/DB/OCR import chains do not compete with user-facing
API requests inside the same Fly Machine.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import asyncpg

from backend.services.crm.drive_poll_service import poll_drive_changes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrivePollWorkerConfig:
    database_url: str
    interval_seconds: int
    jitter_seconds: int
    timeout_seconds: int
    inline_ocr: bool
    once: bool


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw_value, default)
        return default
    return max(minimum, min(value, maximum))


def load_config(argv: list[str] | None = None) -> DrivePollWorkerConfig:
    parser = argparse.ArgumentParser(description="Run the CRM Drive poll worker")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    args = parser.parse_args(argv)

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    return DrivePollWorkerConfig(
        database_url=database_url,
        interval_seconds=_env_int(
            "DRIVE_POLL_WORKER_INTERVAL_SECONDS",
            default=300,
            minimum=30,
            maximum=3600,
        ),
        jitter_seconds=_env_int(
            "DRIVE_POLL_WORKER_JITTER_SECONDS",
            default=10,
            minimum=0,
            maximum=120,
        ),
        timeout_seconds=_env_int(
            "DRIVE_POLL_WORKER_TIMEOUT_SECONDS",
            default=840,
            minimum=60,
            maximum=86_400,
        ),
        inline_ocr=_env_bool("DRIVE_POLL_WORKER_INLINE_OCR", default=False),
        once=args.once or _env_bool("DRIVE_POLL_WORKER_ONCE", default=False),
    )


async def _upsert_setting(conn: asyncpg.Connection, key: str, value: str) -> None:
    await conn.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = NOW()
        """,
        key,
        value,
    )


async def _record_state(
    pool: asyncpg.Pool,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    payload: dict[str, str] = {
        "drive_poll_worker_heartbeat_at": _utc_now_iso(),
        "drive_poll_worker_last_status": status,
    }
    if started_at:
        payload["drive_poll_worker_last_started_at"] = started_at
    if finished_at:
        payload["drive_poll_worker_last_finished_at"] = finished_at
    if result is not None:
        payload["drive_poll_worker_last_result"] = json.dumps(
            result,
            sort_keys=True,
            default=str,
        )
    if error is not None:
        payload["drive_poll_worker_last_error"] = error[:1000]

    async with pool.acquire() as conn:
        for key, value in payload.items():
            await _upsert_setting(conn, key, value)


async def run_once(config: DrivePollWorkerConfig) -> dict[str, Any]:
    """Run one Drive poll cycle and persist worker heartbeat/result state."""
    started_at = _utc_now_iso()
    pool = await asyncpg.create_pool(config.database_url, min_size=1, max_size=1)
    try:
        await _record_state(pool, status="running", started_at=started_at)
        result = await asyncio.wait_for(
            poll_drive_changes(
                inline_ocr=config.inline_ocr,
                acquire_advisory_lock=True,
            ),
            timeout=config.timeout_seconds,
        )
        status = str(result.get("status", "unknown"))
        await _record_state(
            pool,
            status=status,
            result=result,
            error="",
            finished_at=_utc_now_iso(),
        )
        logger.info("Drive poll worker cycle finished: %s", result)
        return result
    except TimeoutError:
        error = f"Drive poll worker exceeded {config.timeout_seconds}s"
        logger.error(error)
        await _record_state(
            pool,
            status="timeout",
            error=error,
            finished_at=_utc_now_iso(),
        )
        return {
            "status": "timeout",
            "error": error,
            "timeout_seconds": config.timeout_seconds,
        }
    except Exception as exc:
        logger.exception("Drive poll worker cycle failed")
        await _record_state(
            pool,
            status="error",
            error=str(exc),
            finished_at=_utc_now_iso(),
        )
        return {"status": "error", "error": str(exc)}
    finally:
        await pool.close()


async def run_forever(config: DrivePollWorkerConfig) -> int:
    """Run the worker loop until SIGINT/SIGTERM."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        logger.info("Drive poll worker shutdown requested")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_args: _request_stop())

    while not stop_event.is_set():
        await run_once(config)
        if config.once:
            return 0

        sleep_seconds = config.interval_seconds
        if config.jitter_seconds:
            sleep_seconds += random.randint(0, config.jitter_seconds)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_seconds)
        except TimeoutError:
            continue

    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        config = load_config(argv)
        return asyncio.run(run_forever(config))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logger.exception("Drive poll worker fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
