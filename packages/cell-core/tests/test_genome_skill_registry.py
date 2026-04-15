"""Tests for Sprint 5.2 Week 3-4 Skill Registry extensions of cell_core.genome.

Covers:
- tier column (nullable, tier1|tier2|None) via runtime migration
- promote_skills(): uses>100 AND success_rate>=0.85 → tier1;
  uses>30 AND success_rate>=0.7 → tier2
- silence_stale_skills_v2(): (uses<5 AND last_used>30d) OR confidence<0.3 → valid_to=today
- record_skill keeps tier across upsert
- migration idempotent on pre-existing DB
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

import pytest

from cell_core.genome import Genome


@pytest.fixture
def genome(tmp_path):
    db = str(tmp_path / "skill_registry.db")
    return Genome(db_path=db)


# ─── tier column existence & migration idempotency ────────────────


def test_tier_column_exists_after_init(genome):
    """After Genome() init, the 'tier' column must exist on the genome table."""
    conn = sqlite3.connect(genome._db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(genome)")}
    conn.close()
    assert "tier" in cols, f"tier column missing; got {sorted(cols)}"


def test_tier_column_nullable_by_default(genome):
    """Newly recorded skills have tier=NULL until promoted."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="x", confidence=0.5)
    conn = sqlite3.connect(genome._db_path)
    row = conn.execute("SELECT tier FROM genome WHERE id='s1'").fetchone()
    conn.close()
    assert row[0] is None


def test_tier_migration_idempotent_on_existing_db(tmp_path):
    """Opening an existing Genome DB twice must not raise or duplicate the column."""
    db = str(tmp_path / "idem.db")
    g1 = Genome(db_path=db)
    g1.record_skill(cell="c1", skill_id="s1", procedure="x")

    # Second open triggers _ensure_schema again; must be idempotent.
    g2 = Genome(db_path=db)
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(genome)")]
    # tier should appear exactly once
    assert cols.count("tier") == 1
    # Existing data preserved
    row = conn.execute("SELECT id FROM genome WHERE id='s1'").fetchone()
    conn.close()
    assert row is not None


