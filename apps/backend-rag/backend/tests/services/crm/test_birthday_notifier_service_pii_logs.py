"""PII log hygiene for BirthdayNotifierService.send_birthday_email — this is
the sender-PII split of PR #7308 (`crm/notifiers.py`), and it targets the
LIVE birthday sender: `backend.services.crm.birthday_notifier_service` is
what `cron_notifiers.py` and `autonomous_scheduler.py` actually import;
`backend.services.crm.notifiers`'s already-redacted duplicate is not on
that live path.

Guilt: every logged line in this module — Brevo success/failure, Zoho
success, and the final outer failure — used to f-string-interpolate
``client['email']`` raw into the message, AND the failure paths logged the
exception's own text, which can itself carry the recipient's address (a
provider rejecting mail often names the address it rejected). Both halves
are asserted throughout: the raw address (and any leaked exception text)
must be absent from the log AND its redacted stand-in must be present, so
an emptied log line does not pass as "fixed".
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.crm import birthday_notifier_service as birthday_module
from backend.services.crm.birthday_notifier_service import BirthdayNotifierService

_LOGGER_NAME = "backend.services.crm.birthday_notifier_service"
_LEAK = "leak.probe@example.com"
_CLIENT = {
    "email": _LEAK,
    "full_name": "Leak Probe",
    "nationality": "Italian",
    "custom_fields": None,
}


def _make_service() -> BirthdayNotifierService:
    service = BirthdayNotifierService.__new__(BirthdayNotifierService)
    service.db_pool = None
    service.email_service = None
    return service


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


class _StubAsyncClient:
    """Stands in for `httpx.AsyncClient`'s context-manager protocol.

    ``post_effect`` is either an exception instance (raised from `.post()`)
    or a zero-arg callable returning a response-like object.
    """

    def __init__(self, post_effect: object, timeout: float = 30.0) -> None:
        self._post_effect = post_effect

    async def __aenter__(self) -> _StubAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def post(self, *args: object, **kwargs: object) -> object:
        if isinstance(self._post_effect, BaseException):
            raise self._post_effect
        return self._post_effect()


def _patch_brevo(monkeypatch: pytest.MonkeyPatch, post_effect: object) -> None:
    monkeypatch.setattr(
        birthday_module.httpx,
        "AsyncClient",
        lambda timeout=30.0: _StubAsyncClient(post_effect, timeout),
    )


class _FakeZohoService:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc
        self.sent: list[dict[str, object]] = []

    async def send_email(self, **kwargs: object) -> None:
        if self._exc is not None:
            raise self._exc
        self.sent.append(kwargs)


class TestBrevoSuccessNeverLogsTheAddress:
    @pytest.mark.asyncio
    async def test_innocence_brevo_success_never_calls_zoho_and_logs_redacted_only(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        service = _make_service()
        service.email_service = _FakeZohoService()
        _patch_brevo(monkeypatch, _FakeResponse)

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.send_birthday_email(_CLIENT)

        assert result is True
        assert not service.email_service.sent, "Zoho must not be tried when Brevo succeeds"
        assert _LEAK not in caplog.text
        assert redact_identifier_for_log(_LEAK) in caplog.text


class TestBrevoFailureFallsThroughAndNeverLogsTheAddress:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "brevo_exc",
        [
            # Each message carries the address itself: a provider error can
            # name the recipient it rejected, so redacting only the argument
            # the log line passes is not enough.
            httpx.ConnectError(f"connection refused for {_LEAK}"),
            OSError(f"network unreachable sending to {_LEAK}"),
            RuntimeError(f"brevo rejected {_LEAK}"),
        ],
        ids=["httpx_connect_error", "os_error", "runtime_error"],
    )
    async def test_guilt_brevo_failure_then_zoho_success_never_logs_the_address(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        brevo_exc: Exception,
    ) -> None:
        service = _make_service()
        service.email_service = _FakeZohoService()
        _patch_brevo(monkeypatch, brevo_exc)

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.send_birthday_email(_CLIENT)

        assert result is True
        assert service.email_service.sent, "Zoho fallback must actually run"
        assert _LEAK not in caplog.text
        assert redact_identifier_for_log(_LEAK) in caplog.text


class TestZohoFailureNeverLogsTheAddressOrExceptionText:
    @pytest.mark.asyncio
    async def test_guilt_zoho_failure_after_brevo_failure_never_logs_address_or_text(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Both legs fail: Brevo's own error AND Zoho's own error each carry
        the synthetic address in their text — neither may reach the log,
        only the redacted stand-in and the exception TYPE."""
        service = _make_service()
        service.email_service = _FakeZohoService(
            exc=RuntimeError(f"zoho rejected recipient {_LEAK}")
        )
        _patch_brevo(monkeypatch, httpx.ConnectError(f"connection refused for {_LEAK}"))

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            result = await service.send_birthday_email(_CLIENT)

        assert result is False
        assert _LEAK not in caplog.text
        assert "zoho rejected recipient" not in caplog.text
        assert redact_identifier_for_log(_LEAK) in caplog.text
        assert "RuntimeError" in caplog.text


class TestNoLoggerExceptionOrTracebackOnAClientAddressedSend:
    @pytest.mark.asyncio
    async def test_no_traceback_is_emitted_on_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """`logger.exception`/`exc_info=True` on a client-addressed send is
        banned outright — it would attach the full traceback (which can
        embed locals, including the raw client dict) regardless of what the
        format string itself says."""
        service = _make_service()
        service.email_service = _FakeZohoService(
            exc=RuntimeError(f"zoho rejected recipient {_LEAK}")
        )
        _patch_brevo(monkeypatch, httpx.ConnectError("refused"))

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            await service.send_birthday_email(_CLIENT)

        assert all(record.exc_info is None for record in caplog.records)


class TestRunLevelFailureNeverLogsException:
    @pytest.mark.asyncio
    async def test_guilt_run_failure_logs_exception_type_only(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """R2 (PR #7385 round 1): `run_birthday_notifications`'s outer
        failure handler used to `%s`-interpolate the exception itself, and
        stash `str(e)` in `stats["error"]` — either can carry the
        recipient's address if the failure came from `get_todays_birthdays`
        surfacing a provider error."""
        service = _make_service()
        service.get_todays_birthdays = AsyncMock(
            side_effect=RuntimeError(f"query failed for {_LEAK}"),
        )

        with caplog.at_level(logging.ERROR, logger=_LOGGER_NAME):
            stats = await service.run_birthday_notifications()

        assert _LEAK not in caplog.text
        assert _LEAK not in stats["error"]
        assert stats["error"] == "RuntimeError"
        assert "RuntimeError" in caplog.text
