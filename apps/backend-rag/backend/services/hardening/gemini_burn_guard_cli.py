"""Run the Gemini burn-rate guard once. Designed to be invoked inside the
prod machine, same architecture as ``llm_credit_sentinel_cli``.

    python3 -m backend.services.hardening.gemini_burn_guard_cli

Exit codes: 0 = normal (or state could not be established), 1 = accelerating.
"cannot_verify" deliberately exits 0 — a Postgres hiccup is not a billing
event and must not page anyone; it prints a distinct STATE so the caller
(the GH Actions workflow) can still tell "measured and fine" apart from
"could not measure" instead of conflating the two into a false all-clear.

It runs inside the Fly machine so it can reuse the SAME live Telegram
channel every other server-side alert already uses (AlertService, with its
own dedup/backoff) rather than a hand-rolled curl — the GitHub Action layer
only needs FLY_API_TOKEN, matching ``llm_credit_sentinel``'s pattern.

AlertService's dedup lives in process memory, which does not survive one
short-lived CLI invocation to the next, so a second, file-based cooldown
(``GEMINI_BURN_GUARD_STATE_PATH``, default ``/data/gemini_burn_guard_last_alert.json``
on the ``rag`` machine's persistent volume) stops a sustained acceleration
from re-alerting every run. A failure to read/write that file degrades
toward alerting again (mild duplicate), never toward silence — the opposite
failure would hide a real acceleration behind a broken cooldown file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.services.hardening.gemini_burn_guard import (
    BurnState,
    BurnWindowStats,
    GeminiBurnGuard,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger("gemini_burn_guard_cli")

_result = logging.getLogger("gemini_burn_guard.result")
_result.propagate = False
if not _result.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _result.addHandler(_handler)
    _result.setLevel(logging.INFO)

RECENT_HOURS = int(os.environ.get("GEMINI_BURN_GUARD_RECENT_HOURS", "72"))
BASELINE_DAYS = int(os.environ.get("GEMINI_BURN_GUARD_BASELINE_DAYS", "14"))
RATIO_THRESHOLD = float(os.environ.get("GEMINI_BURN_GUARD_RATIO_THRESHOLD", "3.0"))
MIN_RECENT_USD = Decimal(os.environ.get("GEMINI_BURN_GUARD_MIN_RECENT_USD", "1.00"))
COOLDOWN_HOURS = float(os.environ.get("GEMINI_BURN_GUARD_COOLDOWN_HOURS", "12"))
STATE_PATH = Path(
    os.environ.get("GEMINI_BURN_GUARD_STATE_PATH", "/data/gemini_burn_guard_last_alert.json"),
)


def _dsn() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")


async def _fetch_windows() -> tuple[BurnWindowStats, BurnWindowStats]:
    """Query llm_cost_events for provider='gemini' and return (recent, baseline).

    ``baseline`` is normalised to the SAME wall-clock length as ``recent``
    (a 14-day trailing average scaled down to the recent-window length) so
    GeminiBurnGuard's ratio is a straight division, not a unit conversion.
    """
    dsn = _dsn()
    if not dsn:
        raise RuntimeError("no DATABASE_URL/POSTGRES_URL in environment")

    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        recent_rows = await conn.fetch(
            """
            SELECT model, SUM(cost_usd) AS total, COUNT(*) AS n
              FROM llm_cost_events
             WHERE provider = 'gemini'
               AND ts_utc >= NOW() - ($1 || ' hours')::interval
             GROUP BY model
            """,
            str(RECENT_HOURS),
        )
        baseline_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(cost_usd), 0) AS total, COUNT(*) AS n
              FROM llm_cost_events
             WHERE provider = 'gemini'
               AND ts_utc >= NOW() - ($1 || ' days')::interval - ($2 || ' hours')::interval
               AND ts_utc <  NOW() - ($2 || ' hours')::interval
            """,
            str(BASELINE_DAYS),
            str(RECENT_HOURS),
        )
    finally:
        await conn.close()

    recent_total = Decimal("0")
    recent_calls = 0
    top_model: str | None = None
    top_model_usd = Decimal("0")
    for row in recent_rows:
        row_total = Decimal(str(row["total"] or 0))
        recent_total += row_total
        recent_calls += int(row["n"] or 0)
        if row_total > top_model_usd:
            top_model_usd = row_total
            top_model = row["model"]

    recent = BurnWindowStats(
        total_usd=recent_total,
        call_count=recent_calls,
        top_model=top_model,
        top_model_usd=top_model_usd,
    )

    baseline_total_full = Decimal(str((baseline_row["total"] if baseline_row else 0) or 0))
    baseline_calls_full = int((baseline_row["n"] if baseline_row else 0) or 0)
    # Normalise the N-day baseline down to a figure covering the SAME number
    # of hours as `recent`, so the guard's ratio is recent-vs-recent-sized-slice.
    scale = Decimal(RECENT_HOURS) / Decimal(BASELINE_DAYS * 24)
    baseline = BurnWindowStats(
        total_usd=baseline_total_full * scale,
        call_count=int(baseline_calls_full * scale),
    )
    return recent, baseline


