import pytest
from pydantic import ValidationError

from backend.services.article_composer.validators import (
    MAX_CONTENT_LENGTH,
    ComposeRequestValidator,
    sanitize_content,
    validate_category,
)


def _content() -> str:
    return "Indonesia business and immigration update. " * 4


def test_sanitize_content_removes_control_characters_and_limits_whitespace() -> None:
    assert sanitize_content("\x00  Hello\x07\n\n\nWorld  ") == "Hello  World"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Immigration ", "immigration"),
        ("tax-legal", "tax"),
        ("legal", "tax"),
        ("BUSINESS", "business"),
    ],
)
def test_validate_category_normalizes_supported_values(raw: str, expected: str) -> None:
    assert validate_category(raw) == expected


def test_validate_category_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="Invalid category"):
        validate_category("sports")


def test_compose_request_validator_sanitizes_fields_and_blank_url() -> None:
    request = ComposeRequestValidator(
        title="  New PT PMA Rule\x00  ",
        content=_content(),
        category="legal",
        source_url="  ",
    )

    assert request.title == "New PT PMA Rule"
    assert request.category == "tax"
    assert request.source_url is None


def test_compose_request_validator_accepts_valid_url() -> None:
    request = ComposeRequestValidator(
        title="New PT PMA Rule",
        content=_content(),
        category="business",
        source_url="https://example.com/news?id=1",
    )

    assert request.source_url == "https://example.com/news?id=1"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "short", "content": _content(), "category": "business"},
        {"title": "New PT PMA Rule", "content": "too short", "category": "business"},
        {"title": "New PT PMA Rule", "content": _content(), "category": "sports"},
        {
            "title": "New PT PMA Rule",
            "content": _content(),
            "category": "business",
            "source_url": "not-a-url",
        },
        {
            "title": "New PT PMA Rule",
            "content": "x" * (MAX_CONTENT_LENGTH + 1),
            "category": "business",
        },
    ],
)
def test_compose_request_validator_rejects_invalid_payloads(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ComposeRequestValidator(**payload)
