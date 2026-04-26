"""Tests for canva_renderer.pending_builder.

pending_builder converts WR2 `slides_json` (Council + Visual output) into
the `canva_pending.json` schema that war-room/APPLICA_WAR_ROOM.md already
knows how to apply via MCP Canva. The format has been stable since
2026-03-26 — we keep bit-for-bit compatibility.
"""

from __future__ import annotations

import pytest

from backend.services.canva_renderer.pending_builder import (
    TEMPLATE_DESIGN_ID,
    TEMPLATE_SLOTS,
    build_canva_pending,
    slides_to_operations,
)


def _slides_fixture() -> list[dict]:
    """Minimal 5-slide fixture mimicking Council+Visual output.

    `build_canva_pending` enforces a minimum of 5 slides (see
    `pending_builder.py`); the ops-level tests only inspect 1–3 but
    the payload-level tests need the full set.
    """
    return [
        {
            "slide_number": 1,
            "headline": "BALI HAS A NEW IMMIGRATION TASK FORCE.",
            "body": "100 officers. Body cameras. Your address is already on their map.",
            "image_url": "https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/slide_01.jpg",
            "is_cover": True,
            "is_hero_image": True,
        },
        {
            "slide_number": 2,
            "headline": "WHAT IS DHARMA DEWATA?\nNOT A TOURISM CAMPAIGN.",
            "body": "Inaugurated April 15, 2026 by the DGI.",
            "image_url": "https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/slide_02.jpg",
            "is_hero_image": True,
        },
        {
            "slide_number": 3,
            "headline": "WHERE THEY ARE OPERATING.",
            "body": "Canggu, Seminyak, Kerobokan, Ubud, Kuta, Benoa.",
            "image_url": None,  # not every slide has an image
        },
        {
            "slide_number": 4,
            "headline": "WHAT THIS MEANS FOR YOU.",
            "body": "If your visa is expiring, act now.",
            "image_url": None,
        },
        {
            "slide_number": 5,
            "headline": "WHAT TO DO NEXT.",
            "body": "Book a consultation with Bali Zero today.",
            "image_url": None,
        },
    ]


class TestSlidesToOperations:
    def test_replace_text_on_heading_uses_mapped_element_id(self) -> None:
        ops = slides_to_operations(_slides_fixture())
        slide_1_heading_ops = [
            op for op in ops
            if op["type"] == "replace_text"
            and op["page_index"] == 1
            and op["element_id"] == TEMPLATE_SLOTS[0][1]  # heading slot for page 1
        ]
        assert len(slide_1_heading_ops) == 1
        assert slide_1_heading_ops[0]["text"] == "BALI HAS A NEW IMMIGRATION TASK FORCE."

    def test_body_text_goes_to_body_element_id(self) -> None:
        ops = slides_to_operations(_slides_fixture())
        page_1_body_slot = TEMPLATE_SLOTS[0][2]  # body element id for page 1
        body_ops = [
            op for op in ops
            if op["type"] == "replace_text"
            and op["element_id"] == page_1_body_slot
        ]
        assert len(body_ops) == 1
        assert "100 officers" in body_ops[0]["text"]

    def test_image_url_produces_upload_asset_op(self) -> None:
        ops = slides_to_operations(_slides_fixture())
        upload_ops = [op for op in ops if op["type"] == "upload-asset-from-url"]
        assert len(upload_ops) == 2  # slides 1 and 2 have images, slide 3 does not
        assert all(
            op["url"].startswith(
                "https://nuzantara-warroom-images.fly.storage.tigris.dev/",
            )
            for op in upload_ops
        )

    def test_slide_without_image_omits_upload_op(self) -> None:
        ops = slides_to_operations(_slides_fixture())
        page_3_upload_ops = [
            op for op in ops
            if op["type"] == "upload-asset-from-url" and op["page_index"] == 3
        ]
        assert page_3_upload_ops == []

    def test_slide_9_and_11_body_skipped(self) -> None:
        """Slides 9 and 11 have no body slot in template DAHE6lx1lf8 —
        builder must not emit body replace_text for them."""
        slides = [
            {
                "slide_number": 9,
                "headline": "ENFORCEMENT IS NOT THEORETICAL.",
                "body": "this body should be skipped because slot is absent",
                "image_url": None,
            },
            {
                "slide_number": 11,
                "headline": "KNOW YOUR CLOCK.",
                "body": "also skipped",
                "image_url": None,
            },
        ]
        ops = slides_to_operations(slides)

        # Heading replace_text for both slides still present
        heading_ops = [op for op in ops if op["type"] == "replace_text"]
        assert len(heading_ops) == 2

        # No body ops for page 9 or 11
        for op in heading_ops:
            page_idx = op["page_index"]
            slot = TEMPLATE_SLOTS[page_idx - 1]
            assert slot[2] is None or op["element_id"] == slot[1], (
                f"page {page_idx} should only have heading ops, not body"
            )


class TestBuildCanvaPending:
    def test_full_payload_has_required_top_level_fields(self) -> None:
        payload = build_canva_pending(
            topic="Bali's New Immigration Task Force: Unseen Risks for Expats",
            tone="pedagogico",
            slides=_slides_fixture(),
        )
        assert payload["template_design_id"] == TEMPLATE_DESIGN_ID
        assert payload["topic"] == "Bali's New Immigration Task Force: Unseen Risks for Expats"
        assert payload["tone"] == "pedagogico"
        assert payload["slides_count"] == 5
        assert isinstance(payload["operations"], list)
        assert len(payload["operations"]) > 0
        assert payload["design_id"] is None  # not yet applied
        assert payload["design_url"] is None

    def test_round_trips_exact_schema_fields_used_by_applica_runbook(self) -> None:
        """APPLICA_WAR_ROOM.md reads these fields by name — regression guard."""
        payload = build_canva_pending(
            topic="x",
            tone="pedagogico",
            slides=_slides_fixture(),
        )
        expected_keys = {
            "template_design_id",
            "folder_id",
            "design_id",
            "design_url",
            "topic",
            "tone",
            "page_index",
            "slides_count",
            "operations_count",
            "operations",
            "slides",
        }
        assert expected_keys.issubset(payload.keys())

    def test_rejects_invalid_tone(self) -> None:
        with pytest.raises(ValueError, match="tone must be one of"):
            build_canva_pending(
                topic="x",
                tone="cinico",  # removed from WR2 register set
                slides=_slides_fixture(),
            )

    def test_rejects_empty_slides(self) -> None:
        with pytest.raises(ValueError, match="slides cannot be empty"):
            build_canva_pending(topic="x", tone="pedagogico", slides=[])

    def test_rejects_more_than_max_slides(self) -> None:
        # MAX_SLIDES_REQUESTED is 13 in pending_builder.py; over that the
        # draft generator is told it produced too many slides.
        slides = [{"slide_number": i, "headline": f"s{i}"} for i in range(1, 15)]
        with pytest.raises(ValueError, match="cannot exceed 13 slides"):
            build_canva_pending(topic="x", tone="pedagogico", slides=slides)
