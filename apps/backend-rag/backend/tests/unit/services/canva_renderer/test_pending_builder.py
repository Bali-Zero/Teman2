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
            and op.get("text") == "BALI HAS A NEW IMMIGRATION TASK FORCE."
        ]
        assert len(slide_1_heading_ops) == 1
        # In current TEMPLATE_SLOTS, element_id is None
        assert slide_1_heading_ops[0]["element_id"] is None

    def test_body_text_emitted_for_non_cover_slide_with_element_id_none(self) -> None:
        """SP-2 fix (cross-LLM brainstorm 2026-05-08): body ops MUST be emitted
        for non-cover slides even when element_id is None. The /canva-apply
        skill (lines 50-53) resolves heading vs body via per-page replace_text
        op order at runtime — first op = role 0 (heading), second op = role 1
        (body). If the builder drops body ops because body_eid is None, the
        skill never gets a chance to resolve them and the carousel ships with
        empty body slots (Badung Horeka run 2026-05-08, 7/11 slides empty).
        """
        ops = slides_to_operations(_slides_fixture())

        # Page 2 has headline + body, is_cover defaults to False → 2 ops in order
        page_2_ops = [
            op for op in ops
            if op["page_index"] == 2 and op["type"] == "replace_text"
        ]
        assert len(page_2_ops) == 2, (
            f"page 2 must emit headline + body ops, got {len(page_2_ops)}: {page_2_ops}"
        )
        assert page_2_ops[0]["text"] == (
            "WHAT IS DHARMA DEWATA?\nNOT A TOURISM CAMPAIGN."
        )
        assert page_2_ops[1]["text"] == "Inaugurated April 15, 2026 by the DGI."
        assert all(op["element_id"] is None for op in page_2_ops)

    def test_cover_slide_has_no_body_op(self) -> None:
        """Cover slides (is_cover=True) stay headline-only by design.
        The cover layout has no body slot in template DAHE6lx1lf8 page 1."""
        ops = slides_to_operations(_slides_fixture())
        page_1_ops = [
            op for op in ops
            if op["page_index"] == 1 and op["type"] == "replace_text"
        ]
        assert len(page_1_ops) == 1, (
            f"page 1 (cover) must have only headline op, got {page_1_ops}"
        )
        assert page_1_ops[0]["text"] == "BALI HAS A NEW IMMIGRATION TASK FORCE."

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

    def test_body_ops_always_emitted_for_non_cover_slides(self) -> None:
        """Builder must emit body replace_text ops for every non-cover slide
        with body text. The /canva-apply skill drops body ops at runtime
        with `🪂 dropped op: no role match on page N` if the live template
        page has no body slot (e.g. pages 9, 11 of DAHE6lx1lf8) — the
        builder cannot know the live slot map, so it errs on the side of
        emitting and lets the skill clamp.

        Regression contract for SP-2 fix (2026-05-08): the previous
        `if body and body_eid:` short-circuit silently dropped EVERY body
        op (since body_eid is always None post-2026-05-07 deprecation),
        producing the 7-of-11 empty-body bug observed in Badung Horeka.
        """
        slides = [
            {
                "slide_number": 9,
                "headline": "ENFORCEMENT IS NOT THEORETICAL.",
                "body": "body that the skill will drop at runtime if no body slot",
                "image_url": None,
            },
            {
                "slide_number": 11,
                "headline": "KNOW YOUR CLOCK.",
                "body": "same — emitted by builder, dropped by skill if needed",
                "image_url": None,
            },
        ]
        ops = slides_to_operations(slides)

        # Builder emits both heading + body for each (4 total replace_text ops)
        replace_text_ops = [op for op in ops if op["type"] == "replace_text"]
        assert len(replace_text_ops) == 4, (
            f"expected 2 headings + 2 bodies = 4 ops, got {len(replace_text_ops)}"
        )

        # Per-page op order: first op = heading, second op = body
        page_9_ops = [op for op in replace_text_ops if op["page_index"] == 9]
        assert len(page_9_ops) == 2
        assert page_9_ops[0]["text"] == "ENFORCEMENT IS NOT THEORETICAL."
        assert page_9_ops[1]["text"].startswith("body that the skill")

        page_11_ops = [op for op in replace_text_ops if op["page_index"] == 11]
        assert len(page_11_ops) == 2
        assert page_11_ops[0]["text"] == "KNOW YOUR CLOCK."
        assert page_11_ops[1]["text"].startswith("same")

        # All element_ids are None — skill resolves at runtime
        assert all(op["element_id"] is None for op in replace_text_ops)


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
