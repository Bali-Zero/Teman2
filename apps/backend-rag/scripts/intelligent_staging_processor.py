#!/usr/bin/env python3
"""
Intelligent Staging Processor
==============================

Auto-processes articles from staging with full AI enrichment:
1. Reads pending articles from /data/staging/
2. Enriches with Claude (catchy titles, summaries, key points)
3. Generates cover images with Gemini (browser automation)
4. Sends rich HTML notifications to Telegram with images
5. Team votes → Auto-publish to Intelligence Center

This is the COMPLETE pipeline for Bali Zero Intelligence.

Usage:
    # Run on Fly.io (has access to /data/staging/)
    python scripts/intelligent_staging_processor.py

    # Dry run (no Telegram send, no image generation)
    python scripts/intelligent_staging_processor.py --dry-run

    # Process only news (skip visa)
    python scripts/intelligent_staging_processor.py --type news
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
import httpx

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from services.intelligence.article_enrichment import ArticleEnrichmentService


# Staging directories (on Fly.io persistent volume)
STAGING_BASE = Path("/data/staging")
NEWS_DIR = STAGING_BASE / "news"
VISA_DIR = STAGING_BASE / "visa"
IMAGES_DIR = Path("/data/intelligence/images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Backend URL (local loopback since we're on same machine)
BACKEND_URL = "http://localhost:8080"


class IntelligentStagingProcessor:
    """
    Intelligent staging processor with full AI enrichment pipeline.
    """

    def __init__(self, dry_run: bool = False, type_filter: str = "all"):
        self.dry_run = dry_run
        self.type_filter = type_filter
        self.enrichment_service = ArticleEnrichmentService()
        self.stats = {
            "news_found": 0,
            "visa_found": 0,
            "enriched": 0,
            "images_generated": 0,
            "sent_to_telegram": 0,
            "errors": 0,
            "skipped": 0,
        }

    async def process_all_pending(self):
        """Process all pending files in staging with full AI pipeline"""
        logger.info("=" * 70)
        logger.info("🤖 INTELLIGENT STAGING PROCESSOR")
        logger.info(f"📅 {datetime.now().isoformat()}")
        logger.info(f"🧪 Dry run: {self.dry_run}")
        logger.info(f"🏷️  Filter: {self.type_filter}")
        logger.info("=" * 70)

        # Process news
        if self.type_filter in ["all", "news"] and NEWS_DIR.exists():
            await self._process_directory(NEWS_DIR, "news")
        elif self.type_filter == "news" and not NEWS_DIR.exists():
            logger.warning(f"❌ News directory not found: {NEWS_DIR}")

        # Process visa
        if self.type_filter in ["all", "visa"] and VISA_DIR.exists():
            await self._process_directory(VISA_DIR, "visa")
        elif self.type_filter == "visa" and not VISA_DIR.exists():
            logger.warning(f"❌ Visa directory not found: {VISA_DIR}")

        # Summary
        logger.info("=" * 70)
        logger.info("✅ PROCESSING COMPLETE")
        logger.info(f"📊 Stats:")
        logger.info(f"   News found: {self.stats['news_found']}")
        logger.info(f"   Visa found: {self.stats['visa_found']}")
        logger.info(f"   Enriched: {self.stats['enriched']}")
        logger.info(f"   Images generated: {self.stats['images_generated']}")
        logger.info(f"   Sent to Telegram: {self.stats['sent_to_telegram']}")
        logger.info(f"   Errors: {self.stats['errors']}")
        logger.info(f"   Skipped: {self.stats['skipped']}")
        logger.info("=" * 70)

        return self.stats

    async def _process_directory(self, directory: Path, intel_type: str):
        """Process all JSON files in a staging directory"""
        logger.info(f"\n📁 Processing {intel_type} directory: {directory}")

        # Find all JSON files (skip processed/ subdirectory)
        json_files = [f for f in directory.glob("*.json") if f.parent == directory]

        logger.info(f"   Found {len(json_files)} pending files")

        if intel_type == "news":
            self.stats["news_found"] = len(json_files)
        else:
            self.stats["visa_found"] = len(json_files)

        for json_file in json_files:
            try:
                await self._process_file(json_file, intel_type)
            except Exception as e:
                logger.error(
                    f"   ❌ Error processing {json_file.name}: {e}", exc_info=True
                )
                self.stats["errors"] += 1

    async def _process_file(self, json_file: Path, intel_type: str):
        """
        Process a single staging file with FULL AI pipeline:
        1. Read raw article
        2. Enrich with Claude
        3. Generate image with Gemini
        4. Send to Telegram with rich formatting
        """
        item_id = json_file.stem

        logger.info(f"\n   📄 Processing: {item_id}")

        # Read article to get metadata
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            title = data.get("title", "Untitled")
            status = data.get("status", "pending")
            source = data.get("source_name", "Unknown")

            logger.info(f"      Title: {title[:60]}...")
            logger.info(f"      Source: {source}")
            logger.info(f"      Status: {status}")

            # Skip if not pending
            if status != "pending":
                logger.info(f"      ⏭️ Skipped (already {status})")
                self.stats["skipped"] += 1
                return

        except Exception as e:
            logger.error(f"      ❌ Failed to read metadata: {e}")
            self.stats["errors"] += 1
            return

        if self.dry_run:
            logger.info(f"      🧪 DRY RUN - Would enrich and send to Telegram")
            return

        # STEP 1: Enrich article with Claude
        logger.info(f"      🤖 Enriching with Claude...")
        try:
            enriched_data = await self.enrichment_service.enrich_article(data)
            self.stats["enriched"] += 1

            logger.success(
                f"      ✅ Enriched: {enriched_data.get('enriched_title', '')[:50]}..."
            )

        except Exception as e:
            logger.error(f"      ❌ Enrichment failed: {e}")
            enriched_data = None

        # STEP 2: Generate image with Gemini (browser automation)
        image_path = None
        if enriched_data and enriched_data.get("image_prompt"):
            logger.info(f"      🎨 Generating image with Gemini...")
            try:
                image_path = await self._generate_image_gemini(
                    prompt=enriched_data["image_prompt"],
                    article_id=item_id
                )

                if image_path:
                    self.stats["images_generated"] += 1
                    logger.success(f"      ✅ Image saved: {image_path}")
                else:
                    logger.warning(f"      ⚠️ Image generation failed")

            except Exception as e:
                logger.error(f"      ❌ Image generation error: {e}")

        # STEP 3: Send to Telegram with rich formatting
        logger.info(f"      📱 Sending to Telegram...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Prepare payload with enriched data + image
                payload = {
                    "intel_type": intel_type,
                    "item_id": item_id,
                    "item_data": data,
                    "enriched_data": enriched_data,
                    "image_path": image_path,
                }

                response = await client.post(
                    f"{BACKEND_URL}/api/intel/staging/approve/{intel_type}/{item_id}",
                    json=payload,
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.success(f"      ✅ Sent to Telegram for voting")
                    self.stats["sent_to_telegram"] += 1
                else:
                    error_detail = response.json().get("detail", response.text)
                    logger.error(f"      ❌ Failed: {error_detail}")
                    logger.error(f"      HTTP {response.status_code}")
                    self.stats["errors"] += 1

        except httpx.TimeoutException:
            logger.error(f"      ❌ Timeout calling backend")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"      ❌ Request failed: {e}")
            self.stats["errors"] += 1

    async def _generate_image_gemini(
        self, prompt: str, article_id: str
    ) -> Optional[str]:
        """
        Generate image using Gemini via browser automation.

        NOTE: This is a PLACEHOLDER. The actual browser automation
        will be implemented using Claude in Chrome MCP tools.

        For now, returns None (no image). The pipeline will still work
        and send text-only notifications to Telegram.

        TODO: Implement browser automation:
        1. Open gemini.google.com/app
        2. Type image prompt
        3. Click generate
        4. Download image
        5. Save to IMAGES_DIR
        """
        logger.warning(
            "      ⚠️ Browser automation not yet implemented - skipping image generation"
        )
        logger.info(f"      📝 Image prompt: {prompt[:80]}...")

        # Future implementation will use MCP browser tools here
        # See gemini_image_generator.py for reference

        return None


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Intelligent staging processor with AI enrichment"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - show what would be processed without sending",
    )
    parser.add_argument(
        "--type",
        choices=["all", "news", "visa"],
        default="all",
        help="Process only specific type (default: all)",
    )

    args = parser.parse_args()

    processor = IntelligentStagingProcessor(
        dry_run=args.dry_run, type_filter=args.type
    )

    await processor.process_all_pending()


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
    )

    asyncio.run(main())
