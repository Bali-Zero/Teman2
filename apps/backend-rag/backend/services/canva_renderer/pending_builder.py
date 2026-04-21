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

MIN_SLIDES = 6
MAX_SLIDES = 11


def slides_to_operations(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Emit the ops array consumed by MCP Canva perform-editing-operations.

    Each slide contributes:
    - 1 replace_text for the heading slot
    - 1 replace_text for the body slot (if the template has one at that page
      AND the slide carries body text)
    - 1 upload-asset-from-url for the image slot (if image_url is provided)

    Slides are clamped to `MAX_SLIDES`. Missing slots in the template (9, 11)
    skip the body op regardless of whether the slide provides body text.
    """
    operations: list[dict[str, Any]] = []
    for slide in slides[:MAX_SLIDES]:
        page_index = slide["slide_number"]
        # TEMPLATE_SLOTS is 0-indexed list matching 1-indexed page_index
        if page_index < 1 or page_index > MAX_SLIDES:
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

        # Body only if both slot exists AND slide carries body text
        body = (slide.get("body") or "").strip()
        if body and body_eid:
            operations.append({
                "type": "replace_text",
                "element_id": body_eid,
                "text": body,
                "page_index": page_index,
            })

        # Image upload
        image_url = slide.get("image_url")
        if image_url:
            image_eid = IMAGE_ELEMENT_IDS.get(page_index)
            op: dict[str, Any] = {
                "type": "upload-asset-from-url",
                "url": image_url,
                "page_index": page_index,
                "element_id": image_eid,
                "placement": "full_bleed" if page_index > 1 else (
                    "full_bleed_background_with_text_overlay_bottom_third"
                ),
            }
            if image_eid is None:
                op["_note"] = (
                    f"element_id unknown for page {page_index} "
                    "— retrieve from start-editing-transaction"
                )
            operations.append(op)

    return operations


def build_canva_pending(
    *,
    topic: str,
    tone: str,
    slides: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the full canva_pending.json payload from WR2 draft data.

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
    if len(slides) > MAX_SLIDES:
        raise ValueError(
            f"cannot exceed {MAX_SLIDES} slides — template DAHE6lx1lf8 has "
            f"{MAX_SLIDES} pages, got {len(slides)}",
        )

    operations = slides_to_operations(slides)

    return {
        "template_design_id": TEMPLATE_DESIGN_ID,
        "folder_id": CAROUSEL_FOLDER_ID,
        "design_id": None,
        "design_url": None,
        "topic": topic,
        "tone": tone,
        "page_index": 0,
        "slides_count": len(slides),
        "operations_count": len(operations),
        "operations": operations,
        "slides": slides,  # passed through for APPLICA STEP 3 editorial pass
    }
