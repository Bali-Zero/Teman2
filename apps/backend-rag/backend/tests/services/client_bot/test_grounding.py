"""GroundingBundleBuilder — domain resolution and the real PricingTool
integration (Golden Rule 11). The KBLI-domain pricing skip and the
DomainNotSpecifiedError guard are the two behaviors most load-bearing for
FinalPolicyGate's own downstream checks — see grounding.py's own module
docstring.

Author: Claude Opus 5 (lane B1b — client-bot engine; lane B1c —
per-service pricing items + domain scoping; lane B1d — qualified-key
uniqueness for the tax-tier collision, 2026-08-25).
"""

from __future__ import annotations

import pytest

from backend.channels.profiles import CLIENT_KBLI_V1, CLIENT_WA_V1
from backend.services.client_bot.contracts import EvidenceItem
from backend.services.client_bot.grounding import (
    DomainNotSpecifiedError,
    GroundingBundleBuilder,
)
from backend.services.client_bot.policy.pricing_check import check_pricing
from backend.tests.duebot.goldens.builders import (
    make_answer_candidate,
    make_claim,
    make_evidence_item,
)


class _FixedRetriever:
    def __init__(self, items: tuple[EvidenceItem, ...]) -> None:
        self._items = items
        self.calls: list[tuple[str, str]] = []

    async def retrieve(self, query: str, domain: str) -> tuple[EvidenceItem, ...]:
        self.calls.append((query, domain))
        return self._items


@pytest.mark.asyncio
async def test_single_domain_profile_infers_domain_without_being_told() -> None:
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Apa itu KBLI 47190?", profile=CLIENT_KBLI_V1)
    assert bundle.domain == "kbli"


@pytest.mark.asyncio
async def test_multi_domain_profile_with_no_explicit_domain_raises() -> None:
    builder = GroundingBundleBuilder()
    with pytest.raises(DomainNotSpecifiedError):
        await builder.build(query="Saya butuh KITAS", profile=CLIENT_WA_V1)


@pytest.mark.asyncio
async def test_multi_domain_profile_with_explicit_domain_is_honored() -> None:
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Saya butuh KITAS", profile=CLIENT_WA_V1, domain="immigration")
    assert bundle.domain == "immigration"


@pytest.mark.asyncio
async def test_kbli_domain_never_carries_a_pricing_snapshot() -> None:
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Apa itu KBLI 47190?", profile=CLIENT_KBLI_V1)
    assert bundle.pricing is None


@pytest.mark.asyncio
async def test_no_evidence_retriever_wired_yields_empty_evidence() -> None:
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Saya butuh KITAS", profile=CLIENT_WA_V1, domain="immigration")
    assert bundle.evidence == ()


@pytest.mark.asyncio
async def test_wired_evidence_retriever_is_called_with_resolved_domain() -> None:
    item = make_evidence_item("gr", suffix="ev1")
    retriever = _FixedRetriever((item,))
    builder = GroundingBundleBuilder(evidence_retriever=retriever)
    bundle = await builder.build(query="Saya butuh KITAS", profile=CLIENT_WA_V1, domain="immigration")
    assert bundle.evidence == (item,)
    assert retriever.calls == [("Saya butuh KITAS", "immigration")]


@pytest.mark.asyncio
async def test_package_sha256_is_deterministic_for_identical_inputs() -> None:
    # KBLI domain deliberately: for any non-kbli domain, _build_pricing_snapshot
    # mints a fresh uuid4() snapshot_id and datetime.now() generated_at on
    # EVERY call (a live PricingTool read, by design — see grounding.py's own
    # module docstring), which is folded into the hash and makes two separate
    # build() calls differ even for byte-identical query/profile/domain. That
    # is correct production behavior (a single request calls build() exactly
    # once), not something this determinism property can observe through a
    # domain that touches pricing — KBLI's bundle.pricing is always None
    # (see test_kbli_domain_never_carries_a_pricing_snapshot above), isolating
    # the property this test actually means to check.
    builder = GroundingBundleBuilder()
    bundle_a = await builder.build(query="Apa itu KBLI 47190?", profile=CLIENT_KBLI_V1)
    bundle_b = await builder.build(query="Apa itu KBLI 47190?", profile=CLIENT_KBLI_V1)
    assert bundle_a.package_sha256 == bundle_b.package_sha256


