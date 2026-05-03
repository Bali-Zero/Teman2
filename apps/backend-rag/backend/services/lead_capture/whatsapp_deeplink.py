"""Build `https://wa.me/<number>?text=<url-encoded>` deeplinks.

Message schema (from docs/plans/2026-04-19-4apps/00-shared-infrastructure.md):

    Hi Bali Zero — I just used [APP_NAME] on your site.

    Context:
    • [Key 1]: [Value 1]
    • [Key 2]: [Value 2]
    • [Key 3]: [Value 3]

    Reference: <balizero.com/<path>/<hash>>
    Lead ID: li_<nanoid>

The business phone number and the public host both come from env vars so
the same code works in dev/staging/prod.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from urllib.parse import quote

from backend.services.lead_capture.source import LeadSource

logger = logging.getLogger(__name__)

# Public host for the result page (user clicks Reference link from their
# WhatsApp history → lands back on the result they were looking at).
_DEFAULT_PUBLIC_HOST = "https://balizero.com"

# Bali Zero main business WhatsApp number. Digits-only (no +, no spaces)
# so `wa.me/<digits>` produces a clickable link on every WhatsApp client.
_DEFAULT_WA_NUMBER = "628213107363"


def _clean_wa_number(raw: str | None) -> str:
    """Strip everything except digits. wa.me rejects '+' and spaces."""
    if not raw:
        return _DEFAULT_WA_NUMBER
    return "".join(ch for ch in raw if ch.isdigit()) or _DEFAULT_WA_NUMBER


def build_whatsapp_url(
    *,
    source: LeadSource,
    context_lines: Iterable[tuple[str, str]],
    result_hash: str | None,
    lead_intent_id: str,
    wa_number: str | None = None,
    public_host: str | None = None,
) -> str:
    """Assemble a wa.me URL with pre-filled context.

    Parameters
    ----------
    source : LeadSource
        App that emitted the handoff. Used to pick the human-friendly
        name and the result URL path.
    context_lines : iterable of (label, value)
        Bullet rows shown under "Context:". 3-5 rows is the usual range
        — pre-curated by each app's endpoint, not by the user.
    result_hash : str or None
        If the app produced a shareable result page, include its URL.
        None for apps that do not have a result page (rare).
    lead_intent_id : str
        The `li_<nanoid>` we just persisted. Helps the matcher correlate
        the inbound WA with the outbound handoff.
    wa_number, public_host : str or None
        Overrides for tests; in prod, env vars WA_BUSINESS_NUMBER and
        PUBLIC_HOST are consulted.
    """
    number = _clean_wa_number(wa_number or os.getenv("WA_BUSINESS_NUMBER"))
    host = (public_host or os.getenv("PUBLIC_HOST") or _DEFAULT_PUBLIC_HOST).rstrip("/")

    app_name = source.human_name
    lines: list[str] = [f"Hi Bali Zero — I just used {app_name} on your site.", ""]

    context_rows = [(label, value) for label, value in context_lines if value]
    if context_rows:
        lines.append("Context:")
        for label, value in context_rows:
            lines.append(f"• {label}: {value}")
        lines.append("")

    if result_hash:
        lines.append(f"Reference: {host}{source.result_url_path}/{result_hash}")
    lines.append(f"Lead ID: {lead_intent_id}")

    body = "\n".join(lines)
    encoded = quote(body, safe="")
    url = f"https://wa.me/{number}?text={encoded}"

    # Log the raw body at DEBUG for troubleshooting; never log the
    # full URL at INFO since encoded bodies can exceed 2KB and clutter.
    logger.debug("wa deeplink source=%s body=%r", source.value, body)
    return url
