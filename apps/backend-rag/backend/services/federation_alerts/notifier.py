"""Telegram notifier for FAD proposals (HITL_ONLY approval requests).

Composes a short, HTML-formatted summary of a proposal and sends it
to the admin chat with inline approve/reject/defer buttons.

Uses ``urllib.request`` directly (no external dependency) — keeps the
daemon's runtime footprint minimal. Best-effort: failures log a
warning but do not crash the daemon.

Per Symbiosis Law 4 (event-driven) and Spec section "Telegram callback
contract", every keyboard button has a one-time-token-prefixed
callback. Buttons:

    ✅ Approve   → fad:approve:<proposal_id>:<token8>
    ❌ Reject    → fad:reject:<proposal_id>:<token8>
    🕒 Defer     → fad:defer:<proposal_id>:<token8>
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from backend.services.federation_alerts.approval import callback_token_prefix
from backend.services.federation_alerts.approval_models import encode_callback

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


def _format_proposal_message(proposal: Any) -> str:
    """HTML-formatted summary safe for Telegram parse_mode='HTML'.

    Pipeline names with underscores are wrapped in <code>...</code> to
    avoid the legacy-Markdown parser's italic-on-underscore footgun
    (cf. cicatrix 2026-04-30 heartbeat HTTP 400).
    """
    severity_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🔵",
        "info": "⚪",
    }.get(getattr(proposal, "severity", "medium"), "⚪")

    action = getattr(proposal, "requested_action", None) or "(none)"
    alert_type = getattr(proposal, "alert_type", "alert")
    risk_level = getattr(proposal, "risk_level", "L2")
    proposal_id = getattr(proposal, "proposal_id", "?")
    deliberation = getattr(proposal, "deliberation_result", {}) or {}
    active = deliberation.get("active_llms")
    passed = deliberation.get("passed")

    lines = [
        f"{severity_emoji} <b>FAD Proposal — {alert_type}</b>",
        f"action: <code>{action}</code>",
        f"risk: <code>{risk_level}</code>",
        f"id: <code>{proposal_id[:8]}</code>",
    ]
    if active is not None or passed is not None:
        lines.append(
            f"consiglio: gate6={'✅' if passed else '⚠️'}  active={active}/4"
        )
    return "\n".join(lines)


def _build_inline_keyboard(
    proposal_id: str, approval_token: str
) -> dict[str, Any]:
    """Three-button keyboard: approve / reject / defer."""
    prefix = callback_token_prefix(approval_token, proposal_id)
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve",
                    "callback_data": encode_callback(
                        "approve", proposal_id, prefix
                    ),
                },
                {
                    "text": "❌ Reject",
                    "callback_data": encode_callback(
                        "reject", proposal_id, prefix
                    ),
                },
                {
                    "text": "🕒 Defer",
                    "callback_data": encode_callback(
                        "defer", proposal_id, prefix
                    ),
                },
            ]
        ]
    }


def send_proposal_to_telegram(
    *,
    bot_token: str,
    chat_id: str,
    proposal: Any,
    approval_token: str,
    timeout_sec: int = 10,
) -> int | None:
    """Synchronous send. Returns Telegram ``message_id`` on success, or None.

    Synchronous because the daemon code path that calls it is already
    inside an async-but-thread-tolerant context (asyncio.to_thread).
    Keeping it sync avoids pulling httpx/aiohttp into the daemon
    runtime — urllib is standard library only.
    """
    if not bot_token or not chat_id:
        logger.warning(
            "send_proposal_to_telegram: bot_token or chat_id missing"
        )
        return None

    proposal_id = getattr(proposal, "proposal_id", None)
    if not proposal_id:
        logger.warning("send_proposal_to_telegram: proposal_id missing")
        return None

    payload = {
        "chat_id": chat_id,
        "text": _format_proposal_message(proposal),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": _build_inline_keyboard(proposal_id, approval_token),
    }
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        f"{_TELEGRAM_API}/bot{bot_token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "Telegram sendMessage failed for proposal %s: %s",
            proposal_id, exc,
        )
        return None

    if not data.get("ok"):
        logger.warning(
            "Telegram sendMessage non-ok for proposal %s: %s",
            proposal_id, data,
        )
        return None
    msg_id = data.get("result", {}).get("message_id")
    return int(msg_id) if isinstance(msg_id, int) else None


def edit_message_after_decision(
    *,
    bot_token: str,
    chat_id: str,
    message_id: int,
    decision: str,           # "approved" | "rejected" | "deferred" | "expired"
    by_user: str | None = None,
    timeout_sec: int = 5,
) -> bool:
    """Strip the inline keyboard + append a status footer to the message.

    Best-effort: returns False on any error (caller logs).
    """
    if not bot_token or not chat_id or not message_id:
        return False
    # Decision footer is intentionally NOT appended here — Telegram's
    # editMessageReplyMarkup only mutates the inline keyboard, not the
    # body text. A future PR can switch to editMessageText if we want
    # the message itself to reflect the decision (currently the
    # answerCallbackQuery toast is the user-visible feedback).
    _ = decision  # accepted but only logged
    _ = by_user

    # Use editMessageReplyMarkup to strip buttons; we cannot append to
    # the body without re-sending all text. Simpler: just remove keyboard.
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": []},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_TELEGRAM_API}/bot{bot_token}/editMessageReplyMarkup",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "Telegram editMessageReplyMarkup failed (msg=%s): %s",
            message_id, exc,
        )
        return False
    return bool(data.get("ok"))


__all__ = [
    "send_proposal_to_telegram",
    "edit_message_after_decision",
]
