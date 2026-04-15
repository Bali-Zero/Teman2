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


# ─── Issue 4: apply_inherited_genome ──────────────────────────


def test_apply_inherited_genome(genome):
    """apply_inherited_genome should insert inherited skills into the daughter cell."""
    # Parent has 2 Project skills and 1 Personal scar
    genome.record_skill(
        cell="parent", skill_id="skill_a",
        procedure="technique A", confidence=0.95, scope="Project",
    )
    genome.record_skill(
        cell="parent", skill_id="skill_b",
        procedure="technique B", confidence=0.80, scope="Project",
    )
    genome.record_scar(
        cell="parent", scar_id="scar_x", procedure="avoid this",
    )

    applied = genome.apply_inherited_genome(
        parent_cell="parent",
        daughter_cell="daughter",
        decay=0.9,
        min_confidence=0.7,
    )

    # Only 2 Project skills with confidence >= 0.7
    assert len(applied) == 2

    daughter_skills = genome.get_active(cell="daughter")
    assert len(daughter_skills) == 2

    ids = {s["id"] for s in daughter_skills}
    assert ids == {"inherited_skill_a", "inherited_skill_b"}

    for s in daughter_skills:
        assert s["inherited_from"] in ("skill_a", "skill_b")
        # Confidence should be original * 0.9
        original = 0.95 if s["inherited_from"] == "skill_a" else 0.80
        assert s["confidence"] == pytest.approx(original * 0.9, abs=0.01)


def test_apply_inherited_genome_empty(genome):
    """If parent has no eligible skills, daughter gets nothing."""
    applied = genome.apply_inherited_genome(
        parent_cell="ghost", daughter_cell="orphan",
    )
    assert applied == []
    assert genome.get_active(cell="orphan") == []


# ─── Issue 5: Compaction (vacuum, compact, db_file_size) ──────


def test_vacuum_removes_old_silenced(tmp_path):
    """vacuum() should permanently delete skills silenced > N days ago."""
    db = str(tmp_path / "vacuum.db")
    g = Genome(db_path=db)
    g.record_skill(cell="c1", skill_id="old_one", procedure="old", confidence=0.3)
    g.record_skill(cell="c1", skill_id="fresh_one", procedure="fresh", confidence=0.9)

    # Silence old_one and backdate its valid_to to 100 days ago
    g.silence_skill("old_one")
    hundred_days_ago = datetime.fromtimestamp(
        time.time() - 100 * 86400, tz=timezone.utc
    ).date().isoformat()
    conn = sqlite3.connect(db)
    conn.execute("UPDATE genome SET valid_to = ? WHERE id = 'old_one'", (hundred_days_ago,))
    conn.commit()
    conn.close()

    assert g.stats()["total"] == 2

    removed = g.vacuum(days_silenced=90)
    assert removed == 1
    assert g.stats()["total"] == 1
    # The fresh one is untouched
    active = g.get_active(cell="c1")
    assert len(active) == 1
    assert active[0]["id"] == "fresh_one"


def test_vacuum_keeps_recently_silenced(genome):
    """Skills silenced within the window should NOT be removed."""
    genome.record_skill(cell="c1", skill_id="recent", procedure="x")
    genome.silence_skill("recent")
    removed = genome.vacuum(days_silenced=90)
    assert removed == 0  # silenced today, not 90 days ago


def test_compact_returns_bytes_freed(tmp_path):
    """compact() should run VACUUM and not crash. May free 0 bytes on small DB."""
    db = str(tmp_path / "compact.db")
    g = Genome(db_path=db)
    for i in range(50):
        g.record_skill(cell="c1", skill_id=f"s_{i}", procedure=f"p{i}" * 100)
    size_before = g.stats()["db_file_size"]
    assert size_before > 0

    # Delete many rows, then compact
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM genome WHERE id LIKE 's_%'")
    conn.commit()
    conn.close()

    freed = g.compact()
    assert isinstance(freed, int)
    assert freed >= 0
    # After compacting deleted rows, DB should be smaller
    size_after = g.stats()["db_file_size"]
    assert size_after <= size_before


def test_stats_includes_db_file_size(genome):
    genome.record_skill(cell="c1", skill_id="s1", procedure="a")
    stats = genome.stats()
    assert "db_file_size" in stats
    assert stats["db_file_size"] > 0


# ─── Bonus: export / import ───────────────────────────────────


def test_export_import_roundtrip(tmp_path):
    """Export from one Genome, import into another — full roundtrip."""
    db_src = str(tmp_path / "source.db")
    db_dst = str(tmp_path / "dest.db")
    src = Genome(db_path=db_src)
    dst = Genome(db_path=db_dst)

    src.record_skill(cell="c1", skill_id="s1", procedure="proc A", confidence=0.9)
    src.record_skill(cell="c1", skill_id="s2", procedure="proc B", confidence=0.7)
    src.record_scar(cell="c1", scar_id="scar1", procedure="avoid this")

    exported = src.export_genome(cell="c1")
    assert len(exported) == 3

    counts = dst.import_genome(exported)
    assert counts["inserted"] == 3
    assert counts["updated"] == 0

    # Re-import is safe (upsert)
    counts2 = dst.import_genome(exported)
    assert counts2["updated"] == 3
    assert counts2["inserted"] == 0

    # Verify data integrity
    dst_skills = dst.get_active(cell="c1")
    assert len(dst_skills) == 3


