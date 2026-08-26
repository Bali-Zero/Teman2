"""End-to-end (HTTP, real router, real HMAC verifier) guilt+innocence tests
for the 2026-08-26 team-bot-ingress routing fix.

Reuses the B6a webhook-replay harness (``conftest.duebot`` + ``replay`` +
``fake_meta_sender``) rather than inventing a parallel style — see those
modules' docstrings for what they prove independently (signature
verification, dedup) so this file does not re-prove it.

The defect (see ``backend/tests/unit/routers/test_team_bot_ingress_routing.py``
for the full writeup): the team-bot number is on the SAME Meta app/webhook
as the public client number. Before this fix its messages fell through into
the legacy inline client-triage flow. This file proves the fix at the
transport layer: a real signed HTTP POST to ``/webhook/whatsapp`` carrying
the team-bot ``phone_number_id`` reaches neither
``process_whatsapp_message_and_mark_processed`` (legacy) nor
``process_meta_inbox_payload`` (client meta-inbox pipeline) — only the
team-bot ingress seam, gated by ``TEAM_BOT_INGRESS_ENABLED``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.app.core.config import settings
from backend.app.routers import whatsapp_chat
from backend.tests.duebot.conftest import DuebotHarness
from backend.tests.duebot.fake_meta_sender import to_raw_body, whatsapp_text_payload
from backend.tests.duebot.replay import whatsapp_replayer

APP_SECRET = "harness-team-bot-ingress-app-secret-do-not-use-in-prod"
TEAM_ID = whatsapp_chat.TEAM_BOT_PHONE_NUMBER_ID
SECOND_META_INBOX_SUBSCRIPTION_ID = "2000000000000000"  # unlisted id, same visible number
PUBLIC_DISPLAY_NUMBER = "628213465159"  # digits of settings.SUPPORT_WHATSAPP default


@pytest.fixture(autouse=True)
def _configured_app_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Arm the real signature check (same rationale as test_webhook_replay.py)
    instead of running against the no-secret dev-mode bypass.
    """
    monkeypatch.setattr(settings, "whatsapp_app_secret", APP_SECRET)


@pytest.fixture
def team_bot_ingress_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patches the ingress seam itself so tests can assert on it directly —
    the seam is a stub (no real B3 handler exists on this branch yet), so
    the interesting assertion is call/no-call, not its internal behavior.
    """
    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(whatsapp_chat, "_handle_team_bot_ingress_payload", mock)
    return mock


@pytest.fixture
def meta_inbox_guard(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Fails the test loudly if the client meta-inbox pipeline is ever
    scheduled — the second wrong destination this lane must avoid.
    """
    mock = AsyncMock(
        side_effect=AssertionError(
            "process_meta_inbox_payload must not run for team-bot traffic"
        )
    )
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", mock)
    return mock


def test_team_bot_message_with_switch_on_reaches_only_the_ingress_seam(
    duebot: DuebotHarness,
    team_bot_ingress_mock: AsyncMock,
    meta_inbox_guard: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt: the exact defect input, switch ON — must reach the ingress
    seam and NEITHER of the two wrong destinations.
    """
    monkeypatch.setenv("TEAM_BOT_INGRESS_ENABLED", "true")
    raw_body = to_raw_body(
        whatsapp_text_payload(message_id="wamid.TEAM_ON", phone_number_id=TEAM_ID)
    )
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    team_bot_ingress_mock.assert_awaited_once()
    duebot.process_whatsapp_mock.assert_not_awaited()
    meta_inbox_guard.assert_not_awaited()


def test_team_bot_message_with_switch_off_is_recognised_and_dropped(
    duebot: DuebotHarness,
    team_bot_ingress_mock: AsyncMock,
    meta_inbox_guard: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed, born OFF: the default (no env var set) must still ACK
    with 200 (Meta must never see a webhook failure) but must not hand the
    change to the ingress seam, and must not fall through to legacy either.
    """
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    raw_body = to_raw_body(
        whatsapp_text_payload(message_id="wamid.TEAM_OFF", phone_number_id=TEAM_ID)
    )
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    team_bot_ingress_mock.assert_not_awaited()
    duebot.process_whatsapp_mock.assert_not_awaited()
    meta_inbox_guard.assert_not_awaited()


@pytest.mark.parametrize("switch_state", ["true", None], ids=["switch-on", "switch-off"])
def test_public_client_traffic_is_completely_untouched(
    duebot: DuebotHarness,
    team_bot_ingress_mock: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    switch_state: str | None,
) -> None:
    """Innocence — the more important half per the mandate: ordinary client
    traffic on the public number must behave EXACTLY as before this lane,
    regardless of the team-bot kill switch's state.
    """
    if switch_state is None:
        monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    else:
        monkeypatch.setenv("TEAM_BOT_INGRESS_ENABLED", switch_state)
    raw_body = to_raw_body(whatsapp_text_payload(message_id="wamid.CLIENT_UNTOUCHED"))
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    duebot.process_whatsapp_mock.assert_awaited_once()
    assert duebot.process_whatsapp_mock.call_args.kwargs["message_id"] == "wamid.CLIENT_UNTOUCHED"
    team_bot_ingress_mock.assert_not_awaited()


def test_double_reply_defense_still_works_end_to_end(
    duebot: DuebotHarness,
    team_bot_ingress_mock: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence — the 2026-08-25 double-reply scar's defense-in-depth
    (an unlisted pnid whose display_phone_number is the public number)
    must still be caught by the pre-existing meta-inbox check, untouched
    by the new team-bot branch sitting ahead of it in the loop.

    The meta-inbox pipeline itself (``process_meta_inbox_payload`` /
    ``_ingest_meta_inbox_media``) is mocked here — it is pre-existing,
    out-of-scope code this test has no business exercising against a bare
    ``MagicMock`` db_pool; the only thing this test cares about is that
    the change is classified as meta-inbox (so it is scheduled at all) and
    that neither the legacy flow nor the team-bot seam sees it.
    """
    monkeypatch.delenv("TEAM_BOT_INGRESS_ENABLED", raising=False)
    meta_inbox_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(whatsapp_chat, "process_meta_inbox_payload", meta_inbox_mock)
    monkeypatch.setattr(
        whatsapp_chat, "_ingest_meta_inbox_media", AsyncMock(return_value=None)
    )
    raw_body = to_raw_body(
        whatsapp_text_payload(
            message_id="wamid.RESUBSCRIBE",
            phone_number_id=SECOND_META_INBOX_SUBSCRIPTION_ID,
            phone=PUBLIC_DISPLAY_NUMBER,
        )
    )
    replayer = whatsapp_replayer(duebot.client)

    result = replayer.send_signed(raw_body, APP_SECRET)

    assert result.status_code == 200
    meta_inbox_mock.assert_awaited_once()
    duebot.process_whatsapp_mock.assert_not_awaited()
    team_bot_ingress_mock.assert_not_awaited()
