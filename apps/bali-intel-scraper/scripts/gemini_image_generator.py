#!/usr/bin/env python3
"""
GEMINI IMAGE GENERATOR - Intelligent Cover Image Creation
==========================================================
Claude REASONS about each article and creates a UNIQUE prompt.

NO predefined shots. NO random selection.
Each image prompt is crafted specifically for that article's:
- Central theme/problem
- Emotional core
- Key moments mentioned
- Target audience reaction

PHILOSOPHY:
"Il lettore deve capire il tema in 2 secondi"
Beautiful but CLEAR, not cryptic.
"""

import re
from pathlib import Path
from typing import Dict
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ArticleContext:
    """Complete context for image generation"""

    title: str
    summary: str
    full_content: str  # The actual article text
    category: str
    tone: str  # "problem", "solution", "informative", "warning", etc.
    key_moments: list  # Specific scenes/situations mentioned in article


class ImagePromptFramework:
    """
    Framework for Claude to REASON about image creation.

    NOT a library of predefined shots.
    A thinking framework for creating the RIGHT image.
    """

    # ═══════════════════════════════════════════════════════════════════
    # REASONING QUESTIONS - Claude should ask these for EVERY article
    # ═══════════════════════════════════════════════════════════════════

    REASONING_FRAMEWORK = """
    BEFORE creating an image prompt, answer these questions:

    1. CENTRAL THEME
       - What is the ONE thing this article is about?
       - Is it a PROBLEM, a SOLUTION, or INFORMATION?
       - What would a headline writer summarize this as?

    2. EMOTIONAL CORE
       - How should the reader FEEL looking at this image?
       - Frustrated? Relieved? Curious? Warned? Inspired?
       - What's the emotional journey of the article?

    3. THE MOMENT
       - Is there a SPECIFIC moment in the article that captures everything?
       - A scene described? A situation mentioned? A workaround suggested?
       - What would a photojournalist shoot if they were covering this story?

    4. UNIVERSAL vs SPECIFIC
       - Is this a universal experience (anyone can relate)?
       - Or Indonesia-specific (needs local context)?
       - Balance: Bali setting visible but topic clear to anyone

    5. THE 2-SECOND TEST
       - If someone sees ONLY the image, will they understand the topic?
       - No cryptic metaphors. No "only Nostradamus understands" imagery.
       - Clear. Beautiful. But CLEAR first.
    """

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY GUIDELINES - Not shots, just direction
    # ═══════════════════════════════════════════════════════════════════

    CATEGORY_GUIDELINES = {
        "immigration": {
            "typical_themes": [
                "visa problems",
                "new policies",
                "service locations",
                "document issues",
                "extensions",
            ],
            "emotional_range": [
                "frustration → relief",
                "confusion → clarity",
                "worry → solution",
            ],
            "setting_options": [
                "immigration office",
                "service counter",
                "digital kiosk",
                "home with documents",
                "mall service center",
            ],
            "forbidden": [
                "passport stamps closeup",
                "airports",
                "suitcases",
                "flags",
                "queues of frustrated people",
                "government office dystopia",
            ],
            "remember": "Immigration articles are usually about SOLVING problems or NAVIGATING systems. Show the solution or the journey, not just the problem.",
        },
        "tax": {
            "typical_themes": [
                "system problems",
                "new regulations",
                "filing deadlines",
                "NPWP issues",
                "compliance",
            ],
            "emotional_range": [
                "confusion → understanding",
                "frustration → resolution",
                "worry → compliance",
            ],
            "setting_options": [
                "laptop with tax portal",
                "tax office (KPP)",
                "consultation with expert",
                "home office filing",
                "error screens",
            ],
            "forbidden": [
                "money piles",
                "coins",
                "calculators alone",
                "abstract metaphors",
                "stressed cartoon faces",
            ],
            "remember": "Tax articles often describe PROBLEMS with systems. Show the REALITY of dealing with it - the reload button, the office visit, the consultant help. Not abstract 'balance' metaphors.",
        },
        "business": {
            "typical_themes": [
                "starting business",
                "regulations",
                "opportunities",
                "PT setup",
                "coworking",
            ],
            "emotional_range": [
                "aspiration → action",
                "complexity → clarity",
                "idea → execution",
            ],
            "setting_options": [
                "coworking space",
                "business meeting",
                "signing documents",
                "modern office",
                "entrepreneur at work",
            ],
            "forbidden": [
                "graphs going up",
                "handshakes",
                "suits in boardroom",
                "skyscrapers",
                "generic corporate",
            ],
            "remember": "Business in Bali is DIFFERENT - casual smart, open air, lifestyle integration. Show THAT business culture, not Western corporate.",
        },
        "property": {
            "typical_themes": [
                "buying process",
                "market trends",
                "legal issues",
                "investment",
                "rentals",
            ],
            "emotional_range": [
                "dreaming → finding",
                "complexity → ownership",
                "searching → home",
            ],
            "setting_options": [
                "villa exterior",
                "property viewing",
                "signing at notary",
                "interior design",
                "aerial of compound",
            ],
            "forbidden": [
                "for sale signs",
                "keys closeup",
                "handshakes",
                "blueprints",
                "price tags",
            ],
            "remember": "Property is emotional - it's about LIFESTYLE, not just investment. Show the dream or the process, not just the transaction.",
        },
        "lifestyle": {
            "typical_themes": [
                "daily life",
                "cost of living",
                "expat experience",
                "health",
                "culture",
            ],
            "emotional_range": [
                "curiosity → discovery",
                "adjustment → belonging",
                "visiting → living",
            ],
            "setting_options": [
                "daily scenes",
                "cafe life",
                "scooter rides",
                "beach moments",
                "local interactions",
            ],
            "forbidden": [
                "cocktails with umbrellas",
                "tourist poses",
                "Instagram clichés",
                "overcrowded beaches",
            ],
            "remember": "Lifestyle is about REAL life in Bali, not vacation fantasy. Show the authentic daily experience.",
        },
        "legal": {
            "typical_themes": [
                "contracts",
                "disputes",
                "compliance",
                "corporate law",
                "immigration law",
            ],
            "emotional_range": [
                "concern → protection",
                "complexity → resolution",
                "risk → security",
            ],
            "setting_options": [
                "law office",
                "consultation",
                "document signing",
                "court (if relevant)",
                "notary",
            ],
            "forbidden": [
                "Western courtroom",
                "gavel",
                "scales of justice cliché",
                "prison imagery",
                "angry confrontation",
            ],
            "remember": "Legal in Indonesia looks DIFFERENT - show professional but Indonesian context. Batik in law offices is normal.",
        },
        "tech": {
            "typical_themes": [
                "digital nomad",
                "connectivity",
                "startups",
                "remote work",
                "apps",
            ],
            "emotional_range": [
                "possibility → productivity",
                "anywhere → here",
                "global → local",
            ],
            "setting_options": [
                "coworking with view",
                "home office setup",
                "video call",
                "tech setup",
                "starlink installation",
            ],
            "forbidden": [
                "circuit boards",
                "Matrix code",
                "robots",
                "sterile labs",
                "generic tech stock",
            ],
            "remember": "Tech in Bali is about FREEDOM - work from paradise. Show the lifestyle integration, not just the tech.",
        },
    }

    # ═══════════════════════════════════════════════════════════════════
    # VISUAL STYLE CONSTANTS - Apply to ALL images
    # ═══════════════════════════════════════════════════════════════════

    STYLE_CONSTANTS = """
    ALWAYS APPLY:
    - Ultra-realistic photography (magazine quality, not AI-looking)
    - Bali/Indonesia setting visible but not overwhelming
    - Warm, natural lighting (Bali's golden hour aesthetic)
    - 16:9 landscape format
    - 8K detail, sharp focus on subject
    - Space in upper area for potential text overlay
    - No text, watermarks, or logos in image
    - Real people in realistic situations (if people included)
    - Cinematic composition (rule of thirds, leading lines)
    """

    ABSOLUTE_FORBIDDEN = """
    NEVER INCLUDE (regardless of category):
    - Stock photo aesthetic (posed, fake smiles, generic)
    - Graphs, charts, arrows pointing up
    - Abstract metaphors that require explanation
    - Cryptic symbolism ("only Nostradamus understands")
    - Western corporate imagery in Bali context
    - Tourist clichés (cocktails, infinity pool selfies)
    - Depressing, dark, or dystopian mood
    - Text or readable documents with specific info
    """


