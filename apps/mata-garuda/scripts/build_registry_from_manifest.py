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


def _py_repr(v: object) -> str:
    """Render a value as a valid Python literal (not JSON).

    - str  → double-quoted JSON string (handles non-ASCII safely)
    - None → None
    - list → [item, ...] with items repr'd recursively
    - anything else → repr()
    """
    if v is None:
        return "None"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        items = ", ".join(_py_repr(i) for i in v)
        return f"[{items}]"
    return repr(v)


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
            body += f"        {json.dumps(k)}: {_py_repr(v)},\n"
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
