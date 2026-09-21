"""Permit label resolver — turns a generic `documents.document_type` (often
just "visa") plus whatever Gemini OCR already extracted into
`documents.ocr_extracted_data` into the precise permit family/label the
client-detail UI needs.

Why this exists: 1,201 documents carry the generic `document_type = "visa"`
(measured 2026-09-21, `nuzantara-rag` prod), and 439 of those already have
`ocr_extracted_data->raw_response->>'visa_type'` with a precise label such as
"KITAP (ELECTRONIC PERMANENT STAY PERMIT)", "VISIT STAY PERMIT" or
"Visa Tinggal Terbatas (E23)" — the storage column just never surfaced it.
This module does NOT change how `document_type` is stored (other readers
filter on its current values); it derives a display-only label at READ time.

Pure function, no I/O, no DB — every family/keyword pairing below is grounded
in production `ocr_extracted_data->raw_response->>'visa_type'` and
`document_type` values actually observed (measured, not invented). Unknown
input resolves to `None` so the caller can fall back to the raw text it
already showed — never guess a family we have no evidence for.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

# ── Families ────────────────────────────────────────────────────────────────
# Mirrors the "visa family" vocabulary already used elsewhere in this repo
# (backend/services/crm/documents.py::CATEGORIZATION_RULES["immigration"],
# apps/mouth ImmigrationTab.tsx::isVisaFamilyDocument) without importing
# across those boundaries — this module has none of the upload-time/DB
# concerns those two carry, only the read-time label.

FAMILY_KITAP = "kitap"
FAMILY_KITAS = "kitas"
FAMILY_ITK = "itk"
FAMILY_MERP = "merp"
FAMILY_EVISA = "evisa"

_FAMILY_LABEL: dict[str, str] = {
    FAMILY_KITAP: "Permanent Stay Permit",
    FAMILY_KITAS: "Limited Stay Permit",
    FAMILY_ITK: "Visit Stay Permit",
    FAMILY_MERP: "Multiple Exit Re-entry Permit",
    FAMILY_EVISA: "e-Visa",
}

_FAMILY_CODE: dict[str, str] = {
    FAMILY_KITAP: "KITAP / ITAP",
    FAMILY_KITAS: "KITAS / ITAS",
    FAMILY_ITK: "ITK",
    FAMILY_MERP: "MERP",
    FAMILY_EVISA: "e-Visa",
}

# Visa-index codes this app already knows about (visa_check/catalogue.py's
# `VisaType` enum, single source of truth for the pre-arrival index). Ordered
# longest-prefix-first so "E23-FREELANCE" is tried before "E23".
_INDEX_CODES: tuple[str, ...] = (
    "E23-FREELANCE",
    "E23",
    "E28A",
    "E30A",
    "E31",
    "E33E",
    "E33F",
    "E33G",
    "E33",
    "D12",
    "D2",
    "C22A",
    "C18",
    "C7A",
    "C7B",
    "C7",
    "C6",
    "C2",
    "C1",
    "B1",
)
_INDEX_CODE_RE = re.compile(
    r"(?<![A-Z0-9])(" + "|".join(re.escape(c) for c in _INDEX_CODES) + r")(?![A-Z0-9])"
)

# document_type values too generic to carry their own signal — for these we
# trust the OCR-extracted `visa_type` text over the stored column.
_GENERIC_DOCUMENT_TYPES = {
    "visa",
    "misc_document",
    "other",
    "document",
    "immigration_document",
}


def _classify(text: str) -> str | None:
    """Keyword classification of a free-text permit label into one family.

    Order matters: KITAP before KITAS (a KITAP string never contains
    "kitas"/standalone "itas", but check order still documents the intent),
    MERP before KITAS/ITK (a re-entry stamp is never a stay permit itself).
    """
    if not text:
        return None
    t = text.lower()

    if "kitap" in t or re.search(r"\bitap\b", t) or "permanent stay" in t or "tinggal tetap" in t:
        return FAMILY_KITAP

    if (
        "merp" in t
        or "re-entry" in t
        or "reentry" in t
        or "re entry" in t
        or "multiple exit" in t
        or "izin masuk kembali" in t
    ):
        return FAMILY_MERP

    if (
        "kitas" in t
        or re.search(r"\bitas\b", t)
        or "limited stay" in t
        or "residence permit" in t
        or "tinggal terbatas" in t
    ):
        return FAMILY_KITAS

    if "itk" in t or "visit stay" in t or "visit visa" in t or "izin tinggal kunjungan" in t:
        return FAMILY_ITK

    # Collapse spaces/hyphens/underscores so "e_visa"/"e-visa"/"E Visa"/
    # "evisa" all normalise to the same "evisa" token.
    compact = re.sub(r"[\s_-]", "", t)
    if "evisa" in compact or "telex" in t:
        return FAMILY_EVISA

    return None


def _extract_index_code(text: str) -> str | None:
    if not text:
        return None
    m = _INDEX_CODE_RE.search(text.upper())
    return m.group(1) if m else None


class PermitLabel(TypedDict):
    permit_family: str
    permit_code: str
    permit_label: str
    permit_number: str | None
    permit_sponsor: str | None


def resolve_permit_label(
    document_type: str | None,
    ocr_extracted_data: dict[str, Any] | None,
) -> PermitLabel | None:
    """Resolve a precise permit label for one document.

    Returns `None` when neither the stored `document_type` nor the OCR
    `visa_type` text matches a known family — the caller keeps showing
    whatever text it showed before (never invent a label).
    """
    raw_response = (ocr_extracted_data or {}).get("raw_response") or {}
    ocr_visa_type = str(raw_response.get("visa_type") or "").strip()
    dt = str(document_type or "").strip()
    dt_probe = dt.replace("_", " ")
    dt_norm = dt.strip().lower()

    # Generic buckets carry no signal of their own — OCR text is the only
    # evidence. Specific buckets (kitas/itap/itk/e_visa/telex_visa/MERP/…)
    # are trusted directly; OCR is only a fallback for those, not primary.
    if dt_norm in _GENERIC_DOCUMENT_TYPES:
        family = _classify(ocr_visa_type) or _classify(dt_probe)
    else:
        family = _classify(dt_probe) or _classify(ocr_visa_type)

    index_code: str | None = None
    if family is None:
        index_code = _extract_index_code(ocr_visa_type) or _extract_index_code(dt_probe)
        if index_code:
            family = FAMILY_EVISA

    if family is None:
        return None

    code = index_code or _FAMILY_CODE[family]
    label = _FAMILY_LABEL[family]

    permit_number = raw_response.get("visa_number")
    permit_sponsor = raw_response.get("sponsor")

    return PermitLabel(
        permit_family=family,
        permit_code=code,
        permit_label=f"{code} — {label}",
        permit_number=str(permit_number).strip() if permit_number else None,
        permit_sponsor=str(permit_sponsor).strip() if permit_sponsor else None,
    )
