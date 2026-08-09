"""Ephemeral loopback-only email sink for the client-portal QA gate.

The sink implements the notification endpoint used by the magic-link sender
and document-upload lead notification. It keeps one validated synthetic link
and a count-only support-mail receipt in process memory. It never logs or
persists recipients, tokens, message bodies, links, or document metadata.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit, urlunsplit

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SYNTHETIC_EMAIL_RE = re.compile(r"^[^@\s]+@example\.com$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_MAGIC_LINK_SUBJECT = "Your Bali Zero portal sign-in link"
_SUPPORT_MAIL_SUBJECT = "📄 New Document Uploaded - Synthetic Active Portal Client"
_SYNTHETIC_CLIENT_NAME = "Synthetic Active Portal Client"
_SYNTHETIC_DOCUMENT_RE = re.compile(r"^synthetic-portal-upload-[a-z0-9-]+\.pdf$")
_SYNTHETIC_CLIENT_PATH_RE = re.compile(r"^https://kita\.balizero\.com/clients/[1-9]\d*$")


@dataclass(frozen=True)
class QAMailSinkSettings:
    """Validated, non-production configuration for the ephemeral sink."""

    key: str
    recipient: str
    support_recipient: str
    frontend_origin: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> QAMailSinkSettings:
        source = os.environ if environment is None else environment
        required = (
            "MY_PORTAL_QA_MAIL_SINK_KEY",
            "MY_PORTAL_QA_MAIL_SINK_RECIPIENT",
            "MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT",
            "MY_PORTAL_QA_FRONTEND_ORIGIN",
        )
        missing = [name for name in required if not source.get(name, "").strip()]
        if missing:
            names = ", ".join(missing)
            raise RuntimeError(f"Portal QA mail sink missing required variable names: {names}")

        key = source["MY_PORTAL_QA_MAIL_SINK_KEY"].strip()
        recipient = source["MY_PORTAL_QA_MAIL_SINK_RECIPIENT"].strip().lower()
        support_recipient = source["MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT"].strip().lower()
        frontend_origin = _validate_frontend_origin(source["MY_PORTAL_QA_FRONTEND_ORIGIN"].strip())
        if not _KEY_RE.fullmatch(key):
            raise RuntimeError("Portal QA mail sink rejected MY_PORTAL_QA_MAIL_SINK_KEY")
        if not _SYNTHETIC_EMAIL_RE.fullmatch(recipient):
            raise RuntimeError("Portal QA mail sink rejected MY_PORTAL_QA_MAIL_SINK_RECIPIENT")
        if not _SYNTHETIC_EMAIL_RE.fullmatch(support_recipient):
            raise RuntimeError("Portal QA mail sink rejected MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT")
        if recipient == support_recipient:
            raise RuntimeError("Portal QA mail sink requires distinct synthetic recipients")
        return cls(
            key=key,
            recipient=recipient,
            support_recipient=support_recipient,
            frontend_origin=frontend_origin,
        )


class NotificationPayload(BaseModel):
    """Minimal contract accepted from the portal notification sender."""

    model_config = ConfigDict(extra="forbid")

    to: str
    subject: str
    body: str


class CapturedMagicLink(BaseModel):
    """Single ephemeral link returned only to the authenticated QA harness."""

    magic_link: str


class SupportMailReceipt(BaseModel):
    """Count-only proof that the strict support notification was accepted."""

    document_upload_notifications: int


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


class _ReceiptStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._latest: str | None = None
        self._document_upload_notifications = 0

    async def replace(self, link: str) -> None:
        async with self._lock:
            self._latest = link

    async def take(self) -> str | None:
        async with self._lock:
            latest = self._latest
            self._latest = None
            return latest

    async def record_document_upload_notification(self) -> None:
        async with self._lock:
            self._document_upload_notifications += 1

    async def support_mail_receipt(self) -> SupportMailReceipt:
        async with self._lock:
            return SupportMailReceipt(
                document_upload_notifications=self._document_upload_notifications,
            )


def _validate_frontend_origin(value: str) -> str:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError as error:
        raise RuntimeError("Portal QA mail sink rejected MY_PORTAL_QA_FRONTEND_ORIGIN") from error
    if (
        parsed.scheme != "http"
        or hostname not in _LOOPBACK_HOSTS
        or port is None
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Portal QA mail sink rejected MY_PORTAL_QA_FRONTEND_ORIGIN")
    return f"http://{parsed.netloc}"


def _extract_valid_magic_link(html_body: str, frontend_origin: str) -> str:
    if len(html_body) > 100_000:
        raise ValueError("notification body exceeds the QA limit")
    collector = _AnchorCollector()
    collector.feed(html_body)
    if len(collector.hrefs) != 1:
        raise ValueError("notification must contain exactly one link")

    link = collector.hrefs[0]
    parsed = urlsplit(link)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    tokens = query.get("token", [])
    if (
        origin != frontend_origin
        or parsed.path != "/portal/magic"
        or parsed.fragment
        or set(query) != {"token"}
        or len(tokens) != 1
        or not _TOKEN_RE.fullmatch(tokens[0])
    ):
        raise ValueError("notification contained an invalid QA magic link")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _validate_document_upload_notification(html_body: str) -> None:
    """Accept only the exact synthetic body emitted by the real portal service."""
    if len(html_body) > 100_000:
        raise ValueError("notification body exceeds the QA limit")
    lines = html_body.split("<br>")
    if len(lines) != 15:
        raise ValueError("notification body has an invalid shape")

    expected_lines = {
        0: "Hello,",
        1: "",
        2: f"Client {_SYNTHETIC_CLIENT_NAME} has uploaded a new document to the portal.",
        3: "",
        4: "Details:",
        6: "• Type: Other",
        7: f"• Client: {_SYNTHETIC_CLIENT_NAME}",
        8: "",
        9: "Open the workspace to review and verify the document:",
        11: "",
        12: "---",
        13: "This is an automated notification from Bali Zero CRM.",
        14: "",
    }
    if any(lines[index] != expected for index, expected in expected_lines.items()):
        raise ValueError("notification body has an invalid synthetic contract")
    if not lines[5].startswith("• File: ") or not _SYNTHETIC_DOCUMENT_RE.fullmatch(
        lines[5].removeprefix("• File: ")
    ):
        raise ValueError("notification body has an invalid document name")
    if not _SYNTHETIC_CLIENT_PATH_RE.fullmatch(lines[10]):
        raise ValueError("notification body has an invalid workspace link")


def _require_key(provided: str | None, expected: str) -> None:
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def create_app(
    settings: QAMailSinkSettings | None = None,
) -> FastAPI:
    """Build the fail-closed QA sink; intended for uvicorn ``--factory``."""

    config = settings or QAMailSinkSettings.from_environment()
    store = _ReceiptStore()
    app = FastAPI(title="Portal QA mail sink", docs_url=None, redoc_url=None)

    @app.get("/health", status_code=status.HTTP_204_NO_CONTENT)
    async def health() -> None:
        return None

    @app.post("/api/notifications/send-email")
    async def capture_notification(
        payload: NotificationPayload,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, bool]:
        _require_key(x_api_key, config.key)
        recipient = payload.to.strip().lower()
        if recipient == config.recipient and payload.subject == _MAGIC_LINK_SUBJECT:
            try:
                link = _extract_valid_magic_link(payload.body, config.frontend_origin)
            except (ValueError, TypeError) as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Synthetic magic link rejected",
                ) from error
            await store.replace(link)
        elif recipient == config.support_recipient and payload.subject == _SUPPORT_MAIL_SUBJECT:
            try:
                _validate_document_upload_notification(payload.body)
            except (ValueError, TypeError) as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Synthetic support notification rejected",
                ) from error
            await store.record_document_upload_notification()
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Synthetic notification contract rejected",
            )
        return {"success": True}

    @app.get("/qa/latest-magic-link", response_model=CapturedMagicLink)
    async def latest_magic_link(
        x_qa_sink_key: str | None = Header(default=None, alias="X-QA-Sink-Key"),
    ) -> CapturedMagicLink:
        _require_key(x_qa_sink_key, config.key)
        link = await store.take()
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not ready")
        return CapturedMagicLink(magic_link=link)

    @app.get("/qa/support-mail-receipt", response_model=SupportMailReceipt)
    async def support_mail_receipt(
        x_qa_sink_key: str | None = Header(default=None, alias="X-QA-Sink-Key"),
    ) -> SupportMailReceipt:
        _require_key(x_qa_sink_key, config.key)
        return await store.support_mail_receipt()

    logger.info("Portal QA mail sink initialized on a synthetic loopback contract")
    return app