@pytest.mark.asyncio
async def test_package_sha256_changes_when_query_changes() -> None:
    # Same KBLI-domain isolation as the determinism test above — otherwise
    # the live pricing snapshot's own per-call randomness would make this
    # assertion pass regardless of whether the query actually changed the
    # hash, which is not what this test means to verify.
    builder = GroundingBundleBuilder()
    bundle_a = await builder.build(query="Apa itu KBLI 47190?", profile=CLIENT_KBLI_V1)
    bundle_b = await builder.build(query="Apa itu KBLI lain?", profile=CLIENT_KBLI_V1)
    assert bundle_a.package_sha256 != bundle_b.package_sha256


# ---------------------------------------------------------------------------
# SPEC-price-service-binding.md P1 + P4 — per-service items, domain-scoped.
# These run against the REAL, live PricingTool catalogue on disk (no mock),
# because P4's whole point is a real constraint against real data:
# PricingSnapshot.items caps at max_length=100 and the live 2026 catalogue
# has ~113 services — an unscoped one-item-per-service snapshot would raise
# ValidationError building a bundle for ANY non-KBLI domain.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pricing_snapshot_items_each_carry_a_first_class_service_key() -> None:
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Berapa biaya KITAS?", profile=CLIENT_WA_V1, domain="immigration")
    assert bundle.pricing is not None
    assert len(bundle.pricing.items) > 0
    for item in bundle.pricing.items:
        assert isinstance(item.get("key"), str) and item["key"]


@pytest.mark.asyncio
async def test_pricing_snapshot_scoped_to_any_domain_stays_under_the_item_cap() -> None:
    builder = GroundingBundleBuilder()
    for domain in ("immigration", "company", "tax", "property"):
        bundle = await builder.build(query="q", profile=CLIENT_WA_V1, domain=domain)
        assert bundle.pricing is not None
        assert len(bundle.pricing.items) <= 100, f"domain={domain!r} exceeded PricingSnapshot's cap"


@pytest.mark.asyncio
async def test_pricing_snapshot_scoping_is_domain_specific() -> None:
    builder = GroundingBundleBuilder()
    tax_bundle = await builder.build(query="q", profile=CLIENT_WA_V1, domain="tax")
    categories = {item["category"] for item in tax_bundle.pricing.items}
    assert categories, "expected the tax domain to carry at least one priced category"
    assert categories <= {"tax_accounting", "consultant_services"}
    assert "kitas_permits" not in categories


@pytest.mark.asyncio
async def test_property_domain_has_no_mapped_pricing_categories_today() -> None:
    # Documents the P4 judgment call explicitly, rather than leaving an
    # empty snapshot unexplained: the 2026 catalogue has no property/
    # real-estate pricing rows, so this domain's snapshot is legitimately
    # empty, not a bug.
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="q", profile=CLIENT_WA_V1, domain="property")
    assert bundle.pricing is not None
    assert bundle.pricing.items == ()


# ---------------------------------------------------------------------------
# Lane B1d, 2026-08-25 — snapshot keys unique BY CONSTRUCTION, not by luck.
#
# B1c's "``key``: service_name" was unique only because nothing in the live
# catalogue happened to collide when B1c wrote it — it does: 4 real "Tier N"
# service names are shared, unqualified, between tax_accounting's
# monthly_tax_basic and monthly_tax_bundled sub-blocks. These tests run
# against the REAL, live catalogue on disk (never a synthetic fixture) —
# a uniqueness guarantee that only holds against a fixture is not a
# guarantee against the data this ships against.
# ---------------------------------------------------------------------------

# Verified 2026-08-25 by walking the real catalogue: every "Tier N" name
# under tax_accounting's monthly_tax_basic/monthly_tax_bundled sub-blocks —
# the ONLY collision this catalogue has today. Pinned explicitly (not just
# "assert no collisions") so a FUTURE catalogue edit that removes one of
# these without adding a new collision is visible as a deliberate test
# update, not a silent behavior change nobody reviews.
_KNOWN_COLLIDING_TAX_TIER_NAMES = ("Tier 0-50", "Tier 50-100", "Tier 100-200", "Tier 200+")


def _real_services_root() -> dict[str, object]:
    from backend.services.pricing.pricing_service import get_pricing_service

    service = get_pricing_service()
    assert service.loaded, "the live 2026 pricing catalogue failed to load — cannot test against it"
    services_root = service.prices.get("services", {})
    assert isinstance(services_root, dict) and services_root
    return services_root


