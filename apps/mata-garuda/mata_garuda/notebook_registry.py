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
