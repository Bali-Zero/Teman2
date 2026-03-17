"""
Bali Zero Image Style — Single source of truth for all image generation prompts.
Used by: intel scraper (step 8 covers), war room (step 3 carousel).

IMPORTANT: Flux generates ONLY the background photograph.
Text overlay (headline, subtitle) is added AFTER by the compositing script.
So prompts must NEVER mention text — just the scene.

Brand identity from @balizero0 Instagram feed:
- Real photography of Bali — suggestive, cinematic, never stock
- Saturated warm colors, dramatic light, high contrast
- Subjects: real places, real situations, real Indonesia
- Mood: investigative journalism, provocative, never banal
- The photo is the emotional hook — text goes on top after
"""

# ── Color palette ──
PALETTE = {
    "base": "#0c0c0e",
    "terracotta": "#d4845a",
    "oro_antico": "#c9a96e",
    "batik_indigo": "#5e7fb5",
    "text": "#edeae4",
}

# ── Style suffix for BACKGROUND photos (no text!) ──
BZ_STYLE_SUFFIX = (
    "Ultra-realistic photograph, vivid saturated colors, bright and impactful. "
    "The subject itself tells the story before any text. "
    "Clean lower third for text overlay. "
    "No text, no words, no letters, no logos, no watermarks."
)

# ── Banned elements (hard filter) ──
BANNED = [
    "handshakes", "shaking hands",
    "generic passports", "passport photos",
    "stock imagery", "stock photo",
    "clipart", "illustration",
    "text overlay", "watermark",
    "thumbs up", "pointing fingers",
    "smiling businesspeople", "corporate group photo",
]

# ── Category-specific prompt modifiers ──
# Each must suggest a REAL SCENE in Bali/Indonesia that hooks the viewer
# ── Category backgrounds — vivid, provocative, storytelling subjects ──
CATEGORY_STYLE = {
    "immigration": "Close-up of a real person holding Indonesian visa documents at immigration counter, bright office light, vivid colors.",
    "tax": "Aerial view of rows of identical desks in Indonesian tax office, or macro of Rupiah banknotes and tax forms, bright natural light.",
    "company": "Bright modern Bali coworking space with tropical garden, or notary brass seal close-up on fresh documents, vivid daylight.",
    "property": "Dramatic drone view of Bali villas from above with pool patterns, or construction site with heavy machinery and tropical backdrop, bright sky.",
    "lifestyle": "Vivid Bali lifestyle moment: surfboards at beach, motorbike on coastal road, colorful warung, bright tropical light.",
    "general": "Striking Balinese cultural image: golden Ganesha statue, ornate temple gate, colorful offerings, bright saturated colors.",
    "regulation": "Indonesian government building or courthouse, imposing architecture, dramatic sky, vivid colors, official atmosphere.",
}


def build_cover_prompt(title: str, category: str = "general") -> str:
    """Build background photo prompt for an intel article cover.
    Title ALONE drives the scene. Category ignored — the title says it all."""
    short_title = title[:100]
    return f"{short_title}. {BZ_STYLE_SUFFIX}"


def build_slide_prompt(title: str, body: str = "", style_hint: str = "") -> str:
    """Build background photo prompt for war room carousel slide.
    Text overlay is added AFTER by compositing script."""
    hint = f" {style_hint}" if style_hint else ""
    short_title = title[:80]
    return f"Background for: {short_title}.{hint} {BZ_STYLE_SUFFIX}"
