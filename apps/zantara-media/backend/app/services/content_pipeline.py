"""
ZANTARA MEDIA - Content Pipeline Service
Orchestrates the content creation workflow from intel to publication
"""

import logging
from datetime import datetime
from typing import Optional
from app.models import (
    Content,
    ContentCreate,
    ContentStatus,
    ContentType,
    ContentCategory,
    ContentMetadata,
    IntelSignal,
    AIGenerateRequest,
)
from app.integrations.nuzantara_client import nuzantara_client, VectorDocument
from app.integrations.intel_client import intel_client

logger = logging.getLogger(__name__)


class ContentPipelineService:
    """
    Orchestrates the full content pipeline:

    Intel Signal → AI Draft → Human Review → Publication → Distribution

    Key responsibilities:
    1. Transform intel signals into content drafts
    2. Manage the review/approval workflow
    3. Index published content in NUZANTARA's Qdrant
    4. Track content performance
    """

    def __init__(self):
        self._content_store: dict[str, Content] = {}
        self._counter = 0

    def _generate_id(self) -> str:
        """Generate unique content ID."""
        self._counter += 1
        return f"content_{self._counter}"

    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug."""
        import re

        slug = title.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        return slug.strip("-")

    # ============================================
    # CONTENT CREATION
    # ============================================

    async def create_from_intel(
        self,
        signal: IntelSignal,
        content_type: ContentType = ContentType.ARTICLE,
        additional_context: Optional[str] = None,
    ) -> Content:
        """
        Create content draft from an intel signal.

        This is the main entry point for the autonomous pipeline:
        1. Takes an intel signal
        2. Enriches with knowledge base data
        3. Generates AI draft
        4. Creates content record
        """
        # Enrich with knowledge base context
        kb_context = await nuzantara_client.query_knowledge_base(
            query=signal.title,
            category=signal.category.value,
            limit=3,
        )

        # Build the AI generation request
        ai_request = AIGenerateRequest(
            topic=signal.title,
            content_type=content_type,
            category=signal.category,
            language="en",
            tone="professional",
            length="medium",
        )

        # Generate content using AI (import here to avoid circular)
        from app.routers.ai_writer import (
            generate_content_with_fallback,
            get_content_prompt,
        )

        prompt = get_content_prompt(ai_request)

        # Add intel context to prompt
        enriched_prompt = f"""{prompt}

Source Intelligence:
- Source: {signal.source_name}
- URL: {signal.source_url}
- Summary: {signal.summary}

