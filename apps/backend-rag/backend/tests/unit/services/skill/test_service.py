"""Unit tests for backend.services.skill.service.

Mirror of experience.service tests, with skill-specific additions:
- tier filter in SkillQuery
- promote + get_top_skills paths
- merge-proposals read (empty by default, populated by Day 5)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.skill.models import (
    SkillQuery,
    SkillRecord,
    SkillTier,
)
from backend.services.skill.service import SkillService


@pytest.fixture
def service(tmp_path):
    return SkillService(db_path=str(tmp_path / "skill.db"))


# ─── Pydantic contract ──────────────────────────────────────────────


def test_skill_record_requires_non_empty_procedure():
    with pytest.raises(ValidationError):
        SkillRecord(
            cell="c1", skill_id="s1", procedure="",
            precondition="x", success_criterion="y",
        )


def test_skill_record_confidence_bounds():
    with pytest.raises(ValidationError):
        SkillRecord(
            cell="c1", skill_id="s1", procedure="p",
            precondition="x", success_criterion="y",
            confidence=1.5,
        )


def test_skill_record_scope_whitelist():
    with pytest.raises(ValidationError):
        SkillRecord(
            cell="c1", skill_id="s1", procedure="p",
            precondition="x", success_criterion="y",
            scope="Global",  # invalid
        )


def test_skill_query_tier_filter_accepts_enum():
    q = SkillQuery(query="x", tier=SkillTier.TIER1)
    assert q.tier == SkillTier.TIER1


def test_skill_query_rejects_invalid_tier_string():
    with pytest.raises(ValidationError):
        SkillQuery(query="x", tier="tier3")


def test_skill_query_limit_upper_bound():
    with pytest.raises(ValidationError):
        SkillQuery(query="x", limit=10_000)


# ─── record() ───────────────────────────────────────────────────────


def test_record_inserts_and_upserts(service):
    rec = SkillRecord(
        cell="rag", skill_id="rag:chunk",
        procedure="Split text into overlapping 10k windows.",
        precondition="Document ready",
        success_criterion="No context loss",
        confidence=0.7,
    )
    first = service.record(rec)
    assert first["action"] == "inserted"
    second = service.record(rec)
    assert second["action"] == "updated"


def test_record_failure_skipped_if_service_unavailable(tmp_path, monkeypatch):
    import backend.services.skill.service as svc_mod

    monkeypatch.setattr(svc_mod, "_GENOME_AVAILABLE", False)
    monkeypatch.setattr(svc_mod, "Genome", None)

    svc = SkillService(db_path=str(tmp_path / "x.db"))
    assert svc.is_available is False

    rec = SkillRecord(
        cell="c", skill_id="s", procedure="p",
        precondition="pc", success_criterion="sc",
    )
    result = svc.record(rec)
    assert result["action"] == "skipped"
    assert result["reason"] == "genome_unavailable"


# ─── query() with tier filter ───────────────────────────────────────


def test_query_returns_matching_skill(service):
    service.record(SkillRecord(
        cell="rag", skill_id="rag:rrf",
        procedure="Hybrid search with RRF fusion.",
        precondition="BM25 + dense indices ready",
        success_criterion="Recall > 0.85",
    ))
    service.record(SkillRecord(
        cell="rag", skill_id="rag:rerank",
        procedure="CrossEncoder reranking on top-20.",
        precondition="Candidate set ready",
        success_criterion="NDCG improved",
    ))
    results = service.query(SkillQuery(query="RRF"))
    assert len(results) == 1
    assert results[0].skill_id == "rag:rrf"


def test_query_filters_by_tier(service):
    service.record(SkillRecord(
        cell="c1", skill_id="tier1_skill",
        procedure="hot procedure alpha",
        precondition="pc", success_criterion="sc",
        confidence=0.9,
    ))
    service.record(SkillRecord(
        cell="c1", skill_id="tier2_skill",
        procedure="hot procedure bravo",
        precondition="pc", success_criterion="sc",
        confidence=0.75,
    ))
    # Directly promote tiers via internal genome access — normally done by
    # the weekly cron; in the unit test we seed the state.
    import sqlite3
    conn = sqlite3.connect(service._db_path)
    conn.execute("UPDATE genome SET tier='tier1' WHERE id='tier1_skill'")
    conn.execute("UPDATE genome SET tier='tier2' WHERE id='tier2_skill'")
    conn.commit()
    conn.close()

    tier1_only = service.query(SkillQuery(query="hot", tier=SkillTier.TIER1))
    assert len(tier1_only) == 1
    assert tier1_only[0].skill_id == "tier1_skill"


def test_query_filters_by_min_confidence(service):
    service.record(SkillRecord(
        cell="c1", skill_id="high",
        procedure="solid technique",
        precondition="pc", success_criterion="sc",
        confidence=0.9,
    ))
    service.record(SkillRecord(
        cell="c1", skill_id="low",
        procedure="solid technique",
        precondition="pc", success_criterion="sc",
        confidence=0.4,
    ))
    results = service.query(SkillQuery(query="solid", min_confidence=0.7))
    ids = [r.skill_id for r in results]
    assert "high" in ids
    assert "low" not in ids


# ─── stats() ────────────────────────────────────────────────────────


def test_stats_aggregates_by_tier_and_cell(service):
    service.record(SkillRecord(
        cell="rag", skill_id="rag:a", procedure="p",
        precondition="pc", success_criterion="sc", confidence=0.9,
    ))
    service.record(SkillRecord(
        cell="rag", skill_id="rag:b", procedure="p",
        precondition="pc", success_criterion="sc", confidence=0.6,
    ))
    service.record(SkillRecord(
        cell="crm", skill_id="crm:a", procedure="p",
        precondition="pc", success_criterion="sc", confidence=0.8,
    ))
    import sqlite3
    conn = sqlite3.connect(service._db_path)
    conn.execute("UPDATE genome SET tier='tier1' WHERE id='rag:a'")
    conn.commit()
    conn.close()

    stats = service.stats()
    assert stats["total"] == 3
    assert stats["by_tier"]["tier1"] == 1
    assert stats["by_tier"]["tier2"] == 0
    assert stats["by_tier"]["untiered"] == 2
    assert stats["by_cell"]["rag"] == 2
    assert stats["by_cell"]["crm"] == 1
    assert 0.0 <= stats["avg_confidence"] <= 1.0


# ─── top skills ──────────────────────────────────────────────────────


def test_get_top_skills_tier1_only(service):
    for i in range(3):
        service.record(SkillRecord(
            cell="c", skill_id=f"t1_{i}", procedure=f"p{i}",
            precondition="pc", success_criterion="sc", confidence=0.9,
        ))
    service.record(SkillRecord(
        cell="c", skill_id="nope", procedure="px",
        precondition="pc", success_criterion="sc", confidence=0.5,
    ))
    import sqlite3
    conn = sqlite3.connect(service._db_path)
    conn.execute("UPDATE genome SET tier='tier1' WHERE id LIKE 't1_%'")
    conn.commit()
    conn.close()

    top = service.get_top_skills(tier=SkillTier.TIER1)
    ids = {r.skill_id for r in top}
    assert ids == {"t1_0", "t1_1", "t1_2"}


def test_get_top_skills_empty_when_none_promoted(service):
    service.record(SkillRecord(
        cell="c", skill_id="cold", procedure="p",
        precondition="pc", success_criterion="sc", confidence=0.5,
    ))
    top = service.get_top_skills(tier=SkillTier.TIER1)
    assert top == []


# ─── get_by_id ───────────────────────────────────────────────────────


def test_get_by_id_returns_skill(service):
    service.record(SkillRecord(
        cell="c", skill_id="findme", procedure="proc body",
        precondition="pc", success_criterion="sc", confidence=0.7,
    ))
    result = service.get_by_id("findme")
    assert result is not None
    assert result.skill_id == "findme"
    assert result.procedure == "proc body"


def test_get_by_id_none_for_missing(service):
    assert service.get_by_id("nope") is None


def test_get_by_id_none_for_non_skill_type(service):
    """A trajectory row with the same id must not leak through get_by_id."""
    from cell_core.genome import Genome
    g = Genome(db_path=service._db_path)
    g.record_trajectory(
        cell="c", trajectory_id="dup", outcome="success", procedure="trajectory body",
    )
    assert service.get_by_id("dup") is None


# ─── merge proposals ────────────────────────────────────────────────


def test_merge_proposals_empty_when_file_missing(service, tmp_path, monkeypatch):
    """When the proposals jsonl doesn't exist yet, service returns an empty list."""
    nonexistent = tmp_path / "never_written.jsonl"
    monkeypatch.setattr(
        "backend.services.skill.service.MERGE_PROPOSALS_PATH", str(nonexistent),
    )
    assert service.merge_proposals() == []


def test_merge_proposals_reads_jsonl(service, tmp_path, monkeypatch):
    path = tmp_path / "proposals.jsonl"
    path.write_text(
        '{"pair": ["a", "b"], "cosine": 0.08, "rationale": "similar"}\n'
        '{"pair": ["c", "d"], "cosine": 0.11, "rationale": "similar"}\n'
    )
    monkeypatch.setattr(
        "backend.services.skill.service.MERGE_PROPOSALS_PATH", str(path),
    )
    proposals = service.merge_proposals()
    assert len(proposals) == 2
    assert proposals[0]["pair"] == ["a", "b"]
