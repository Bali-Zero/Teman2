"""Tests for cell_core.genome — DNA recording."""
import pytest
import sqlite3
import tempfile
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from cell_core.genome import Genome


@pytest.fixture
def genome(tmp_path):
    db = str(tmp_path / "test_genome.db")
    return Genome(db_path=db)


def test_record_skill_insert(genome):
    action = genome.record_skill(
        cell="akta_archive",
        skill_id="proxy_detection_v1",
        procedure="Use Python regex for 'bertindak berdasarkan' before LLM.",
        precondition="Text contains Indonesian akta with Surat Kuasa.",
        success_criterion="Zero procuratori in founders table.",
        confidence=0.94,
    )
    assert action == "inserted"


def test_record_skill_upsert(genome):
    """Re-recording the same skill_id updates procedure and keeps max confidence."""
    genome.record_skill(cell="akta_archive", skill_id="s1", procedure="do X", confidence=0.8)
    action = genome.record_skill(cell="akta_archive", skill_id="s1", procedure="do Y", confidence=0.6)
    assert action == "updated"
    # procedure updated, confidence kept at max(0.8, 0.6) = 0.8
    results = genome.get_active(cell="akta_archive")
    assert results[0]["procedure"] == "do Y"
    assert results[0]["confidence"] == 0.8


def test_get_active_returns_inserted(genome):
    genome.record_skill(cell="akta_archive", skill_id="s1", procedure="do X", confidence=0.8)
    results = genome.get_active(cell="akta_archive")
    assert len(results) == 1
    assert results[0]["id"] == "s1"
    assert results[0]["confidence"] == 0.8


def test_silence_skill(genome):
    genome.record_skill(cell="c1", skill_id="old_skill", procedure="old way", confidence=0.9)
    genome.silence_skill("old_skill", reason="deprecated")
    active = genome.get_active(cell="c1")
    assert len(active) == 0  # silenced, not in active results


def test_silence_does_not_delete(genome):
    genome.record_skill(cell="c1", skill_id="old_skill", procedure="old way")
    genome.silence_skill("old_skill")
    # Still in DB, just has valid_to set
    conn = sqlite3.connect(genome._db_path)
    row = conn.execute("SELECT valid_to FROM genome WHERE id='old_skill'").fetchone()
    conn.close()
    assert row is not None
    assert row[0] is not None  # valid_to is set, not NULL


def test_use_skill_increments(genome):
    genome.record_skill(cell="c1", skill_id="s1", procedure="do X", confidence=0.5)
    genome.use_skill("s1")
    genome.use_skill("s1")
    results = genome.get_active(cell="c1")
    assert results[0]["uses"] == 2
    assert results[0]["confidence"] > 0.5  # confidence increased


def test_inherit_genome_selective(genome):
    # High confidence Project skill — should be inherited
    genome.record_skill(
        cell="akta_archive", skill_id="good_skill",
        procedure="solid technique", confidence=0.9, scope="Project",
    )
    # Low confidence — should NOT be inherited (below 0.7 threshold)
    genome.record_skill(
        cell="akta_archive", skill_id="weak_skill",
        procedure="uncertain technique", confidence=0.5, scope="Project",
    )
    # Personal scope — should NOT be inherited
    genome.record_skill(
        cell="akta_archive", skill_id="personal_skill",
        procedure="local hack", confidence=0.95, scope="Personal",
    )
    # Scar — should NOT be inherited (type='scar')
    genome.record_scar(
        cell="akta_archive", scar_id="scar_1",
        procedure="never do this",
    )

    inherited = genome.inherit_genome(parent_cell="akta_archive", min_confidence=0.7)
    ids = [s["id"] for s in inherited]

    assert "good_skill" in ids
    assert "weak_skill" not in ids
    assert "personal_skill" not in ids
    assert "scar_1" not in ids


def test_inherit_genome_empty_if_no_skills(genome):
    inherited = genome.inherit_genome(parent_cell="nonexistent_cell")
    assert inherited == []


def test_search_fts(genome):
    genome.record_skill(
        cell="akta_archive", skill_id="proxy_v1",
        procedure="Use regex to detect Surat Kuasa proxies in Indonesian akta.",
        confidence=0.9,
    )
    genome.record_skill(
        cell="akta_archive", skill_id="kbli_v1",
        procedure="Always extract KBLI codes from the business scope section.",
        confidence=0.8,
    )
    results = genome.search("Surat Kuasa")
    assert len(results) >= 1
    assert any(r["id"] == "proxy_v1" for r in results)


def test_stats(genome):
    genome.record_skill(cell="c1", skill_id="s1", procedure="a", confidence=0.8)
    genome.record_skill(cell="c1", skill_id="s2", procedure="b", confidence=0.6, entry_type="pattern")
    genome.record_scar(cell="c1", scar_id="scar1", procedure="never")

    stats = genome.stats(cell="c1")
    assert stats["total"] == 3
    assert stats["active"] == 3
    assert stats["silenced"] == 0
    assert len(stats["by_type"]) >= 2


