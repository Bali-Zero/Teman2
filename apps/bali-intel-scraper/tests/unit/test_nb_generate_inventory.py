"""Unit tests for nb_generate_inventory.py — pure-function coverage only.

No live nlm calls. Tests cover:
  - classify_notebook:  healthy/empty/near_cap thresholds, field passthrough,
                        missing source_count edge case.
  - build_inventory:    JSON shape, all top-level keys, nb_intel structure,
                        near_cap flag propagation, classify_notebook wiring.

Uses the importlib-load pattern from test_nb_dedup_challenge_sweep.py so the
script is imported by file path without needing it on sys.path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    # parents[2] = apps/bali-intel-scraper/
    # parents[3] = apps/
    # parents[4] = repo root (where scripts/ lives)
    Path(__file__).resolve().parents[4] / "scripts" / "nb_generate_inventory.py"
)
_spec = importlib.util.spec_from_file_location("nb_generate_inventory", SCRIPT)
nbi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nbi)


# ──────────────────────────────────────────────────────────────────────────────
# classify_notebook
# ──────────────────────────────────────────────────────────────────────────────

def test_classify_healthy_preserves_fields():
    nb = {"id": "abc", "title": "Test NB", "source_count": 10, "updated_at": "2026-01-01T00:00:00Z"}
    out = nbi.classify_notebook(nb)
    assert out["health"] == "healthy"
    assert out["near_cap"] is False
    # Original fields are preserved
    assert out["id"] == "abc"
    assert out["title"] == "Test NB"
    assert out["source_count"] == 10
    assert out["updated_at"] == "2026-01-01T00:00:00Z"


def test_classify_empty_when_zero_sources():
    nb = {"id": "abc", "title": "Empty NB", "source_count": 0, "updated_at": "2026-01-01T00:00:00Z"}
    out = nbi.classify_notebook(nb)
    assert out["health"] == "empty"
    assert out["near_cap"] is False


def test_classify_near_cap_at_threshold():
    """source_count == threshold is near_cap."""
    nb = {"id": "x", "title": "Big NB", "source_count": 480, "updated_at": "2026-01-01T00:00:00Z"}
    out = nbi.classify_notebook(nb, near_cap_threshold=480)
    assert out["health"] == "healthy"
    assert out["near_cap"] is True


def test_classify_near_cap_one_below():
    nb = {"id": "x", "title": "Almost Big", "source_count": 479, "updated_at": "2026-01-01T00:00:00Z"}
    out = nbi.classify_notebook(nb, near_cap_threshold=480)
    assert out["near_cap"] is False


def test_classify_near_cap_above_threshold():
    nb = {"id": "x", "title": "At cap", "source_count": 500, "updated_at": "2026-01-01T00:00:00Z"}
    out = nbi.classify_notebook(nb, near_cap_threshold=480)
    assert out["near_cap"] is True


def test_classify_missing_source_count_is_empty():
    """Missing source_count is treated as 0 → health='empty'."""
    nb = {"id": "x", "title": "No count field"}
    out = nbi.classify_notebook(nb)
    assert out["health"] == "empty"
    assert out["near_cap"] is False


def test_classify_none_source_count_is_empty():
    """Explicit None source_count is treated as 0 → health='empty'."""
    nb = {"id": "x", "title": "Null count", "source_count": None}
    out = nbi.classify_notebook(nb)
    assert out["health"] == "empty"
    assert out["near_cap"] is False


# ──────────────────────────────────────────────────────────────────────────────
# build_inventory
# ──────────────────────────────────────────────────────────────────────────────

FAKE_NOTEBOOKS = [
    {"id": "nb1", "title": "NB One", "source_count": 50, "updated_at": "2026-01-01T00:00:00Z"},
    {"id": "nb2", "title": "NB Two", "source_count": 0, "updated_at": "2026-01-02T00:00:00Z"},
]

FAKE_NB_INTEL_SOURCES: dict[str, list[dict]] = {
    "immigration": [
        {"id": "s1", "title": "Article One", "type": "web_page", "url": "https://example.com/1"},
        {"id": "s2", "title": "Article Two", "type": "web_page", "url": "https://example.com/2"},
    ],
    "tax": [],
    "press": [{"id": "s3", "title": "Press Item", "type": "generated_text", "url": None}],
    "regulation": [],
    "ai_research": [],
}


def test_build_inventory_top_level_shape():
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    assert "generated_at" in inv
    assert "notebook_count" in inv
    assert "notebooks" in inv
    assert "nb_intel" in inv


def test_build_inventory_notebook_count():
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    assert inv["notebook_count"] == 2
    assert len(inv["notebooks"]) == 2


def test_build_inventory_nb_intel_keys():
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    assert set(inv["nb_intel"].keys()) == {"immigration", "tax", "press", "regulation", "ai_research"}


def test_build_inventory_nb_intel_has_uuid():
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    imm = inv["nb_intel"]["immigration"]
    assert "uuid" in imm
    assert imm["uuid"] == nbi.NB_INTEL["immigration"]


def test_build_inventory_nb_intel_source_count_and_titles():
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    imm = inv["nb_intel"]["immigration"]
    assert imm["source_count"] == 2
    assert "Article One" in imm["titles"]
    assert "Article Two" in imm["titles"]


def test_build_inventory_nb_intel_empty_section():
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    tax = inv["nb_intel"]["tax"]
    assert tax["source_count"] == 0
    assert tax["titles"] == []
    assert tax["near_cap"] is False


def test_build_inventory_nb_intel_near_cap_propagates():
    """A section with source_count >= threshold must have near_cap=True."""
    sources_at_cap = [
        {"id": f"s{i}", "title": f"Article {i}", "type": "web_page", "url": None}
        for i in range(480)
    ]
    sources = {**FAKE_NB_INTEL_SOURCES, "press": sources_at_cap}
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, sources, near_cap_threshold=480)
    assert inv["nb_intel"]["press"]["near_cap"] is True
    assert inv["nb_intel"]["immigration"]["near_cap"] is False


def test_build_inventory_classifies_notebooks():
    """build_inventory must wire through classify_notebook for health field."""
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    nb_by_id = {nb["id"]: nb for nb in inv["notebooks"]}
    assert nb_by_id["nb1"]["health"] == "healthy"
    assert nb_by_id["nb2"]["health"] == "empty"


def test_build_inventory_empty_notebooks_list():
    inv = nbi.build_inventory([], FAKE_NB_INTEL_SOURCES)
    assert inv["notebook_count"] == 0
    assert inv["notebooks"] == []


def test_build_inventory_generated_at_is_iso8601():
    """generated_at must be a parseable ISO-8601 UTC string."""
    from datetime import datetime, timezone
    inv = nbi.build_inventory(FAKE_NOTEBOOKS, FAKE_NB_INTEL_SOURCES)
    # Must not raise
    dt = datetime.fromisoformat(inv["generated_at"].replace("Z", "+00:00"))
    assert dt.tzinfo is not None
