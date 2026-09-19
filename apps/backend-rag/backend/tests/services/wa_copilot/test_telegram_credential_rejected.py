"""A credential Telegram REFUSES must be as loud as one that was never set.

Why this file exists (measured 2026-09-19/20, PROD `nuzantara-rag`): the bot
token was revoked, `getMe` answered `401 Unauthorized`, and every staff page
and both GARUDA alarms went mute — including the alarm whose whole job is to
shout that a job exhausted its retries, because it sends through the same
token. In the logs the only trace was a WARNING reading `HTTP 401
(non-retryable)`, indistinguishable from a malformed message, while the branch
for an UNSET token already screamed `NO WAY TO SEND IT`. Row 36 of
`garuda_order_outbox` then spent all five attempts against that dead token.

The two are one entity — "no way to send" — and only one of them was audible.
These tests pin the distinction, in both directions: a rejected credential is
recognised (guilt), and the other 4xx are NOT (innocence), because a guard
that over-matches is the same defect as one that under-matches (superscar #3).
"""

from __future__ import annotations

import logging

import httpx
import pytest

from backend.services.wa_copilot.telegram_notifier import (
    CREDENTIAL_REJECTED_STATUSES,
    is_credential_rejected,
    send_telegram_message,
)

TOKEN = "123456:FAKE-TOKEN-FOR-TESTS"
CHAT_ID = "999"


def _client(status: int, body: str) -> httpx.AsyncClient:
    """An httpx client whose every POST answers `status` with `body`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# guilt — the statuses that mean the credential is dead
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status", sorted(CREDENTIAL_REJECTED_STATUSES))
async def test_rejected_credential_is_flagged_as_such(status: int) -> None:
    async with _client(status, '{"ok":false,"description":"Unauthorized"}') as client:
        ok, err = await send_telegram_message(client, TOKEN, CHAT_ID, "hi")

    assert ok is False
    assert is_credential_rejected(err), f"HTTP {status} must read as a dead credential"


@pytest.mark.asyncio
async def test_rejected_credential_logs_at_error_not_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The volume IS the fix: WARNING is what it used to be, and nobody heard it."""
    with caplog.at_level(logging.WARNING):
        async with _client(401, '{"ok":false,"description":"Unauthorized"}') as client:
            await send_telegram_message(client, TOKEN, CHAT_ID, "hi")

    rejected = [r for r in caplog.records if "CREDENTIAL REJECTED" in r.getMessage()]
    assert rejected, "a refused token must announce itself in the log"
    assert all(r.levelno >= logging.ERROR for r in rejected)


@pytest.mark.asyncio
async def test_the_error_text_never_carries_the_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The loud path is a new place a secret could leak. It must not."""
    with caplog.at_level(logging.DEBUG):
        async with _client(401, '{"ok":false,"description":"Unauthorized"}') as client:
            _, err = await send_telegram_message(client, TOKEN, CHAT_ID, "hi")

    assert TOKEN not in (err or "")
    assert all(TOKEN not in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# innocence — every other 4xx is about the message, not the credential
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body"),
    [
        (400, '{"ok":false,"description":"Bad Request: can\'t parse entities"}'),
        (429, '{"ok":false,"description":"Too Many Requests: retry after 30"}'),
        (404, '{"ok":false,"description":"Not Found"}'),
    ],
)
async def test_other_4xx_are_not_a_dead_credential(status: int, body: str) -> None:
    async with _client(status, body) as client:
        ok, err = await send_telegram_message(client, TOKEN, CHAT_ID, "hi")

    assert ok is False
    assert not is_credential_rejected(err), f"HTTP {status} is about the message"


@pytest.mark.asyncio
async def test_a_400_quoting_the_word_unauthorized_is_still_not_one() -> None:
    """The predicate reads OUR prefix, never the body Telegram sent.

    Without this, a 400 whose free-text description happens to contain the
    word would be promoted to "the credential is dead" — the over-match half
    of superscar #3, and the reason membership is a set of CODES.
    """
    body = '{"ok":false,"description":"Bad Request: the word Unauthorized appears here"}'
    async with _client(400, body) as client:
        _, err = await send_telegram_message(client, TOKEN, CHAT_ID, "hi")

    assert not is_credential_rejected(err)


def test_predicate_on_absent_and_unrelated_errors() -> None:
    assert not is_credential_rejected(None)
    assert not is_credential_rejected("")
    assert not is_credential_rejected("TimeoutException: timed out")
    assert not is_credential_rejected("exhausted retries")


def test_5xx_is_not_in_the_rejected_set() -> None:
    """A transient server error must keep retrying, not be declared fatal."""
    assert 500 not in CREDENTIAL_REJECTED_STATUSES
    assert 502 not in CREDENTIAL_REJECTED_STATUSES
