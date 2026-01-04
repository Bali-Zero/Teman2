#!/usr/bin/env python3
"""
GEMINI BROWSER AUTOMATION - Cover Image Generation
===================================================
Complete workflow for Claude Code to generate images via Gemini.

This module provides the exact sequence of mcp__claude-in-chrome
tool calls needed to generate an artistic cover image.

UNIQUE BALIZERO VISUAL IDENTITY:
- NOT stock photos
- Photographic art that tells a story
- Balinese soul meets Swiss precision
- Every image should be poster-worthy
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ImageRequest:
    """Request for image generation"""

    title: str
    summary: str
    category: str
    article_id: Optional[str] = None


class BaliZeroImageStyle:
    """
    BALIZERO UNIQUE VISUAL IDENTITY
    ================================

    Our images are NOT:
    - Generic stock photos
    - Obvious literal illustrations
    - Corporate clichés
    - AI-looking synthetic images

    Our images ARE:
    - Museum-quality photographic art
    - Visual metaphors that make you think
    - Emotionally resonant
    - Distinctly Balinese yet universally sophisticated
    """

    # UNIQUE BALIZERO SIGNATURE ELEMENTS
    SIGNATURE_ELEMENTS = {
        "lighting": [
            "Bali's unique golden hour - warmer and more amber than Mediterranean",
            "Dramatic crepuscular rays through tropical clouds",
            "Dappled light through palm fronds creating natural bokeh",
            "First light on Mount Agung with pink-orange gradient",
            "Candlelit temple scenes with warm tungsten glow",
        ],
        "textures": [
            "Weathered volcanic stone with centuries of patina",
            "Hand-carved teak with visible chisel marks",
            "Aged bronze with verdigris green accents",
            "Palm fiber rope coiled in perfect spirals",
            "Moss growing on ancient stone carvings",
        ],
        "water": [
            "Mirror-still rice paddy reflections at dawn",
            "Infinity pool edge merging with jungle horizon",
            "Ocean at Uluwatu with spray catching golden light",
            "Sacred spring water with floating flower offerings",
            "Morning dew on tropical leaves",
        ],
        "cultural_details": [
            "Canang sari offerings - but artistically composed, not tourist-snapshot",
            "Gamelan mallets resting on bronze keys",
            "Ceremonial umbrellas (tedung) in procession",
            "Traditional ikat fabric patterns",
            "Lontar palm manuscripts with ancient script",
        ],
    }

    # CATEGORY-SPECIFIC UNIQUE IMAGERY
    CATEGORY_IMAGERY = {
        "immigration": {
            "concept": "The threshold moment - standing at the edge of transformation",
            "unique_shots": [
                "Split-screen temple gate: darkness behind, golden light ahead - symbolizing the journey from uncertainty to clarity",
                "Traditional Balinese bridge (bamboo or stone) emerging from jungle mist toward clear sky",
                "Footprints on Bali's distinctive BLACK volcanic sand leading toward crystal turquoise water",
                "Empty jukung boat with fresh offerings, ready to set sail at first light",
                "Stone steps of Pura Lempuyang ascending through clouds toward the 'Gates of Heaven'",
            ],
            "color_mood": "Transition from cool mist to warm gold",
            "avoid": [
                "passport imagery",
                "airport scenes",
                "suitcases",
                "visa stamps",
                "immigration queues",
            ],
        },
        "business": {
            "concept": "Rooted growth - the banyan tree philosophy",
            "unique_shots": [
                "Massive banyan tree (like the one in Monkey Forest) with aerial roots creating natural architecture",
                "Tegallalang rice terraces showing the genius of subak irrigation - ancient sustainable business",
                "Master silversmith's hands in Celuk village - extreme close-up showing decades of craft",
                "Sunrise over Sanur harbor with traditional boats and modern ones side by side",
                "Coffee cherry drying process in Kintamani - from raw to refined",
            ],
            "color_mood": "Rich earth tones, emerald greens, golden accents",
            "avoid": [
                "graphs",
                "handshakes",
                "laptops",
                "office buildings",
                "suits",
                "meeting rooms",
            ],
        },
        "tax": {
            "concept": "Perfect balance - the harmony that enables prosperity",
            "unique_shots": [
                "Antique Chinese merchant's scale (dacin) with brass weights, weathered by trade routes",
                "Balinese water temple (Tirta Empul) showing the equal distribution of sacred water",
                "Stone labyrinth at ancient temple viewed from above, one clear golden path visible",
                "Water drops falling into temple basin creating perfect concentric ripples",
                "Yin-yang naturally formed by black volcanic sand and white coral beach",
            ],
            "color_mood": "Serene blues and golds, balanced light",
            "avoid": ["calculators", "money", "tax forms", "spreadsheets", "receipts"],
        },
        "property": {
            "concept": "Where dreams take root - home as sanctuary",
            "unique_shots": [
                "Aerial dusk shot: modern villa with infinity pool merging into jungle canopy",
                "Architectural detail: ancient joglo wood beam meeting contemporary glass",
                "Garden view through traditional Balinese carved stone doorway",
                "Reflection of villa in still rice paddy at blue hour",
                "Master craftsman fitting traditional palm-fiber roof (alang-alang)",
            ],
            "color_mood": "Warm wood tones, tropical greens, sunset amber",
            "avoid": [
                "for sale signs",
                "keys",
                "contracts",
                "real estate agents",
                "blueprints",
            ],
        },
        "lifestyle": {
            "concept": "The art of living well - intentional, beautiful, balanced",
            "unique_shots": [
                "Vintage single-fin surfboard leaning against moss-covered temple wall at golden hour",
                "Steaming cup of kopi tubruk on reclaimed teak table, Mount Agung in soft focus behind",
                "Yoga silhouette on Uluwatu cliff edge, sun creating halo effect",
                "Traditional market at dawn: pyramids of mangosteen, rambutan, salak arranged like art",
                "Balinese healer's (balian) hands preparing traditional medicine from fresh herbs",
            ],
            "color_mood": "Vibrant but natural, golden warmth, tropical saturation",
            "avoid": [
                "cocktails on beach",
                "tourist crowds",
                "Instagram poses",
                "generic yoga",
            ],
        },
        "legal": {
            "concept": "Ancient wisdom meets modern clarity",
            "unique_shots": [
                "Library of lontar manuscripts (palm leaf texts) illuminated by single candle beam",
                "Ceremonial kris dagger laid on antique map of archipelago",
                "Stone Garuda statue (symbol of protection) with morning mist",
                "Traditional village meeting (banjar) under sacred banyan - collective justice",
                "Courthouse steps in Denpasar with traditional Balinese architecture details",
            ],
            "color_mood": "Dignified amber and shadow, dramatic chiaroscuro",
            "avoid": [
                "Western courtrooms",
                "gavels",
                "prison bars",
                "angry confrontation",
            ],
        },
        "tech": {
            "concept": "Ancient patterns, future thinking - tradition informs innovation",
            "unique_shots": [
                "Traditional Balinese calendar (tika) with its complex cycles - original algorithm",
                "Fiber optic cable installation through rice terraces - old meets new",
                "Young coder working in bamboo coworking space with jungle view",
                "Drone hovering over ceremonial procession - technology serving culture",
                "Solar panels on traditional village rooftops, seamlessly integrated",
            ],
            "color_mood": "Cool tech blues with warm Bali gold accents",
            "avoid": [
                "generic tech imagery",
                "circuit boards",
                "robots",
                "Matrix-style code",
            ],
        },
    }

    # FORBIDDEN CLICHÉS - ABSOLUTE NO
    FORBIDDEN = [
        "Graphs or charts of any kind",
        "Arrows pointing up",
        "Handshakes (business or otherwise)",
        "People in suits",
        "Passport stamps or visa imagery",
        "Flags (any nationality)",
        "Generic 'laptop on beach'",
        "Piles of money or coins",
        "Calculators or spreadsheets",
        "Stock-photo smiling faces",
        "Thumbs up gestures",
        "Keys (house keys, car keys)",
        "For Sale or Sold signs",
        "Airport/airplane imagery",
        "Generic yoga poses on generic beach",
        "Cocktails with umbrellas",
        "Obvious tourist scenes",
    ]


def build_gemini_prompt(request: ImageRequest) -> str:
    """
    Build the complete Gemini prompt with unique BaliZero details.
    """
    style = BaliZeroImageStyle()
    category = request.category.lower()

    # Get category-specific imagery
    cat_data = style.CATEGORY_IMAGERY.get(category, style.CATEGORY_IMAGERY["lifestyle"])

    # Select signature elements
    import random

    lighting = random.choice(style.SIGNATURE_ELEMENTS["lighting"])
    texture = random.choice(style.SIGNATURE_ELEMENTS["textures"])
    cultural = random.choice(style.SIGNATURE_ELEMENTS["cultural_details"])
    unique_shot = random.choice(cat_data["unique_shots"])

    prompt = f"""Create a stunning, museum-quality photograph for this article:

