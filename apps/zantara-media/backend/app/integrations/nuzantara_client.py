"""
ZANTARA MEDIA - NUZANTARA Integration Client
Connects to the central NUZANTARA RAG system for:
- Qdrant vector indexing of published content
- CRM integration for lead tracking
- Auth token validation
- Analytics sync
"""

import logging
from typing import Optional
import httpx
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)


class VectorDocument(BaseModel):
    """Document to be indexed in Qdrant via NUZANTARA."""

    content_id: str
    title: str
    body: str
    category: str
    metadata: dict


class LeadCapture(BaseModel):
    """Lead captured from content engagement."""

    email: str
    source_content_id: str
    channel: str
    engagement_type: str  # newsletter_signup, download, contact_form


class NuzantaraClient:
    """
    Client for NUZANTARA RAG system integration.

    Uses the NUZANTARA API to:
    1. Index published content in Qdrant for RAG retrieval
    2. Sync leads to CRM
    3. Validate auth tokens
    4. Report analytics
    """

    def __init__(self):
        self.base_url = settings.nuzantara_api_url.rstrip("/")
        self.api_key = settings.nuzantara_api_key
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
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ============================================
    # QDRANT VECTOR INDEXING
    # ============================================

    async def index_content(self, document: VectorDocument) -> dict:
        """
        Index published content in NUZANTARA's Qdrant for RAG retrieval.
        This makes our content searchable by Zantara AI.
        """
        try:
            client = await self._get_client()

            payload = {
                "collection": "zantara_media_content",
                "documents": [
                    {
                        "id": document.content_id,
                        "text": f"{document.title}\n\n{document.body}",
                        "metadata": {
                            "source": "zantara_media",
                            "category": document.category,
                            "content_id": document.content_id,
                            **document.metadata,
                        },
                    }
                ],
            }

            response = await client.post("/api/v1/ingest/documents", json=payload)
            response.raise_for_status()

            logger.info(f"Content indexed in Qdrant: {document.content_id}")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to index content: {e}")
            raise

    async def delete_from_index(self, content_id: str) -> bool:
        """Remove content from Qdrant index when archived/deleted."""
        try:
            client = await self._get_client()

            response = await client.delete(
                f"/api/v1/ingest/documents/{content_id}",
                params={"collection": "zantara_media_content"},
            )
            response.raise_for_status()

            logger.info(f"Content removed from index: {content_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to delete from index: {e}")
            return False

    # ============================================
    # CRM INTEGRATION
    # ============================================

    async def sync_lead(self, lead: LeadCapture) -> dict:
        """
        Sync captured lead to NUZANTARA CRM.
        Leads captured from content engagement (newsletter, downloads, etc.)
        """
        try:
            client = await self._get_client()

            payload = {
                "email": lead.email,
                "source": f"zantara_media:{lead.channel}",
                "source_content_id": lead.source_content_id,
                "engagement_type": lead.engagement_type,
                "tags": ["content_lead", lead.channel],
            }

            response = await client.post("/api/v1/crm/leads", json=payload)
            response.raise_for_status()

            logger.info(f"Lead synced to CRM: {lead.email}")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to sync lead: {e}")
            raise

    async def get_lead_by_email(self, email: str) -> Optional[dict]:
        """Check if lead exists in CRM."""
        try:
            client = await self._get_client()
            response = await client.get("/api/v1/crm/leads", params={"email": email})
            response.raise_for_status()
            data = response.json()
            return data.get("lead")
        except httpx.HTTPError:
            return None

    # ============================================
    # AUTH INTEGRATION
    # ============================================

    async def validate_token(self, token: str) -> Optional[dict]:
        """
        Validate auth token against NUZANTARA auth system.
        Returns user data if valid, None otherwise.
        """
        try:
            client = await self._get_client()

            response = await client.post(
                "/api/v1/auth/validate",
                json={"token": token},
            )

            if response.status_code == 200:
                return response.json().get("user")
            return None

        except httpx.HTTPError as e:
            logger.error(f"Token validation failed: {e}")
            return None

    async def get_user_permissions(self, user_id: str) -> list[str]:
        """Get user permissions from NUZANTARA."""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/auth/users/{user_id}/permissions")
            response.raise_for_status()
            return response.json().get("permissions", [])
        except httpx.HTTPError:
            return []

    # ============================================
    # ANALYTICS SYNC
    # ============================================

    async def report_content_metrics(
        self,
        content_id: str,
        metrics: dict,
    ) -> bool:
        """
        Report content performance metrics to NUZANTARA analytics.
        Enables cross-platform analytics in the main dashboard.
        """
        try:
            client = await self._get_client()

            payload = {
                "source": "zantara_media",
                "content_id": content_id,
                "metrics": metrics,
            }

            response = await client.post("/api/v1/analytics/events", json=payload)
            response.raise_for_status()
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to report metrics: {e}")
            return False

    async def get_content_performance(self, content_id: str) -> dict:
        """Get aggregated performance data for content."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"/api/v1/analytics/content/{content_id}",
                params={"source": "zantara_media"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {}

    # ============================================
    # KNOWLEDGE BASE QUERIES
    # ============================================

    async def query_knowledge_base(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Query NUZANTARA's knowledge base for research.
        Useful for content creation with factual backing.
        """
        try:
            client = await self._get_client()

            params = {
                "query": query,
                "limit": limit,
                "include_sources": True,
            }
            if category:
                params["category"] = category

            response = await client.get("/api/v1/rag/search", params=params)
            response.raise_for_status()
            return response.json().get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Knowledge base query failed: {e}")
            return []

    # ============================================
    # HEALTH CHECK
    # ============================================

    async def health_check(self) -> bool:
        """Check if NUZANTARA API is reachable."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False


# Singleton instance
nuzantara_client = NuzantaraClient()
