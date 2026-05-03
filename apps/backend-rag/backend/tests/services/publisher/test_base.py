"""Tests for Publisher ABC data classes."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.services.publisher.base import (
    DraftPayload,
    Publisher,
    PublishResult,
    SlidePayload,
    ValidationResult,
)
from backend.services.war_room.models import Platform


def test_draft_payload_minimal():
    d = DraftPayload(
        draft_id=uuid4(),
        topic="B211A",
        tone_register=None,
        cover_image_url="https://x/y.png",
        main_caption="caption",
    )
    assert d.slides == []
    assert d.hashtags == []
    assert d.link_url is None


def test_slide_payload_default_caption_none():
    s = SlidePayload(slide_number=2, image_url="https://x/2.png")
    assert s.caption is None
    assert s.final_text is None


def test_publish_result_dataclass():
    r = PublishResult(
        ok=True,
        platform=Platform.INSTAGRAM,
        draft_id=uuid4(),
        post_external_id="abc",
        attempts=2,
    )
    assert r.ok is True
    assert r.platform == Platform.INSTAGRAM
    assert r.attempts == 2


def test_validation_result_builder():
    v = ValidationResult(
        ok=False,
        platform=Platform.X,
        issues=["missing caption"],
    )
    assert v.ok is False
    assert len(v.issues) == 1


def test_publisher_is_abstract():
    with pytest.raises(TypeError):
        Publisher()  # type: ignore[abstract]
