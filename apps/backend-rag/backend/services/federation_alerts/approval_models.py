"""Callback schema for FAD Telegram approval gate.

Format (max 64 bytes — Telegram callback_data limit):

    fad:<action>:<proposal_id>:<token8>

Where:
    action       in {"approve", "reject", "defer", "mode"}
    proposal_id  UUID4 string (36 chars) for non-mode actions
                 OR a target FederationAlertMode value for action=mode
    token8       8 hex chars (HMAC prefix from approval_token)

The "mode" action is special: it sets a new federation_alert_mode in
system_settings. ``proposal_id`` carries the target mode literal
(e.g. ``fad:mode:dry_action:t9z8y7w6``). The token is HMACed against
the literal "mode:<target_mode>" instead of a real proposal_id so
admins can change mode without going through the proposal SM.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.services.federation_alerts.models import FederationAlertMode

_PREFIX = "fad"


@dataclass(frozen=True)
class FADCallback:
    """Parsed fad:* callback payload."""

    action: str           # "approve" | "reject" | "defer" | "mode"
    target: str           # proposal_id, or mode literal when action=="mode"
    token_prefix: str     # 8 hex chars

    def is_mode_change(self) -> bool:
        return self.action == "mode"

    def is_approval(self) -> bool:
        return self.action in {"approve", "reject", "defer"}


def encode_callback(action: str, target: str, token_prefix: str) -> str:
    """Encode a callback. Caller is responsible for validating action."""
    if action not in {"approve", "reject", "defer", "mode"}:
        raise ValueError(f"unknown FAD action: {action}")
    if action == "mode" and target not in {m.value for m in FederationAlertMode}:
        raise ValueError(f"unknown target mode: {target}")
    if len(token_prefix) != 8:
        raise ValueError("token_prefix must be 8 hex chars")
    candidate = f"{_PREFIX}:{action}:{target}:{token_prefix}"
    if len(candidate.encode("utf-8")) > 64:
        raise ValueError(
            f"callback exceeds Telegram 64-byte limit: {len(candidate)}"
        )
    return candidate


def decode_callback(callback_data: str) -> FADCallback | None:
    """Parse fad:* callback. Returns None on malformed input.

    Defensive against malicious/truncated input — caller treats None
    as "drop callback silently".
    """
    if not callback_data.startswith(f"{_PREFIX}:"):
        return None
    parts = callback_data.split(":")
    if len(parts) != 4:
        return None
    _, action, target, token_prefix = parts
    if action not in {"approve", "reject", "defer", "mode"}:
        return None
    if not target:
        return None
    if len(token_prefix) != 8:
        return None
    # Reject non-hex token prefixes early (defense in depth)
    try:
        int(token_prefix, 16)
    except ValueError:
        return None
    if action == "mode" and target not in {m.value for m in FederationAlertMode}:
        return None
    return FADCallback(action=action, target=target, token_prefix=token_prefix)


__all__ = ["FADCallback", "encode_callback", "decode_callback"]
