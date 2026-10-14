"""Official document checklist per product, from a committed source-stamped catalogue.

The catalogue is a snapshot of the imigrasi.go.id per-code pages (canonical URL, fetch time and
content fingerprint recorded per product). A product in the catalogue shows AVAILABLE with the
page's own document list; every other product keeps the explicit UNKNOWN, never a guessed list.
The catalogue lists documents only: it adds no eligibility gate.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

__all__ = ["CatalogEntry", "catalogue_codes", "documentation_for"]

_SNAPSHOT = (
    Path(__file__).resolve().parents[2] / "data" / "bali_zero_documentation_catalog_2026.json"
)
AVAILABLE_REASON_CODE = "OFFICIAL_IMIGRASI_DOCUMENT_CHECKLIST"
UNKNOWN_REASON_CODE = "DOCUMENTATION_CATALOG_NOT_VERIFIED"

CatalogEntry = tuple[tuple[dict[str, str], ...], tuple[dict[str, str], ...]]


def _items(raw: list[dict[str, str]], code: str) -> tuple[dict[str, str], ...]:
    items = []
    for row in raw:
        en, id_ = row.get("en"), row.get("id")
        if not isinstance(en, str) or not en.strip() or not isinstance(id_, str) or not id_.strip():
            raise ValueError(f"documentation item for {code} needs both en and id: {row!r}")
        items.append({"en": en, "id": id_})
    return tuple(items)


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, CatalogEntry]:
    raw = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    entries: dict[str, CatalogEntry] = {}
    for code, row in raw["products"].items():
        requirements = _items(row["requirements"], code)
        checklist = _items(row["checklist"], code)
        if not requirements and not checklist:
            raise ValueError(f"catalogue entry for {code} lists no document")
        entries[code] = (requirements, checklist)
    return entries


def catalogue_codes() -> frozenset[str]:
    return frozenset(_catalogue())


def documentation_for(product_code: str, observed_at: str) -> dict[str, object]:
    """The B.2 ``documentation`` block for one product."""

    entry = _catalogue().get(product_code)
    if entry is None:
        return {
            "status": "UNKNOWN",
            "reason_code": UNKNOWN_REASON_CODE,
            "observed_at": observed_at,
            "requirements": [],
            "checklist": [],
        }
    return {
        "status": "AVAILABLE",
        "reason_code": AVAILABLE_REASON_CODE,
        "observed_at": observed_at,
        "requirements": [dict(item) for item in entry[0]],
        "checklist": [dict(item) for item in entry[1]],
    }
