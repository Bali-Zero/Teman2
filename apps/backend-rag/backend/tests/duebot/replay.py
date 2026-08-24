"""Drives a local FastAPI ``TestClient`` against the WhatsApp/Instagram
webhook routers with exact raw bytes — the replay half of the B6a harness.

``WebhookReplayer`` deliberately does NOT re-serialize whatever payload it
is given: every ``send*`` method takes ``bytes`` in, and hands those same
bytes to httpx's ``content=`` parameter (never ``json=``, which re-encodes
the payload and would silently defeat the raw-body signature contract this
harness exists to prove — see ``webhook_signer`` module docstring).

``TestClient`` talks to the FastAPI app over an in-process ASGI transport —
no socket is ever opened, so this module needs no network at all, and runs
correctly under this package's autouse no-network guard (``conftest.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from backend.tests.duebot.webhook_signer import sign_payload

WHATSAPP_WEBHOOK_PATH = "/webhook/whatsapp"
INSTAGRAM_WEBHOOK_PATH = "/webhook/instagram"


@dataclass(frozen=True)
class ReplayResult:
    """One HTTP response from a replayed webhook POST."""

    status_code: int
    body: Any
    headers: dict[str, str]


class WebhookReplayer:
    """Thin, explicit wrapper around ``TestClient.post`` — no hidden
    retries, no hidden signing. Every signature that reaches the wire is
    visible at the call site that produced it.
    """

    def __init__(self, client: TestClient, path: str) -> None:
        self._client = client
        self._path = path

    def send_raw(
        self,
        raw_body: bytes,
        *,
        signature: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> ReplayResult:
        """POST ``raw_body`` unchanged.

        Args:
            raw_body: exact wire bytes (from ``fake_meta_sender.to_raw_body``
                or ``load_static_payload``).
            signature: the ``X-Hub-Signature-256`` header value. Pass
                ``None`` to omit the header entirely (the "missing header"
                scenario); pass an explicit — possibly wrong or malformed —
                string to test rejection paths directly.
            extra_headers: merged in last, so a caller can override
                ``Content-Type`` etc. for edge-case tests if needed.
        """
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Hub-Signature-256"] = signature
        if extra_headers:
            headers.update(extra_headers)
        resp = self._client.post(self._path, content=raw_body, headers=headers)
        try:
            body: Any = resp.json()
        except ValueError:
            body = resp.text
        return ReplayResult(status_code=resp.status_code, body=body, headers=dict(resp.headers))

    def send_signed(self, raw_body: bytes, app_secret: str, **kw: Any) -> ReplayResult:
        """Sign ``raw_body`` with ``app_secret`` and POST it — the common
        "valid delivery" path.
        """
        return self.send_raw(raw_body, signature=sign_payload(raw_body, app_secret), **kw)

    def replay(
        self,
        raw_body: bytes,
        app_secret: str,
        *,
        times: int,
        **kw: Any,
    ) -> list[ReplayResult]:
        """Send the identical signed request ``times`` times.

        Models Meta re-delivering the same event (network retry / at-least-
        once delivery semantics) rather than ``times`` distinct events —
        every call in the returned list carries the SAME message id, so a
        correct router acks 200 every time but persists/processes at most
        once (research capture §5.2: "same event replayed concurrently 2,
        10, and 100 times").
        """
        return [self.send_signed(raw_body, app_secret, **kw) for _ in range(times)]


def whatsapp_replayer(client: TestClient) -> WebhookReplayer:
    return WebhookReplayer(client, WHATSAPP_WEBHOOK_PATH)


def instagram_replayer(client: TestClient) -> WebhookReplayer:
    return WebhookReplayer(client, INSTAGRAM_WEBHOOK_PATH)
