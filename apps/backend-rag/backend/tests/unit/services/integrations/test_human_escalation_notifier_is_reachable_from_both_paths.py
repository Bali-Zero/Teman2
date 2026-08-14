"""The human-escalation notifier must be reachable without a router.

Why this exists. Two WhatsApp surfaces need to tell a human that a conversation
needs them: the router (`whatsapp_chat.py`) and the inbox bot behind
`wa_outbox_worker` (a background service). Until 2026-08-11 the notifier lived
inside the router, so only the router could escalate — and `wa_inbox_bot.py`
stripped the persona's `[ESCALATE]` marker under a comment saying *"mirror
whatsapp_chat.py"* while calling nothing. It mirrored the FORM and not the
EFFECT.

The property that keeps that from happening again is not "the function moved"
(a grep proves that and proves nothing). It is: **a background service can
reach the notifier without importing a FastAPI router.** That is what the first
test asserts, by importing the notifier into a fresh interpreter with the router
absent and checking the router never gets pulled in — a plain import in this
process would pass even if the module dragged the whole web app behind it,
because pytest has already imported half the app.
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

NOTIFIER = "backend.services.integrations.human_escalation_notifier"
ROUTER = "backend.app.routers.whatsapp_chat"


def test_importing_the_notifier_does_not_drag_in_the_router() -> None:
    """A background service must not have to import a router to escalate.

    Run in a SUBPROCESS on purpose: inside the pytest process the router is
    already imported by other tests, so `sys.modules` would show it present no
    matter what this module does, and the assertion would be vacuous.
    """
    code = (
        "import importlib, sys\n"
        f"importlib.import_module({NOTIFIER!r})\n"
        f"print({ROUTER!r} in sys.modules)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"notifier failed to import standalone: {proc.stderr[-800:]}"
    assert proc.stdout.strip() == "False", (
        "importing the notifier pulled the FastAPI router in with it — the "
        f"extraction bought nothing. stdout={proc.stdout!r}"
    )


def test_the_router_still_exposes_the_same_function_object() -> None:
    """The re-export is the SAME object, not a lookalike.

    Two callables with one name is how the drift this fixes began.
    """
    from backend.app.routers import whatsapp_chat
    from backend.services.integrations import human_escalation_notifier

    assert whatsapp_chat.notify_human_telegram is human_escalation_notifier.notify_human_telegram


@pytest.mark.asyncio
async def test_it_sends_and_masks_the_phone_but_not_the_body() -> None:
    """Guilt: it notifies — and the payload is what it was before the move.

    The masking is asserted because it is a live PII property, not decoration:
    the identifier is reduced, the message body is not. Any future caller that
    wants a narrower payload has to change the CALL, and this pins what today's
    call actually ships.
    """
    telegram = MagicMock()
    telegram.send_message = AsyncMock()

    with (
        patch(f"{NOTIFIER}.settings") as settings,
        patch(f"{NOTIFIER}.telegram_bot", telegram),
    ):
        settings.admin_telegram_chat_id = "8847435604"
        from backend.services.integrations.human_escalation_notifier import (
            notify_human_telegram,
        )

        await notify_human_telegram(
            phone="621234567890",
            message_text="I need help with my visa renewal",
            sender_name="Test Sender",
            reason="ai_escalation",
        )

    telegram.send_message.assert_called_once()
    text = telegram.send_message.call_args.kwargs["text"]
    assert "6212***90" in text, "the phone mask changed shape"
    assert "621234567890" not in text, "the full phone leaked into the notification"
    assert "I need help with my visa renewal" in text, (
        "the body is NOT masked today — if this ever starts passing for the "
        "opposite reason, the payload narrowed and the callers must be re-read"
    )


@pytest.mark.asyncio
async def test_it_stays_quiet_when_no_admin_chat_is_configured() -> None:
    """Innocence: unset chat id → no send, and no exception either."""
    telegram = MagicMock()
    telegram.send_message = AsyncMock()

    with (
        patch(f"{NOTIFIER}.settings") as settings,
        patch(f"{NOTIFIER}.telegram_bot", telegram),
    ):
        settings.admin_telegram_chat_id = None
        from backend.services.integrations.human_escalation_notifier import (
            notify_human_telegram,
        )

        await notify_human_telegram(phone="62123", message_text="Help")

    telegram.send_message.assert_not_called()
