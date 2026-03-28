"""
Input Validation for Article Composer

Best Practices 2026:
- Advanced input validation
- Content sanitization
- Size limits
- Category validation
"""

import re

from pydantic import BaseModel, Field, field_validator, model_validator

# Valid categories
VALID_CATEGORIES = [
    "immigration",
    "business",
    "tax",
    "property",
    "lifestyle",
    "tech",
    "legal",
]

# Content size limits
MAX_CONTENT_LENGTH = 50000  # 50KB
MAX_TITLE_LENGTH = 200
MIN_TITLE_LENGTH = 10
MIN_CONTENT_LENGTH = 100


def sanitize_content(content: str) -> str:
    """
    Sanitize content by removing potentially dangerous characters.

    Args:
        content: Raw content string

    Returns:
        Sanitized content
    """
    # Remove null bytes
    content = content.replace("\x00", "")

    # Remove control characters except newlines and tabs
    content = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", content)

    # Limit consecutive whitespace
    content = re.sub(r"\s{3,}", "  ", content)

    return content.strip()


def validate_category(category: str) -> str:
    """
    Validate and normalize category.

    Args:
        category: Category string

    Returns:
        Normalized category

    Raises:
        ValueError: If category is invalid
    """
    category_lower = category.lower().strip()

    # Map common variations
    category_map = {
        "tax-legal": "tax",
        "legal": "tax",
        "immigration": "immigration",
        "business": "business",
        "property": "property",
        "lifestyle": "lifestyle",
        "tech": "tech",
    }

    normalized = category_map.get(category_lower, category_lower)

    if normalized not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(VALID_CATEGORIES)}",
        )

    return normalized


class ComposeRequestValidator(BaseModel):
    """Enhanced request validator with advanced validation"""

    title: str = Field(
        ...,
        min_length=MIN_TITLE_LENGTH,
        max_length=MAX_TITLE_LENGTH,
        description="Article title",
    )
    content: str = Field(
        ...,
        min_length=MIN_CONTENT_LENGTH,
        description="Raw article content",
    )
    category: str = Field(
        default="business",
        description="Category: immigration|business|tax|property|lifestyle|tech|legal",
    )
    source_url: str | None = Field(default=None, description="Original source URL if any")
    author: str = Field(default="Marketing Team", description="Author name")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate and sanitize title"""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return sanitize_content(v.strip())

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate and sanitize content"""
        if len(v) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"Content too large ({len(v)} chars). Maximum allowed: {MAX_CONTENT_LENGTH} chars",
            )
        return sanitize_content(v)

    @field_validator("category")
    @classmethod
    def validate_category_field(cls, v: str) -> str:
        """Validate category"""
        return validate_category(v)

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Validate URL format if provided"""
        if v is None:
            return None

        v = v.strip()
        if not v:
            return None

        # Basic URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(v):
            raise ValueError(f"Invalid URL format: {v}")

        return v

    @model_validator(mode="after")
    def validate_model(self) -> "ComposeRequestValidator":
        """Additional model-level validation"""
        # Ensure content is not just whitespace
        if not self.content.strip():
            raise ValueError("Content cannot be empty or only whitespace")

        return self
