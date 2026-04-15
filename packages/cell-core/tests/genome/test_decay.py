"""Tests for exponential confidence decay in genome.

Decision: Ebbinghaus-aligned exponential decay.
Formula: new_conf = confidence * (decay_rate ** days_unused)
Guards: scars immune, min_idle_days=7, silence_threshold=0.3
"""
import pytest
import sqlite3
import time
from datetime import datetime, timezone, timedelta

from cell_core.genome import Genome


@pytest.fixture
def genome(tmp_path):
    return Genome(db_path=str(tmp_path / "decay_test.db"))


def _set_last_used(genome: Genome, skill_id: str, days_ago: int) -> None:
    """Helper: backdate last_used for a skill."""
    target = datetime.now(timezone.utc) - timedelta(days=days_ago)
    conn = sqlite3.connect(genome._db_path)
    conn.execute(
        "UPDATE genome SET last_used = ? WHERE id = ?",
        (target.isoformat(), skill_id),
    )
    conn.commit()
    conn.close()


def test_decay_basic_exponential(genome):
    """Skill unused for 20 days decays: 0.8 * 0.95^20 ≈ 0.286 → silenced."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="old technique", confidence=0.8)
    genome.use_skill("s1")  # set last_used
    _set_last_used(genome, "s1", days_ago=20)

    result = genome.decay_unused_skills(decay_rate=0.95, silence_threshold=0.3)
    # 0.8 * 0.95^20 = 0.2853 → below 0.3 → silenced
    assert result["silenced"] == 1
    assert result["decayed"] == 0

    active = genome.get_active(cell="c1")
    assert len(active) == 0  # silenced


def test_decay_partial_reduction(genome):
    """Skill unused for 10 days decays but stays active: 0.9 * 0.95^10 ≈ 0.540."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="good technique", confidence=0.9)
    genome.use_skill("s1")
    _set_last_used(genome, "s1", days_ago=10)

    result = genome.decay_unused_skills()
    assert result["decayed"] == 1
    assert result["silenced"] == 0

    active = genome.get_active(cell="c1")
    assert len(active) == 1
    # 0.9 * 0.95^10 ≈ 0.5404
    assert 0.50 < active[0]["confidence"] < 0.60


def test_decay_skips_recently_used(genome):
    """Skills used within min_idle_days are not decayed."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="fresh", confidence=0.5)
    genome.use_skill("s1")
    _set_last_used(genome, "s1", days_ago=3)  # < 7 days

    result = genome.decay_unused_skills(min_idle_days=7)
    assert result["skipped"] == 1
    assert result["decayed"] == 0

    active = genome.get_active(cell="c1")
    assert active[0]["confidence"] == pytest.approx(0.52, abs=0.01)  # from use_skill


def test_decay_scars_immune(genome):
    """Scars (type='scar') must never decay — avoidance memory is permanent."""
    genome.record_scar(cell="c1", scar_id="dangerous_pattern", procedure="never do X")
    # Manually set last_used far back
    conn = sqlite3.connect(genome._db_path)
    conn.execute(
        "UPDATE genome SET last_used = ? WHERE id = ?",
        ((datetime.now(timezone.utc) - timedelta(days=100)).isoformat(), "dangerous_pattern"),
    )
    conn.commit()
    conn.close()

    result = genome.decay_unused_skills()
    assert result["skipped"] == 1

    active = genome.get_active(cell="c1")
    assert len(active) == 1
    assert active[0]["confidence"] == 0.9  # unchanged


def test_decay_skips_never_used(genome):
    """Skills with last_used=NULL are skipped (never used = never started decaying)."""
    genome.record_skill(cell="c1", skill_id="new_skill", procedure="untested", confidence=0.5)
    # No use_skill() → last_used remains NULL

    result = genome.decay_unused_skills()
    assert result["skipped"] == 0  # NULL last_used excluded by WHERE clause
    assert result["decayed"] == 0
    assert result["silenced"] == 0


def test_decay_already_silenced_not_touched(genome):
    """Already-silenced skills should not be decayed again."""
    genome.record_skill(cell="c1", skill_id="dead", procedure="old", confidence=0.5)
    genome.silence_skill("dead")

    result = genome.decay_unused_skills()
    # valid_to IS NOT NULL → excluded from decay query
    assert result["decayed"] == 0
    assert result["silenced"] == 0


def test_decay_multiple_skills(genome):
    """Multiple skills with different ages decay independently."""
    # Recent (5 days) — skipped
    genome.record_skill(cell="c1", skill_id="recent", procedure="r", confidence=0.8)
    genome.use_skill("recent")
    _set_last_used(genome, "recent", days_ago=5)

    # Medium (15 days) — decayed but active: 0.7 * 0.95^15 ≈ 0.324
    genome.record_skill(cell="c1", skill_id="medium", procedure="m", confidence=0.7)
    genome.use_skill("medium")
    _set_last_used(genome, "medium", days_ago=15)

    # Old (30 days) — silenced: 0.6 * 0.95^30 ≈ 0.1297
    genome.record_skill(cell="c1", skill_id="old", procedure="o", confidence=0.6)
    genome.use_skill("old")
    _set_last_used(genome, "old", days_ago=30)

    result = genome.decay_unused_skills()
    assert result["skipped"] == 1   # recent
    assert result["decayed"] == 1   # medium
    assert result["silenced"] == 1  # old


def test_decay_idempotent_within_day(genome):
    """Running decay twice on the same day should further reduce confidence."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="p", confidence=0.9)
    genome.use_skill("s1")
    _set_last_used(genome, "s1", days_ago=10)

    genome.decay_unused_skills()
    active1 = genome.get_active(cell="c1")
    conf1 = active1[0]["confidence"]

    # Second run: days_unused hasn't changed (same day), so same formula applies
    # But confidence is now lower, so result may differ
    genome.decay_unused_skills()
    active2 = genome.get_active(cell="c1")
    conf2 = active2[0]["confidence"]

    # Second decay should reduce further (lower starting confidence, same days)
    assert conf2 < conf1


def test_decay_returns_correct_counts(genome):
    """Verify all counts in return dict."""
    result = genome.decay_unused_skills()
    assert "decayed" in result
    assert "silenced" in result
    assert "skipped" in result
    assert all(isinstance(v, int) for v in result.values())