ARTICLE: "{request.title}"
{f"CONTEXT: {request.summary[:200]}" if request.summary else ""}

═══════════════════════════════════════════════════════════════
CREATIVE DIRECTION: {cat_data["concept"]}
═══════════════════════════════════════════════════════════════

EXACT SHOT TO CREATE:
{unique_shot}

SIGNATURE BALIZERO ELEMENTS TO INCLUDE:
• LIGHTING: {lighting}
• TEXTURE: {texture}
• CULTURAL DETAIL: {cultural}

COLOR MOOD: {cat_data["color_mood"]}

═══════════════════════════════════════════════════════════════
TECHNICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════

STYLE: Ultra-realistic photography, NOT illustration, NOT AI-looking
QUALITY: 8K resolution, extremely detailed, film grain subtle
LIGHTING: Cinematographic, Denis Villeneuve aesthetic
COMPOSITION: Rule of thirds, leading lines, space for text overlay
ASPECT RATIO: 16:9 landscape (article header format)

ABSOLUTE REQUIREMENTS:
✓ Must look like a National Geographic or Condé Nast photo
✓ Must feel uniquely Balinese (not generic tropical)
✓ Must evoke emotion, not just inform
✓ Must be poster-worthy - you'd hang it on your wall
✓ NO TEXT, NO WATERMARKS, NO LOGOS

