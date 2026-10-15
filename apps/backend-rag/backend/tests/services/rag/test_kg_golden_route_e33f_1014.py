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
USD_FIGURE_RE = re.compile(r"\bUSD\s+([\d,]+)\b")
INCOME_CLAIM_RE = re.compile(r"income or allowance of at least USD ([\d,]+)/month")
DEPOSIT_CLAIM_RE = re.compile(r"USD ([\d,]+) deposit")
PROPERTY_CLAIM_RE = re.compile(r"USD ([\d,]+) qualifying property")
SAVED_PAGE_USD_ENTITY_RE = re.compile(r"(?:US\$|USD)\s?\$?\s?([\d.,]+)")
PASSPORT_MONTHS_RE = re.compile(r"at least (\d+) months")

PINNED_PATH = [
    "Choose the route: E28A Investor Visa (committed PT PMA) or Second Home Senior (E33E, 5 years; E33F Second Home Senior KITAS, 1 year)",
    "E28A Investor: commit to a PT PMA in Indonesia as shareholder-director or shareholder-commissioner; the signed rules allow an initial stay of 2 years",
    "E33F Second Home Senior KITAS: provide proof of income or allowance of at least USD 3,000/month",
    "E33F: a sponsor (penjamin) is required; the sponsor applies online via evisa.imigrasi.go.id with a passport valid for at least 6 months",
    "E33F: the Limited Stay Permit (KITAS, 1 year) and the Re-entry Permit are issued automatically once the officer admits you at the immigration checkpoint",
    "E33F: renewal of the stay permit can be done online via evisa.imigrasi.go.id",
    "E33 Second Home (up to 5 years first grant): USD 130,000 deposit or USD 1,000,000 qualifying property route",
]
PINNED_KEY_CONDITIONS = [
    "E28A Investor Visa requires a committed PT PMA (as shareholder-director or shareholder-commissioner)",
    "E33F Second Home Senior KITAS: minimum age 55, proof of income or allowance of at least USD 3,000/month",
    "E33 Second Home: USD 130,000 deposit in own name at a state-owned (BUMN) Indonesian bank, or USD 1,000,000 qualifying property",
    "E33F Second Home Senior KITAS: the official page covers staying in Indonesia and activities related to business, meetings or shopping (including checking goods at an office, factory or production site), plus tourism and visiting friends or family; it prohibits overstaying, work not in line with the stay permit, and selling goods or services unless required for that work",
]


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


