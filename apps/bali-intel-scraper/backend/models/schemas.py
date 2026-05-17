"""
Pydantic schemas for data validation.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ArticleStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NewsCategory(str, Enum):
    POLITICS = "politics"
    BUSINESS = "business"
    TECHNOLOGY = "technology"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


class ArticleBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    content: str | None = None
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    category: NewsCategory | None = None


class ArticleCreate(ArticleBase):
    source_id: UUID


class ArticleResponse(ArticleBase):
    id: UUID
    source_id: UUID
    status: ArticleStatus
    created_at: datetime
    sentiment_score: float | None = None


class SourceBase(BaseSchema):
    name: str
    url: HttpUrl
    is_active: bool = True


class SourceResponse(SourceBase):
    id: UUID
    created_at: datetime
    last_crawled_at: datetime | None = None


class ScrapeRequest(BaseSchema):
    url: HttpUrl
    use_browser: bool = False


class ScrapeResponse(BaseSchema):
    success: bool
    url: str
    title: str | None = None
    error: str | None = None


class HealthCheck(BaseSchema):
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float


__all__ = [
    "ArticleStatus",
    "NewsCategory",
    "BaseSchema",
    "ArticleBase",
    "ArticleCreate",
    "ArticleResponse",
    "SourceBase",
    "SourceResponse",
    "ScrapeRequest",
    "ScrapeResponse",
    "HealthCheck",
]
