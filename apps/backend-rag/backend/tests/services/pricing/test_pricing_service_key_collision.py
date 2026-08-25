"""``get_service_by_key`` must refuse to guess when two catalogue entries
share a key — regression suite for the "silent first-match" defect its own
docstring names as the failure it exists to make impossible. The live 2026
catalogue has 4 real ``service_name`` collisions, all in ``tax_accounting``
between the ``monthly_tax_basic`` (tier-range price, LKPM/Annual Tax NOT
included) and ``monthly_tax_bundled`` (single price, LKPM + Annual Tax
included) sub-blocks — a real spread of ~500k-1.5M IDR and a different
scope of work sitting behind the identical dict key.

  guilt      the 4 real collisions refuse a bare key (``None``, never a
             guess); the qualified ``"<sub_block>::<name>"`` form resolves
             each one to its OWN, distinct row
  innocence  every unambiguous key in the real catalogue still resolves
             exactly as before; each of the three live consumers keeps its
             existing behaviour on a normal (non-colliding) key

Deliberately discovers the collision set from the REAL, shipped on-disk
catalogue at test time via an independent walk (never a hardcoded literal
list, never a call into the collision-resolution logic under test) — a 5th
future collision widens the parametrization and is covered the day it
lands, rather than needing this file to be remembered and updated by hand.

Reachability per consumer (verified 2026-08-25, see the lane report):

  * ``GET /api/pricing/service?key=...`` (``app/routers/dynamic_pricing.py``)
    is PUBLIC, unauthenticated, and ``key`` is an arbitrary client-supplied
    query string with no enum constraint — the ONLY consumer that could
    reach a colliding key from outside the system today.
  * ``garuda_flow/pricing.py::price_for_case`` uses two hardcoded source
    literals (``_ISSUANCE_PRICE_KEY`` / ``_EXTENSION_PRICE_KEY``), never
    client- or data-supplied, and neither is one of the 4 real colliding
    names — provably unreachable today by construction, not merely by
    the current data.
  * ``visa_engine/pricing_adapter.py::resolve_candidate_pricing`` reads
    ``product.pricing_key`` from a SIGNED RulePack payload — curated data,
    not a live HTTP input, and no signed pack today names a
    ``tax_accounting`` category or one of the 4 colliding item keys — but
    the schema does not forbid it, and the adapter's own
    ``row.get("category") != pricing_key.category`` guard cannot
    disambiguate the two sub-blocks (both report ``category ==
    "tax_accounting"``), so this consumer's safety is a property of the
    catalogue data today, not a mechanism, unlike garuda_flow's.
"""

from __future__ import annotations

import collections
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.pricing import (
    _EXTENSION_PRICE_KEY,
    _ISSUANCE_PRICE_KEY,
    price_for_case,
)
from backend.services.pricing.pricing_service import (
    _KEY_QUALIFIER_SEP,
    _NESTED_CATEGORIES,
    PricingService,
    _entry_display_price,
)
from backend.services.visa_engine.models import PricingKey
from backend.services.visa_engine.pricing_adapter import resolve_candidate_pricing
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader

REAL_COLLIDING_KEYS = ["Tier 0-50", "Tier 50-100", "Tier 100-200", "Tier 200+"]

