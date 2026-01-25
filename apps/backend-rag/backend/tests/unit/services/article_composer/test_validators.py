"""
Unit tests for Input Validators
"""

import pytest
from pydantic import ValidationError

from backend.services.article_composer.validators import (
    ComposeRequestValidator,
    sanitize_content,
    validate_category,
)


class TestSanitizeContent:
    """Test content sanitization"""

    def test_sanitize_removes_null_bytes(self):
        """Test null bytes are removed"""
        content = "Test\x00content"
        sanitized = sanitize_content(content)
        assert "\x00" not in sanitized

    def test_sanitize_removes_control_chars(self):
        """Test control characters are removed"""
        content = "Test\x01\x02content"
        sanitized = sanitize_content(content)
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized

    def test_sanitize_preserves_newlines(self):
        """Test newlines are preserved"""
        content = "Line 1\nLine 2\nLine 3"
        sanitized = sanitize_content(content)
        assert "\n" in sanitized

    def test_sanitize_limits_consecutive_whitespace(self):
        """Test consecutive whitespace is limited"""
        content = "Test    too    many    spaces"
        sanitized = sanitize_content(content)
        assert "    " not in sanitized
        assert "  " in sanitized  # Should be limited to 2 spaces


class TestValidateCategory:
    """Test category validation"""

    def test_validate_valid_categories(self):
        """Test valid categories pass"""
        assert validate_category("immigration") == "immigration"
        assert validate_category("business") == "business"
        assert validate_category("tax") == "tax"
        assert validate_category("property") == "property"

    def test_validate_case_insensitive(self):
        """Test category validation is case insensitive"""
        assert validate_category("IMMIGRATION") == "immigration"
        assert validate_category("Business") == "business"

    def test_validate_normalizes_variations(self):
        """Test category variations are normalized"""
        assert validate_category("tax-legal") == "tax"
        assert validate_category("legal") == "tax"

    def test_validate_invalid_category(self):
        """Test invalid category raises error"""
        with pytest.raises(ValueError, match="Invalid category"):
            validate_category("invalid_category")


class TestComposeRequestValidator:
    """Test ComposeRequestValidator model"""

    def test_valid_request(self):
        """Test valid request passes validation"""
        request = ComposeRequestValidator(
            title="Test Article Title",
            content="This is a test article content with enough words to pass validation. " * 2
            + "Additional content to meet minimum length requirements.",
            category="business",
        )

        assert request.title == "Test Article Title"
        assert len(request.content) > 0
        assert request.category == "business"

    def test_title_min_length(self):
        """Test title minimum length validation"""
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title="Short",  # Too short
                content="Valid content with enough words",
                category="business",
            )

    def test_title_max_length(self):
        """Test title maximum length validation"""
        long_title = "A" * 201  # Exceeds max length
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title=long_title,
                content="Valid content",
                category="business",
            )

    def test_content_min_length(self):
        """Test content minimum length validation"""
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title="Valid Title",
                content="Short",  # Too short
                category="business",
            )

    def test_content_max_length(self):
        """Test content maximum length validation"""
        long_content = "A" * 50001  # Exceeds max length
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title="Valid Title",
                content=long_content,
                category="business",
            )

    def test_category_validation(self):
        """Test category is validated"""
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title="Valid Title",
                content="Valid content with enough words",
                category="invalid_category",
            )

    def test_url_validation(self):
        """Test URL validation"""
        # Valid URL
        long_content = (
            "This is a valid article content with enough words to pass validation. " * 2
            + "Additional content to meet minimum length requirements."
        )
        request = ComposeRequestValidator(
            title="Valid Title",
            content=long_content,
            category="business",
            source_url="https://example.com/article",
        )
        assert request.source_url == "https://example.com/article"

        # Invalid URL
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title="Valid Title",
                content=long_content,
                category="business",
                source_url="not-a-url",
            )

    def test_empty_content_validation(self):
        """Test empty content is rejected"""
        with pytest.raises(ValidationError):
            ComposeRequestValidator(
                title="Valid Title",
                content="   ",  # Only whitespace
                category="business",
            )

    def test_content_sanitization(self):
        """Test content is sanitized"""
        long_content = (
            "Test\x00content with control chars\x01 " * 10
        ) + "Additional content to meet minimum length requirements."
        request = ComposeRequestValidator(
            title="Valid Title",
            content=long_content,
            category="business",
        )
        assert "\x00" not in request.content
        assert "\x01" not in request.content
