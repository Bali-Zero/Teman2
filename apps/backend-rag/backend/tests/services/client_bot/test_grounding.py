"""GroundingBundleBuilder — domain resolution and the real PricingTool
integration (Golden Rule 11). The KBLI-domain pricing skip and the
DomainNotSpecifiedError guard are the two behaviors most load-bearing for
FinalPolicyGate's own downstream checks — see grounding.py's own module
docstring.

Author: Claude Opus 5 (lane B1b — client-bot engine; lane B1c —
per-service pricing items + domain scoping, 2026-08-25).
"""

from __future__ import annotations

import pytest

from backend.channels.profiles import CLIENT_KBLI_V1, CLIENT_WA_V1
from backend.services.client_bot.contracts import EvidenceItem
from backend.services.client_bot.grounding import (
    DomainNotSpecifiedError,
    GroundingBundleBuilder,
)
from backend.tests.duebot.goldens.builders import make_evidence_item


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
