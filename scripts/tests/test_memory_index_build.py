"""Unit tests for scripts/memory/memory_index_build.py — the Layer 3 catalog
generator (MEMORY_INDEX.md). Fixtures live entirely in tmp_path; nothing
under ~/.claude is touched.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

SCRIPTS_MEMORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
sys.path.insert(0, SCRIPTS_MEMORY)

import memory_index_build as index_mod  # noqa: E402


def _write_memory_file(memdir, filename, name, desc, typ, topic):
    (memdir / filename).write_text(
        f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: {typ}\n---\n\n"
        f"Body text about {topic}.\n",
        encoding="utf-8",
    )


def test_catalog_includes_frontmatter_less_file_via_first_heading(tmp_path):
    memdir = tmp_path / "memdir_catalog"
    memdir.mkdir()
    (memdir / "discovery_with_frontmatter_2026_09_01.md").write_text(
        "---\nname: has-fm\ndescription: has frontmatter\nmetadata:\n  type: discovery\n---\n\nbody\n",
        encoding="utf-8",
    )
    (memdir / "no_frontmatter_file.md").write_text(
        "# A Heading Used As Title\n\nSome body text with no frontmatter block at all.\n",
        encoding="utf-8",
    )

    text, meta = index_mod.build_index(str(memdir))

    assert "A Heading Used As Title" in text
    assert "no_frontmatter_file.md" in text
    assert meta["frontmatter_less_count"] == 1


def test_catalog_idempotent(tmp_path):
    memdir = tmp_path / "memdir_idem"
    memdir.mkdir()
    _write_memory_file(memdir, "discovery_x_2026_09_01.md", "x", "desc", "discovery", "topic")

    text1, _m1 = index_mod.build_index(str(memdir))
    text2, _m2 = index_mod.build_index(str(memdir))
    assert text1 == text2


@pytest.mark.parametrize("filename", ["MEMORY_DIGEST.md", "discovery_stale_2026_01_01.md.bak", "discovery_backup_copy.md"])
def test_catalog_excludes_memory_and_backup_files(tmp_path, filename):
    memdir = tmp_path / f"memdir_excl_{filename.replace('.', '_')}"
    memdir.mkdir()
    (memdir / filename).write_text("should be excluded\n", encoding="utf-8")
    (memdir / "discovery_kept_2026_09_01.md").write_text(
        "---\nname: kept\ndescription: kept entry\nmetadata:\n  type: discovery\n---\n\nbody\n",
        encoding="utf-8",
    )

    text, _meta = index_mod.build_index(str(memdir))

    assert filename not in text
    assert "discovery_kept_2026_09_01.md" in text


@pytest.mark.parametrize("desc, needle, placeholder", [
    ("contact the client at mario.rossi@example.com for details", "mario.rossi@example.com", "<email>"),
    ("call the client on +62 812 345 6789 tomorrow", "812 345 6789", "<num>"),
    ("reference number 1234567890123 on file", "1234567890123", "<num>"),
    ("copy of passport A1234567 attached", "A1234567", "<id>"),
    ("KTP number 3171234567890123 on file", "3171234567890123", "<id>"),
])
def test_catalog_redacts_pii_in_descriptions(tmp_path, desc, needle, placeholder):
    memdir = tmp_path / "memdir_pii"
    memdir.mkdir()
    _write_memory_file(memdir, "discovery_pii_2026_09_01.md", "pii-entry", desc, "discovery", "client")

    text, meta = index_mod.build_index(str(memdir))

    assert needle not in text
    assert placeholder in text
    assert meta["pii_offender_count"] == 1


def test_redact_clean_text_has_no_hits():
    clean = "the migration runner reads schema_migrations and applies pending DDL"
    _text, hits = index_mod.redact(clean)
    assert hits == []


def test_is_stale_true_when_catalog_missing(tmp_path):
    memdir = tmp_path / "memdir_stale_missing"
    memdir.mkdir()
    assert index_mod.is_stale(str(memdir), str(memdir / "MEMORY_INDEX.md")) is True


def test_is_stale_true_after_new_memory_file_added(tmp_path):
    memdir = tmp_path / "memdir_stale_new"
    memdir.mkdir()
    _write_memory_file(memdir, "discovery_x_2026_09_01.md", "x", "desc", "discovery", "topic")
    out_path = memdir / "MEMORY_INDEX.md"
    text, _meta = index_mod.build_index(str(memdir))
    out_path.write_text(text, encoding="utf-8")
    assert index_mod.is_stale(str(memdir), str(out_path)) is False

    time.sleep(0.01)
    _write_memory_file(memdir, "discovery_y_2026_09_02.md", "y", "desc2", "discovery", "topic2")
    os.utime(memdir / "discovery_y_2026_09_02.md", (time.time() + 5, time.time() + 5))

    assert index_mod.is_stale(str(memdir), str(out_path)) is True


def test_resolve_memdir_slug_shape(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    memdir = index_mod.resolve_memdir(cwd="/Users/balizero/nuzantara", home=str(fake_home))

    assert memdir == str(fake_home / ".claude" / "projects" / "-Users-balizero-nuzantara" / "memory")
