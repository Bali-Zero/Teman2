"""Read-only bridge between Visa Check and `PricingService`.

Rule (CLAUDE.md Golden Rule #12): never hardcode prices. This module
asks `PricingService` for the quote matching a VisaType and returns
it to the router as a plain int (IDR), plus the source string for
the UI disclaimer.

If PricingService cannot find a quote we return `None` — the UI then
says "Let's confirm the exact fee on WhatsApp" instead of inventing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.services.pricing.pricing_service import PricingService
from backend.services.visa_check.catalogue import VisaType

logger = logging.getLogger(__name__)

# Known-None set: VisaTypes for which the pricing JSON has no entry.
# Bridge returns (None, None) for these and the UI shows
# "confirm on WhatsApp". These are intentional, not bugs.
KNOWN_NONE_VISAS: frozenset[VisaType] = frozenset({
    VisaType.C6,       # Social visit — no standalone C6 row in pricing JSON
    VisaType.E30A,     # Education — JSON lacks a student visa entry
})


# Map our VisaType codes to substrings likely to appear in the
# price JSON keys. Names reflect the JSON shape exactly (see
# backend/data/bali_zero_official_prices_2026.json). Offshore
# variants are preferred (standard fresh-applicant path).
_SEARCH_HINTS: dict[VisaType, tuple[str, ...]] = {
    VisaType.C1:             ("C1 Tourism",),
    VisaType.C2:             ("C2 Business",),
    VisaType.C6:             ("C6", "Social"),                              # known None
    VisaType.C7:             ("C7A&B Music/Art", "C7"),                     # best-effort
    VisaType.C7A:            ("C7A&B Music/Art", "C7A"),
    VisaType.C7B:            ("C7A&B Music/Art", "C7B"),
    VisaType.C18:            ("C18 Work Trial",),
    VisaType.C22A:           ("C22A&B Internship (60 Days)", "C22A&B Internship"),
    VisaType.D2:             ("D12 Business Investigation (1 Year)", "D2"),  # closest multi-entry row
    VisaType.D12:            (
        "D12 Business Investigation (1 Year)",
        "D12 Business Investigation (2 Years)",
    ),
    VisaType.E23:            ("Working KITAS (Offshore)", "Working KITAS"),
    VisaType.E23_FREELANCE:  ("Freelance E23 (Offshore)", "Freelance E23"),
    VisaType.E28A:           ("Investor KITAS 2 Years (Offshore)", "Investor KITAS"),
    VisaType.E30A:           ("Education", "Student"),                       # known None
    VisaType.E31:            (
        "Dependent 1 Year (Offshore)",
        "Spouse 1 Year (Offshore)",
        "Family",
    ),
    VisaType.E33E:           ("Retirement KITAP + MERP", "Retirement"),
    VisaType.E33F:           ("Retirement (Offshore)", "Retirement"),
    VisaType.E33G:           ("E33G Remote Worker (Offshore)", "E33G Remote Worker"),
}


def _idr_string_to_int(raw: str) -> int | None:
    """Parse '5.800.000 IDR' → 5_800_000. Returns None if unparseable."""
    if not raw:
        return None
    match = re.search(r"([\d.,]+)\s*IDR", raw)
    if not match:
        return None
    digits = re.sub(r"[.,]", "", match.group(1))
    try:
        return int(digits)
    except ValueError:
        return None


def estimate_match_cost(
    *,
    visa_type: VisaType,
    pricing: PricingService,
) -> tuple[int | None, str | None]:
    """Return (cost_idr, human_source).

    `human_source` is the price-JSON key that matched (e.g.
    "C2 Business"), used for the UI disclaimer "priced as C2 Business".
    """
    hints = _SEARCH_HINTS.get(visa_type, (visa_type.value,))
    for hint in hints:
        results = pricing.search_service(hint)
        if not isinstance(results, dict):
            continue
        services = results.get("results") or results.get("services") or results
        candidate = _best_pricing_candidate(services, hint)
        if candidate is not None:
            return candidate

    logger.warning(
        "pricing_bridge: no quote found for %s (hints=%s)",
        visa_type.value,
        hints,
    )
    return None, None


def _normalise_match_text(raw: str) -> str:
    """Normalize labels so punctuation changes do not hide exact matches."""
    return re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()


def _match_terms(raw: str) -> set[str]:
    return set(_normalise_match_text(raw).split())


def _best_pricing_candidate(
    services: Any,
    hint: str,
) -> tuple[int, str] | None:
    """Pick the strongest candidate from a broad PricingService result.

    `PricingService.search_service` intentionally returns broad keyword
    matches. For example, "E33G Remote Worker" can also match the C7 artist row
    because its description mentions "cultural workers". The bridge has a
    stricter hint from `VisaType`, so rank candidates by key/name/code before
    falling back to description-level matches.
    """
    if not isinstance(services, dict):
        return None

    candidates: list[tuple[int, int, str]] = []
    for category, items in services.items():
        if category == "contact_info":
            continue
        for key, item in _iter_candidate_items(items):
            cost = _extract_cost(item)
            if cost is None:
                continue
            name = str(item.get("name") or item.get("code") or key or hint)
            source = str(key or name)
            score = _candidate_score(hint, source, item)
            candidates.append((score, cost, source))

    if not candidates:
        return None
    _score, cost, source = max(candidates, key=lambda candidate: candidate[0])
    return cost, source


def _iter_candidate_items(items: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(items, list):
        return [
            (str(item.get("name") or item.get("code") or ""), item)
            for item in items
            if isinstance(item, dict)
        ]
    if not isinstance(items, dict):
        return []

    candidates: list[tuple[str, dict[str, Any]]] = []
    for key, item in items.items():
        if not isinstance(item, dict):
            continue
        if _extract_cost(item) is not None:
            candidates.append((str(key), item))
            continue
        for nested_key, nested_item in item.items():
            if isinstance(nested_item, dict):
                candidates.append((str(nested_key), nested_item))
    return candidates


def _candidate_score(hint: str, source: str, item: dict[str, Any]) -> int:
    label_text = _normalise_match_text(
        " ".join(
            str(value)
            for value in (
                source,
                item.get("name", ""),
                item.get("code", ""),
            )
        ),
    )
    full_text = _normalise_match_text(
        " ".join(
            str(value)
            for value in (
                label_text,
                item.get("notes", ""),
                item.get("description_en", ""),
                " ".join(item.get("legacy_names", []))
                if isinstance(item.get("legacy_names"), list)
                else "",
            )
        ),
    )
    hint_text = _normalise_match_text(hint)
    hint_terms = _match_terms(hint)
    label_terms = set(label_text.split())
    full_terms = set(full_text.split())

    score = 0
    if hint_text and hint_text in label_text:
        score += 1000
    score += 20 * len(hint_terms & label_terms)
    score += len(hint_terms & full_terms)
    return score


def _extract_cost(item: dict[str, Any]) -> int | None:
    """Try several shape possibilities in the price JSON."""
    raw = item.get("price") or item.get("price_idr")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        return _idr_string_to_int(raw)
    return None


__all__ = [
    "KNOWN_NONE_VISAS",
    "_idr_string_to_int",
    "estimate_match_cost",
]
