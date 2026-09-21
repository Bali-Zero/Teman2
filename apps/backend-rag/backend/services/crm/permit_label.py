"""Permit label resolver — turns a generic `documents.document_type` (often
just "visa") plus whatever Gemini OCR already extracted into
`documents.ocr_extracted_data` into the precise permit label the
client-detail UI needs.

Why this exists: 1,201 documents carry the generic `document_type = "visa"`
(measured 2026-09-21, `nuzantara-rag` prod), and 439 of those already have
`ocr_extracted_data->raw_response->>'visa_type'` with a precise label such as
"KITAP (ELECTRONIC PERMANENT STAY PERMIT)", "VISIT STAY PERMIT" or
"Visa Tinggal Terbatas (E23)" — the storage column just never surfaced it.
This module does NOT change how `document_type` is stored (other readers
filter on its current values); it derives a display-only label at READ time.

Owner correction (2026-09-21): the precise label is NOT just the family
(KITAP / KITAS / Visit Stay Permit) — it must lead with the visa INDEX and
its OFFICIAL name from the `visa_types` catalogue table, e.g.
"D12 — Pre-Investment (Multiple Entry)" or "E23 — Working KITAS". The family
label (`KITAS / ITAS — Limited Stay Permit`, ...) becomes secondary, and is
the primary fallback only when no index can be derived at all.

Pure function, no I/O, no DB — every family/keyword pairing below is grounded
in production `ocr_extracted_data->raw_response->>'visa_type'` and
`document_type` values actually observed (measured, not invented). Unknown
input resolves to `None` so the caller can fall back to the raw text it
already showed — never guess a family or an index we have no evidence for.
The optional `catalogue` mapping (UPPER code -> official name) is supplied
by the caller (a single `visa_types` query per request) — this module never
queries the database itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
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

# document_type values too generic to carry their own signal — for these we
# trust the OCR-extracted `visa_type` text over the stored column.
_GENERIC_DOCUMENT_TYPES = {
    "visa",
    "misc_document",
    "other",
    "document",
    "immigration_document",
}


def _family_label(family: str) -> str:
    code = _FAMILY_CODE[family]
    label = _FAMILY_LABEL[family]
    # FAMILY_EVISA's code and label are the same string ("e-Visa") — don't
    # double it into "e-Visa — e-Visa".
    return code if code == label else f"{code} — {label}"


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


# ── Index parsing ───────────────────────────────────────────────────────────
# Prod OCR `visa_type` strings carry a visa index in two shapes: bare
# ("D12", "E28A") or fused with the follow-on stay-permit sub-index
# ("C12B14", "E232C11", "E33G2C12" — the pattern is CODE + "2" + LETTER +
# 0-2 digits, e.g. "2B14"). We parse every alphanumeric TOKEN in the text
# (never a substring of a longer token) against:
#   CODE = [A-E]\d{1,2}[A-Z]?
#   STAY = 2[A-Z]\d{0,2}
# and accept a token only if CODE (+ optional STAY) consumes it exactly.
# Ambiguous tokens (e.g. "C12B" splits into CODE=C1+STAY=2B, or CODE=C12B
# alone) are resolved by preferring the split whose CODE is in the supplied
# catalogue; among those, the longest CODE; with no catalogue match at all,
# the longest-CODE split still wins (never invent which one is "real").
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STAY_RE = re.compile(r"2[A-Z]\d{0,2}")


def _parse_index_token(token: str) -> list[tuple[str, str | None]]:
    """All valid (code, stay) full-length parses of one uppercased token."""
    if not token or token[0] not in "ABCDE":
        return []

    candidates: list[tuple[str, str | None]] = []
    for digit_len in (2, 1):
        if len(token) < 1 + digit_len:
            continue
        digits = token[1 : 1 + digit_len]
        if not digits.isdigit():
            continue
        rest = token[1 + digit_len :]

        # Without the optional trailing letter: CODE = letter + digits.
        code_no_letter = token[: 1 + digit_len]
        if rest == "":
            candidates.append((code_no_letter, None))
        elif _STAY_RE.fullmatch(rest):
            candidates.append((code_no_letter, rest))

        # With the optional trailing letter folded into CODE.
        if rest and rest[0].isalpha():
            code_with_letter = code_no_letter + rest[0]
            remainder = rest[1:]
            if remainder == "":
                candidates.append((code_with_letter, None))
            elif _STAY_RE.fullmatch(remainder):
                candidates.append((code_with_letter, remainder))

    return candidates


def _best_candidate(
    candidates: list[tuple[str, str | None]], catalogue: Mapping[str, str]
) -> tuple[str, str | None] | None:
    if not candidates:
        return None
    in_catalogue = [c for c in candidates if c[0] in catalogue]
    pool = in_catalogue or candidates
    return max(pool, key=lambda c: len(c[0]))


def _extract_index(text: str, catalogue: Mapping[str, str]) -> tuple[str, str | None] | None:
    if not text:
        return None
    for token in _TOKEN_RE.findall(text.upper()):
        best = _best_candidate(_parse_index_token(token), catalogue)
        if best:
            return best
    return None


_CODE_PREFIX_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _strip_catalogue_prefix(name: str, code: str) -> str:
    """Strip a leading "{code} - "/"{code} – "/"{code} — " from a catalogue
    name — most rows repeat the code that way, a minority (e.g. E28D) don't."""
    pattern = _CODE_PREFIX_RE_CACHE.get(code)
    if pattern is None:
        pattern = re.compile(r"^" + re.escape(code) + r"\s*[-–—]\s*")
        _CODE_PREFIX_RE_CACHE[code] = pattern
    return pattern.sub("", name, count=1)