def test_silence_stale_removes_low_confidence_old_skills(genome):
    genome.record_skill(cell="c1", skill_id="old_weak", procedure="x", confidence=0.3)
    # Manually set last_used to 60 days ago
    sixty_days_ago = datetime.fromtimestamp(time.time() - 60 * 86400, tz=timezone.utc).date().isoformat()
    conn = sqlite3.connect(genome._db_path)
    conn.execute("UPDATE genome SET last_used = ? WHERE id = 'old_weak'", (sixty_days_ago,))
    conn.commit()
    conn.close()

    n = genome.silence_stale_skills(cell="c1", unused_days=30)
    assert n == 1
    active = genome.get_active(cell="c1")
    assert len(active) == 0


def test_daughter_cell_inherits_with_decay(genome):
    """Full differentiation flow: mother records, daughter inherits with decay."""
    genome.record_skill(
        cell="akta_archive", skill_id="chunking_v1",
        procedure="Split text into 10000-char overlapping chunks.",
        confidence=0.95, scope="Project",
    )

    inherited = genome.inherit_genome(parent_cell="akta_archive", min_confidence=0.7)
    assert len(inherited) == 1

    # Daughter stores with 10% decay
    for skill in inherited:
        genome.record_skill(
            cell="sertifikat_parser",
            skill_id=f"inherited_{skill['id']}",
            procedure=skill["procedure"],
            confidence=skill["confidence"] * 0.9,
            inherited_from=skill["id"],
        )

    daughter_skills = genome.get_active(cell="sertifikat_parser")
    assert len(daughter_skills) == 1
    assert daughter_skills[0]["confidence"] == pytest.approx(0.95 * 0.9, abs=0.01)
    assert daughter_skills[0]["inherited_from"] == "chunking_v1"


# ─── Issue 1: Thread Safety ────────────────────────────────────


def test_concurrent_writes_10_threads(tmp_path):
    """10 threads writing concurrently must not lose data or raise errors."""
    db = str(tmp_path / "concurrent.db")
    g = Genome(db_path=db)
    errors: list[Exception] = []

    def writer(thread_id: int) -> None:
        try:
            for i in range(10):
                g.record_skill(
                    cell=f"cell_{thread_id}",
                    skill_id=f"skill_{thread_id}_{i}",
                    procedure=f"Thread {thread_id} procedure {i}",
                    confidence=0.5 + (i * 0.04),
                )
        except Exception as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(writer, tid) for tid in range(10)]
        for f in as_completed(futures):
            f.result()  # re-raise

    assert errors == [], f"Thread errors: {errors}"
    # 10 threads × 10 skills = 100 total
    stats = g.stats()
    assert stats["total"] == 100


def test_concurrent_read_write(tmp_path):
    """Reads while writes are in-flight should never raise."""
    db = str(tmp_path / "rw.db")
    g = Genome(db_path=db)
    g.record_skill(cell="c", skill_id="seed", procedure="base")
    errors: list[Exception] = []

    def reader() -> None:
        try:
            for _ in range(50):
                g.get_active(cell="c")
                g.stats()
        except Exception as exc:
            errors.append(exc)

    def writer() -> None:
        try:
            for i in range(50):
                g.record_skill(cell="c", skill_id=f"w_{i}", procedure=f"p{i}")
        except Exception as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = []
        for _ in range(5):
            futures.append(pool.submit(reader))
            futures.append(pool.submit(writer))
        for f in as_completed(futures):
            f.result()

    assert errors == []


# ─── Issue 2: FTS Triggers (UPDATE / DELETE) ───────────────────


def test_fts_finds_updated_content(genome):
    """After upsert, FTS should find the new procedure, not the old one."""
    genome.record_skill(
        cell="c1", skill_id="evolving",
        procedure="Parse documents using regex",
        confidence=0.8,
    )
    assert len(genome.search("regex")) >= 1

    # Upsert with new procedure
    genome.record_skill(
        cell="c1", skill_id="evolving",
        procedure="Parse documents using tree-sitter AST",
        confidence=0.7,
    )
    # Old term gone from FTS
    assert len(genome.search("regex")) == 0
    # New term found
    results = genome.search("tree")
    assert len(results) == 1
    assert results[0]["id"] == "evolving"


def test_fts_removes_deleted_rows(tmp_path):
    """After DELETE, FTS should not return the deleted row."""
    db = str(tmp_path / "fts_del.db")
    g = Genome(db_path=db)
    g.record_skill(cell="c1", skill_id="doomed", procedure="ephemeral technique")
    assert len(g.search("ephemeral")) == 1

    # Direct DELETE (not exposed as API, but tests trigger integrity)
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM genome WHERE id = 'doomed'")
    conn.commit()
    conn.close()

    assert len(g.search("ephemeral")) == 0
