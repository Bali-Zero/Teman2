#!/usr/bin/env python3
"""
KG Monitoring Cron Runner - Phase 8

Daily cron job for monitoring legal websites and auto-ingesting changes.
Can be run as a standalone script or scheduled via cron.

Usage:
    python cron_runner.py [--check-only] [--source SOURCE] [--verbose]

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    REDIS_URL: Redis connection string (optional)
    SLACK_WEBHOOK_URL: Slack webhook for alerts
    QDRANT_URL: Qdrant vector DB URL
    LLM_API_KEY: API key for LLM service
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("kg_monitoring.cron")


async def run_monitoring(
    check_only: bool = False,
    source_filter: str | None = None,
    max_pages: int = 5,
) -> dict:
    """
    Run the full monitoring pipeline.

    Args:
        check_only: Only check for changes, don't ingest
        source_filter: Only process specific source
        max_pages: Maximum pages to scrape per source

    Returns:
        Dict with results summary
    """
    from backend.app.core.database import get_pool
    from backend.services.kg_monitoring import (
        AutoIngestionService,
        ChangeDetector,
        LegalScraper,
        QualityCheckService,
    )

    results = {
        "started_at": datetime.now().isoformat(),
        "sources_processed": 0,
        "documents_scraped": 0,
        "changes_detected": 0,
        "documents_ingested": 0,
        "errors": [],
        "completed_at": None,
    }

    logger.info("=" * 60)
    logger.info("🔍 KG MONITORING CRON JOB STARTED")
    logger.info("=" * 60)

    try:
        # Initialize database pool
        pool = await get_pool()
        logger.info("✅ Database connected")

        # Initialize components
        scraper = LegalScraper()
        detector = ChangeDetector(
            db_pool=pool,
            alert_on_change=True,
        )
        quality = QualityCheckService(min_accept_score=0.50)

        # Initialize ingestion service if not check-only
        ingestion = None
        if not check_only:
            ingestion = AutoIngestionService(
                db_pool=pool,
                quality_service=quality,
            )
            await ingestion.initialize_db()

        # Initialize DB tables
        await detector.initialize_db()
        logger.info("✅ Database tables initialized")

        # Get sources to process
        sources = list(scraper.sources.keys())
        if source_filter:
            sources = [s for s in sources if s == source_filter]
            if not sources:
                raise ValueError(f"Source not found: {source_filter}")

        logger.info(f"📋 Processing {len(sources)} source(s): {', '.join(sources)}")

        # Process each source
        for source_id in sources:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"🌐 Processing source: {source_id}")
                logger.info(f"{'='*60}")

                # Step 1: Scrape
                logger.info("📥 Step 1: Scraping documents...")
                documents = await scraper.scrape_source(
                    source_id=source_id,
                    max_pages=max_pages,
                )
                results["documents_scraped"] += len(documents)
                logger.info(f"✅ Scraped {len(documents)} documents")

                if not documents:
                    logger.info("No documents found, skipping...")
                    continue

                # Step 2: Detect changes
                logger.info("🔍 Step 2: Detecting changes...")
                changes = await detector.detect_changes(documents, source_id)
                significant_changes = [
                    c for c in changes
                    if c.change_type in ("new", "updated")
                ]
                results["changes_detected"] += len(significant_changes)
                logger.info(f"✅ Detected {len(significant_changes)} changes ({len(changes)} total)")

                # Step 3: Ingest changes (if not check-only)
                if not check_only and significant_changes:
                    logger.info("📥 Step 3: Ingesting changes...")

                    # Get documents that changed
                    changed_doc_ids = {c.document_id for c in significant_changes}
                    changed_docs = [d for d in documents if d.document_id in changed_doc_ids]

                    # Fetch full content for changed documents
                    logger.info("   Fetching full document content...")
                    for doc in changed_docs:
                        try:
                            await scraper.fetch_document_detail(doc)
                        except Exception as e:
                            logger.warning(f"   Failed to fetch detail for {doc.document_id}: {e}")

                    # Ingest
                    ingestion_results = await ingestion.ingest_batch(
                        changed_docs,
                        target_collection="legal_updates",
                    )

                    successful = sum(1 for r in ingestion_results if r.status.value == "completed")
                    results["documents_ingested"] += successful
                    logger.info(f"✅ Ingested {successful}/{len(changed_docs)} documents")

                results["sources_processed"] += 1

            except Exception as e:
                error_msg = f"Error processing source {source_id}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("📊 SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Sources processed: {results['sources_processed']}")
        logger.info(f"Documents scraped: {results['documents_scraped']}")
        logger.info(f"Changes detected: {results['changes_detected']}")
        if not check_only:
            logger.info(f"Documents ingested: {results['documents_ingested']}")
        logger.info(f"Errors: {len(results['errors'])}")

        results["completed_at"] = datetime.now().isoformat()

        logger.info(f"\n✅ KG MONITORING CRON JOB COMPLETED")
        logger.info(f"{'='*60}\n")

        return results

    except Exception as e:
        logger.error(f"Fatal error in monitoring job: {e}")
        results["errors"].append(f"Fatal error: {e}")
        raise

    finally:
        # Cleanup
        logger.info("🧹 Cleaning up...")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="KG Monitoring Cron Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python cron_runner.py                    # Full run
    python cron_runner.py --check-only       # Check only, no ingestion
    python cron_runner.py --source jdih_kemenkumham  # Single source
    python cron_runner.py --verbose          # Debug logging
        """,
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for changes, don't ingest",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Process only specific source",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum pages to scrape per source (default: 5)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Check required environment variables
    required_vars = ["DATABASE_URL"]
    missing_vars = [v for v in required_vars if not os.getenv(v)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Run
    try:
        results = asyncio.run(run_monitoring(
            check_only=args.check_only,
            source_filter=args.source,
            max_pages=args.max_pages,
        ))

        # Exit with error if there were errors
        if results.get("errors"):
            logger.warning(f"Completed with {len(results['errors'])} errors")
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Job failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