def _collect_pack_usd_thresholds(
    node: Any,
    out: dict[str, set[int]] | None = None,
) -> dict[str, set[int]]:
    """Walk the signed pack payload and collect fact -> set(values) for *_usd threshold dicts."""
    if out is None:
        out = {}
    if isinstance(node, dict):
        fact = node.get("fact")
        op = node.get("op")
        value = node.get("value")
        if (
            isinstance(fact, str)
            and fact.endswith("_usd")
            and op in {"gte", "lte"}
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            out.setdefault(fact, set()).add(int(value))
        for val in node.values():
            _collect_pack_usd_thresholds(val, out)
    elif isinstance(node, list):
        for item in node:
            _collect_pack_usd_thresholds(item, out)
    return out


def _collect_saved_page_usd_entities() -> set[int]:
    """Parse saved official pages for US$/USD entities and convert to int."""
    entities: set[int] = set()
    for directory in SAVED_PAGE_DIRS:
        if not directory.exists():
            continue
        for txt_file in sorted(directory.glob("*.txt")):
            content = txt_file.read_text(encoding="utf-8")
            for raw in SAVED_PAGE_USD_ENTITY_RE.findall(content):
                cleaned = raw.replace(",", "").replace(".", "")
                if cleaned.isdigit():
                    entities.add(int(cleaned))
    return entities


def _saved_pages_contain_phrase(phrase: str) -> bool:
    """Return True if phrase appears in at least one saved official page."""
    for directory in SAVED_PAGE_DIRS:
        if not directory.exists():
            continue
        for txt_file in sorted(directory.glob("*.txt")):
            if phrase in txt_file.read_text(encoding="utf-8"):
                return True
    return False


def _check_bound_usd_figures(
    route: GoldenRoute,
    pack_thresholds: Mapping[str, set[int]],
    page_usd_entities: set[int],
) -> list[str]:
    """Verify every USD claim in route is bound to the expected pack threshold and saved page entity."""
    text = _flatten_golden_route(route)
    issues: list[str] = []

    expected_income = 3000
    expected_deposit = 130000
    expected_property = 1000000

    if pack_thresholds.get("secondhome.passive_monthly_income_usd") != {expected_income}:
        issues.append("pack income threshold mismatch")
    if expected_deposit not in pack_thresholds.get("secondhome.bank_deposit_usd", set()):
        issues.append("pack deposit threshold missing 130000")
    if expected_property not in pack_thresholds.get(
        "secondhome.qualifying_property_value_usd", set()
    ):
        issues.append("pack property threshold missing 1000000")

    bound_specs = (
        ("income", INCOME_CLAIM_RE, expected_income),
        ("deposit", DEPOSIT_CLAIM_RE, expected_deposit),
        ("property", PROPERTY_CLAIM_RE, expected_property),
    )

    covered_spans: set[tuple[int, int]] = set()
    for label, pattern, expected_val in bound_specs:
        matches = list(pattern.finditer(text))
        if not matches:
            issues.append(f"missing {label} claim match")
            continue
        for match in matches:
            covered_spans.add(match.span(1))
            numeric_val = int(match.group(1).replace(",", ""))
            if numeric_val != expected_val:
                issues.append(f"{label} figure {numeric_val} != {expected_val}")
            if numeric_val not in page_usd_entities:
                issues.append(f"{label} figure {numeric_val} not in saved pages")

    for match in USD_FIGURE_RE.finditer(text):
        if match.span(1) not in covered_spans:
            issues.append(f"unbound USD figure: USD {match.group(1)}")

    return issues


def _check_passport_validity_in_saved_pages(route: GoldenRoute) -> list[str]:
    """Verify 'at least N months' in route appears as 'paling singkat N bulan' in saved pages."""
    text = _flatten_golden_route(route)
    matches = PASSPORT_MONTHS_RE.findall(text)
    if not matches:
        return ["missing 'at least N months' passport claim"]
    issues: list[str] = []
    for months in matches:
        indonesian_phrase = f"paling singkat {months} bulan"
        if not _saved_pages_contain_phrase(indonesian_phrase):
            issues.append(f"unbacked passport validity: {indonesian_phrase}")
    return issues


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
    """(c) Entity-bound USD figures, exact route pin, passport validity, and guilt mutations."""
    service = KGEnhancedRetrieval(db_pool=object())
    route = service.GOLDEN_ROUTES["investor_kitas_retirement"]

    signed_pack = json.loads(SIGNED_PACK_PATH.read_text(encoding="utf-8"))
    pack_thresholds = _collect_pack_usd_thresholds(signed_pack["payload"])
    assert pack_thresholds["secondhome.passive_monthly_income_usd"] == {3000}
    assert 130000 in pack_thresholds["secondhome.bank_deposit_usd"]
    assert 1000000 in pack_thresholds["secondhome.qualifying_property_value_usd"]

    page_usd_entities = _collect_saved_page_usd_entities()
    assert {3000, 130000, 1000000}.issubset(page_usd_entities)

    assert route.path == PINNED_PATH
    assert route.key_conditions == PINNED_KEY_CONDITIONS

    assert _check_bound_usd_figures(route, pack_thresholds, page_usd_entities) == []

    usd_mutations = [
        dataclasses.replace(
            route,
            path=[s.replace("USD 3,000/month", "USD 13,000/month") for s in route.path],
        ),
        dataclasses.replace(
            route,
            path=[s.replace("USD 3,000/month", "USD 2,000/month") for s in route.path],
        ),
        dataclasses.replace(
            route,
            path=[s.replace("USD 130,000 deposit", "USD 500,000 deposit") for s in route.path],
        ),
        dataclasses.replace(
            route,
            path=[
                s.replace(
                    "USD 1,000,000 qualifying property",
                    "USD 500,000 qualifying property",
                )
                for s in route.path
            ],
        ),
        dataclasses.replace(
            route,
            key_conditions=[
                *route.key_conditions,
                "Requires minimum balance of USD 9,999 in bank",
            ],
        ),
    ]
    for mutated_route in usd_mutations:
        assert _check_bound_usd_figures(mutated_route, pack_thresholds, page_usd_entities) != []

    mutated_activities = dataclasses.replace(
        route,
        key_conditions=[
            s.replace("activities related to business", "allows business")
            for s in route.key_conditions
        ],
    )
    assert mutated_activities.key_conditions != PINNED_KEY_CONDITIONS

    assert _saved_pages_contain_phrase("paling singkat 6 bulan")
    assert _check_passport_validity_in_saved_pages(route) == []
    mutated_passport = dataclasses.replace(
        route,
        path=[s.replace("at least 6 months", "at least 60 months") for s in route.path],
    )
    assert _check_passport_validity_in_saved_pages(mutated_passport) == [
        "unbacked passport validity: paling singkat 60 bulan"
    ]
