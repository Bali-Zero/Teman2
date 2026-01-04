#!/usr/bin/env python3
"""
BALIZERO COMPLETE ENRICHMENT - Article + Cover Image
=====================================================
Workflow automatico eseguito da Claude Code con Max:

1. Claude Max scrive l'articolo completo (Executive Brief)
2. Claude Code apre Gemini nel browser
3. Imagen 3 genera la cover image artistica
4. Tutto viene salvato e inviato all'API

Questo script è progettato per essere eseguito DA Claude Code,
che ha accesso ai tool mcp__claude-in-chrome per browser automation.

Usage:
    # Claude Code esegue questo quando riceve un articolo da enrichire
    python enrich_with_image.py --url "https://..." --title "..." --category immigration
"""

import asyncio
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

# Configure logging
Path("logs").mkdir(exist_ok=True)
logger.add("logs/enrich_complete_{time}.log", rotation="1 day")


async def enrich_article_complete(
    url: str,
    title: str,
    summary: str = "",
    source: str = "Unknown",
    category: str = "business",
    api_key: Optional[str] = None,
    dry_run: bool = False,
) -> Dict:
    """
    Complete enrichment pipeline: Article + Image.

    Steps:
    1. Fetch full article from URL
    2. Claude Max writes Executive Brief
    3. Generate artistic image prompt
    4. Return everything for browser automation

    The browser automation (Gemini image gen) should be executed
    by Claude Code after this function returns.
    """
    logger.info("=" * 70)
    logger.info("🚀 BALIZERO COMPLETE ENRICHMENT")
    logger.info(f"📰 {title[:50]}...")
    logger.info("=" * 70)

    # Import enricher
    from article_deep_enricher import ArticleDeepEnricher

    # Initialize (with image generation enabled)
    enricher = ArticleDeepEnricher(generate_images=True)

    # Step 1 & 2: Enrich article with Claude Max
    logger.info("\n📝 Step 1: Writing article with Claude Max...")

    enriched = await enricher.enrich_article(
        title=title, summary=summary, source_url=url, source=source, category=category
    )

    if not enriched:
        logger.error("❌ Article enrichment failed")
        return {"success": False, "error": "enrichment_failed"}

    logger.success(f"✅ Article written: {enriched.headline}")

    # Step 3: Prepare image generation
    logger.info("\n🎨 Step 2: Preparing cover image generation...")

    from gemini_image_generator import GeminiImageGenerator

    image_gen = GeminiImageGenerator()

    image_prompt = image_gen.build_image_prompt(
        article_title=enriched.headline,
        article_summary=enriched.ai_summary,
        category=enriched.category,
    )

    # Generate output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "_", enriched.headline.lower())[:30]
    image_filename = f"cover_{timestamp}_{slug}.png"
    image_path = f"data/images/{image_filename}"

    Path("data/images").mkdir(parents=True, exist_ok=True)

    # Step 4: Format article as markdown
    markdown = enricher.format_as_markdown(enriched)

    # Save article locally
    article_path = f"data/enriched/{timestamp}_{slug}.md"
    Path("data/enriched").mkdir(parents=True, exist_ok=True)
    with open(article_path, "w") as f:
        f.write(markdown)
    logger.info(f"💾 Article saved: {article_path}")

    # Return complete result with browser automation instructions
    result = {
        "success": True,
        "article": {
            "headline": enriched.headline,
            "category": enriched.category,
            "priority": enriched.priority,
            "relevance_score": enriched.relevance_score,
            "markdown_path": article_path,
            "ai_summary": enriched.ai_summary,
            "ai_tags": enriched.ai_tags,
        },
        "image": {
            "prompt": image_prompt,
            "output_path": image_path,
            "filename": image_filename,
        },
        "browser_automation": {
            "required": True,
            "target": "gemini.google.com/app",
            "action": "generate_image",
            "prompt_to_enter": image_prompt,
            "save_image_to": image_path,
            "steps": [
                "Navigate to https://gemini.google.com/app",
                "Wait for page load (3 seconds)",
                "Find the message input textarea",
                "Enter the image prompt",
                "Press Enter to submit",
                "Wait 30-45 seconds for Imagen 3",
                "When image appears, take screenshot or save image",
                f"Save to: {image_path}",
            ],
        },
        "api_payload": {
            "title": enriched.headline,
            "content": markdown,
            "summary": enriched.ai_summary,
            "category": enriched.category,
            "priority": enriched.priority,
            "source": source,
            "source_url": url,
            "ai_tags": enriched.ai_tags,
            "relevance_score": enriched.relevance_score,
            "cover_image": image_path,  # Will be updated after browser automation
        },
    }

    # Save complete result
    result_path = f"data/enriched/{timestamp}_{slug}_complete.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Complete result: {result_path}")

    logger.info("\n" + "=" * 70)
    logger.info("✅ ENRICHMENT COMPLETE - Ready for browser automation")
    logger.info("=" * 70)
    logger.info("\n🎨 IMAGE GENERATION REQUIRED:")
    logger.info("   Target: gemini.google.com/app")
    logger.info(f"   Output: {image_path}")
    logger.info("\n   Claude Code should now execute browser automation")
    logger.info("   to generate the cover image with Gemini Imagen 3")
    logger.info("=" * 70)

    return result


