"""Builds Meta-shaped webhook payloads (WhatsApp + Instagram).

Payload SHAPES match the pydantic models the live routers validate against
(``WhatsAppWebhook`` in ``backend.app.routers.whatsapp_chat``,
``InstagramWebhook`` in ``backend.app.routers.instagram_chat``) — kept in
sync BY HAND, deliberately not by importing those models here. Importing
them would let a shape drift in this harness silently follow a shape drift
in the router; a hand-authored shape that the router's own pydantic
validation accepts is the actual proof the harness payloads are realistic.

Two ways to get a payload:

1. ``whatsapp_text_payload(...)`` etc. — parametrized builders, for tests
   that need a specific message id / phone / text.
2. ``load_static_payload("whatsapp_text.json")`` — the checked-in
   ``payloads/*.json`` fixtures (research capture §5.2 layout), returned as
   the file's exact on-disk bytes. Use these when the test cares about a
   stable, reviewable fixture rather than a fresh id per call.

``to_raw_body`` is the ONE place a dict becomes wire bytes in this harness.
Call it once per payload and pass the resulting bytes through unchanged —
``webhook_signer.sign_payload`` and ``replay.WebhookReplayer`` both take
bytes, never a dict, so there is no second serialization step anywhere
downstream that could produce a different byte stream than the one that
was signed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PAYLOADS_DIR = Path(__file__).parent / "payloads"

DEFAULT_PHONE_NUMBER_ID = "100000000000001"
DEFAULT_WABA_PHONE = "6281234567890"
DEFAULT_IG_PAGE_ID = "ig_page_1"


def whatsapp_text_payload(
    *,
    message_id: str = "wamid.HARNESS_DEFAULT",
    phone: str = DEFAULT_WABA_PHONE,
    text: str = "Hello",
    phone_number_id: str = DEFAULT_PHONE_NUMBER_ID,
) -> dict[str, Any]:
    """A single inbound text message, WhatsApp Cloud API shape."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": phone,
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Harness Test User"}, "wa_id": phone}
                            ],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": message_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def whatsapp_image_payload(
    *,
    message_id: str = "wamid.HARNESS_IMAGE",
    phone: str = DEFAULT_WABA_PHONE,
    media_id: str = "media_harness_1",
    phone_number_id: str = DEFAULT_PHONE_NUMBER_ID,
) -> dict[str, Any]:
    """An attachment-only inbound message — one of the required golden
    classes in the research capture §5.1 ("Attachment-only message").
    """
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": phone,
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Harness Test User"}, "wa_id": phone}
                            ],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": message_id,
                                    "timestamp": "1700000100",
                                    "type": "image",
                                    "image": {"id": media_id, "mime_type": "image/jpeg"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def whatsapp_status_payload(
    *,
    message_id: str = "wamid.HARNESS_STATUS",
    status: str = "delivered",
    phone_number_id: str = DEFAULT_PHONE_NUMBER_ID,
) -> dict[str, Any]:
    """A delivery-receipt change — ``field="statuses"``, not ``"messages"``.

    Used to prove the router's ``change.field != "messages"`` filter skips
    it cleanly (no persist, no background task) rather than crashing on the
    different value shape under that field.
    """
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "field": "statuses",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": phone_number_id},
                            "statuses": [
                                {
                                    "id": message_id,
                                    "status": status,
                                    "timestamp": "1700000200",
                                    "recipient_id": DEFAULT_WABA_PHONE,
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def instagram_dm_payload(
    *,
    mid: str = "ig_mid_harness_1",
    sender_id: str = "ig_user_1",
    text: str = "Hello from Instagram",
    page_id: str = DEFAULT_IG_PAGE_ID,
) -> dict[str, Any]:
    """A single inbound Instagram DM, Messenger-platform-shaped."""
    return {
        "object": "instagram",
        "entry": [
            {
                "id": page_id,
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": sender_id},
                        "recipient": {"id": page_id},
                        "timestamp": 1700000000,
                        "message": {"mid": mid, "text": text, "is_echo": False},
                    }
                ],
            }
        ],
    }


def to_raw_body(payload: dict[str, Any]) -> bytes:
    """Serialize a payload dict to canonical UTF-8 JSON bytes.

    Call this exactly once per payload and thread the returned bytes
    through unchanged. Calling ``json.dumps`` a second time on the "same"
    payload is not guaranteed to produce the same bytes (dict ordering is
    insertion-order-stable within one process but nothing here promises
    stability ACROSS two independent ``dict`` constructions), and a
    signature computed over one dumps() call will not verify against bytes
    from a different one — that mismatch is precisely
    ``test_signature_over_reserialized_json_body_does_not_match``.
    """
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def load_static_payload(name: str) -> bytes:
    """Load one of the checked-in ``payloads/*.json`` fixtures as raw bytes.

    Returns the file's exact on-disk bytes (not a re-encoded round-trip
    through ``json.load`` + ``json.dumps``) — signing these bytes and
    signing a round-tripped copy are two different byte streams whenever
    the file's on-disk formatting (indentation, trailing newline) differs
    from ``json.dumps``'s compact output, which it deliberately does here
    (the files are pretty-printed for human review).
    """
    path = PAYLOADS_DIR / name
    return path.read_bytes()
