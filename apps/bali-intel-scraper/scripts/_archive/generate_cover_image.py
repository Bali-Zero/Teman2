#!/usr/bin/env python3
"""
GENERATE COVER IMAGE - Chrome Browser Automation for Gemini
============================================================
This script is designed to be run BY Claude Code using browser tools.

It provides the structured prompt and instructions for Claude Code
to generate an image using Gemini via Chrome browser automation.

Usage (by Claude Code):
    python generate_cover_image.py --title "Article Title" --category immigration

Claude Code will then use mcp__claude-in-chrome tools to:
1. Navigate to gemini.google.com/app
2. Enter the image generation prompt
3. Wait for image generation
4. Download the generated image
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


# Image style - NO CLICHÉS, photographic art only
IMAGE_STYLE_PROMPT = """
PHOTOGRAPHIC STYLE REQUIREMENTS:
- Cinematographic quality like Denis Villeneuve films
- Golden hour lighting, Bali atmosphere
- Ultra-detailed, 8K quality
- Luminous, optimistic mood
- Fine art photography, museum-worthy

ABSOLUTELY FORBIDDEN (stock photo clichés):
- Graphs with arrows going up
- Handshakes between business people
- Passport stamps or visa documents
- Flags waving
- People in suits smiling
- Laptop on beach (too obvious)
- Piles of money or coins

USE INSTEAD (creative visual metaphors):
- Architecture: stairs ascending, doors opening, bridges
- Nature: seeds sprouting, trees with visible roots, tides
- Light: sunrises, rays through clouds, prismatic reflections
- Balinese elements: temple at dawn, flower offerings, golden gamelan
- Transformation: butterflies, stylized phoenixes, breaking waves
"""

CATEGORY_STYLES = {
    "immigration": {
        "mood": "hopeful journey, new beginnings",
        "elements": "Balinese temple gate opening to golden horizon, bridge through misty jungle, footprints on volcanic black sand leading to ocean",
        "avoid": "passport stamps, visa documents, airport scenes, suitcases",
    },
    "business": {
        "mood": "growth, strategic vision, opportunity",
        "elements": "Giant banyan tree with aerial roots in golden sunset, Tegallalang rice terraces at dawn with rising mist, craftsman hands weaving rattan",
        "avoid": "graphs, charts, handshakes, office buildings, suits",
    },
    "tax": {
        "mood": "balance, clarity, precision",
        "elements": "Ancient bronze Balinese scale in perfect equilibrium, stone labyrinth seen from above with illuminated path, water drops on lotus leaf",
        "avoid": "calculators, money, coins, tax forms, numbers",
    },
    "property": {
        "mood": "aspiration, establishment, foundation",
        "elements": "Aerial view of jungle villa with infinity pool at sunset, teak wood meeting modern glass architecture, villa reflection in calm rice paddy",
        "avoid": "sold signs, house keys, for sale boards, real estate agents",
    },
    "lifestyle": {
        "mood": "freedom, quality of life, balance",
        "elements": "Vintage surfboard against moss-covered temple wall, Balinese coffee on teak table with Agung volcano view, sunset yoga silhouette on Uluwatu cliff",
        "avoid": "generic beach scenes, cocktails, tourist activities",
    },
    "legal": {
        "mood": "wisdom, structure, resolution",
        "elements": "Ancient library with lontar palm leaf texts lit by candle, sandalwood gavel on marble base, bronze scales reflected in serene water",
        "avoid": "courtrooms, legal documents, gavels in typical setting",
    },
}


def build_gemini_prompt(title: str, summary: str, category: str) -> str:
    """Build the complete prompt for Gemini Imagen 3"""

    cat_style = CATEGORY_STYLES.get(category, CATEGORY_STYLES.get("lifestyle"))

    prompt = f"""Create a stunning photographic artwork for this news article:

ARTICLE: "{title}"
BRIEF: {summary[:200] if summary else "No summary"}

MOOD: {cat_style["mood"]}

VISUAL DIRECTION:
{cat_style["elements"]}

ABSOLUTELY AVOID:
{cat_style["avoid"]}

