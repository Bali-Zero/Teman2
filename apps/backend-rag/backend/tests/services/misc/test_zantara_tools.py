from __future__ import annotations

from types import SimpleNamespace

from backend.services.misc import zantara_tools as zantara_module
from backend.services.misc.zantara_tools import ZantaraTools, get_zantara_tools


class FakePricingService:
    def __init__(self, *, loaded: bool = True) -> None:
        self.loaded = loaded

    def search_service(self, query: str) -> dict[str, str]:
        return {"query": query, "price": "official"}

    def get_pricing(self, service_type: str) -> dict[str, str]:
        return {"service_type": service_type, "price": "official"}


class FakeCollaboratorService:
    def __init__(self) -> None:
        self.profile = SimpleNamespace(
            name="Ada",
            email="ada@example.test",
            role="Ops",
            department="operations",
            expertise_level="senior",
            language="en",
            notes="Reliable",
            traits=["precise"],
        )

    def search_members(self, query: str) -> list[SimpleNamespace]:
        return [self.profile] if query == "ada" else []

    def list_members(self, department: str | None = None) -> list[SimpleNamespace]:
        if department and department != "operations":
            return []
        return [self.profile]

    def get_team_stats(self) -> dict[str, int]:
        return {"total": 1}


def build_tools(*, pricing_loaded: bool = True) -> ZantaraTools:
    tools = ZantaraTools.__new__(ZantaraTools)
    tools.pricing_service = FakePricingService(loaded=pricing_loaded)
    tools.collaborator_service = FakeCollaboratorService()
    return tools


def test_get_zantara_tools_returns_existing_singleton(monkeypatch) -> None:
    fake_tools = object()
    monkeypatch.setattr(zantara_module, "_zantara_tools", fake_tools)

    assert get_zantara_tools() is fake_tools


async def test_execute_tool_dispatches_pricing_and_unknown_tools() -> None:
    tools = build_tools()

    assert await tools.execute_tool("get_pricing", {"query": "KITAS"}) == {
        "success": True,
        "data": {"query": "KITAS", "price": "official"},
    }
    assert await tools.execute_tool("unknown", {}) == {
        "success": False,
        "error": "Unknown tool: unknown",
    }


async def test_get_pricing_reports_unloaded_official_prices() -> None:
    result = await build_tools(pricing_loaded=False).execute_tool(
        "get_pricing",
        {"service_type": "visa"},
    )

    assert result["success"] is False
    assert result["error"] == "Official prices not loaded"
    assert result["fallback_contact"]["email"] == "info@balizero.com"


async def test_team_tools_search_and_group_roster_by_department() -> None:
    tools = build_tools()

    search = await tools.execute_tool("search_team_member", {"query": "Ada"})
    roster = await tools.execute_tool(
        "get_team_members_list",
        {"department": "operations"},
    )

    assert search["data"]["count"] == 1
    assert search["data"]["results"][0]["email"] == "ada@example.test"
    assert roster["data"]["total_members"] == 1
    assert list(roster["data"]["by_department"]) == ["operations"]
    assert roster["data"]["stats"] == {"total": 1}


def test_get_tool_definitions_exposes_pricing_and_team_tools() -> None:
    names = [tool["name"] for tool in build_tools().get_tool_definitions()]

    assert names == ["get_pricing", "search_team_member", "get_team_members_list"]
