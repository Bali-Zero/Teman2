"""Parse inbound Meta WhatsApp webhooks for media attachments (Anello 1b, pure part).

The live-message path in ``adapter.py`` extracts only ``text``. For the intake
pipeline we need the OTHER message kinds: an inbound ``image`` or ``document``
(and, defensively, ``audio``/``video``/``sticker``) carries a ``media_id`` plus
its MIME type inside a type-named sub-object:

    {"type": "document",
     "document": {"id": "<media_id>", "mime_type": "application/pdf",
                  "filename": "passport.pdf", "sha256": "..."}}
    {"type": "image",
     "image": {"id": "<media_id>", "mime_type": "image/jpeg", "sha256": "..."}}

This module is the PURE extraction half of Anello 1b: webhook dict in →
``list[InboundMedia]`` out. It does ZERO I/O — no Meta download (that's
``media_download.download_media``), no DB enqueue (that's the DB-coupled half,
which must be tested on the Pro against nuzantara_dev). Keeping the parse pure
means the fiddly "what does a Meta media webhook actually look like" logic is
fully unit-tested on any machine.

A webhook ``value`` may also carry ``metadata.phone_number_id`` (which BALI
ZERO line received it) and ``contacts`` (sender name) — extracted here so the
DB half can record provenance and resolve the receiving team member.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Message ``type`` values that carry a downloadable media object, each nested
# under a same-named key. Order is irrelevant; membership is what matters.
_MEDIA_TYPES: tuple[str, ...] = ("image", "document", "audio", "video", "sticker")


@dataclass(frozen=True)
class InboundMedia:
    """One downloadable attachment found in an inbound webhook message.

    Attributes:
        media_id: Meta media_id to feed into ``download_media``.
        message_type: The Meta message ``type`` ("image"/"document"/...).
        mime_type: MIME Meta declared in the sub-object (may be None).
        filename: Original filename (documents only; None otherwise).
        declared_sha256: Meta's declared sha256 (may be None) — the downloader
            re-verifies it.
        wa_message_id: The ``wamid.*`` id of the carrying message (provenance,
            idempotency key for "did we already ingest this message").
        from_phone: Sender's phone number (the client).
        phone_number_id: The BALI ZERO line that RECEIVED it (provenance; maps
            to which official number → which team owner downstream).
        sender_name: Sender display name from ``contacts`` (may be None).
    """

    media_id: str
    message_type: str
    mime_type: str | None
    filename: str | None
    declared_sha256: str | None
    wa_message_id: str | None
    from_phone: str | None
    phone_number_id: str | None
    sender_name: str | None


@dataclass(frozen=True)
class ParsedWebhook:
    """All media found in one webhook POST (Meta may batch several messages)."""

    media: list[InboundMedia] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.media)


def _iter_value_blocks(raw_event: dict):
    """Yield each ``changes[].value`` block in a webhook envelope, defensively.

    Meta nests: entry[] → changes[] → value. Real payloads usually have one of
    each, but the schema allows arrays; we walk them all and skip malformed
    nodes rather than throwing (a webhook handler must never 500 on a weird
    shape — it would make Meta retry forever).
    """
    if not isinstance(raw_event, dict):
        return
    for entry in raw_event.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if isinstance(value, dict):
                yield value


def _extract_sender_name(value: dict) -> str | None:
    contacts = value.get("contacts") or []
    if contacts and isinstance(contacts[0], dict):
        profile = contacts[0].get("profile") or {}
        if isinstance(profile, dict):
            return profile.get("name")
    return None


def parse_media_webhook(raw_event: dict) -> ParsedWebhook:
    """Extract every downloadable media attachment from a Meta webhook.

    Pure: dict in, ``ParsedWebhook`` out, no I/O. Messages with no media
    (plain text, status callbacks, reactions) yield nothing. Malformed nodes
    are skipped with a debug log, never raised — the webhook endpoint must
    stay 200 so Meta doesn't enter a retry storm.

    Args:
        raw_event: The JSON body Meta POSTs to the webhook.

    Returns:
        ``ParsedWebhook`` whose ``.media`` lists one ``InboundMedia`` per
        attachment across all batched messages.
    """
    found: list[InboundMedia] = []

    for value in _iter_value_blocks(raw_event):
        metadata = value.get("metadata") or {}
        phone_number_id = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
        sender_name = _extract_sender_name(value)

        for message in value.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            mtype = message.get("type")
            if mtype not in _MEDIA_TYPES:
                continue  # text / interactive / status — not our concern here

            sub = message.get(mtype)
            if not isinstance(sub, dict):
                logger.debug("WA media message type=%s missing sub-object", mtype)
                continue

            media_id = sub.get("id")
            if not media_id:
                logger.debug("WA media message type=%s missing media id", mtype)
                continue

            found.append(
                InboundMedia(
                    media_id=str(media_id),
                    message_type=str(mtype),
                    mime_type=sub.get("mime_type"),
                    filename=sub.get("filename"),
                    declared_sha256=sub.get("sha256"),
                    wa_message_id=message.get("id"),
                    from_phone=message.get("from"),
                    phone_number_id=phone_number_id,
                    sender_name=sender_name,
                )
            )

    return ParsedWebhook(media=found)
