"""Unit tests for Anello 1b (pure part) — Meta media webhook parsing.

Runs anywhere: pure dict-in/dataclass-out, no I/O.
"""

from __future__ import annotations

from backend.channels.whatsapp.media_webhook_parse import (
    InboundMedia,
    parse_media_webhook,
)


def _envelope(messages: list[dict], *, phone_number_id="1104946272705747", contact_name="Mario Rossi") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"profile": {"name": contact_name}}],
                            "messages": messages,
                        }
                    }
                ]
            }
        ],
    }


def test_document_message_extracted():
    msg = {
        "from": "6281111111",
        "id": "wamid.AAA",
        "type": "document",
        "document": {"id": "media-doc-1", "mime_type": "application/pdf", "filename": "passport.pdf", "sha256": "abc"},
    }
    parsed = parse_media_webhook(_envelope([msg]))
    assert parsed.has_media
    assert len(parsed.media) == 1
    m = parsed.media[0]
    assert isinstance(m, InboundMedia)
    assert m.media_id == "media-doc-1"
    assert m.message_type == "document"
    assert m.mime_type == "application/pdf"
    assert m.filename == "passport.pdf"
    assert m.declared_sha256 == "abc"
    assert m.wa_message_id == "wamid.AAA"
    assert m.from_phone == "6281111111"
    assert m.phone_number_id == "1104946272705747"
    assert m.sender_name == "Mario Rossi"


def test_image_message_extracted():
    msg = {"from": "62822", "id": "wamid.IMG", "type": "image", "image": {"id": "media-img-9", "mime_type": "image/jpeg"}}
    parsed = parse_media_webhook(_envelope([msg]))
    assert len(parsed.media) == 1
    assert parsed.media[0].media_id == "media-img-9"
    assert parsed.media[0].message_type == "image"
    assert parsed.media[0].filename is None  # images have no filename


def test_text_message_yields_nothing():
    msg = {"from": "62", "id": "wamid.T", "type": "text", "text": {"body": "hello"}}
    parsed = parse_media_webhook(_envelope([msg]))
    assert not parsed.has_media
    assert parsed.media == []


def test_multiple_messages_batched():
    msgs = [
        {"from": "62", "id": "w1", "type": "text", "text": {"body": "hi"}},
        {"from": "62", "id": "w2", "type": "document", "document": {"id": "d2", "mime_type": "application/pdf"}},
        {"from": "62", "id": "w3", "type": "image", "image": {"id": "i3", "mime_type": "image/png"}},
    ]
    parsed = parse_media_webhook(_envelope(msgs))
    ids = sorted(m.media_id for m in parsed.media)
    assert ids == ["d2", "i3"]  # text skipped


def test_media_message_missing_id_is_skipped():
    msg = {"from": "62", "id": "wX", "type": "document", "document": {"mime_type": "application/pdf"}}  # no id
    parsed = parse_media_webhook(_envelope([msg]))
    assert not parsed.has_media


def test_media_type_with_missing_subobject_is_skipped():
    msg = {"from": "62", "id": "wX", "type": "image"}  # no "image" sub-object
    parsed = parse_media_webhook(_envelope([msg]))
    assert not parsed.has_media


def test_malformed_envelope_never_raises():
    # A grab-bag of broken shapes — the parser must return empty, not throw.
    for bad in [
        {},
        {"entry": None},
        {"entry": [None]},
        {"entry": [{"changes": None}]},
        {"entry": [{"changes": [None]}]},
        {"entry": [{"changes": [{"value": None}]}]},
        {"entry": [{"changes": [{"value": {"messages": None}}]}]},
        {"entry": [{"changes": [{"value": {"messages": [None]}}]}]},
        "not-a-dict",
        None,
    ]:
        parsed = parse_media_webhook(bad)  # type: ignore[arg-type]
        assert parsed.media == []


def test_audio_video_sticker_also_extracted():
    for t in ("audio", "video", "sticker"):
        msg = {"from": "62", "id": "w", "type": t, t: {"id": f"{t}-id", "mime_type": f"{t}/x"}}
        parsed = parse_media_webhook(_envelope([msg]))
        assert len(parsed.media) == 1
        assert parsed.media[0].media_id == f"{t}-id"
        assert parsed.media[0].message_type == t


def test_missing_metadata_and_contacts_tolerated():
    env = {
        "entry": [{"changes": [{"value": {
            "messages": [{"from": "62", "id": "w", "type": "document", "document": {"id": "d", "mime_type": "application/pdf"}}]
        }}]}]
    }
    parsed = parse_media_webhook(env)
    assert len(parsed.media) == 1
    assert parsed.media[0].phone_number_id is None
    assert parsed.media[0].sender_name is None
