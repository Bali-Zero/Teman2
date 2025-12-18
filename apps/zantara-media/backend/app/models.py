"""
ZANTARA MEDIA - Pydantic Models
Request/Response schemas for the API
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# Enums
class ContentStatus(str, Enum):
    INTAKE = "intake"
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentType(str, Enum):
    ARTICLE = "article"
    SOCIAL_POST = "social_post"
    NEWSLETTER = "newsletter"
    PODCAST_SCRIPT = "podcast_script"
    VIDEO_SCRIPT = "video_script"
    THREAD = "thread"


class ContentPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ContentCategory(str, Enum):
    IMMIGRATION = "immigration"
    TAX = "tax"
    BUSINESS = "business"
    PROPERTY = "property"
    LEGAL = "legal"
    BALI_NEWS = "bali_news"
    LIFESTYLE = "lifestyle"
    GENERAL = "general"


class DistributionPlatform(str, Enum):
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    NEWSLETTER = "newsletter"
    WEBSITE = "website"
    YOUTUBE = "youtube"


class DistributionStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class IntelPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Base Models
class ContentMetadata(BaseModel):
    word_count: int = 0
    reading_time_minutes: int = 0
    ai_generated: bool = False
    ai_model: Optional[str] = None
    language: str = "en"
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    cover_image_url: Optional[str] = None


class DistributionMetrics(BaseModel):
    impressions: int = 0
    engagements: int = 0
    clicks: int = 0
    shares: int = 0


# Content Models
class ContentBase(BaseModel):
    title: str
    type: ContentType
    category: ContentCategory
    priority: ContentPriority = ContentPriority.NORMAL
    body: str = ""
    summary: Optional[str] = None
    tags: list[str] = []


class ContentCreate(ContentBase):
    pass


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[ContentType] = None
    status: Optional[ContentStatus] = None
    category: Optional[ContentCategory] = None
    priority: Optional[ContentPriority] = None
    body: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    scheduled_at: Optional[datetime] = None


class Content(ContentBase):
    id: str
    slug: str
    status: ContentStatus
    author_id: str
    author_name: str
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    metadata: ContentMetadata
    intel_source_id: Optional[str] = None

    class Config:
        from_attributes = True


# Distribution Models
class DistributionCreate(BaseModel):
    content_id: str
    platform: DistributionPlatform
    scheduled_at: Optional[datetime] = None
    custom_text: Optional[str] = None


class Distribution(BaseModel):
    id: str
    content_id: str
    platform: DistributionPlatform
    status: DistributionStatus
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    platform_post_id: Optional[str] = None
    platform_url: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Optional[DistributionMetrics] = None

    class Config:
        from_attributes = True


# Intel Signal Models
class IntelSignal(BaseModel):
    id: str
    title: str
    source_name: str
    source_url: str
    category: ContentCategory
    priority: IntelPriority
    summary: str
    detected_at: datetime
    processed: bool = False
    content_id: Optional[str] = None

    class Config:
        from_attributes = True


class IntelSignalProcess(BaseModel):
    signal_id: str
    action: str = "create_content"  # create_content, dismiss, archive
    content_type: Optional[ContentType] = ContentType.ARTICLE


# Dashboard Models
class DashboardStats(BaseModel):
    today: dict = Field(default_factory=dict)
    week: dict = Field(default_factory=dict)
    platforms: list[dict] = Field(default_factory=list)


class PlatformStatus(BaseModel):
    platform: DistributionPlatform
    connected: bool
    followers: int = 0
    posts_this_week: int = 0


# AI Generation Models
class AIGenerateRequest(BaseModel):
    signal_id: Optional[str] = None
    topic: str
    content_type: ContentType = ContentType.ARTICLE
    category: ContentCategory
    language: str = "en"
    tone: str = "professional"
    length: str = "medium"  # short, medium, long


class AIGenerateResponse(BaseModel):
    success: bool
    content_id: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    summary: Optional[str] = None
    model_used: Optional[str] = None  # Which AI model generated this
    error: Optional[str] = None


# API Response Models
class APIResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    message: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    has_more: bool
