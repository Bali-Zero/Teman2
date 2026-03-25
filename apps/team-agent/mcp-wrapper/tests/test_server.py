"""Tests for MCP wrapper server logic (unit tests, no subprocess needed)."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import make_error_response, filter_tools_list
from permissions import PermissionChecker


@pytest.fixture
def checker():
    config_path = str(Path(__file__).parent.parent / "config" / "roles.yaml")
    return PermissionChecker(config_path)


def test_make_error_response():
    resp = make_error_response(42, -32600, "Not allowed")
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 42
    assert resp["error"]["code"] == -32600
    assert "Not allowed" in resp["error"]["message"]


def test_make_error_response_null_id():
    resp = make_error_response(None, -32600, "Not allowed")
    assert resp["id"] is None


def test_make_error_response_string_id():
    resp = make_error_response("abc-123", -32600, "Not allowed")
    assert resp["id"] == "abc-123"


def test_filter_tools_list_visa():
    """Visa specialist should see only their tools."""
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {"name": "get_visa_details", "description": "..."},
                {"name": "regenerate_invoice", "description": "..."},
                {"name": "get_client", "description": "..."},
                {"name": "delete_everything", "description": "..."},
            ]
        },
    }

    filtered = filter_tools_list(response)
    tool_names = [t["name"] for t in filtered["result"]["tools"]]

    assert "get_visa_details" in tool_names
    assert "get_client" in tool_names
    assert "regenerate_invoice" not in tool_names
    assert "delete_everything" not in tool_names


def test_filter_tools_list_admin():
    """Admin should see all tools."""
    config_path = str(Path(__file__).parent.parent / "config" / "roles.yaml")
    admin_checker = PermissionChecker(config_path)

    assert admin_checker.is_allowed("admin", "regenerate_invoice") is True
    assert admin_checker.is_allowed("admin", "delete_everything") is True
    assert admin_checker.is_allowed("admin", "any_tool_at_all") is True


def test_filter_empty_response():
    response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    filtered = filter_tools_list(response)
    assert filtered["result"]["tools"] == []


def test_filter_no_result():
    response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "fail"}}
    filtered = filter_tools_list(response)
    assert "error" in filtered
    assert "result" not in filtered


def test_error_response_is_valid_jsonrpc():
    """Error response must be serializable as valid JSON-RPC."""
    resp = make_error_response(7, -32601, "Method not found")
    serialized = json.dumps(resp)
    parsed = json.loads(serialized)
    assert parsed["jsonrpc"] == "2.0"
    assert parsed["id"] == 7
    assert parsed["error"]["code"] == -32601


def test_filter_preserves_tool_metadata():
    """Filtering should keep all tool fields intact, not just name."""
    response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {
                    "name": "get_visa_details",
                    "description": "Get visa details",
                    "inputSchema": {"type": "object"},
                },
            ]
        },
    }

    filtered = filter_tools_list(response)
    tool = filtered["result"]["tools"][0]
    assert tool["name"] == "get_visa_details"
    assert tool["description"] == "Get visa details"
    assert tool["inputSchema"] == {"type": "object"}
