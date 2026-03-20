"""
Bali Zero Image Style — Single source of truth for all image generation prompts.
Used by: intel scraper (step 8 covers), war room (step 3 carousel).

PHILOSOPHY:
  Images are NOT illustrations of the article. They are EMOTIONAL HOOKS.
  A surveillance article → not a camera, but shadow of a watching eye over a temple.
  A tax crackdown → not a desk with forms, but gold rupiah coins melting in heat.
  The image must make the reader feel something BEFORE reading a single word.

  Flux generates ONLY the background photograph.
  Text overlay (headline, subtitle) is added AFTER by the compositing script.
  Prompts must NEVER mention text — just the scene.

Brand identity (from @balizero0):
- Cinematic photography, Bali-rooted, never stock
- Vivid saturated palette: terracotta, gold, indigo, tropical green
- Dramatic light: golden hour, rim light, deep shadows
- Narrative symbolism: one strong image = whole story
- Mood: investigative journalism, visceral, provokes a reaction
"""

import os
import sys
from typing import Optional

# ── Brand color palette ──
PALETTE = {
    "base": "#0c0c0e",
    "terracotta": "#d4845a",
    "oro_antico": "#c9a96e",
    "batik_indigo": "#5e7fb5",
    "text": "#edeae4",
}

# ── Universal quality suffix (appended to every prompt) ──
BZ_QUALITY = (
    "Cinematic photography, ultra-sharp, vivid saturated colors, dramatic lighting. "
    "Emotionally powerful, tells a story without words. "
    "Clean lower third area for text overlay. "
    "No text, no words, no letters, no logos, no watermarks. "
    "No stock photo clichés, no handshakes, no smiling businesspeople."
)

# ── Symbolic visual language per category ──
# Not literal scenes — symbolic, emotional, narrative
CATEGORY_SYMBOLISM = {
    "immigration": [
        "single weathered passport on cracked Balinese stone, dramatic side light, deep shadows",
        "lone figure silhouette at glass immigration window, warm backlight, long shadow",
        "ornate Bali gate at dawn, single traveler passing through, mist and golden light",
        "close-up of visa stamp ink wet on white page, macro, vivid red and gold",
    ],
    "tax": [
        "cascade of gold rupiah coins catching sunlight against dark volcanic stone",
        "aerial view of Ubud rice terraces with currency symbols in the patterns, abstract",
        "macro of ancient brass scales tipping, Balinese offering flowers as counterweight",
        "dramatic sky over BPKP building reflected in flooded rice paddy, surreal light",
    ],
    "company": [
        "modern glass coworking space with Bali jungle pressing in from all sides, dramatic",
        "macro of official Indonesian company stamp pressing into golden wax, cinematic",
        "aerial Canggu startup district at golden hour, motorbikes creating light trails",
        "lush tropical plants breaking through corporate minimalist office walls, symbolic",
    ],
    "property": [
        "dramatic drone view of infinity pool villa mirroring stormy Bali sky",
        "lone villa on clifftop above Indian Ocean at sunset, rich terracotta tones",
        "hands holding miniature traditional Balinese house, deep selective focus, golden",
        "construction silhouette against blazing orange Bali sunset, powerful contrast",
    ],
    "lifestyle": [
        "lone surfer at Uluwatu cliff edge at golden hour, explosive ocean spray",
        "motorbike headlight cutting through tropical night rain, neon reflections on asphalt",
        "vibrant Balinese market explosion of spices and flowers, saturated overhead shot",
        "hammock between palms over turquoise Nusa Penida water, hyper-vivid blue",
    ],
    "regulation": [
        "Indonesian government building columns casting dramatic long shadows at noon",
        "close-up of official red government seal on white document, bold and powerful",
        "scales of justice in Balinese stone against stormy tropical sky",
        "lone official in white uniform at junction directing traffic, symbolic authority",
    ],
    "general": [
        "golden Garuda Indonesia eagle statue against cinematic storm clouds, dramatic",
        "ornate temple gate splitting frame between shadow and brilliant sunlight",
        "macro of traditional Balinese offering, rich colors, symbolic geometry",
        "aerial Mount Agung at sunrise above sea of clouds, epic scale",
    ],
}


def build_cover_prompt(title: str, category: str = "general",
                       summary: Optional[str] = None) -> str:
    """Build a cinematic background prompt for an intel article cover.

    If summary is provided, uses Claude to generate a symbolic visual concept.
    Otherwise falls back to title-derived symbolism.
    """
    if summary:
        return _prompt_via_claude(title, category, summary)
    return _prompt_from_title(title, category)


def _prompt_from_title(title: str, category: str) -> str:
    """Derive a symbolic visual from the article title using category symbolism."""
    import random
    import hashlib

    # Use title hash for deterministic but varied selection
    idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % 4
    cat = category if category in CATEGORY_SYMBOLISM else "general"
    visual = CATEGORY_SYMBOLISM[cat][idx]

    return f"{visual}, inspired by: {title[:80]}. {BZ_QUALITY}"


def _prompt_via_claude(title: str, category: str, summary: str) -> str:
    """Use claude CLI (Max subscription) to generate a symbolic visual concept.
    Falls back to _prompt_from_title if CLI unavailable."""
    import subprocess

    prompt = (
        "You are a visual director for an investigative journalism brand in Bali. "
        "Given this article, describe ONE cinematic photograph that captures the emotional "
        "essence — symbolic, not literal. No text in the image. "
        "Max 2 sentences. Vivid, specific, Bali-rooted. "
        "Output ONLY the image description, nothing else.\n\n"
        f"Title: {title}\n\nSummary: {summary[:400]}"
    )

    try:
        # Strip ANTHROPIC_API_KEY from env — claude CLI uses OAuth (Max subscription)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        result = subprocess.run(
            ["claude", "--print", "--model", "claude-haiku-4-5-20251001", prompt],
            capture_output=True, text=True, timeout=30, env=env
        )
        if result.returncode == 0 and result.stdout.strip():
            visual = result.stdout.strip()
            return f"{visual} {BZ_QUALITY}"
        print(f"  claude CLI returned empty ({result.returncode}) — using fallback", file=sys.stderr)
    except Exception as e:
        print(f"  claude CLI failed ({e}) — using title fallback", file=sys.stderr)

    return _prompt_from_title(title, category)


def build_slide_prompt(title: str, body: str = "", style_hint: str = "") -> str:
    """Build background photo prompt for war room carousel slide."""
    hint = f" {style_hint}" if style_hint else ""
    return _prompt_from_title(title, "general") + hint
