"""Tests for canva_renderer.pending_builder.

pending_builder converts WR2 `slides_json` (Council + Visual output) into
the `canva_pending.json` schema that war-room/APPLICA_WAR_ROOM.md already
knows how to apply via MCP Canva. The format has been stable since
2026-03-26 — we keep bit-for-bit compatibility.
"""

from __future__ import annotations

import re

import pytest

from backend.services.canva_renderer.pending_builder import (
    CAROUSEL_FOLDER_ID,
    MAX_SLIDES_TEMPLATE,
    TEMPLATE_DESIGN_ID,
    build_canva_pending,
    slides_to_operations,
)


# Canva design ID format: 11 chars, starts with "DAH", URL-safe alphabet.
# Folder ID format: same shape but starts with "FAH".
_DESIGN_ID_RE = re.compile(r"^DAH[A-Za-z0-9_-]{8}$")
_FOLDER_ID_RE = re.compile(r"^FAH[A-Za-z0-9_-]{8}$")


class TestTemplateConstants:
    """Guards on the template constants — flag misformatted IDs in CI.

    These tests catch the *shape* of the Canva ID strings; they cannot
    verify the live design exists or has the right structure (that
    requires a Canva MCP round-trip and is gated behind
    `scripts/wr2_validate_master.py`). See cicatrix scar
    "WR2 master template requires verified richtext slot count
    (2026-05-10)" for the broader context: PR #565 promoted a
    structurally-incompatible master that passed every CI check
    because no test exercised the live shape.
    """

    def test_template_design_id_format(self) -> None:
        assert _DESIGN_ID_RE.match(TEMPLATE_DESIGN_ID), (
            f"TEMPLATE_DESIGN_ID={TEMPLATE_DESIGN_ID!r} does not match "
            f"the Canva design ID format {_DESIGN_ID_RE.pattern!r}. "
            "Bumping this constant requires running "
            "scripts/wr2_validate_master.py and pasting the JSON "
            "output in the PR description — see "
            "cicatrix-scars.md (2026-05-10 entry)."
        )

    def test_carousel_folder_id_format(self) -> None:
        assert _FOLDER_ID_RE.match(CAROUSEL_FOLDER_ID), (
            f"CAROUSEL_FOLDER_ID={CAROUSEL_FOLDER_ID!r} does not match "
            f"the Canva folder ID format {_FOLDER_ID_RE.pattern!r}."
        )

    def test_max_slides_template_invariant(self) -> None:
        # The renderer (pending_builder) clamps to MAX_SLIDES_TEMPLATE.
        # If a future contributor bumps it, they must also re-validate
        # that the master template at TEMPLATE_DESIGN_ID actually has
        # that many usable pages. Pin the value as a tripwire.
        assert MAX_SLIDES_TEMPLATE == 11, (
            "MAX_SLIDES_TEMPLATE was changed. Re-run "
            "scripts/wr2_validate_master.py to verify the master "
            "still has at least this many usable pages."
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

    def test_body_text_emitted_even_when_body_eid_is_none(self) -> None:
        # TEMPLATE_SLOTS has None for all body slots in the live template.
        # The builder MUST still emit the body op (element_id=None) so the
        # canva-apply skill can remap to the body slot via top-ascending
        # role_index. Skipping body ops produces the headline-only carousel
        # bug observed in DAHJDtWApaw / DAHJCzTzn1I (2026-05-08).
        ops = slides_to_operations(_slides_fixture())
        body_ops = [
            op for op in ops
            if op["type"] == "replace_text"
            and "100 officers" in (op.get("text") or "")
        ]
        assert len(body_ops) == 1
        assert body_ops[0]["element_id"] is None
        assert body_ops[0]["page_index"] == 1

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

    def test_body_ops_emitted_for_slides_9_and_11(self) -> None:
        """Slides 9/11 have no body slot in the original template, but
        TEMPLATE_SLOTS is now None-filled across all pages. The builder
        emits body ops uniformly (element_id=None); the canva-apply
        skill is responsible for resolving — or skipping — the body
        slot at apply time via runtime remap. Builder MUST NOT make
        per-page exceptions, otherwise the headline-only-carousel
        regression returns whenever template page geometry changes."""
        slides = [
            {
                "slide_number": 9,
                "headline": "ENFORCEMENT IS NOT THEORETICAL.",
                "body": "body text reaches Canva — skill decides if slot exists",
                "image_url": None,
            },
            {
                "slide_number": 11,
                "headline": "KNOW YOUR CLOCK.",
                "body": "same here — apply skill remaps via role_index",
                "image_url": None,
            },
        ]
        ops = slides_to_operations(slides)

        replace_ops = [op for op in ops if op["type"] == "replace_text"]
        # 2 heading ops + 2 body ops, one of each per slide
        assert len(replace_ops) == 4

        for page_index in (9, 11):
            page_ops = [op for op in replace_ops if op["page_index"] == page_index]
            assert len(page_ops) == 2, (
                f"page {page_index} must have heading + body ops"
            )
            # All element_ids are None because TEMPLATE_SLOTS is None-filled
            assert all(op["element_id"] is None for op in page_ops)


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
