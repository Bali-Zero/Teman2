import pytest
import os
from pathlib import Path

# Tests run from mcp-wrapper dir, config is relative
@pytest.fixture
def checker():
    from permissions import PermissionChecker
    config_path = str(Path(__file__).parent.parent / "config" / "roles.yaml")
    return PermissionChecker(config_path)

def test_visa_specialist_allowed_tool(checker):
    assert checker.is_allowed("visa_specialist", "get_visa_details") is True

def test_visa_specialist_blocked_tool(checker):
    assert checker.is_allowed("visa_specialist", "regenerate_invoice") is False

def test_admin_wildcard(checker):
    assert checker.is_allowed("admin", "anything_at_all") is True

def test_unknown_role(checker):
    assert checker.is_allowed("hacker", "get_visa_details") is False

def test_empty_tool(checker):
    assert checker.is_allowed("visa_specialist", "") is False

def test_tax_consultant_tools(checker):
    assert checker.is_allowed("tax_consultant", "get_compliance_alerts") is True
    assert checker.is_allowed("tax_consultant", "compose_article") is False

def test_get_allowed_tools(checker):
    tools = checker.get_allowed_tools("visa_specialist")
    assert "get_visa_details" in tools
    assert len(tools) == 19
