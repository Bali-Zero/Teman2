"""Unit tests for ActivityLoggingMiddleware.dispatch()

Covers the hot path that runs on every non-excluded request:
  * excluded paths are NOT logged (early return)
  * happy path: response status + timing are forwarded to activity_logger
  * logger exceptions never fail the request (defensive catch)
  * call_next() raising an exception still logs + re-raises (finally block)
  * session logging only fires when both session_id and user_email present
  * IP extraction honors the Fly-Client-IP / X-Forwarded-For / X-Real-IP order
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, Response

from backend.middleware.activity_logging import ActivityLoggingMiddleware


@pytest.fixture
def middleware() -> ActivityLoggingMiddleware:
    return ActivityLoggingMiddleware(app=MagicMock())


def _make_request(
    *,
    path: str = "/api/crm/clients",
    method: str = "GET",
    user: object | None = None,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    client_host: str | None = "10.0.0.1",
    request_body: object | None = None,
) -> Request:
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.user = user
    req.state.request_body = request_body
    req.method = method

    url = MagicMock()
    url.path = path
    req.url = url

    req.headers = headers or {}
    req.cookies = cookies or {}
    req.query_params = query_params or {}

    if client_host is None:
        req.client = None
    else:
        client = MagicMock()
        client.host = client_host
        req.client = client

    return req


def _make_response(status: int = 200) -> Response:
    response = MagicMock(spec=Response)
    response.status_code = status
    return response


# ---------------------------------------------------------------------------
# Excluded paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excluded_path_is_not_logged(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Health checks must bypass activity_logger entirely (zero DB writes)."""
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(path="/health")
    response = _make_response(200)
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response
    call_next.assert_awaited_once_with(request)
    logger_mock.log_api_call.assert_not_called()


@pytest.mark.asyncio
async def test_excluded_prefix_is_not_logged(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paths starting with an excluded prefix (e.g. /docs/some-page) are skipped."""
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(path="/docs/oauth2-redirect")
    response = _make_response(200)
    call_next = AsyncMock(return_value=response)

    await middleware.dispatch(request, call_next)

    logger_mock.log_api_call.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_logs_api_call_with_correct_metadata(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    logger_mock.log_session = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(
        path="/api/crm/clients",
        method="POST",
        user={"email": "user@balizero.com"},
        headers={
            "User-Agent": "pytest/1.0",
            "X-Correlation-ID": "corr-42",
        },
        cookies={"session_id": "sess-abc"},
        query_params={"page": "1"},
        client_host="203.0.113.10",
        request_body={"name": "Foo"},
    )
    response = _make_response(201)
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response
    logger_mock.log_api_call.assert_awaited_once()
    kwargs = logger_mock.log_api_call.await_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["endpoint"] == "/api/crm/clients"
    assert kwargs["response_status"] == 201
    assert kwargs["user_email"] == "user@balizero.com"
    assert kwargs["query_params"] == {"page": "1"}
    assert kwargs["request_body"] == {"name": "Foo"}
    assert kwargs["error_message"] is None
    assert kwargs["correlation_id"] == "corr-42"
    assert kwargs["session_id"] == "sess-abc"
    assert kwargs["user_agent"] == "pytest/1.0"
    assert kwargs["ip_address"] == "203.0.113.10"
    assert isinstance(kwargs["response_time_ms"], int)
    assert kwargs["response_time_ms"] >= 0

    logger_mock.log_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_requests_do_not_forward_request_body(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET requests must not pass a request_body even if one happens to be on state."""
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(
        method="GET",
        request_body={"should": "be-ignored"},
    )
    call_next = AsyncMock(return_value=_make_response(200))

    await middleware.dispatch(request, call_next)

    kwargs = logger_mock.log_api_call.await_args.kwargs
    assert kwargs["request_body"] is None


# ---------------------------------------------------------------------------
# Error paths — logger failure must never fail the request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_logger_exception_does_not_fail_request(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock(side_effect=RuntimeError("DB down"))
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request()
    response = _make_response(200)
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response  # request must succeed despite logger failure
    logger_mock.log_api_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_log_session_exception_does_not_fail_request(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If log_session raises after log_api_call succeeds, the request still returns."""
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    logger_mock.log_session = AsyncMock(side_effect=RuntimeError("session write failed"))
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(
        user={"email": "user@balizero.com"},
        cookies={"session_id": "sess-xyz"},
    )
    response = _make_response(200)
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response


# ---------------------------------------------------------------------------
# Upstream handler raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_next_exception_is_logged_and_reraised(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If downstream handler raises, activity_logger still records status=500 + error_message."""
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request()
    call_next = AsyncMock(side_effect=ValueError("boom"))

    with pytest.raises(ValueError, match="boom"):
        await middleware.dispatch(request, call_next)

    logger_mock.log_api_call.assert_awaited_once()
    kwargs = logger_mock.log_api_call.await_args.kwargs
    assert kwargs["response_status"] == 500
    assert kwargs["error_message"] == "boom"


# ---------------------------------------------------------------------------
# Session log gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_not_logged_without_user_email(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """log_session requires both session_id AND user_email — anon clients skip it."""
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    logger_mock.log_session = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(
        user=None,
        cookies={"session_id": "sess-anon"},
    )
    call_next = AsyncMock(return_value=_make_response(200))

    await middleware.dispatch(request, call_next)

    logger_mock.log_session.assert_not_called()


@pytest.mark.asyncio
async def test_session_not_logged_without_session_id(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    logger_mock.log_session = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(user={"email": "user@balizero.com"}, cookies={})
    call_next = AsyncMock(return_value=_make_response(200))

    await middleware.dispatch(request, call_next)

    logger_mock.log_session.assert_not_called()


# ---------------------------------------------------------------------------
# IP extraction precedence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ip_extraction_prefers_fly_header(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(
        headers={
            "Fly-Client-IP": "1.2.3.4",
            "X-Forwarded-For": "5.6.7.8, 9.9.9.9",
            "X-Real-IP": "7.7.7.7",
        },
        client_host="10.0.0.1",
    )
    await middleware.dispatch(request, AsyncMock(return_value=_make_response(200)))

    kwargs = logger_mock.log_api_call.await_args.kwargs
    assert kwargs["ip_address"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_ip_extraction_uses_forwarded_for_first_entry(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(
        headers={"X-Forwarded-For": "5.6.7.8, 9.9.9.9"},
        client_host="10.0.0.1",
    )
    await middleware.dispatch(request, AsyncMock(return_value=_make_response(200)))

    kwargs = logger_mock.log_api_call.await_args.kwargs
    assert kwargs["ip_address"] == "5.6.7.8"


@pytest.mark.asyncio
async def test_ip_extraction_falls_back_to_unknown(
    middleware: ActivityLoggingMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mock = MagicMock()
    logger_mock.log_api_call = AsyncMock()
    monkeypatch.setattr(
        "backend.middleware.activity_logging.activity_logger", logger_mock
    )

    request = _make_request(client_host=None)
    await middleware.dispatch(request, AsyncMock(return_value=_make_response(200)))

    kwargs = logger_mock.log_api_call.await_args.kwargs
    assert kwargs["ip_address"] == "unknown"
