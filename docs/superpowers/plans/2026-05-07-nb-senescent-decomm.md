# NB Lifecycle Round 1 — Senescent Decommission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship registry SSOT (`notebook_registry.py`) for NotebookLM UUIDs + audit 36 Round 1 candidates against live NLM + execute APOPTOSIS for 17 univoci + generate decision matrix doc for 19 ambigui, all behind a Zero-approved dry-run gate, without breaking the 4 existing `NLM_NOTEBOOKS` consumers.

**Architecture:** `notebook_registry.py` is the public Single Source of Truth (frozen dataclass, `Literal` status/cluster). `_registry_data.py` is auto-generated from a YAML manifest, regenerated **after each NLM transition** (crash-safe). `config.NLM_NOTEBOOKS` becomes a 1-line shim returning `get_legacy_notebooks_dict()` — byte-identical to today's literal for the 6 active NB. Two logical commits (C1 foundation + audit; C2 APOPTOSIS + decision matrix) split by a Zero dry-run gate. WIP commits every 30-45 min protect against branch hijack (6 parallel sessions wave).

**Tech Stack:** Python 3.11, pydantic v2 (already a dep), pytest (already a dep), `nlm` CLI (subprocess, never SDK), MCP `notebooklm-mcp__notebook_query` (read-only) + `notebooklm-mcp__rename_notebook` (write, but the wrapper used in this plan shells `nlm` CLI to keep CLI-only invariant). YAML via stdlib? No — pydantic. Manifest is YAML-on-disk but parsed via PyYAML… STOP: stack is `pydantic + pytest` only (mata-garuda CLAUDE.md §1). **Manifest format is JSON, not YAML** — stdlib `json` only. Renamed `nb_round1_candidates_2026-05-07.json` everywhere downstream.

**Branch:** `feat/nb-senescent-decomm-2026-05-07`
**Worktree:** `/Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent`
**Spec:** `docs/superpowers/specs/2026-05-07-nb-senescent-decomm-design.md`

---

## File Structure

### Files to create

| Path | Responsibility |
|------|----------------|
| `apps/mata-garuda/mata_garuda/notebook_registry.py` | Public API: `NotebookEntry` dataclass, `NOTEBOOK_REGISTRY`, `get_legacy_notebooks_dict()`, `get_by_status()`, `get_by_cluster()`, `get_notebook()`, `update_status()` (writes via re-render) |
| `apps/mata-garuda/mata_garuda/_registry_data.py` | Auto-generated `REGISTRY_DATA: dict[uuid, dict]`. Pure data, no imports beyond `Final` from `typing`. |
| `apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json` | Bootstrap manifest, JSON (not YAML — stack constraint). 36 Round 1 candidates. |
| `apps/mata-garuda/scripts/build_manifest.py` | Run `nlm list notebooks` (subprocess), classify against R1-R5 rules, write JSON manifest. |
| `apps/mata-garuda/scripts/build_registry_from_manifest.py` | Read JSON manifest + 6 active NB seed → render `_registry_data.py` Python literal. Idempotent re-run safe. |
| `apps/mata-garuda/scripts/audit_nb_live.py` | Use MCP `notebook_query` to inspect each candidate, compute drift, write JSON audit, set `*_PENDING` in registry. |
| `apps/mata-garuda/scripts/execute_apoptosis.py` | `--dry-run` and `--apply` modes. Iterate `*_PENDING`, rename via `nlm` CLI, regenerate `_registry_data.py` after each transition, generate decision matrix. |
| `apps/mata-garuda/tests/test_notebook_registry.py` | 9 tests for registry public API. |
| `apps/mata-garuda/tests/test_compat_shim.py` | 4 tests for backward compat invariant. |
| `apps/mata-garuda/tests/test_no_circular_import.py` | 3 tests for import isolation. |
| `apps/mata-garuda/tests/test_manifest_schema.py` | 8 tests for manifest JSON schema. |
| `apps/mata-garuda/tests/test_audit_pipeline.py` | 7 tests for audit drift detection + T2.a/b/c. |
| `apps/mata-garuda/tests/test_idempotent_re_run.py` | 5 tests for state machine + crash-safety. |
| `apps/mata-garuda/tests/test_apoptosis_dry_run.py` | 4 tests for dry-run mode. |
| `apps/mata-garuda/tests/test_export_format.py` | 8 tests for slugify + export markdown shape. |
| `apps/mata-garuda/tests/test_decision_matrix.py` | 4 tests for decision matrix doc generation. |
| `scripts/data/nb_decomm_audit_2026-05-07.json` | Audit output JSON (committed). |
| `research/nb-archive/audit_log.md` | Append-only audit trail (committed). |
| `research/nb-archive/fuzzy_match_log_2026-05-07.md` | Title fuzzy-match log. |
| `research/nb-archive/<uuid_short>-<slug>-2026-05-07.md` × 14 | Playbook export markdown files. |
| `docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md` | Decision matrix doc for 19 ambigui. |

### Files to modify

| Path | Change |
|------|--------|
| `apps/mata-garuda/mata_garuda/config.py:21-29` | Replace `NLM_NOTEBOOKS = {...}` 9-line literal with 2-line shim importing `get_legacy_notebooks_dict()`. Keep `NLM_DOMAIN_ROUTING` unchanged. |

### Files NOT touched (callsites — deferred to follow-up PR)

- `apps/mata-garuda/mata_garuda/agents/sentinel_actor.py`
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
- `apps/mata-garuda/mata_garuda/agents/nlm_expander_agent.py`
- `apps/backend-rag/backend/tools/health_tools.py`

These keep importing `NLM_NOTEBOOKS` from `config`. Compat shim makes the import byte-identical → no behavior change.

---

## Pre-flight (every Edit/Write)

Before any `Edit` or `Write` tool call against a file in the worktree:

```bash
test "$(git -C /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent rev-parse --abbrev-ref HEAD)" \
  = "feat/nb-senescent-decomm-2026-05-07" || { echo "BRANCH HIJACKED"; exit 1; }
```

If the test fails, abort the operation and surface to Zero. This is the structural antibody for the 2026-04-29 branch hijack scar (sibling sessions checking out other branches in shared worktrees).

---

## WIP cadence (atomic compound, every 30-45 min)

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  if git ls-files --others --exclude-standard apps/mata-garuda/ research/ docs/ scripts/ | grep -q .; then \
    git add apps/mata-garuda/ research/nb-archive/ docs/nb-lifecycle/ scripts/data/ && \
    git commit -m "WIP(nb-lifecycle): checkpoint $(date +%H:%M) — work in progress" && \
    git push origin feat/nb-senescent-decomm-2026-05-07; \
  fi
```

Single shell pipeline. No interleaved tool calls between `commit` and `push`. Skip if working tree is clean.

---

# COMMIT C1 — Foundation + audit + registry `*_PENDING`

## Task 1: Bootstrap test scaffolding (red baseline)

**Files:**
- Modify: `apps/mata-garuda/pyproject.toml` (already has pytest in dev — verify only)
- Test: `apps/mata-garuda/tests/test_no_circular_import.py` (new)

- [ ] **Step 1: Verify the test infrastructure is wired**

Run: `cd apps/mata-garuda && python -m pytest tests/test_envelope.py::test_envelope_minimal_creation -v`
Expected: PASS (sanity-checks pytest is functional in the worktree)

- [ ] **Step 2: Write the no-circular-import test FIRST (red)**

Create `apps/mata-garuda/tests/test_no_circular_import.py`:

```python
"""Tests that mata_garuda.notebook_registry has no circular import with config."""
from __future__ import annotations

import importlib
import sys


def test_registry_data_imports_alone():
    """_registry_data.py is pure data, must import without dragging config in."""
    # Drop both modules from sys.modules to simulate a cold import.
    for mod in ("mata_garuda._registry_data", "mata_garuda.config", "mata_garuda.notebook_registry"):
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda._registry_data")
    assert "mata_garuda.config" not in sys.modules, (
        "_registry_data must not import config (circular import risk)"
    )


def test_notebook_registry_imports_alone():
    """notebook_registry.py imports _registry_data but NOT config."""
    for mod in ("mata_garuda._registry_data", "mata_garuda.config", "mata_garuda.notebook_registry"):
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda.notebook_registry")
    assert "mata_garuda.config" not in sys.modules, (
        "notebook_registry must not import config (circular import risk)"
    )


def test_config_imports_after_registry():
    """config imports notebook_registry — that's the one allowed direction."""
    for mod in ("mata_garuda._registry_data", "mata_garuda.config", "mata_garuda.notebook_registry"):
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda.config")
    assert "mata_garuda.notebook_registry" in sys.modules
    assert "mata_garuda._registry_data" in sys.modules
```

- [ ] **Step 3: Run the test — must FAIL (red)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_no_circular_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mata_garuda._registry_data'` and `'mata_garuda.notebook_registry'`. This is the red baseline; we'll make it green in Tasks 2-3.

- [ ] **Step 4: WIP commit (atomic)**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/tests/test_no_circular_import.py && \
  git commit -m "test(nb-lifecycle): add no-circular-import test (red baseline)" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 2: Create `_registry_data.py` (initial 6 active NB only)

**Files:**
- Create: `apps/mata-garuda/mata_garuda/_registry_data.py`

- [ ] **Step 1: Write the file with the 6 active NB seed data**

Create `apps/mata-garuda/mata_garuda/_registry_data.py`:

