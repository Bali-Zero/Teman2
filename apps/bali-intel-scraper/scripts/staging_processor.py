#!/usr/bin/env python3
"""
Staging Processor - Process articles from backend staging to Telegram
======================================================================

Reads articles from /data/staging/ (on Fly.io nuzantara-rag) and sends them
to Telegram for team voting approval.

Flow:
1. Read JSON files from /data/staging/news/ and /data/staging/visa/
2. For each article:
   - Send to Telegram for approval (no enrichment for speed)
   - Move to /data/staging/processed/
3. Team votes via Telegram (2/3 majority)
4. Approved articles get published to Qdrant

Usage:
    # Run locally (reads from remote Fly.io volume via API)
    python staging_processor.py

    # Run on Fly.io (direct access to /data/staging/)
    fly ssh console -a nuzantara-rag -C "cd /app && python scripts/staging_processor.py"

    # Dry run (no Telegram send, just show what would be processed)
    python staging_processor.py --dry-run
"""

import asyncio
import json
import os
import sys
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

try:
    from telegram_approval import TelegramApproval
except ImportError:
    logger.warning("telegram_approval.py not found - Telegram notifications disabled")
    TelegramApproval = None


# Backend API URL (where staging files are located)
BACKEND_URL = os.environ.get("BACKEND_URL", "https://nuzantara-rag.fly.dev")


class StagingProcessor:
    """Process articles from backend staging directory"""

    def __init__(
        self,
        staging_dir: Path = Path("/data/staging"),
        dry_run: bool = False
    ):
        self.staging_dir = staging_dir
        self.dry_run = dry_run

        # Initialize Telegram approval system
        if TelegramApproval:
            self.telegram = TelegramApproval()
        else:
            self.telegram = None
            logger.warning("Telegram approval disabled (module not found)")

        self.stats = {
            "news_found": 0,
            "visa_found": 0,
            "sent_to_telegram": 0,
            "errors": 0,
            "skipped": 0
        }

    async def process_staging_files(self):
        """Process all pending files in staging directories"""
        logger.info("=" * 70)
        logger.info("🔄 STAGING PROCESSOR - Processing pending articles")
        logger.info(f"📅 {datetime.now().isoformat()}")
        logger.info(f"📂 Staging dir: {self.staging_dir}")
        logger.info(f"🧪 Dry run: {self.dry_run}")
        logger.info("=" * 70)

        # Process news articles
        news_dir = self.staging_dir / "news"
        if news_dir.exists():
            await self._process_directory(news_dir, "news")
        else:
            logger.warning(f"News directory not found: {news_dir}")

        # Process visa articles
        visa_dir = self.staging_dir / "visa"
        if visa_dir.exists():
            await self._process_directory(visa_dir, "visa")
        else:
            logger.warning(f"Visa directory not found: {visa_dir}")

        # Summary
        logger.info("=" * 70)
        logger.info("✅ STAGING PROCESSING COMPLETE")
        logger.info(f"📊 Stats:")
        logger.info(f"   News found: {self.stats['news_found']}")
        logger.info(f"   Visa found: {self.stats['visa_found']}")
        logger.info(f"   Sent to Telegram: {self.stats['sent_to_telegram']}")
        logger.info(f"   Errors: {self.stats['errors']}")
        logger.info(f"   Skipped: {self.stats['skipped']}")
        logger.info("=" * 70)

        return self.stats

    async def _process_directory(self, directory: Path, category_type: str):
        """Process all JSON files in a directory"""
        logger.info(f"\n📁 Processing {category_type} directory: {directory}")

        json_files = list(directory.glob("*.json"))
        logger.info(f"   Found {len(json_files)} files")

        if category_type == "news":
            self.stats["news_found"] = len(json_files)
        else:
            self.stats["visa_found"] = len(json_files)

        for json_file in json_files:
            try:
                await self._process_file(json_file, category_type)
            except Exception as e:
                logger.error(f"   ❌ Error processing {json_file.name}: {e}")
                self.stats["errors"] += 1

    async def _process_file(self, json_file: Path, category_type: str):
        """Process a single staging file"""
        logger.info(f"\n   📄 Processing: {json_file.name}")

        # Read article data
        with open(json_file, "r") as f:
            data = json.load(f)

        title = data.get("title", "Untitled")
        content = data.get("content", "")
        source_url = data.get("source_url", "")
        source_name = data.get("source_name", "Unknown")
        category = data.get("category", category_type)
        relevance_score = data.get("relevance_score", 0)

        logger.info(f"      Title: {title[:60]}...")
        logger.info(f"      Source: {source_name}")
        logger.info(f"      Score: {relevance_score}")
        logger.info(f"      Category: {category}")

        # Skip if already processed (status != pending)
        status = data.get("status", "pending")
        if status != "pending":
            logger.info(f"      ⏭️ Skipped (status: {status})")
            self.stats["skipped"] += 1
            return

        if self.dry_run:
            logger.info(f"      🧪 DRY RUN - Would send to Telegram")
            return

        # Send to Telegram for approval
        if self.telegram:
            try:
                # Prepare article data for Telegram
                article_data = {
                    "title": title,
                    "content": content,
                    "enriched_content": content,  # No enrichment for speed
                    "category": category,
                    "source": source_name,
                    "source_url": source_url,
                    "image_url": "",  # No image for speed
                }

                # Simple SEO metadata (no full optimization)
                seo_metadata = {
                    "title": title,
                    "meta_description": content[:160] if content else "",
                    "keywords": [category, category_type],
                    "faq_items": [],
                    "reading_time_minutes": len(content.split()) // 200 if content else 1,
                }

                # Submit for approval
                pending = await self.telegram.submit_for_approval(
                    article=article_data,
                    seo_metadata=seo_metadata,
                    enriched_content=content
                )

                if pending and pending.telegram_message_id:
                    logger.success(f"      ✅ Sent to Telegram (ID: {pending.article_id})")
                    self.stats["sent_to_telegram"] += 1

                    # Move to processed
                    processed_dir = json_file.parent / "processed"
                    processed_dir.mkdir(exist_ok=True)
                    new_path = processed_dir / json_file.name
                    json_file.rename(new_path)
                    logger.info(f"      📦 Moved to: {new_path}")
                else:
                    logger.warning(f"      ⚠️ Telegram send failed (no message ID)")
                    self.stats["errors"] += 1

            except Exception as e:
                logger.error(f"      ❌ Telegram approval failed: {e}")
                self.stats["errors"] += 1
        else:
            logger.warning(f"      ⚠️ Telegram not configured - skipping")
            self.stats["skipped"] += 1


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Process staging articles to Telegram")
    parser.add_argument(
        "--staging-dir",
        default="/data/staging",
        help="Path to staging directory (default: /data/staging on Fly.io)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - show what would be processed without sending"
    )

    args = parser.parse_args()

    processor = StagingProcessor(
        staging_dir=Path(args.staging_dir),
        dry_run=args.dry_run
    )

    await processor.process_staging_files()


if __name__ == "__main__":
    asyncio.run(main())
