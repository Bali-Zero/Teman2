#!/usr/bin/env python3
"""
Staging Processor - Auto-approve pending articles from staging
===============================================================

Reads articles from /data/staging/ and triggers Telegram approval workflow
by calling the backend's approval endpoint.

This processor runs as a background task and:
1. Scans /data/staging/news/ and /data/staging/visa/ for pending JSON files
2. For each file, calls POST /api/intel/staging/approve/{type}/{item_id}
3. Backend sends article to Telegram for team voting
4. Team votes (2/3 majority) → Auto-publish to Qdrant

Usage:
    # Run on Fly.io
    python scripts/staging_processor.py

    # Dry run
    python scripts/staging_processor.py --dry-run

    # Process only news (skip visa)
    python scripts/staging_processor.py --type news
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx
from loguru import logger

# Staging directories (on Fly.io persistent volume)
STAGING_BASE = Path("/data/staging")
NEWS_DIR = STAGING_BASE / "news"
VISA_DIR = STAGING_BASE / "visa"

# Backend URL (local loopback since we're on same machine)
BACKEND_URL = "http://localhost:8080"


class StagingProcessor:
    """Auto-approve pending articles from staging"""

    def __init__(self, dry_run: bool = False, type_filter: str = "all"):
        self.dry_run = dry_run
        self.type_filter = type_filter  # all, news, visa
        self.stats = {
            "news_found": 0,
            "visa_found": 0,
            "sent_to_telegram": 0,
            "errors": 0,
            "skipped": 0,
        }

    async def process_all_pending(self):
        """Process all pending files in staging"""
        logger.info("=" * 70)
        logger.info("🔄 STAGING AUTO-APPROVER - Processing pending articles")
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
        logger.info("✅ AUTO-APPROVE COMPLETE")
        logger.info("📊 Stats:")
        logger.info(f"   News found: {self.stats['news_found']}")
        logger.info(f"   Visa found: {self.stats['visa_found']}")
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
                logger.error(f"   ❌ Error processing {json_file.name}: {e}", exc_info=True)
                self.stats["errors"] += 1

    async def _process_file(self, json_file: Path, intel_type: str):
        """Process a single staging file by calling backend approval endpoint"""
        # Extract item_id from filename (e.g., "news_20260105_034315_68085c3c.json")
        item_id = json_file.stem

        logger.info(f"\n   📄 Processing: {item_id}")

        # Read article to get metadata for logging
        try:
            with open(json_file) as f:
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
            logger.info(
                f"      🧪 DRY RUN - Would call /api/intel/staging/approve/{intel_type}/{item_id}"
            )
            return

        # Call backend approval endpoint
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/api/intel/staging/approve/{intel_type}/{item_id}"
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.success("      ✅ Sent to Telegram for voting")
                    logger.info(f"      📱 Voting status: {result.get('voting_status', 'pending')}")
                    self.stats["sent_to_telegram"] += 1
                else:
                    error_detail = response.json().get("detail", response.text)
                    logger.error(f"      ❌ Approval failed: {error_detail}")
                    logger.error(f"      HTTP {response.status_code}")
                    self.stats["errors"] += 1

        except httpx.TimeoutException:
            logger.error("      ❌ Timeout calling approval endpoint")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"      ❌ Approval request failed: {e}")
            self.stats["errors"] += 1


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-approve pending articles from staging to Telegram"
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

    processor = StagingProcessor(dry_run=args.dry_run, type_filter=args.type)

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
