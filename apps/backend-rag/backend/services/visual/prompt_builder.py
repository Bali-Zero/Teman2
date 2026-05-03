"""4-layer prompt assembly for Imagen 4 (design §4.1).

Layers:
    [SCENE_CORE]       — from slides.json image_prompt
    [BRAND_SUFFIX]     — from brand.json:51 (editorial Wired/Bloomberg style)
    [STYLE_MODIFIERS]  — macrografia editoriale, surrealista
    [NEGATIVE_PROMPT]  — hands holding objects, passport close-ups, stock, watermark
"""

from __future__ import annotations

BRAND_SUFFIX: str = (
    "Editorial style, high resolution, no stock imagery, "
    "no handshakes, no generic passports, cinematic lighting"
)

DEFAULT_STYLE_MODIFIERS: tuple[str, ...] = (
    "macrografia editoriale",
    "surrealista",
    "stile Wired magazine",
    "stile Bloomberg photography",
)

NEGATIVE_PROMPT: str = (
    "hands holding objects, passport close-ups, generic handshake, "
    "stock photo aesthetic, text overlays, watermark, logo, "
    "deformed hands, extra fingers, distorted faces, illegible text"
)


def build_imagen_prompt(
    scene_core: str,
    *,
    style_modifiers: tuple[str, ...] | None = None,
    brand_suffix: str = BRAND_SUFFIX,
    extra_hints: str | None = None,
) -> str:
    """Assemble the 4-layer prompt. Returns a single string.

    scene_core comes from slides.json image_prompt — produced by the Director
    for each specific slide. style_modifiers default to brand.json editorial.
    """
    if not scene_core or not scene_core.strip():
        raise ValueError("scene_core is required")
    style = ", ".join(style_modifiers or DEFAULT_STYLE_MODIFIERS)
    parts = [scene_core.strip(), brand_suffix, style]
    if extra_hints:
        parts.append(extra_hints.strip())
    return ". ".join(p for p in parts if p).strip()