def test_service_key_index_is_unique_across_the_whole_real_catalogue() -> None:
    """P1 requirement 1: unique across the WHOLE catalogue, provably, over
    the real on-disk data — not merely "no collision found in a fixture".
    If a future catalogue edit reintroduces a duplicate that even
    category/sub-block qualification cannot disambiguate,
    ``_service_key_index`` itself raises (see its own docstring); this test
    additionally proves the resulting index is injective as observed from
    the outside, so a regression is caught by pytest even if someone later
    weakens that internal guard.
    """
    from backend.services.client_bot.grounding import _service_key_index

    key_index = _service_key_index(_real_services_root())
    assert len(key_index) > 0
    assigned_keys = list(key_index.values())
    assert len(assigned_keys) == len(set(assigned_keys)), (
        "two different catalogue entries were assigned the SAME snapshot "
        f"key — not unique by construction: {sorted(assigned_keys)!r}"
    )


def test_service_key_index_qualifies_exactly_the_known_tax_tier_collision() -> None:
    """Census, pinned: the live catalogue's ONLY collision today is the 4
    "Tier N" names shared between monthly_tax_basic/monthly_tax_bundled.
    Every colliding name must come back QUALIFIED (never the bare,
    ambiguous dict key); every OTHER catalogue entry must be UNCHANGED
    from B1c's plain display-name key — qualifying more than necessary
    would needlessly break model-emittability for the ~109 services that
    were never ambiguous in the first place.
    """
    from backend.services.client_bot.grounding import (
        _iter_service_entries_with_subblock,
        _service_key_index,
    )

    services_root = _real_services_root()
    key_index = _service_key_index(services_root)
    triples = _iter_service_entries_with_subblock(services_root)

    for category, sub_block, service_name, _entry in triples:
        assigned = key_index[(category, sub_block, service_name)]
        if service_name in _KNOWN_COLLIDING_TAX_TIER_NAMES:
            assert sub_block is not None, "the known collision is inside tax_accounting sub-blocks"
            assert assigned == f"{sub_block}::{service_name}", (
                f"{service_name!r} in {sub_block!r} should have been qualified, got {assigned!r}"
            )
        else:
            assert assigned == service_name, (
                f"{service_name!r} (unambiguous) was needlessly qualified to {assigned!r} — "
                "this breaks model-emittability for a name that was never ambiguous"
            )

    # And the inverse: every known-colliding name actually appears TWICE
    # (once per sub-block) — pins the census itself, so if the catalogue
    # ever de-duplicates one of these on its own, this test says so.
    for name in _KNOWN_COLLIDING_TAX_TIER_NAMES:
        occurrences = [t for t in triples if t[2] == name]
        assert len(occurrences) == 2, (
            f"expected exactly 2 occurrences of {name!r} (the known "
            f"monthly_tax_basic/monthly_tax_bundled collision), found "
            f"{len(occurrences)} — the catalogue census has changed, update "
            "this pin deliberately"
        )


@pytest.mark.asyncio
async def test_tax_domain_snapshot_never_carries_the_bare_ambiguous_tier_key() -> None:
    """End-to-end through the real ``build()`` path (not just the internal
    index function): a domain="tax" snapshot must show BOTH qualified
    variants of every colliding tier name and NEVER the bare, ambiguous
    original — the shape a provider actually sees.
    """
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Berapa biaya jasa pajak bulanan?", profile=CLIENT_WA_V1, domain="tax")
    assert bundle.pricing is not None
    keys = {item["key"] for item in bundle.pricing.items}

    for name in _KNOWN_COLLIDING_TAX_TIER_NAMES:
        assert name not in keys, f"bare, ambiguous key {name!r} leaked into a real snapshot"
        assert f"monthly_tax_basic::{name}" in keys
        assert f"monthly_tax_bundled::{name}" in keys


@pytest.mark.asyncio
async def test_qualified_tier_items_still_carry_their_own_distinguishing_price_and_name() -> None:
    """The two items behind a qualified key are not just distinguishable BY
    key — they must still carry their own, different price and
    description, so a provider reading the snapshot has what it needs to
    pick the right one (not just avoid a crash on an ambiguous string).
    """
    builder = GroundingBundleBuilder()
    bundle = await builder.build(query="Berapa biaya jasa pajak bulanan?", profile=CLIENT_WA_V1, domain="tax")
    assert bundle.pricing is not None
    by_key = {item["key"]: item for item in bundle.pricing.items}

    basic = by_key["monthly_tax_basic::Tier 0-50"]
    bundled = by_key["monthly_tax_bundled::Tier 0-50"]
    assert basic["price"] != bundled["price"]
    assert basic["name"] != bundled["name"]
    assert "without" in basic["name"].lower()
    assert "including" in bundled["name"].lower()


