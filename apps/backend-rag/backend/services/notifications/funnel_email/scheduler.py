"""Scheduling helpers + cron runner for funnel drip emails.

Two pieces:
    subscribe_*       called from routers when a user opts in.
    fire_due          called from cron (*/10 min Air) to send due rows.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from backend.app.services.internal_email import send_internal_email
from backend.services.notifications.funnel_email.repository import (
    EmailSubscription,
    EmailSubscriptionRepository,
)
from backend.services.notifications.funnel_email.templates import (
    render_clock,
    render_match_prearrival,
)

logger = logging.getLogger(__name__)

_PUBLIC_HOST = os.getenv("PUBLIC_HOST", "https://balizero.com").rstrip("/")


# ----------------------------------------------------------------------
# Subscription helpers — call from routers on opt-in
# ----------------------------------------------------------------------


async def subscribe_visa_clock(
    *,
    email: str,
    visa_type: str,
    entry_date: date,
    expiry_date: date,
    result_hash: str,
    whatsapp_url: str,
    pool: Any,
) -> list[EmailSubscription]:
    """Schedule all 5 Clock reminders at once (D-60/30/14/7/1).

    Reminders land at 09:00 WITA (UTC+8 = 01:00 UTC) on the day-of.
    Ones already in the past are skipped.
    """
    repo = EmailSubscriptionRepository(pool)
    now = datetime.now(timezone.utc)
    offsets = {
        "visa_clock_d60": 60,
        "visa_clock_d30": 30,
        "visa_clock_d14": 14,
        "visa_clock_d7": 7,
        "visa_clock_d1": 1,
    }
    payload_common: dict[str, Any] = {
        "visa_type": visa_type,
        "entry_date": entry_date.isoformat(),
        "expiry_date": expiry_date.isoformat(),
        "result_hash": result_hash,
        "whatsapp_url": whatsapp_url,
    }

    out: list[EmailSubscription] = []
    for trigger, days_before in offsets.items():
        fire_at = datetime.combine(
            expiry_date - timedelta(days=days_before),
            time(hour=1, minute=0),  # 01:00 UTC == 09:00 WITA
            tzinfo=timezone.utc,
        )
        if fire_at <= now:
            continue  # skip past checkpoints
        sub = await repo.upsert(
            email=email,
            app="visa_clock",
            trigger_type=trigger,
            payload=payload_common,
            next_fire_at=fire_at,
        )
        out.append(sub)
    return out


async def subscribe_visa_match_prearrival(
    *,
    email: str,
    recommended_visa: str,
    arrival_date: date,
    pre_arrival_steps: list[str],
    result_hash: str,
    whatsapp_url: str,
    pool: Any,
) -> EmailSubscription | None:
    """Schedule one pre-arrival nudge 7 days before arrival_date.

    Returns None if the D-7 window has already passed — the caller
    can show a "you're landing in less than a week — WhatsApp us" UI
    state instead.
    """
    fire_at = datetime.combine(
        arrival_date - timedelta(days=7),
        time(hour=1, minute=0),  # 01:00 UTC
        tzinfo=timezone.utc,
    )
    if fire_at <= datetime.now(timezone.utc):
        return None

    repo = EmailSubscriptionRepository(pool)
    sub = await repo.upsert(
        email=email,
        app="visa_match",
        trigger_type="visa_match_prearrival_d7",
        payload={
            "recommended_visa": recommended_visa,
            "arrival_date": arrival_date.isoformat(),
            "pre_arrival_steps": pre_arrival_steps,
            "result_hash": result_hash,
            "whatsapp_url": whatsapp_url,
        },
        next_fire_at=fire_at,
    )
    return sub


# ----------------------------------------------------------------------
# Cron runner
# ----------------------------------------------------------------------


async def fire_due(*, pool: Any, limit: int = 100) -> dict[str, int]:
    """Send all due rows, returning counts for observability.

    Fire-and-forget send (internal_email swallows its own failures),
    but we mark the row fired regardless to avoid infinite retries.
    If a pre-fire template renders fail, we log and skip that row —
    no DB write happens so the cron will pick it up again next tick.
    """
    repo = EmailSubscriptionRepository(pool)
    due = await repo.fetch_due(limit=limit)

    sent = 0
    skipped_render = 0
    for sub in due:
        try:
            rendered = _render(sub)
        except Exception:
            logger.exception(
                "funnel_email: render failed sub_id=%s trigger=%s",
                sub.id,
                sub.trigger_type,
            )
            skipped_render += 1
            continue

        await send_internal_email(
            to=sub.email,
            subject=rendered.subject,
            body=rendered.html,
            log_context=f"funnel={sub.app} trigger={sub.trigger_type} sub_id={sub.id}",
        )
        # Clock has 5 reminders — the next one is already scheduled as a
        # separate row, so next_fire_at for THIS row is NULL (done).
        await repo.mark_fired(sub.id, next_fire_at=None)
        sent += 1

    return {"due": len(due), "sent": sent, "skipped_render": skipped_render}


def _render(sub: EmailSubscription) -> Any:
    """Dispatch to template by trigger_type."""
    p = sub.payload or {}
    unsub_url = f"{_PUBLIC_HOST}/api/funnel_email/unsubscribe/{sub.unsubscribe_token}"

    if sub.trigger_type.startswith("visa_clock_"):
        return render_clock(
            trigger_type=sub.trigger_type,
            visa_type=p.get("visa_type", ""),
            expiry_date=_fmt_date(p.get("expiry_date")),
            whatsapp_url=p.get("whatsapp_url", ""),
            unsubscribe_url=unsub_url,
        )

    if sub.trigger_type == "visa_match_prearrival_d7":
        return render_match_prearrival(
            recommended_visa=p.get("recommended_visa", ""),
            arrival_date=_fmt_date(p.get("arrival_date")),
            whatsapp_url=p.get("whatsapp_url", ""),
            pre_arrival_steps=list(p.get("pre_arrival_steps", [])),
            unsubscribe_url=unsub_url,
        )

    raise ValueError(f"no renderer for trigger_type={sub.trigger_type}")


def _fmt_date(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return str(raw)
    return d.strftime("%-d %b %Y")
