"""Resend HTTPS API client used as fallback when Brevo fails.

NB-E (2026-04-29): Brevo remains primary for external recipients; Resend
is the secondary path. The two providers use different verified domains
on purpose so a Brevo account suspension or DNS misconfiguration on the
apex ``balizero.com`` cannot also take down the fallback:

- Brevo  → ``zantara@balizero.com``        (alias of zero@balizero.com)
- Resend → ``zantara@send.balizero.com``    (subdomain, separate DKIM/MX)

The fallback exists for *delivery* failures (Brevo HTTP 5xx, account
freeze, network), not for *content* failures (bad recipient address,
malformed payload). The Resend call uses the same payload semantics so
a payload that fails Brevo will also fail Resend; degrade-gracefully —
the goal is to keep the channel diversified, not to retry past a
genuine bad request.

Configuration:
- ``RESEND_API_KEY``       — Resend API key, format ``re_...``
- ``RESEND_FROM_EMAIL``    — sender override, default ``zantara@send.balizero.com``
- ``RESEND_FROM_NAME``     — sender display name, default ``Zantara``

Failure mode contract: returns ``False`` on any non-2xx, missing key, or
exception. NEVER raises. The caller decides whether to alert.
"""
from __future__ import annotations

import logging
import os

from backend.services.notifications.email_http import get_email_client

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"


async def send_via_resend(
    *,
    to_email: str,
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> bool:
    """Send an HTML email via Resend.

    Returns True on 2xx, False on any other outcome. Never raises.

    The ``from`` address defaults to the verified ``send.balizero.com``
    subdomain so a DKIM/MX failure on the apex ``balizero.com`` (Brevo's
    domain) does not also kill the fallback path.
    """
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.debug("resend_http: RESEND_API_KEY not set — skipping fallback")
        return False

    from_email = os.getenv("RESEND_FROM_EMAIL", "zantara@send.balizero.com")
    from_name = os.getenv("RESEND_FROM_NAME", "Zantara")

    payload: dict = {
        "from": f"{from_name} <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": body,
    }
    if cc:
        payload["cc"] = list(cc)
    if bcc:
        payload["bcc"] = list(bcc)
    if attachments:
        payload["attachments"] = [
            {"filename": a.get("name", "attachment"), "content": a.get("content", "")}
            for a in attachments
        ]

    try:
        client = await get_email_client()
        resp = await client.post(
            _RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code in (200, 201, 202):
            logger.info(
                "Resend fallback sent: to=%s subject=%r from=%s",
                to_email,
                subject,
                from_email,
            )
            return True
        logger.error(
            "Resend API error %d for %s: %s",
            resp.status_code,
            to_email,
            resp.text[:300],
        )
        return False
    except Exception as e:
        logger.error("Resend fallback failed for %s: %s", to_email, e)
        return False
