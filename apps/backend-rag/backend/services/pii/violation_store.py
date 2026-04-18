"""
Durable PII-violation audit trail.

Responsibilities:
- Accept a per-response list of detected patterns + the route that produced
  them, and persist one row per (pattern, request).
- Never raise back to the caller. The PII scanner is a hot-path middleware
  and MUST NOT 500 a request because the audit pipeline is degraded.
- Stay optional: when no DB pool is registered (tests, main_api cold-boot),
  the record call is a silent no-op.

The scanner (pii_scanner.py) registers the FastAPI app via `set_app(app)`
at startup so the middleware — which runs at ASGI level and doesn't own a
Request — can still reach `app.state.db_pool`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Severity policy per pattern. Governed by UU PDP No. 27/2022.
#   high: government-issued identifiers (KTP, NPWP, Passport)
#   medium: contact information (phone, email)
#   low: PERSON name matches (Presidio's built-in, high false-positive rate)
_SEVERITY_BY_PATTERN: dict[str, str] = {
    "ID_KTP": "high",
    "ID_NPWP": "high",
    "ID_PASSPORT": "high",
    "PHONE_ID": "medium",
    "PHONE_NUMBER": "medium",
    "EMAIL_ADDRESS": "medium",
    "PERSON": "low",
}


@dataclass
class PIIViolation:
    request_id: str | None
    route: str
    pattern_matched: str
    severity: str
    user_hash: str | None
    occurrence_count: int = 1


# ── Module-level app reference ──
# The scanner is an ASGI middleware; it does not own a Request. Starlette's
# scope["app"] works during dispatch, but we store a module-level reference
# so record_violations() can also be called from async tasks spawned after
# the response is sent.

_app: Any = None


def set_app(app: Any) -> None:
    """Register the FastAPI app so record_violations() can reach the DB pool."""
    global _app
    _app = app


def _pool() -> Any:
    if _app is None:
        return None
    return getattr(_app.state, "db_pool", None)


def severity_for(pattern: str) -> str:
    return _SEVERITY_BY_PATTERN.get(pattern, "low")


def hash_subject(raw: str | None) -> str | None:
    """Hash a user email / client IP so the audit log itself isn't PII."""
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def aggregate(
    patterns: list[str],
    *,
    request_id: str | None,
    route: str,
    user_hash: str | None,
) -> list[PIIViolation]:
    """
    Turn a flat list of detected patterns (from pii_scanner.scan_text) into
    one PIIViolation per pattern — with occurrence_count folded in so we
    write O(distinct patterns) rows, not O(total matches).
    """
    counts: dict[str, int] = {}
    for p in patterns:
        counts[p] = counts.get(p, 0) + 1
    return [
        PIIViolation(
            request_id=request_id,
            route=route,
            pattern_matched=pattern,
            severity=severity_for(pattern),
            user_hash=user_hash,
            occurrence_count=count,
        )
        for pattern, count in sorted(counts.items())
    ]


async def _write(violations: list[PIIViolation]) -> None:
    """Insert violations in a single batch; swallow every exception."""
    pool = _pool()
    if pool is None or not violations:
        return
    try:
        async with pool.acquire() as conn:
            # asyncpg's executemany is the cheapest path for <100 rows and
            # keeps a single prepared statement hot.
            await conn.executemany(
                """
                INSERT INTO pii_violations
                    (request_id, route, pattern_matched, severity,
                     user_hash, occurrence_count)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                [
                    (
                        v.request_id,
                        v.route,
                        v.pattern_matched,
                        v.severity,
                        v.user_hash,
                        v.occurrence_count,
                    )
                    for v in violations
                ],
            )
    except Exception as exc:  # noqa: BLE001 — never fail the request path
        logger.warning(
            "pii_violation_store.write_failed",
            extra={
                "error_type": type(exc).__name__,
                "count": len(violations),
            },
        )


def record_violations(violations: list[PIIViolation]) -> None:
    """
    Fire-and-forget write.

    Returns immediately; the insert runs on the event loop's task queue.
    Safe to call from sync ASGI send() boundaries.
    """
    if not violations:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Not inside an event loop (tests calling synchronously) — skip.
        return
    loop.create_task(_write(violations))
