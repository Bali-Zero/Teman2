# scripts/zantara-gateway/test_gateway.py
"""Tests for gateway core."""

import pytest
from gateway import ndjson_line_to_sse, verify_gateway_token

# ── NDJSON → SSE conversion ──


def test_text_delta_converts_to_token():
    line = '{"type":"textDelta","text":"Hello "}'
    result = ndjson_line_to_sse(line)
    assert result == 'data: {"type":"token","data":"Hello "}\n\n'


def test_done_converts_to_done():
    line = '{"type":"done"}'
    result = ndjson_line_to_sse(line)
    assert result == "data: [DONE]\n\n"


def test_tool_call_start_converts():
    line = '{"type":"toolCallStart","toolName":"list_clients","args":{"limit":5}}'
    result = ndjson_line_to_sse(line)
    assert '"type":"tool_call"' in result
    assert '"name":"list_clients"' in result


def test_unknown_type_returns_none():
    line = '{"type":"unknownEvent","data":"whatever"}'
    result = ndjson_line_to_sse(line)
    assert result is None


def test_invalid_json_returns_none():
    result = ndjson_line_to_sse("not json at all")
    assert result is None


# ── Auth ──


def test_valid_token():
    assert verify_gateway_token("abc123", "abc123") is True


def test_invalid_token():
    assert verify_gateway_token("abc123", "wrong") is False


def test_empty_configured_token_disables_auth():
    """If no token is configured, auth is disabled (dev mode)."""
    assert verify_gateway_token("", "anything") is True