def test_service_key_index_logs_but_does_not_crash_on_a_residual_collision(caplog) -> None:
    """Pathological, hand-built input (NOT the real catalogue — that is
    proven collision-free by the test above): a flat category literally
    named the same as a nested category's own sub-block, both containing a
    service with the SAME name, produces two entries whose QUALIFIED keys
    still collide (both qualify to "consultant_services::widget").
    ``_service_key_index`` must log loudly, never raise — crashing here
    would take down pricing for the WHOLE engine over one bad corner of a
    hypothetical future catalogue edit, when ``pricing_check.py``'s own
    per-claim ambiguity refusal already defends against exactly this.
    """
    from backend.services.client_bot.grounding import _service_key_index

    synthetic_services_root: dict[str, object] = {
        "consultant_services": {"widget": {"name": "Widget A", "price": "1.000.000 IDR"}},
        "tax_accounting": {
            "consultant_services": {"widget": {"name": "Widget B", "price": "2.000.000 IDR"}}
        },
    }
    with caplog.at_level("ERROR"):
        key_index = _service_key_index(synthetic_services_root)
    assert any("remain ambiguous" in record.message for record in caplog.records), (
        "a residual collision must be logged loudly, not silently accepted"
    )
    # Both entries share the identical (unfortunate, constructed-on-purpose)
    # qualified key — proving the residual-collision path is real and that
    # this function still returns a usable (if locally ambiguous) index
    # rather than crashing.
    assert (
        key_index[("consultant_services", None, "widget")]
        == key_index[("tax_accounting", "consultant_services", "widget")]
    )


@pytest.mark.asyncio
async def test_end_to_end_real_bundle_qualified_key_binds_through_check_pricing() -> None:
    """The full pipeline, not a re-derived approximation of it: a REAL
    ``GroundingBundle`` (built through the actual ``GroundingBundleBuilder``
    against the on-disk catalogue, nothing hand-rolled) is handed straight
    into ``check_pricing`` with a claim referencing the qualified key the
    bundle itself produced. Proves grounding.py's output and
    pricing_check.py's binding actually agree with each other, not just
    with a shape each module's own tests assumed the other produces.
    """
    builder = GroundingBundleBuilder()
    bundle = await builder.build(
        query="Berapa biaya jasa pajak bulanan bundled untuk 0-50 transaksi?",
        profile=CLIENT_WA_V1,
        domain="tax",
    )
    assert bundle.pricing is not None
    bundled_item = next(
        item for item in bundle.pricing.items if item["key"] == "monthly_tax_bundled::Tier 0-50"
    )
    assert bundled_item["price"] == "2.500.000 IDR"

    claim = make_claim(
        suffix="e2e-bundled",
        text="Rp 2.500.000",
        kind="price",
        price_service_key="monthly_tax_bundled::Tier 0-50",
    )
    candidate = make_answer_candidate(
        "e2e-bundled",
        answer="Paket bundled 0-50 transaksi (sudah termasuk LKPM & tahunan): Rp 2.500.000.",
        claims=(claim,),
    )
    assert check_pricing(candidate, bundle.pricing) is None, (
        "a claim bound to grounding.py's OWN qualified key, quoting the "
        "matching amount grounding.py itself produced, was refused by "
        "check_pricing — the two modules disagree about the contract "
        "between them"
    )

    # And the wrong-variant guilt case, still end-to-end: the SAME real
    # bundle, a claim correctly naming the bundled key, but quoting the
    # BASIC tier's range instead — must still be refused.
    wrong_claim = make_claim(
        suffix="e2e-wrong",
        text="Rp 1.800.000",
        kind="price",
        price_service_key="monthly_tax_bundled::Tier 0-50",
    )
    wrong_candidate = make_answer_candidate(
        "e2e-wrong",
        answer="Paket bundled 0-50 transaksi: Rp 1.800.000.",
        claims=(wrong_claim,),
    )
    outcome = check_pricing(wrong_candidate, bundle.pricing)
    assert outcome is not None
    assert outcome.reason_detail == "quoted_amount_not_for_claimed_service"
