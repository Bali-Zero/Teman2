"""Fail-closed adapter for synthetic portal support-mail notifications.

The adapter activates only when the dedicated synthetic support recipient is
configured. It reuses the internal notification endpoint contract, but accepts
only a loopback HTTP endpoint, a strong synthetic key, and an ``example.com``
recipient. Production notification delivery is therefore unchanged.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_SYNTHETIC_EMAIL_RE = re.compile(r"^[^@\s]+@example\.com$", re.IGNORECASE)
_NOTIFICATION_PATH = "/api/notifications/send-email"


@dataclass(frozen=True)
class QASupportMailSinkClient:
    """Minimal async client for one synthetic, loopback-only mail effect."""

    url: str
    key: str
    recipient: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> QASupportMailSinkClient | None:
        source = os.environ if environment is None else environment
        recipient = source.get("MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT", "").strip().lower()
        if not recipient:
            return None

        url_value = source.get("INTERNAL_EMAIL_API_URL", "").strip()
        key = source.get("NUZANTARA_API_KEY", "").strip()
        if not url_value or not key:
            raise RuntimeError("Portal QA support mail sink configuration is incomplete")
        if not _SYNTHETIC_EMAIL_RE.fullmatch(recipient):
            raise RuntimeError(
                "Portal QA support mail sink rejected MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT"
            )
        if not _KEY_RE.fullmatch(key):
            raise RuntimeError("Portal QA support mail sink rejected NUZANTARA_API_KEY")

        return cls(
            url=_validate_sink_url(url_value),
            key=key,
            recipient=recipient,
        )

    async def send_document_notification(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
    ) -> None:
        """Capture one validated notification without any external fallback."""
        if recipient.strip().lower() != self.recipient:
            raise RuntimeError("Portal QA support mail sink rejected the assigned recipient")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.url,
                    headers={"X-API-Key": self.key},
                    json={"to": self.recipient, "subject": subject, "body": html_body},
                )
        except httpx.HTTPError as error:
            raise RuntimeError("Portal QA support mail sink is unavailable") from error
        if response.status_code != 200:
            raise RuntimeError("Portal QA support mail sink rejected the notification")


def _validate_sink_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise RuntimeError("Portal QA support mail sink rejected INTERNAL_EMAIL_API_URL") from error
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "http"
        or hostname not in _LOOPBACK_HOSTS
        or port is None
        or parsed.username
        or parsed.password
        or parsed.path != _NOTIFICATION_PATH
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Portal QA support mail sink rejected INTERNAL_EMAIL_API_URL")
    return value