"""
        if kb_context:
            enriched_prompt += "Related Knowledge Base Context:\n"
            for ctx in kb_context:
                enriched_prompt += (
                    f"- {ctx.get('title', '')}: {ctx.get('snippet', '')}\n"
                )

        if additional_context:
            enriched_prompt += f"\nAdditional Context:\n{additional_context}"

        # Generate
        raw_content, model_used = await generate_content_with_fallback(enriched_prompt)

        # Parse the generated content
        from app.routers.ai_writer import parse_generated_content

        parsed = parse_generated_content(raw_content, content_type)

        # Create content record
        content = await self.create_content(
            ContentCreate(
                title=parsed["title"],
                body=parsed["body"],
                summary=parsed["summary"],
                type=content_type,
                category=signal.category,
                tags=[signal.category.value, "ai-generated"],
            ),
            source_signal_id=signal.id,
            ai_model_used=model_used,
        )

        # Mark signal as processed
        await intel_client.mark_signal_processed(
            signal_id=signal.id,
            action="content_created",
            content_id=content.id,
        )

        logger.info(f"Content created from intel signal: {content.id} from {signal.id}")
        return content

    async def create_content(
        self,
        data: ContentCreate,
        source_signal_id: Optional[str] = None,
        ai_model_used: Optional[str] = None,
    ) -> Content:
        """Create a new content record."""
        content_id = self._generate_id()
        now = datetime.utcnow()

        word_count = len(data.body.split()) if data.body else 0

        content = Content(
            id=content_id,
            title=data.title,
            slug=self._generate_slug(data.title),
            body=data.body,
            summary=data.summary,
            type=data.type,
            category=data.category,
            tags=data.tags or [],
            status=ContentStatus.DRAFT,
            author_id="system",
            author_name="AI Writer" if ai_model_used else "Unknown",
            created_at=now,
            updated_at=now,
            metadata=ContentMetadata(
                word_count=word_count,
                reading_time_minutes=max(1, word_count // 200),
                ai_model=ai_model_used,
                source_signal_id=source_signal_id,
            ),
        )

        self._content_store[content_id] = content
        return content

    # ============================================
    # WORKFLOW MANAGEMENT
    # ============================================

    async def submit_for_review(self, content_id: str) -> Content:
        """Submit content for human review."""
        content = self._content_store.get(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        if content.status != ContentStatus.DRAFT:
            raise ValueError(
                f"Can only submit drafts, current status: {content.status}"
            )

        content.status = ContentStatus.REVIEW
        content.updated_at = datetime.utcnow()

        logger.info(f"Content submitted for review: {content_id}")
        return content

    async def approve_content(self, content_id: str, reviewer_id: str) -> Content:
        """Approve content after review."""
        content = self._content_store.get(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        if content.status != ContentStatus.REVIEW:
            raise ValueError(
                f"Can only approve content in review, current status: {content.status}"
            )

        content.status = ContentStatus.APPROVED
        content.updated_at = datetime.utcnow()
        content.metadata.approved_by = reviewer_id
        content.metadata.approved_at = datetime.utcnow()

        logger.info(f"Content approved: {content_id} by {reviewer_id}")
        return content

    async def publish_content(self, content_id: str) -> Content:
        """
        Publish content and index in NUZANTARA's Qdrant.

        This makes the content:
        1. Visible on the platform
        2. Searchable by Zantara AI
        3. Available for distribution
        """
        content = self._content_store.get(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        if content.status not in [ContentStatus.APPROVED, ContentStatus.SCHEDULED]:
            raise ValueError(f"Cannot publish content with status: {content.status}")

        now = datetime.utcnow()
        content.status = ContentStatus.PUBLISHED
        content.published_at = now
        content.updated_at = now

        # Index in NUZANTARA's Qdrant for RAG
        try:
            await nuzantara_client.index_content(
                VectorDocument(
                    content_id=content.id,
                    title=content.title,
                    body=content.body,
                    category=content.category.value,
                    metadata={
                        "type": content.type.value,
                        "published_at": now.isoformat(),
                        "tags": content.tags,
                        "slug": content.slug,
                    },
                )
            )
            logger.info(f"Content indexed in Qdrant: {content_id}")
        except Exception as e:
            logger.error(f"Failed to index content: {e}")
            # Don't fail publication if indexing fails

        logger.info(f"Content published: {content_id}")
        return content

    async def schedule_content(
        self,
        content_id: str,
        scheduled_at: datetime,
    ) -> Content:
        """Schedule content for future publication."""
        content = self._content_store.get(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        if scheduled_at <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")

        content.status = ContentStatus.SCHEDULED
        content.scheduled_at = scheduled_at
        content.updated_at = datetime.utcnow()

        logger.info(f"Content scheduled: {content_id} for {scheduled_at}")
        return content

    async def archive_content(self, content_id: str) -> Content:
        """Archive content and remove from Qdrant index."""
        content = self._content_store.get(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        content.status = ContentStatus.ARCHIVED
        content.updated_at = datetime.utcnow()

        # Remove from Qdrant index
        await nuzantara_client.delete_from_index(content_id)

        logger.info(f"Content archived: {content_id}")
        return content

    # ============================================
    # QUERIES
    # ============================================

    def get_content(self, content_id: str) -> Optional[Content]:
        """Get content by ID."""
        return self._content_store.get(content_id)

    def list_content(
        self,
        status: Optional[ContentStatus] = None,
        category: Optional[ContentCategory] = None,
        limit: int = 50,
    ) -> list[Content]:
        """List content with optional filters."""
        items = list(self._content_store.values())

        if status:
            items = [c for c in items if c.status == status]
        if category:
            items = [c for c in items if c.category == category]

        items.sort(key=lambda x: x.updated_at, reverse=True)
        return items[:limit]

    def get_pending_review(self) -> list[Content]:
        """Get all content pending review."""
        return self.list_content(status=ContentStatus.REVIEW)

    def get_scheduled(self) -> list[Content]:
        """Get all scheduled content."""
        return self.list_content(status=ContentStatus.SCHEDULED)


# Singleton instance
content_pipeline = ContentPipelineService()
