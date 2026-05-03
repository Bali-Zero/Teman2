"""
Unit tests for ActivityLoggingMiddleware — user_email extraction timing.

Verifies that _get_user_email reads from request.state.user (set by auth
middleware) and that the extraction happens correctly via the helper method.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import Request

from backend.middleware.activity_logging import ActivityLoggingMiddleware


@pytest.fixture
def mock_app() -> MagicMock:
    return MagicMock()


@pytest.fixture
def middleware(mock_app: MagicMock) -> ActivityLoggingMiddleware:
    return ActivityLoggingMiddleware(app=mock_app)


def _make_request(*, user: object = None, header_email: str | None = None) -> Request:
    """Build a minimal mock Request with controllable state and headers."""
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.user = user

    headers: dict[str, str] = {}
    if header_email is not None:
        headers["X-User-Email"] = header_email
    req.headers = headers

    return req


# ---------------------------------------------------------------------------
# _get_user_email tests
# ---------------------------------------------------------------------------


def test_get_user_email_from_state(middleware: ActivityLoggingMiddleware) -> None:
    """Extracts email from request.state.user when it is a dict (JWT payload)."""
    request = _make_request(user={"email": "user@balizero.com", "sub": "123"})
    result = middleware._get_user_email(request)
    assert result == "user@balizero.com"


def test_get_user_email_returns_none_when_no_user(middleware: ActivityLoggingMiddleware) -> None:
    """Returns None when request.state.user is None (unauthenticated call)."""
    request = _make_request(user=None)
    result = middleware._get_user_email(request)
    assert result is None


def test_get_user_email_header_fallback(middleware: ActivityLoggingMiddleware) -> None:
    """Falls back to X-User-Email header when state.user is not set."""
    request = _make_request(user=None, header_email="debug@balizero.com")
    result = middleware._get_user_email(request)
    assert result == "debug@balizero.com"


def test_get_user_email_state_takes_priority_over_header(middleware: ActivityLoggingMiddleware) -> None:
    """state.user email takes priority over X-User-Email header."""
    request = _make_request(
        user={"email": "real@balizero.com"},
        header_email="header@balizero.com",
    )
    result = middleware._get_user_email(request)
    assert result == "real@balizero.com"


def test_get_user_email_from_object_with_email_attr(middleware: ActivityLoggingMiddleware) -> None:
    """Handles user objects with an .email attribute (Pydantic model path)."""
    user_obj = MagicMock()
    user_obj.email = "obj@balizero.com"
    # Make isinstance(user, dict) return False so the attribute path is taken
    request = _make_request(user=user_obj)
    # Override so it is NOT a dict
    request.state.user = user_obj
    result = middleware._get_user_email(request)
    assert result == "obj@balizero.com"
