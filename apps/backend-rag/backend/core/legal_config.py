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
    "NB-2": "cff93ab0-813a-42f2-a8de-36987e724271",  # Immigration
    "NB-3": "933509f9-1561-403d-bd44-4a7a67a36df2",  # Company Setup
    "NB-4": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # Tax
    "NB-5": "d9438180-5e63-4e2a-a473-6061101f6a8d",  # Property
    "NB-6": "85207af3-352f-4554-8d2a-18f42cc541ba",  # Operations
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
