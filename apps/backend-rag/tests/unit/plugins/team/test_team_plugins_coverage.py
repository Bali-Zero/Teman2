import sys
import types

import pytest

services_module = types.ModuleType("services")
crm_module = types.ModuleType("backend.services.crm")
collab_module = types.ModuleType("backend.services.crm.collaborator_service")


class CollaboratorService:
    pass


collab_module.CollaboratorService = CollaboratorService
sys.modules.setdefault("services", services_module)
sys.modules.setdefault("backend.services.crm", crm_module)
sys.modules.setdefault("backend.services.crm.collaborator_service", collab_module)

from backend.plugins.team.list_members_plugin import TeamListInput, TeamMembersListPlugin
from backend.plugins.team.search_member_plugin import TeamMemberSearchPlugin, TeamSearchInput


class DummyProfile:
    def __init__(
        self,
        name="Zero",
        email="zero@balizero.com",
        role="Lead",
        department="technology",
        expertise_level="senior",
        language="en",
        traits=None,
        notes=None,
    ):
        self.name = name
        self.email = email
        self.role = role
        self.department = department
        self.expertise_level = expertise_level
        self.language = language
        self.traits = traits or []
        self.notes = notes


class DummyCollaboratorService:
    def __init__(self, profiles=None, stats=None):
        self._profiles = profiles or []
        self._stats = stats or {}
        self.last_department = None
        self.last_query = None

    def list_members(self, department):
        self.last_department = department
        return self._profiles

    def get_team_stats(self):
        return self._stats

    def search_members(self, query):
        self.last_query = query
        return self._profiles


@pytest.mark.asyncio
async def test_team_list_groups_by_department():
    profiles = [DummyProfile(), DummyProfile(name="Dea", department="operations")]
    service = DummyCollaboratorService(profiles=profiles, stats={"total": 2})
    plugin = TeamMembersListPlugin(collaborator_service=service)

    output = await plugin.execute(TeamListInput(department=" Technology "))
    assert output.success is True
    assert output.total_members == 2
    assert service.last_department == "technology"
    assert "technology" in output.by_department
    assert "operations" in output.by_department
    assert output.stats == {"total": 2}


@pytest.mark.asyncio
async def test_team_list_handles_exception():
    service = DummyCollaboratorService()

    def boom(_department):
        raise RuntimeError("boom")

    service.list_members = boom
    plugin = TeamMembersListPlugin(collaborator_service=service)
    output = await plugin.execute(TeamListInput())
    assert output.success is False
    assert "Team list failed: boom" in output.error


@pytest.mark.asyncio
async def test_team_search_validate():
    service = DummyCollaboratorService()
    plugin = TeamMemberSearchPlugin(collaborator_service=service)
    assert await plugin.validate(TeamSearchInput(query="Zero")) is True
    assert await plugin.validate(TeamSearchInput(query="  ")) is False


@pytest.mark.asyncio
async def test_team_search_results():
    profiles = [DummyProfile(), DummyProfile(name="Dea")]
    service = DummyCollaboratorService(profiles=profiles)
    plugin = TeamMemberSearchPlugin(collaborator_service=service)

    output = await plugin.execute(TeamSearchInput(query="Dea"))
    assert output.success is True
    assert output.count == 2
    assert output.results[0]["name"] == "Zero"
    assert service.last_query == "dea"


@pytest.mark.asyncio
async def test_team_search_no_results():
    service = DummyCollaboratorService(profiles=[])
    plugin = TeamMemberSearchPlugin(collaborator_service=service)
    output = await plugin.execute(TeamSearchInput(query="Missing"))
    assert output.success is True
    assert "No team member found" in output.message


@pytest.mark.asyncio
async def test_team_search_handles_exception():
    service = DummyCollaboratorService()

    def boom(_query):
        raise RuntimeError("boom")

    service.search_members = boom
    plugin = TeamMemberSearchPlugin(collaborator_service=service)
    output = await plugin.execute(TeamSearchInput(query="Zero"))
    assert output.success is False
    assert "Team search failed: boom" in output.error
