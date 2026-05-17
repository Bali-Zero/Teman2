"""
Legal domain configuration: NB target mapping and notebook IDs.
Modify NB_TARGET_MAP and NB_NOTEBOOK_IDS here — no deploy required.
"""

import os
from typing import Final

# Maps tipo -> default NB target. Override with nb_target param in request.
NB_TARGET_MAP: Final[dict[str, str]] = {
    "PP": "NB-3",
    "Perpres": "NB-3",
    "Permen": "NB-3",
    "SKB": "NB-3",
    "PMK": "NB-4",
    "SE": "NB-4",
}

# NotebookLM notebook UUIDs — update here when notebooks change
NB_NOTEBOOK_IDS: Final[dict[str, str]] = {
    "NB-2": "271c7159-0c32-49a1-bda8-803c8e0993a6",  # Immigration
    "NB-3": "045f3cdb-ef62-488c-90ba-82594928b671",  # Company Setup
    "NB-4": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # Tax
    "NB-5": "93314ad3-177e-4d2f-956b-fe4be3e47697",  # Property
    "NB-6": "7fbf37ed-e290-491a-98f5-677d6371ad62",  # Operations
}

# Valid tipo enum values
VALID_TIPO: Final[frozenset[str]] = frozenset(NB_TARGET_MAP.keys())

# Valid nb_target values
VALID_NB_TARGETS: Final[frozenset[str]] = frozenset(NB_NOTEBOOK_IDS.keys())

# Google Sheet ID for legal catalog — set via LEGAL_CATALOG_SHEET_ID env var
LEGAL_CATALOG_SHEET_ID: str = os.getenv("LEGAL_CATALOG_SHEET_ID", "")

# Drive folder name for legal documents (relative to team root)
DRIVE_LEGAL_ROOT: Final[str] = "PERATURAN"


def resolve_nb_target(tipo: str, nb_target_override: str | None) -> str:
    """Return NB target: use override if valid, else auto-map from tipo."""
    if nb_target_override and nb_target_override in VALID_NB_TARGETS:
        return nb_target_override
    return NB_TARGET_MAP.get(tipo, "NB-3")


def resolve_nb_notebook_id(nb_target: str) -> str | None:
    """Return NLM notebook UUID for an NB target key."""
    return NB_NOTEBOOK_IDS.get(nb_target)
