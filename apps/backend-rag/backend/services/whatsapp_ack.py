"""Concierge ack for slow WhatsApp replies.

The OpenClaw bridge takes ~10s on a trivial message and 20-50s on a
priced/reasoned consultation answer (latency dominated by inference +
PricingTool round-trips, worse when the Pro is under load). On WhatsApp
that silence reads as "nobody is there". This module sends ONE short
"got it, checking" message right after triage, before the slow path —
only when the question looks non-trivial, throttled per phone.

Decision requested by Antonello 2026-06-11 (lever C of
research/operations/2026-06-08-zantara-wa-latency-routing-spec.md).

Kill-switch: WHATSAPP_ACK_ENABLED=false (default enabled).
"""

from __future__ import annotations

import os
import re
import time

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Messages shorter than this are greetings/acks/one-worders: their replies
# are the fast(er) path and a pre-message would just double the bubbles.
_MIN_CHARS_FOR_ACK = 25

# Pure pleasantries — never ack these regardless of length.
_TRIVIAL_RE = re.compile(
    r"^\s*(hi|hello|hey|halo|hai|ciao|salve|ok(ay)?|oke|sip|thanks?|thank you|"
    r"makasih|terima kasih|grazie|mille grazie|spasibo|спасибо|привет|"
    r"good (morning|afternoon|evening)|selamat (pagi|siang|sore|malam)|"
    r"yes|no|ya|iya|tidak|si|sì|bye|sampai jumpa)[\s!.,🙏👍]*$",
    re.IGNORECASE,
)

# One ack per phone per window — a back-and-forth consultation should not
# get a robotic "checking…" before every single answer.
_ACK_THROTTLE_SECONDS = int(os.getenv("WHATSAPP_ACK_THROTTLE_SECONDS", "120"))
_last_ack_at: dict[str, float] = {}

_ACK_TEXTS = {
    "en": "Got it — let me check this properly for you. One moment 🙏",
    "id": "Siap, saya cek dulu ya — sebentar 🙏",
    "it": "Ricevuto — verifico e ti rispondo tra un momento 🙏",
    "ru": "Принято — сейчас уточню и отвечу через минуту 🙏",
    "fr": "Bien reçu — je vérifie et je reviens vers vous dans un instant 🙏",
}


def ack_enabled() -> bool:
    return os.getenv("WHATSAPP_ACK_ENABLED", "true").strip().lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


def ack_text(detected_language: str | None) -> str:
    return _ACK_TEXTS.get((detected_language or "en").lower(), _ACK_TEXTS["en"])


def should_send_ack(
    message_text: str,
    phone: str,
    *,
    now: float | None = None,
) -> bool:
    """True when the message warrants a "checking…" pre-message.

    Skips: kill-switch off, trivial/short messages (fast path), and phones
    acked within the throttle window.
    """
    if not ack_enabled():
        return False
    text = (message_text or "").strip()
    if len(text) < _MIN_CHARS_FOR_ACK:
        return False
    if _TRIVIAL_RE.match(text):
        return False
    ts = now if now is not None else time.time()
    last = _last_ack_at.get(phone)
    if last is not None and (ts - last) < _ACK_THROTTLE_SECONDS:
        return False
    return True


def mark_acked(phone: str, *, now: float | None = None) -> None:
    _last_ack_at[phone] = now if now is not None else time.time()
    # Bounded memory: drop oldest entries past 5k phones.
    if len(_last_ack_at) > 5000:
        for stale in sorted(_last_ack_at, key=_last_ack_at.get)[:1000]:
            _last_ack_at.pop(stale, None)


def _reset_for_testing() -> None:
    _last_ack_at.clear()
