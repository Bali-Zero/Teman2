"""GARUDA VOA civil-day anchor — the single place that resolves "today".

The engine's business logic (``safe_clock.py``, ``intake.py``) is pure: every
function that needs "today" takes it as an explicit parameter and never reads
a clock itself. This module is the ONE composition-root helper that resolves
the real calendar date, so there is exactly one place to get the timezone
right.

Why ``Asia/Makassar`` (WITA, UTC+8) and not the server's own timezone: the
backend runs on Fly.io in UTC. The D-7 filing deadline this engine computes
is an Indonesian immigration deadline enforced at Ngurah Rai — the only
defensible "today" is the Indonesian civil date at the port, not the
server's. Using ``date.today()`` (host-local, undefined on a UTC container)
or a bare ``datetime.now(timezone.utc)`` date shifts the ACCEPT/DECLINE
cutoff and the published D-7 deadline shown to a customer by up to one full
day for the first eight hours of every Bali day.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

# Named constant so the timezone identifier is never hardcoded twice.
# Asia/Makassar = WITA = UTC+8, the Bali civil timezone. Do NOT use
# Asia/Jakarta (WIB, UTC+7) — that is the wrong zone for a Bali/Ngurah Rai
# deadline.
GARUDA_CIVIL_TIMEZONE: ZoneInfo = ZoneInfo("Asia/Makassar")


def garuda_today() -> date:
    """Return the engine's civil "today": the current date in Asia/Makassar."""
    return datetime.now(GARUDA_CIVIL_TIMEZONE).date()


__all__ = ["GARUDA_CIVIL_TIMEZONE", "garuda_today"]
