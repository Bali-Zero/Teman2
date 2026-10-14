"""Tests for Zero's 2026-10-14 E33F ruling on GOLDEN_ROUTES['investor_kitas_retirement']."""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.services.rag.kg_enhanced_retrieval import GoldenRoute, KGEnhancedRetrieval

REPO_ROOT = Path(__file__).resolve().parents[6]
SIGNED_PACK_PATH = (
    REPO_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-prod-029.signed.json"
)
SAVED_PAGE_DIRS = (
    REPO_ROOT / "research" / "visa" / "2026-10-14-e33-documents" / "text",
    REPO_ROOT / "research" / "visa" / "2026-10-13-organ-reattest-seq29" / "text",
)
USD_FIGURE_RE = re.compile(r"\bUSD\s+(\d[\d,]*)\b")


def _flatten_golden_route(route: GoldenRoute) -> str:
    """Flatten name, description, path, and key_conditions of a GoldenRoute into one string."""
    parts: list[str] = [
        route.name,
        route.description,
        *route.path,
        *route.key_conditions,
    ]
    return "\n".join(parts)


def _find_retirement_kitas_routes(routes: Mapping[str, GoldenRoute]) -> list[str]:
    """Return route_ids whose flattened text contains 'Retirement KITAS' (case-insensitive)."""
    offenders: list[str] = []
    for route_id, route in routes.items():
        if "retirement kitas" in _flatten_golden_route(route).lower():
            offenders.append(route_id)
    return offenders


def _check_e33f_second_home_senior_named(route: GoldenRoute) -> list[str]:
    """Return missing required substrings ('E33F', 'Second Home Senior') from a route."""
    text = _flatten_golden_route(route)
    missing: list[str] = []
    for required in ("E33F", "Second Home Senior"):
        if required not in text:
            missing.append(required)
    return missing


def _collect_payload_numbers(node: Any, out: set[int | float] | None = None) -> set[int | float]:
    """Walk the signed pack payload and collect all numeric values."""
    if out is None:
        out = set()
    if isinstance(node, dict):
        for val in node.values():
            _collect_payload_numbers(val, out)
    elif isinstance(node, list):
        for item in node:
            _collect_payload_numbers(item, out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.add(node)
    return out


def _figure_in_saved_pages(raw_figure: str) -> bool:
    """Check whether raw_figure (allowing both '3,000' and '3.000' spellings) is in saved pages."""
    comma_spelling = raw_figure
    dot_spelling = raw_figure.replace(",", ".")
    for directory in SAVED_PAGE_DIRS:
        if not directory.exists():
            continue
        for txt_file in sorted(directory.glob("*.txt")):
            content = txt_file.read_text(encoding="utf-8")
            if comma_spelling in content or dot_spelling in content:
                return True
    return False


def _find_unbacked_usd_figures(
    route: GoldenRoute,
    payload_numbers: set[int | float],
) -> list[str]:
    """Return any 'USD N' / 'USD N,NNN' figure in route not backed by pack payload or saved pages."""
    text = _flatten_golden_route(route)
    unbacked: list[str] = []
    for match in USD_FIGURE_RE.finditer(text):
        raw_figure = match.group(1)
        numeric_value = int(raw_figure.replace(",", ""))
        in_pack = numeric_value in payload_numbers
        in_pages = _figure_in_saved_pages(raw_figure)
        if not (in_pack or in_pages):
            unbacked.append(f"USD {raw_figure}")
    return unbacked


def test_no_golden_route_contains_retirement_kitas_and_convicts_mutation() -> None:
    """(a) Innocence + guilt: no route contains 'Retirement KITAS' (case-insensitive)."""
    service = KGEnhancedRetrieval(db_pool=object())
    routes = dict(service.GOLDEN_ROUTES)

    assert _find_retirement_kitas_routes(routes) == []

    target_route = routes["investor_kitas_retirement"]
    mutations = [
        dataclasses.replace(target_route, name="Investor KITAS or Retirement KITAS"),
        dataclasses.replace(target_route, description="Long-term stay via retirement kitas"),
        dataclasses.replace(
            target_route,
            path=[*target_route.path, "Convert to Retirement KITAS at immigration"],
        ),
        dataclasses.replace(
            target_route,
            key_conditions=[*target_route.key_conditions, "Cannot work on Retirement KITAS"],
        ),
    ]
    for mutated_route in mutations:
        mutated_map = {**routes, "investor_kitas_retirement": mutated_route}
        assert _find_retirement_kitas_routes(mutated_map) == ["investor_kitas_retirement"]


def test_investor_kitas_retirement_names_e33f_and_second_home_senior() -> None:
    """(b) investor_kitas_retirement names 'E33F' and 'Second Home Senior' (innocence + guilt)."""
    service = KGEnhancedRetrieval(db_pool=object())
    route = service.GOLDEN_ROUTES["investor_kitas_retirement"]

    assert _check_e33f_second_home_senior_named(route) == []
    assert "E33F" in route.name
    assert "Second Home Senior" in route.name

    stripped_route = dataclasses.replace(
        route,
        name="Investor KITAS",
        description="Obtain long-term stay permit",
        path=["Apply online"],
        key_conditions=["Valid passport"],
    )
    assert _check_e33f_second_home_senior_named(stripped_route) == [
        "E33F",
        "Second Home Senior",
    ]


def test_investor_kitas_retirement_usd_figures_backed_by_seq29_or_saved_pages() -> None:
    """(c) Every USD figure in investor_kitas_retirement is backed by seq-29 pack or saved pages."""
    service = KGEnhancedRetrieval(db_pool=object())
    route = service.GOLDEN_ROUTES["investor_kitas_retirement"]

    signed_pack = json.loads(SIGNED_PACK_PATH.read_text(encoding="utf-8"))
    payload_numbers = _collect_payload_numbers(signed_pack["payload"])

    extracted = USD_FIGURE_RE.findall(_flatten_golden_route(route))
    assert extracted, "Expected at least one USD threshold figure in investor_kitas_retirement"
    assert _find_unbacked_usd_figures(route, payload_numbers) == []

    for raw_figure in set(extracted):
        assert _figure_in_saved_pages(raw_figure), (
            f"Expected USD {raw_figure} to also appear in saved official pages"
        )

    mutated_route = dataclasses.replace(
        route,
        key_conditions=[
            *route.key_conditions,
            "Requires minimum balance of USD 9,999 in bank",
        ],
    )
    assert _find_unbacked_usd_figures(mutated_route, payload_numbers) == ["USD 9,999"]
