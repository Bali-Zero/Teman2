"""Tests that config.NLM_NOTEBOOKS shim stays consistent with the registry SSOT.

If this test fails, the 4 unmigrated consumer files will break.
The snapshot pins the exact values that the running code (sentinel_actor /
nlm_feeder / nlm_expander_agent / health_tools) imports as `NLM_NOTEBOOKS`.
ONLY change a value here as part of a deliberate, coordinated re-point of a
legacy_key in `_registry_data.py` — never to silence an accidental drift.

History:
- ai_research re-pointed 2026-06-30 dc5d01cd → 069f009c: the original NB hit the
  500/500 NLM source cap, so writes route to the overflow NB-2. All 4 consumers
  move to the overflow together — intended drift, verified live.
"""
from __future__ import annotations

import re

EXPECTED_FROZEN_SNAPSHOT: dict[str, str] = {
    "ai_research":   "069f009c-ce74-42e5-b75c-e584aa18feb1",  # overflow NB-2 (dc5d01cd full)
    "self_evolving": "305f5f2e-d2f4-4f77-a771-c2b7aa0867e4",
    "regulation":    "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",
    "tax":           "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f",
    "immigration":   "1ed02e54-542f-426a-94f8-53c5ffde4b7d",
    "press":         "9d262101-abeb-4e15-af9c-c38e028c62fe",
}


def test_legacy_dict_byte_identical_to_pre_pr_snapshot():
    from mata_garuda.config import NLM_NOTEBOOKS
    assert NLM_NOTEBOOKS == EXPECTED_FROZEN_SNAPSHOT, (
        "compat shim drifted from frozen snapshot — the 4 unmigrated consumers WILL break"
    )


def test_legacy_dict_matches_registry():
    from mata_garuda.config import NLM_NOTEBOOKS
    from mata_garuda.notebook_registry import get_legacy_notebooks_dict
    assert get_legacy_notebooks_dict() == NLM_NOTEBOOKS


def test_legacy_dict_keys_match_expected_set():
    from mata_garuda.config import NLM_NOTEBOOKS
    assert set(NLM_NOTEBOOKS.keys()) == set(EXPECTED_FROZEN_SNAPSHOT.keys())


def test_legacy_dict_uuid_format():
    from mata_garuda.config import NLM_NOTEBOOKS
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    for uuid in NLM_NOTEBOOKS.values():
        assert uuid_re.match(uuid)
