"""Tests for the restored IGPublisher + Tigris PNG upload.

Covers:
  (a) Legge 5 — publish() REFUSES unless approval_state == "approved".
  (c) upload_png sets ContentType="image/png".

(The CLI dry-run test (b) lives in test_wr2_ig_publish_cli.py.)
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from backend.services.publisher.base import DraftPayload, SlidePayload
from backend.services.publisher.ig_publisher import IGPublisher


def _draft(approval_state: str = "pending", slides: int = 2) -> DraftPayload:
    return DraftPayload(
        draft_id=uuid4(),
        topic="permenkumham-22-2024-kitap",
        tone_register=None,
        cover_image_url="https://tigris/cover.png",
        main_caption="Bali Zero regulatory update.",
        slides=[
            SlidePayload(slide_number=i + 1, image_url=f"https://tigris/s{i}.png")
            for i in range(slides)
        ],
        approval_state=approval_state,
    )


def _publisher() -> IGPublisher:
    # Pass creds explicitly so the test never depends on real env secrets.
    return IGPublisher(
        ig_user_id="24126743553672359",
        access_token="test-token-not-real",
        graph_base="https://graph.instagram.com/v22.0",
    )


# ── (a) Legge 5 approval gate ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_refuses_when_not_approved() -> None:
    """publish() must REFUSE (ok=False, no Meta call) when approval_state != approved."""
    pub = _publisher()
    # A network call would fail loudly; assert we never reach it by spying client.
    pub._client = MagicMock(spec=httpx.AsyncClient)

    for state in ("pending", "rejected", "", "Approved", "APPROVED", "yes"):
        result = await pub.publish(_draft(approval_state=state))
        assert result.ok is False, f"state={state!r} should be refused"
        assert "approval_state" in (result.error or ""), result.error
        assert "approved" in (result.error or "")

    # Hard proof no Meta HTTP call was attempted for the refused drafts.
    pub._client.post.assert_not_called()
    pub._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_publish_passes_gate_when_approved_then_validates() -> None:
    """When approved, publish() proceeds past the Legge-5 gate into validation.

    We do NOT mock a full happy path here (that's an integration concern); we
    only prove the gate itself no longer blocks an 'approved' draft — i.e. the
    error, if any, is NOT the approval_state refusal.
    """
    pub = _publisher()

    # Make the first Meta POST (child container) fail fast so publish() returns
    # a non-approval error — proving the gate was passed.
    async def _post(*args: object, **kwargs: object) -> httpx.Response:
        r = MagicMock(spec=httpx.Response)
        r.status_code = 400
        r.text = "stub-fail"
        r.json.return_value = {}
        return r

    client = MagicMock(spec=httpx.AsyncClient)
    client.post = _post
    pub._client = client

    result = await pub.publish(_draft(approval_state="approved"))
    assert result.ok is False
    # The failure is a create_child failure, NOT the Legge-5 approval refusal.
    assert "approval_state" not in (result.error or "")
    assert "create_child" in (result.error or "")


# ── (c) upload_png ContentType ────────────────────────────────────────


def test_upload_png_sets_image_png_content_type() -> None:
    """upload_png must put_object with ContentType='image/png' and verify via HEAD."""
    from backend.services.canva_renderer_v2 import _tigris

    captured: dict[str, object] = {}

    class _FakeS3:
        def put_object(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def head_object(self, **kwargs: object) -> dict[str, object]:
            # Mirror what Tigris returns; ContentType must match what we put.
            return {
                "ContentType": captured.get("ContentType"),
                "ContentLength": 123,
                "ETag": '"abc"',
            }

    url, key = _tigris.upload_png(
        _FakeS3(),
        b"\x89PNG\r\n\x1a\n fake png bytes",
        draft_id="draftX",
        slide_index=3,
        prefix="wr2-ig",
    )

    assert captured["ContentType"] == "image/png"
    assert captured["ACL"] == "public-read"
    assert key == "wr2-ig/draftX/03.png"
    assert url == f"https://{_tigris.PUBLIC_HOST}/wr2-ig/draftX/03.png"


def test_upload_png_raises_on_content_type_mismatch() -> None:
    """If Tigris HEAD reports a non-png ContentType, upload_png must raise."""
    from backend.services.canva_renderer_v2 import _tigris

    class _FakeS3:
        def put_object(self, **kwargs: object) -> None:
            pass

        def head_object(self, **kwargs: object) -> dict[str, object]:
            return {"ContentType": "application/octet-stream", "ContentLength": 1}

    with pytest.raises(_tigris.TigrisError, match="ContentType mismatch"):
        _tigris.upload_png(
            _FakeS3(),
            b"x",
            draft_id="d",
            slide_index=0,
        )
