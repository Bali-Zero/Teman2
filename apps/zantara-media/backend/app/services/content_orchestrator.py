"""
ZANTARA MEDIA - Content Orchestrator
Automated pipeline: Intel → AI Generation → Image → Publication → Distribution

This is the CORE automation service that runs daily to produce Bali Zero Journal content.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

from app.models import ContentType, ContentCategory, ContentStatus
from app.db.content_repository import content_repository
from app.integrations.intel_client import intel_client
from app.services.ai_engine import ai_engine
from app.services.google_ai import google_ai_service
from app.services.imagine_art import imagine_art_service

logger = logging.getLogger(__name__)


class ContentOrchestrator:
    """
    Orchestrates the full automated content pipeline.

    Daily Workflow:
    1. Fetch intel signals from bali-intel-scraper
    2. Generate articles using AI (with fallback chain)
    3. Generate cover images using Google Imagen or ImagineArt
    4. Publish to database
    5. Schedule distribution across platforms
    """

    def __init__(self):
        self.daily_target_articles = 5  # Articles per day
        self.min_priority = 7  # Only process high-priority signals

    async def run_daily_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete daily content generation pipeline.

        Returns:
            Dict: Statistics about the run
        """
        start_time = datetime.utcnow()
        logger.info("=" * 80)
        logger.info("BALI ZERO JOURNAL - Daily Content Pipeline Starting")
        logger.info("=" * 80)

        stats = {
            "started_at": start_time.isoformat(),
            "intel_signals_fetched": 0,
            "articles_generated": 0,
            "images_generated": 0,
            "articles_published": 0,
            "errors": [],
            "articles_created": [],
        }

        try:
            # Step 1: Fetch intel signals
            logger.info("\n[Step 1] Fetching intel signals...")
            signals = await self._fetch_intel_signals()
            stats["intel_signals_fetched"] = len(signals)
            logger.info(f"✓ Fetched {len(signals)} high-priority intel signals")

            if not signals:
                logger.warning("No intel signals found. Ending pipeline.")
                stats["completed_at"] = datetime.utcnow().isoformat()
                stats["duration_seconds"] = (
                    datetime.utcnow() - start_time
                ).total_seconds()
                return stats

            # Step 2: Generate articles from intel
            logger.info(
                f"\n[Step 2] Generating {min(len(signals), self.daily_target_articles)} articles..."
            )
            articles = []

            for i, signal in enumerate(signals[: self.daily_target_articles]):
                try:
                    logger.info(
                        f"\n  → Article {i + 1}/{min(len(signals), self.daily_target_articles)}: {signal['title'][:60]}..."
                    )

                    # Generate article
                    article = await self._generate_article_from_signal(signal)
                    articles.append(article)
                    stats["articles_generated"] += 1
                    stats["articles_created"].append(
                        {
                            "id": str(article["id"]),
                            "title": article["title"],
                            "category": article["category"],
                        }
                    )

                    logger.info(f"    ✓ Article generated: {article['title'][:60]}...")

                except Exception as e:
                    logger.error(f"    ✗ Failed to generate article: {e}")
                    stats["errors"].append(
                        f"Article generation failed for signal {signal.get('id', 'unknown')}: {str(e)}"
                    )
                    continue

            logger.info(f"✓ Generated {len(articles)} articles")

            # Step 3: Generate images for articles
            logger.info("\n[Step 3] Generating cover images...")
            for i, article in enumerate(articles):
                try:
                    logger.info(
                        f"  → Image {i + 1}/{len(articles)}: {article['title'][:60]}..."
                    )

                    # Generate cover image
                    image_url = await self._generate_cover_image(article)
                    stats["images_generated"] += 1

                    logger.info("    ✓ Image generated")

                except Exception as e:
                    logger.error(f"    ✗ Failed to generate image: {e}")
                    stats["errors"].append(
                        f"Image generation failed for article {article['id']}: {str(e)}"
                    )
                    # Continue even if image generation fails

            logger.info(f"✓ Generated {stats['images_generated']} images")

            # Step 4: Publish articles
            logger.info("\n[Step 4] Publishing articles...")
            for article in articles:
                try:
                    # Mark as ready for review (can be auto-approved if desired)
                    await content_repository.update_content_status(
                        content_id=UUID(article["id"]),
                        status=ContentStatus.REVIEW,
                    )

                    # For now, auto-approve AI-generated content
                    # In production, you might want manual review
                    await content_repository.update_content_status(
                        content_id=UUID(article["id"]),
                        status=ContentStatus.APPROVED,
                        approved_by="auto_pipeline",
                    )

                    # Publish immediately
                    await content_repository.update_content_status(
                        content_id=UUID(article["id"]),
                        status=ContentStatus.PUBLISHED,
                    )

                    stats["articles_published"] += 1
                    logger.info(f"  ✓ Published: {article['title'][:60]}...")

                except Exception as e:
                    logger.error(f"  ✗ Failed to publish: {e}")
                    stats["errors"].append(
                        f"Publication failed for article {article['id']}: {str(e)}"
                    )

            logger.info(f"✓ Published {stats['articles_published']} articles")

            # Step 5: Schedule distribution (for tomorrow)
            logger.info("\n[Step 5] Scheduling distributions...")
            # This will be handled by the distribution service
            # For now, just log
            logger.info(f"  → {len(articles)} articles ready for distribution")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            stats["errors"].append(f"Pipeline error: {str(e)}")

        # Final stats
        end_time = datetime.utcnow()
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()

        logger.info("\n" + "=" * 80)
        logger.info("BALI ZERO JOURNAL - Daily Pipeline Completed")
        logger.info(f"  Duration: {stats['duration_seconds']:.2f}s")
        logger.info(f"  Signals: {stats['intel_signals_fetched']}")
        logger.info(f"  Articles Generated: {stats['articles_generated']}")
        logger.info(f"  Images Generated: {stats['images_generated']}")
        logger.info(f"  Articles Published: {stats['articles_published']}")
        logger.info(f"  Errors: {len(stats['errors'])}")
        logger.info("=" * 80)

        return stats

    async def _fetch_intel_signals(self) -> List[Dict[str, Any]]:
        """
        Fetch high-priority intel signals.

        Returns:
            List of intel signal dictionaries
        """
        # First, check database for unprocessed signals
        db_signals = await content_repository.get_pending_intel_signals(
            limit=self.daily_target_articles * 2,  # Fetch extra in case some fail
            min_priority=self.min_priority,
        )

        if db_signals:
            logger.info(f"  Found {len(db_signals)} signals in database")
            return db_signals

        # If no DB signals, fetch from intel scraper API
        logger.info("  No signals in DB, fetching from Intel Scraper...")
        try:
            signals = await intel_client.fetch_signals(
                limit=self.daily_target_articles * 2,
                min_priority=self.min_priority,
            )

            # Store them in database
            for signal_data in signals:
                try:
                    await content_repository.create_intel_signal(
                        title=signal_data["title"],
                        summary=signal_data["summary"],
                        category=ContentCategory(signal_data["category"]),
                        source_name=signal_data["source_name"],
                        source_url=signal_data.get("source_url"),
                        source_tier=signal_data.get("source_tier"),
                        confidence_score=signal_data.get("confidence_score"),
                        priority=signal_data.get("priority", 5),
                        tags=signal_data.get("tags", []),
                        raw_data=signal_data,
                    )
                except Exception as e:
                    logger.error(f"Failed to store signal: {e}")

            return signals

        except Exception as e:
            logger.error(f"Failed to fetch signals from API: {e}")
            return []

    async def _generate_article_from_signal(
        self, signal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a full article from an intel signal.

        Args:
            signal: Intel signal dictionary

        Returns:
            Dict: Created article data
        """
        # Build article generation prompt
        prompt = self._build_article_prompt(signal)

        # Generate article using AI engine (with fallback chain)
        logger.info("    Generating article with AI...")
        article_text, model_used = await ai_engine.generate_with_fallback(prompt)

        # Parse the generated article
        parsed = self._parse_article_response(article_text)

        # Calculate metadata
        word_count = len(parsed["body"].split())
        reading_time = max(1, word_count // 200)

        # Generate a slug
        slug = self._generate_slug(parsed["title"])

        # Create article in database
        article = await content_repository.create_content(
            title=parsed["title"],
            slug=slug,
            body=parsed["body"],
            summary=parsed["summary"],
            content_type=ContentType.ARTICLE,
            category=ContentCategory(signal.get("category", "GENERAL")),
            tags=[
                signal.get("category", "general"),
                "ai-generated",
                "bali-zero-journal",
            ],
            author_name="Bali Zero AI",
            word_count=word_count,
            reading_time_minutes=reading_time,
            ai_generated=True,
            ai_model=model_used,
            source_signal_id=str(signal.get("id")) if signal.get("id") else None,
            seo_title=parsed["title"][:60],
            seo_description=parsed["summary"][:160],
        )

        # Mark signal as processed
        if signal.get("id"):
            try:
                await content_repository.mark_intel_signal_processed(
                    signal_id=UUID(signal["id"]),
                    action="content_created",
                    content_id=UUID(article["id"]),
                )
            except Exception as e:
                logger.warning(f"Could not mark signal as processed: {e}")

        return article

    async def _generate_cover_image(self, article: Dict[str, Any]) -> str:
        """
        Generate a cover image for an article.

        Args:
            article: Article dictionary

        Returns:
            str: Image URL
        """
        # Build image generation prompt
        image_prompt = self._build_image_prompt(article)

        try:
            # Try Google Imagen first
            logger.info("    Trying Google Imagen...")
            result = await google_ai_service.generate_image(
                prompt=image_prompt,
                aspect_ratio="16:9",
            )

            if result.success and result.data:
                # Save image as media asset
                image_url = f"data:image/png;base64,{result.data.decode('utf-8') if isinstance(result.data, bytes) else result.data}"

                await content_repository.create_media_asset(
                    content_id=UUID(article["id"]),
                    asset_type="image",
                    storage_url=image_url,
                    generated_by="google_imagen",
                    generation_prompt=image_prompt,
                    width=result.width,
                    height=result.height,
                )

                # Update article with cover image
                # Note: This would need a method in content_repository
                # For now, we'll skip the update

                return image_url

        except Exception as e:
            logger.warning(f"    Google Imagen failed: {e}")

        try:
            # Fallback to ImagineArt
            logger.info("    Trying ImagineArt...")
            result = await imagine_art_service.generate_image(
                prompt=image_prompt,
                style="realistic",
                aspect_ratio="16:9",
            )

            if result.success and result.url:
                await content_repository.create_media_asset(
                    content_id=UUID(article["id"]),
                    asset_type="image",
                    storage_url=result.url,
                    generated_by="imagineart",
                    generation_prompt=image_prompt,
                    width=result.width,
                    height=result.height,
                )

                return result.url

        except Exception as e:
            logger.warning(f"    ImagineArt failed: {e}")

        # If both fail, return placeholder
        logger.warning("    All image generation failed, using placeholder")
        return "https://placehold.co/1920x1080/png?text=Bali+Zero+Journal"

    def _build_article_prompt(self, signal: Dict[str, Any]) -> str:
        """Build the prompt for article generation."""
        category = signal.get("category", "GENERAL")
        title = signal.get("title", "Untitled")
        summary = signal.get("summary", "")

        prompt = f"""You are a professional journalist writing for Bali Zero Journal, a premium publication for expats and digital nomads in Bali, Indonesia.

Write a comprehensive, well-researched article about the following topic:

**Topic**: {title}
**Category**: {category}
**Source Summary**: {summary}

**Requirements**:
1. Write in a professional, informative tone
2. Target audience: Expats, digital nomads, and foreigners living in or moving to Bali
3. Length: 600-800 words
4. Include practical, actionable information
5. Cite sources when mentioning specific regulations or data
6. Use clear section headings
7. End with a brief "Key Takeaways" section

**Format your response as**:
TITLE: [Article Title]

SUMMARY: [2-3 sentence summary]

BODY:
[Full article text with headings and paragraphs]

Begin writing:"""

        return prompt

    def _parse_article_response(self, text: str) -> Dict[str, str]:
        """Parse AI-generated article response."""
        lines = text.split("\n")

        title = ""
        summary = ""
        body_lines = []
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
                current_section = "title"
            elif line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
                current_section = "summary"
            elif line.startswith("BODY:"):
                current_section = "body"
            elif current_section == "body":
                body_lines.append(line)
            elif current_section == "summary" and not line.startswith("BODY:"):
                summary += " " + line

        body = "\n\n".join(body_lines) if body_lines else text

        # Fallback if parsing failed
        if not title:
            title = body_lines[0] if body_lines else "Untitled Article"

        if not summary:
            summary = (
                " ".join(body_lines[:3])[:200] if body_lines else "No summary available"
            )

        return {
            "title": title,
            "summary": summary,
            "body": body,
        }

    def _build_image_prompt(self, article: Dict[str, Any]) -> str:
        """Build prompt for image generation."""
        title = article.get("title", "")
        category = article.get("category", "general")

        # Category-specific image styles
        style_map = {
            "IMMIGRATION": "professional visa documents, passport, Indonesian immigration office",
            "TAX": "business accounting, tax documents, professional financial setting",
            "BUSINESS": "modern Indonesian business environment, professional setting",
            "PROPERTY": "beautiful Bali property, villa, real estate",
            "LEGAL": "legal documents, professional law office in Indonesia",
            "BALI_NEWS": "scenic Bali landscape, local culture and community",
            "LIFESTYLE": "tropical Bali lifestyle, beach, palm trees, expat living",
            "GENERAL": "modern Bali, tropical island, Indonesian culture",
        }

        style = style_map.get(category, style_map["GENERAL"])

        prompt = f"""Professional editorial photograph for an article titled "{title}".
Style: {style}.
High quality, professional journalism photography, natural lighting, realistic,
suitable for a premium publication. No text or watermarks."""

        return prompt

    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug."""
        import re

        slug = title.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        # Add date prefix for uniqueness
        date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
        return f"{date_prefix}-{slug}"[:100]


# Singleton instance
content_orchestrator = ContentOrchestrator()
