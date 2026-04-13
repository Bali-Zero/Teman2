"""
Tests for TeamMembersListPlugin.
"""

from unittest.mock import MagicMock

import pytest


def test_execute_with_empty_string_department():
    """Plugin should handle empty string department by treating as None."""
    from backend.plugins.team.list_members_plugin import TeamListInput, TeamMembersListPlugin

    mock_collab = MagicMock()
    mock_collab.list_members.return_value = []
    mock_collab.get_team_stats.return_value = {"total": 0}

    plugin = TeamMembersListPlugin(collaborator_service=mock_collab)
    input_data = TeamListInput(department="")

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(plugin.execute(input_data))
    assert result.success is True
