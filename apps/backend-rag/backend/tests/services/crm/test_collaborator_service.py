import pytest

from backend.services.crm.collaborator_service import CollaboratorProfile, CollaboratorService


def test_profile_serialization_and_matching() -> None:
    profile = CollaboratorProfile(
        id="u-1",
        email="advisor@example.com",
        name="Ada Advisor",
        role="Consultant",
        department="Setup",
        team="Immigration",
        language="en",
        traits=["precise", "calm"],
    )

    serialized = profile.to_dict()

    assert serialized["email"] == "advisor@example.com"
    assert serialized["traits"] == ["precise", "calm"]
    assert profile.matches("advisor")
    assert profile.matches("Setup")
    assert profile.matches("precise")
    assert not profile.matches("unrelated")


@pytest.mark.asyncio
async def test_identify_known_member_uses_cache() -> None:
    service = CollaboratorService()
    member = service.members[0]

    first = await service.identify(f"  {member.email.upper()}  ")
    second = await service.identify(member.email)

    assert first.email == member.email
    assert second is first
    assert member.email in service.cache


@pytest.mark.asyncio
async def test_identify_unknown_or_empty_returns_anonymous_profile() -> None:
    service = CollaboratorService()

    anonymous_from_none = await service.identify(None)
    anonymous_from_unknown = await service.identify("missing@example.com")

    assert anonymous_from_none.id == "anonymous"
    assert anonymous_from_unknown.email == "anonymous@balizero.com"


def test_member_listing_search_and_stats_are_consistent() -> None:
    service = CollaboratorService()
    member = service.members[0]

    assert service.get_member(member.email.upper()) == member
    assert member in service.list_members(member.department.upper())
    assert service.search_members(member.name.split()[0])
    assert service.search_members("   ") == []

    stats = service.get_team_stats()

    assert stats["total"] == len(service.members)
    assert sum(stats["departments"].values()) == len(service.members)
    assert sum(stats["languages"].values()) == len(service.members)
