import json
from unittest.mock import patch

import httpx

from backend.llm.deepseek_client import DeepSeekAuthError, DeepSeekError
from backend.services.article_composer.error_handler import (
    APIError,
    ErrorCode,
    handle_anthropic_error,
    handle_json_error,
    handle_validation_error,
    log_error_with_context,
)


def test_api_error_create_normalizes_enum_code_and_details() -> None:
    error = APIError.create(
        code=ErrorCode.INVALID_REQUEST,
        message="Invalid payload",
        details={"field": "title"},
        request_id="req-1",
    )

    assert error.code == "INVALID_REQUEST"
    assert error.message == "Invalid payload"
    assert error.details == {"field": "title"}
    assert error.request_id == "req-1"
    assert error.timestamp


def test_handle_anthropic_error_maps_deepseek_auth_to_401() -> None:
    exc = handle_anthropic_error(
        DeepSeekAuthError("missing key"),
        article_title="Title",
        category="business",
        request_id="req-1",
    )

    assert exc.status_code == 401
    assert exc.detail["code"] == ErrorCode.API_KEY_NOT_CONFIGURED
    assert exc.detail["request_id"] == "req-1"
    assert exc.detail["details"]["article_title"] == "Title"
    assert "DEEPSEEK_API_KEY" in exc.detail["details"]["suggestion"]


def test_handle_anthropic_error_maps_timeout_connect_and_rate_limit() -> None:
    timeout = handle_anthropic_error(httpx.TimeoutException("slow"))
    connect = handle_anthropic_error(httpx.ConnectError("down"))
    rate = handle_anthropic_error(DeepSeekError("429 rate limit"))

    assert timeout.status_code == 504
    assert timeout.detail["code"] == ErrorCode.API_TIMEOUT
    assert connect.status_code == 503
    assert connect.detail["code"] == ErrorCode.API_CONNECTION_ERROR
    assert rate.status_code == 429
    assert rate.detail["code"] == ErrorCode.RATE_LIMIT_EXCEEDED


def test_handle_json_error_includes_location_and_preview() -> None:
    try:
        json.loads("{bad json")
    except json.JSONDecodeError as error:
        api_error = handle_json_error(
            error,
            response_text="x" * 600,
            article_title="Title",
            request_id="req-2",
        )

    assert api_error.code == ErrorCode.JSON_PARSE_ERROR
    assert api_error.request_id == "req-2"
    assert api_error.details["article_title"] == "Title"
    assert api_error.details["error_line"] == 1
    assert len(api_error.details["response_preview"]) == 500


def test_handle_validation_error_preserves_context() -> None:
    api_error = handle_validation_error(
        ValueError("bad field"),
        article_title="Title",
        request_id="req-3",
    )

    assert api_error.code == ErrorCode.VALIDATION_ERROR
    assert api_error.message == "Validation failed: bad field"
    assert api_error.details["error_type"] == "ValueError"
    assert api_error.request_id == "req-3"


def test_log_error_with_context_uses_requested_log_level() -> None:
    with patch("backend.services.article_composer.error_handler.logger") as logger:
        log_error_with_context(
            RuntimeError("temporary"),
            {"article_title": "Title"},
            level="WARNING",
        )

    logger.warning.assert_called_once()
    assert logger.warning.call_args.kwargs["extra"]["article_title"] == "Title"
    assert logger.warning.call_args.kwargs["extra"]["error_type"] == "RuntimeError"
