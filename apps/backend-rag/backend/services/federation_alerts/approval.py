"""Telegram approval token primitives for FAD HITL_ONLY actions.

Per spec section "Telegram callback contract":

    fad:<action>:<proposal_id>:<token8>

Where:
    action       - approve | reject | defer | mode
    proposal_id  - UUID of federation_alert_proposals row
    token8       - first 8 hex chars of HMAC-SHA256(approval_token, proposal_id)

The full ``approval_token`` lives in the DB row (column
``approval_token``), generated at proposal creation time. The 8-byte
prefix in the callback is enough entropy to defeat replay (Telegram's
delivery is at-least-once, so the same callback may arrive twice; we
use the proposal status guard to refuse double-execution).

Comparison is timing-safe via ``hmac.compare_digest``. Mismatched
tokens → callback rejected, logged, no state change.

NB: FAD callbacks DO NOT carry chat_id. The whitelist of allowed
``approver_chat_id`` values is enforced by ``is_admin_chat_id``,
checked at the webhook layer before any DB mutation.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from typing import Final

logger = logging.getLogger(__name__)

# Token format constants — the full token is opaque, the public prefix
# is what travels through the Telegram callback (max 64 bytes total).
_TOKEN_BYTES: Final[int] = 32       # 32 random bytes -> 64 hex chars
_PREFIX_HEX_CHARS: Final[int] = 8    # surfaced in fad:<action>:<id>:<8hex>


def generate_approval_token() -> str:
    """Return a fresh opaque approval token (hex string).

    Stored in federation_alert_proposals.approval_token. Never reused —
    if a proposal is re-issued (lease expired, retry), generate a new
    token so the old Telegram message cannot trigger the new run.
    """
    return secrets.token_hex(_TOKEN_BYTES)


def callback_token_prefix(approval_token: str, proposal_id: str) -> str:
    """Compute the 8-hex-char prefix used in the Telegram callback.

    Anchoring the HMAC to ``proposal_id`` means a captured prefix from
    one proposal cannot be replayed against another (different
    proposal_id → different prefix).
    """
    digest = hmac.new(
        approval_token.encode("utf-8"),
        proposal_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:_PREFIX_HEX_CHARS]


def verify_callback_token(
    approval_token: str | None,
    proposal_id: str,
    presented_prefix: str,
) -> bool:
    """Timing-safe verify of the 8-hex-char prefix.

    Returns False (never raises) on:
        * approval_token is None or empty (proposal not in awaiting_approval)
        * prefix length wrong (defensive — Telegram clients won't truncate)
        * HMAC mismatch
    """
    if not approval_token:
        return False
    if len(presented_prefix) != _PREFIX_HEX_CHARS:
        return False
    expected = callback_token_prefix(approval_token, proposal_id)
    return hmac.compare_digest(expected, presented_prefix.lower())


# ---------------------------------------------------------------------------
# Admin chat allow-list — env-driven
# ---------------------------------------------------------------------------


def admin_chat_ids() -> frozenset[str]:
    """Whitelist of chat_ids allowed to send fad:approve/reject/mode callbacks.

    Defaults to {TELEGRAM_OWNER_CHAT_ID}. Override with
    FEDERATION_ALERT_ADMIN_CHAT_IDS as a comma-separated list.
    """
    raw = os.environ.get("FEDERATION_ALERT_ADMIN_CHAT_IDS", "").strip()
    if raw:
        ids = {part.strip() for part in raw.split(",") if part.strip()}
    else:
        owner = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
        ids = {owner} if owner else set()
    return frozenset(ids)


def is_admin_chat_id(chat_id: object) -> bool:
    """Return True iff chat_id is in the admin allow-list.

    Telegram chat_id may arrive as int or str; we normalize to str.
    """
    if chat_id is None:
        return False
    return str(chat_id) in admin_chat_ids()


__all__ = [
    "generate_approval_token",
    "callback_token_prefix",
    "verify_callback_token",
    "admin_chat_ids",
    "is_admin_chat_id",
]