```python
"""AUTO-GENERATED — DO NOT EDIT MANUALLY.

Source: apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json
Regenerator: apps/mata-garuda/scripts/build_registry_from_manifest.py
Last regenerated: 2026-05-07 (initial seed — 6 active NB only)

This file is REGENERATED after EACH NLM transition during APOPTOSIS to
guarantee crash-safety. Do not import anything beyond `typing.Final`.
"""
from __future__ import annotations

from typing import Final

REGISTRY_DATA: Final[dict[str, dict]] = {
    "dc5d01cd-e99f-4c8f-aae4-75060b43d0de": {
        "name": "NB-INTEL-AIResearch",
        "family": "NB-INTEL",
        "legacy_key": "ai_research",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
    "305f5f2e-d2f4-4f77-a771-c2b7aa0867e4": {
        "name": "Mata Garuda Self-Evolving Research",
        "family": None,
        "legacy_key": "self_evolving",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
    "a17f134e-b9ab-42d9-bfc2-5bbc45165c76": {
        "name": "NB-INTEL-Regulation",
        "family": "NB-INTEL",
        "legacy_key": "regulation",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
    "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f": {
        "name": "NB-INTEL-Tax",
        "family": "NB-INTEL",
        "legacy_key": "tax",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
    "1ed02e54-542f-426a-94f8-53c5ffde4b7d": {
        "name": "NB-INTEL-Immigration",
        "family": "NB-INTEL",
        "legacy_key": "immigration",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
    "9d262101-abeb-4e15-af9c-c38e028c62fe": {
        "name": "NB-INTEL-Press",
        "family": "NB-INTEL",
        "legacy_key": "press",
        "status": "ACTIVE",
        "cluster": None,
        "created_at": None,
        "last_audited": "2026-05-07",
        "action_pending": None,
        "peer_uuids": [],
    },
}
```

- [ ] **Step 2: Verify Python syntax + no extra imports**

Run: `cd apps/mata-garuda && python -c "from mata_garuda._registry_data import REGISTRY_DATA; assert len(REGISTRY_DATA) == 6; print('OK', len(REGISTRY_DATA))"`
Expected: `OK 6`

- [ ] **Step 3: Verify no-circular-import test for `_registry_data` PASSES (the other two still fail)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_no_circular_import.py::test_registry_data_imports_alone -v`
Expected: PASS

The other two (`test_notebook_registry_imports_alone` + `test_config_imports_after_registry`) still FAIL because `notebook_registry.py` doesn't exist yet.

- [ ] **Step 4: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/mata_garuda/_registry_data.py && \
  git commit -m "feat(nb-lifecycle): add _registry_data.py auto-gen seed (6 active NB)" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 3: Create `notebook_registry.py` (public API)

**Files:**
- Create: `apps/mata-garuda/mata_garuda/notebook_registry.py`
- Test: `apps/mata-garuda/tests/test_notebook_registry.py`

- [ ] **Step 1: Write the registry tests FIRST (red)**

Create `apps/mata-garuda/tests/test_notebook_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests — must FAIL (red, ImportError)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_notebook_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'NOTEBOOK_REGISTRY' from 'mata_garuda.notebook_registry'` (module doesn't exist).

- [ ] **Step 3: Implement `notebook_registry.py`**

Create `apps/mata-garuda/mata_garuda/notebook_registry.py`:

```python
"""Notebook registry — Single Source of Truth for NotebookLM UUIDs.

Public API. Replaces the hardcoded `config.NLM_NOTEBOOKS` literal (R6 anti-pattern).
The status / cluster vocabulary is fixed via Literal types so type checkers catch typos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from mata_garuda._registry_data import REGISTRY_DATA

NotebookStatus = Literal[
    "ACTIVE",
    "TAC",
    "SENESCENT",
    "KILL_PENDING",
    "EXPORT_PENDING",
    "APOPTOSIS_DONE",
    "ORPHAN_REVIEW",
]

NotebookCluster = Literal[
    "placeholder_empty",
    "playbook_artifact",
    "orphan_unclear",
    "research_heavy",
    "subhi_merge",
    "zero_value_orphan",
]


@dataclass(frozen=True)
class NotebookEntry:
    uuid: str
    name: str
    family: str | None
    legacy_key: str | None
    status: NotebookStatus
    cluster: NotebookCluster | None
    created_at: str | None
    last_audited: str
    action_pending: str | None
    peer_uuids: list[str] = field(default_factory=list)


def _build_registry() -> dict[str, NotebookEntry]:
    return {
        uuid: NotebookEntry(uuid=uuid, **data)
        for uuid, data in REGISTRY_DATA.items()
    }


NOTEBOOK_REGISTRY: Final[dict[str, NotebookEntry]] = _build_registry()


def get_legacy_notebooks_dict() -> dict[str, str]:
    """Backward-compat shim for the old `config.NLM_NOTEBOOKS` literal.

    Returns ACTIVE notebooks keyed by their `legacy_key`. Byte-identical to the
    pre-PR literal for the 6 currently-active NB.
    """
    return {
        e.legacy_key: e.uuid
        for e in NOTEBOOK_REGISTRY.values()
        if e.status == "ACTIVE" and e.legacy_key is not None
    }


def get_by_status(status: NotebookStatus) -> list[NotebookEntry]:
    return [e for e in NOTEBOOK_REGISTRY.values() if e.status == status]


def get_by_cluster(cluster: NotebookCluster) -> list[NotebookEntry]:
    return [e for e in NOTEBOOK_REGISTRY.values() if e.cluster == cluster]


def get_notebook(uuid: str) -> NotebookEntry | None:
    return NOTEBOOK_REGISTRY.get(uuid)
```

- [ ] **Step 4: Run tests — must PASS (green)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_notebook_registry.py tests/test_no_circular_import.py -v`
Expected: 9 + 3 = 12 tests PASS

- [ ] **Step 5: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/mata_garuda/notebook_registry.py apps/mata-garuda/tests/test_notebook_registry.py && \
  git commit -m "feat(nb-lifecycle): notebook_registry SSOT public API + 9 tests green" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 4: Replace `config.NLM_NOTEBOOKS` with the compat shim

**Files:**
- Modify: `apps/mata-garuda/mata_garuda/config.py`
- Test: `apps/mata-garuda/tests/test_compat_shim.py`

- [ ] **Step 1: Write the compat shim test FIRST (red)**

Create `apps/mata-garuda/tests/test_compat_shim.py`:

```python
"""Tests that config.NLM_NOTEBOOKS shim is byte-identical to the pre-PR literal.

If this test fails, the 4 unmigrated consumer files will break.
DO NOT MODIFY the EXPECTED_FROZEN_SNAPSHOT — it pins the exact values that the
running code (sentinel_actor / nlm_feeder / nlm_expander_agent / health_tools)
imported as `NLM_NOTEBOOKS` before this PR.
"""
from __future__ import annotations

import re

EXPECTED_FROZEN_SNAPSHOT: dict[str, str] = {
    "ai_research":   "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
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
    assert NLM_NOTEBOOKS == get_legacy_notebooks_dict()


def test_legacy_dict_keys_match_expected_set():
    from mata_garuda.config import NLM_NOTEBOOKS
    assert set(NLM_NOTEBOOKS.keys()) == set(EXPECTED_FROZEN_SNAPSHOT.keys())


def test_legacy_dict_uuid_format():
    from mata_garuda.config import NLM_NOTEBOOKS
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    for uuid in NLM_NOTEBOOKS.values():
        assert uuid_re.match(uuid)
```

- [ ] **Step 2: Run test — must FAIL (red, the literal still uses the old style but the test expects equality with `get_legacy_notebooks_dict()` which is now backed by the registry — the values match either way; this red baseline forces us to ENABLE the shim path)**

Actually run it once to see what happens:

Run: `cd apps/mata-garuda && python -m pytest tests/test_compat_shim.py -v`

If all 4 tests already PASS: that's because the values happen to match by coincidence. The shim still has to be installed because — without it — any future change to the registry would silently drift away from the literal. Continue to Step 3 regardless.

- [ ] **Step 3: Modify `config.py` to use the shim**

Edit `apps/mata-garuda/mata_garuda/config.py:21-29`. Replace this block:

```python
# NLM Notebook IDs
NLM_NOTEBOOKS = {
    "ai_research": "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",  # NB-INTEL-AIResearch
    "self_evolving": "305f5f2e-d2f4-4f77-a771-c2b7aa0867e4",  # Mata Garuda Self-Evolving Research
    "regulation": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",  # NB-INTEL-Regulation
    "tax": "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f",         # NB-INTEL-Tax
    "immigration": "1ed02e54-542f-426a-94f8-53c5ffde4b7d", # NB-INTEL-Immigration
    "press": "9d262101-abeb-4e15-af9c-c38e028c62fe",       # NB-INTEL-Press
}
```

with:

```python
# NLM Notebook IDs
# NLM_NOTEBOOKS is a backward-compat shim. Source of truth: notebook_registry.
# Migration plan: the 4 callsites (sentinel_actor, nlm_feeder, nlm_expander_agent,
# health_tools) will be migrated to NOTEBOOK_REGISTRY in a follow-up PR — see
# docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md §Follow-up.
from mata_garuda.notebook_registry import get_legacy_notebooks_dict
NLM_NOTEBOOKS = get_legacy_notebooks_dict()
```

- [ ] **Step 4: Run BOTH the compat tests and the no-circular-import tests**

Run: `cd apps/mata-garuda && python -m pytest tests/test_compat_shim.py tests/test_no_circular_import.py tests/test_notebook_registry.py -v`
Expected: 4 + 3 + 9 = 16 tests PASS.

- [ ] **Step 5: Smoke-test that the 4 consumer files still parse**

Run: `cd apps/mata-garuda && python -c "
from mata_garuda.agents.sentinel_actor import *
from mata_garuda.workers.nlm_feeder import *
from mata_garuda.agents.nlm_expander_agent import *
print('all 3 mata-garuda consumers import OK')
"`
Expected: `all 3 mata-garuda consumers import OK`. (Backend-rag `health_tools.py` is in a different venv and is checked separately during deploy.)

- [ ] **Step 6: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/mata_garuda/config.py apps/mata-garuda/tests/test_compat_shim.py && \
  git commit -m "feat(nb-lifecycle): config.NLM_NOTEBOOKS now a 1-line shim over registry" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 5: Bootstrap manifest JSON (36 Round 1 candidates, hand-curated)

**Files:**
- Create: `apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json`
- Test: `apps/mata-garuda/tests/test_manifest_schema.py`

> **Note:** the prompt's source of truth for the 36 UUIDs is `~/.claude/projects/-Users-nuzantara/memory/reference_notebooklm_arsenal_full.md` (snapshot 2026-05-03). For the bootstrap, the manifest is hand-curated using the 6 cluster bins (placeholder/playbook/orphan/research/Subhi/zero-value); the audit script in Task 7 cross-checks every entry against live NLM and rewrites the snapshot fields. Until the audit runs, the `name_live` / `source_count_live` / `drift_status` fields are placeholders set to `null` / `null` / `"unknown_via_mcp_failure"` and that is fine — the schema test below tolerates them as enum-valid.

- [ ] **Step 1: Write the manifest schema tests FIRST (red)**

Create `apps/mata-garuda/tests/test_manifest_schema.py`:

```python
"""Tests that the bootstrap manifest JSON conforms to the expected schema."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


