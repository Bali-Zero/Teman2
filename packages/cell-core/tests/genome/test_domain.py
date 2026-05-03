"""Tests for domain column migration and domain taxonomy."""
import pytest
import sqlite3

from cell_core.genome import Genome
from cell_core.hgt.domains import CANONICAL_DOMAINS, validate_domain


@pytest.fixture
def genome(tmp_path):
    return Genome(db_path=str(tmp_path / "domain_test.db"))


# ─── Domain taxonomy ─────────────────────────────────────


def test_canonical_domains_count():
    """11 canonical domains defined."""
    assert len(CANONICAL_DOMAINS) == 11


def test_validate_known_domain():
    assert validate_domain("visa") == "visa"
    assert validate_domain("VISA") == "visa"
    assert validate_domain(" Tax ") == "tax"


def test_validate_unknown_domain():
    assert validate_domain("bananas") == "generic"
    assert validate_domain("") == "generic"


def test_generic_in_domains():
    assert "generic" in CANONICAL_DOMAINS


# ─── Schema migration ────────────────────────────────────


def test_domain_column_exists(genome):
    """After init, genome table should have domain column."""
    conn = sqlite3.connect(genome._db_path)
    cursor = conn.execute("PRAGMA table_info(genome)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert "domain" in columns


def test_domain_default_generic(genome):
    """Skills recorded without domain get 'generic'."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="test")
    active = genome.get_active(cell="c1")
    assert active[0]["domain"] == "generic"


def test_record_skill_with_domain(genome):
    """record_skill accepts domain parameter."""
    genome.record_skill(
        cell="c1", skill_id="visa_skill",
        procedure="KITAS processing shortcut",
        domain="visa",
    )
    active = genome.get_active(cell="c1")
    assert active[0]["domain"] == "visa"


def test_domain_preserved_on_upsert(genome):
    """Upserting skill preserves domain if not changed."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="v1", domain="legal")
    genome.record_skill(cell="c1", skill_id="s1", procedure="v2", domain="legal")
    active = genome.get_active(cell="c1")
    assert active[0]["domain"] == "legal"
    assert active[0]["procedure"] == "v2"


def test_domain_index_exists(genome):
    """idx_genome_domain index should exist."""
    conn = sqlite3.connect(genome._db_path)
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='genome'"
    ).fetchall()
    conn.close()
    index_names = {row[0] for row in indexes}
    assert "idx_genome_domain" in index_names


def test_idempotent_schema_migration(tmp_path):
    """Creating Genome twice on same DB shouldn't fail."""
    db = str(tmp_path / "idempotent.db")
    g1 = Genome(db_path=db)
    g1.record_skill(cell="c1", skill_id="s1", procedure="test", domain="visa")

    # Second init should not crash
    g2 = Genome(db_path=db)
    active = g2.get_active(cell="c1")
    assert len(active) == 1
    assert active[0]["domain"] == "visa"


def test_get_active_filter_by_domain(genome):
    """get_active should support domain filtering."""
    genome.record_skill(cell="c1", skill_id="s1", procedure="a", domain="visa")
    genome.record_skill(cell="c1", skill_id="s2", procedure="b", domain="tax")
    genome.record_skill(cell="c1", skill_id="s3", procedure="c", domain="visa")

    visa_skills = genome.get_active(cell="c1", domain="visa")
    assert len(visa_skills) == 2
    assert all(s["domain"] == "visa" for s in visa_skills)

    tax_skills = genome.get_active(cell="c1", domain="tax")
    assert len(tax_skills) == 1
