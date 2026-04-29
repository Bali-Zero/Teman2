"""NewsletterPublisher — send weekly HTML email via internal notifications endpoint.

Auth + sender policy (from ``memory/feedback_email_sender``):
    - Sender is ALWAYS ``zantara@balizero.com`` with name "Zantara".
    - Never use zero@, nuzantara@, notifications@ as sender.
    - Transport is the internal FastAPI route ``/api/notifications/send-email``
      with header ``X-API-Key: REDACTED-ROTATED-KEY``.
    - The route auto-detects Brevo vs SendGrid based on key prefix; we don't
      care here, we just POST.

Idempotency: caller supplies ``week_of`` as a per-issue key. The publisher
does not write to a PG ledger in this sprint (deferred — a later migration
adds ``newsletter_issues`` table per design §21). For now, the CLI logs
the outcome and is idempotent-by-schedule (Monday 06:00 cron).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from string import Template
from typing import Any

import httpx

from backend.services.layout.template_renderer import TemplateRenderer
from backend.services.layout.templates import (
    NEWSLETTER_HTML,
)
from backend.services.newsletter.builder import RoundupContent

logger = logging.getLogger(__name__)


LOCKED_SENDER_EMAIL = "zantara@balizero.com"
LOCKED_SENDER_NAME = "Zantara"

DEFAULT_NOTIFICATIONS_URL = (
    os.environ.get("NOTIFICATIONS_EMAIL_URL")
    or "http://127.0.0.1:8000/api/notifications/send-email"
)
DEFAULT_API_KEY = os.environ.get("NOTIFICATIONS_API_KEY", "REDACTED-ROTATED-KEY")
DEFAULT_TIMEOUT = 15.0


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_newsletter_publisher_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


@dataclass
class PerRecipientResult:
    email: str
    ok: bool
    status: int | None = None
    error: str | None = None


@dataclass
class NewsletterSendResult:
    week_of: date
    recipients_attempted: int = 0
    recipients_sent: int = 0
    recipients_failed: int = 0
    subject: str = ""
    per_recipient: list[PerRecipientResult] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""


class NewsletterPublisher:
    """Renders the weekly roundup HTML and sends via internal endpoint.

    Parameters
    ----------
    template_renderer : TemplateRenderer
        Reuses the ``NEWSLETTER`` email-safe template from Sprint 5.
    http_client : httpx.AsyncClient, optional
        Injected for tests; a transient client is created per-call otherwise.
    notifications_url : str
        Override default endpoint URL (env ``NOTIFICATIONS_EMAIL_URL``).
    api_key : str
        Override default internal API key.
    cover_fallback_url : str
        Used when the top dossier has no cover image URL.
    """

    def __init__(
        self,
        template_renderer: TemplateRenderer | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        notifications_url: str | None = None,
        api_key: str | None = None,
        cover_fallback_url: str = "https://balizero.com/newsletter/cover.png",
        timeout: float | None = None,
    ) -> None:
        self.template_renderer = template_renderer or TemplateRenderer()
        self._client = http_client
        self.notifications_url = notifications_url or DEFAULT_NOTIFICATIONS_URL
        self.api_key = api_key or DEFAULT_API_KEY
        self.cover_fallback_url = cover_fallback_url
        self.timeout = timeout or DEFAULT_TIMEOUT

    # ── Public API ─────────────────────────────────────────────

    async def send_roundup(
        self,
        content: RoundupContent,
        recipients: Sequence[str],
    ) -> NewsletterSendResult:
        result = NewsletterSendResult(week_of=content.week_of)

        if content.is_empty:
            result.skipped = True
            result.skip_reason = "empty_roundup"
            return result

        recipient_list = [r.strip() for r in recipients if r and r.strip()]
        if not recipient_list:
            result.skipped = True
            result.skip_reason = "no_recipients"
            return result

        result.recipients_attempted = len(recipient_list)

        try:
            html = self._render_html(content)
        except Exception as exc:  # noqa: BLE001
            result.skipped = True
            result.skip_reason = f"render_failed: {type(exc).__name__}: {exc}"
            return result

        subject = self._build_subject(content)
        result.subject = subject

        client = self._client or _get_module_client(self.timeout)

        for email in recipient_list:
            per = await self._send_one(client, email, subject, html)
            result.per_recipient.append(per)
            if per.ok:
                result.recipients_sent += 1
            else:
                result.recipients_failed += 1

        return result

    # ── Internals ─────────────────────────────────────────────

    async def _send_one(
        self,
        client: httpx.AsyncClient,
        email: str,
        subject: str,
        html: str,
    ) -> PerRecipientResult:
        payload = {
            "to": email,
            "subject": subject,
            "body": html,
            "body_html": html,
            "from": LOCKED_SENDER_EMAIL,
            "from_name": LOCKED_SENDER_NAME,
        }
        try:
            resp = await client.post(
                self.notifications_url,
                headers={"X-API-Key": self.api_key},
                json=payload,
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            return PerRecipientResult(
                email=email,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        ok = 200 <= resp.status_code < 300
        err: str | None = None
        if not ok:
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return PerRecipientResult(
            email=email,
            ok=ok,
            status=resp.status_code,
            error=err,
        )

    def _render_html(self, content: RoundupContent) -> str:
        """Render the NEWSLETTER template directly.

        We bypass :class:`TemplateRenderer` because its security policy
        HTML-escapes every variable, which would neuter the sanitized HTML
        fragments we build for the body. The :meth:`_build_body_html`
        method is the only authority for escaping user-derived content
        (dossier titles, thesis implications). The template string itself
        is trusted — it ships with the codebase.
        """
        template = Template(NEWSLETTER_HTML)
        return template.safe_substitute(
            kicker=_escape(f"Week of {content.week_of.isoformat()}"),
            headline=_escape(self._build_headline(content)),
            body=self._build_body_html(content),   # already HTML-safe
            image_url=self._select_cover(content),  # URL — used in src=""
            patch_css="",
        )

    def _build_headline(self, content: RoundupContent) -> str:
        if content.brief and content.brief.narrative:
            return content.brief.narrative.splitlines()[0][:180]
        if content.dossiers:
            return content.dossiers[0].title[:180]
        return f"Bali Zero Weekly — {content.week_of.isoformat()}"

    def _build_body_html(self, content: RoundupContent) -> str:
        """Assemble HTML fragments safe for the NEWSLETTER template `$body`.

        The template puts ``$body`` inside a <p class="body"> — so we keep the
        content as a single stream with inline ``<br>``, ``<strong>``, and
        short section markers. Email clients tolerate this well.
        """
        fragments: list[str] = []

        if content.brief and content.brief.narrative:
            fragments.append(
                f"<strong>Strategos — {_escape(content.week_of.isoformat())}</strong><br>"
                f"{_escape(content.brief.narrative[:600])}"
            )

        if content.dossiers:
            fragments.append("<br><br><strong>Dossier della settimana</strong>")
            for d in content.dossiers:
                title = _escape(d.title[:180])
                summary = _escape((d.summary_short or d.summary_medium or "")[:240])
                fragments.append(
                    f"<br>• <strong>{title}</strong>"
                    + (f"<br>&nbsp;&nbsp;{summary}" if summary else "")
                )

        if content.theses:
            fragments.append("<br><br><strong>Tesi emerse (Connector)</strong>")
            for t in content.theses:
                title = _escape(t.title[:180])
                implication = _escape((t.implication or "")[:220])
                fragments.append(
                    f"<br>• {title}"
                    + (f" — <em>{implication}</em>" if implication else "")
                )

        fragments.append(
            "<br><br><em>Bali Zero · balizero.com</em>"
        )
        return "".join(fragments)

    def _build_subject(self, content: RoundupContent) -> str:
        base = f"Bali Zero · {content.week_of.isoformat()}"
        if content.dossiers:
            first = content.dossiers[0].title
            return f"{base} — {first[:80]}"
        return base

    def _select_cover(self, content: RoundupContent) -> str:
        for d in content.dossiers:
            cover = getattr(d, "cover_image_url", None)
            if cover:
                return str(cover)
        return self.cover_fallback_url


def _escape(value: Any) -> str:
    """HTML-escape content safe for email clients."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
