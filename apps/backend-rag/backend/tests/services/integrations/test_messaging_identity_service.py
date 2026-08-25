from __future__ import annotations

import logging
import re
from typing import Any

import asyncpg
import pytest

from backend.services.integrations import messaging_identity_service as identity_module
from backend.services.integrations.messaging_identity_service import MessagingIdentityService

#: Module logger name — messaging_identity_service.py does
#: ``logging.getLogger(__name__)``.
_LOGGER_NAME = "backend.services.integrations.messaging_identity_service"

# Obviously-synthetic — never a shape that could be mistaken for a real
# client's WhatsApp number or Telegram chat id.
_SYNTHETIC_PHONE = "+62 000-111-2222"
_SYNTHETIC_PHONE_DIGITS = "620001112222"
_SYNTHETIC_CHAT_ID = 194920123

_NON_DIGITS_RE = re.compile(r"\D+")


def _digits_only(text: str) -> str:
    """Collapse a log line to its bare digit run.

    Load-bearing for the guilt tests below: the ORIGINAL (unfixed) code
    only did ``phone.lstrip("+")`` before logging at some call sites, so a
    leaking phone could surface as ``"62 000-111-2222"`` (leading '+'
    stripped, internal dashes/space intact) rather than verbatim as the
    caller passed it. An exact-string check against the caller's literal
    input (with its '+' and dashes) MISSES that — proven empirically: the
    first draft of these tests passed even against the unfixed code for
    exactly this reason. Comparing digit runs is robust to whichever of
    '+62 000-111-2222' / '62 000-111-2222' / '620001112222' the leak takes.
    """
    return _NON_DIGITS_RE.sub("", text)


