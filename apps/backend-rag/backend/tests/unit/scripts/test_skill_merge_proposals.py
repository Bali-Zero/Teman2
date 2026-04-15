"""Tests for backend/scripts/skill_merge_proposals.py.

The job scans active skills, embeds their procedures, and emits a jsonl of
pairs whose cosine distance falls under a threshold. We never auto-apply
(SYMBIOSIS Legge 5) — Zero reviews and approves.

Testing strategy:
- Use a deterministic mock embedder that returns stable vectors based on
  the text. Real OpenAI calls are out of scope.
- Compute cosine similarity in-process so the job runs offline.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.scripts.skill_merge_proposals import (
    cosine_distance,
    find_merge_candidates,
    main,
)


class StubEmbedder:
    """Deterministic embedder: returns a fixed vector per skill_id.

    The test sets up the map so two near-duplicate skills share almost-identical
    vectors (cosine distance ~0.05), while an unrelated skill lives far away.
    """

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def embed(self, text: str, skill_id: str | None = None) -> list[float]:
        if skill_id and skill_id in self._vectors:
            return self._vectors[skill_id]
        # Fallback: deterministic pseudo-hash vector so unmapped skills don't
        # collide by accident (each gets a unique far-away direction).
        return [float(hash(text) % 1000) / 1000.0] + [0.0] * 1535


# ─── cosine_distance ──────────────────────────────────────────────


def test_cosine_distance_identical_vectors_is_zero():
    v = [1.0, 0.0, 0.0]
    assert cosine_distance(v, v) == pytest.approx(0.0, abs=1e-9)


def test_cosine_distance_orthogonal_is_one():
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    assert cosine_distance(v1, v2) == pytest.approx(1.0, abs=1e-9)


def test_cosine_distance_opposite_is_two():
    v1 = [1.0, 0.0, 0.0]
    v2 = [-1.0, 0.0, 0.0]
    assert cosine_distance(v1, v2) == pytest.approx(2.0, abs=1e-9)


def test_cosine_distance_zero_vector_returns_inf():
    """Degenerate input (zero-length embedding) should NOT crash — return inf
    so the pair is never suggested as a merge candidate."""
    assert math.isinf(cosine_distance([0.0, 0.0], [1.0, 0.0]))


# ─── find_merge_candidates ────────────────────────────────────────


def _skill(skill_id: str, procedure: str = "p", confidence: float = 0.7) -> dict:
    return {
        "id": skill_id,
        "cell_origin": "c",
        "type": "skill",
        "procedure": procedure,
        "precondition": "pc",
        "success_criterion": "sc",
        "confidence": confidence,
        "valid_to": None,
    }


def test_find_candidates_returns_pair_below_threshold():
    skills = [
        _skill("a", "hybrid rrf retrieval"),
        _skill("b", "hybrid rrf retrieval"),  # near duplicate
        _skill("c", "ocr indonesian akta"),
    ]
    embedder = StubEmbedder({
        "a": [1.0, 0.0, 0.0],
        "b": [0.99, 0.01, 0.0],   # cosine ~0 with a
        "c": [0.0, 1.0, 0.0],     # orthogonal
    })
    candidates = find_merge_candidates(
        skills, embedder=embedder, threshold=0.15,
    )
    pairs = {frozenset(c["pair"]) for c in candidates}
    assert frozenset({"a", "b"}) in pairs
    assert frozenset({"a", "c"}) not in pairs
    assert frozenset({"b", "c"}) not in pairs


def test_find_candidates_respects_threshold():
    skills = [_skill("a"), _skill("b")]
    embedder = StubEmbedder({
        "a": [1.0, 0.0],
        "b": [0.0, 1.0],  # cosine distance = 1.0, above 0.15
    })
    candidates = find_merge_candidates(skills, embedder=embedder, threshold=0.15)
    assert candidates == []


def test_find_candidates_empty_when_fewer_than_two_skills():
    candidates = find_merge_candidates([_skill("a")], embedder=StubEmbedder({}))
    assert candidates == []


def test_find_candidates_includes_rationale_and_distance():
    skills = [
        _skill("a", "hybrid rrf retrieval"),
        _skill("b", "hybrid rrf retrieval"),
    ]
    embedder = StubEmbedder({
        "a": [1.0, 0.0], "b": [0.999, 0.001],
    })
    candidates = find_merge_candidates(skills, embedder=embedder, threshold=0.15)
    assert len(candidates) == 1
    c = candidates[0]
    assert set(c.keys()) >= {"pair", "cosine", "rationale", "procedures"}
    assert 0.0 <= c["cosine"] < 0.15
    assert c["procedures"]["a"] == "hybrid rrf retrieval"


def test_find_candidates_does_not_include_self_pair():
    skills = [_skill("a")]
    embedder = StubEmbedder({"a": [1.0, 0.0]})
    candidates = find_merge_candidates(skills, embedder=embedder, threshold=0.15)
    assert candidates == []


def test_find_candidates_each_pair_emitted_once():
    skills = [
        _skill("a"), _skill("b"), _skill("c"),
    ]
    embedder = StubEmbedder({
        "a": [1.0, 0.0], "b": [1.0, 0.0], "c": [1.0, 0.0],  # all identical
    })
    candidates = find_merge_candidates(skills, embedder=embedder, threshold=0.15)
    pairs = {frozenset(c["pair"]) for c in candidates}
    assert pairs == {
        frozenset({"a", "b"}),
        frozenset({"a", "c"}),
        frozenset({"b", "c"}),
    }


# ─── main() smoke ────────────────────────────────────────────────


def test_main_writes_proposals_jsonl(tmp_path, monkeypatch):
    """Integration smoke: seed the Genome with two near-duplicate skills,
    run main with the stub embedder, assert a jsonl line appears."""
    from cell_core.genome import Genome
    from backend.services.skill.models import SkillRecord
    from backend.services.skill.service import SkillService

    db = tmp_path / "skills.db"
    svc = SkillService(db_path=str(db))

    svc.record(SkillRecord(
        cell="c", skill_id="m1", procedure="hybrid rrf retrieval",
        precondition="pc", success_criterion="sc",
    ))
    svc.record(SkillRecord(
        cell="c", skill_id="m2", procedure="hybrid rrf retrieval",
        precondition="pc", success_criterion="sc",
    ))

    proposals_path = tmp_path / "proposals.jsonl"

    import backend.scripts.skill_merge_proposals as mod

    def _factory():
        return StubEmbedder({"m1": [1.0, 0.0], "m2": [0.999, 0.001]})

    monkeypatch.setattr(mod, "_default_embedder", _factory)

    rc = main([
        "--db-path", str(db),
        "--out", str(proposals_path),
        "--threshold", "0.15",
    ])
    assert rc == 0
    assert proposals_path.exists()

    lines = [line for line in proposals_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert set(record["pair"]) == {"m1", "m2"}
    assert record["cosine"] < 0.15


def test_main_with_empty_genome_writes_no_proposals(tmp_path, monkeypatch):
    import backend.scripts.skill_merge_proposals as mod

    def _factory():
        return StubEmbedder({})

    monkeypatch.setattr(mod, "_default_embedder", _factory)

    db = tmp_path / "empty.db"
    proposals = tmp_path / "p.jsonl"
    rc = main([
        "--db-path", str(db), "--out", str(proposals), "--threshold", "0.15",
    ])
    assert rc == 0
    # File either does not exist or is empty.
    if proposals.exists():
        assert proposals.read_text().strip() == ""