═══════════════════════════════════════════════════════════════
FORBIDDEN (will reject if present)
═══════════════════════════════════════════════════════════════
{chr(10).join(f"✗ {item}" for item in cat_data["avoid"])}
✗ Stock photo aesthetic
✗ Generic, forgettable imagery
✗ Obvious, literal illustrations of the topic

═══════════════════════════════════════════════════════════════

OUTPUT: One powerful photograph that captures the SOUL of this story.
Make viewers stop scrolling. Make them feel something.
"""
    return prompt


def get_browser_automation_steps(prompt: str, output_filename: str) -> Dict:
    """
    Returns the exact mcp__claude-in-chrome tool sequence.
    Claude Code should execute these in order.
    """

    return {
        "description": "Generate BaliZero cover image via Gemini browser automation",
        "output_file": output_filename,
        "steps": [
            {
                "action": "Get browser context",
                "tool": "mcp__claude-in-chrome__tabs_context_mcp",
                "params": {"createIfEmpty": True},
                "notes": "Creates MCP tab group if needed",
            },
            {
                "action": "Create new tab for Gemini",
                "tool": "mcp__claude-in-chrome__tabs_create_mcp",
                "params": {},
                "notes": "Fresh tab for image generation",
            },
            {
                "action": "Navigate to Gemini",
                "tool": "mcp__claude-in-chrome__navigate",
                "params": {"url": "https://gemini.google.com/app"},
                "notes": "User should be logged into Google",
            },
            {
                "action": "Wait for page load",
                "tool": "mcp__claude-in-chrome__browser_wait_for",
                "params": {"time": 3},
                "notes": "Allow page to fully load",
            },
            {
                "action": "Read page to find input",
                "tool": "mcp__claude-in-chrome__read_page",
                "params": {"filter": "interactive"},
                "notes": "Find the message input field",
            },
            {
                "action": "Find message input",
                "tool": "mcp__claude-in-chrome__find",
                "params": {"query": "message input textarea"},
                "notes": "Locate the text input area",
            },
            {
                "action": "Enter the image prompt",
                "tool": "mcp__claude-in-chrome__form_input",
                "params": {"value": prompt},
                "notes": "Type the complete image generation prompt",
            },
            {
                "action": "Submit prompt",
                "tool": "mcp__claude-in-chrome__computer",
                "params": {"action": "key", "text": "Enter"},
                "notes": "Press Enter to submit",
            },
            {
                "action": "Wait for image generation",
                "tool": "mcp__claude-in-chrome__browser_wait_for",
                "params": {"time": 45},
                "notes": "Imagen 3 typically takes 15-45 seconds",
            },
            {
                "action": "Take screenshot of result",
                "tool": "mcp__claude-in-chrome__computer",
                "params": {"action": "screenshot"},
                "notes": "Capture the generated image",
            },
            {
                "action": "Download image if available",
                "manual_step": True,
                "instructions": [
                    "1. Look for the generated image in Gemini response",
                    "2. Right-click on the image",
                    "3. Select 'Save image as...'",
                    f"4. Save to: {output_filename}",
                ],
            },
        ],
        "prompt_to_use": prompt,
        "troubleshooting": {
            "not_logged_in": "User needs to log into Google account in Chrome first",
            "image_not_generated": "Try regenerating or simplifying the prompt",
            "timeout": "Increase wait time to 60 seconds for complex prompts",
            "multiple_images": "Select the best one that matches BaliZero style",
        },
    }


def generate_image_for_article(
    title: str,
    summary: str = "",
    category: str = "lifestyle",
    output_dir: str = "data/images",
) -> Dict:
    """
    Main function to generate image automation for an article.

    Returns complete instructions for Claude Code browser automation.
    """
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:30]
    filename = f"cover_{timestamp}_{slug}.png"
    output_path = str(Path(output_dir) / filename)

    # Create request
    request = ImageRequest(title=title, summary=summary, category=category)

    # Build prompt
    prompt = build_gemini_prompt(request)

    # Get automation steps
    automation = get_browser_automation_steps(prompt, output_path)

    return {
        "article": {"title": title, "category": category},
        "image": {"prompt": prompt, "output_path": output_path, "filename": filename},
        "automation": automation,
    }


# For direct execution / testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--category", default="lifestyle")
    parser.add_argument("--output-dir", default="data/images")

    args = parser.parse_args()

    result = generate_image_for_article(
        title=args.title,
        summary=args.summary,
        category=args.category,
        output_dir=args.output_dir,
    )

    print("\n" + "=" * 70)
    print("🎨 BALIZERO IMAGE GENERATION")
    print("=" * 70)
    print(f"\n📰 Article: {result['article']['title']}")
    print(f"📁 Category: {result['article']['category']}")
    print(f"💾 Output: {result['image']['output_path']}")
    print("\n" + "-" * 70)
    print("GEMINI PROMPT:")
    print("-" * 70)
    print(result["image"]["prompt"])
    print("\n" + "-" * 70)
    print("BROWSER AUTOMATION STEPS:")
    print("-" * 70)
    for i, step in enumerate(result["automation"]["steps"], 1):
        print(f"  {i}. {step['action']}")
    print("=" * 70)