def test_import_with_target_cell_override(tmp_path):
    """import_genome with target_cell overrides cell_origin."""
    db_src = str(tmp_path / "src.db")
    db_dst = str(tmp_path / "dst.db")
    src = Genome(db_path=db_src)
    dst = Genome(db_path=db_dst)

    src.record_skill(cell="original_cell", skill_id="s1", procedure="p1", confidence=0.8)
    exported = src.export_genome()

    dst.import_genome(exported, target_cell="new_cell")
    skills = dst.get_active(cell="new_cell")
    assert len(skills) == 1
    assert skills[0]["cell_origin"] == "new_cell"


# ─── Sprint 5.2: Trajectory recording (Experience Library) ─────


def test_record_trajectory_success(genome):
    action = genome.record_trajectory(
        cell="curator_war_room",
        trajectory_id="run_2026_04_15_abc",
        outcome="success",
        procedure="Selected photo X, caption Y, published to IG carousel.",
        tokens=1420,
        duration_ms=8750,
        tags=["ig", "carousel", "morning"],
        confidence=0.8,
    )
    assert action == "inserted"

    results = genome.get_active(cell="curator_war_room", entry_type="trajectory")
    assert len(results) == 1
    row = results[0]
    assert row["id"] == "run_2026_04_15_abc"
    assert row["type"] == "trajectory"
    assert row["outcome"] == "success"
    assert row["tokens"] == 1420
    assert row["duration_ms"] == 8750


def test_record_trajectory_failure_is_personal_scope(genome):
    """Failure trajectories should be Personal scope (scar-like), not inherited."""
    genome.record_trajectory(
        cell="curator_war_room",
        trajectory_id="run_failed_1",
        outcome="failure",
        procedure="Tried compose without checking DLP flags — blocked on publish.",
    )
    rows = genome.get_active(cell="curator_war_room", entry_type="trajectory")
    assert rows[0]["scope"] == "Personal"


def test_record_trajectory_success_is_project_scope(genome):
    """Success trajectories default to Project scope — but are still not inherited (type filter)."""
    genome.record_trajectory(
        cell="curator_war_room",
        trajectory_id="run_good_1",
        outcome="success",
        procedure="Published asset cleanly.",
    )
    rows = genome.get_active(cell="curator_war_room", entry_type="trajectory")
    assert rows[0]["scope"] == "Project"


def test_record_trajectory_partial_stored_with_lower_confidence(genome):
    genome.record_trajectory(
        cell="c1",
        trajectory_id="run_partial",
        outcome="partial",
        procedure="Published 2 of 3 assets — third timed out on DLP scan.",
        confidence=0.6,
    )
    rows = genome.get_active(cell="c1", entry_type="trajectory")
    assert rows[0]["outcome"] == "partial"
    assert rows[0]["confidence"] == 0.6


def test_record_trajectory_rejects_invalid_outcome(genome):
    with pytest.raises(ValueError, match="outcome"):
        genome.record_trajectory(
            cell="c1",
            trajectory_id="bad",
            outcome="maybe",
            procedure="x",
        )


def test_record_trajectory_upsert_keeps_max_confidence(genome):
    """Re-recording the same trajectory_id updates procedure, keeps max confidence."""
    genome.record_trajectory(
        cell="c1", trajectory_id="t1", outcome="partial",
        procedure="first attempt", confidence=0.7,
    )
    action = genome.record_trajectory(
        cell="c1", trajectory_id="t1", outcome="success",
        procedure="revised attempt", confidence=0.5,
    )
    assert action == "updated"
    rows = genome.get_active(cell="c1", entry_type="trajectory")
    assert rows[0]["procedure"] == "revised attempt"
    assert rows[0]["confidence"] == 0.7  # max preserved
    assert rows[0]["outcome"] == "success"  # outcome updated


def test_search_trajectories_by_fts(genome):
    genome.record_trajectory(
        cell="c1", trajectory_id="t1", outcome="success",
        procedure="DLP scan detected PII in draft caption and blocked publish.",
    )
    genome.record_trajectory(
        cell="c1", trajectory_id="t2", outcome="success",
        procedure="Selected a morning photo from GARUDA photos folder.",
    )
    results = genome.search_trajectories("DLP")
    assert len(results) == 1
    assert results[0]["id"] == "t1"


def test_search_trajectories_filter_by_outcome(genome):
    genome.record_trajectory(cell="c1", trajectory_id="ok", outcome="success", procedure="published cleanly")
    genome.record_trajectory(cell="c1", trajectory_id="ko", outcome="failure", procedure="published cleanly")
    failures = genome.search_trajectories("published", outcome="failure")
    assert len(failures) == 1
    assert failures[0]["id"] == "ko"


