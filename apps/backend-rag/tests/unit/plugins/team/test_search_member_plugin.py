"""
Tests for TeamMemberSearchPlugin.
"""

from unittest.mock import MagicMock

import pytest

from backend.core.plugins import PluginCategory


def test_plugin_metadata_category():
    """Plugin should have AUTH category."""
    from backend.plugins.team.search_member_plugin import TeamMemberSearchPlugin
    plugin = TeamMemberSearchPlugin(collaborator_service=MagicMock())
    assert plugin.metadata.category == PluginCategory.AUTH


def test_plugin_metadata_compatibility():
    """Plugin metadata should have required fields."""
    from backend.plugins.team.search_member_plugin import TeamMemberSearchPlugin
    plugin = TeamMemberSearchPlugin(collaborator_service=MagicMock())
    meta = plugin.metadata
    assert meta.name == "team.search_member"
    assert "team" in meta.tags
    assert meta.version == "1.0.0"
