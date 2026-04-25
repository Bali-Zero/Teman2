"""Build canva_pending.json from WR2 slides_json.

Format is the one consumed by the APPLICA_WAR_ROOM.md runbook (shipped
alongside claude_invoker.py at runbooks/APPLICA_WAR_ROOM.md). The
Council decides tone + structure, the Visual service produces images,
and this module composes the operations array using stable element IDs
of template DAHE6lx1lf8.

Historical note: the legacy WR1 pipeline (apps/war-room/, removed
2026-04-22) used to emit this same schema from a bash-composed
06_canva_builder.py agent. The format is preserved verbatim so any
archived canva_pending.json remains replayable.
"""

from __future__ import annotations

from typing import Any

# Master carousel template. See runbooks/APPLICA_WAR_ROOM.md.
TEMPLATE_DESIGN_ID = "DAHE6lx1lf8"
CAROUSEL_FOLDER_ID = "FAHEwkTYduI"

# Legibility Armor gradient overlay — 4:5 PNG with strong dark at top (heading
# zone) + strong dark at bottom (body zone), transparent middle. Placed by the
# /canva-apply skill on top of hero images during the apply transaction so the
# League Spartan / Montserrat white text stays readable regardless of what
# Gemini Nano Banana 2 Pro generated for that slide.
# Regenerate locally with scripts/generate_legibility_armor.py and re-upload
# to bump the version; update URL here to invalidate cache.
LEGIBILITY_ARMOR_URL = (
    "https://nuzantara-warroom-images.fly.storage.tigris.dev/"
    "warroom/template-assets/legibility-armor-gradient-v1.png"
)

# (page_index, heading_element_id, body_element_id_or_None)
# Recovered 2026-03-26 via start-editing-transaction, re-confirmed 2026-04-22.
# Pages 9 and 11 have image+heading only — no body slot in the template.
TEMPLATE_SLOTS: list[tuple[int, str, str | None]] = [
    (1, "PB6Rxs8n5DZkNS9Z-LB7Ms2Np5mWMHmSS", "PB6Rxs8n5DZkNS9Z-LBKpxy8Y8VM8g5sm"),
    (2, "PBRnkF5C2FHvWPPp-LBwYVgC9yVwkqB5w", "PBRnkF5C2FHvWPPp-LBSxs84s03skX2bJ"),
    (3, "PBswT8p6LMg6vyX4-LBZ0XDG56kG2Vclt", "PBswT8p6LMg6vyX4-LBR7pfgBKZYHQxLJ"),
    (4, "PB9rgJ5tQj1yNJrD-LBtDrMM3Bp4nJ4v9", "PB9rgJ5tQj1yNJrD-LBGHjSsS3lj7VY3Z"),
    (5, "PBZjXPTPh9tnvx82-LBSZHpqHtJfq43QC", "PBZjXPTPh9tnvx82-LB9q34XMJhYmJcVV"),
    (6, "PBgr2GbZD3DJkPP0-LB0cZMDY3BRdprNk", "PBgr2GbZD3DJkPP0-LB1kPFcPYqsqQYfQ"),
    (7, "PBk1XphW0PnpKMh2-LBbh37qB3S4DrdrD", "PBk1XphW0PnpKMh2-LB2XL6f0tjmwhgk8"),
    (8, "PBNffcgkNpZKTtmM-LBqZPxQl4n18fr93", "PBNffcgkNpZKTtmM-LBY2F75l9NJp4bpf"),
    (9, "PBqdbS4QcwHgGN0F-LBxNXD1BhmjjkJfc", None),
    (10, "PBz4hjP71RbnjKhb-LBbCpkK9wH5C1KQX", "PBz4hjP71RbnjKhb-LBTVJsF8WVLZBx8L"),
    (11, "PBxns7m6jJJm3BKT-LBtXZ6mvNj5TH3n0", None),
]