def test_search_trajectories_filter_by_cell(genome):
    genome.record_trajectory(cell="cell_a", trajectory_id="a1", outcome="success", procedure="common prose")
    genome.record_trajectory(cell="cell_b", trajectory_id="b1", outcome="success", procedure="common prose")
    only_a = genome.search_trajectories("common", cell="cell_a")
    assert len(only_a) == 1
    assert only_a[0]["cell_origin"] == "cell_a"


def test_trajectory_not_inherited_at_fork(genome):
    """inherit_genome should NOT include trajectories — only skills/patterns are germline."""
    genome.record_trajectory(
        cell="parent_cell", trajectory_id="t1", outcome="success",
        procedure="episode detail", confidence=0.95,
    )
    genome.record_skill(
        cell="parent_cell", skill_id="s1",
        procedure="distilled technique", confidence=0.95, scope="Project",
    )
    inherited = genome.inherit_genome(parent_cell="parent_cell", min_confidence=0.7)
    ids = [s["id"] for s in inherited]
    assert "s1" in ids
    assert "t1" not in ids


def test_trajectory_stats(genome):
    genome.record_trajectory(cell="c1", trajectory_id="ok_1", outcome="success", procedure="p")
    genome.record_trajectory(cell="c1", trajectory_id="ok_2", outcome="success", procedure="p")
    genome.record_trajectory(cell="c1", trajectory_id="ko_1", outcome="failure", procedure="p")
    genome.record_trajectory(cell="c1", trajectory_id="part_1", outcome="partial", procedure="p")

    stats = genome.trajectory_stats(cell="c1")
    assert stats["total"] == 4
    assert stats["by_outcome"]["success"] == 2
    assert stats["by_outcome"]["failure"] == 1
    assert stats["by_outcome"]["partial"] == 1


def test_trajectory_tags_roundtrip(genome):
    genome.record_trajectory(
        cell="c1", trajectory_id="t1", outcome="success",
        procedure="x", tags=["ig", "video", "evening"],
    )
    rows = genome.get_active(cell="c1", entry_type="trajectory")
    # tags stored as JSON string in DB; search via dedicated API or tag filter
    assert "ig" in rows[0]["tags"]
    assert "video" in rows[0]["tags"]


def test_search_trajectories_filter_by_tag(genome):
    genome.record_trajectory(cell="c1", trajectory_id="t1", outcome="success",
                              procedure="prose", tags=["ig"])
    genome.record_trajectory(cell="c1", trajectory_id="t2", outcome="success",
                              procedure="prose", tags=["wa"])
    results = genome.search_trajectories("prose", tag="ig")
    assert len(results) == 1
    assert results[0]["id"] == "t1"


def test_search_trajectories_tag_exact_match_not_substring(genome):
    """Bug caught by DeepSeek review 2026-04-15:
    tag='ig' must NOT match a trajectory tagged ['ig_video'] or ['big'].
    The LIKE-on-JSON implementation produced false positives."""
    genome.record_trajectory(cell="c1", trajectory_id="exact",
                              outcome="success", procedure="p", tags=["ig"])
    genome.record_trajectory(cell="c1", trajectory_id="longer",
                              outcome="success", procedure="p", tags=["ig_video"])
    genome.record_trajectory(cell="c1", trajectory_id="prefixed",
                              outcome="success", procedure="p", tags=["big"])

    results = genome.search_trajectories("p", tag="ig")
    ids = {r["id"] for r in results}
    assert ids == {"exact"}, f"expected only 'exact', got {ids}"


def test_search_trajectories_tag_special_chars(genome):
    """Tag containing double quote or backslash must not blow up the query
    or create false positives. Note: JSON-serialised tags with embedded
    quotes are stored escaped, and our LIKE pattern will miss them — this
    is accepted silent failure; callers must pass ASCII tags. The service
    layer enforces this via Pydantic validator (see models.py:Tag)."""
    genome.record_trajectory(cell="c1", trajectory_id="t1",
                              outcome="success", procedure="p", tags=['normal'])
    # Must not raise. Must not match 'normal'.
    results = genome.search_trajectories("p", tag='weird"quote')
    assert results == []


def test_get_trajectory_returns_row(genome):
    genome.record_trajectory(
        cell="c1", trajectory_id="lookup_me", outcome="success",
        procedure="fetch by id", tokens=999,
    )
    row = genome.get_trajectory("lookup_me")
    assert row is not None
    assert row["id"] == "lookup_me"
    assert row["tokens"] == 999


def test_get_trajectory_none_for_missing_id(genome):
    assert genome.get_trajectory("nope") is None


def test_get_trajectory_none_for_non_trajectory_type(genome):
    """A skill with the same id must NOT be returned by get_trajectory."""
    genome.record_skill(cell="c1", skill_id="dup", procedure="skill body")
    assert genome.get_trajectory("dup") is None
