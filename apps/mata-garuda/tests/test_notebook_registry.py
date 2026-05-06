"""Tests for the notebook_registry public API."""
from __future__ import annotations

import re
import dataclasses

import pytest


def test_registry_loads_without_error():
    from mata_garuda.notebook_registry import NOTEBOOK_REGISTRY
    assert isinstance(NOTEBOOK_REGISTRY, dict)
    assert len(NOTEBOOK_REGISTRY) >= 6


def test_notebook_entry_is_frozen_dataclass():
    from mata_garuda.notebook_registry import NotebookEntry
    assert dataclasses.is_dataclass(NotebookEntry)
    # Attempt to mutate must raise FrozenInstanceError.
    entry = NotebookEntry(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        name="NB-INTEL-AIResearch",
        family="NB-INTEL",
        legacy_key="ai_research",
        status="ACTIVE",
        cluster=None,
        created_at=None,
        last_audited="2026-05-07",
        action_pending=None,
        peer_uuids=[],
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.status = "SENESCENT"  # type: ignore[misc]


def test_get_legacy_notebooks_dict_returns_6_uuids():
    from mata_garuda.notebook_registry import get_legacy_notebooks_dict
    legacy = get_legacy_notebooks_dict()
    assert isinstance(legacy, dict)
    assert len(legacy) == 6


def test_get_legacy_notebooks_dict_only_active():
    """Even if the registry contains non-ACTIVE entries, legacy dict shows ACTIVE only."""
    from mata_garuda.notebook_registry import get_legacy_notebooks_dict, NOTEBOOK_REGISTRY
    legacy = get_legacy_notebooks_dict()
    for legacy_key, uuid in legacy.items():
        entry = NOTEBOOK_REGISTRY[uuid]
        assert entry.status == "ACTIVE"
        assert entry.legacy_key == legacy_key


def test_get_notebook_returns_none_for_unknown_uuid():
    from mata_garuda.notebook_registry import get_notebook
    assert get_notebook("00000000-0000-0000-0000-000000000000") is None


def test_get_by_status_returns_correct_subset():
    from mata_garuda.notebook_registry import get_by_status, NOTEBOOK_REGISTRY
    active = get_by_status("ACTIVE")
    assert len(active) == sum(1 for e in NOTEBOOK_REGISTRY.values() if e.status == "ACTIVE")
    assert all(e.status == "ACTIVE" for e in active)


def test_get_by_cluster_returns_correct_subset():
    from mata_garuda.notebook_registry import get_by_cluster
    placeholder = get_by_cluster("placeholder_empty")
    assert all(e.cluster == "placeholder_empty" for e in placeholder)


def test_registry_uuid_format():
    """All keys are valid UUID v4 format."""
    from mata_garuda.notebook_registry import NOTEBOOK_REGISTRY
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    for uuid in NOTEBOOK_REGISTRY:
        assert uuid_re.match(uuid), f"invalid UUID: {uuid}"


def test_registry_no_duplicate_legacy_keys():
    from mata_garuda.notebook_registry import NOTEBOOK_REGISTRY
    legacy_keys = [e.legacy_key for e in NOTEBOOK_REGISTRY.values() if e.legacy_key]
    assert len(legacy_keys) == len(set(legacy_keys)), "duplicate legacy_key detected"
