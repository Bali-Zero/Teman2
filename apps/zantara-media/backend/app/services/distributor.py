"""
ZANTARA MEDIA - Distributor Service
Handles content distribution across social media platforms
"""

import logging
from datetime import datetime
from typing import Optional
from app.models import (
    Distribution,
    DistributionStatus,
    DistributionPlatform,
    DistributionMetrics,
    Content,
    ContentType,
)
from app.integrations.nuzantara_client import nuzantara_client

logger = logging.getLogger(__name__)


class DistributorService:
    """
    Manages content distribution across multiple platforms.

    Supported platforms:
    - Twitter/X (threads, single posts)
    - LinkedIn (articles, posts)
    - Instagram (posts, stories, reels)
    - TikTok (videos)
    - Telegram (channel posts)
    - Newsletter (email campaigns)

    Features:
    - Cross-platform scheduling
    - Content adaptation per platform
    - Engagement tracking
    - Optimal timing suggestions
    """

    def __init__(self):
        self._distribution_store: dict[str, Distribution] = {}
        self._counter = 0

    def _generate_id(self) -> str:
        """Generate unique distribution ID."""
        self._counter += 1
        return f"dist_{self._counter}"

    # ============================================
    # DISTRIBUTION CREATION
    # ============================================

    async def create_distribution(
        self,
        content_id: str,
        platform: DistributionPlatform,
        scheduled_at: Optional[datetime] = None,
        custom_text: Optional[str] = None,
    ) -> Distribution:
        """
        Create a distribution for content to a platform.

        Args:
            content_id: ID of the content to distribute
            platform: Target platform
            scheduled_at: When to publish (None = immediate queue)
            custom_text: Custom text for this platform (overrides default)
        """
        dist_id = self._generate_id()

        status = (
            DistributionStatus.SCHEDULED if scheduled_at else DistributionStatus.PENDING
        )

        distribution = Distribution(
            id=dist_id,
            content_id=content_id,
            platform=platform,
            status=status,
            scheduled_at=scheduled_at,
            custom_text=custom_text,
        )

        self._distribution_store[dist_id] = distribution
        logger.info(f"Distribution created: {dist_id} for {platform.value}")
        return distribution

    async def create_multi_platform(
        self,
        content_id: str,
        platforms: list[DistributionPlatform],
        scheduled_at: Optional[datetime] = None,
    ) -> list[Distribution]:
        """
        Create distributions for multiple platforms at once.

        This is the common case - publish to all relevant platforms.
        """
        distributions = []
        for platform in platforms:
            dist = await self.create_distribution(
                content_id=content_id,
                platform=platform,
                scheduled_at=scheduled_at,
            )
            distributions.append(dist)

        logger.info(
            f"Created {len(distributions)} distributions for content {content_id}"
        )
        return distributions

    # ============================================
    # PUBLISHING
    # ============================================

    async def publish(self, distribution_id: str) -> Distribution:
        """
        Publish a distribution to its platform.

        This connects to the actual platform API to post content.
        """
        dist = self._distribution_store.get(distribution_id)
        if not dist:
            raise ValueError(f"Distribution not found: {distribution_id}")

        if dist.status == DistributionStatus.PUBLISHED:
            raise ValueError("Distribution already published")

        # Get the actual publishing method
        publisher = self._get_publisher(dist.platform)

        try:
            result = await publisher(dist)

            dist.status = DistributionStatus.PUBLISHED
            dist.published_at = datetime.utcnow()
            dist.platform_post_id = result.get("post_id")
            dist.platform_url = result.get("url")

            logger.info(
                f"Distribution published: {distribution_id} to {dist.platform.value}"
            )

        except Exception as e:
            dist.status = DistributionStatus.FAILED
            dist.error_message = str(e)
            logger.error(f"Distribution failed: {distribution_id} - {e}")
            raise

        return dist

    def _get_publisher(self, platform: DistributionPlatform):
        """Get the appropriate publisher method for a platform."""
        publishers = {
            DistributionPlatform.TWITTER: self._publish_twitter,
            DistributionPlatform.LINKEDIN: self._publish_linkedin,
            DistributionPlatform.INSTAGRAM: self._publish_instagram,
            DistributionPlatform.TIKTOK: self._publish_tiktok,
            DistributionPlatform.TELEGRAM: self._publish_telegram,
            DistributionPlatform.NEWSLETTER: self._publish_newsletter,
        }
        return publishers.get(platform, self._publish_mock)

    # ============================================
    # PLATFORM-SPECIFIC PUBLISHERS
    # ============================================

    async def _publish_twitter(self, dist: Distribution) -> dict:
        """Publish to Twitter/X."""
        # TODO: Implement actual Twitter API integration
        logger.info(f"Publishing to Twitter: {dist.content_id}")
        return {
            "post_id": f"twitter_{dist.id}",
            "url": f"https://twitter.com/balizero/status/{dist.id}",
        }

    async def _publish_linkedin(self, dist: Distribution) -> dict:
        """Publish to LinkedIn."""
        # TODO: Implement actual LinkedIn API integration
        logger.info(f"Publishing to LinkedIn: {dist.content_id}")
        return {
            "post_id": f"linkedin_{dist.id}",
            "url": f"https://linkedin.com/posts/{dist.id}",
        }

    async def _publish_instagram(self, dist: Distribution) -> dict:
        """Publish to Instagram."""
        # TODO: Implement actual Instagram API integration
        logger.info(f"Publishing to Instagram: {dist.content_id}")
        return {
            "post_id": f"instagram_{dist.id}",
            "url": f"https://instagram.com/p/{dist.id}",
        }

    async def _publish_tiktok(self, dist: Distribution) -> dict:
        """Publish to TikTok."""
        # TODO: Implement actual TikTok API integration
        logger.info(f"Publishing to TikTok: {dist.content_id}")
        return {
            "post_id": f"tiktok_{dist.id}",
            "url": f"https://tiktok.com/@balizero/video/{dist.id}",
        }

    async def _publish_telegram(self, dist: Distribution) -> dict:
        """Publish to Telegram channel."""
        # TODO: Implement actual Telegram Bot API integration
        logger.info(f"Publishing to Telegram: {dist.content_id}")
        return {
            "post_id": f"telegram_{dist.id}",
            "url": f"https://t.me/balizero/{dist.id}",
        }

    async def _publish_newsletter(self, dist: Distribution) -> dict:
        """Send via newsletter (email campaign)."""
        # TODO: Implement actual email service integration (SendGrid, Resend, etc.)
        logger.info(f"Sending newsletter: {dist.content_id}")
        return {
            "post_id": f"newsletter_{dist.id}",
            "url": f"https://balizero.com/newsletter/{dist.id}",
        }

    async def _publish_mock(self, dist: Distribution) -> dict:
        """Mock publisher for testing."""
        return {
            "post_id": f"mock_{dist.id}",
            "url": f"https://example.com/post/{dist.id}",
        }

    # ============================================
    # CONTENT ADAPTATION
    # ============================================

    def adapt_for_platform(
        self,
        content: Content,
        platform: DistributionPlatform,
    ) -> str:
        """
        Adapt content text for a specific platform.

        Each platform has different requirements:
        - Twitter: 280 chars, hashtags
        - LinkedIn: Professional tone, longer form
        - Instagram: Visual-first, emojis ok
        - TikTok: Short, engaging hooks
        - Telegram: Markdown supported
        """
        text = content.summary or content.body[:500]

        if platform == DistributionPlatform.TWITTER:
            # Truncate for Twitter, add hashtags
            if len(text) > 250:
                text = text[:247] + "..."
            text += f"\n\n#{content.category.value.replace('_', '')}"

        elif platform == DistributionPlatform.LINKEDIN:
            # More professional, can be longer
            text = f"📢 {content.title}\n\n{text}"
            if len(text) > 1000:
                text = text[:997] + "..."

        elif platform == DistributionPlatform.INSTAGRAM:
            # Visual-friendly, more casual
            text = f"✨ {content.title}\n\n{text}\n\n#balizero #indonesia #{content.category.value}"

        elif platform == DistributionPlatform.TELEGRAM:
            # Markdown formatting
            text = (
                f"**{content.title}**\n\n{text}\n\n[Read more →](https://balizero.com)"
            )

        elif platform == DistributionPlatform.NEWSLETTER:
            # Full content for email
            text = content.body

        return text

    # ============================================
    # SCHEDULING & QUEUE
    # ============================================

    async def get_pending_queue(self) -> list[Distribution]:
        """Get all pending distributions ready to be published."""
        now = datetime.utcnow()
        pending = [
            d
            for d in self._distribution_store.values()
            if d.status == DistributionStatus.PENDING
            or (
                d.status == DistributionStatus.SCHEDULED
                and d.scheduled_at
                and d.scheduled_at <= now
            )
        ]
        pending.sort(key=lambda x: x.scheduled_at or datetime.max)
        return pending

    async def get_scheduled(self) -> list[Distribution]:
        """Get all scheduled (future) distributions."""
        now = datetime.utcnow()
        scheduled = [
            d
            for d in self._distribution_store.values()
            if d.status == DistributionStatus.SCHEDULED
            and d.scheduled_at
            and d.scheduled_at > now
        ]
        scheduled.sort(key=lambda x: x.scheduled_at or datetime.max)
        return scheduled

    async def cancel_distribution(self, distribution_id: str) -> bool:
        """Cancel a pending or scheduled distribution."""
        dist = self._distribution_store.get(distribution_id)
        if not dist:
            return False

        if dist.status == DistributionStatus.PUBLISHED:
            raise ValueError("Cannot cancel already published distribution")

        del self._distribution_store[distribution_id]
        logger.info(f"Distribution cancelled: {distribution_id}")
        return True

    # ============================================
    # METRICS & ANALYTICS
    # ============================================

    async def get_metrics(self, distribution_id: str) -> DistributionMetrics:
        """
        Get engagement metrics for a distribution.

        Fetches real-time metrics from the platform API.
        """
        dist = self._distribution_store.get(distribution_id)
        if not dist:
            raise ValueError(f"Distribution not found: {distribution_id}")

        if dist.status != DistributionStatus.PUBLISHED:
            raise ValueError("Metrics only available for published distributions")

        # TODO: Fetch real metrics from platform APIs
        # For now, return mock data
        return DistributionMetrics(
            impressions=1500,
            engagements=120,
            clicks=45,
            shares=12,
        )

    async def sync_all_metrics(self) -> dict:
        """
        Sync metrics for all published distributions.

        Called periodically by background worker.
        """
        published = [
            d
            for d in self._distribution_store.values()
            if d.status == DistributionStatus.PUBLISHED
        ]

        synced = 0
        for dist in published:
            try:
                metrics = await self.get_metrics(dist.id)

                # Report to NUZANTARA analytics
                await nuzantara_client.report_content_metrics(
                    content_id=dist.content_id,
                    metrics={
                        "platform": dist.platform.value,
                        "impressions": metrics.impressions,
                        "engagements": metrics.engagements,
                        "clicks": metrics.clicks,
                        "shares": metrics.shares,
                    },
                )
                synced += 1
            except Exception as e:
                logger.error(f"Failed to sync metrics for {dist.id}: {e}")

        return {"synced": synced, "total": len(published)}

    # ============================================
    # OPTIMAL TIMING
    # ============================================

    def suggest_optimal_time(
        self,
        platform: DistributionPlatform,
        content_type: ContentType,
    ) -> dict:
        """
        Suggest optimal posting time for a platform.

        Based on general best practices for each platform.
        In production, this would use historical engagement data.
        """
        # Best times by platform (in WIB timezone, UTC+7)
        optimal_times = {
            DistributionPlatform.TWITTER: {
                "weekday": ["09:00", "12:00", "17:00"],
                "weekend": ["10:00", "14:00"],
            },
            DistributionPlatform.LINKEDIN: {
                "weekday": ["08:00", "12:00", "17:30"],
                "weekend": ["10:00"],
            },
            DistributionPlatform.INSTAGRAM: {
                "weekday": ["11:00", "14:00", "19:00"],
                "weekend": ["11:00", "19:00"],
            },
            DistributionPlatform.TIKTOK: {
                "weekday": ["19:00", "21:00"],
                "weekend": ["14:00", "19:00"],
            },
            DistributionPlatform.TELEGRAM: {
                "weekday": ["09:00", "18:00"],
                "weekend": ["11:00"],
            },
            DistributionPlatform.NEWSLETTER: {
                "weekday": ["08:00", "10:00"],
                "weekend": [],  # Don't send newsletters on weekends
            },
        }

        times = optimal_times.get(
            platform, {"weekday": ["12:00"], "weekend": ["12:00"]}
        )

        return {
            "platform": platform.value,
            "recommended_times": times,
            "timezone": "Asia/Jakarta",
            "note": "Times based on general best practices. Use analytics for personalized suggestions.",
        }


# Singleton instance
distributor = DistributorService()
