"""Tests for GenomeAdapter async wrapper + no-genome graceful mode."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.services.learner.genome_adapter import (
    WAR_ROOM_CELL,
    GenomeAdapter,
    ScarEntry,
    SkillEntry,
)


@dataclass
class _FakeGenome:
    calls: list[tuple[str, tuple, dict]] = field(default_factory=list)
    return_value: str = "inserted"

    def record_skill(self, *args, **kwargs) -> str:
        self.calls.append(("record_skill", args, kwargs))
        return self.return_value

    def record_scar(self, *args, **kwargs) -> str:
        self.calls.append(("record_scar", args, kwargs))
        return self.return_value


@pytest.mark.asyncio
async def test_available_true_when_genome_present():
    g = GenomeAdapter(genome=_FakeGenome())
    assert g.available is True


@pytest.mark.asyncio
async def test_available_false_when_no_genome():
    g = GenomeAdapter(genome=None)
    assert g.available is False


@pytest.mark.asyncio
async def test_skill_skipped_when_no_genome():
    g = GenomeAdapter(genome=None)
    out = await g.record_skill(SkillEntry(
        skill_id="x", procedure="p",
    ))
    assert out == "skipped"


@pytest.mark.asyncio
async def test_scar_skipped_when_no_genome():
    g = GenomeAdapter(genome=None)
    out = await g.record_scar(ScarEntry(scar_id="y", procedure="q"))
    assert out == "skipped"


@pytest.mark.asyncio
async def test_skill_forwards_to_genome():
    fake = _FakeGenome(return_value="inserted")
    g = GenomeAdapter(genome=fake)
    out = await g.record_skill(SkillEntry(
        skill_id="war_room:analitico:ig:abc",
        procedure="procedure text",
        precondition="reg=analitico",
        success_criterion="composite > 0.7",
        confidence=0.82,
        domain="war_room",
        scope="Project",
    ))
    assert out == "inserted"
    assert len(fake.calls) == 1
    kind, args, kwargs = fake.calls[0]
    assert kind == "record_skill"
    # positional: (cell, skill_id, procedure, precondition, success_criterion,
    #              confidence, scope, inherited_from, entry_type, domain)
    assert args[0] == WAR_ROOM_CELL
    assert args[1] == "war_room:analitico:ig:abc"
    assert args[5] == 0.82
    assert args[6] == "Project"
    assert args[9] == "war_room"


@pytest.mark.asyncio
async def test_scar_forwards_to_genome():
    fake = _FakeGenome(return_value="inserted")
    g = GenomeAdapter(genome=fake)
    out = await g.record_scar(ScarEntry(
        scar_id="war_room_scar:low_score:ig:abc",
        procedure="avoid",
        precondition="reason=low_score",
    ))
    assert out == "inserted"
    kind, args, kwargs = fake.calls[0]
    assert kind == "record_scar"
    assert args[0] == WAR_ROOM_CELL
    assert args[1] == "war_room_scar:low_score:ig:abc"


@pytest.mark.asyncio
async def test_custom_cell_name():
    fake = _FakeGenome()
    g = GenomeAdapter(genome=fake, cell="custom_cell")
    await g.record_skill(SkillEntry(skill_id="x", procedure="p"))
    assert fake.calls[0][1][0] == "custom_cell"