class GeminiImageGenerator:
    """
    Generate image prompts through REASONING, not random selection.

    Usage:
    1. Provide full article context
    2. Claude analyzes using the framework
    3. Unique prompt created for that specific article
    """

    def __init__(self, output_dir: str = "data/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.framework = ImagePromptFramework()

    def get_reasoning_framework(self) -> str:
        """Return the reasoning framework for Claude to use"""
        return ImagePromptFramework.REASONING_FRAMEWORK

    def get_category_guidelines(self, category: str) -> Dict:
        """Get guidelines for a specific category"""
        cat_key = category.lower()
        return ImagePromptFramework.CATEGORY_GUIDELINES.get(
            cat_key,
            ImagePromptFramework.CATEGORY_GUIDELINES.get("lifestyle"),  # default
        )

    def build_reasoning_prompt(
        self, title: str, summary: str, full_content: str, category: str
    ) -> str:
        """
        Build a prompt that helps Claude REASON about the image.

        This is NOT the final Gemini prompt.
        This is the thinking framework for Claude to use.
        """
        guidelines = self.get_category_guidelines(category)

        return f"""
═══════════════════════════════════════════════════════════════════════════════
ARTICLE TO CREATE IMAGE FOR:
═══════════════════════════════════════════════════════════════════════════════

TITLE: {title}
CATEGORY: {category}
SUMMARY: {summary}

FULL CONTENT:
{full_content[:2000]}{"..." if len(full_content) > 2000 else ""}

═══════════════════════════════════════════════════════════════════════════════
REASONING FRAMEWORK - Answer these before creating the prompt:
═══════════════════════════════════════════════════════════════════════════════

{ImagePromptFramework.REASONING_FRAMEWORK}

═══════════════════════════════════════════════════════════════════════════════
CATEGORY GUIDELINES ({category.upper()}):
═══════════════════════════════════════════════════════════════════════════════

Typical themes: {", ".join(guidelines["typical_themes"])}
Emotional range: {", ".join(guidelines["emotional_range"])}
Setting options: {", ".join(guidelines["setting_options"])}
FORBIDDEN: {", ".join(guidelines["forbidden"])}
REMEMBER: {guidelines["remember"]}

═══════════════════════════════════════════════════════════════════════════════
STYLE REQUIREMENTS:
═══════════════════════════════════════════════════════════════════════════════

{ImagePromptFramework.STYLE_CONSTANTS}

{ImagePromptFramework.ABSOLUTE_FORBIDDEN}

═══════════════════════════════════════════════════════════════════════════════
NOW CREATE THE IMAGE PROMPT:
═══════════════════════════════════════════════════════════════════════════════

Based on your reasoning above, create a detailed image prompt for Gemini/Imagen.
The prompt should describe ONE specific scene that:
1. Immediately communicates the article topic (2-second test)
2. Captures the emotional core
3. Is beautiful but CLEAR, not cryptic
4. Shows a real moment, not an abstract concept

Write the prompt in English, be specific about composition, lighting, and mood.
"""

    def create_gemini_prompt(
        self, scene_description: str, mood: str, category: str, key_details: list = None
    ) -> str:
        """
        Create the final Gemini prompt from Claude's reasoned scene.

        Args:
            scene_description: The specific scene Claude decided on
            mood: The emotional tone
            category: Article category
            key_details: Specific details to include
        """
        guidelines = self.get_category_guidelines(category)
        forbidden = ", ".join(guidelines["forbidden"])

        details_text = ""
        if key_details:
            details_text = "\n".join(f"- {d}" for d in key_details)

        prompt = f"""Create a stunning, magazine-quality photograph:

SCENE:
{scene_description}

{f"KEY DETAILS TO INCLUDE:{chr(10)}{details_text}" if details_text else ""}

MOOD: {mood}

STYLE:
- Ultra-realistic photography, NOT illustration, NOT AI-looking
- Bali/Indonesia setting with warm, natural lighting
- 8K resolution, sharp details, cinematic composition
- 16:9 landscape format
- Leave space in upper third for potential text overlay

REQUIREMENTS:
- The image must IMMEDIATELY communicate the topic
- A viewer should understand the subject in 2 seconds
- Beautiful but CLEAR - no cryptic metaphors
- Real, relatable scene - not abstract concept

DO NOT INCLUDE: {forbidden}, stock photo aesthetic, text or watermarks

Create ONE powerful photograph that tells this story clearly."""

        return prompt

    def get_output_path(self, title: str, article_id: str = None) -> str:
        """Generate output path for image"""
        if article_id:
            filename = f"cover_{article_id}.png"
        else:
            slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:50]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cover_{timestamp}_{slug}.png"

        return str(self.output_dir / filename)

    def get_browser_automation_sequence(self, prompt: str, output_path: str) -> Dict:
        """Browser automation steps for Claude Code"""
        return {
            "description": "Generate cover image via Gemini Imagen 3",
            "output_path": output_path,
            "steps": [
                {
                    "step": 1,
                    "tool": "mcp__claude-in-chrome__tabs_context_mcp",
                    "params": {"createIfEmpty": True},
                },
                {
                    "step": 2,
                    "tool": "mcp__claude-in-chrome__tabs_create_mcp",
                    "params": {},
                },
                {
                    "step": 3,
                    "tool": "mcp__claude-in-chrome__navigate",
                    "params": {"url": "https://gemini.google.com/app"},
                },
                {
                    "step": 4,
                    "tool": "mcp__claude-in-chrome__computer",
                    "params": {"action": "wait", "duration": 3},
                },
                {
                    "step": 5,
                    "tool": "mcp__claude-in-chrome__read_page",
                    "params": {"filter": "interactive"},
                },
                {
                    "step": 6,
                    "tool": "mcp__claude-in-chrome__find",
                    "params": {"query": "message input"},
                },
                {
                    "step": 7,
                    "tool": "mcp__claude-in-chrome__form_input",
                    "note": "Enter prompt here",
                },
                {
                    "step": 8,
                    "tool": "mcp__claude-in-chrome__computer",
                    "params": {"action": "key", "text": "Enter"},
                },
                {
                    "step": 9,
                    "tool": "mcp__claude-in-chrome__computer",
                    "params": {"action": "wait", "duration": 45},
                },
                {
                    "step": 10,
                    "tool": "mcp__claude-in-chrome__computer",
                    "params": {"action": "screenshot"},
                },
            ],
            "prompt": prompt,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLE: How Claude should use this
# ═══════════════════════════════════════════════════════════════════════════════

USAGE_EXAMPLE = """
HOW CLAUDE SHOULD USE THIS GENERATOR:

1. RECEIVE article (title, summary, full_content, category)

2. GET reasoning framework:
   generator = GeminiImageGenerator()
   framework = generator.build_reasoning_prompt(title, summary, content, category)

3. REASON about the article (Claude thinks):
   - Central theme: "Coretax system is broken, people can't register NPWP"
   - Emotional core: "Frustration → finding workarounds"
   - The moment: "Person refreshing the page for the 10th time" OR "Going to KPP office as backup"
   - Universal: Yes - anyone who's dealt with broken government websites relates
   - 2-second test: Loading spinner on screen = immediately understood

4. DECIDE on scene:
   "Close-up of person pressing refresh, loading spinner visible, frustrated but determined expression,
    Bali home office setting, cold coffee forgotten nearby"

5. CREATE final prompt:
   prompt = generator.create_gemini_prompt(
       scene_description="Close-up of person pressing refresh...",
       mood="Relatable frustration, determination, 'we've all been there'",
       category="tax",
       key_details=["Loading spinner on screen", "Finger on F5 key", "Cold coffee cup", "Bali view through window"]
   )

6. EXECUTE browser automation to generate image

THE KEY: Claude THINKS about each article individually.
No random selection from predefined list.
Each image is crafted for THAT specific article.
"""


if __name__ == "__main__":
    print("=" * 70)
    print("GEMINI IMAGE GENERATOR - Reasoning Framework")
    print("=" * 70)
    print(USAGE_EXAMPLE)
    print("=" * 70)