# Browser automation prompt for Claude Code
BROWSER_AUTOMATION_PROMPT = """
After running enrich_with_image.py, execute this browser automation:

```
# 1. Get browser context
mcp__claude-in-chrome__tabs_context_mcp(createIfEmpty=True)

# 2. Create new tab
mcp__claude-in-chrome__tabs_create_mcp()

# 3. Navigate to Gemini
mcp__claude-in-chrome__navigate(url="https://gemini.google.com/app", tabId=<tab_id>)

# 4. Wait for load
mcp__claude-in-chrome__browser_wait_for(time=3, tabId=<tab_id>)

# 5. Find input field
mcp__claude-in-chrome__find(query="message input textarea", tabId=<tab_id>)

# 6. Enter the image prompt from result["image"]["prompt"]
mcp__claude-in-chrome__form_input(ref=<input_ref>, value=<prompt>, tabId=<tab_id>)

# 7. Submit
mcp__claude-in-chrome__computer(action="key", text="Enter", tabId=<tab_id>)

# 8. Wait for Imagen 3 (30-45 seconds)
mcp__claude-in-chrome__browser_wait_for(time=45, tabId=<tab_id>)

# 9. Take screenshot
mcp__claude-in-chrome__computer(action="screenshot", tabId=<tab_id>)

# 10. The screenshot is the cover image - save it to result["image"]["output_path"]
```
"""


async def main():
    parser = argparse.ArgumentParser(description="BaliZero Complete Enrichment")
    parser.add_argument("--url", required=True, help="Article URL")
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--summary", default="", help="Article summary")
    parser.add_argument("--source", default="Unknown", help="Source name")
    parser.add_argument(
        "--category",
        default="business",
        choices=[
            "immigration",
            "business",
            "tax",
            "property",
            "lifestyle",
            "legal",
            "tech",
        ],
        help="Article category",
    )
    parser.add_argument("--api-key", help="BaliZero API key")
    parser.add_argument("--dry-run", action="store_true", help="Don't send to API")

    args = parser.parse_args()

    result = await enrich_article_complete(
        url=args.url,
        title=args.title,
        summary=args.summary,
        source=args.source,
        category=args.category,
        api_key=args.api_key,
        dry_run=args.dry_run,
    )

    if result["success"]:
        print("\n" + "=" * 70)
        print("✅ ENRICHMENT COMPLETE")
        print("=" * 70)
        print(f"\n📰 Article: {result['article']['headline']}")
        print(f"📁 Saved to: {result['article']['markdown_path']}")
        print(f"\n🎨 Image prompt generated ({len(result['image']['prompt'])} chars)")
        print(f"📷 Save to: {result['image']['output_path']}")
        print("\n⚠️  NEXT: Execute browser automation to generate image")
        print("=" * 70)
    else:
        print(f"\n❌ Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
