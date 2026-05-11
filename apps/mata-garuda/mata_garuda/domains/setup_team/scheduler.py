"""Bali calendar guard (Task 8).

Skip outbound Telegram alerts and auto-promotion deadlines on Galungan or
Kuningan ±1 day — banjar (village council) is offline, owner availability
drops to ~0%, escalation should not happen during ceremony windows.

Wraps foundations.bali_calendar (Pawukon-derived Galungan/Kuningan dates).

Default contract:
  should_skip_today() -> (skip: bool, reason: str)

  skip=True if today OR tomorrow OR yesterday is Galungan/Kuningan.
  reason is "Galungan ±1" / "Kuningan ±1" / "" depending on hit.

The ±1 window matches the spec § "extend SLA by 3 days if window crosses
Galungan/Kuningan" — the cron uses this to defer the run, the promotion
gate uses it to extend SLA.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from mata_garuda.foundations.bali_calendar import is_galungan, is_kuningan


def _check(target: date) -> Optional[str]:
    if is_galungan(target):
        return "Galungan"
    if is_kuningan(target):
        return "Kuningan"
    return None


def should_skip_today(today: Optional[date] = None) -> tuple[bool, str]:
    """Return (skip, reason).

    Args:
        today: date to evaluate (defaults to date.today()). Lets tests pin
               wall-clock without monkeypatching.
    """
    when = today or date.today()
    yesterday = when - timedelta(days=1)
    tomorrow = when + timedelta(days=1)

    # Today first (most likely hit).
    hit_today = _check(when)
    if hit_today is not None:
        return (True, f"{hit_today} ±1 (today)")

    hit_tomorrow = _check(tomorrow)
    if hit_tomorrow is not None:
        return (True, f"{hit_tomorrow} ±1 (tomorrow)")

    hit_yesterday = _check(yesterday)
    if hit_yesterday is not None:
        return (True, f"{hit_yesterday} ±1 (yesterday)")

    return (False, "")


def sla_deadline_extension_days(today: Optional[date] = None) -> int:
    """If Galungan/Kuningan falls within the next 14 days, return 3 days
    extension. Otherwise 0. Used by promotion_gate when SLA window crosses
    a ceremony window (per spec §8 task body).
    """
    when = today or date.today()
    for offset in range(0, 15):
        d = when + timedelta(days=offset)
        if is_galungan(d) or is_kuningan(d):
            return 3
    return 0


__all__ = [
    "should_skip_today",
    "sla_deadline_extension_days",
]
