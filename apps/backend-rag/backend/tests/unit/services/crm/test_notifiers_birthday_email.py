"""Guilt AND innocence for BirthdayNotifierService.send_birthday_email's
Brevo-to-Zoho fallback and PII log hygiene (spec_Fa_r3.md S3).

The defect (round-2 cross-family review of commit b25367f620, HIGH): S2 gave
a 200-but-not-delivered Brevo response its own exception type,
`InternalEmailNotDeliveredError` — a `RuntimeError` subclass — instead of a
bare `RuntimeError`. This module's Brevo leg caught only `httpx.HTTPError`/
`OSError`, so the new type fell through to the OUTER `except Exception`:
Zoho was never tried (a silent drop, not a fallback) and the outer handler
logged the client's raw email address in cleartext.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.app.services.internal_email import InternalEmailNotDeliveredError
from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm.notifiers import BirthdayNotifierService

_LOGGER_NAME = "backend.services.crm.notifiers"

_CLIENT = {
    "email": "birthday.client@example.com",
    "full_name": "Birthday Client",
    "nationality": "Italian",
    "custom_fields": None,
}


def _make_service() -> BirthdayNotifierService:
    """A service with a mocked Zoho leg — no real DB/HTTP behind either."""
    service = BirthdayNotifierService.__new__(BirthdayNotifierService)
    service.db_pool = MagicMock()
    service.email_service = MagicMock()
    service.email_service.send_email = AsyncMock()
    return service


class TestBrevoToZohoFallback:
    """S4.1: every Brevo failure shape falls through to Zoho; a Brevo
    success does the opposite — Zoho is never tried."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "brevo_exc",
        [
            httpx.ConnectError("connection refused"),
            OSError("network unreachable"),
            InternalEmailNotDeliveredError("all providers failed: brevo, resend, zoho"),
        ],
        ids=["http_error", "os_error", "not_delivered"],
    )
    async def test_guilt_every_brevo_failure_shape_falls_through_to_zoho(
        self, monkeypatch: pytest.MonkeyPatch, brevo_exc: Exception
    ) -> None:
        service = _make_service()
        monkeypatch.setattr(
            "backend.services.crm.notifiers.send_internal_email",
            AsyncMock(side_effect=brevo_exc),
        )

        result = await service.send_birthday_email(_CLIENT)

        assert result is True
        service.email_service.send_email.assert_awaited_once()
        kwargs = service.email_service.send_email.await_args.kwargs
        assert kwargs["to"] == [_CLIENT["email"]]

    @pytest.mark.asyncio
    async def test_innocence_brevo_success_never_calls_zoho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = _make_service()
        monkeypatch.setattr(
            "backend.services.crm.notifiers.send_internal_email",
            AsyncMock(return_value=True),
        )

        result = await service.send_birthday_email(_CLIENT)

        assert result is True
        service.email_service.send_email.assert_not_awaited()


class TestFailurePathsNeverLogTheClientEmail:
    """S4.2: no failure path — including the ones that recover via Zoho —
    may put the client's raw address in a log line. Both halves asserted:
    the literal address must be absent AND its redacted stand-in present,
    so an emptied log line does not pass as "fixed"."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "brevo_exc",
        [
            httpx.ConnectError("connection refused"),
            OSError("network unreachable"),
            InternalEmailNotDeliveredError("all providers failed: brevo, resend, zoho"),
        ],
        ids=["http_error", "os_error", "not_delivered"],
    )
    async def test_brevo_failure_then_zoho_success_never_logs_the_address(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, brevo_exc: Exception
    ) -> None:
        service = _make_service()
        monkeypatch.setattr(
            "backend.services.crm.notifiers.send_internal_email",
            AsyncMock(side_effect=brevo_exc),
        )

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.send_birthday_email(_CLIENT)

        assert result is True
        assert _CLIENT["email"] not in caplog.text
        assert redact_identifier_for_log(_CLIENT["email"]) in caplog.text

    @pytest.mark.asyncio
    async def test_outer_exception_never_logs_the_address(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Zoho itself blows up with something none of the named except
        clauses catch (not httpx.HTTPError, not asyncpg/OSError, not
        KeyError/ValueError) — the bare `except Exception` / `logger.
        exception` at the bottom is exactly the path a bare `RuntimeError`
        from `send_internal_email` used to reach before S2/S3 (it would
        have been raised inside the SAME outer try, uncaught by the old
        httpx.HTTPError/OSError-only Brevo except). It must redact exactly
        like every other branch."""
        service = _make_service()
        monkeypatch.setattr(
            "backend.services.crm.notifiers.send_internal_email",
            AsyncMock(side_effect=httpx.ConnectError("connection refused")),
        )
        service.email_service.send_email = AsyncMock(side_effect=RuntimeError("zoho boom"))

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            result = await service.send_birthday_email(_CLIENT)

        assert result is False
        assert _CLIENT["email"] not in caplog.text
        assert redact_identifier_for_log(_CLIENT["email"]) in caplog.text