# Image element IDs per page — None means APPLICA runbook retrieves ID
# dynamically via start-editing-transaction (see step 2 of the runbook).
IMAGE_ELEMENT_IDS: dict[int, str | None] = {
    1: "PB6Rxs8n5DZkNS9Z-LBHqK4g0FxbCCC2M",
    2: None,
    3: "PBswT8p6LMg6vyX4-LBxWhDcGyymfN9lK",
    4: "PB9rgJ5tQj1yNJrD-LBtpL9tDPBgSywD2",
    5: None,
    6: "PBgr2GbZD3DJkPP0-LB95B2ZrsbxVqpQL",
    7: None,
    8: None,
    9: "PBqdbS4QcwHgGN0F-LBzTLpBTRhdtwgRX",
    10: None,
    11: None,
}

# WR2 Council register set (design doc §3.2). WR1 toni legacy
# ("cinico", "istituzionale_severo") are rejected — see Council hard rules.
VALID_TONES = frozenset({
    "rituale",
    "analitico",
    "ironico",
    "militante",
    "pedagogico",
    "poetico",
    "tecnico",
})

# Template DAHE6lx1lf8 has exactly 11 pages. Carousels SHORTER than 11 use the
# first N pages; the apply skill resets (wipes) the unused pages to blank so
# the Canva duplicate in the output folder only exposes N slides when a user
# views it (Canva engine still renders all 11 internally, but blank pages are
# visually absorbed by the Instagram reader which auto-crops trailing empties).
# For `deep` tier requesting 12-13 slides: clamp to 11 (hard limit of template).
MIN_SLIDES = 5
MAX_SLIDES = 11
MAX_SLIDES_REQUESTED = 13  # what the draft generator is allowed to output
MAX_SLIDES_TEMPLATE = 11  # hard cap of DAHE6lx1lf8 template


