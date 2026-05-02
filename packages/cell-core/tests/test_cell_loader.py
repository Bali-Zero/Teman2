"""Tests for cell_core.cell_loader — Sprint 1.

Covers:
- Round-trip YAML load → dict shape feeds AdmissionTest cleanly
- intel_scraper_cell.yaml passes the 7 Leggi admission test
- Missing 'name' field in a cell file raises ValueError
- Duplicate cell names across files raise ValueError
- Empty cells dir returns {} (not crash)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cell_core.admission_test import AdmissionTest
from cell_core.cell_loader import load_all_cells, load_cell_definition


REPO_CELLS_DIR = Path(__file__).resolve().parents[1] / "cells"


def test_intel_scraper_cell_yaml_loads():
    """The shipped intel_scraper_cell.yaml parses to a dict."""
    path = REPO_CELLS_DIR / "intel_scraper_cell.yaml"
    cell = load_cell_definition(path)
    assert isinstance(cell, dict)
    assert cell["name"] == "intel-scraper-cell"
    assert cell["level"] == "L1"
    assert cell["class"] == "light"


def test_intel_scraper_cell_passes_admission():
    """Sprint 1 deliverable: the cell definition must PASS all 7 Leggi."""
    cell = load_cell_definition(REPO_CELLS_DIR / "intel_scraper_cell.yaml")
    result = AdmissionTest().run_all(cell)
    assert result.passed is True, result.summary()


def test_load_all_cells_returns_name_keyed_dict(tmp_path):
    """load_all_cells walks *.yaml, returns dict keyed by 'name'."""
    cell_a = tmp_path / "alpha.yaml"
    cell_a.write_text(textwrap.dedent("""\
        name: alpha-cell
        level: L1
        exposes_gui: false
        publishes_via: pg_notify
        fallback_modes: [llm_provider_down]
        kill_switch: true
        metrics: [a, b, c]
    """), encoding="utf-8")
    cell_b = tmp_path / "beta.yaml"
    cell_b.write_text(textwrap.dedent("""\
        name: beta-cell
        level: L1
        exposes_gui: false
        publishes_via: pg_notify
        fallback_modes: [llm_provider_down]
        kill_switch: true
        metrics: [x, y, z]
    """), encoding="utf-8")

    cells = load_all_cells(tmp_path)
    assert set(cells.keys()) == {"alpha-cell", "beta-cell"}
    assert cells["alpha-cell"]["_source_path"].endswith("alpha.yaml")


def test_load_cell_missing_name_raises(tmp_path):
    """A cell file without `name` is fail-loud at load time."""
    bad = tmp_path / "no_name.yaml"
    bad.write_text("level: L1\nexposes_gui: false\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing a 'name' field"):
        load_all_cells(tmp_path)


def test_load_cell_duplicate_name_raises(tmp_path):
    """Two cell files with the same `name:` collide loudly."""
    dup = textwrap.dedent("""\
        name: dup-cell
        level: L1
        exposes_gui: false
        publishes_via: pg_notify
        fallback_modes: [llm_provider_down]
        kill_switch: true
        metrics: [a, b, c]
    """)
    (tmp_path / "first.yaml").write_text(dup, encoding="utf-8")
    (tmp_path / "second.yaml").write_text(dup, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate cell name"):
        load_all_cells(tmp_path)


def test_load_cell_nonexistent_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_cell_definition(tmp_path / "nope.yaml")


def test_load_cell_root_must_be_mapping(tmp_path):
    """A YAML file with a list at the root rejects with ValueError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("- name: foo\n- name: bar\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_cell_definition(bad)


def test_load_all_cells_missing_dir_returns_empty(tmp_path):
    """load_all_cells on a non-existent dir returns {} (not crash)."""
    cells = load_all_cells(tmp_path / "does_not_exist")
    assert cells == {}
