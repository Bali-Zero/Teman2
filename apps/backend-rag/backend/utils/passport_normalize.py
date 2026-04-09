"""Passport field normalization utilities.

Converts raw MRZ/OCR output into clean, human-readable form data
for the Nuzantara CRM passport intake flow.
"""

from __future__ import annotations

import re
from datetime import datetime


# ---------------------------------------------------------------------------
# NATIONALITY_MAP
# Keys: ISO3 codes, full country names (upper), adjective forms, and common
# variants (including Indonesian-language terms).
# Values: the standard adjective form matching the frontend dropdown.
# ---------------------------------------------------------------------------

_NATIONALITIES: list[tuple[str, list[str]]] = [
    ("Australian",   ["AUS", "AUSTRALIA"]),
    ("American",     ["USA", "UNITED STATES", "UNITED STATES OF AMERICA", "US", "AMERIKA"]),
    ("British",      ["GBR", "UNITED KINGDOM", "GREAT BRITAIN", "UK", "INGGRIS"]),
    ("Canadian",     ["CAN", "CANADA", "KANADA"]),
    ("Chinese",      ["CHN", "CHINA", "TIONGKOK", "CINA"]),
    ("Dutch",        ["NLD", "NETHERLANDS", "HOLLAND", "BELANDA"]),
    ("French",       ["FRA", "FRANCE", "PERANCIS", "PRANCIS"]),
    ("German",       ["DEU", "GERMANY", "JERMAN", "D"]),
    ("Indian",       ["IND", "INDIA"]),
    ("Indonesian",   ["IDN", "INDONESIA"]),
    ("Italian",      ["ITA", "ITALY", "ITALIA"]),
    ("Japanese",     ["JPN", "JAPAN", "JEPANG"]),
    ("Korean",       ["KOR", "KOREA", "SOUTH KOREA", "REPUBLIC OF KOREA"]),
    ("Malaysian",    ["MYS", "MALAYSIA"]),
    ("Russian",      ["RUS", "RUSSIA", "RUSSIAN FEDERATION", "RUSIA"]),
    ("Singaporean",  ["SGP", "SINGAPORE", "SINGAPURA"]),
    ("Spanish",      ["ESP", "SPAIN", "SPANYOL"]),
    ("Swedish",      ["SWE", "SWEDEN", "SWEDIA"]),
    ("Swiss",        ["CHE", "SWITZERLAND", "SWISS"]),
    ("Ukrainian",    ["UKR", "UKRAINE", "UKRAINA"]),
]

NATIONALITY_MAP: dict[str, str] = {}
for _adj, _keys in _NATIONALITIES:
    # Map the adjective form itself (upper) so "Russian" -> "Russian" works
    NATIONALITY_MAP[_adj.upper()] = _adj
    for _k in _keys:
        NATIONALITY_MAP[_k.upper()] = _adj


# ---------------------------------------------------------------------------
# Month abbreviation / full-name lookup for date parsing
# ---------------------------------------------------------------------------

_MONTH_NAMES: dict[str, int] = {
    "JAN": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5,
    "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}


# ===== PUBLIC API ==========================================================


def title_case_name(name: str | None) -> str | None:
    """Convert MRZ uppercase name to Title Case.

    Handles:
    - ``<<`` separators  (KIRMASOV<<MAKSIM -> Kirmasov Maksim)
    - Apostrophes        (O'BRIAN -> O'Brian)
    - Hyphens            (JEAN-PIERRE -> Jean-Pierre)

    Returns ``None`` for ``None`` or empty input.
    """
    if not name:
        return None

    # Replace MRZ chevron separators with spaces
    cleaned = name.replace("<<", " ").replace("<", " ")
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return None

    def _title_part(part: str) -> str:
        """Title-case a single space-delimited token, respecting hyphens and apostrophes."""
        # Split on hyphens
        segments = part.split("-")
        titled_segments: list[str] = []
        for seg in segments:
            # Split on apostrophes
            apo_parts = seg.split("'")
            titled_segments.append(
                "'".join(p.capitalize() for p in apo_parts)
            )
        return "-".join(titled_segments)

    return " ".join(_title_part(p) for p in cleaned.split())


def normalize_nationality(nationality: str | None) -> str | None:
    """Normalize a nationality string to the standard adjective form.

    Accepts ISO-3166 alpha-3 codes, full country names (any case), and
    common variants (including Indonesian-language terms).

    Falls back to Title Case for unknown values.
    Returns ``None`` for ``None`` or empty input.
    """
    if not nationality:
        return None

    key = nationality.strip().upper()
    if not key:
        return None

    result = NATIONALITY_MAP.get(key)
    if result:
        return result

    # Fallback: title-case the raw input
    return nationality.strip().title()


def normalize_date(date_str: str | None) -> str | None:
    """Normalize a date string to ISO YYYY-MM-DD format.

    Supported formats:
    - ISO 8601:   ``YYYY-MM-DD`` (pass-through)
    - MRZ 6-digit: ``YYMMDD``  (>50 -> 19xx, <=50 -> 20xx)
    - Textual:    ``DD MON YYYY`` or ``DD MONTH YYYY``

    Returns ``None`` for unparseable or ``None`` input.
    """
    if not date_str:
        return None

    s = date_str.strip()

    # --- ISO 8601: YYYY-MM-DD ---
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            datetime(y, m, d)
            return s
        except ValueError:
            return None

    # --- MRZ 6-digit: YYMMDD ---
    mrz_match = re.fullmatch(r"(\d{2})(\d{2})(\d{2})", s)
    if mrz_match:
        yy, mm, dd = int(mrz_match.group(1)), int(mrz_match.group(2)), int(mrz_match.group(3))
        year = 1900 + yy if yy > 50 else 2000 + yy
        try:
            datetime(year, mm, dd)
            return f"{year:04d}-{mm:02d}-{dd:02d}"
        except ValueError:
            return None

    # --- Textual: "DD MON YYYY" / "DD MONTH YYYY" ---
    text_match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if text_match:
        dd = int(text_match.group(1))
        month_str = text_match.group(2).upper()
        yyyy = int(text_match.group(3))
        mm = _MONTH_NAMES.get(month_str)
        if mm is None:
            return None
        try:
            datetime(yyyy, mm, dd)
            return f"{yyyy:04d}-{mm:02d}-{dd:02d}"
        except ValueError:
            return None

    return None