_EVALUATED_AT = datetime(2026, 8, 25, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def svc() -> PricingService:
    """A ``PricingService`` reading the REAL, shipped 2026 catalogue — not
    a fixture stub. The whole point of this file is that the collision is
    a property of the live data, so the tests must run against it."""
    instance = PricingService()
    assert instance.loaded, "the shipped catalogue failed to load — check the data file path"
    return instance


def _real_catalogue_collisions(
    services: dict[str, Any],
) -> dict[str, list[tuple[str, str | None]]]:
    """Independently discover every ``service_name`` that names 2+ entries
    in the real catalogue, by walking the raw services mapping directly.

    Deliberately does NOT call ``_iter_service_entries_with_subblock`` (the
    function ``get_service_by_key`` — the subject of this file — is built
    on): a bug in the fix under test must never also blind the oracle that
    is supposed to catch it. ``_NESTED_CATEGORIES`` is reused because it is
    documented SCHEMA knowledge (the module docstring names it), not part
    of the collision-resolution logic this file holds accountable.
    """
    locations: dict[str, list[tuple[str, str | None]]] = collections.defaultdict(list)
    for category_name, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category_name in _NESTED_CATEGORIES:
            for sub_block_name, sub_block in category_payload.items():
                if not isinstance(sub_block, dict):
                    continue
                for service_name, entry in sub_block.items():
                    if isinstance(entry, dict):
                        locations[service_name].append((category_name, sub_block_name))
        else:
            for service_name, entry in category_payload.items():
                if isinstance(entry, dict):
                    locations[service_name].append((category_name, None))
    return {name: locs for name, locs in locations.items() if len(locs) > 1}


def _unambiguous_real_entries(
    services: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    """``(service_name, category, entry)`` for every catalogue entry whose
    name occurs exactly once across the whole real catalogue — same
    independent-walk discipline as :func:`_real_catalogue_collisions`."""
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = collections.defaultdict(list)
    for category_name, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category_name in _NESTED_CATEGORIES:
            for sub_block in category_payload.values():
                if not isinstance(sub_block, dict):
                    continue
                for service_name, entry in sub_block.items():
                    if isinstance(entry, dict):
                        grouped[service_name].append((category_name, entry))
        else:
            for service_name, entry in category_payload.items():
                if isinstance(entry, dict):
                    grouped[service_name].append((category_name, entry))
    return [(name, locs[0][0], locs[0][1]) for name, locs in grouped.items() if len(locs) == 1]


# ── ground-truth pin ──────────────────────────────────────────────────────


def test_real_catalogue_has_exactly_the_four_known_tax_tier_collisions(
    svc: PricingService,
) -> None:
    """Pins the CURRENT shape of the defect against the real, shipped data.
    If a 5th collision ever lands, this test goes red first — the
    parametrized guilt tests below then cover it automatically once
    ``REAL_COLLIDING_KEYS`` is updated to match."""
    collisions = _real_catalogue_collisions(svc.prices["services"])
    assert set(collisions) == set(REAL_COLLIDING_KEYS)
    for name, locs in collisions.items():
        assert len(locs) == 2, f"{name!r} collides {len(locs)} ways, expected 2"
        assert {cat for cat, _sub in locs} == {"tax_accounting"}
        assert {sub for _cat, sub in locs} == {"monthly_tax_basic", "monthly_tax_bundled"}


# ── guilt: the bare key must refuse to guess ──────────────────────────────


@pytest.mark.parametrize("key", REAL_COLLIDING_KEYS)
def test_bare_colliding_key_refuses_to_guess(svc: PricingService, key: str) -> None:
    """The exact defect: a bare colliding key must return ``None``, never
    silently the first sub-block the catalogue walk happens to reach."""
    assert svc.get_service_by_key(key) is None


@pytest.mark.parametrize("key", REAL_COLLIDING_KEYS)
def test_qualified_colliding_key_resolves_to_its_own_distinct_row(
    svc: PricingService, key: str
) -> None:
    """The escape hatch: a qualified key resolves to exactly ONE row, and
    the two sub-blocks of the same bare name are never priced the same."""
    basic_key = f"monthly_tax_basic{_KEY_QUALIFIER_SEP}{key}"
    bundled_key = f"monthly_tax_bundled{_KEY_QUALIFIER_SEP}{key}"

    basic = svc.get_service_by_key(basic_key)
    bundled = svc.get_service_by_key(bundled_key)

    assert basic is not None
    assert bundled is not None
    assert basic["key"] == basic_key
    assert bundled["key"] == bundled_key
    assert basic["category"] == "tax_accounting"
    assert bundled["category"] == "tax_accounting"
    assert basic["price"] != bundled["price"], (
        "the two sub-blocks of a colliding key must carry different prices "
        "on the live catalogue — if this ever fails, re-verify the "
        "catalogue before touching this test"
    )
    assert basic["notes"] and "NOT included" in basic["notes"]
    assert bundled["notes"] and "Includes LKPM" in bundled["notes"]


@pytest.mark.parametrize("key", REAL_COLLIDING_KEYS)
def test_wrong_qualifier_for_a_colliding_key_is_also_none(svc: PricingService, key: str) -> None:
    """A qualifier that names neither real sub-block must not silently
    fall back to a guess either."""
    assert svc.get_service_by_key(f"annual_basic_packages{_KEY_QUALIFIER_SEP}{key}") is None
    assert svc.get_service_by_key(f"not_a_real_sub_block{_KEY_QUALIFIER_SEP}{key}") is None


def test_qualified_form_reaches_end_to_end_through_the_public_router() -> None:
    """The public, unauthenticated ``/api/pricing/service`` route accepts
    the qualified form too — closing the reachability gap for the ONE
    consumer a real client can hit directly, not just degrading it to a
    clean 404."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.routers import dynamic_pricing

    app = FastAPI()
    app.include_router(dynamic_pricing.router)
    client = TestClient(app)

    bare = client.get("/api/pricing/service", params={"key": "Tier 0-50"})
    assert bare.status_code == 404, bare.text

    qualified = client.get(
        "/api/pricing/service",
        params={"key": f"monthly_tax_bundled{_KEY_QUALIFIER_SEP}Tier 0-50"},
    )
    assert qualified.status_code == 200, qualified.text
    body = qualified.json()
    assert body["key"] == f"monthly_tax_bundled{_KEY_QUALIFIER_SEP}Tier 0-50"
    assert body["price"] == "2.500.000 IDR"


# ── innocence: the fix must not move anything that was never ambiguous ───


def test_every_unambiguous_real_key_still_resolves_unchanged(svc: PricingService) -> None:
    """The 105 keys that were never ambiguous must resolve exactly as
    before: same key, category, name, price, validity and notes."""
    unambiguous = _unambiguous_real_entries(svc.prices["services"])
    assert len(unambiguous) == 105, (
        "the real catalogue's unambiguous-key count moved — re-verify the "
        "4-collision assumption this whole file rests on before touching "
        "this number"
    )
    for service_name, category, entry in unambiguous:
        row = svc.get_service_by_key(service_name)
        assert row is not None, f"{service_name!r} regressed to unresolved"
        assert row["key"] == service_name
        assert row["category"] == category
        assert row["name"] == (entry.get("name") or service_name)
        assert row["price"] == _entry_display_price(entry)
        assert row["validity"] == (entry.get("validity") or None)
        assert row["notes"] == (entry.get("notes") or None)


def test_unknown_key_is_still_none(svc: PricingService) -> None:
    """Baseline unaffected: a key nothing in the catalogue names is still
    a plain, silent ``None`` — no new warning noise for the common
    not-found path."""
    assert svc.get_service_by_key("No Such Service In The Catalogue 2026") is None


# ── innocence: the three live consumers on a normal, non-colliding key ───


def test_garuda_flow_hardcoded_keys_are_not_among_the_known_collisions() -> None:
    """garuda_flow's two case-type keys are compile-time source literals,
    never client- or data-supplied, and neither is a real catalogue
    collision — this consumer cannot reach the defect today. Pinned so a
    future rename that DID collide would fail loudly instead of silently
    reintroducing exposure."""
    assert _ISSUANCE_PRICE_KEY not in REAL_COLLIDING_KEYS
    assert _EXTENSION_PRICE_KEY not in REAL_COLLIDING_KEYS


@pytest.mark.parametrize("case_type", [CaseType.ISSUANCE, CaseType.EXTENSION])
def test_garuda_flow_price_for_case_unchanged_on_a_normal_key(
    svc: PricingService, case_type: CaseType
) -> None:
    """The fix does not alter this consumer's existing, already
    fail-closed behaviour on either B1 case type."""
    amount, key = price_for_case(case_type, pricing=svc)
    assert amount is not None
    assert amount > 0
    assert key in (_ISSUANCE_PRICE_KEY, _EXTENSION_PRICE_KEY)


def test_visa_engine_adapter_unchanged_on_a_normal_key(svc: PricingService) -> None:
    """An ordinary, non-colliding visa product still resolves to
    ``AVAILABLE`` with an amount — the fix does not degrade the common
    path this consumer relies on for every real signed RulePack today."""
    product = gold_loader.load_and_compile_rule_pack().source_pack.payload.products[0]
    product = product.model_copy(
        update={"pricing_key": PricingKey(category="single_entry_visas", item_key="C1 Tourism")}
    )
    result = resolve_candidate_pricing(
        product,
        pricing_catalog=svc,
        evaluated_at=_EVALUATED_AT,
    )
    assert result.status == "AVAILABLE"
    assert result.amount is not None


def test_visa_engine_adapter_fails_closed_if_a_pricing_key_ever_collided(
    svc: PricingService,
) -> None:
    """Consumer-facing guilt: this adapter's OWN ``category`` guard cannot
    disambiguate ``tax_accounting``'s two sub-blocks (both report the same
    top-level category), so the fix at the pricing-service layer is
    load-bearing for this consumer too — proven with a hypothetical
    ``PricingKey`` shaped like the real collision. No signed RulePack does
    this today (verified separately against every ``contracts/packs/*``
    file), but the schema does not forbid it, so this is a real, not a
    theoretical, regression guard."""
    product = gold_loader.load_and_compile_rule_pack().source_pack.payload.products[0]
    product = product.model_copy(
        update={"pricing_key": PricingKey(category="tax_accounting", item_key="Tier 0-50")}
    )
    result = resolve_candidate_pricing(
        product,
        pricing_catalog=svc,
        evaluated_at=_EVALUATED_AT,
    )
    assert result.status == "CONTACT_REQUIRED"
    assert result.reason_code == "PRICING_ROW_MISSING"
    assert result.amount is None
