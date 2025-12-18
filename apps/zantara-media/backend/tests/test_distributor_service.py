"""
Unit tests for Distributor Service
Tests for content distribution across social media platforms
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.services.distributor import DistributorService, distributor
from app.models import (
    DistributionStatus,
    DistributionPlatform,
    DistributionMetrics,
    Content,
    ContentType,
    ContentStatus,
    ContentCategory,
    ContentPriority,
    ContentMetadata,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def service():
    """Create a fresh DistributorService instance"""
    return DistributorService()


@pytest.fixture
def sample_content():
    """Create sample content for testing"""
    return Content(
        id="content_1",
        slug="test-content",
        title="Test Content Title",
        type=ContentType.ARTICLE,
        category=ContentCategory.IMMIGRATION,
        priority=ContentPriority.NORMAL,
        status=ContentStatus.APPROVED,
        body="This is the full body of the test content. It contains information about immigration updates and visa processing.",
        summary="Test summary for the content",
        tags=["immigration", "visa"],
        author_id="author_1",
        author_name="Test Author",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata=ContentMetadata(
            word_count=100,
            reading_time_minutes=1,
            ai_generated=True,
            ai_model="gpt-4",
            language="en",
        ),
    )


# ============================================================================
# Distribution Creation Tests
# ============================================================================


class TestCreateDistribution:
    """Tests for create_distribution method"""

    @pytest.mark.asyncio
    async def test_create_distribution_pending(self, service):
        """Test creating a pending distribution (no scheduled time)"""
        dist = await service.create_distribution(
            content_id="content_1",
            platform=DistributionPlatform.TWITTER,
        )

        assert dist.id.startswith("dist_")
        assert dist.content_id == "content_1"
        assert dist.platform == DistributionPlatform.TWITTER
        assert dist.status == DistributionStatus.PENDING
        assert dist.scheduled_at is None

    @pytest.mark.asyncio
    async def test_create_distribution_scheduled(self, service):
        """Test creating a scheduled distribution"""
        scheduled_time = datetime.utcnow() + timedelta(hours=2)
        dist = await service.create_distribution(
            content_id="content_1",
            platform=DistributionPlatform.LINKEDIN,
            scheduled_at=scheduled_time,
        )

        assert dist.status == DistributionStatus.SCHEDULED
        assert dist.scheduled_at == scheduled_time

    @pytest.mark.asyncio
    async def test_create_distribution_with_custom_text(self, service):
        """Test creating a distribution with custom text"""
        dist = await service.create_distribution(
            content_id="content_1",
            platform=DistributionPlatform.TWITTER,
            custom_text="Custom tweet text for this distribution",
        )

        assert dist.custom_text == "Custom tweet text for this distribution"

    @pytest.mark.asyncio
    async def test_create_distribution_unique_ids(self, service):
        """Test that each distribution gets a unique ID"""
        dist1 = await service.create_distribution(
            "content_1", DistributionPlatform.TWITTER
        )
        dist2 = await service.create_distribution(
            "content_1", DistributionPlatform.LINKEDIN
        )
        dist3 = await service.create_distribution(
            "content_2", DistributionPlatform.TWITTER
        )

        assert dist1.id != dist2.id != dist3.id


class TestCreateMultiPlatform:
    """Tests for create_multi_platform method"""

    @pytest.mark.asyncio
    async def test_create_multi_platform_all_platforms(self, service):
        """Test creating distributions for multiple platforms"""
        platforms = [
            DistributionPlatform.TWITTER,
            DistributionPlatform.LINKEDIN,
            DistributionPlatform.INSTAGRAM,
        ]

        distributions = await service.create_multi_platform(
            content_id="content_1",
            platforms=platforms,
        )

        assert len(distributions) == 3
        created_platforms = [d.platform for d in distributions]
        assert set(created_platforms) == set(platforms)

    @pytest.mark.asyncio
    async def test_create_multi_platform_with_schedule(self, service):
        """Test creating scheduled distributions for multiple platforms"""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        platforms = [DistributionPlatform.TWITTER, DistributionPlatform.TELEGRAM]

        distributions = await service.create_multi_platform(
            content_id="content_1",
            platforms=platforms,
            scheduled_at=scheduled_time,
        )

        for dist in distributions:
            assert dist.status == DistributionStatus.SCHEDULED
            assert dist.scheduled_at == scheduled_time


# ============================================================================
# Publishing Tests
# ============================================================================


class TestPublish:
    """Tests for publish method"""

    @pytest.mark.asyncio
    async def test_publish_success(self, service):
        """Test successful publishing"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.TWITTER
        )

        published = await service.publish(dist.id)

        assert published.status == DistributionStatus.PUBLISHED
        assert published.published_at is not None
        assert published.platform_post_id is not None
        assert published.platform_url is not None

    @pytest.mark.asyncio
    async def test_publish_not_found(self, service):
        """Test publishing non-existent distribution raises error"""
        with pytest.raises(ValueError, match="Distribution not found"):
            await service.publish("non_existent_id")

    @pytest.mark.asyncio
    async def test_publish_already_published(self, service):
        """Test publishing already published distribution raises error"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.TWITTER
        )
        await service.publish(dist.id)

        with pytest.raises(ValueError, match="already published"):
            await service.publish(dist.id)


class TestPlatformPublishers:
    """Tests for platform-specific publishers"""

    @pytest.mark.asyncio
    async def test_publish_to_twitter(self, service):
        """Test publishing to Twitter"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.TWITTER
        )
        result = await service._publish_twitter(dist)

        assert "post_id" in result
        assert "url" in result
        assert "twitter" in result["url"]

    @pytest.mark.asyncio
    async def test_publish_to_linkedin(self, service):
        """Test publishing to LinkedIn"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.LINKEDIN
        )
        result = await service._publish_linkedin(dist)

        assert "post_id" in result
        assert "linkedin" in result["url"]

    @pytest.mark.asyncio
    async def test_publish_to_instagram(self, service):
        """Test publishing to Instagram"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.INSTAGRAM
        )
        result = await service._publish_instagram(dist)

        assert "post_id" in result
        assert "instagram" in result["url"]

    @pytest.mark.asyncio
    async def test_publish_to_tiktok(self, service):
        """Test publishing to TikTok"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.TIKTOK
        )
        result = await service._publish_tiktok(dist)

        assert "post_id" in result
        assert "tiktok" in result["url"]

    @pytest.mark.asyncio
    async def test_publish_to_telegram(self, service):
        """Test publishing to Telegram"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.TELEGRAM
        )
        result = await service._publish_telegram(dist)

        assert "post_id" in result
        assert "t.me" in result["url"]

    @pytest.mark.asyncio
    async def test_publish_newsletter(self, service):
        """Test sending newsletter"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.NEWSLETTER
        )
        result = await service._publish_newsletter(dist)

        assert "post_id" in result
        assert "newsletter" in result["url"]

    @pytest.mark.asyncio
    async def test_publish_mock(self, service):
        """Test mock publisher"""
        dist = await service.create_distribution(
            "content_1", DistributionPlatform.TWITTER
        )
        result = await service._publish_mock(dist)

        assert "post_id" in result
        assert "mock" in result["post_id"]


# ============================================================================
# Content Adaptation Tests
# ============================================================================


class TestAdaptForPlatform:
    """Tests for adapt_for_platform method"""

    def test_adapt_for_twitter_truncates_long_text(self, service, sample_content):
        """Test that Twitter adaptation truncates long text"""
        sample_content.summary = "A" * 300  # Long text
        result = service.adapt_for_platform(
            sample_content, DistributionPlatform.TWITTER
        )

        # Should be truncated with hashtag
        assert len(result.split("\n\n")[0]) <= 250 or "..." in result

    def test_adapt_for_twitter_adds_hashtag(self, service, sample_content):
        """Test that Twitter adaptation adds category hashtag"""
        result = service.adapt_for_platform(
            sample_content, DistributionPlatform.TWITTER
        )
        assert "#" in result

    def test_adapt_for_linkedin_adds_emoji(self, service, sample_content):
        """Test that LinkedIn adaptation adds announcement emoji"""
        result = service.adapt_for_platform(
            sample_content, DistributionPlatform.LINKEDIN
        )
        assert result.startswith("📢")

    def test_adapt_for_instagram_adds_hashtags(self, service, sample_content):
        """Test that Instagram adaptation adds multiple hashtags"""
        result = service.adapt_for_platform(
            sample_content, DistributionPlatform.INSTAGRAM
        )
        assert "#balizero" in result
        assert "#indonesia" in result

    def test_adapt_for_telegram_uses_markdown(self, service, sample_content):
        """Test that Telegram adaptation uses markdown formatting"""
        result = service.adapt_for_platform(
            sample_content, DistributionPlatform.TELEGRAM
        )
        assert "**" in result  # Bold markdown
        assert "[Read more" in result

    def test_adapt_for_newsletter_full_content(self, service, sample_content):
        """Test that newsletter gets full content body"""
        result = service.adapt_for_platform(
            sample_content, DistributionPlatform.NEWSLETTER
        )
        assert result == sample_content.body


# ============================================================================
# Queue Management Tests
# ============================================================================


class TestQueueManagement:
    """Tests for queue management methods"""

    @pytest.mark.asyncio
    async def test_get_pending_queue(self, service):
        """Test getting pending distributions"""
        await service.create_distribution("c1", DistributionPlatform.TWITTER)
        await service.create_distribution("c2", DistributionPlatform.LINKEDIN)

        pending = await service.get_pending_queue()

        assert len(pending) == 2
        for dist in pending:
            assert dist.status in [
                DistributionStatus.PENDING,
                DistributionStatus.SCHEDULED,
            ]

    @pytest.mark.asyncio
    async def test_get_pending_queue_includes_due_scheduled(self, service):
        """Test that pending queue includes scheduled items that are due"""
        past_time = datetime.utcnow() - timedelta(hours=1)
        await service.create_distribution(
            "c1", DistributionPlatform.TWITTER, scheduled_at=past_time
        )

        pending = await service.get_pending_queue()

        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_get_scheduled_future_only(self, service):
        """Test that scheduled list only includes future items"""
        future_time = datetime.utcnow() + timedelta(hours=2)
        past_time = datetime.utcnow() - timedelta(hours=1)

        await service.create_distribution(
            "c1", DistributionPlatform.TWITTER, scheduled_at=future_time
        )
        await service.create_distribution(
            "c2", DistributionPlatform.LINKEDIN, scheduled_at=past_time
        )

        scheduled = await service.get_scheduled()

        assert len(scheduled) == 1
        assert scheduled[0].content_id == "c1"


class TestCancelDistribution:
    """Tests for cancel_distribution method"""

    @pytest.mark.asyncio
    async def test_cancel_pending_distribution(self, service):
        """Test cancelling a pending distribution"""
        dist = await service.create_distribution("c1", DistributionPlatform.TWITTER)

        result = await service.cancel_distribution(dist.id)

        assert result is True
        # Verify it's removed
        assert service._distribution_store.get(dist.id) is None

    @pytest.mark.asyncio
    async def test_cancel_scheduled_distribution(self, service):
        """Test cancelling a scheduled distribution"""
        future = datetime.utcnow() + timedelta(hours=1)
        dist = await service.create_distribution(
            "c1", DistributionPlatform.TWITTER, scheduled_at=future
        )

        result = await service.cancel_distribution(dist.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_published_distribution_fails(self, service):
        """Test that cancelling published distribution raises error"""
        dist = await service.create_distribution("c1", DistributionPlatform.TWITTER)
        await service.publish(dist.id)

        with pytest.raises(ValueError, match="Cannot cancel already published"):
            await service.cancel_distribution(dist.id)

    @pytest.mark.asyncio
    async def test_cancel_non_existent_returns_false(self, service):
        """Test cancelling non-existent distribution returns False"""
        result = await service.cancel_distribution("non_existent")
        assert result is False


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for metrics-related methods"""

    @pytest.mark.asyncio
    async def test_get_metrics_success(self, service):
        """Test getting metrics for published distribution"""
        dist = await service.create_distribution("c1", DistributionPlatform.TWITTER)
        await service.publish(dist.id)

        metrics = await service.get_metrics(dist.id)

        assert isinstance(metrics, DistributionMetrics)
        assert metrics.impressions >= 0
        assert metrics.engagements >= 0
        assert metrics.clicks >= 0
        assert metrics.shares >= 0

    @pytest.mark.asyncio
    async def test_get_metrics_not_found(self, service):
        """Test getting metrics for non-existent distribution"""
        with pytest.raises(ValueError, match="Distribution not found"):
            await service.get_metrics("non_existent")

    @pytest.mark.asyncio
    async def test_get_metrics_not_published(self, service):
        """Test getting metrics for unpublished distribution fails"""
        dist = await service.create_distribution("c1", DistributionPlatform.TWITTER)

        with pytest.raises(ValueError, match="only available for published"):
            await service.get_metrics(dist.id)

    @pytest.mark.asyncio
    async def test_sync_all_metrics(self, service):
        """Test syncing metrics for all published distributions"""
        # Create and publish some distributions
        dist1 = await service.create_distribution("c1", DistributionPlatform.TWITTER)
        dist2 = await service.create_distribution("c2", DistributionPlatform.LINKEDIN)
        await service.publish(dist1.id)
        await service.publish(dist2.id)

        with patch.object(
            service, "get_metrics", new_callable=AsyncMock
        ) as mock_metrics:
            mock_metrics.return_value = DistributionMetrics(
                impressions=100, engagements=10, clicks=5, shares=2
            )

            with patch(
                "app.integrations.nuzantara_client.nuzantara_client.report_content_metrics",
                new_callable=AsyncMock,
            ):
                result = await service.sync_all_metrics()

        assert result["total"] == 2


