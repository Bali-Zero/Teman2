"""
ZANTARA RAG - Pydantic Models
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class TierLevel(str, Enum):
    """Book tier classifications"""

    S = "S"  # Supreme - Quantum physics, consciousness, advanced metaphysics
    A = "A"  # Advanced - Philosophy, psychology, spiritual teachings
    B = "B"  # Intermediate - History, culture, practical wisdom
    C = "C"  # Basic - Self-help, business, general knowledge
    D = "D"  # Public - Popular science, introductory texts


class AccessLevel(int, Enum):
    """User access levels"""

    LEVEL_0 = 0  # Only Tier S
    LEVEL_1 = 1  # Tiers S + A
    LEVEL_2 = 2  # Tiers S + A + B + C
    LEVEL_3 = 3  # All tiers


class ChunkMetadata(BaseModel):
    """Metadata for each text chunk"""

    book_title: str
    book_author: str
    tier: TierLevel
    min_level: int = Field(ge=0, le=3)
    chunk_index: int
    page_number: int | None = None
    language: str = "en"
    topics: list[str] = Field(default_factory=list)
    file_path: str
    total_chunks: int


class SearchQuery(BaseModel):
    """Search request model"""

    query: str = Field(..., min_length=1, description="Search query text")
    level: int = Field(0, ge=0, le=3, description="User access level (0-3)")
    limit: int = Field(5, ge=1, le=50, description="Maximum results to return")
    tier_filter: list[TierLevel] | None = Field(None, description="Filter by specific tiers")
    collection: str | None = Field(None, description="Optional specific collection to search")


class SearchResult(BaseModel):
    """Single search result"""

    text: str
    metadata: ChunkMetadata
    similarity_score: float = Field(ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    """Search response model"""

    query: str
    results: list[SearchResult]
    total_found: int
    user_level: int
    execution_time_ms: float


class BookIngestionRequest(BaseModel):
    """Request to ingest a single book"""

    file_path: str
    title: str | None = None
    author: str | None = None
    language: str = "en"
    tier_override: TierLevel | None = None


class BookIngestionResponse(BaseModel):
    """Response from book ingestion"""

    success: bool
    book_title: str
    book_author: str
    tier: TierLevel
    chunks_created: int
    message: str
    error: str | None = None


class BatchIngestionRequest(BaseModel):
    """Request to ingest multiple books"""

    directory_path: str
    file_patterns: list[str] = Field(default_factory=lambda: ["*.pdf", "*.epub"])
    skip_existing: bool = True


class BatchIngestionResponse(BaseModel):
    """Response from batch ingestion"""

    total_books: int
    successful: int
    failed: int
    results: list[BookIngestionResponse]
    execution_time_seconds: float


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    database: dict[str, Any]
    embeddings: dict[str, Any]


class UserProfile(BaseModel):
    """
    Unified User Profile model
    Combines authentication and oracle-specific user preferences
    Supports both 'id' and 'user_id' for backward compatibility
    """

    # Core identification - accept either 'id' or 'user_id'
    id: str | None = Field(None, description="User ID (primary)")
    user_id: str | None = Field(None, description="User ID (alias, for backward compatibility)")

    # Basic info
    email: str
    name: str
    role: str
    status: str | None = Field(None, description="User status (active, inactive, etc.)")

    # Language preferences (unified)
    language: str = Field(default="en", description="User's preferred response language")
    language_preference: str | None = Field(
        None, description="Alias for language, for backward compatibility"
    )

    # Oracle-specific preferences
    tone: str | None = Field(default="professional", description="Communication tone")
    complexity: str | None = Field(default="medium", description="Response complexity level")
    timezone: str | None = Field(default="Asia/Bali", description="User's timezone")
    role_level: str | None = Field(default="member", description="User's role level")

    # Metadata (unified)
    metadata: dict[str, Any] | None = Field(None, description="General metadata")
    meta_json: dict[str, Any] = Field(
        default_factory=dict, description="Alias for metadata, for backward compatibility"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_ids(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Normalize id/user_id before validation"""
        if isinstance(values, dict):
            # If user_id is provided but id is not, use user_id as id
            if values.get("user_id") and not values.get("id"):
                values["id"] = values["user_id"]
            # If id is provided but user_id is not, use id as user_id
            elif values.get("id") and not values.get("user_id"):
                values["user_id"] = values["id"]
            # Ensure at least one is present
            if not values.get("id") and not values.get("user_id"):
                raise ValueError("Either 'id' or 'user_id' must be provided")
        return values

    def model_post_init(self, __context: Any) -> None:
        """Sync aliases after initialization"""
        # Ensure both id and user_id are set
        if self.id and not self.user_id:
            self.user_id = self.id
        elif self.user_id and not self.id:
            self.id = self.user_id

        # Sync language preferences
        if self.language_preference is None:
            self.language_preference = self.language
        elif self.language is None or self.language == "en":
            self.language = self.language_preference

        # Sync metadata
        if self.meta_json == {} and self.metadata is not None:
            self.meta_json = self.metadata
        elif self.metadata is None and self.meta_json:
            self.metadata = self.meta_json
