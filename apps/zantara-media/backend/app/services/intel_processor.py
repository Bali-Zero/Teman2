"""
ZANTARA MEDIA - Intel Processor Service
Processes intel signals from INTEL SCRAPING system
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from app.models import IntelSignal, IntelPriority, ContentCategory, ContentType
from app.integrations.intel_client import intel_client, IntelSignalRaw

logger = logging.getLogger(__name__)


class IntelProcessorService:
    """
    Processes intelligence signals from the INTEL SCRAPING system.

    Responsibilities:
    1. Fetch and filter signals from 630+ sources
    2. Prioritize signals by relevance and urgency
    3. Route signals to appropriate content types
    4. Manage signal lifecycle (process, dismiss, archive)

    Priority Logic:
    - HIGH: Government regulations, tax deadlines, visa changes
    - MEDIUM: Industry news, business updates, market trends
    - LOW: General interest, lifestyle, culture
    """

    def __init__(self):
        self._local_cache: dict[str, IntelSignal] = {}
        self._last_sync: Optional[datetime] = None

    # ============================================
    # SIGNAL FETCHING & CACHING
    # ============================================

    async def sync_signals(self, force: bool = False) -> int:
        """
        Sync signals from INTEL SCRAPING to local cache.

        Args:
            force: Force sync even if recently synced

        Returns:
            Number of new signals added
        """
        # Skip if synced recently (unless forced)
        if not force and self._last_sync:
            if datetime.utcnow() - self._last_sync < timedelta(minutes=5):
                logger.debug("Skipping sync - recently synced")
                return 0

        # Fetch new signals
        raw_signals = await intel_client.get_signals(limit=100)

        new_count = 0
        for raw in raw_signals:
            if raw.id not in self._local_cache:
                signal = self._convert_signal(raw)
                self._local_cache[signal.id] = signal
                new_count += 1

        self._last_sync = datetime.utcnow()
        logger.info(f"Synced {new_count} new signals from INTEL SCRAPING")
        return new_count

    def _convert_signal(self, raw: IntelSignalRaw) -> IntelSignal:
        """Convert raw signal from INTEL SCRAPING to our model."""
        # Map category
        category_map = {
            "immigration": ContentCategory.IMMIGRATION,
            "tax": ContentCategory.TAX,
            "business": ContentCategory.BUSINESS,
            "legal": ContentCategory.LEGAL,
            "banking": ContentCategory.BANKING,
            "property": ContentCategory.PROPERTY,
            "lifestyle": ContentCategory.LIFESTYLE,
        }
        category = category_map.get(raw.category.lower(), ContentCategory.BUSINESS)

        # Map priority
        priority_map = {
            "high": IntelPriority.HIGH,
            "medium": IntelPriority.MEDIUM,
            "low": IntelPriority.LOW,
        }
        priority = priority_map.get(raw.priority.lower(), IntelPriority.MEDIUM)

        return IntelSignal(
            id=raw.id,
            title=raw.title,
            source_name=raw.source_name,
            source_url=raw.source_url,
            category=category,
            priority=priority,
            summary=raw.summary,
            detected_at=raw.detected_at,
            processed=False,
        )

    # ============================================
    # SIGNAL QUERIES
    # ============================================

    async def get_signals(
        self,
        category: Optional[ContentCategory] = None,
        priority: Optional[IntelPriority] = None,
        processed: Optional[bool] = None,
        limit: int = 50,
    ) -> list[IntelSignal]:
        """Get signals with optional filtering."""
        # Ensure we have recent data
        await self.sync_signals()

        signals = list(self._local_cache.values())

        if category:
            signals = [s for s in signals if s.category == category]
        if priority:
            signals = [s for s in signals if s.priority == priority]
        if processed is not None:
            signals = [s for s in signals if s.processed == processed]

        # Sort by priority (high first) then by detection time
        priority_order = {
            IntelPriority.HIGH: 0,
            IntelPriority.MEDIUM: 1,
            IntelPriority.LOW: 2,
        }
        signals.sort(
            key=lambda x: (
                priority_order.get(x.priority, 99),
                -x.detected_at.timestamp(),
            )
        )

        return signals[:limit]

    async def get_signal(self, signal_id: str) -> Optional[IntelSignal]:
        """Get signal by ID."""
        await self.sync_signals()
        return self._local_cache.get(signal_id)

    async def get_high_priority(self) -> list[IntelSignal]:
        """Get unprocessed high priority signals."""
        return await self.get_signals(
            priority=IntelPriority.HIGH,
            processed=False,
        )

    async def get_unprocessed_count(self) -> dict:
        """Get count of unprocessed signals by category and priority."""
        signals = await self.get_signals(processed=False)

        by_priority = {
            "high": len([s for s in signals if s.priority == IntelPriority.HIGH]),
            "medium": len([s for s in signals if s.priority == IntelPriority.MEDIUM]),
            "low": len([s for s in signals if s.priority == IntelPriority.LOW]),
        }

        by_category = {}
        for cat in ContentCategory:
            count = len([s for s in signals if s.category == cat])
            if count > 0:
                by_category[cat.value] = count

        return {
            "total": len(signals),
            "by_priority": by_priority,
            "by_category": by_category,
        }

    # ============================================
    # SIGNAL PROCESSING
    # ============================================

    async def process_signal(
        self,
        signal_id: str,
        action: str,
        content_id: Optional[str] = None,
    ) -> bool:
        """
        Process a signal with given action.

        Actions:
        - create_content: Signal was used to create content
        - dismiss: Signal was dismissed (not relevant)
        - archive: Signal was archived for later

        Args:
            signal_id: ID of the signal
            action: Action taken
            content_id: If content was created, the ID

        Returns:
            True if successful
        """
        signal = self._local_cache.get(signal_id)
        if not signal:
            logger.warning(f"Signal not found: {signal_id}")
            return False

        if signal.processed:
            logger.warning(f"Signal already processed: {signal_id}")
            return False

        # Update local cache
        signal.processed = True
        if content_id:
            signal.content_id = content_id

        # Sync to INTEL SCRAPING
        success = await intel_client.mark_signal_processed(
            signal_id=signal_id,
            action=action,
            content_id=content_id,
        )

        if success:
            logger.info(f"Signal processed: {signal_id} with action {action}")
        else:
            logger.error(f"Failed to sync signal processing: {signal_id}")

        return success

    async def dismiss_signal(
        self, signal_id: str, reason: str = "not_relevant"
    ) -> bool:
        """Dismiss a signal as not relevant."""
        return await self.process_signal(signal_id, f"dismissed:{reason}")

    async def bulk_dismiss(
        self, signal_ids: list[str], reason: str = "not_relevant"
    ) -> int:
        """Dismiss multiple signals at once."""
        # Update local cache
        for signal_id in signal_ids:
            if signal_id in self._local_cache:
                self._local_cache[signal_id].processed = True

        # Sync to INTEL SCRAPING
        dismissed = await intel_client.bulk_dismiss_signals(signal_ids, reason)
        return dismissed

    # ============================================
    # CONTENT TYPE ROUTING
    # ============================================

    def suggest_content_type(self, signal: IntelSignal) -> ContentType:
        """
        Suggest the best content type for a signal based on its characteristics.

        Rules:
        - HIGH priority government/legal → ARTICLE
        - TAX deadlines → NEWSLETTER + SOCIAL_POST
        - General news → SOCIAL_POST or THREAD
        - Complex topics → ARTICLE
        """
        if signal.priority == IntelPriority.HIGH:
            if signal.category in [ContentCategory.LEGAL, ContentCategory.IMMIGRATION]:
                return ContentType.ARTICLE
            elif signal.category == ContentCategory.TAX:
                return ContentType.NEWSLETTER

        if signal.category == ContentCategory.LIFESTYLE:
            return ContentType.SOCIAL_POST

        # Default to article for most business content
        return ContentType.ARTICLE

    def suggest_distribution_channels(self, signal: IntelSignal) -> list[str]:
        """
        Suggest distribution channels based on signal characteristics.

        Returns list of recommended platforms.
        """
        channels = []

        if signal.priority == IntelPriority.HIGH:
            channels.extend(["newsletter", "telegram", "linkedin"])

        if signal.category in [ContentCategory.TAX, ContentCategory.IMMIGRATION]:
            channels.extend(["linkedin", "newsletter"])

        if signal.category == ContentCategory.LIFESTYLE:
            channels.extend(["instagram", "tiktok"])

        # Always include Twitter for reach
        if "twitter" not in channels:
            channels.append("twitter")

        return list(set(channels))  # Remove duplicates

    # ============================================
    # ANALYTICS & INSIGHTS
    # ============================================

    async def get_trending_topics(self, limit: int = 10) -> list[dict]:
        """Get trending topics from recent signals."""
        return await intel_client.get_trending_topics(limit=limit)

    async def get_source_stats(self) -> dict:
        """Get statistics about intel sources."""
        return await intel_client.get_source_stats()

    async def trigger_refresh(self, categories: Optional[list[str]] = None) -> dict:
        """Trigger a refresh of intel sources."""

        if categories:
            return await intel_client.trigger_priority_scrape(categories)
        else:
            return await intel_client.trigger_full_scrape()


# Singleton instance
intel_processor = IntelProcessorService()
