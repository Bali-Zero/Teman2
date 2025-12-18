"""
ZANTARA MEDIA - INTEL SCRAPING Integration Client
Connects to the INTEL SCRAPING system for:
- Fetching intelligence signals from 630+ sources
- Triggering scraping jobs
- Getting signal status and priorities
"""

import logging
from datetime import datetime
from typing import Optional
import httpx
from pydantic import BaseModel
from app.config import settings
from app.models import IntelPriority, ContentCategory

logger = logging.getLogger(__name__)


class IntelSignalRaw(BaseModel):
    """Raw intel signal from INTEL SCRAPING system."""

    id: str
    title: str
    source_name: str
    source_url: str
    category: str
    priority: str
    summary: str
    full_content: Optional[str] = None
    detected_at: datetime
    source_type: str  # government, news, social, regulation
    confidence_score: float
    keywords: list[str] = []
    entities: list[dict] = []


class ScrapeJobRequest(BaseModel):
    """Request to trigger a scraping job."""

    source_ids: Optional[list[str]] = None  # None = all sources
    categories: Optional[list[str]] = None
    priority_only: bool = False


class IntelClient:
    """
    Client for INTEL SCRAPING system integration.

    INTEL SCRAPING monitors 630+ Indonesian sources:
    - Government websites (Imigrasi, DJP, OJK, etc.)
    - News outlets (national and local)
    - Social media signals
    - Regulatory announcements

    Uses 3-tier AI fallback for signal processing:
    1. Llama 4 Scout (cheapest)
    2. Gemini 2.0 Flash
    3. Claude Haiku (fallback)
    """

    def __init__(self):
        self.base_url = settings.intel_api_url.rstrip("/")
        self.api_key = settings.intel_api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-Source": "zantara-media",
                },
                timeout=60.0,  # Longer timeout for scraping operations
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ============================================
    # SIGNAL FETCHING
    # ============================================

    async def get_signals(
        self,
        category: Optional[ContentCategory] = None,
        priority: Optional[IntelPriority] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IntelSignalRaw]:
        """
        Fetch intel signals from INTEL SCRAPING system.

        Args:
            category: Filter by category (immigration, tax, business, etc.)
            priority: Filter by priority (high, medium, low)
            since: Only signals detected after this time
            limit: Max signals to return
            offset: Pagination offset
        """
        try:
            client = await self._get_client()

            params = {
                "limit": limit,
                "offset": offset,
                "status": "new",  # Only unprocessed signals
            }

            if category:
                params["category"] = category.value
            if priority:
                params["priority"] = priority.value
            if since:
                params["since"] = since.isoformat()

            response = await client.get("/api/v1/signals", params=params)
            response.raise_for_status()

            data = response.json()
            signals = [IntelSignalRaw(**s) for s in data.get("signals", [])]

            logger.info(f"Fetched {len(signals)} intel signals")
            return signals

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch intel signals: {e}")
            return []

    async def get_signal_by_id(self, signal_id: str) -> Optional[IntelSignalRaw]:
        """Get detailed signal by ID."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/signals/{signal_id}")
            response.raise_for_status()
            return IntelSignalRaw(**response.json())
        except httpx.HTTPError:
            return None

    async def get_high_priority_signals(self, limit: int = 20) -> list[IntelSignalRaw]:
        """Get high priority signals that need immediate attention."""
        return await self.get_signals(priority=IntelPriority.HIGH, limit=limit)

    # ============================================
    # SIGNAL PROCESSING
    # ============================================

    async def mark_signal_processed(
        self,
        signal_id: str,
        action: str,
        content_id: Optional[str] = None,
    ) -> bool:
        """
        Mark signal as processed in INTEL SCRAPING.

        Args:
            signal_id: ID of the signal
            action: What was done (content_created, dismissed, archived)
            content_id: If content was created, link to it
        """
        try:
            client = await self._get_client()

            payload = {
                "action": action,
                "processed_by": "zantara-media",
                "processed_at": datetime.utcnow().isoformat(),
            }

            if content_id:
                payload["content_id"] = content_id

            response = await client.post(
                f"/api/v1/signals/{signal_id}/process",
                json=payload,
            )
            response.raise_for_status()

            logger.info(f"Signal {signal_id} marked as {action}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to mark signal processed: {e}")
            return False

    async def bulk_dismiss_signals(
        self, signal_ids: list[str], reason: str = "not_relevant"
    ) -> int:
        """Dismiss multiple signals at once."""
        try:
            client = await self._get_client()

            payload = {
                "signal_ids": signal_ids,
                "action": "dismissed",
                "reason": reason,
                "processed_by": "zantara-media",
            }

            response = await client.post("/api/v1/signals/bulk-process", json=payload)
            response.raise_for_status()

            dismissed = response.json().get("processed", 0)
            logger.info(f"Bulk dismissed {dismissed} signals")
            return dismissed

        except httpx.HTTPError as e:
            logger.error(f"Failed to bulk dismiss: {e}")
            return 0

    # ============================================
    # SCRAPING JOBS
    # ============================================

    async def trigger_scrape(self, request: ScrapeJobRequest) -> dict:
        """
        Trigger a scraping job on INTEL SCRAPING system.

        Can specify:
        - Specific source IDs to scrape
        - Categories to focus on
        - Priority-only mode (faster, fewer sources)
        """
        try:
            client = await self._get_client()

            payload = request.model_dump(exclude_none=True)

            response = await client.post("/api/v1/scrape/trigger", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Scrape job triggered: {result.get('job_id')}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to trigger scrape: {e}")
            raise

    async def get_scrape_job_status(self, job_id: str) -> dict:
        """Get status of a scraping job."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/scrape/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {"status": "unknown"}

    async def trigger_full_scrape(self) -> dict:
        """Trigger a full scrape of all 630+ sources."""
        return await self.trigger_scrape(ScrapeJobRequest())

    async def trigger_priority_scrape(self, categories: list[str]) -> dict:
        """Trigger scrape of high-priority sources in specific categories."""
        return await self.trigger_scrape(
            ScrapeJobRequest(categories=categories, priority_only=True)
        )

    # ============================================
    # SOURCE MANAGEMENT
    # ============================================

    async def get_sources(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict]:
        """Get list of intel sources."""
        try:
            client = await self._get_client()

            params = {"active": active_only}
            if category:
                params["category"] = category

            response = await client.get("/api/v1/sources", params=params)
            response.raise_for_status()
            return response.json().get("sources", [])

        except httpx.HTTPError:
            return []

    async def get_source_stats(self) -> dict:
        """Get statistics about intel sources."""
        try:
            client = await self._get_client()
            response = await client.get("/api/v1/sources/stats")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {
                "total_sources": 630,
                "active_sources": 630,
                "by_category": {},
            }

    # ============================================
    # ANALYTICS
    # ============================================

    async def get_signal_stats(self, days: int = 7) -> dict:
        """Get signal statistics for the past N days."""
        try:
            client = await self._get_client()
            response = await client.get(
                "/api/v1/signals/stats",
                params={"days": days},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {}

    async def get_trending_topics(self, limit: int = 10) -> list[dict]:
        """Get trending topics from recent signals."""
        try:
            client = await self._get_client()
            response = await client.get(
                "/api/v1/signals/trending",
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json().get("topics", [])
        except httpx.HTTPError:
            return []

    # ============================================
    # HEALTH CHECK
    # ============================================

    async def health_check(self) -> bool:
        """Check if INTEL SCRAPING API is reachable."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_system_status(self) -> dict:
        """Get overall system status including scraper health."""
        try:
            client = await self._get_client()
            response = await client.get("/api/v1/status")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {
                "status": "unknown",
                "scrapers": [],
                "queue_size": 0,
            }


# Singleton instance
intel_client = IntelClient()