def slides_to_operations(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Emit the ops array consumed by MCP Canva perform-editing-operations.

    Each slide contributes:
    - 1 replace_text for the heading slot
    - 1 replace_text for the body slot (if the template has one at that page
      AND the slide carries body text)
    - 1 upload-asset-from-url for the image slot (only for hero slides where
      `is_hero_image=True` and `image_url` is non-empty)

    Slides are clamped to MAX_SLIDES_TEMPLATE. Missing text slots in the
    template (pages 9, 11 have no body slot) skip the body op. Non-hero
    slides do NOT trigger image ops — they keep the template's static
    Text-as-Art / typography design.
    """
    operations: list[dict[str, Any]] = []
    for slide in slides[:MAX_SLIDES_TEMPLATE]:
        page_index = slide["slide_number"]
        # TEMPLATE_SLOTS is 0-indexed list matching 1-indexed page_index
        if page_index < 1 or page_index > MAX_SLIDES_TEMPLATE:
            continue
        _, heading_eid, body_eid = TEMPLATE_SLOTS[page_index - 1]

        # Heading always goes on its dedicated element
        headline = slide.get("headline", "").strip()
        if headline:
            operations.append({
                "type": "replace_text",
                "element_id": heading_eid,
                "text": headline,
                "page_index": page_index,
            })

        # Body — optionally extended with the image_prompt when the slide
        # doesn't ship a generated image. The editor sees the prompt inline in
        # Canva and can copy-paste it into their image generator of choice
        # (Midjourney / DALL-E / Canva AI / Firefly). See wr2-carousel-pipeline
        # design doc §7.
        body = (slide.get("body") or "").strip()
        image_url = slide.get("image_url")
        image_prompt = (slide.get("image_prompt") or "").strip()

        if not image_url and image_prompt:
            if slide.get("is_cover"):
                # Cover without a generated image: mark as "to generate by hand"
                marker = "\n\n🖼️⚠️ [COVER DA GENERARE A MANO]\n"
            else:
                marker = "\n\n📸 [PROMPT IMMAGINE]\n"
            body = f"{body}{marker}{image_prompt}" if body else f"{marker.lstrip()}{image_prompt}"

        if body and body_eid:
            operations.append({
                "type": "replace_text",
                "element_id": body_eid,
                "text": body,
                "page_index": page_index,
            })

        # Image upload ONLY for hero slides with a real URL. Non-hero slides
        # keep the template's Text-as-Art design (no image, just typography).
        is_hero = bool(slide.get("is_hero_image"))
        image_url = slide.get("image_url")
        if is_hero and image_url:
            image_eid = IMAGE_ELEMENT_IDS.get(page_index)
            op: dict[str, Any] = {
                "type": "upload-asset-from-url",
                "url": image_url,
                "page_index": page_index,
                "element_id": image_eid,
                "placement": (
                    "full_bleed_background_with_text_overlay_bottom_third"
                    if page_index == 1
                    else "full_bleed_with_legibility_armor_gradient"
                ),
            }
            if image_eid is None:
                op["_note"] = (
                    f"element_id unknown for hero page {page_index} "
                    "— retrieve from start-editing-transaction in /canva-apply"
                )
            operations.append(op)

            # Overlay gradient for legibility. The apply skill inserts this as
            # a NEW fill on top of the hero image (not replacing an existing
            # element) — positioned to cover the full page, BELOW the text
            # boxes but ABOVE the image placeholder. Opacity baked into the PNG.
            operations.append({
                "type": "insert-overlay-from-url",
                "url": LEGIBILITY_ARMOR_URL,
                "page_index": page_index,
                "z_order": "above_image_below_text",
                "opacity": 1.0,
                "placement": "full_bleed",
                "_note": (
                    "Legibility armor gradient — ensures white text on dark "
                    "top/bottom zones regardless of hero image luminance. "
                    "Apply skill should insert_fill on page with this asset "
                    "at 0<left<page_width, 0<top<page_height, spanning full."
                ),
            })

    return operations


def build_canva_pending(
    *,
    topic: str,
    tone: str,
    slides: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the full canva_pending.json payload from WR2 draft data.

    Accepts variable-length carousels (5-13 slides as produced by the WR2
    draft generator with content tiers breaking/explainer/deep).
    Slides beyond MAX_SLIDES_TEMPLATE (11) are clamped with a warning.

    Schema matches the one APPLICA_WAR_ROOM.md (shipped in runbooks/)
    expects: a dict with keys template_design_id, folder_id, topic, tone,
    slides, slides_count, operations.
    """
    if tone not in VALID_TONES:
        raise ValueError(
            f"tone must be one of {sorted(VALID_TONES)}, got {tone!r}. "
            "WR1 tones 'cinico' / 'istituzionale_severo' are removed in WR2.",
        )
    if not slides:
        raise ValueError("slides cannot be empty")
    if len(slides) < MIN_SLIDES:
        raise ValueError(f"need at least {MIN_SLIDES} slides, got {len(slides)}")
    if len(slides) > MAX_SLIDES_REQUESTED:
        raise ValueError(
            f"cannot exceed {MAX_SLIDES_REQUESTED} slides (draft generator "
            f"hard cap), got {len(slides)}",
        )

    # Template holds only MAX_SLIDES_TEMPLATE pages — clamp if needed
    effective_slides = slides[:MAX_SLIDES_TEMPLATE]
    if len(slides) > MAX_SLIDES_TEMPLATE:
        # Bubble up the fact we dropped slides so the apply skill knows
        pass  # handled in the dict below

    operations = slides_to_operations(effective_slides)
    hero_slides_used = [s["slide_number"] for s in effective_slides if s.get("is_hero_image")]

    return {
        "template_design_id": TEMPLATE_DESIGN_ID,
        "folder_id": CAROUSEL_FOLDER_ID,
        "design_id": None,
        "design_url": None,
        "topic": topic,
        "tone": tone,
        "content_tier": _infer_tier(len(slides)),
        "page_index": 0,
        "slides_count": len(effective_slides),
        "slides_requested": len(slides),
        "slides_dropped": max(0, len(slides) - MAX_SLIDES_TEMPLATE),
        "hero_slide_indices": hero_slides_used,
        "operations_count": len(operations),
        "operations": operations,
        "slides": effective_slides,  # passed through for APPLICA STEP 3 editorial pass
    }


def _infer_tier(n_slides: int) -> str:
    if n_slides <= 7:
        return "breaking"
    if n_slides <= 10:
        return "explainer"
    return "deep"