class FakeConnection:
    def __init__(
        self,
        *,
        fetchrow_result: dict[str, Any] | None = None,
        fetch_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self.fetchrow_result = fetchrow_result
        self.fetch_result = fetch_result or []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((sql, args))
        return self.fetchrow_result

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((sql, args))
        return self.fetch_result

    async def execute(self, sql: str, *args: Any) -> None:
        self.execute_calls.append((sql, args))


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def test_get_messaging_identity_service_reuses_singleton() -> None:
    identity_module._messaging_identity_service = None
    pool = FakePool(FakeConnection())

    first = identity_module.get_messaging_identity_service(pool)
    second = identity_module.get_messaging_identity_service(FakePool(FakeConnection()))

    try:
        assert first is second
        assert first.db_pool is pool
    finally:
        identity_module._messaging_identity_service = None


@pytest.mark.asyncio
async def test_get_user_by_phone_normalizes_plus_prefix() -> None:
    row = {
        "user_id": "user-1",
        "display_name": "Client",
        "verified": True,
        "last_message_at": None,
    }
    connection = FakeConnection(fetchrow_result=row)
    service = MessagingIdentityService(FakePool(connection))

    assert await service.get_user_by_phone("+628123") == row
    assert connection.fetchrow_calls[0][1] == ("628123",)


@pytest.mark.asyncio
async def test_get_user_by_telegram_returns_mapping() -> None:
    row = {"user_id": "user-1", "display_name": "Client", "verified": False}
    connection = FakeConnection(fetchrow_result=row)
    service = MessagingIdentityService(FakePool(connection))

    assert await service.get_user_by_telegram(12345) == row
    assert connection.fetchrow_calls[0][1] == (12345,)


@pytest.mark.asyncio
async def test_create_mapping_validates_channel_and_required_identifier() -> None:
    service = MessagingIdentityService(FakePool(FakeConnection()))

    assert await service.create_mapping("user-1", "sms") is False
    assert await service.create_mapping("user-1", "whatsapp") is False
    assert await service.create_mapping("user-1", "telegram") is False


@pytest.mark.asyncio
async def test_create_mapping_persists_normalized_whatsapp_phone() -> None:
    connection = FakeConnection()
    service = MessagingIdentityService(FakePool(connection))

    result = await service.create_mapping(
        user_id="user-1",
        channel="whatsapp",
        phone="+628123",
        display_name="Client",
        verified=True,
    )

    assert result is True
    _, args = connection.execute_calls[0]
    assert args == ("user-1", "whatsapp", "628123", None, "Client", True)


@pytest.mark.asyncio
async def test_update_last_message_and_deactivate_require_an_identifier() -> None:
    connection = FakeConnection()
    service = MessagingIdentityService(FakePool(connection))

    assert await service.update_last_message() is False
    assert await service.deactivate_mapping() is False
    assert await service.update_last_message(phone="+628123") is True
    assert await service.deactivate_mapping(telegram_chat_id=456) is True
    assert connection.execute_calls[0][1] == ("628123",)
    assert connection.execute_calls[1][1] == (456,)


@pytest.mark.asyncio
async def test_get_mappings_for_user_returns_rows_as_dicts() -> None:
    rows = [
        {"id": 1, "channel": "whatsapp", "phone": "628123", "verified": True},
        {"id": 2, "channel": "telegram", "telegram_chat_id": 456, "verified": False},
    ]
    connection = FakeConnection(fetch_result=rows)
    service = MessagingIdentityService(FakePool(connection))

    assert await service.get_mappings_for_user("user-1") == rows
    assert connection.fetch_calls[0][1] == ("user-1",)


# ── F7: raw phone/chat_id must NEVER appear in a log record ────────────────
#
# Guilt/innocence per cicatrix-superscar.md family #3: prove the raw value
# never survives to a log record (guilt) AND prove the digest still lets an
# operator correlate lines (innocence) — a redaction that collapses every
# line to the same placeholder destroys correlation, which is a different
# failure, not a fix.


class RaisingConnection(FakeConnection):
    """A connection whose fetchrow/execute raise instead of returning."""

    def __init__(self, *, raises: BaseException) -> None:
        super().__init__()
        self._raises = raises

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((sql, args))
        raise self._raises

    async def execute(self, sql: str, *args: Any) -> None:
        self.execute_calls.append((sql, args))
        raise self._raises


def _all_log_text(records: list[logging.LogRecord]) -> str:
    """Every rendered message across every captured record, concatenated —
    guilt must be checked across ALL lines, not just the one line a fix
    happened to target (that is exactly how a partial fix reads as done)."""
    return "\n".join(r.getMessage() for r in records)


class TestRawPhoneNeverInLogsGuilt:
    @pytest.mark.asyncio
    async def test_get_user_by_phone_success_never_logs_raw_phone(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        row = {
            "user_id": "user-1",
            "display_name": "Client",
            "verified": True,
            "last_message_at": None,
        }
        connection = FakeConnection(fetchrow_result=row)
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            await service.get_user_by_phone(_SYNTHETIC_PHONE)

        text = _all_log_text(caplog.records)
        assert _SYNTHETIC_PHONE not in text
        assert _SYNTHETIC_PHONE_DIGITS not in _digits_only(text)

    @pytest.mark.asyncio
    async def test_get_user_by_phone_db_error_never_logs_raw_phone(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connection = RaisingConnection(raises=asyncpg.PostgresError("boom"))
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.get_user_by_phone(_SYNTHETIC_PHONE)

        assert result is None
        text = _all_log_text(caplog.records)
        assert _SYNTHETIC_PHONE not in text
        assert _SYNTHETIC_PHONE_DIGITS not in _digits_only(text)

    @pytest.mark.asyncio
    async def test_get_user_by_telegram_success_never_logs_raw_chat_id(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        row = {"user_id": "user-1", "display_name": "Client", "verified": False}
        connection = FakeConnection(fetchrow_result=row)
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            await service.get_user_by_telegram(_SYNTHETIC_CHAT_ID)

        text = _all_log_text(caplog.records)
        assert str(_SYNTHETIC_CHAT_ID) not in text

    @pytest.mark.asyncio
    async def test_get_user_by_telegram_db_error_never_logs_raw_chat_id(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connection = RaisingConnection(raises=asyncpg.PostgresError("boom"))
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.get_user_by_telegram(_SYNTHETIC_CHAT_ID)

        assert result is None
        text = _all_log_text(caplog.records)
        assert str(_SYNTHETIC_CHAT_ID) not in text

    @pytest.mark.asyncio
    async def test_create_mapping_success_never_logs_raw_phone(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connection = FakeConnection()
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.create_mapping(
                user_id="user-1",
                channel="whatsapp",
                phone=_SYNTHETIC_PHONE,
                display_name="Client",
                verified=True,
            )

        assert result is True
        text = _all_log_text(caplog.records)
        assert _SYNTHETIC_PHONE not in text
        assert _SYNTHETIC_PHONE_DIGITS not in _digits_only(text)

    @pytest.mark.asyncio
    async def test_create_mapping_duplicate_never_logs_raw_phone(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connection = RaisingConnection(raises=asyncpg.UniqueViolationError("dup key"))
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.create_mapping(
                user_id="user-1",
                channel="whatsapp",
                phone=_SYNTHETIC_PHONE,
            )

        assert result is False
        text = _all_log_text(caplog.records)
        assert _SYNTHETIC_PHONE not in text
        assert _SYNTHETIC_PHONE_DIGITS not in _digits_only(text)

    @pytest.mark.asyncio
    async def test_deactivate_mapping_never_logs_raw_phone(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connection = FakeConnection()
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.deactivate_mapping(phone=_SYNTHETIC_PHONE)

        assert result is True
        text = _all_log_text(caplog.records)
        assert _SYNTHETIC_PHONE not in text
        assert _SYNTHETIC_PHONE_DIGITS not in _digits_only(text)

    @pytest.mark.asyncio
    async def test_deactivate_mapping_never_logs_raw_chat_id(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        connection = FakeConnection()
        service = MessagingIdentityService(FakePool(connection))

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            result = await service.deactivate_mapping(telegram_chat_id=_SYNTHETIC_CHAT_ID)

        assert result is True
        text = _all_log_text(caplog.records)
        assert str(_SYNTHETIC_CHAT_ID) not in text


class TestRedactedLogStaysCorrelatable:
    """The fix must not degrade the logs into a useless '***' — a stable
    digest must appear so an operator can still follow one conversation
    across log lines."""

    @pytest.mark.asyncio
    async def test_digest_present_and_stable_across_two_calls(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        row = {
            "user_id": "user-1",
            "display_name": "Client",
            "verified": True,
            "last_message_at": None,
        }

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            await MessagingIdentityService(
                FakePool(FakeConnection(fetchrow_result=row)),
            ).get_user_by_phone(_SYNTHETIC_PHONE)
            first_text = _all_log_text(caplog.records)
            caplog.clear()

            await MessagingIdentityService(
                FakePool(FakeConnection(fetchrow_result=row)),
            ).get_user_by_phone(_SYNTHETIC_PHONE)
            second_text = _all_log_text(caplog.records)

        assert "id:" in first_text
        assert "id:" in second_text
        # Same phone -> same digest, so the two log lines are correlatable
        # even though neither carries the raw phone.
        first_digest = next(tok for tok in first_text.split() if tok.startswith("id:"))
        second_digest = next(tok for tok in second_text.split() if tok.startswith("id:"))
        assert first_digest == second_digest

    @pytest.mark.asyncio
    async def test_different_phones_get_different_digests(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        row = {
            "user_id": "user-1",
            "display_name": "Client",
            "verified": True,
            "last_message_at": None,
        }

        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            await MessagingIdentityService(
                FakePool(FakeConnection(fetchrow_result=row)),
            ).get_user_by_phone(_SYNTHETIC_PHONE)
            first_text = _all_log_text(caplog.records)
            caplog.clear()

            await MessagingIdentityService(
                FakePool(FakeConnection(fetchrow_result=row)),
            ).get_user_by_phone("+62 999-888-7777")
            second_text = _all_log_text(caplog.records)

        first_digest = next(tok for tok in first_text.split() if tok.startswith("id:"))
        second_digest = next(tok for tok in second_text.split() if tok.startswith("id:"))
        assert first_digest != second_digest