# ============================================================================
# Optimal Timing Tests
# ============================================================================


class TestOptimalTiming:
    """Tests for optimal timing suggestions"""

    def test_suggest_optimal_time_twitter(self, service):
        """Test optimal time suggestion for Twitter"""
        result = service.suggest_optimal_time(
            DistributionPlatform.TWITTER, ContentType.ARTICLE
        )

        assert result["platform"] == "twitter"
        assert "recommended_times" in result
        assert "weekday" in result["recommended_times"]
        assert "weekend" in result["recommended_times"]
        assert result["timezone"] == "Asia/Jakarta"

    def test_suggest_optimal_time_linkedin(self, service):
        """Test optimal time suggestion for LinkedIn"""
        result = service.suggest_optimal_time(
            DistributionPlatform.LINKEDIN, ContentType.ARTICLE
        )

        assert result["platform"] == "linkedin"
        # LinkedIn typically has morning slots
        weekday_times = result["recommended_times"]["weekday"]
        assert any("08:" in t or "09:" in t for t in weekday_times)

    def test_suggest_optimal_time_newsletter_no_weekend(self, service):
        """Test that newsletter doesn't recommend weekend times"""
        result = service.suggest_optimal_time(
            DistributionPlatform.NEWSLETTER, ContentType.NEWSLETTER
        )

        assert len(result["recommended_times"]["weekend"]) == 0


# ============================================================================
# Singleton Instance Tests
# ============================================================================


class TestSingletonInstance:
    """Tests for the singleton distributor instance"""

    def test_singleton_exists(self):
        """Test that singleton instance exists"""
        assert distributor is not None
        assert isinstance(distributor, DistributorService)

    def test_singleton_generates_ids(self):
        """Test that singleton can generate IDs"""
        id1 = distributor._generate_id()
        id2 = distributor._generate_id()
        assert id1 != id2