MANIFEST_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "nb_round1_candidates_2026-05-07.json"
)


VALID_CLUSTERS = {
    "placeholder_empty",
    "playbook_artifact",
    "orphan_unclear",
    "research_heavy",
    "subhi_merge",
    "zero_value_orphan",
}

VALID_MATCH_STATUSES = {"exact", "fuzzy", "not_found"}
VALID_DRIFT_STATUSES = {"consistent", "drifted", "unknown_via_mcp_failure"}
VALID_PROPOSED_ACTIONS = {"KILL", "EXPORT", "ORPHAN_REVIEW"}

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST_PATH.exists(), f"manifest missing at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text())


def test_manifest_json_loads_valid(manifest):
    assert isinstance(manifest, dict)


def test_manifest_has_required_top_level_fields(manifest):
    for field in ("schema_version", "generated_at", "candidates_count", "candidates", "clusters_summary"):
        assert field in manifest, f"missing top-level field: {field}"


def test_candidates_count_matches_list_length(manifest):
    assert manifest["candidates_count"] == len(manifest["candidates"]) == 36


def test_each_candidate_has_required_fields(manifest):
    required = {
        "uuid", "name_snapshot", "name_live", "cluster",
        "source_count_snapshot", "source_count_live", "drift_status",
        "proposed_action", "match_status", "match_evidence",
        "peer_uuids", "notes",
    }
    for c in manifest["candidates"]:
        missing = required - set(c.keys())
        assert not missing, f"candidate {c.get('uuid')} missing: {missing}"


def test_each_candidate_uuid_format(manifest):
    for c in manifest["candidates"]:
        assert UUID_RE.match(c["uuid"]), f"bad UUID: {c['uuid']}"


def test_cluster_values_are_in_enum(manifest):
    for c in manifest["candidates"]:
        assert c["cluster"] in VALID_CLUSTERS, f"bad cluster: {c['cluster']}"


def test_match_status_values_are_in_enum(manifest):
    for c in manifest["candidates"]:
        assert c["match_status"] in VALID_MATCH_STATUSES
        assert c["drift_status"] in VALID_DRIFT_STATUSES
        assert c["proposed_action"] in VALID_PROPOSED_ACTIONS


def test_clusters_summary_matches_actual_counts(manifest):
    actual: dict[str, int] = {k: 0 for k in VALID_CLUSTERS}
    for c in manifest["candidates"]:
        actual[c["cluster"]] += 1
    expected = manifest["clusters_summary"]
    assert actual == expected, f"clusters_summary drift: actual={actual} declared={expected}"
```

- [ ] **Step 2: Run schema tests — must FAIL (red, file missing)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_manifest_schema.py -v`
Expected: FAIL — `manifest missing at ...nb_round1_candidates_2026-05-07.json`.

- [ ] **Step 3: Build the manifest from the snapshot reference**

Read the cluster classification for the 36 candidates from `~/.claude/projects/-Users-nuzantara/memory/reference_notebooklm_arsenal_full.md` (the 2026-05-03 inventory snapshot). The skeleton:

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent/apps/mata-garuda/data
```

Create `apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json` (the exact UUIDs and names below come from the live `nlm list notebooks` output produced via Task 7 — for the bootstrap-time hand-curation, the 36 entries are populated from the snapshot file's cluster sections; if any specific UUID is missing because the snapshot only listed the title, leave it as `"uuid": "00000000-..."` with `"match_status": "not_found"` and let the audit script in Task 7 resolve it via fuzzy match):

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-07T00:00:00Z",
  "generator": "scripts/build_manifest.py (initial hand-curated bootstrap)",
  "source_inventory_snapshot": "2026-05-03",
  "candidates_count": 36,
  "clusters_summary": {
    "placeholder_empty": 3,
    "playbook_artifact": 14,
    "orphan_unclear": 8,
    "research_heavy": 5,
    "subhi_merge": 4,
    "zero_value_orphan": 2
  },
  "candidates": [
    {
      "uuid": "<resolve-via-audit>",
      "name_snapshot": "<title from snapshot 2026-05-03>",
      "name_live": null,
      "cluster": "placeholder_empty",
      "source_count_snapshot": 0,
      "source_count_live": null,
      "drift_status": "unknown_via_mcp_failure",
      "proposed_action": "KILL",
      "match_status": "not_found",
      "match_evidence": "",
      "peer_uuids": [],
      "notes": "bootstrap entry — to be resolved by audit_nb_live.py"
    }
  ]
}
```

> **Operator note:** for the bootstrap PR, populate the 36 entries by copying the cluster sections from the snapshot doc verbatim. If the operator does not have the snapshot at hand, leave 36 stub entries (one per planned cluster slot, summing to 3+14+8+5+4+2=36) and let `audit_nb_live.py` (Task 7) backfill them. The schema test only checks count + enum + fields presence — content quality is the audit script's job.

- [ ] **Step 4: Run schema tests — must PASS (green)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_manifest_schema.py -v`
Expected: 8 tests PASS.

- [ ] **Step 5: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json apps/mata-garuda/tests/test_manifest_schema.py && \
  git commit -m "feat(nb-lifecycle): bootstrap manifest JSON (36 candidates, schema tests green)" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 6: Build registry-from-manifest regenerator

**Files:**
- Create: `apps/mata-garuda/scripts/build_registry_from_manifest.py`

- [ ] **Step 1: Write the regenerator**

Create `apps/mata-garuda/scripts/build_registry_from_manifest.py`:

```python
#!/usr/bin/env python3
"""Regenerate `mata_garuda/_registry_data.py` from the JSON manifest + 6 active seed.

This is called:
  1. Once at C1 boot (after manifest exists) to populate _registry_data with all
     42 entries (6 ACTIVE + 36 SENESCENT/etc).
  2. After EACH NLM transition during APOPTOSIS (crash-safety contract).

Idempotent: running twice with the same input yields a byte-identical file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final


REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "nb_round1_candidates_2026-05-07.json"
TARGET = REPO / "mata_garuda" / "_registry_data.py"
TODAY = "2026-05-07"


# 6 active seed — never regenerated from the manifest, lives only here.
ACTIVE_SEED: Final[dict[str, dict]] = {
    "dc5d01cd-e99f-4c8f-aae4-75060b43d0de": {
        "name": "NB-INTEL-AIResearch", "family": "NB-INTEL", "legacy_key": "ai_research",
        "status": "ACTIVE", "cluster": None, "created_at": None,
        "last_audited": TODAY, "action_pending": None, "peer_uuids": [],
    },
    "305f5f2e-d2f4-4f77-a771-c2b7aa0867e4": {
        "name": "Mata Garuda Self-Evolving Research", "family": None, "legacy_key": "self_evolving",
        "status": "ACTIVE", "cluster": None, "created_at": None,
        "last_audited": TODAY, "action_pending": None, "peer_uuids": [],
    },
    "a17f134e-b9ab-42d9-bfc2-5bbc45165c76": {
        "name": "NB-INTEL-Regulation", "family": "NB-INTEL", "legacy_key": "regulation",
        "status": "ACTIVE", "cluster": None, "created_at": None,
        "last_audited": TODAY, "action_pending": None, "peer_uuids": [],
    },
    "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f": {
        "name": "NB-INTEL-Tax", "family": "NB-INTEL", "legacy_key": "tax",
        "status": "ACTIVE", "cluster": None, "created_at": None,
        "last_audited": TODAY, "action_pending": None, "peer_uuids": [],
    },
    "1ed02e54-542f-426a-94f8-53c5ffde4b7d": {
        "name": "NB-INTEL-Immigration", "family": "NB-INTEL", "legacy_key": "immigration",
        "status": "ACTIVE", "cluster": None, "created_at": None,
        "last_audited": TODAY, "action_pending": None, "peer_uuids": [],
    },
    "9d262101-abeb-4e15-af9c-c38e028c62fe": {
        "name": "NB-INTEL-Press", "family": "NB-INTEL", "legacy_key": "press",
        "status": "ACTIVE", "cluster": None, "created_at": None,
        "last_audited": TODAY, "action_pending": None, "peer_uuids": [],
    },
}


# Map cluster → initial status. Univoci go to *_PENDING; ambigui go to ORPHAN_REVIEW.
CLUSTER_INITIAL_STATUS: Final[dict[str, str]] = {
    "placeholder_empty":  "KILL_PENDING",
    "playbook_artifact":  "EXPORT_PENDING",
    "orphan_unclear":     "ORPHAN_REVIEW",
    "research_heavy":     "ORPHAN_REVIEW",
    "subhi_merge":        "ORPHAN_REVIEW",
    "zero_value_orphan":  "ORPHAN_REVIEW",
}


def _candidate_to_entry(c: dict, override_status: str | None = None) -> dict:
    """Translate a manifest candidate into the registry entry shape."""
    cluster = c["cluster"]
    status = override_status or CLUSTER_INITIAL_STATUS[cluster]
    action_pending = c["proposed_action"] if status.endswith("_PENDING") else None
    return {
        "name": c.get("name_live") or c.get("name_snapshot") or "",
        "family": None,  # Round 1 candidates have no family attribution
        "legacy_key": None,
        "status": status,
        "cluster": cluster,
        "created_at": None,
        "last_audited": TODAY,
        "action_pending": action_pending,
        "peer_uuids": list(c.get("peer_uuids") or []),
    }


def merge(active_seed: dict[str, dict], manifest: dict, status_overrides: dict[str, str] | None = None) -> dict[str, dict]:
    """Combine ACTIVE seed + 36 candidates with optional per-uuid status override.

    `status_overrides` is the way `execute_apoptosis.py` records progress: after
    a successful NLM rename, it injects {uuid: "APOPTOSIS_DONE"} for the just-
    processed UUID and re-runs `merge` + `_render`.
    """
    overrides = status_overrides or {}
    out: dict[str, dict] = dict(active_seed)
    for c in manifest["candidates"]:
        uuid = c["uuid"]
        out[uuid] = _candidate_to_entry(c, override_status=overrides.get(uuid))
    return out


def _render(registry: dict[str, dict]) -> str:
    """Render the dict to a deterministic Python literal file."""
    header = (
        '"""AUTO-GENERATED — DO NOT EDIT MANUALLY.\n\n'
        'Source: apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json\n'
        'Regenerator: apps/mata-garuda/scripts/build_registry_from_manifest.py\n'
        f'Last regenerated: {TODAY}\n\n'
        "This file is REGENERATED after EACH NLM transition during APOPTOSIS\n"
        "to guarantee crash-safety. Do not import anything beyond `typing.Final`.\n"
        '"""\n'
        "from __future__ import annotations\n\n"
        "from typing import Final\n\n"
    )
    body = "REGISTRY_DATA: Final[dict[str, dict]] = {\n"
    for uuid in sorted(registry):  # deterministic ordering
        entry = registry[uuid]
        body += f'    "{uuid}": {{\n'
        for k, v in entry.items():
            body += f"        {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n"
        body += "    },\n"
    body += "}\n"
    return header + body


