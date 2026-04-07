# scripts/zantara-gateway/test_gateway.py
"""Tests for gateway core."""

import pytest
from gateway import ndjson_line_to_sse, verify_gateway_token

# ── NDJSON → SSE conversion ──


def test_assistant_message_converts_to_token():
    line = '{"type":"message","role":"assistant","content":"Hello ","delta":true}'
    result = ndjson_line_to_sse(line)
    assert result == 'data: {"type":"token","data":"Hello "}\n\n'


def test_result_converts_to_done():
    line = '{"type":"result","status":"success","stats":{}}'
    result = ndjson_line_to_sse(line)
    assert result == "data: [DONE]\n\n"


def test_tool_use_converts():
    line = '{"type":"tool_use","tool_name":"mcp_nuzantara-mcp_list_clients","tool_id":"abc","parameters":{"limit":5}}'
    result = ndjson_line_to_sse(line)
    assert '"type":"tool_call"' in result
    assert '"name":"list_clients"' in result  # prefix stripped


def test_tool_result_converts():
    line = '{"type":"tool_result","tool_id":"abc","status":"success","output":"data here"}'
    result = ndjson_line_to_sse(line)
    assert '"type":"tool_result"' in result


def test_init_skipped():
    line = '{"type":"init","session_id":"abc","model":"auto-gemini-3"}'
    result = ndjson_line_to_sse(line)
    assert result is None


def test_user_message_skipped():
    line = '{"type":"message","role":"user","content":"hello"}'
    result = ndjson_line_to_sse(line)
    assert result is None


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
