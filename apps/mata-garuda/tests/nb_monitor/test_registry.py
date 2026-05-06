"""Tests for nb_monitor.registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from mata_garuda.scripts.nb_monitor.registry import (
    NotebookEntry,
    load_registry,
    RegistryLoadError,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_returns_dataclass_list():
    path = FIXTURES / "bootstrap.json"
    entries = load_registry(path)
    assert len(entries) == 2
    assert all(isinstance(e, NotebookEntry) for e in entries)
    assert entries[0].uuid == "1ed02e54-542f-426a-94f8-53c5ffde4b7d"
    assert entries[0].name == "NB-INTEL-Immigration"
    assert entries[0].family == "INTEL"
    assert entries[0].lifecycle_stage == "TAC"
    assert entries[0].active_routing is True
    assert entries[0].first_audited == "2026-05-04"
    assert entries[0].round2_classification == "Curated High Value"


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(RegistryLoadError, match="not found"):
        load_registry(tmp_path / "nonexistent.json")


def test_load_malformed_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(RegistryLoadError, match="invalid JSON"):
        load_registry(bad)


def test_load_missing_required_field_raises(tmp_path):
    bad = tmp_path / "incomplete.json"
    bad.write_text('{"schema_version": 1, "notebooks": [{"uuid": "x"}]}')
    with pytest.raises(RegistryLoadError, match="missing required field"):
        load_registry(bad)


def test_load_wrong_schema_version_raises(tmp_path):
    bad = tmp_path / "v999.json"
    bad.write_text('{"schema_version": 999, "notebooks": []}')
    with pytest.raises(RegistryLoadError, match="schema_version"):
        load_registry(bad)
