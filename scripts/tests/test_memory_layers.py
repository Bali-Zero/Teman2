"""Unit tests for scripts/memory/mos_recall_sessionstart.py (SessionStart
recall hook). Fixtures live entirely in tmp_path; nothing under ~/.claude
is touched.
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

def _write(memdir, filename, name, desc, typ, topic):
    (memdir / filename).write_text(FRONT.format(name=name, desc=desc, typ=typ, topic=topic), encoding="utf-8")

@pytest.mark.parametrize("project_dir, slug", [
    ("/Users/balizero/nuzantara", "-Users-balizero-nuzantara"),
    ("/Users/nuzantara/Desktop/nuzantara", "-Users-nuzantara-Desktop-nuzantara"),
])
def test_slug_derivation_matches_home_claude_projects_shape(tmp_path, project_dir, slug):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    memdir = mos.resolve_memdir(cwd=project_dir, home=str(fake_home))
    assert memdir == str(fake_home / ".claude" / "projects" / slug / "memory")

def test_resolve_memdir_falls_back_to_main_worktree_when_slug_dir_missing(tmp_path, monkeypatch):
    fake_home, main_repo = tmp_path / "home", tmp_path / "nuzantara"
    worktree = main_repo / ".worktrees" / "some-lane"
    (fake_home / ".claude" / "projects" / str(main_repo).replace(os.sep, "-") / "memory").mkdir(parents=True)
    worktree.mkdir(parents=True)
    monkeypatch.setattr(mos, "git_main_worktree", lambda cwd: str(main_repo))
    memdir = mos.resolve_memdir(cwd=str(worktree), home=str(fake_home))
    assert memdir == str(fake_home / ".claude" / "projects" / str(main_repo).replace(os.sep, "-") / "memory")
    # no main-worktree memdir either -> still gives up quietly, never raises
    monkeypatch.setattr(mos, "git_main_worktree", lambda cwd: str(tmp_path / "unwired-main"))
    assert not os.path.isdir(mos.resolve_memdir(cwd=str(worktree), home=str(tmp_path / "other_home")))

def test_main_exits_quietly_when_memdir_not_wired(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mos, "resolve_memdir", lambda cwd=None, home=None: str(tmp_path / "not_wired" / "memory"))
    monkeypatch.setattr(sys, "argv", ["mos_recall_sessionstart.py"])
    rc = mos.main()
    assert rc == 0 and capsys.readouterr().out == ""

def test_format_output_stays_under_cap_with_many_results(tmp_path):
    memdir = tmp_path / "memdir_many"
    memdir.mkdir()
    for i in range(40):
        _write(memdir, f"discovery_widget_{i}_2026_09_01.md", f"discovery-widget-{i}",
               "a" * 200 + f" widget finding number {i} about manufacturing", "discovery", "widget")
    results, _ = mos.recall(str(memdir), str(tmp_path / "cache_many.json"),
                             query="widget manufacturing", topk=40, threshold=0.0)
    out = mos.format_output(results)
    assert len(out.encode("utf-8")) <= mos.OUTPUT_CAP_BYTES and mos.HEADER_LINE in out

@pytest.mark.parametrize("text, needle, placeholder", [
    ("contact the client at mario.rossi@example.com for details", "mario.rossi@example.com", "<email>"),
    ("call the client on +62 812 345 6789 tomorrow", "812 345 6789", "<num>"),
    ("reference number 1234567890123 on file", "1234567890123", "<num>"),
    ("copy of passport A1234567 attached", "A1234567", "<id>"),
])
def test_redact_pii_shapes(text, needle, placeholder):
    out = mos.redact(text)
    assert placeholder in out and needle not in out

@pytest.mark.parametrize("size, expect_warning", [(100, False), (mos.MEMORY_MD_WARN_BYTES + 500, True)])
def test_memory_md_warning_gated_on_2560_bytes(tmp_path, size, expect_warning):
    memdir = tmp_path / f"memdir_index_{size}"
    memdir.mkdir()
    (memdir / "MEMORY.md").write_text("x" * size, encoding="utf-8")
    warning = mos.memory_md_warning(str(memdir))
    ok = (warning is not None and str(size) in warning and "MEMORY_INDEX.md" in warning) if expect_warning else warning is None
    assert ok

def test_recall_scoring_monotonic_in_recency(tmp_path):
    memdir = tmp_path / "memdir_recency"
    memdir.mkdir()
    today, old_date = time.strftime("%Y_%m_%d"), "2020_01_01"
    _write(memdir, f"discovery_recent_topic_{today}.md", "discovery-recent", "recent finding about widgets", "discovery", "widgets")
    _write(memdir, f"discovery_old_topic_{old_date}.md", "discovery-old", "old finding about widgets", "discovery", "widgets")
    index, _ = mos.build_or_refresh_index(str(memdir), str(tmp_path / "cache.json"))
    now_ts = time.time()
    recent_entry = next(e for p, e in index.items() if "recent_topic" in p)
    old_entry = next(e for p, e in index.items() if "old_topic" in p)
    assert mos.recency_score(recent_entry, now_ts) > mos.recency_score(old_entry, now_ts)

def test_recall_scoring_monotonic_in_importance(tmp_path):
    memdir = tmp_path / "memdir_importance"
    memdir.mkdir()
    date = "2026_09_01"
    _write(memdir, f"decision_x_{date}.md", "decision-x", "a decision", "project", "topic")
    _write(memdir, f"fact_x_{date}.md", "fact-x", "a fact", "fact", "topic")
    index, _ = mos.build_or_refresh_index(str(memdir), str(tmp_path / "cache2.json"))
    decision_entry = next(e for p, e in index.items() if p.split(os.sep)[-1].startswith("decision_"))
    fact_entry = next(e for p, e in index.items() if p.split(os.sep)[-1].startswith("fact_"))
    assert mos.importance_score(decision_entry) > mos.importance_score(fact_entry)
