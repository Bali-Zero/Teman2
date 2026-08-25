"""GroundingBundleBuilder — the ONE frozen evidence/pricing/history package
every provider sees identically (research capture Sol §1.1/§1.5 routing
rule 2: "GroundingBundleBuilder runs before provider selection. Gemini and
Codex receive the same evidence and PricingTool snapshot").

Two collaborators, two different maturity levels — both deliberate, both
reported to the team lead before this lane built outward on them:

- ``PricingSnapshot`` construction is wired to the REAL, live PricingTool
  (``services/pricing/pricing_service.py::get_pricing_service()``) —
  Golden Rule 11 ("PricingTool Only") makes this the highest-risk path in
  the whole client-bot engine, so it gets a real integration, not a stub.
- Evidence (KB/Qdrant) retrieval is an injectable ``EvidenceRetriever``
  protocol with a safe empty default. The existing agentic RAG retrieval
  stack (``services/rag/agentic/orchestrator_core.py`` and its siblings)
  is a large, multi-file subsystem this lane does not own and has not
  wired — reaching into it correctly is a real integration project of its
  own, not something to rush during a dark-ship pass. An empty evidence
  tuple is SAFE here (never a false ALLOW): every FinalPolicyGate check
  that depends on evidence (6/8/9) fails closed — ABSTAIN or HANDOFF —

  **But safe is not the same as measured (team lead, 2026-08-25).** With
  no retriever wired, this builder returns an empty ``evidence`` tuple on
  EVERY query, which makes checks 6/8/9 abstain/handoff on EVERY claim
  that needs evidence — a well-formed, 100%-handoff result that LOOKS
  exactly like "the gates are working" and is INDISTINGUISHABLE from it in
  the output alone. It is not a measurement of retrieval quality, answer
  quality, or anything else — it is a stub returning its one possible
  answer. ``evidence_retrieval_is_stubbed`` below exists so no caller can
  produce a shadow/quality number from this builder without knowing that.
  **No shadow number from a stubbed builder measures answer quality —
  only that no evidence was ever offered to the gate.**

``domain`` classification (which of "immigration"/"company"/"tax"/
"property"/"kbli" a query belongs to) is likewise NOT this builder's job —
it is an input the caller (``engine.py``, or a future domain-classifier
lane) supplies, defaulting to the profile's sole allowed domain for
single-domain profiles (KBLI widget) and left unresolved (raises) for
multi-domain profiles without an explicit domain — see ``build()``.

``package_sha256`` is computed over every OTHER field before the bundle is
constructed (the bundle cannot hash itself) — the exact same canonical
serialization ``BrainCandidate.package_sha256`` must echo back verbatim
for check 2 (``final_gate.py``) to pass.

SPEC-price-service-binding.md (2026-08-25), P1 + P4 — ``_build_pricing_snapshot``
no longer calls ``PricingService.get_pricing("all")`` (the entire nested
catalogue folded into one opaque item, which is what let check 7 only ever
ask "is this amount A real price anywhere", never "the price of THIS
service"). It now builds ONE ``PricingSnapshot`` item PER SERVICE via
``_iter_service_entries()``, each item carrying its catalogue key as a
first-class ``"key"`` field — the identity ``Claim.price_service_key``
(``contracts.py`` P2) and ``pricing_check.py``'s per-claim binding (P3)
need. This is also why the snapshot is now DOMAIN-SCOPED rather than
exhaustive (P4): the live 2026 catalogue has ~113 services, well over
``PricingSnapshot.items``'s own ``max_length=100`` — an unscoped
one-item-per-service snapshot would raise ``ValidationError`` on
construction for every non-KBLI query. ``_DOMAIN_PRICING_CATEGORIES``
below is the scoping heuristic; see its own comment for what it is (and is
not) a claim about.

Follow-up (lane B1d, 2026-08-25) — B1c's "``"key": service_name``" above
was unique BY LUCK, not by construction: the live catalogue has 4 real
collisions, all "Tier N" names shared between ``tax_accounting``'s
``monthly_tax_basic`` and ``monthly_tax_bundled`` sub-blocks (a genuinely
different price AND scope of work behind the identical dict key — see
``_service_key_index``'s own docstring for the exact numbers). Two items
sharing a key is exactly the shape ``pricing_check.py``'s per-claim
binding (P1-P3) exists to prevent one layer up — a snapshot key that is
not provably unique defeats the whole point of binding a claim to "the"
item it names. ``_service_key_index`` below computes, once per build from
the WHOLE on-disk catalogue (never a domain-scoped subset — see its own
docstring for why), a key for every catalogue entry that is unique across
the ENTIRE catalogue by construction: unambiguous entries keep their
natural, human-readable display name unchanged (still verbatim what a
model is meant to echo back into ``Claim.price_service_key``); only the
genuinely colliding ones get a qualified ``"<sub_block>::<name>"`` form —
still copy-paste-able from the ``"key"`` field the model is shown on the
disambiguating item, never something the model has to construct from a
scheme it was never told. ``pricing_check.py``'s own binding is hardened
to match: a key claimed by more than one distinct item in a snapshot is
now refused as ambiguous rather than silently merged (see that module's
own comment on ``_snapshot_index_by_key``).

Author: Claude Opus 5 (lane B1b — client-bot engine; lane B1c —
service-identity binding + domain-scoped snapshot; lane B1d — qualified
keys unique by construction across the whole catalogue, 2026-08-25).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.channels.profiles import SurfaceProfile
from backend.services.client_bot.contracts import (
    EvidenceItem,
    GroundingBundle,
    HistoryTurn,
    PricingSnapshot,
)
from backend.services.pricing.pricing_service import (
    _NESTED_CATEGORIES,
    _entry_display_price,
    get_pricing_service,
)

logger = logging.getLogger("zantara.backend")

__all__ = ["DomainNotSpecifiedError", "EvidenceRetriever", "GroundingBundleBuilder"]

# Logged once per stubbed build() call — deliberately WARNING, not INFO:
# this is a standing condition worth an operator's attention every time it
# fires, not routine progress. Never includes `query` (client text — PII
# boundary, CLAUDE.md §14); `domain` is a closed, small vocabulary string.
_STUBBED_EVIDENCE_WARNING = (
    "grounding: evidence retrieval is STUBBED (no EvidenceRetriever wired) for "
    "domain=%r — this bundle carries zero evidence by construction. Every "
    "FinalPolicyGate check that depends on evidence (6/8/9) will fail closed "
    "(ABSTAIN/HANDOFF), which is SAFE, but NO shadow/containment/abstain-rate "
    "number computed against this call measures retrieval or answer quality — "
    "see GroundingBundleBuilder.evidence_retrieval_is_stubbed."
)

_PRICING_TOOL_VERSION = "pricing-service-2026"

# SPEC-price-service-binding.md P4 — which pricing-catalogue categories a
# domain "plausibly concerns" (a retrieval/filter step, never an
# exhaustive dump). This is a DELIBERATE JUDGMENT CALL, not a mapping
# ``PricingService`` itself exposes: the live 2026 catalogue's category
# names (see ``bali_zero_official_prices_2026.json``) do not line up 1:1
# with this channel layer's domain vocabulary
# (``backend.channels.profiles._REGULATED_DOMAINS``). Chosen to err toward
# OVER-inclusion, not precision: an under-scoped domain would make
# check_pricing wrongly HANDOFF a genuinely correct price (its service key
# would be entirely missing from the snapshot); an over-scoped one only
# widens the candidate pool a provider sees, which P1-P3's per-key binding
# still verifies correctly no matter how many unrelated items sit
# alongside the one actually claimed. "property" maps to zero categories
# on purpose — the 2026 catalogue carries no real-estate/property pricing
# rows at all, so a property-domain price claim always fails, correctly:
# this business has no PricingTool-backed property price to quote.
# "kbli" is intentionally absent — ``build()`` never calls
# ``_build_pricing_snapshot`` for that domain at all (see its own branch).
_DOMAIN_PRICING_CATEGORIES: dict[str, tuple[str, ...]] = {
    "immigration": (
        "single_entry_visas",
        "multiple_entry_visas",
        "kitas_permits",
        "kitap_permits",
        "urgent_processing",
        # Passport/SKTT/SKCK/Molina — civil-registry documents that come up
        # in the same immigration conversations as visas/KITAS.
        "other_process",
    ),
    "company": ("company_services", "consultant_services"),
    # consultant_services (NPWPD/BPJS/Coretax/EFIN registration) sits in
    # BOTH company and tax on purpose — it is genuinely a mix of
    # company-closure and tax-registration services, and duplicating a
    # category across two domain groups costs nothing but candidate-pool
    # size (see the "over-scoped" reasoning above).
    "tax": ("tax_accounting", "consultant_services"),
    "property": (),
}


class DomainNotSpecifiedError(ValueError):
    """Raised when ``build()`` is called with no explicit ``domain`` for a
    profile whose ``allowed_domains`` has more than one member — silently
    guessing a domain for a multi-domain surface is exactly the kind of
    unverified assumption CLAUDE.md §6 forbids.
    """


class EvidenceRetriever(Protocol):
    """A future lane's real KB/Qdrant retrieval. See module docstring for
    why no lane has wired this yet.
    """

    async def retrieve(self, query: str, domain: str) -> tuple[EvidenceItem, ...]: ...


# Namespace separator for a QUALIFIED key ("<sub_block or category>::<name>").
# Chosen over "/" deliberately: several real catalogue display names already
# contain a bare "/" (e.g. "Working KITAS (Altus/Onshore)", "Update Data /
# Coretax Activation" — verified against the live 2026 catalogue), so "/"
# would not visibly distinguish a qualified identifier from an ordinary
# display name that happens to contain one. No catalogue name contains "::".
_KEY_QUALIFIER_SEP = "::"


def _iter_service_entries_with_subblock(
    services_root: dict[str, Any],
) -> list[tuple[str, str | None, str, dict[str, Any]]]:
    """Same walk as ``pricing_service._iter_service_entries`` but additionally
    yields the nested sub-block name (``None`` for flat categories) — the one
    extra piece of context needed to build a collision-proof key when two
    services share the SAME dict key across different sub-blocks.

    Deliberately duplicated rather than changing
    ``_iter_service_entries``'s shared 3-tuple return shape: that function
    also backs ``PricingService.get_service_by_key()`` and its own
    load-time service count, neither of which is this lane's mandate to
    touch (``get_service_by_key`` has the identical first-match-wins
    limitation on a colliding name — noted, not fixed here; see this
    lane's report).
    """
    triples: list[tuple[str, str | None, str, dict[str, Any]]] = []
    for category_name, category_payload in services_root.items():
        if not isinstance(category_payload, dict):
            continue
        if category_name in _NESTED_CATEGORIES:
            for sub_block_name, sub_block in category_payload.items():
                if not isinstance(sub_block, dict):
                    continue
                for service_name, entry in sub_block.items():
                    if isinstance(entry, dict):
                        triples.append((category_name, sub_block_name, service_name, entry))
        else:
            for service_name, entry in category_payload.items():
                if isinstance(entry, dict):
                    triples.append((category_name, None, service_name, entry))
    return triples


def _service_key_index(
    services_root: dict[str, Any],
) -> dict[tuple[str, str | None, str], str]:
    """Maps every ``(category, sub_block, service_name)`` triple in the WHOLE
    catalogue to a key GUARANTEED unique across the ENTIRE catalogue —
    computed once from every entry, deliberately NOT scoped to any single
    domain's included categories.

    Why global, not per-snapshot: today's ``_DOMAIN_PRICING_CATEGORIES``
    never splits a colliding pair across two different domain snapshots
    (both live inside ``tax_accounting``, which is included or excluded as
    a whole), so a per-snapshot census would produce the identical result
    for every real query today — but tying the qualification DECISION to a
    domain-scoping heuristic that is itself "a deliberate judgment call,
    not a mapping PricingService itself exposes" (see
    ``_DOMAIN_PRICING_CATEGORIES``'s own comment) would make the same
    catalogue entry sometimes qualified and sometimes not depending on
    which domain happened to build the snapshot — a confusing, hard-to-audit
    property for an identity string a client-facing check binds a price to.
    A global, catalogue-wide census is a stable, static fact about the data
    itself, not an artifact of how one particular call scoped it.

    Most service names occur exactly once in the live 2026 catalogue and
    keep their natural, human-readable display name as the key unchanged
    from B1c — a model reading the snapshot echoes it back verbatim in
    ``Claim.price_service_key`` (contracts.py P2). The live catalogue has
    exactly 4 collisions today (verified 2026-08-25): "Tier 0-50",
    "Tier 50-100", "Tier 100-200", "Tier 200+" — each shared between
    ``tax_accounting``'s ``monthly_tax_basic`` (a tier-range price,
    LKPM/Annual Tax NOT included) and ``monthly_tax_bundled`` (a single
    price, LKPM + Annual Tax included) sub-blocks. A real spread of
    ~500k-1.5M IDR and a different scope of work sit behind the identical
    dict key. Those 4 pairs (8 items) get a qualified
    ``"<sub_block or category>::<service_name>"`` key instead — still a
    string a model can plausibly emit VERBATIM, because it is exactly the
    ``"key"`` field value the model is shown on the one disambiguating item
    it means to quote (never a scheme the model has to construct from
    nothing it was shown).

    Logs (never raises) if qualification still leaves a duplicate — see
    the "why log, not raise" note below.
    """
    all_triples = _iter_service_entries_with_subblock(services_root)
    name_counts = Counter(service_name for _category, _sub_block, service_name, _entry in all_triples)

    keys: dict[tuple[str, str | None, str], str] = {}
    for category, sub_block, service_name, _entry in all_triples:
        if name_counts[service_name] > 1:
            qualifier = sub_block or category
            keys[(category, sub_block, service_name)] = f"{qualifier}{_KEY_QUALIFIER_SEP}{service_name}"
        else:
            keys[(category, sub_block, service_name)] = service_name

    # Defensive, but deliberately NOT a raise: a residual collision after
    # qualification would need a pathological catalogue shape (e.g. a flat
    # category literally named the same as another category's sub-block,
    # both containing a same-named service — not the live 2026 data, which
    # test_service_key_index_is_unique_across_the_whole_real_catalogue
    # proves clean). If it ever happened, crashing here would take down
    # PRICING FOR THE ENTIRE ENGINE (this function runs once per
    # ``build()`` call, for every non-KBLI domain, with no try/except
    # around it) over ONE bad corner of the catalogue — a wildly
    # disproportionate blast radius for a data-quality problem that
    # ``pricing_check.py``'s own ``_snapshot_index_by_key`` already
    # defends against independently (a key claimed by 2+ distinct items is
    # refused there, per-claim, regardless of what produced the
    # snapshot — see that module's own comment). So: log loudly (an
    # operator must still fix the catalogue or the qualification scheme)
    # and let the check-layer's per-claim refusal be the actual backstop,
    # exactly the graceful-degradation posture the rest of this builder
    # already takes (cf. "PricingService not loaded" above: WARNING +
    # continue, never a crash).
    assigned_counts = Counter(keys.values())
    still_ambiguous = sorted(key for key, count in assigned_counts.items() if count > 1)
    if still_ambiguous:
        logger.error(
            "grounding: pricing catalogue has key(s) that remain ambiguous "
            "even after category/sub-block qualification: %r — a price "
            "claim naming any of these will be safely REFUSED downstream "
            "by pricing_check.py's own ambiguity check, not silently "
            "accepted, but this must still be resolved in the catalogue "
            "or the qualification scheme",
            still_ambiguous,
        )
    return keys


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_package_sha256(
    *,
    query: str,
    domain: str,
    evidence: tuple[EvidenceItem, ...],
    pricing: PricingSnapshot | None,
    history: tuple[HistoryTurn, ...],
    persona_digest: str,
) -> str:
    payload = {
        "query": query,
        "domain": domain,
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "pricing": pricing.model_dump(mode="json") if pricing is not None else None,
        "history": [h.model_dump(mode="json") for h in history],
        "persona_digest": persona_digest,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class GroundingBundleBuilder:
    def __init__(
        self,
        *,
        evidence_retriever: EvidenceRetriever | None = None,
        persona_digest: str = "zantara-persona-v1",
    ) -> None:
        self._evidence_retriever = evidence_retriever
        self._persona_digest = persona_digest

    @property
    def evidence_retrieval_is_stubbed(self) -> bool:
        """``True`` when this builder was constructed with no real
        ``EvidenceRetriever`` — every bundle it builds carries an empty
        ``evidence`` tuple regardless of the query. See the module
        docstring's "safe is not the same as measured" note. Check this
        BEFORE trusting any shadow/quality number produced from this
        builder's output — `ClientBotEngine` exposes the same signal.
        """
        return self._evidence_retriever is None

    async def build(
        self,
        *,
        query: str,
        profile: SurfaceProfile,
        domain: str | None = None,
        history: tuple[HistoryTurn, ...] = (),
    ) -> GroundingBundle:
        resolved_domain = self._resolve_domain(profile, domain)

        evidence: tuple[EvidenceItem, ...] = ()
        if self._evidence_retriever is not None:
            evidence = await self._evidence_retriever.retrieve(query, resolved_domain)
        else:
            logger.warning(_STUBBED_EVIDENCE_WARNING, resolved_domain)

        pricing = self._build_pricing_snapshot(resolved_domain) if resolved_domain != "kbli" else None

        package_sha256 = _compute_package_sha256(
            query=query,
            domain=resolved_domain,
            evidence=evidence,
            pricing=pricing,
            history=history,
            persona_digest=self._persona_digest,
        )

        return GroundingBundle(
            bundle_id=uuid.uuid4(),
            query=query,
            domain=resolved_domain,
            evidence=evidence,
            pricing=pricing,
            history=history,
            persona_digest=self._persona_digest,
            package_sha256=package_sha256,
        )

    @staticmethod
    def _resolve_domain(profile: SurfaceProfile, domain: str | None) -> str:
        if domain is not None:
            if domain not in profile.allowed_domains:
                logger.warning(
                    "grounding: explicit domain=%r not in profile %s's allowed_domains — "
                    "FinalPolicyGate check 5 will abstain, this is not silently corrected here",
                    domain,
                    profile.profile_id,
                )
            return domain
        if len(profile.allowed_domains) == 1:
            return next(iter(profile.allowed_domains))
        raise DomainNotSpecifiedError(
            f"{profile.profile_id} allows {sorted(profile.allowed_domains)!r} — "
            "an explicit domain is required, none was inferred"
        )

    def _build_pricing_snapshot(self, domain: str) -> PricingSnapshot | None:
        """Real PricingTool integration (Golden Rule 11) — never a
        hardcoded price. ``get_pricing_service()`` returns the same
        process-wide singleton ``PricingTool`` (services/rag/agentic/
        tools.py) already uses, so this builder and the existing RAG path
        can never disagree about what "the frozen pricing snapshot" means.

        SPEC-price-service-binding.md P1 + P4: ONE item PER SERVICE (never
        ``get_pricing("all")``'s single opaque catalogue blob), each
        carrying its catalogue key as a first-class ``"key"`` field, scoped
        to the categories ``_DOMAIN_PRICING_CATEGORIES`` maps this
        ``domain`` to. ``None`` still means "no snapshot at all" (tool not
        loaded / bad payload) — an empty ``items`` tuple for a domain that
        maps to zero categories (or an unrecognized domain) is a different,
        valid state: the tool IS working, there is simply nothing priced
        for this domain to quote.

        Lane B1d: the ``"key"`` field is no longer the bare catalogue dict
        key by default — it is whatever ``_service_key_index`` (built over
        the WHOLE catalogue, not just this domain's slice) assigned that
        entry, which is the bare name for every unambiguous service and a
        qualified ``sub_block::name`` for the 4 colliding tax-tier pairs.
        See ``_service_key_index``'s own docstring for the full rationale.
        """
        service = get_pricing_service()
        if not getattr(service, "loaded", False):
            logger.warning("grounding: PricingService not loaded — no PricingSnapshot built")
            return None

        categories = _DOMAIN_PRICING_CATEGORIES.get(domain)
        if categories is None:
            logger.warning(
                "grounding: no pricing-category mapping for domain=%r — pricing snapshot "
                "will carry zero items (safe default, see _DOMAIN_PRICING_CATEGORIES)",
                domain,
            )
            categories = ()

        services_root = service.prices.get("services", {})
        if not isinstance(services_root, dict):
            logger.warning(
                "grounding: PricingService.prices['services'] is not a dict — no items built"
            )
            services_root = {}

        key_index = _service_key_index(services_root)

        items: list[dict[str, object]] = []
        for category, sub_block, service_name, entry in _iter_service_entries_with_subblock(
            services_root
        ):
            if category not in categories:
                continue
            items.append(
                {
                    "key": key_index[(category, sub_block, service_name)],
                    "name": entry.get("name") or service_name,
                    "price": _entry_display_price(entry),
                    "category": category,
                    "validity": entry.get("validity") or None,
                    "notes": entry.get("notes") or None,
                }
            )

        snapshot_sha256 = hashlib.sha256(
            _canonical_json({"domain": domain, "items": items}).encode("utf-8")
        ).hexdigest()
        return PricingSnapshot(
            snapshot_id=uuid.uuid4(),
            pricing_tool_version=_PRICING_TOOL_VERSION,
            generated_at=datetime.now(timezone.utc),
            items=tuple(items),
            snapshot_sha256=snapshot_sha256,
        )
