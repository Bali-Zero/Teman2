"""Webhook callback handler for FAD ``fad:*`` Telegram callbacks.

Wired into ``apps/backend-rag/backend/app/routers/telegram_webhook.py``
ahead of the ChannelRouter fallthrough.

Validation pipeline:
    1. Decode (defensive parser, returns None on malformed)
    2. Verify chat_id is in admin allow-list
    3. Verify HMAC token prefix against DB approval_token
    4. Apply state transition (record_approval / record_rejection /
       set_db_mode)
    5. Edit Telegram message to strip inline keyboard

All failure paths log + answer the callback so the user gets feedback
in the UI ("Invalid token", "Already processed", etc.).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

import asyncpg

from backend.services.federation_alerts.approval import (
    is_admin_chat_id,
    verify_callback_token,
)
from backend.services.federation_alerts.approval_models import (
    FADCallback,
    decode_callback,
)
from backend.services.federation_alerts.notifier import (
    edit_message_after_decision,
)
from backend.services.federation_alerts.repository import FederationAlertRepo

logger = logging.getLogger(__name__)


def _answer_callback(
    bot_token: str,
    callback_id: str,
    text: str,
    *,
    show_alert: bool = False,
    timeout_sec: int = 5,
) -> None:
    """Best-effort answer to acknowledge the inline-button press."""
    if not bot_token or not callback_id:
        return
    payload = {
        "callback_query_id": callback_id,
        "text": text[:200],
        "show_alert": show_alert,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec):  # noqa: S310
            pass
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.debug("answerCallbackQuery failed: %s", exc)


async def handle_fad_callback(
    callback_query: dict[str, Any],
    *,
    pool: asyncpg.Pool,
    bot_token: str,
) -> bool:
    """Process a fad:* callback. Returns True iff this handler owned it."""
    callback_data = callback_query.get("data", "")
    if not callback_data.startswith("fad:"):
        return False

    callback_id = callback_query.get("id", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    from_user = callback_query.get("from", {}) or {}
    actor = (
        from_user.get("username")
        or str(from_user.get("id", "unknown"))
    )

    parsed: FADCallback | None = decode_callback(callback_data)
    if parsed is None:
        logger.warning("FAD callback malformed: %s", callback_data[:80])
        _answer_callback(
            bot_token, callback_id,
            "Invalid callback (malformed)",
            show_alert=True,
        )
        return True

    if not is_admin_chat_id(chat_id):
        logger.warning(
            "FAD callback from non-admin chat_id=%s (data=%s)",
            chat_id, callback_data[:60],
        )
        _answer_callback(
            bot_token, callback_id,
            "Not authorized",
            show_alert=True,
        )
        return True

    repo = FederationAlertRepo(pool=pool)

    if parsed.is_mode_change():
        return await _handle_mode_change(
            repo, parsed, callback_id, chat_id, message_id,
            bot_token, actor,
        )

    return await _handle_approval(
        repo, parsed, callback_id, chat_id, message_id,
        bot_token, actor,
    )


async def _handle_approval(
    repo: FederationAlertRepo,
    parsed: FADCallback,
    callback_id: str,
    chat_id: object,
    message_id: int | None,
    bot_token: str,
    actor: str,
) -> bool:
    proposal_id = parsed.target
    proposal = await repo.get_by_proposal_id(proposal_id)
    if proposal is None:
        _answer_callback(
            bot_token, callback_id,
            "Proposal not found",
            show_alert=True,
        )
        return True

    # Token check (B6: even if message ID is captured, token mismatch rejects)
    valid = verify_callback_token(
        proposal.approval_token, proposal_id, parsed.token_prefix
    )
    if not valid:
        logger.warning(
            "FAD callback token mismatch for proposal=%s (presented=%s)",
            proposal_id, parsed.token_prefix,
        )
        _answer_callback(
            bot_token, callback_id,
            "Token expired or invalid",
            show_alert=True,
        )
        return True

    # State guard: only accept callbacks while in awaiting_approval
    status_str = (
        proposal.status if isinstance(proposal.status, str)
        else proposal.status.value
    )
    if status_str != "awaiting_approval":
        _answer_callback(
            bot_token, callback_id,
            f"Already {status_str}",
            show_alert=False,
        )
        return True

    if parsed.action == "approve":
        try:
            await repo.record_approval(proposal_id, approved_by=actor)
        except LookupError:
            _answer_callback(
                bot_token, callback_id, "Race lost — already decided"
            )
            return True
        _answer_callback(bot_token, callback_id, "✅ Approved")
        if message_id is not None and chat_id is not None:
            edit_message_after_decision(
                bot_token=bot_token,
                chat_id=str(chat_id),
                message_id=int(message_id),
                decision="approved",
                by_user=actor,
            )
        return True

    if parsed.action == "reject":
        try:
            await repo.record_rejection(
                proposal_id,
                rejected_by=actor,
                reason="rejected via Telegram inline button",
            )
        except LookupError:
            _answer_callback(
                bot_token, callback_id, "Race lost — already decided"
            )
            return True
        _answer_callback(bot_token, callback_id, "❌ Rejected")
        if message_id is not None and chat_id is not None:
            edit_message_after_decision(
                bot_token=bot_token,
                chat_id=str(chat_id),
                message_id=int(message_id),
                decision="rejected",
                by_user=actor,
            )
        return True

    if parsed.action == "defer":
        # No DB mutation — leaves status=awaiting_approval, daemon
        # will re-surface on next pulse (out of scope V1: actually
        # increment next_attempt_at).
        _answer_callback(bot_token, callback_id, "🕒 Deferred")
        return True

    _answer_callback(
        bot_token, callback_id, f"Unknown action: {parsed.action}",
        show_alert=True,
    )
    return True


async def _handle_mode_change(
    repo: FederationAlertRepo,
    parsed: FADCallback,
    callback_id: str,
    chat_id: object,
    message_id: int | None,
    bot_token: str,
    actor: str,
) -> bool:
    # parsed.target is the mode literal; HMAC token is computed against
    # f"mode:{target_mode}" so admins can change mode without going
    # through a real proposal_id.
    expected_anchor = f"mode:{parsed.target}"
    # We don't have a dedicated "mode change token" stored anywhere, so
    # mode changes via callback require an out-of-band token rotation
    # mechanism. For V1 we accept the change ONLY if the chat is admin
    # AND the prefix matches a daemon-side rotating secret in the
    # FEDERATION_ALERT_MODE_TOKEN env var.
    import hashlib
    import hmac
    import os

    mode_secret = os.environ.get("FEDERATION_ALERT_MODE_TOKEN", "").strip()
    if not mode_secret:
        _answer_callback(
            bot_token, callback_id,
            "Mode change disabled (no token configured)",
            show_alert=True,
        )
        return True
    expected_prefix = hmac.new(
        mode_secret.encode("utf-8"),
        expected_anchor.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:8]
    if not hmac.compare_digest(expected_prefix, parsed.token_prefix.lower()):
        logger.warning(
            "FAD mode change token mismatch (target=%s)", parsed.target
        )
        _answer_callback(
            bot_token, callback_id,
            "Mode change token invalid",
            show_alert=True,
        )
        return True

    try:
        await repo.set_db_mode(parsed.target, changed_by=actor)
    except ValueError as exc:
        _answer_callback(
            bot_token, callback_id, f"Invalid mode: {exc}",
            show_alert=True,
        )
        return True
    _answer_callback(
        bot_token, callback_id,
        f"Mode → {parsed.target}",
    )
    if message_id is not None and chat_id is not None:
        edit_message_after_decision(
            bot_token=bot_token,
            chat_id=str(chat_id),
            message_id=int(message_id),
            decision="approved",
            by_user=f"{actor} → mode={parsed.target}",
        )
    return True


__all__ = ["handle_fad_callback"]
