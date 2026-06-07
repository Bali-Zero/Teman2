"""Digest suppressed-but-still-active human alerts."""
from __future__ import annotations

import inspect
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


DIGEST_ACTION = "suppression_digest_emitted"


@dataclass(frozen=True)
class SuppressionGroup:
    message: str
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    age_hours: float


@dataclass(frozen=True)
class SuppressionDigestResult:
    should_emit: bool
    text: str = ""
    groups: list[SuppressionGroup] = field(default_factory=list)
    reason: str = ""


def suppression_digest_enabled() -> bool:
    value = os.environ.get("CELL_SUPPRESSION_DIGEST_ENABLED", "").strip().lower()
    return value not in {"false", "0", "no", "off", "disabled"}


def should_run_suppression_digest(
    pulse_number: int,
    *,
    interval_pulses: int = 60,
) -> bool:
    return (
        suppression_digest_enabled()
        and interval_pulses > 0
        and pulse_number > 0
        and pulse_number % interval_pulses == 0
    )


async def build_suppression_digest(
    pool: Any,
    *,
    current_headline: str,
    now: datetime | None = None,
    lookback_hours: float = 24.0,
    min_age_hours: float = 2.0,
    cooldown_hours: float = 6.0,
) -> SuppressionDigestResult:
    """Build a digest for suppressed alerts matching the current red driver."""
    if not suppression_digest_enabled():
        return SuppressionDigestResult(False, reason="disabled")

    active_messages = _active_messages(current_headline)
    if not active_messages:
        return SuppressionDigestResult(False, reason="no-active-headline")

    now_utc = _as_aware_utc(now or datetime.now(timezone.utc))
    cooldown_since = now_utc - timedelta(hours=cooldown_hours)
    lookback_since = now_utc - timedelta(hours=lookback_hours)

    async with pool.acquire() as conn:
        recent_digest = await conn.fetchrow(
            """
            SELECT created_at
            FROM cell_alerts
            WHERE action = $1
              AND created_at >= $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            DIGEST_ACTION,
            cooldown_since,
        )
        if recent_digest:
            return SuppressionDigestResult(False, reason="cooldown")

        rows = await conn.fetch(
            """
            SELECT
                message,
                COUNT(*) FILTER (WHERE action = 'alert_suppressed') AS suppressed_count,
                MIN(created_at) AS first_seen_at,
                MAX(created_at) AS last_seen_at
            FROM cell_alerts
            WHERE action IN ('alert_suppressed', 'alert_human')
              AND created_at >= $1
            GROUP BY message
            HAVING COUNT(*) FILTER (WHERE action = 'alert_suppressed') > 0
            ORDER BY suppressed_count DESC, last_seen_at DESC
            """,
            lookback_since,
        )

    groups: list[SuppressionGroup] = []
    for row in rows:
        message = str(_row_get(row, "message", "") or "").strip()
        if message not in active_messages:
            continue
        first_seen = _as_aware_utc(_row_get(row, "first_seen_at"))
        last_seen = _as_aware_utc(_row_get(row, "last_seen_at"))
        age_hours = max(0.0, (now_utc - first_seen).total_seconds() / 3600.0)
        if age_hours < min_age_hours:
            continue
        groups.append(
            SuppressionGroup(
                message=message,
                count=int(_row_get(row, "suppressed_count", 0) or 0),
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                age_hours=age_hours,
            )
        )

    if not groups:
        return SuppressionDigestResult(False, reason="no-active-suppressed-groups")

    groups.sort(key=lambda group: (-group.count, group.message))
    lines = [
        "Suppressed alert digest",
        f"{sum(group.count for group in groups)} suppressed alert(s) still active:",
    ]
    lines.extend(
        f"- {group.message} ({group.count}x, active for {_format_hours(group.age_hours)})"
        for group in groups
    )
    return SuppressionDigestResult(True, text="\n".join(lines), groups=groups)


async def record_digest_emitted(
    pool: Any,
    *,
    text: str,
    health_status: str,
    pulse_number: int,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO cell_alerts (level, action, message, health_status, pulse_number)
            VALUES ($1, $2, $3, $4, $5)
            """,
            "warn",
            DIGEST_ACTION,
            text,
            health_status,
            pulse_number,
        )


async def run_suppression_digest(
    pool: Any,
    *,
    current_headline: str,
    health_status: str,
    pulse_number: int,
    emitter: Callable[[str], Awaitable[None] | None] | None = None,
    now: datetime | None = None,
    lookback_hours: float = 24.0,
    min_age_hours: float = 2.0,
    cooldown_hours: float = 6.0,
) -> SuppressionDigestResult:
    result = await build_suppression_digest(
        pool,
        current_headline=current_headline,
        now=now,
        lookback_hours=lookback_hours,
        min_age_hours=min_age_hours,
        cooldown_hours=cooldown_hours,
    )
    if not result.should_emit:
        return result

    if emitter is not None:
        maybe_awaitable = emitter(result.text)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    await record_digest_emitted(
        pool,
        text=result.text,
        health_status=health_status,
        pulse_number=pulse_number,
    )
    return result


def _active_messages(current_headline: str) -> set[str]:
    headline = current_headline.strip()
    if not headline:
        return set()
    messages = {headline}
    messages.update(part.strip() for part in headline.split(";") if part.strip())
    return messages


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError):
        return getattr(row, key, default)


def _as_aware_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raise TypeError(f"expected datetime, got {type(value).__name__}")


def _format_hours(hours: float) -> str:
    rounded = round(hours, 1)
    if rounded.is_integer():
        return f"{int(rounded)}h"
    return f"{rounded:.1f}h"
