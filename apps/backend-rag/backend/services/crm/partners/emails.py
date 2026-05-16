"""
Partner email module — welcome + commission-earned via Brevo.

Sending: POST /api/notifications/send-email with X-API-Key (Brevo).
Sender: zantara@balizero.com / Zantara (non-negotiable per feedback_email_sender).
Both functions are idempotent: they read the sentinel timestamp before sending
and call mark_*_sent only after a successful HTTP response.

PII sterilization (UU PDP 27/2022):
- Client full names are sterilized to "First L." before passing to any template.
- Sterilization happens in Python, never inside Jinja2 templates.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import jinja2

from backend.services.crm.partners.repository import PartnersRepository
from backend.services.pricing.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)

# ─── Jinja2 environment ────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape([]),  # markdown-only, no HTML escaping needed
    keep_trailing_newline=True,
)

# ─── Email API constants ────────────────────────────────────────────────────
# Sender MUST be zantara@balizero.com per feedback_email_sender memory rule.
SENDER_EMAIL = "zantara@balizero.com"
SENDER_NAME = "Zantara"


def _get_endpoint() -> str:
    """Return the notifications endpoint URL, raising if env var is unset.

    CRIT-4: The previous os.environ.get() fallback pointed to the production
    URL and a literal API key. Any dev/CI/local environment without these env
    vars would silently route emails through production credentials — a Golden
    Rule #6 violation.

    Resolved at call time (not import time) so tests that mock _post_email
    bypass this check entirely without needing to set env vars.
    """
    endpoint = os.environ.get("NOTIFICATIONS_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "NOTIFICATIONS_ENDPOINT is not set — refusing to fall back to production. "
            "Set it in .env, docker-compose env, or fly secrets."
        )
    return endpoint


def _get_api_key() -> str:
    """Return the notifications API key, raising if env var is unset.

    CRIT-4: Same reasoning as _get_endpoint. The literal 'REDACTED-ROTATED-KEY'
    fallback was a hard-coded production credential in source code.
    """
    key = os.environ.get("NOTIFICATIONS_X_API_KEY")
    if not key:
        raise RuntimeError(
            "NOTIFICATIONS_X_API_KEY is not set — refusing to fall back. "
            "Set it in .env, docker-compose env, or fly secrets."
        )
    return key


# ─── Internal helpers ───────────────────────────────────────────────────────

async def _post_email(*, to: str, cc: list[str] | None, subject: str, body: str) -> None:
    """
    POST to the internal Brevo email relay endpoint.

    Payload shape matches the existing endpoint contract used by
    welcome_email_service.py — fields: to, subject, body, cc.
    Sender (from_email / from_name) is set server-side; the payload does not
    include those fields.
    """
    payload: dict[str, Any] = {
        "to": to,
        "subject": subject,
        "body": body,
    }
    if cc:
        payload["cc"] = cc

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            _get_endpoint(),
            json=payload,
            headers={"X-API-Key": _get_api_key()},
        )
        r.raise_for_status()


def _sterilize(name: str) -> str:
    """
    Reduce a full name to "FirstName L." for UU PDP compliance.

    Examples:
      "Mario Rossi"        → "Mario R."
      "Alice"              → "Alice"
      "Jean-Claude Van Dam" → "Jean-Claude D."
      ""                   → ""
    """
    parts = name.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _build_pricing_services() -> list[dict[str, str]]:
    """Return list of {name, price_display} pairs from PricingService.

    The pricing JSON has 3 levels:
      services (top) -> sub_category (dict) -> service_name (dict key) -> {price, duration, ...}

    We flatten to a list of {name, price_display}. Returns empty list if
    PricingService is not loaded (graceful degradation for the welcome
    email — terms still communicate; services list is absent).

    Golden Rule #12: prices ONLY from PricingTool/PricingService, never hardcoded.
    """
    svc = get_pricing_service()
    if not getattr(svc, "loaded", False):
        logger.warning("PricingService not loaded — welcome email services list will be empty")
        return []
    all_prices = svc.get_all_prices() or {}
    top = all_prices.get("services", all_prices)
    result: list[dict[str, str]] = []
    if not isinstance(top, dict):
        return result
    for _, entries in top.items():
        if isinstance(entries, dict):
            for service_name, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                price_str = entry.get("price") or entry.get("final_price") or "On request"
                if not isinstance(price_str, str):
                    price_str = str(price_str)
                result.append({
                    "name": str(service_name),
                    "price_display": price_str,
                })
        elif isinstance(entries, list):
            # Legacy flat-list shape, keep for safety
            for item in entries:
                if isinstance(item, dict) and "name" in item:
                    result.append({
                        "name": str(item["name"]),
                        "price_display": str(item.get("price_display") or item.get("price") or "On request"),
                    })
    return result


# ─── Public API ─────────────────────────────────────────────────────────────

async def enqueue_welcome(
    conn: Any,
    partner_id: UUID,
    # CATA-5: actor_user is team_members.id (VARCHAR string ID)
    actor_user: str | None = None,
) -> None:
    """Enqueue a welcome email. Idempotent per partner_id.

    CRIT-2: Must be called INSIDE the transaction that activates the partner.
    The email payload is frozen at enqueue time and sent later by flush_outbox().
    """
    from backend.services.crm.partners.repository import PartnersRepository
    repo = PartnersRepository(conn)
    p = await repo.get_partner(partner_id)
    if p is None:
        logger.warning("enqueue_welcome: partner %s not found — skip", partner_id)
        return
    if p.welcome_email_sent_at is not None:
        logger.info(
            "enqueue_welcome: welcome already sent for partner %s — skip (idempotent)",
            partner_id,
        )
        return

    pricing = _build_pricing_services()
    commission_rate = (
        f"{p.default_commission_value}%"
        if p.default_commission_type == "percentage"
        else f"IDR {p.default_commission_value:,.0f}"
    )
    tpl = _env.get_template("welcome.md.j2")
    body = tpl.render(
        partner=p,
        commission_rate=commission_rate,
        commission_type=p.default_commission_type,
        pricing_services=pricing,
    )
    await repo.insert_email_outbox(
        email_type="welcome",
        partner_id=partner_id,
        commission_id=None,
        to_email=p.email,
        cc_emails=None,
        subject="Welcome to Bali Zero Partners",
        body_markdown=body,
        idempotency_key=f"welcome:{partner_id}",
        created_by=actor_user,
    )
    logger.info("enqueue_welcome: enqueued for partner %s (%s)", partner_id, p.email)


async def enqueue_commission_earned(
    conn: Any,
    commission_id: UUID,
    # CATA-5: actor_user is team_members.id (VARCHAR string ID)
    actor_user: str | None = None,
) -> None:
    """Enqueue a commission-earned email. Idempotent per commission_id.

    CRIT-2: Must be called INSIDE the transaction that marks the commission paid.
    The email payload is frozen at enqueue time and sent later by flush_outbox().
    """
    from backend.services.crm.partners.repository import PartnersRepository
    repo = PartnersRepository(conn)
    c = await repo.get_commission(commission_id)
    if c is None or c.status != "paid":
        logger.info(
            "enqueue_commission_earned: commission %s not found or not paid — skip",
            commission_id,
        )
        return
    if c.commission_email_sent_at is not None:
        logger.info(
            "enqueue_commission_earned: already sent for commission %s — skip (idempotent)",
            commission_id,
        )
        return

    p = await repo.get_partner(c.partner_id)
    if p is None:
        logger.warning(
            "enqueue_commission_earned: partner %s not found — skip", c.partner_id
        )
        return

    proc = None
    if c.practice_id is not None:
        proc = await conn.fetchrow(
            """
            SELECT p.service_type, c.full_name AS client_name
            FROM practices p
            LEFT JOIN clients c ON c.id = p.client_id
            WHERE p.id = $1
            """,
            c.practice_id,
        )

    service_type = (proc["service_type"] if proc and proc["service_type"] else "service") if proc else "service"
    raw_client_name = (proc["client_name"] or "") if proc else ""
    client_display = _sterilize(raw_client_name) if raw_client_name else "client"

    cc_list: list[str] = []
    if c.assigned_to_snapshot is not None:
        row = await conn.fetchrow(
            # CATA-5: assigned_to_snapshot is team_members.id (VARCHAR string ID)
            "SELECT email FROM team_members WHERE id = $1", c.assigned_to_snapshot
        )
        if row and row["email"]:
            cc_list.append(row["email"])

    tpl = _env.get_template("commission.md.j2")
    body = tpl.render(
        partner=p,
        client_display=client_display,
        service_type=service_type,
        gross_idr=f"{c.gross_amount_idr:,.0f}",
        withholding_idr=f"{c.withholding_amount_idr:,.0f}",
        withholding_category=c.withholding_category,
        net_idr=f"{c.net_amount_idr:,.0f}",
        paid_via=c.paid_via or "",
        payment_reference=c.payment_reference or "",
        paid_at=c.paid_at.isoformat() if c.paid_at else "",
        receipt_file_url=c.receipt_file_url,
    )
    subject = f"Commissione maturata — {client_display}"

    await repo.insert_email_outbox(
        email_type="commission_earned",
        partner_id=c.partner_id,
        commission_id=commission_id,
        to_email=p.email,
        cc_emails=cc_list or None,
        subject=subject,
        body_markdown=body,
        idempotency_key=f"commission:{commission_id}",
        created_by=actor_user,
    )
    logger.info(
        "enqueue_commission_earned: enqueued for commission %s to %s",
        commission_id, p.email,
    )


async def flush_outbox(conn: Any, limit: int = 50) -> dict:
    """Send pending outbox emails synchronously (for /flush endpoint or cron).

    Returns counts: {'sent': N, 'retried': N, 'dlq': N}.

    v1: synchronous. v2 will replace with an async worker process.
    """
    from backend.services.crm.partners.repository import PartnersRepository
    repo = PartnersRepository(conn)
    pending = await repo.list_pending_outbox(limit=limit)
    sent = retried = dlq = 0
    for row in pending:
        try:
            await _post_email(
                to=row["to_email"],
                cc=list(row["cc_emails"]) if row["cc_emails"] else [],
                subject=row["subject"],
                body=row["body_markdown"],
            )
            await repo.mark_outbox_sent(row["id"])
            # Also stamp the idempotency column on the source record.
            if row["email_type"] == "welcome":
                await repo.mark_welcome_sent(row["partner_id"])
            elif row["email_type"] == "commission_earned" and row["commission_id"]:
                await repo.mark_commission_email_sent(row["commission_id"])
            sent += 1
        except Exception as e:
            new_attempts = (row["attempts"] or 0) + 1
            await repo.mark_outbox_retry(row["id"], str(e)[:500])
            if new_attempts >= 5:
                dlq += 1
            else:
                retried += 1
    return {"sent": sent, "retried": retried, "dlq": dlq}


async def send_welcome(conn: Any, partner_id: UUID) -> None:
    """
    Send the partner welcome email.

    Idempotent: reads welcome_email_sent_at before sending.
    If already sent, logs and returns without HTTP call.

    Args:
        conn: asyncpg.Connection (passed directly by the router).
        partner_id: UUID of the partner.
    """
    repo = PartnersRepository(conn)
    p = await repo.get_partner(partner_id)
    if p is None:
        logger.warning("send_welcome: partner %s not found — skip", partner_id)
        return
    if p.welcome_email_sent_at is not None:
        logger.info("send_welcome: already sent for partner %s — skip (idempotent)", partner_id)
        return

    pricing_services = _build_pricing_services()

    commission_rate = (
        f"{p.default_commission_value}%"
        if p.default_commission_type == "percentage"
        else f"IDR {p.default_commission_value:,.0f}"
    )

    tpl = _env.get_template("welcome.md.j2")
    body = tpl.render(
        partner=p,
        commission_rate=commission_rate,
        commission_type=p.default_commission_type,
        pricing_services=pricing_services,
    )

    await _post_email(
        to=p.email,
        cc=None,
        subject="Welcome to Bali Zero Partners",
        body=body,
    )
    await repo.mark_welcome_sent(partner_id)
    logger.info("send_welcome: sent to partner %s (%s)", partner_id, p.email)


async def send_commission_earned(conn: Any, commission_id: UUID) -> None:
    """
    Send the commission-earned notification email.

    Idempotent: reads commission_email_sent_at before sending.
    Client name is sterilized to "First L." BEFORE template rendering (UU PDP).

    Args:
        conn: asyncpg.Connection (passed directly by the router).
        commission_id: UUID of the partner_commissions row.
    """
    repo = PartnersRepository(conn)
    c = await repo.get_commission(commission_id)
    if c is None or c.status != "paid":
        logger.info(
            "send_commission_earned: commission %s not found or not paid — skip",
            commission_id,
        )
        return
    if c.commission_email_sent_at is not None:
        logger.info(
            "send_commission_earned: already sent for commission %s — skip (idempotent)",
            commission_id,
        )
        return

    p = await repo.get_partner(c.partner_id)
    if p is None:
        logger.warning("send_commission_earned: partner %s not found — skip", c.partner_id)
        return

    # Fetch practice + client name via JOIN
    proc = None
    if c.practice_id is not None:
        proc = await conn.fetchrow(
            """
            SELECT p.service_type, c.full_name AS client_name
            FROM practices p
            LEFT JOIN clients c ON c.id = p.client_id
            WHERE p.id = $1
            """,
            c.practice_id,
        )

    service_type = (proc["service_type"] if proc and proc["service_type"] else "service") if proc else "service"
    raw_client_name = (proc["client_name"] or "") if proc else ""

    # UU PDP: sterilize BEFORE template render, never inside template
    client_display = _sterilize(raw_client_name) if raw_client_name else "client"

    # CC the assigned-to user if resolvable
    cc_list: list[str] = []
    if c.assigned_to_snapshot is not None:
        row = await conn.fetchrow(
            # CATA-5: assigned_to_snapshot is team_members.id (VARCHAR string ID)
            "SELECT email FROM team_members WHERE id = $1",
            c.assigned_to_snapshot,
        )
        if row and row["email"]:
            cc_list.append(row["email"])

    tpl = _env.get_template("commission.md.j2")
    body = tpl.render(
        partner=p,
        client_display=client_display,
        service_type=service_type,
        gross_idr=f"{c.gross_amount_idr:,.0f}",
        withholding_idr=f"{c.withholding_amount_idr:,.0f}",
        withholding_category=c.withholding_category,
        net_idr=f"{c.net_amount_idr:,.0f}",
        paid_via=c.paid_via or "",
        payment_reference=c.payment_reference or "",
        paid_at=c.paid_at.isoformat() if c.paid_at else "",
        receipt_file_url=c.receipt_file_url,
    )

    subject = f"Commissione maturata — {client_display}"
    await _post_email(
        to=p.email,
        cc=cc_list if cc_list else None,
        subject=subject,
        body=body,
    )
    await repo.mark_commission_email_sent(commission_id)
    logger.info("send_commission_earned: sent for commission %s to %s", commission_id, p.email)
