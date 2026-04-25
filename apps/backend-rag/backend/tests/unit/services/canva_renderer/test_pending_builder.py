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
    """Minimal 3-slide fixture mimicking Council+Visual output."""
    return [
        {
            "slide_number": 1,
            "headline": "BALI HAS A NEW IMMIGRATION TASK FORCE.",
            "body": "100 officers. Body cameras. Your address is already on their map.",
            "image_url": "https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/slide_01.jpg",
            "is_cover": True,
        },
        {
            "slide_number": 2,
            "headline": "WHAT IS DHARMA DEWATA?\nNOT A TOURISM CAMPAIGN.",
            "body": "Inaugurated April 15, 2026 by the DGI.",
            "image_url": "https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/slide_02.jpg",
        },
        {
            "slide_number": 3,
            "headline": "WHERE THEY ARE OPERATING.",
            "body": "Canggu, Seminyak, Kerobokan, Ubud, Kuta, Benoa.",
            "image_url": None,  # not every slide has an image
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
        assert payload["slides_count"] == 3
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
        slides = [{"slide_number": i, "headline": f"s{i}"} for i in range(1, 13)]
        with pytest.raises(ValueError, match="cannot exceed 11 slides"):
            build_canva_pending(topic="x", tone="pedagogico", slides=slides)


# ─────────────────────────────────────────────────────────────────────────────
# Image-prompt-in-body (manual generation workflow, 2026-04-24)
#
# For slides without image_url, the image_prompt is appended to the body with
# a visible marker so the human editor sees it inside Canva and can paste it
# into their image generator of choice. Cover failures get a distinct marker.
# See docs/wr2-carousel-pipeline-design.md §7.
# ─────────────────────────────────────────────────────────────────────────────


class TestImagePromptInBody:
    def test_body_slide_appends_prompt_when_no_url(self) -> None:
        slides = [
            {
                "slide_number": 1,
                "headline": "Cover",
                "body": "Cover body",
                "image_url": "https://example.com/cover.png",
                "is_cover": True,
            },
            {
                "slide_number": 2,
                "headline": "Body slide",
                "body": "Real body text.",
                "image_prompt": "Macro shot of a lontar palm leaf manuscript",
                "image_url": None,
            },
        ]
        ops = slides_to_operations(slides)
        # Find the replace_text op for page 2 body
        body_op = next(
            o for o in ops
            if o["type"] == "replace_text"
            and o["page_index"] == 2
            and o["text"].startswith("Real body text.")
        )
        assert "📸 [PROMPT IMMAGINE]" in body_op["text"]
        assert "Macro shot of a lontar palm leaf" in body_op["text"]
        # And NO upload op for page 2
        upload_ops_p2 = [
            o for o in ops if o["type"] == "upload-asset-from-url" and o["page_index"] == 2
        ]
        assert upload_ops_p2 == []

    def test_cover_without_url_uses_distinct_marker(self) -> None:
        slides = [
            {
                "slide_number": 1,
                "headline": "Cover",
                "body": "Cover body",
                "image_prompt": "Editorial scene for cover",
                "image_url": None,
                "is_cover": True,
            },
        ]
        ops = slides_to_operations(slides)
        body_op = next(o for o in ops if o["type"] == "replace_text" and o["page_index"] == 1 and "Cover body" in o["text"])
        assert "🖼️⚠️ [COVER DA GENERARE A MANO]" in body_op["text"]
        assert "Editorial scene for cover" in body_op["text"]

    def test_slide_with_image_url_does_not_append_prompt(self) -> None:
        """Backward compat: when image_url is present, body must stay clean."""
        slides = [
            {
                "slide_number": 1,
                "headline": "Cover",
                "body": "Cover body",
                "image_prompt": "this prompt must NOT leak into body",
                "image_url": "https://example.com/cover.png",
                "is_cover": True,
            },
        ]
        ops = slides_to_operations(slides)
        body_op = next(o for o in ops if o["type"] == "replace_text" and o["page_index"] == 1 and "Cover body" in o["text"])
        assert body_op["text"] == "Cover body"
        assert "PROMPT IMMAGINE" not in body_op["text"]

    def test_body_slide_without_body_but_with_prompt(self) -> None:
        """If body is empty but prompt exists, the marker becomes the body text."""
        slides = [
            {"slide_number": 1, "headline": "Cover", "body": "C", "image_url": "http://x/c.png", "is_cover": True},
            {
                "slide_number": 2,
                "headline": "Slide two head",
                "body": "",
                "image_prompt": "standalone prompt",
                "image_url": None,
            },
        ]
        ops = slides_to_operations(slides)
        # The body slot op is the one that is NOT the headline
        page2_ops = [o for o in ops if o["type"] == "replace_text" and o["page_index"] == 2]
        # We expect 2 ops on page 2: headline + body (prompt-only)
        assert len(page2_ops) == 2
        body_op = next(o for o in page2_ops if o["text"] != "Slide two head")
        assert "📸 [PROMPT IMMAGINE]" in body_op["text"]
        assert "standalone prompt" in body_op["text"]