class PermitLabel(TypedDict):
    permit_family: str
    permit_code: str
    permit_label: str
    permit_family_label: str | None
    permit_stay_index: str | None
    permit_number: str | None
    permit_sponsor: str | None


def resolve_permit_label(
    document_type: str | None,
    ocr_extracted_data: Any | None,
    catalogue: Mapping[str, str] | None = None,
) -> PermitLabel | None:
    """Resolve a precise permit label for one document.

    `catalogue` is an UPPER `code` -> official `name` mapping from the
    `visa_types` table (caller's single query per request); `None` still
    parses an index (code-only labels, never a DB round-trip here).

    Returns `None` when neither a family keyword nor a visa index can be
    derived from either `document_type` or the OCR `visa_type` text — the
    caller keeps showing whatever text it showed before (never invent one).

    `ocr_extracted_data` is a JSONB column round-tripped through
    `from_jsonb()` — always a dict in practice, but a malformed write
    upstream could leave it (or its `raw_response` key) as a list/str/etc.
    Treated as "no OCR" rather than raised: a bad JSONB value on ONE
    document must never break the whole client profile.
    """
    if not isinstance(ocr_extracted_data, dict):
        ocr_extracted_data = None
    raw_response = (ocr_extracted_data or {}).get("raw_response")
    if not isinstance(raw_response, dict):
        raw_response = {}
    ocr_visa_type = str(raw_response.get("visa_type") or "").strip()
    dt = str(document_type or "").strip()
    dt_probe = dt.replace("_", " ")
    dt_norm = dt.strip().lower()
    cat = catalogue or {}

    # A specific (non-generic) document_type is trusted on its own; OCR text
    # is consulted for family/index ONLY when document_type itself carries
    # no signal (the generic buckets) OR it already classifies as a permit
    # family. A specific, NON-permit document_type (an RPTKA/IMTA approval,
    # an address slip, a travel itinerary, ...) must never borrow a family
    # or an index from unrelated OCR text sitting on the same row — measured
    # prod bug: those documents' OCR text sometimes quotes the client's own
    # KITAS/visa index (e.g. the sponsor's permit number on an RPTKA form).
    is_generic = dt_norm in _GENERIC_DOCUMENT_TYPES
    dt_family = _classify(dt_probe)
    trust_ocr = is_generic or dt_family is not None

    if is_generic:
        family = _classify(ocr_visa_type) or dt_family
    else:
        family = dt_family

    if trust_ocr:
        index = _extract_index(ocr_visa_type, cat) or _extract_index(dt_probe, cat)
    else:
        index = _extract_index(dt_probe, cat)

    if family is None and index is None:
        return None

    # An index with no family keyword still surfaces as an e-Visa bucket —
    # today's behaviour, kept: most bare-index OCR text ("D12") belongs to
    # the pre-arrival e-Visa family and no other keyword ever fires for it.
    effective_family = family if family is not None else FAMILY_EVISA

    permit_family_label = _family_label(family) if family is not None else None

    if index is not None:
        code, stay = index
        catalogue_name = cat.get(code)
        if catalogue_name:
            name = _strip_catalogue_prefix(catalogue_name, code)
            primary_label = f"{code} — {name}"
        else:
            primary_label = code
        permit_code = code
        permit_stay_index = stay
    else:
        permit_code = _FAMILY_CODE[effective_family]
        primary_label = permit_family_label
        permit_stay_index = None

    permit_number = raw_response.get("visa_number")
    permit_sponsor = raw_response.get("sponsor")

    return PermitLabel(
        permit_family=effective_family,
        permit_code=permit_code,
        permit_label=primary_label,
        permit_family_label=permit_family_label,
        permit_stay_index=permit_stay_index,
        permit_number=str(permit_number).strip() if permit_number else None,
        permit_sponsor=str(permit_sponsor).strip() if permit_sponsor else None,
    )