{IMAGE_STYLE_PROMPT}

TECHNICAL SPECS:
- Aspect ratio: 16:9 (landscape, article header)
- Style: Ultra-realistic photography
- Lighting: Golden hour / dramatic natural light
- Quality: 8K, extremely detailed
- Composition: Rule of thirds, leading lines

OUTPUT: One powerful, memorable photograph. NOT a literal illustration, but a VISUAL METAPHOR that captures the essence of the story.
"""
    return prompt


def generate_browser_instructions(prompt: str, output_path: str) -> dict:
    """Generate instructions for Claude Code browser automation"""

    return {
        "tool_sequence": [
            {
                "step": 1,
                "tool": "mcp__claude-in-chrome__tabs_context_mcp",
                "params": {"createIfEmpty": True},
                "purpose": "Get browser context",
            },
            {
                "step": 2,
                "tool": "mcp__claude-in-chrome__navigate",
                "params": {"url": "https://gemini.google.com/app"},
                "purpose": "Navigate to Gemini",
            },
            {
                "step": 3,
                "tool": "mcp__claude-in-chrome__browser_wait_for",
                "params": {"time": 3},
                "purpose": "Wait for page load",
            },
            {
                "step": 4,
                "tool": "mcp__claude-in-chrome__read_page",
                "params": {},
                "purpose": "Read page structure",
            },
            {
                "step": 5,
                "tool": "mcp__claude-in-chrome__find",
                "params": {"query": "text input field for message"},
                "purpose": "Find input field",
            },
            {
                "step": 6,
                "action": "Type the prompt into the input field",
                "prompt": prompt[:500] + "...",  # Truncated for display
                "purpose": "Enter image generation prompt",
            },
            {
                "step": 7,
                "tool": "mcp__claude-in-chrome__computer",
                "params": {"action": "key", "text": "Enter"},
                "purpose": "Submit prompt",
            },
            {
                "step": 8,
                "tool": "mcp__claude-in-chrome__browser_wait_for",
                "params": {"time": 30},
                "purpose": "Wait for image generation (can take 10-30 seconds)",
            },
            {
                "step": 9,
                "action": "Take screenshot or download generated image",
                "output_path": output_path,
                "purpose": "Save the generated image",
            },
        ],
        "notes": [
            "User must be logged into Google account in Chrome",
            "Gemini (Imagen 3) is free with Google One AI Premium",
            "Image generation typically takes 10-30 seconds",
            "If Gemini shows multiple images, select the best one",
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate cover image prompt for Gemini"
    )
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--summary", default="", help="Article summary")
    parser.add_argument(
        "--category",
        default="lifestyle",
        choices=["immigration", "business", "tax", "property", "lifestyle", "legal"],
        help="Article category",
    )
    parser.add_argument("--output-dir", default="data/images", help="Output directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cover_{timestamp}.png"
    output_path = str(output_dir / filename)

    # Build prompt
    prompt = build_gemini_prompt(args.title, args.summary, args.category)

    # Generate instructions
    instructions = generate_browser_instructions(prompt, output_path)

    if args.json:
        result = {
            "title": args.title,
            "category": args.category,
            "prompt": prompt,
            "output_path": output_path,
            "browser_instructions": instructions,
        }
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "=" * 70)
        print("🎨 GEMINI IMAGE GENERATION PROMPT")
        print("=" * 70)
        print(f"\n📰 Article: {args.title}")
        print(f"📁 Category: {args.category}")
        print(f"💾 Output: {output_path}")
        print("\n" + "-" * 70)
        print("PROMPT FOR GEMINI:")
        print("-" * 70)
        print(prompt)
        print("\n" + "-" * 70)
        print("BROWSER AUTOMATION STEPS:")
        print("-" * 70)
        for step in instructions["tool_sequence"]:
            print(f"  {step['step']}. {step.get('purpose', step.get('action', ''))}")
        print("\n" + "=" * 70)
        print("💡 Copy the prompt above and paste into Gemini")
        print("   OR use Claude Code browser automation to automate this")
        print("=" * 70)


if __name__ == "__main__":
    main()
