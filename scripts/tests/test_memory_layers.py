"""Unit tests for scripts/memory/mos_recall_sessionstart.py — the SessionStart
recall hook (Layer 2, wired via scripts/hooks/memory_recall_sessionstart.sh).

Fixtures live entirely in tmp_path; nothing under ~/.claude is touched.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

SCRIPTS_MEMORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
sys.path.insert(0, SCRIPTS_MEMORY)

import mos_recall_sessionstart as mos  # noqa: E402


FRONT = """---
name: {name}
description: {desc}
metadata:
  type: {typ}
---

Body text about {topic} with several relevant words repeated: {topic} {topic}.
"""


def _write_memory_file(memdir, filename, name, desc, typ, topic):
    (memdir / filename).write_text(
        FRONT.format(name=name, desc=desc, typ=typ, topic=topic), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Slug derivation (resolve_memdir)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("project_dir, slug", [
    ("/Users/balizero/nuzantara", "-Users-balizero-nuzantara"),
    ("/Users/nuzantara/Desktop/nuzantara", "-Users-nuzantara-Desktop-nuzantara"),
])
def test_slug_derivation_matches_home_claude_projects_shape(tmp_path, project_dir, slug):
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    memdir = mos.resolve_memdir(cwd=project_dir, home=str(fake_home))

    assert memdir == str(fake_home / ".claude" / "projects" / slug / "memory")


# ---------------------------------------------------------------------------
# Quiet when memdir missing
# ---------------------------------------------------------------------------

def test_recall_quiet_when_memdir_missing(tmp_path):
    missing = tmp_path / "does_not_exist" / "memory"
    assert not missing.exists()

    # main()'s own directory-existence check is exercised via the CLI path,
    # but the underlying recall() must also behave sanely against an absent
    # dir rather than raising.
    results, stats = mos.recall(str(missing), str(tmp_path / "cache.json"), query="anything")
    assert results == []
    assert stats["file_count"] == 0


def test_main_exits_quietly_when_memdir_not_wired(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        mos, "resolve_memdir",
        lambda cwd=None, home=None: str(tmp_path / "not_wired" / "memory"),
    )
    monkeypatch.setattr(sys, "argv", ["mos_recall_sessionstart.py"])

    rc = mos.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == ""


# ---------------------------------------------------------------------------
# Output cap (1,500 bytes)
# ---------------------------------------------------------------------------

def test_format_output_stays_under_cap_with_many_results(tmp_path):
    memdir = tmp_path / "memdir_many"
    memdir.mkdir()
    for i in range(40):
        _write_memory_file(
            memdir, f"discovery_widget_{i}_2026_09_01.md",
            f"discovery-widget-{i}",
            "a" * 200 + f" widget finding number {i} about manufacturing",
            "discovery", "widget",
        )

    results, _stats = mos.recall(str(memdir), str(tmp_path / "cache_many.json"),
                                  query="widget manufacturing", topk=40, threshold=0.0)
    out = mos.format_output(results)

    assert len(out.encode("utf-8")) <= mos.OUTPUT_CAP_BYTES
    assert mos.HEADER_LINE in out


def test_format_output_empty_when_no_results():
    assert mos.format_output([]) == ""


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, needle, placeholder", [
    ("contact the client at mario.rossi@example.com for details", "mario.rossi@example.com", "<email>"),
    ("call the client on +62 812 345 6789 tomorrow", "812 345 6789", "<num>"),
    ("reference number 1234567890123 on file", "1234567890123", "<num>"),
    ("copy of passport A1234567 attached", "A1234567", "<id>"),
])
def test_redact_pii_shapes(text, needle, placeholder):
    out = mos.redact(text)
    assert placeholder in out
    assert needle not in out


def test_redact_leaves_clean_text_untouched():
    clean = "the migration runner reads schema_migrations and applies pending DDL"
    assert mos.redact(clean) == clean


def test_format_output_redacts_description(tmp_path):
    memdir = tmp_path / "memdir_pii"
    memdir.mkdir()
    _write_memory_file(
        memdir, "discovery_client_email_2026_09_01.md",
        "discovery-client-email",
        "widget client contact mario.rossi@example.com about widget order",
        "discovery", "widget",
    )
    results, _stats = mos.recall(str(memdir), str(tmp_path / "cache_pii.json"),
                                  query="widget", threshold=0.0)
    out = mos.format_output(results)
    assert "mario.rossi@example.com" not in out
    assert "<email>" in out


# ---------------------------------------------------------------------------
# MEMORY.md oversize warning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("size, expect_warning", [(100, False), (mos.MEMORY_MD_WARN_BYTES + 500, True)])
def test_memory_md_warning_gated_on_2560_bytes(tmp_path, size, expect_warning):
    memdir = tmp_path / f"memdir_index_{size}"
    memdir.mkdir()
    (memdir / "MEMORY.md").write_text("x" * size, encoding="utf-8")

    warning = mos.memory_md_warning(str(memdir))
    if expect_warning:
        assert warning is not None and str(size) in warning and "MEMORY_INDEX.md" in warning
    else:
        assert warning is None


def test_format_output_includes_warning_line(tmp_path):
    warning = mos.MEMORY_MD_WARN_TEMPLATE.format(bytes=3000)
    out = mos.format_output([], warning=warning)
    assert out == warning


# ---------------------------------------------------------------------------
# Recency / importance monotonicity (kept from prototype)
# ---------------------------------------------------------------------------

def test_recall_scoring_monotonic_in_recency(tmp_path):
    memdir = tmp_path / "memdir_recency"
    memdir.mkdir()
    today = time.strftime("%Y_%m_%d")
    old_date = "2020_01_01"
    _write_memory_file(memdir, f"discovery_recent_topic_{today}.md",
                        "discovery-recent", "recent finding about widgets", "discovery", "widgets")
    _write_memory_file(memdir, f"discovery_old_topic_{old_date}.md",
                        "discovery-old", "old finding about widgets", "discovery", "widgets")

    index, _stats = mos.build_or_refresh_index(str(memdir), str(tmp_path / "cache.json"))
    now_ts = time.time()
    recent_entry = next(e for p, e in index.items() if "recent_topic" in p)
    old_entry = next(e for p, e in index.items() if "old_topic" in p)

    assert mos.recency_score(recent_entry, now_ts) > mos.recency_score(old_entry, now_ts)


def test_recall_scoring_monotonic_in_importance(tmp_path):
    memdir = tmp_path / "memdir_importance"
    memdir.mkdir()
    date = "2026_09_01"
    _write_memory_file(memdir, f"decision_x_{date}.md", "decision-x", "a decision", "project", "topic")
    _write_memory_file(memdir, f"fact_x_{date}.md", "fact-x", "a fact", "fact", "topic")

    index, _stats = mos.build_or_refresh_index(str(memdir), str(tmp_path / "cache2.json"))
    decision_entry = next(e for p, e in index.items() if p.split(os.sep)[-1].startswith("decision_"))
    fact_entry = next(e for p, e in index.items() if p.split(os.sep)[-1].startswith("fact_"))

    # decision (filename-prefix taxonomy) = 1.0 importance, fact = 0.6
    assert mos.importance_score(decision_entry) > mos.importance_score(fact_entry)


def test_recall_quiet_when_nothing_pertinent(tmp_path):
    memdir = tmp_path / "memdir_quiet"
    memdir.mkdir()
    _write_memory_file(memdir, "discovery_foo_2026_09_01.md",
                        "discovery-foo", "a discovery about databases", "discovery", "database")

    results, stats = mos.recall(
        str(memdir), str(tmp_path / "cache3.json"),
        query="zzqvortex wibblefrump squonkalorian blibberflax",
    )
    assert results == []
    assert stats["best_relevance"] == 0.0
    assert mos.format_output(results) == ""


def test_recall_finds_relevant_result(tmp_path):
    memdir = tmp_path / "memdir_relevant"
    memdir.mkdir()
    _write_memory_file(memdir, "discovery_widgets_thing_2026_09_01.md",
                        "discovery-widgets", "a discovery about widget manufacturing", "discovery", "widget")
    _write_memory_file(memdir, "fact_unrelated_2026_09_01.md",
                        "fact-unrelated", "a fact about something else entirely", "fact", "gadget")

    results, stats = mos.recall(str(memdir), str(tmp_path / "cache4.json"), query="widget manufacturing")
    assert results
    assert results[0]["filename"] == "discovery_widgets_thing_2026_09_01.md"
