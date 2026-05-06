"""NB registry loader.

Reads the bootstrap JSON file at ~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json
and returns a list of NotebookEntry dataclasses. ADR-006 documents the
migration plan to apps/mata-garuda/mata_garuda/notebook_registry.py post-FASE-2 merge.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
REQUIRED_FIELDS = (
    "uuid",
    "name",
    "family",
    "lifecycle_stage",
    "active_routing",
    "first_audited",
)


class RegistryLoadError(Exception):
    """Raised when the bootstrap registry cannot be parsed."""


@dataclass(frozen=True)
class NotebookEntry:
    uuid: str
    name: str
    family: str  # INTEL | MATA-GARUDA | CORE | RESEARCH | SUBHI | META
    lifecycle_stage: str  # DM | TAC | SENESCENT | KILL_PENDING | APOPTOSIS_DONE | ORPHAN_REVIEW
    active_routing: bool
    first_audited: str  # ISO date
    last_audited: str | None = None
    round2_classification: str | None = None


def load_registry(path: Path) -> list[NotebookEntry]:
    """Load the bootstrap JSON file and return a list of NotebookEntry."""
    if not path.exists():
        raise RegistryLoadError(f"registry file not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise RegistryLoadError(f"invalid JSON in {path}: {e}") from e

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise RegistryLoadError(
            f"unsupported schema_version {schema_version!r} (expected {SCHEMA_VERSION})"
        )

    notebooks = data.get("notebooks", [])
    return list(_parse_entries(notebooks, source=str(path)))


def _parse_entries(notebooks: Iterable[dict], source: str) -> Iterable[NotebookEntry]:
    for idx, nb in enumerate(notebooks):
        for field in REQUIRED_FIELDS:
            if field not in nb:
                raise RegistryLoadError(
                    f"{source}: notebooks[{idx}] missing required field '{field}'"
                )
        yield NotebookEntry(
            uuid=nb["uuid"],
            name=nb["name"],
            family=nb["family"],
            lifecycle_stage=nb["lifecycle_stage"],
            active_routing=bool(nb["active_routing"]),
            first_audited=nb["first_audited"],
            last_audited=nb.get("last_audited"),
            round2_classification=nb.get("round2_classification"),
        )