def _read_last_alert() -> dict[str, Any] | None:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return None


def _write_last_alert(state: str, now: datetime) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps({"state": state, "ts_utc": now.isoformat()}))
    except OSError as exc:
        logger.warning("impossibile scrivere il cooldown file %s: %s", STATE_PATH, exc)


def _should_skip_for_cooldown(now: datetime) -> bool:
    """True only when the SAME condition alerted within the cooldown window.

    Any uncertainty here (missing/corrupt file, unparsable timestamp) resolves
    toward "do not skip" — a lost cooldown file causes a duplicate alert, not
    a suppressed one.
    """
    last = _read_last_alert()
    if not last:
        return False
    try:
        last_ts = datetime.fromisoformat(last["ts_utc"])
    except (KeyError, ValueError):
        return False
    if last.get("state") != BurnState.ACCELERATING.value:
        return False
    return (now - last_ts) < timedelta(hours=COOLDOWN_HOURS)


def _build_notifiers() -> dict:
    from backend.services.monitoring.alert_service import AlertLevel, get_alert_service

    async def telegram(text: str) -> bool:
        result = await get_alert_service().send_alert(
            title="Gemini burn-rate accelerando",
            message=text,
            level=AlertLevel.WARNING,
            dedup_key="gemini_burn_guard:accelerating",
        )
        return bool(result.get("telegram"))

    return {"telegram:alert_service": telegram}


async def main() -> int:
    now = datetime.now(timezone.utc)

    # Cooldown decides WHICH notifiers the guard gets, decided before the
    # single check() call — GeminiBurnGuard always notifies on ACCELERATING,
    # so an active cooldown passes no-op notifiers rather than skip logic
    # living inside the guard (which stays measurement-only, DB-agnostic).
    skip_notify = _should_skip_for_cooldown(now)
    guard = GeminiBurnGuard(
        _fetch_windows,
        {} if skip_notify else _build_notifiers(),
        ratio_threshold=RATIO_THRESHOLD,
        min_recent_usd=MIN_RECENT_USD,
        window_label=f"{RECENT_HOURS}h",
    )

    verdict = await guard.check()
    _result.info("STATE=%s", verdict.state.value)
    _result.info("DETAIL=%s", verdict.detail[:300])
    if verdict.ratio is not None:
        _result.info("RATIO=%.2f", verdict.ratio)

    if verdict.state is BurnState.ACCELERATING:
        if skip_notify:
            _result.info("ALERT_SENT=0 (cooldown attivo, ultima notifica <%.0fh fa)", COOLDOWN_HOURS)
        else:
            _result.info("ALERT_SENT=1")
            _write_last_alert(verdict.state.value, now)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
