"""
BALI ZERO JOURNAL ORCHESTRATOR
Complete pipeline: Scraping → Filtering → Article Generation → Image Generation → PostgreSQL Upload

Handles 600+ sources across 12 categories
Cost: ~$0.0004 per article + ~$0.03 per image (91% cheaper than Claude-only)
"""

from pathlib import Path
import time
import asyncio
from typing import List, Dict, Optional
from loguru import logger
import argparse
import json
from datetime import datetime

# Import our modules
from unified_scraper import BaliZeroScraper
from ai_journal_generator import AIJournalGenerator


class BaliZeroOrchestrator:
    """
    Complete orchestration of Bali Zero Intelligence System
    Stage 1: Web Scraping (600+ sources) with date filtering
    Stage 2: AI Pre-filtering & Article Generation (Llama + Gemini + Claude)
    Stage 2.5: Image Generation (Google Imagen + ImagineArt fallback)
    Stage 3: PostgreSQL Vector Upload (optional)
    """

    def __init__(
        self, config_path: str = "config/categories.json", dry_run: bool = False
    ):
        self.config_path = config_path
        self.dry_run = dry_run

        # Initialize components
        self.scraper = BaliZeroScraper(config_path=config_path)
        self.generator = AIJournalGenerator()

        # Directories
        self.raw_dir = Path("data/raw")
        self.articles_dir = Path("data/articles")
        self.articles_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint system
        self.checkpoint_dir = Path("data/checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / "pipeline_checkpoint.json"
        self.checkpoint = self._load_checkpoint()

        logger.info("🚀 Bali Zero Orchestrator initialized")
        if self.checkpoint:
            logger.info(
                f"📍 Checkpoint loaded: {self.checkpoint.get('run_id', 'unknown')}"
            )

    def run_stage1_scraping(
        self, categories: Optional[List[str]] = None, limit: int = 10
    ) -> Dict:
        """
        STAGE 1: Web Scraping (Async optimized with httpx)
        Scrapes 600+ sources across 12 categories in parallel
        """

        logger.info("=" * 70)
        logger.info("📰 STAGE 1: WEB SCRAPING (ASYNC)")
        logger.info("=" * 70)

        if self.dry_run:
            logger.warning("⚠️  DRY RUN MODE - Skipping actual scraping")
            return {"success": True, "dry_run": True}

        # Run async scraper with asyncio.run()
        results = asyncio.run(
            self.scraper.scrape_all_categories(limit=limit, categories=categories)
        )

        logger.success(f"✅ Stage 1 complete: {results['total_scraped']} items scraped")

        return results

    def run_stage2_generation(
        self, categories: Optional[List[str]] = None, max_articles: int = 100
    ) -> Dict:
        """
        STAGE 2: AI Article Generation
        Transforms raw scraped content into professional journal articles
        Uses 3-tier AI fallback for optimal cost/quality
        """

        logger.info("=" * 70)
        logger.info("🤖 STAGE 2: AI ARTICLE GENERATION")
        logger.info("=" * 70)

        if self.dry_run:
            logger.warning("⚠️  DRY RUN MODE - Skipping article generation")
            return {"success": True, "dry_run": True}

        # Find all raw files
        raw_files = []

        if categories:
            for category in categories:
                category_dir = self.raw_dir / category
                if category_dir.exists():
                    raw_files.extend(list(category_dir.glob("*.md")))
        else:
            raw_files = list(self.raw_dir.glob("**/*.md"))

        logger.info(f"📄 Found {len(raw_files)} raw files to process")

        # Limit processing
        if len(raw_files) > max_articles:
            logger.warning(f"⚠️  Limiting to {max_articles} articles")
            raw_files = raw_files[:max_articles]

        # Process each file
        processed = 0
        failed = 0
        processed_files = (
            self.checkpoint.get("data", {}).get("processed_files", [])
            if self.checkpoint
            else []
        )

        for raw_file in raw_files:
            # Skip if already processed (checkpoint resume)
            if str(raw_file) in processed_files:
                logger.info(f"⏭️  Skipping (checkpoint): {raw_file.name}")
                processed += 1
                continue

            logger.info(f"\n📝 Processing: {raw_file.name}")

            result = self.generator.generate_article(
                raw_file=raw_file, output_dir=self.articles_dir
            )

            if result["success"]:
                processed += 1
                processed_files.append(str(raw_file))
                # Save checkpoint after each successful processing
                self._save_checkpoint(
                    "stage2_generation",
                    {
                        "processed_files": processed_files,
                        "processed_count": processed,
                        "failed_count": failed,
                    },
                )
            else:
                failed += 1

            time.sleep(2)  # Rate limiting

        # Get final metrics
        metrics = self.generator.get_metrics()

        logger.info("=" * 70)
        logger.success("✅ STAGE 2 COMPLETE")
        logger.info(f"📊 Processed: {processed}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"💰 Total Cost: ${metrics.get('total_cost_usd', 0):.4f}")

        # Only show detailed metrics if articles were processed
        if processed > 0:
            logger.info(
                f"💰 Avg Cost/Article: ${metrics.get('avg_cost_per_article', 0):.6f}"
            )
            logger.info(
                f"💰 Savings vs Haiku-only: {metrics.get('savings_percentage', 'N/A')}"
            )
            logger.info(
                f"🦙 Llama Success Rate: {metrics.get('llama_success_rate', 'N/A')}"
            )
        logger.info("=" * 70)

        return {
            "success": True,
            "processed": processed,
            "failed": failed,
            "metrics": metrics,
        }

    def run_stage25_image_generation(
        self, categories: Optional[List[str]] = None
    ) -> Dict:
        """
        STAGE 2.5: Image Generation
        Generates professional cover images for articles using AI
        """
        import asyncio

        logger.info("=" * 70)
        logger.info("🎨 STAGE 2.5: IMAGE GENERATION")
        logger.info("=" * 70)

        if self.dry_run:
            logger.warning("⚠️  DRY RUN MODE - Skipping image generation")
            return {"success": True, "dry_run": True}

        # Find all generated articles
        article_files = []

        if categories:
            for category in categories:
                category_dir = self.articles_dir / category
                if category_dir.exists():
                    article_files.extend(list(category_dir.glob("*.md")))
        else:
            article_files = list(self.articles_dir.glob("**/*.md"))

        logger.info(f"📄 Found {len(article_files)} articles")

        # Import image generator
        from image_generator import ImageGenerator

        async def generate_all_images():
            generator = ImageGenerator()
            generated = 0
            failed = 0
            skipped = 0

            for article_file in article_files:
                # Check if image already exists
                img_path = article_file.with_suffix(".png")
                if img_path.exists():
                    logger.info(f"⏭️  Image exists: {article_file.name}")
                    skipped += 1
                    continue

                logger.info(f"🎨 Generating image for: {article_file.name}")

                # Parse article for title and category
                import re

                content = article_file.read_text()
                metadata_match = re.search(r"---\n(.*?)\n---", content, re.DOTALL)

                if metadata_match:
                    metadata_str = metadata_match.group(1)
                    metadata = {}
                    for line in metadata_str.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            metadata[key.strip()] = value.strip()
                else:
                    metadata = {}

                # Extract title from content
                title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                title = (
                    title_match.group(1)
                    if title_match
                    else metadata.get("title", "Bali Business News")
                )

                category = metadata.get("category", article_file.parent.name)

                # Generate image
                result = await generator.generate_article_cover(
                    title=title, category=category, output_path=img_path
                )

                if result["success"]:
                    generated += 1
                    logger.success(
                        f"✅ Image saved: {img_path.name} (provider: {result.get('provider')})"
                    )
                else:
                    failed += 1
                    logger.error(f"❌ Failed: {result.get('error')}")

                await asyncio.sleep(1)  # Rate limiting

            return {
                "generated": generated,
                "failed": failed,
                "skipped": skipped,
                "metrics": generator.get_metrics(),
            }

        # Run async generation
        result = asyncio.run(generate_all_images())

        logger.info("=" * 70)
        logger.success("✅ STAGE 2.5 COMPLETE")
        logger.info(f"🎨 Generated: {result['generated']}")
        logger.info(f"⏭️  Skipped (exists): {result['skipped']}")
        logger.info(f"❌ Failed: {result['failed']}")
        logger.info(f"💰 Total Cost: ${result['metrics']['total_cost_usd']:.4f}")
        logger.info("=" * 70)

        return {"success": True, **result}

    def run_stage3_vector_upload(
        self,
        categories: Optional[List[str]] = None,
        max_per_category: Optional[int] = None,
    ) -> Dict:
        """
        STAGE 3: Vector DB Upload
        Uploads generated articles to NUZANTARA PostgreSQL for semantic search
        """
        import asyncio
        from vector_uploader import run_stage3_upload

        logger.info("=" * 70)
        logger.info("📊 STAGE 3: VECTOR DB UPLOAD")
        logger.info("=" * 70)

        if self.dry_run:
            logger.warning("⚠️  DRY RUN MODE - Skipping vector upload")
            return {"success": True, "dry_run": True}

        # Run async upload
        result = asyncio.run(run_stage3_upload(categories, max_per_category))

        logger.success(f"✅ Stage 3 complete: {result['total_uploaded']} uploaded")

        return result

    def run_full_pipeline(
        self,
        categories: Optional[List[str]] = None,
        scrape_limit: int = 10,
        max_articles: int = 100,
        skip_scraping: bool = False,
        skip_generation: bool = False,
        skip_images: bool = False,
        skip_upload: bool = True,
    ) -> Dict:
        """
        Run the complete pipeline with all stages
        """

        logger.info("=" * 80)
        logger.info("🌟 BALI ZERO JOURNAL - FULL PIPELINE EXECUTION")
        logger.info("=" * 80)

        start_time = time.time()
        results = {}

        # Stage 1: Scraping (with date filtering)
        if not skip_scraping:
            results["stage1"] = self.run_stage1_scraping(
                categories=categories, limit=scrape_limit
            )
        else:
            logger.warning("⏭️  Skipping Stage 1 (Scraping)")
            results["stage1"] = {"skipped": True}

        # Stage 2: Article Generation (with AI pre-filtering)
        if not skip_generation:
            results["stage2"] = self.run_stage2_generation(
                categories=categories, max_articles=max_articles
            )
        else:
            logger.warning("⏭️  Skipping Stage 2 (Generation)")
            results["stage2"] = {"skipped": True}

        # Stage 2.5: Image Generation
        if not skip_images and not skip_generation:
            results["stage2.5"] = self.run_stage25_image_generation(
                categories=categories
            )
        else:
            if skip_images:
                logger.warning("⏭️  Skipping Stage 2.5 (Images)")
            results["stage2.5"] = {"skipped": True}

        # Stage 3: PostgreSQL Vector Upload
        if not skip_upload:
            results["stage3"] = self.run_stage3_vector_upload(categories=categories)
        else:
            logger.warning("⏭️  Skipping Stage 3 (Vector DB)")
            results["stage3"] = {"skipped": True}

        duration = time.time() - start_time

        # Final Summary
        logger.info("=" * 80)
        logger.success("🎉 PIPELINE COMPLETE")
        logger.info(f"⏱️  Total Duration: {duration:.1f}s")
        logger.info("📊 Summary:")

        if (
            not skip_scraping
            and "stage1" in results
            and not results["stage1"].get("skipped")
        ):
            logger.info(
                f"  Stage 1 - Scraped: {results['stage1'].get('total_scraped', 0)} items"
            )

        if (
            not skip_generation
            and "stage2" in results
            and not results["stage2"].get("skipped")
        ):
            s2 = results["stage2"]
            logger.info(f"  Stage 2 - Generated: {s2.get('processed', 0)} articles")
            if "metrics" in s2:
                logger.info(
                    f"  Stage 2 - Cost: ${s2['metrics'].get('total_cost_usd', 0):.4f}"
                )
                logger.info(
                    f"  Stage 2 - Filtered: {s2['metrics'].get('filter_efficiency', 'N/A')}"
                )
                logger.info(
                    f"  Stage 2 - Savings: {s2['metrics'].get('savings_percentage', 'N/A')}"
                )

        if (
            not skip_images
            and "stage2.5" in results
            and not results["stage2.5"].get("skipped")
        ):
            s25 = results["stage2.5"]
            logger.info(f"  Stage 2.5 - Images: {s25.get('generated', 0)} generated")
            if "metrics" in s25:
                logger.info(
                    f"  Stage 2.5 - Cost: ${s25['metrics']['total_cost_usd']:.4f}"
                )

        logger.info("📁 Output Directories:")
        logger.info("  Raw scraped data: data/raw/")
        logger.info("  Generated articles: data/articles/")
        logger.info("  Cover images: data/articles/*/*.png")
        logger.info("=" * 80)

        # Clear checkpoint on successful completion
        self._clear_checkpoint()

        return {"success": True, "duration_seconds": duration, "results": results}

    def _load_checkpoint(self) -> Dict:
        """Load checkpoint from disk if exists"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                    logger.info(
                        f"✅ Loaded checkpoint from {checkpoint.get('timestamp', 'unknown')}"
                    )
                    return checkpoint
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
                return {}
        return {}

    def _save_checkpoint(self, stage: str, data: Dict):
        """Save checkpoint to disk"""
        try:
            checkpoint = {
                "run_id": self.checkpoint.get(
                    "run_id", datetime.now().strftime("%Y%m%d_%H%M%S")
                ),
                "timestamp": datetime.now().isoformat(),
                "stage": stage,
                "data": data,
            }
            with open(self.checkpoint_file, "w") as f:
                json.dump(checkpoint, f, indent=2)
            logger.debug(f"💾 Checkpoint saved: {stage}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def _clear_checkpoint(self):
        """Clear checkpoint after successful completion"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("🗑️  Checkpoint cleared")


def main():
    parser = argparse.ArgumentParser(description="Bali Zero Journal Orchestrator")

    # Pipeline control
    parser.add_argument(
        "--stage",
        choices=["all", "1", "2", "3"],
        default="all",
        help="Which stage to run",
    )
    parser.add_argument(
        "--categories", nargs="+", help="Specific categories to process"
    )
    parser.add_argument(
        "--scrape-limit", type=int, default=10, help="Max items to scrape per category"
    )
    parser.add_argument(
        "--max-articles", type=int, default=100, help="Max articles to generate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual scraping/generation)",
    )

    # Skipping options
    parser.add_argument(
        "--skip-scraping", action="store_true", help="Skip scraping stage"
    )
    parser.add_argument(
        "--skip-generation", action="store_true", help="Skip article generation stage"
    )
    parser.add_argument(
        "--skip-images", action="store_true", help="Skip image generation stage"
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        default=True,
        help="Skip PostgreSQL vector upload stage",
    )

    args = parser.parse_args()

    # Initialize orchestrator
    orchestrator = BaliZeroOrchestrator(dry_run=args.dry_run)

    # Run based on stage selection
    if args.stage == "all":
        orchestrator.run_full_pipeline(
            categories=args.categories,
            scrape_limit=args.scrape_limit,
            max_articles=args.max_articles,
            skip_scraping=args.skip_scraping,
            skip_generation=args.skip_generation,
            skip_images=args.skip_images,
            skip_upload=args.skip_upload,
        )
    elif args.stage == "1":
        orchestrator.run_stage1_scraping(
            categories=args.categories, limit=args.scrape_limit
        )
    elif args.stage == "2":
        orchestrator.run_stage2_generation(
            categories=args.categories, max_articles=args.max_articles
        )
    elif args.stage == "3":
        orchestrator.run_stage3_vector_upload()


# ============================================================================
# STANDALONE FUNCTIONS FOR API
# ============================================================================


def run_stage1_scraping(
    categories: Optional[List[str]] = None, limit: int = 10
) -> Dict:
    """Standalone function for Stage 1 (for API use) - async optimized."""
    orchestrator = BaliZeroOrchestrator()
    return orchestrator.run_stage1_scraping(categories, limit)


def run_stage2_generation(
    categories: Optional[List[str]] = None, max_articles: int = 100
) -> Dict:
    """Standalone function for Stage 2 (for API use)."""
    orchestrator = BaliZeroOrchestrator()
    return orchestrator.run_stage2_generation(categories, max_articles)


def run_stage3_upload(categories: Optional[List[str]] = None) -> Dict:
    """Standalone function for Stage 3 (for API use)."""
    orchestrator = BaliZeroOrchestrator()
    return orchestrator.run_stage3_vector_upload(categories)


if __name__ == "__main__":
    main()
