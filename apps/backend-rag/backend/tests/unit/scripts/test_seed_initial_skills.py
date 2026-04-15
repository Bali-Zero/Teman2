"""Tests for backend/scripts/seed_initial_skills.py.

The seed script ships a hand-picked set of canonical skills (precondition +
procedure + success_criterion) that represent the reusable procedural
knowledge the Bali Zero platform has accumulated. Unlike
``catalog_initial_skills`` (AST scan, discovery), the seed is curated and
intended for ``--apply`` in the Week 3-4 PR.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.scripts.seed_initial_skills import (
    SEED_SKILLS,
    apply_seed,
    main,
)


def test_seed_count_within_target_range():
    """30-40 skills is the ceiling from the Week 3-4 plan (quality > volume)."""
    assert 30 <= len(SEED_SKILLS) <= 40, f"got {len(SEED_SKILLS)} seed skills"


def test_seed_ids_are_unique():
    ids = [s["skill_id"] for s in SEED_SKILLS]
    assert len(ids) == len(set(ids)), "duplicate skill_ids"


def test_every_seed_has_required_fields():
    """Every row must have the canonical fields populated (no empty procedure,
    precondition, or success_criterion — the point of the seed is signal)."""
    required = ("cell", "skill_id", "procedure", "precondition", "success_criterion")
    for s in SEED_SKILLS:
        for field in required:
            assert s.get(field), f"{s.get('skill_id', '?')} missing {field}"


def test_seed_confidence_in_range():
    for s in SEED_SKILLS:
        assert 0.0 <= s["confidence"] <= 1.0


def test_seed_scope_is_project():
    """Seeds are germline knowledge — Project scope (the default)."""
    for s in SEED_SKILLS:
        # scope defaults to Project; if explicit, it must still be Project.
        assert s.get("scope", "Project") == "Project"


def test_seed_cell_diversity():
    """No single cell should hog the seed — at least 5 distinct cells."""
    cells = {s["cell"] for s in SEED_SKILLS}
    assert len(cells) >= 5, f"seed too concentrated: {cells}"


def test_apply_seed_records_all_into_fresh_genome(tmp_path):
    """apply_seed should call SkillService.record for every seed and return counts."""
    from cell_core.genome import Genome

    db = tmp_path / "seed.db"
    g = Genome(db_path=str(db))

    counts = apply_seed(SEED_SKILLS, genome=g)
    assert counts["inserted"] == len(SEED_SKILLS)
    assert counts["updated"] == 0
    assert counts["skipped"] == 0

    # Sanity: every id is retrievable.
    for s in SEED_SKILLS[:3]:
        active = g.get_active(cell=s["cell"])
        assert any(r["id"] == s["skill_id"] for r in active)


def test_apply_seed_idempotent(tmp_path):
    """Second apply must be a no-op on inserts (updates only, same content)."""
    from cell_core.genome import Genome

    db = tmp_path / "seed.db"
    g = Genome(db_path=str(db))

    apply_seed(SEED_SKILLS, genome=g)
    counts = apply_seed(SEED_SKILLS, genome=g)
    assert counts["inserted"] == 0
    assert counts["updated"] == len(SEED_SKILLS)


def test_main_dry_run_does_not_write(tmp_path, capsys):
    """main() with default flags must be a dry-run — no rows written."""
    from cell_core.genome import Genome

    db = tmp_path / "dryrun.db"
    rc = main(["--db-path", str(db)])
    assert rc == 0

    g = Genome(db_path=str(db))
    # Fresh genome after dry-run: nothing recorded.
    assert g.stats()["total"] == 0


def test_main_apply_writes(tmp_path):
    from cell_core.genome import Genome

    db = tmp_path / "apply.db"
    rc = main(["--db-path", str(db), "--apply"])
    assert rc == 0

    g = Genome(db_path=str(db))
    assert g.stats()["total"] == len(SEED_SKILLS)