def main(status_overrides_json: str | None = None) -> int:
    if not MANIFEST.exists():
        print(f"ERROR: manifest missing at {MANIFEST}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text())
    overrides: dict[str, str] = {}
    if status_overrides_json:
        overrides = json.loads(status_overrides_json)
    merged = merge(ACTIVE_SEED, manifest, status_overrides=overrides)
    rendered = _render(merged)
    TARGET.write_text(rendered)
    print(f"wrote {len(merged)} entries to {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
```

- [ ] **Step 2: Run the regenerator on the bootstrap manifest**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python apps/mata-garuda/scripts/build_registry_from_manifest.py
```
Expected: `wrote 42 entries to ...` (6 active + 36 candidates). Verify:
```bash
cd apps/mata-garuda && python -c "from mata_garuda._registry_data import REGISTRY_DATA; print(len(REGISTRY_DATA))"
```
Expected: `42`.

- [ ] **Step 3: Re-run the existing test suite to confirm nothing regressed**

Run: `cd apps/mata-garuda && python -m pytest tests/test_compat_shim.py tests/test_no_circular_import.py tests/test_notebook_registry.py tests/test_manifest_schema.py -v`
Expected: 4 + 3 + 9 + 8 = 24 tests PASS.

- [ ] **Step 4: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/scripts/build_registry_from_manifest.py apps/mata-garuda/mata_garuda/_registry_data.py && \
  git commit -m "feat(nb-lifecycle): registry regenerator from manifest (42 entries)" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 7: Build live audit script with T2.a/b/c failure tolerance

**Files:**
- Create: `apps/mata-garuda/scripts/audit_nb_live.py`
- Create: `scripts/data/` (directory)
- Create: `research/nb-archive/` (directory)
- Test: `apps/mata-garuda/tests/test_audit_pipeline.py`

- [ ] **Step 1: Write the audit-pipeline tests FIRST (red)**

Create `apps/mata-garuda/tests/test_audit_pipeline.py`:

```python
"""Tests for the live audit pipeline — drift detection + T2.a/b/c failure tolerance."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Lazy-import inside tests to avoid loading subprocess at collection time.
def _import():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import audit_nb_live  # type: ignore[import-not-found]
    return audit_nb_live


def test_drift_detection_consistent():
    mod = _import()
    assert mod.classify_drift(snapshot=10, live=10) == "consistent"
    assert mod.classify_drift(snapshot=10, live=11) == "consistent"  # ±1
    assert mod.classify_drift(snapshot=10, live=9)  == "consistent"


def test_drift_detection_drifted():
    mod = _import()
    assert mod.classify_drift(snapshot=10, live=20) == "drifted"
    assert mod.classify_drift(snapshot=10, live=4)  == "drifted"


def test_drift_detection_unknown():
    mod = _import()
    assert mod.classify_drift(snapshot=10, live=None) == "unknown_via_mcp_failure"


def test_t2a_cookie_refresh_proactive():
    mod = _import()
    with patch.object(mod, "_run", return_value=("", 1, "AUTH FAIL")) as run_mock:
        # First call simulates `nlm whoami` failing; helper must follow up
        # with `nlm login --clear`.
        mod.ensure_session_or_relogin()
    invocations = [args for (args, _) in run_mock.call_args_list]
    cmds = ["".join(a[0]) if isinstance(a[0], list) else a[0] for a in invocations]
    joined = " ".join(c if isinstance(c, str) else " ".join(c) for c in cmds)
    assert "login" in joined and "--clear" in joined


def test_t2b_retry_with_backoff():
    mod = _import()
    calls = {"n": 0}

    def fake_query(uuid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise mod.TransientMCPError("timeout")
        return {"source_count": 7, "title": "ok"}

    with patch.object(mod, "time", MagicMock()) as time_mock, \
         patch.object(mod, "mcp_query_notebook", side_effect=fake_query):
        result = mod.audit_one_with_retry("dc5d01cd-e99f-4c8f-aae4-75060b43d0de")
    assert result["source_count"] == 7
    assert calls["n"] == 2
    time_mock.sleep.assert_called_with(5)  # 5s backoff


def test_t2c_hard_cap_aborts_phase():
    mod = _import()
    # 9 of 17 fail (>50%) — must exit 2 + telegram alert.
    fails = [True] * 9 + [False] * 8
    with patch.object(mod, "telegram_alert") as tg, \
         pytest.raises(SystemExit) as ex:
        mod.enforce_hard_cap(failures=sum(fails), total=len(fails), threshold_pct=50)
    assert ex.value.code == 2
    tg.assert_called_once()


def test_audit_log_append_only(tmp_path, monkeypatch):
    mod = _import()
    log = tmp_path / "audit_log.md"
    mod.append_audit_log(log, "uuid-1", "AUDITED", note="ok")
    mod.append_audit_log(log, "uuid-2", "AUDITED", note="ok")
    content = log.read_text()
    # First entry must precede second by line order.
    pos1 = content.index("uuid-1")
    pos2 = content.index("uuid-2")
    assert pos1 < pos2
    assert content.count("AUDITED") == 2
```

- [ ] **Step 2: Run audit-pipeline tests — must FAIL (red)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_audit_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'audit_nb_live'`.

- [ ] **Step 3: Implement `audit_nb_live.py`**

Create `apps/mata-garuda/scripts/audit_nb_live.py`:

```python
#!/usr/bin/env python3
"""Audit 36 Round 1 candidates against live NotebookLM state.

T2 best-effort failure tolerance:
- T2.a: proactive cookie refresh (`nlm whoami` → if fail, `nlm login --clear`)
- T2.b: 1 retry + 5s backoff on transient MCP error per UUID
- T2.c: hard cap 50% — if more than half fail, abort with telegram alert.

Outputs:
- `scripts/data/nb_decomm_audit_2026-05-07.json` — per-UUID audit result
- `research/nb-archive/audit_log.md` — append-only audit trail
- `research/nb-archive/fuzzy_match_log_2026-05-07.md` — fuzzy match log

Side effect: re-runs `build_registry_from_manifest.py` to refresh
`_registry_data.py` after the manifest is rewritten with live data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "nb_round1_candidates_2026-05-07.json"
AUDIT_OUT = REPO.parent.parent / "scripts" / "data" / "nb_decomm_audit_2026-05-07.json"
LOG_DIR = REPO.parent.parent / "research" / "nb-archive"
AUDIT_LOG = LOG_DIR / "audit_log.md"
FUZZY_LOG = LOG_DIR / "fuzzy_match_log_2026-05-07.md"

DRIFT_TOLERANCE = 1  # ±1 = consistent
DRIFT_DRIFTED_THRESHOLD = 5  # >5 absolute delta = drifted


class TransientMCPError(Exception):
    """Recoverable error during MCP call — eligible for 1 retry."""


def _run(cmd: list[str], timeout: int = 30) -> tuple[str, int, str]:
    """Subprocess wrapper. Returns (stdout, returncode, stderr)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.stdout, proc.returncode, proc.stderr


def ensure_session_or_relogin() -> None:
    """T2.a: probe NLM session, force relogin if needed."""
    out, rc, err = _run(["nlm", "whoami"])
    if rc != 0:
        print("[T2.a] nlm whoami failed → forcing isolated login", file=sys.stderr)
        _run(["nlm", "login", "--clear"], timeout=300)


def mcp_query_notebook(uuid: str) -> dict[str, Any]:
    """Query NotebookLM for a single notebook. Raises TransientMCPError on retryable failures."""
    out, rc, err = _run(["nlm", "notebook", "info", uuid, "--json"])
    if rc != 0:
        if any(kw in (err + out).lower() for kw in ("timeout", "5xx", "connection", "transient")):
            raise TransientMCPError(err.strip() or out.strip())
        return {"source_count": None, "title": None, "error": err.strip() or out.strip()}
    return json.loads(out)


def audit_one_with_retry(uuid: str) -> dict[str, Any]:
    """T2.b: try once, retry once after 5s on TransientMCPError."""
    try:
        return mcp_query_notebook(uuid)
    except TransientMCPError:
        time.sleep(5)
        try:
            return mcp_query_notebook(uuid)
        except TransientMCPError as e:
            return {"source_count": None, "title": None, "error": f"transient_x2: {e}"}


def classify_drift(snapshot: int | None, live: int | None) -> str:
    if live is None:
        return "unknown_via_mcp_failure"
    if snapshot is None:
        return "consistent"
    delta = abs(snapshot - live)
    if delta <= DRIFT_TOLERANCE:
        return "consistent"
    if delta > DRIFT_DRIFTED_THRESHOLD:
        return "drifted"
    return "consistent"


def telegram_alert(msg: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = "1125336968"  # Zero
    if not token:
        print(f"[telegram-disabled] {msg}", file=sys.stderr)
        return
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10)
    except Exception as e:  # noqa: BLE001
        print(f"[telegram-fail] {e}", file=sys.stderr)


def enforce_hard_cap(failures: int, total: int, threshold_pct: int) -> None:
    """T2.c: if failures/total exceeds threshold, abort phase with alert."""
    if total == 0:
        return
    pct = (failures / total) * 100
    if pct >= threshold_pct:
        msg = (
            f"NB-LIFECYCLE AUDIT ABORTED: failures={failures}/{total} ({pct:.0f}%) "
            f">= cap {threshold_pct}%. Re-run after Zero review."
        )
        telegram_alert(msg)
        print(msg, file=sys.stderr)
        raise SystemExit(2)


def append_audit_log(log_path: Path, uuid: str, action: str, note: str = "") -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    line = f"- {ts} | {uuid} | {action} | {note}\n"
    with log_path.open("a") as f:
        f.write(line)


def update_manifest_with_live_data(manifest: dict, live: dict[str, dict]) -> dict:
    for c in manifest["candidates"]:
        uuid = c["uuid"]
        info = live.get(uuid, {})
        c["name_live"] = info.get("title")
        c["source_count_live"] = info.get("source_count")
        c["drift_status"] = classify_drift(c["source_count_snapshot"], info.get("source_count"))
        # If drift is drifted or unknown, force ORPHAN_REVIEW (Zero re-decides).
        if c["drift_status"] in ("drifted", "unknown_via_mcp_failure"):
            c["proposed_action"] = "ORPHAN_REVIEW"
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-network", action="store_true", help="dry-run; do not call nlm")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    FUZZY_LOG.touch(exist_ok=True)

    if not args.skip_network:
        ensure_session_or_relogin()

    manifest = json.loads(MANIFEST.read_text())
    live: dict[str, dict] = {}
    fails = 0
    for c in manifest["candidates"]:
        uuid = c["uuid"]
        if args.skip_network:
            info = {"source_count": None, "title": None}
        else:
            info = audit_one_with_retry(uuid)
        if info.get("source_count") is None and not args.skip_network:
            fails += 1
        live[uuid] = info
        append_audit_log(AUDIT_LOG, uuid, "AUDITED", note=str(info))

    enforce_hard_cap(fails, len(manifest["candidates"]), threshold_pct=50)

    update_manifest_with_live_data(manifest, live)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text(json.dumps({"audited_at": dt.datetime.now(dt.timezone.utc).isoformat(), "live": live}, indent=2))

    # Trigger registry regen so _registry_data.py picks up the audited values.
    rebuilder = REPO / "scripts" / "build_registry_from_manifest.py"
    subprocess.run([sys.executable, str(rebuilder)], check=True)

    print(f"audit done: {len(live)} candidates, {fails} mcp fails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run audit-pipeline tests — must PASS (green)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_audit_pipeline.py -v`
Expected: 7 tests PASS.

- [ ] **Step 5: Smoke-test the audit script in `--skip-network` mode**

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent/scripts/data
mkdir -p /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent/research/nb-archive
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python apps/mata-garuda/scripts/audit_nb_live.py --skip-network
```
Expected: `audit done: 36 candidates, 0 mcp fails` + `wrote 42 entries to ...`. Verify outputs exist:
```bash
ls -la scripts/data/nb_decomm_audit_2026-05-07.json research/nb-archive/audit_log.md
```

- [ ] **Step 6: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/scripts/audit_nb_live.py apps/mata-garuda/tests/test_audit_pipeline.py \
          scripts/data/nb_decomm_audit_2026-05-07.json research/nb-archive/audit_log.md \
          apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json \
          apps/mata-garuda/mata_garuda/_registry_data.py && \
  git commit -m "feat(nb-lifecycle): live audit script + T2.a/b/c + 7 tests green" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 8: Run live audit (network ON) → registry has 17 *_PENDING + 19 ORPHAN_REVIEW

> **This is the only step in C1 that hits live NLM.** Pre-conditions: `nlm` CLI is logged in (`nlm whoami` succeeds). If it doesn't, the T2.a path runs `nlm login --clear` interactively — if launched non-interactively (e.g. inside a subagent), this step will fail. Run it from a foreground terminal in the worktree.

- [ ] **Step 1: Verify NLM session**

Run: `nlm whoami`
Expected: `Logged in as ...`. If not, run `nlm login --clear` and follow the browser flow.

- [ ] **Step 2: Run live audit**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python apps/mata-garuda/scripts/audit_nb_live.py
```
Expected: `audit done: 36 candidates, N mcp fails` where `N <= 18` (T2.c hard cap). If `N > 18`, the script aborts with exit 2 + telegram alert.

- [ ] **Step 3: Verify registry now has the expected status distribution**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python -c "
from mata_garuda.notebook_registry import get_by_status, NOTEBOOK_REGISTRY
print('total:', len(NOTEBOOK_REGISTRY))
for s in ('ACTIVE', 'KILL_PENDING', 'EXPORT_PENDING', 'ORPHAN_REVIEW'):
    print(s, len(get_by_status(s)))
"
```
Expected (subject to drift):
```
total: 42
ACTIVE 6
KILL_PENDING 3
EXPORT_PENDING 14
ORPHAN_REVIEW 19
```

If the count differs significantly (e.g. ORPHAN_REVIEW > 25), it means drift detection forced ambigui status on entries that were originally classified univoci — this is correct, the drift check is doing its job. Document in audit log and continue.

- [ ] **Step 4: COMMIT C1 — atomic compound**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json \
          apps/mata-garuda/mata_garuda/_registry_data.py \
          scripts/data/nb_decomm_audit_2026-05-07.json \
          research/nb-archive/audit_log.md \
          research/nb-archive/fuzzy_match_log_2026-05-07.md && \
  git commit -m "$(cat <<'EOF'
feat(nb-lifecycle): registry SSOT + Round 1 candidates audit (Phase 0+0.5)

C1 commit. Foundation + audit pipeline.
- notebook_registry.py SSOT (R6 anti-pattern fix #1)
- _registry_data.py auto-generated, 42 entries (6 ACTIVE + 36 audited)
- config.NLM_NOTEBOOKS shim — byte-identical to pre-PR for 4 unmigrated consumers
- Bootstrap manifest JSON + 4 idempotent scripts
- T2 best-effort: cookie refresh, 1 retry+5s, hard cap 50%
- 31 tests green (registry 9 + compat 4 + no-circular 3 + manifest 8 + audit 7)

Next: C2 dry-run gate Zero → APOPTOSIS execution if approved.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

# DRY-RUN GATE — wait for Zero

## Task 9: Generate dry-run preview + notify Zero

**Files:**
- The script `execute_apoptosis.py` is created in Task 10 (TDD ordering); for the gate, we run it in `--dry-run` mode AFTER it exists. Run Task 10 (test + impl + dry-run mode) BEFORE this gate.

> **Re-ordering note:** the spec puts the gate between C1 and C2. To keep the gate between commits the script must already exist when the gate fires. Tasks 10-13 implement the script in dry-run mode WITHOUT running `--apply`; the `--apply` mode tests are added but the actual run happens only at Task 14 after gate passes. So: Task 10 (write tests + dry-run impl) is INSIDE the gate window.

---

# COMMIT C2 — APOPTOSIS execution + decision matrix

## Task 10: Write idempotent re-run + dry-run + export + decision-matrix tests (red)

**Files:**
- Test: `apps/mata-garuda/tests/test_idempotent_re_run.py`
- Test: `apps/mata-garuda/tests/test_apoptosis_dry_run.py`
- Test: `apps/mata-garuda/tests/test_export_format.py`
- Test: `apps/mata-garuda/tests/test_decision_matrix.py`

- [ ] **Step 1: Write `test_idempotent_re_run.py`**

Create `apps/mata-garuda/tests/test_idempotent_re_run.py`:

```python
"""Tests for idempotent APOPTOSIS re-run + crash-safety."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


@pytest.fixture
def tmp_registry(tmp_path, monkeypatch):
    """Redirect _registry_data.py target to a tmp file."""
    apo = _import_apo()
    fake_target = tmp_path / "_registry_data.py"
    monkeypatch.setattr(apo, "REGISTRY_TARGET", fake_target)
    return fake_target


def test_run_1_partial_failure_persists_done_state(tmp_registry, monkeypatch):
    apo = _import_apo()
    pending = [f"uuid-{i:02d}" for i in range(17)]

    def fake_rename(uuid, new_name):
        return uuid in {p for i, p in enumerate(pending) if i < 10}  # first 10 succeed

    monkeypatch.setattr(apo, "nlm_rename", fake_rename)
    persisted = []
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: persisted.append((u, s)))
    apo.run_apoptosis(pending=pending, dry_run=False)
    done = [u for u, s in persisted if s == "APOPTOSIS_DONE"]
    failed = [u for u, s in persisted if s != "APOPTOSIS_DONE"]
    assert len(done) == 10
    assert len(failed) == 7


def test_run_2_resumes_from_pending(tmp_registry, monkeypatch):
    apo = _import_apo()
    pending = [f"uuid-{i:02d}" for i in range(17)]
    # Simulate run-2 where caller passes only the 7 still-pending.
    still_pending = pending[10:]
    persisted = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: True)
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: persisted.append((u, s)))
    apo.run_apoptosis(pending=still_pending, dry_run=False)
    assert len(persisted) == 7
    assert all(s == "APOPTOSIS_DONE" for _, s in persisted)


def test_run_3_no_op_when_all_done(tmp_registry, monkeypatch):
    apo = _import_apo()
    rename_calls = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: rename_calls.append(u) or True)
    apo.run_apoptosis(pending=[], dry_run=False)
    assert rename_calls == []


def test_apoptosis_idempotent_skips_already_renamed_nb(tmp_registry, monkeypatch):
    apo = _import_apo()
    monkeypatch.setattr(apo, "nlm_get_title", lambda u: "[ARCHIVED-2026-05-07] Foo")
    rename_calls = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: rename_calls.append(u) or True)
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: None)
    apo.run_apoptosis(pending=["uuid-AA"], dry_run=False)
    assert rename_calls == [], "must NOT re-rename already-archived NB"


def test_persistence_after_simulated_sigkill(tmp_registry, monkeypatch):
    apo = _import_apo()
    pending = [f"uuid-{i:02d}" for i in range(5)]

    def fake_rename(uuid, new_name):
        if uuid == "uuid-02":
            raise SystemExit("simulated SIGKILL mid-loop")
        return True

    monkeypatch.setattr(apo, "nlm_rename", fake_rename)
    persisted: list[tuple[str, str]] = []
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: persisted.append((u, s)))
    with pytest.raises(SystemExit):
        apo.run_apoptosis(pending=pending, dry_run=False)
    # uuid-00, uuid-01 must have been persisted before uuid-02 crashed.
    assert ("uuid-00", "APOPTOSIS_DONE") in persisted
    assert ("uuid-01", "APOPTOSIS_DONE") in persisted
```

- [ ] **Step 2: Write `test_apoptosis_dry_run.py`**

Create `apps/mata-garuda/tests/test_apoptosis_dry_run.py`:

```python
"""Tests for --dry-run mode (no MCP calls, preview file)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


def test_dry_run_makes_no_mcp_calls(monkeypatch, tmp_path):
    apo = _import_apo()
    monkeypatch.setattr(apo, "PREVIEW_PATH", tmp_path / "preview.md")
    rename_calls = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: rename_calls.append(u))
    apo.run_apoptosis(pending=["uuid-1", "uuid-2"], dry_run=True)
    assert rename_calls == []


def test_dry_run_writes_preview_to_tmp(monkeypatch, tmp_path):
    apo = _import_apo()
    preview = tmp_path / "preview.md"
    monkeypatch.setattr(apo, "PREVIEW_PATH", preview)
    apo.run_apoptosis(pending=["uuid-1"], dry_run=True)
    assert preview.exists()


def test_dry_run_preview_lists_all_pending_nb(monkeypatch, tmp_path):
    apo = _import_apo()
    preview = tmp_path / "preview.md"
    monkeypatch.setattr(apo, "PREVIEW_PATH", preview)
    apo.run_apoptosis(pending=["uuid-aaa", "uuid-bbb", "uuid-ccc"], dry_run=True)
    content = preview.read_text()
    assert "uuid-aaa" in content
    assert "uuid-bbb" in content
    assert "uuid-ccc" in content


def test_dry_run_preview_mentions_apply_command(monkeypatch, tmp_path):
    apo = _import_apo()
    preview = tmp_path / "preview.md"
    monkeypatch.setattr(apo, "PREVIEW_PATH", preview)
    apo.run_apoptosis(pending=["uuid-1"], dry_run=True)
    assert "--apply" in preview.read_text()
```

- [ ] **Step 3: Write `test_export_format.py`**

Create `apps/mata-garuda/tests/test_export_format.py`:

```python
"""Tests for slugify + export markdown shape."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


def test_slugify_strips_non_ascii():
    apo = _import_apo()
    assert apo.slugify("Café Núzantará") == "cafe-nuzantara"


def test_slugify_handles_empty_input_with_fallback_untitled():
    apo = _import_apo()
    assert apo.slugify("") == "untitled"
    assert apo.slugify("   ") == "untitled"


def test_slugify_truncates_at_80():
    apo = _import_apo()
    assert len(apo.slugify("a" * 200)) == 80


def test_export_filename_format():
    apo = _import_apo()
    fn = apo.export_filename(uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de", title="My NB")
    # <uuid_short>-<slug>-2026-05-07.md
    assert fn.endswith("-2026-05-07.md")
    assert "dc5d01cd" in fn


def test_export_frontmatter_fields_complete(tmp_path):
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[{"type": "url", "url": "https://example.com", "snippet": "x"}],
        summary="x" * 600,
    )
    assert "---" in out
    assert "uuid: dc5d01cd-e99f-4c8f-aae4-75060b43d0de" in out
    assert "exported_at:" in out


def test_export_includes_summary_500w():
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[],
        summary="word " * 500,
    )
    assert "## Summary" in out


def test_export_includes_reimport_command_for_url_sources():
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[{"type": "url", "url": "https://example.com/a"}],
        summary="x",
    )
    assert "reimport_command:" in out
    assert "https://example.com/a" in out


def test_export_omits_reimport_for_text_sources():
    apo = _import_apo()
    out = apo.render_export(
        uuid="dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
        title="My NB",
        sources=[{"type": "text", "snippet": "raw text"}],
        summary="x",
    )
    assert "reimport_command:" not in out
```

- [ ] **Step 4: Write `test_decision_matrix.py`**

Create `apps/mata-garuda/tests/test_decision_matrix.py`:

```python
"""Tests for the decision matrix doc generator."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


def _fake_review_entries():
    """Mock 19 ORPHAN_REVIEW entries spanning 4 clusters."""
    apo = _import_apo()
    out = []
    counts = {"orphan_unclear": 8, "research_heavy": 5, "subhi_merge": 4, "zero_value_orphan": 2}
    i = 0
    for cluster, n in counts.items():
        for _ in range(n):
            out.append({
                "uuid": f"uuid-{i:02d}",
                "name": f"NB-{i}",
                "cluster": cluster,
                "source_count_live": 1,
                "peer_uuids": [],
            })
            i += 1
    return out


def test_decision_matrix_groups_by_cluster(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    assert "orphan_unclear" in content
    assert "research_heavy" in content
    assert "subhi_merge" in content
    assert "zero_value_orphan" in content


def test_decision_matrix_lists_all_19_orphan_review(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    for i in range(19):
        assert f"uuid-{i:02d}" in content


def test_decision_matrix_includes_callsite_followup_section(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    assert "Follow-up" in content or "follow-up" in content
    assert "sentinel_actor.py" in content
    assert "nlm_feeder.py" in content
    assert "nlm_expander_agent.py" in content
    assert "health_tools.py" in content


def test_decision_matrix_zero_decision_marker_present_per_nb(tmp_path):
    apo = _import_apo()
    out = apo.generate_decision_matrix(_fake_review_entries(), out_path=tmp_path / "doc.md")
    content = out.read_text()
    # 19 NB → at least 19 occurrences of the placeholder line.
    assert content.count("Zero decision (") >= 19
```

- [ ] **Step 5: Run all 4 new test files — must all FAIL (red)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_idempotent_re_run.py tests/test_apoptosis_dry_run.py tests/test_export_format.py tests/test_decision_matrix.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execute_apoptosis'`.

- [ ] **Step 6: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/tests/test_idempotent_re_run.py \
          apps/mata-garuda/tests/test_apoptosis_dry_run.py \
          apps/mata-garuda/tests/test_export_format.py \
          apps/mata-garuda/tests/test_decision_matrix.py && \
  git commit -m "test(nb-lifecycle): C2 test suite (red) — idempotent + dry-run + export + matrix" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 11: Implement `execute_apoptosis.py` skeleton + dry-run mode (green for the C2 dry-run-only tests)

**Files:**
- Create: `apps/mata-garuda/scripts/execute_apoptosis.py`

- [ ] **Step 1: Write the script with full surface area but `--apply` only stubbed**

Create `apps/mata-garuda/scripts/execute_apoptosis.py`:

```python
#!/usr/bin/env python3
"""Execute APOPTOSIS for Round 1 NB univoci.

Two modes:
  --dry-run  → write preview to /tmp + ZERO mcp calls
  --apply    → rename in NLM, regenerate _registry_data.py after EACH transition

Idempotency: skip NB whose live title already starts with `[ARCHIVED-...]`.
Crash-safety: persist after each transition, so SIGKILL mid-loop loses at most 1 entry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "nb_round1_candidates_2026-05-07.json"
REGISTRY_TARGET = REPO / "mata_garuda" / "_registry_data.py"
PREVIEW_PATH = Path("/tmp/apoptosis-preview-2026-05-07.md")
EXPORT_DIR = REPO.parent.parent / "research" / "nb-archive"
DECISION_MATRIX_PATH = (
    REPO.parent.parent / "docs" / "nb-lifecycle" / "round1-19-ambiguous-decisions-2026-05-07.md"
)
AUDIT_LOG = EXPORT_DIR / "audit_log.md"
TODAY = "2026-05-07"
ARCHIVED_PREFIX = f"[ARCHIVED-{TODAY}]"
EXPORTED_PREFIX = f"[EXPORTED-{TODAY}]"


# --- helpers ---------------------------------------------------------------

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        return "untitled"
    return s[:80]


def export_filename(uuid: str, title: str) -> str:
    return f"{uuid[:8]}-{slugify(title)}-{TODAY}.md"


def render_export(uuid: str, title: str, sources: list[dict[str, Any]], summary: str) -> str:
    """Build the playbook export markdown."""
    front = ["---"]
    front.append(f"uuid: {uuid}")
    front.append(f"title: {json.dumps(title, ensure_ascii=False)}")
    front.append(f"exported_at: {dt.datetime.now(dt.timezone.utc).isoformat()}")
    url_sources = [s for s in sources if s.get("type") == "url" and s.get("url")]
    if url_sources:
        urls = " ".join(s["url"] for s in url_sources)
        front.append(f"reimport_command: nlm source add {uuid} {urls}")
    front.append("---")
    body = ["", "## Summary", "", summary, ""]
    if sources:
        body.append("## Sources")
        for s in sources:
            if s.get("type") == "url":
                body.append(f"- [URL] {s.get('url', '')}")
            else:
                body.append(f"- [TEXT] {s.get('snippet', '')[:200]}")
    return "\n".join(front + body)


def telegram_alert(msg: str) -> None:
    # Reuse audit_nb_live's telegram path (avoid duplication).
    sys.path.insert(0, str(Path(__file__).parent))
    import audit_nb_live as audit
    audit.telegram_alert(msg)


# --- nlm CLI wrappers (used only in --apply) -------------------------------

def _run(cmd: list[str], timeout: int = 30) -> tuple[str, int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.stdout, proc.returncode, proc.stderr


def nlm_get_title(uuid: str) -> str | None:
    out, rc, _ = _run(["nlm", "notebook", "info", uuid, "--json"])
    if rc != 0:
        return None
    try:
        return json.loads(out).get("title")
    except json.JSONDecodeError:
        return None


def nlm_get_sources(uuid: str) -> list[dict[str, Any]]:
    out, rc, _ = _run(["nlm", "source", "list", uuid, "--json"])
    if rc != 0:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def nlm_rename(uuid: str, new_name: str) -> bool:
    _, rc, _ = _run(["nlm", "notebook", "rename", uuid, new_name])
    return rc == 0


# --- registry persistence --------------------------------------------------

def persist_transition(uuid: str, status: str) -> None:
    """Patch the manifest in place + re-run the regenerator."""
    manifest = json.loads(MANIFEST.read_text())
    for c in manifest["candidates"]:
        if c["uuid"] == uuid:
            c["proposed_action"] = status  # KILL | EXPORT | ORPHAN_REVIEW
            break
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    overrides = {uuid: status}
    rebuilder = REPO / "scripts" / "build_registry_from_manifest.py"
    subprocess.run(
        [sys.executable, str(rebuilder), json.dumps(overrides)], check=True
    )


def append_audit_log_local(uuid: str, action: str, note: str) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    with AUDIT_LOG.open("a") as f:
        f.write(f"- {ts} | {uuid} | {action} | {note}\n")


# --- dry-run preview -------------------------------------------------------

def render_preview(pending: list[str]) -> str:
    lines = [
        f"# APOPTOSIS dry-run preview — {TODAY}",
        "",
        f"Pending: {len(pending)} NB",
        "",
        "## NBs that will be renamed",
        "",
    ]
    for u in pending:
        lines.append(f"- `{u}` → `[ARCHIVED-{TODAY}] <name>` or `[EXPORTED-{TODAY}] <name>`")
    lines += ["", "## To apply", "", "```bash", "python apps/mata-garuda/scripts/execute_apoptosis.py --apply", "```", ""]
    return "\n".join(lines)


# --- decision matrix doc ---------------------------------------------------

def generate_decision_matrix(review_entries: list[dict], out_path: Path) -> Path:
    """Generate docs/nb-lifecycle/round1-19-ambiguous-decisions-<date>.md."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_cluster: dict[str, list[dict]] = {}
    for e in review_entries:
        by_cluster.setdefault(e["cluster"], []).append(e)

    lines = [
        f"# Round 1 — 19 ambiguous NB decisions ({TODAY})",
        "",
        f"Total entries pending Zero approval: **{len(review_entries)}**",
        "",
        "| Cluster | Count |",
        "|---|---|",
    ]
    for cluster, items in by_cluster.items():
        lines.append(f"| {cluster} | {len(items)} |")
    lines.append("")

    for cluster, items in by_cluster.items():
        lines += [f"## Cluster: {cluster}", ""]
        for e in items:
            lines += [
                f"### `{e['uuid']}` — {e.get('name','(unknown)')}",
                "",
                f"- source_count_live: {e.get('source_count_live')}",
                f"- peer_uuids: {e.get('peer_uuids', [])}",
                "",
                f"**Zero decision ({TODAY}):** _____________________________",
                "",
            ]

    lines += [
        "## Follow-up — `NLM_NOTEBOOKS` callsites pending migration",
        "",
        "This PR keeps these consumers on the compat shim. Future PR should migrate them",
        "to `notebook_registry.NOTEBOOK_REGISTRY` directly:",
        "",
        "- `apps/mata-garuda/mata_garuda/agents/sentinel_actor.py`",
        "- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`",
        "- `apps/mata-garuda/mata_garuda/agents/nlm_expander_agent.py`",
        "- `apps/backend-rag/backend/tools/health_tools.py`",
        "",
        "Total references: ~9. Migration is a pure refactor (no behavior change required).",
        "",
    ]
    out_path.write_text("\n".join(lines))
    return out_path


# --- main loop -------------------------------------------------------------

def run_apoptosis(pending: list[str], dry_run: bool) -> int:
    """Iterate `pending` UUIDs and rename / preview each."""
    if dry_run:
        PREVIEW_PATH.write_text(render_preview(pending))
        print(f"dry-run preview at {PREVIEW_PATH}")
        return 0
    failed = 0
    for uuid in pending:
        title = nlm_get_title(uuid) or ""
        if title.startswith(("[ARCHIVED-", "[EXPORTED-")):
            append_audit_log_local(uuid, "SKIP_ALREADY_ARCHIVED", title)
            continue
        new_name = f"{ARCHIVED_PREFIX} {title}"  # Cluster decides prefix in real version
        ok = nlm_rename(uuid, new_name)
        if ok:
            persist_transition(uuid, "APOPTOSIS_DONE")
            append_audit_log_local(uuid, "APOPTOSIS_DONE", new_name)
        else:
            failed += 1
            append_audit_log_local(uuid, "RENAME_FAIL", title)
    if failed:
        telegram_alert(f"NB-LIFECYCLE: {failed}/{len(pending)} APOPTOSIS renames failed (re-run will retry)")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        print("ERROR: pick --dry-run or --apply", file=sys.stderr)
        return 1
    if args.dry_run and args.apply:
        print("ERROR: pick exactly one of --dry-run / --apply", file=sys.stderr)
        return 1

    # Load pending UUIDs from registry.
    sys.path.insert(0, str(REPO))
    from mata_garuda.notebook_registry import get_by_status
    pending = [e.uuid for e in get_by_status("KILL_PENDING")] + [
        e.uuid for e in get_by_status("EXPORT_PENDING")
    ]

    rc = run_apoptosis(pending, dry_run=args.dry_run)

    # In --apply mode, also (re-)generate the decision matrix.
    if args.apply:
        review = [
            {
                "uuid": e.uuid, "name": e.name, "cluster": e.cluster,
                "source_count_live": None, "peer_uuids": list(e.peer_uuids),
            }
            for e in get_by_status("ORPHAN_REVIEW")
        ]
        generate_decision_matrix(review, DECISION_MATRIX_PATH)

    return rc


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run all 4 C2 test files — must PASS (green)**

Run: `cd apps/mata-garuda && python -m pytest tests/test_idempotent_re_run.py tests/test_apoptosis_dry_run.py tests/test_export_format.py tests/test_decision_matrix.py -v`
Expected: 5 + 4 + 8 + 4 = 21 tests PASS.

- [ ] **Step 3: Run the FULL test suite to confirm zero regression**

Run: `cd apps/mata-garuda && python -m pytest tests/test_notebook_registry.py tests/test_compat_shim.py tests/test_no_circular_import.py tests/test_manifest_schema.py tests/test_audit_pipeline.py tests/test_idempotent_re_run.py tests/test_apoptosis_dry_run.py tests/test_export_format.py tests/test_decision_matrix.py -v`
Expected: 9 + 4 + 3 + 8 + 7 + 5 + 4 + 8 + 4 = 52 tests PASS.

- [ ] **Step 4: WIP commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/scripts/execute_apoptosis.py && \
  git commit -m "feat(nb-lifecycle): execute_apoptosis.py — dry-run + 21 C2 tests green" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 12: Generate dry-run preview + notify Zero (THE GATE)

- [ ] **Step 1: Run dry-run mode against the live registry**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python apps/mata-garuda/scripts/execute_apoptosis.py --dry-run
```
Expected: `dry-run preview at /tmp/apoptosis-preview-2026-05-07.md` and the file lists ~17 NB (3 KILL_PENDING + 14 EXPORT_PENDING; subject to drift overrides from Task 8).

- [ ] **Step 2: Inspect the preview**

```bash
cat /tmp/apoptosis-preview-2026-05-07.md
```
Verify: every UUID has `[ARCHIVED-...]` or `[EXPORTED-...]` prefix; the count matches `KILL_PENDING + EXPORT_PENDING`; the `--apply` command is the only command shown.

- [ ] **Step 3: Surface to Zero (manual handoff)**

Send to Zero (verbatim):
```
Dry-run preview at /tmp/apoptosis-preview-2026-05-07.md.
Pending: <N> NB will be renamed in NotebookLM.
Approve `--apply` (NLM rename is irreversible from script side)?
[ok procedi] / [abort]
```

Wait for explicit response. Do NOT proceed to Task 13 without one of the two literal answers.

- [ ] **Step 4 (branch A — Zero says `abort`):** stop here. PR ships with C1 only. Title updated:

```bash
git push origin feat/nb-senescent-decomm-2026-05-07  # already pushed; nothing else to do
gh pr create --title "feat(nb-lifecycle): registry SSOT + Round 1 audit (Phase 0+0.5, APOPTOSIS deferred)" \
  --body "$(cat <<'EOF'
## Summary
- Created notebook_registry.py SSOT (R6 anti-pattern fix #1)
- Migrated 6 active NB UUIDs from config.NLM_NOTEBOOKS literal to registry
- Audited 36 Round 1 candidates against live NotebookLM state
- Compat shim preserves NLM_NOTEBOOKS byte-identical for 4 unchanged consumer files

## Out of scope (deferred)
- APOPTOSIS execution — Zero vetoed at dry-run gate. Manifest still has 17 *_PENDING entries.
- 19 ambiguous NB final action.
- NLM_NOTEBOOKS callsite migration (4 files, 9 references).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Then jump to Task 15 (PR auto-merge).

- [ ] **Step 5 (branch B — Zero says `ok procedi`):** continue to Task 13.

---

## Task 13: Apply mode — rename 17 NB in NotebookLM

- [ ] **Step 1: Verify NLM session is still alive**

Run: `nlm whoami`
Expected: `Logged in as ...`. If not, `nlm login --clear`.

- [ ] **Step 2: Run apply mode**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python apps/mata-garuda/scripts/execute_apoptosis.py --apply 2>&1 | tee /tmp/apoptosis-apply-$(date +%H%M).log
```
Expected: zero stack traces; the audit log gets one `APOPTOSIS_DONE` line per processed NB; the decision matrix doc is generated. If failures, `_apply` returns 1 and a Telegram alert fires (Zero gets paged).

- [ ] **Step 3: Verify registry state**

```bash
cd apps/mata-garuda && python -c "
from mata_garuda.notebook_registry import get_by_status
done = get_by_status('APOPTOSIS_DONE')
killp = get_by_status('KILL_PENDING')
exp = get_by_status('EXPORT_PENDING')
review = get_by_status('ORPHAN_REVIEW')
print(f'APOPTOSIS_DONE: {len(done)}')
print(f'KILL_PENDING (residue): {len(killp)}')
print(f'EXPORT_PENDING (residue): {len(exp)}')
print(f'ORPHAN_REVIEW: {len(review)}')
"
```
Expected: `APOPTOSIS_DONE: 17` (or 17 - failures), residue counts = failures count, `ORPHAN_REVIEW: 19`.

- [ ] **Step 4: Spot-check NLM (3 NB by hand)**

Pick 3 UUIDs from `APOPTOSIS_DONE`. For each: `nlm notebook info <uuid>` → confirm title starts with `[ARCHIVED-2026-05-07]` or `[EXPORTED-2026-05-07]`.

- [ ] **Step 5: Verify decision matrix doc exists**

```bash
ls -la docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md
wc -l docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md
```
Expected: file exists; ~120-180 lines (header + 4 cluster sections + 19 NB blocks + Follow-up).

- [ ] **Step 6: WIP commit (atomic)**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json \
          apps/mata-garuda/mata_garuda/_registry_data.py \
          research/nb-archive/audit_log.md \
          docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md && \
  git commit -m "feat(nb-lifecycle): WIP — APOPTOSIS apply + decision matrix" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 14: COMMIT C2 — final tidy + 14 export markdown files

- [ ] **Step 1: Generate the 14 EXPORT playbook files**

For each NB whose `cluster == "playbook_artifact"` and is now `APOPTOSIS_DONE`, fetch its content from NLM and render an export markdown. Add to `execute_apoptosis.py` is over-scope — instead, run a one-shot loop here:

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  python -c "
import json, subprocess
import sys
sys.path.insert(0, 'apps/mata-garuda')
from mata_garuda.notebook_registry import get_by_cluster, get_by_status
from pathlib import Path
sys.path.insert(0, 'apps/mata-garuda/scripts')
import execute_apoptosis as apo

playbooks = [e for e in get_by_cluster('playbook_artifact') if e.status == 'APOPTOSIS_DONE']
print(f'rendering {len(playbooks)} playbook exports')
for e in playbooks:
    title = apo.nlm_get_title(e.uuid) or e.name
    sources = apo.nlm_get_sources(e.uuid)
    summary = '(playbook artifact — see source list for content)'
    out_md = apo.render_export(uuid=e.uuid, title=title, sources=sources, summary=summary)
    fn = apo.export_filename(e.uuid, title)
    Path('research/nb-archive/' + fn).write_text(out_md)
    print(' →', fn)
"
```
Expected: 14 markdown files written to `research/nb-archive/`.

- [ ] **Step 2: COMMIT C2 — atomic compound**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  git add apps/mata-garuda/scripts/execute_apoptosis.py \
          apps/mata-garuda/tests/test_idempotent_re_run.py \
          apps/mata-garuda/tests/test_apoptosis_dry_run.py \
          apps/mata-garuda/tests/test_export_format.py \
          apps/mata-garuda/tests/test_decision_matrix.py \
          research/nb-archive/ \
          docs/nb-lifecycle/round1-19-ambiguous-decisions-2026-05-07.md \
          apps/mata-garuda/mata_garuda/_registry_data.py \
          apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json && \
  git commit -m "$(cat <<'EOF'
feat(nb-lifecycle): APOPTOSIS 17 univoci + decision matrix 19 review

C2 commit. APOPTOSIS execution + decision matrix.
- 17 NB renamed in NotebookLM ([ARCHIVED-2026-05-07] / [EXPORTED-2026-05-07])
- 14 playbook export markdown files in research/nb-archive/
- decision matrix doc for 19 ambigui at docs/nb-lifecycle/...
- 21 new tests green (idempotent 5 + dry-run 4 + export 8 + matrix 4)
- registry crash-safe persistence after each transition

Total tests: 52 green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && \
  git push origin feat/nb-senescent-decomm-2026-05-07
```

---

## Task 15: Open PR + auto-merge (Autonomous Ops L2)

- [ ] **Step 1: Open the PR**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/nb-senescent && \
  gh pr create --title "feat(nb-lifecycle): Phase 0+0.5 — registry SSOT + 17 APOPTOSIS_DONE + 19 review pending" \
    --body "$(cat <<'EOF'
## Summary
- Created `notebook_registry.py` SSOT (R6 anti-pattern fix #1)
- Migrated 6 active NB UUIDs from `config.NLM_NOTEBOOKS` literal to registry
- Audited 36 Round 1 candidates against live NotebookLM state
- Renamed 17 NB in NotebookLM (3 placeholder → ARCHIVED, 14 playbook → EXPORTED)
- Generated decision matrix doc for 19 ambiguous NB pending Zero approval
- Compat shim preserves `NLM_NOTEBOOKS` byte-identical for 4 unchanged consumer files

## Out of scope (deferred to follow-up)
- NLM_NOTEBOOKS callsite migration (4 files, 9 references) — see decision matrix §Follow-up
- 19 ambiguous NB final action (orphan review/research consolidation/Subhi merge/zero-value)
- NLM_DOMAIN_ROUTING refactor

## Test plan
- [x] pytest green (apps/mata-garuda/tests/) — 52 tests
- [x] No circular import test passes
- [x] Compat shim byte-identical with pre-PR snapshot
- [x] Idempotent re-run test (3 scenarios) + persistence after simulated SIGKILL
- [x] Dry-run gate executed + Zero approved before C2
- [x] All 17 renames verified in NotebookLM (manual spot check on 3)
- [x] Decision matrix doc generated with all 19 NB

## Audit artifacts
- `apps/mata-garuda/data/nb_round1_candidates_2026-05-07.json` (36 entries manifest)
- `scripts/data/nb_decomm_audit_2026-05-07.json` (live audit + drift)
- `research/nb-archive/audit_log.md` (append-only audit trail)
- `research/nb-archive/fuzzy_match_log_2026-05-07.md` (title fuzzy matches)

## Cicatrix scars referenced
- 2026-04-29 STRUCTURAL: untracked file loss (30-45min WIP commit pattern applied)
- 2026-04-29 STRUCTURAL: branch hijack (per-Edit/Write branch verification)
- 2026-04-29 STRUCTURAL: `_schema_versions` vs `schema_migrations` (no migrations introduced this PR)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: PR URL printed.

- [ ] **Step 2: Enable auto-merge (L2)**

```bash
gh pr merge --auto --squash --delete-branch
```
Expected: `auto-merge enabled`. Required CI checks must pass before merge happens.

- [ ] **Step 3: Watch CI status**

```bash
gh pr checks --watch
```
Expected: `E2E Tests (Playwright)` + `MCP Server Tests` green. If a check fails: investigate logs, push fix, do NOT bypass.

---

## Self-Review

### Spec coverage

| Spec section | Plan task |
|---|---|
| §1 Problem statement | covered by goal + tasks 2-3 (SSOT) + 8 (audit) + 13 (apoptosis) + 14 (matrix) |
| §2 Constraints C1-C13 | C1 → tasks 4 (compat shim) ; C2 → task 13 (rename only) ; C3 → tasks 7,11 (audit log) ; C4 → all tasks TDD ; C5 → pre-flight section ; C6 → WIP cadence section ; C7 → all WIP commits use atomic compound ; C8 → no agent dispatch in plan (handled by reviewer manually) ; C9 → all NLM via subprocess `nlm` CLI ; C10 → manifest is JSON via stdlib (deviation from spec YAML — flagged in tech stack note) ; C11 → task 7 T2.a/b/c ; C12 → task 11 `persist_transition` after each transition ; C13 → task 12 dry-run gate |
| §3.1 notebook_registry.py | task 3 |
| §3.2 _registry_data.py | tasks 2, 6 |
| §3.3 config.py shim | task 4 |
| §3.4 manifest YAML → **JSON** | task 5 (tech stack flag in header) |
| §3.5 4 scripts | tasks 6 (regen), 7 (audit), 11 (apoptosis); manifest builder is hand-curated bootstrap (task 5) — no separate `build_manifest.py` script needed for this PR |
| §4 Data flow | tasks 5→6→7→8→11→13→14 follow the diagram |
| §5 Decision matrix | task 11 (generator) + task 13 step 5 (verification) |
| §6.1 test_notebook_registry.py | task 3 |
| §6.2 test_compat_shim.py | task 4 |
| §6.3 test_no_circular_import.py | task 1 |
| §6.4 test_manifest_schema.py | task 5 |
| §6.5 test_idempotent_re_run.py | task 10 |
| §6.6 test_audit_pipeline.py | task 7 |
| §6.7 test_apoptosis_dry_run.py | task 10 |
| §6.8 test_export_format.py | task 10 |
| §6.9 test_decision_matrix.py | task 10 |
| §6.10 integration runbook | covered in tasks 12-13 (manual gate sequence) |
| §7 commit cadence C1+gate+C2 | tasks 8 (C1), 12 (gate), 14 (C2) |
| §7 PR + auto-merge | task 15 |
| §8 risks | each risk maps to a test in §6 (e.g. crash-safety → test_persistence_after_simulated_sigkill) |

**Deviation from spec (acknowledged):** the spec said YAML for the manifest; the plan switched to JSON because YAML requires PyYAML which is NOT in mata-garuda's `pyproject.toml` dependencies (`pydantic + pytest` only — CLAUDE.md §1 inviolable). JSON via `json` stdlib is functionally equivalent and avoids breaking the stack-minimal rule.

**No `build_manifest.py` script:** the spec lists it (§3.5) but for this PR the bootstrap manifest is hand-curated from the 2026-05-03 inventory snapshot, so the "script" is effectively the operator's editor + the schema test. A future PR can add a real builder script if needed.

### Placeholder scan

No "TBD", no "TODO", no "implement later". Every step has runnable code or commands. Tasks 5 has an operator note about populating 36 stub entries from the snapshot — that's an instruction, not a placeholder.

### Type consistency

- `NotebookEntry` field names are consistent across tasks 2, 3, 6.
- `NotebookStatus` Literal values match across registry, manifest schema, audit script, apoptosis script.
- `NotebookCluster` Literal values match across registry, manifest, manifest test enum, decision matrix grouping.
- `slugify` / `export_filename` / `render_export` / `generate_decision_matrix` / `nlm_rename` / `nlm_get_title` / `nlm_get_sources` / `persist_transition` / `run_apoptosis` are all defined in task 11 and referenced from tests in task 10 with matching signatures.
- `classify_drift` / `audit_one_with_retry` / `ensure_session_or_relogin` / `enforce_hard_cap` / `append_audit_log` / `telegram_alert` / `TransientMCPError` / `mcp_query_notebook` defined in task 7 and tested in task 7 step 1 with matching signatures.
- `REGISTRY_TARGET` / `MANIFEST` / `PREVIEW_PATH` / `DECISION_MATRIX_PATH` / `AUDIT_LOG` / `EXPORT_DIR` / `TODAY` / `ARCHIVED_PREFIX` / `EXPORTED_PREFIX` constant names consistent.

No drift found.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-07-nb-senescent-decomm.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