def test_tier_migration_on_legacy_db_without_column(tmp_path):
    """A pre-Week-3 DB without the tier column must gain it on open, with existing rows' tier=NULL."""
    db = str(tmp_path / "legacy.db")
    # Build a legacy-shaped genome table manually: no tier column.
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE genome (
            id TEXT PRIMARY KEY,
            cell_origin TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('skill','pattern','scar','insight','trajectory')),
            scope TEXT NOT NULL DEFAULT 'Project' CHECK(scope IN ('Project','Personal')),
            precondition TEXT,
            procedure TEXT NOT NULL,
            success_criterion TEXT,
            valid_from TEXT NOT NULL,
            valid_to TEXT,
            confidence REAL NOT NULL DEFAULT 0.5,
            uses INTEGER NOT NULL DEFAULT 0,
            last_used TEXT,
            inherited_from TEXT,
            outcome TEXT,
            tokens INTEGER,
            duration_ms INTEGER,
            tags TEXT
        );
        INSERT INTO genome (id, cell_origin, type, procedure, valid_from, confidence)
        VALUES ('legacy', 'c1', 'skill', 'proc', '2026-01-01', 0.8);
    """)
    conn.commit()
    conn.close()

    # Open via Genome — migration adds tier.
    g = Genome(db_path=db)
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(genome)")}
    assert "tier" in cols
    row = conn.execute("SELECT tier FROM genome WHERE id='legacy'").fetchone()
    conn.close()
    assert row[0] is None  # Legacy rows start untiered.


# ─── promote_skills() ─────────────────────────────────────────────


def _backdate_skill(db_path: str, skill_id: str, uses: int, success_rate: float) -> None:
    """Test helper: push a skill to a given uses/success_rate state directly."""
    # We model success_rate as confidence in the current schema (no separate
    # success counter). Tests pass success_rate and we store into confidence.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE genome SET uses = ?, confidence = ? WHERE id = ?",
        (uses, success_rate, skill_id),
    )
    conn.commit()
    conn.close()


def test_promote_skills_tier1_for_hot_and_reliable(genome):
    """uses>100 AND confidence>=0.85 → tier1."""
    genome.record_skill(cell="c1", skill_id="hot", procedure="x", confidence=0.5)
    _backdate_skill(genome._db_path, "hot", uses=150, success_rate=0.9)

    promoted = genome.promote_skills()
    assert promoted["tier1"] == 1
    conn = sqlite3.connect(genome._db_path)
    tier = conn.execute("SELECT tier FROM genome WHERE id='hot'").fetchone()[0]
    conn.close()
    assert tier == "tier1"


def test_promote_skills_tier2_for_warm(genome):
    """uses>30 AND confidence>=0.7 but not tier1 → tier2."""
    genome.record_skill(cell="c1", skill_id="warm", procedure="x", confidence=0.5)
    _backdate_skill(genome._db_path, "warm", uses=50, success_rate=0.75)

    promoted = genome.promote_skills()
    assert promoted["tier2"] == 1
    conn = sqlite3.connect(genome._db_path)
    tier = conn.execute("SELECT tier FROM genome WHERE id='warm'").fetchone()[0]
    conn.close()
    assert tier == "tier2"


def test_promote_skills_leaves_cold_untiered(genome):
    """Cold skills (few uses or low confidence) stay tier=NULL."""
    genome.record_skill(cell="c1", skill_id="cold", procedure="x", confidence=0.5)
    _backdate_skill(genome._db_path, "cold", uses=5, success_rate=0.6)

    promoted = genome.promote_skills()
    assert promoted["tier1"] == 0
    assert promoted["tier2"] == 0
    conn = sqlite3.connect(genome._db_path)
    tier = conn.execute("SELECT tier FROM genome WHERE id='cold'").fetchone()[0]
    conn.close()
    assert tier is None


def test_promote_skills_ignores_non_skill_types(genome):
    """Trajectories/scars/patterns must never get a tier."""
    genome.record_trajectory(
        cell="c1", trajectory_id="t1", outcome="success",
        procedure="p", confidence=0.95,
    )
    _backdate_skill(genome._db_path, "t1", uses=200, success_rate=0.95)

    promoted = genome.promote_skills()
    assert promoted["tier1"] == 0
    conn = sqlite3.connect(genome._db_path)
    tier = conn.execute("SELECT tier FROM genome WHERE id='t1'").fetchone()[0]
    conn.close()
    assert tier is None


def test_promote_skills_does_not_downgrade(genome):
    """A skill already at tier1 must NOT drop to tier2 if it still qualifies tier2.

    Promotions are monotonic upward — only silence_stale can remove a tier.
    """
    genome.record_skill(cell="c1", skill_id="k", procedure="x", confidence=0.5)
    _backdate_skill(genome._db_path, "k", uses=200, success_rate=0.95)
    genome.promote_skills()  # tier1

    # Degrade the underlying metrics: still qualifies tier2 but not tier1
    _backdate_skill(genome._db_path, "k", uses=40, success_rate=0.72)
    genome.promote_skills()

    conn = sqlite3.connect(genome._db_path)
    tier = conn.execute("SELECT tier FROM genome WHERE id='k'").fetchone()[0]
    conn.close()
    assert tier == "tier1"  # retained


def test_promote_skills_returns_counts(genome):
    genome.record_skill(cell="c1", skill_id="s1", procedure="x")
    _backdate_skill(genome._db_path, "s1", uses=200, success_rate=0.9)
    genome.record_skill(cell="c1", skill_id="s2", procedure="x")
    _backdate_skill(genome._db_path, "s2", uses=60, success_rate=0.75)
    genome.record_skill(cell="c1", skill_id="s3", procedure="x")  # cold

    result = genome.promote_skills()
    assert result == {"tier1": 1, "tier2": 1}


# ─── silence_stale_skills_v2() ────────────────────────────────────


def test_silence_stale_v2_uses_low_and_old(genome):
    """uses<5 AND last_used>30 days old → valid_to=today."""
    genome.record_skill(cell="c1", skill_id="dusty", procedure="x", confidence=0.8)
    old = datetime.fromtimestamp(time.time() - 45 * 86400, tz=timezone.utc).date().isoformat()
    conn = sqlite3.connect(genome._db_path)
    conn.execute(
        "UPDATE genome SET uses = ?, last_used = ? WHERE id = 'dusty'",
        (2, old),
    )
    conn.commit()
    conn.close()

    n = genome.silence_stale_skills_v2()
    assert n == 1
    active = genome.get_active(cell="c1")
    assert len(active) == 0


def test_silence_stale_v2_confidence_below_threshold(genome):
    """confidence<0.3 → silenced regardless of uses."""
    genome.record_skill(cell="c1", skill_id="low_conf", procedure="x", confidence=0.2)
    n = genome.silence_stale_skills_v2()
    assert n == 1


def test_silence_stale_v2_keeps_hot_skills(genome):
    """High-confidence hot skills are never silenced by v2."""
    genome.record_skill(cell="c1", skill_id="hot", procedure="x", confidence=0.9)
    now = datetime.now(timezone.utc).date().isoformat()
    conn = sqlite3.connect(genome._db_path)
    conn.execute(
        "UPDATE genome SET uses = ?, last_used = ? WHERE id = 'hot'",
        (200, now),
    )
    conn.commit()
    conn.close()
    n = genome.silence_stale_skills_v2()
    assert n == 0


def test_silence_stale_v2_never_used_with_old_valid_from(genome):
    """Skills recorded >30 days ago, never used (uses=0, last_used=NULL) are stale."""
    genome.record_skill(cell="c1", skill_id="orphan", procedure="x", confidence=0.5)
    old = datetime.fromtimestamp(time.time() - 60 * 86400, tz=timezone.utc).date().isoformat()
    conn = sqlite3.connect(genome._db_path)
    conn.execute("UPDATE genome SET valid_from = ? WHERE id = 'orphan'", (old,))
    conn.commit()
    conn.close()
    n = genome.silence_stale_skills_v2()
    assert n == 1


def test_silence_stale_v2_idempotent(genome):
    """Running twice silences the same rows once; second run returns 0."""
    genome.record_skill(cell="c1", skill_id="ghost", procedure="x", confidence=0.1)
    assert genome.silence_stale_skills_v2() == 1
    assert genome.silence_stale_skills_v2() == 0


# ─── record_skill preserves tier across upsert ────────────────────


def test_record_skill_upsert_preserves_tier(genome):
    """Re-recording an already-tiered skill must not reset its tier to NULL."""
    genome.record_skill(cell="c1", skill_id="k", procedure="v1", confidence=0.5)
    _backdate_skill(genome._db_path, "k", uses=200, success_rate=0.9)
    genome.promote_skills()

    # Upsert with new procedure
    genome.record_skill(cell="c1", skill_id="k", procedure="v2", confidence=0.7)

    conn = sqlite3.connect(genome._db_path)
    row = conn.execute("SELECT tier, procedure FROM genome WHERE id='k'").fetchone()
    conn.close()
    assert row[0] == "tier1"
    assert row[1] == "v2"
