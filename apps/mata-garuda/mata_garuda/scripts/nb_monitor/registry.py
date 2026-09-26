"""NB registry loader.

Reads the bootstrap JSON file at ~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json
and returns a list of NotebookEntry dataclasses. ADR-012 documents the
migration plan to apps/mata-garuda/mata_garuda/notebook_registry.py post-FASE-2 merge.

Names are REDACTED here, at the one place every consumer reads them from. The weekly
report, the Telegram alerts and the log lines all print `NotebookEntry.name`, and some
NotebookLM titles name a client (Builder Contract §4). Redaction is the repo's policy file
(`agent-library/config/redaction-rules.yaml`, `nb_titles` + pass1-3) through
`scripts/_redact_pii.py`. If that cannot load, the title is WITHHELD, never printed raw.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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


# registry.py -> nb_monitor -> scripts -> mata_garuda -> mata-garuda -> apps -> repo root
_REDACT_PII_PATH = Path(__file__).resolve().parents[5] / "scripts" / "_redact_pii.py"
_redactor: Any = None
_redactor_error: str | None = None


def _title_redactor() -> Any:
    """Load the repo redactor once; remember a failure instead of retrying per title."""
    global _redactor, _redactor_error
    if _redactor is None and _redactor_error is None:
        try:
            spec = importlib.util.spec_from_file_location("nuzantara_redact_pii", _REDACT_PII_PATH)
            if spec is None or spec.loader is None:
                raise ImportError(f"no loader for {_REDACT_PII_PATH}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module  # dataclasses resolve their module by name
            spec.loader.exec_module(module)
            _redactor = module.Redactor.load_static()
        except Exception as e:  # noqa: BLE001 — any failure must end in WITHHELD, not raw
            _redactor_error = f"{type(e).__name__}: {e}"
            logger.error("nb_monitor: title redactor unavailable, titles withheld: %s", _redactor_error)
    return _redactor


def display_name(name: str, uuid: str) -> str:
    """The notebook title as it may appear in a report, an alert or a log line."""
    redactor = _title_redactor()
    if redactor is None:
        return f"[NB-TITLE-WITHHELD:{uuid[:8]}]"
    try:
        return redactor.redact_notebook_title(name, uuid)
    except Exception as e:  # noqa: BLE001 — fail closed per title, keep the run alive
        logger.error("nb_monitor: redaction failed for %s: %s", uuid[:8], type(e).__name__)
        return f"[NB-TITLE-WITHHELD:{uuid[:8]}]"


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
            name=display_name(nb["name"], nb["uuid"]),
            family=nb["family"],
            lifecycle_stage=nb["lifecycle_stage"],
            active_routing=bool(nb["active_routing"]),
            first_audited=nb["first_audited"],
            last_audited=nb.get("last_audited"),
            round2_classification=nb.get("round2_classification"),
        )
