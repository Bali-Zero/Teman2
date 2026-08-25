"""Check 7 — PricingTool enforcement (research capture Sol §1.6).

"Every currency amount and service/variant combination must exactly match
the frozen PricingSnapshot. The model cannot recompute, round, convert, or
combine prices unless PricingTool supplied that exact result. No pricing
snapshot means no price may be stated." Failure: POLICY_BLOCKED, normally
HANDOFF, not provider fallback (check 7 is explicitly NOT eligible for the
one-retry TEXT_DEFECT path — a fabricated price is not a formatting defect).
GateReason's own comment permits either verdict; this module always
returns HANDOFF — the "normally HANDOFF" branch (a price question deserves
a human follow-up, not a bare block) — verified against the B6b golden
fixture "client.pricing-correct-and-invented"/invented variant.
POLICY_BLOCKED is the alternate terminal verdict for a repeat/abusive
case, which this stateless check has no way to detect (no per-actor
attempt history is available here) — a future lane may escalate to it.

Golden Rule 11 ("PricingTool Only. All prices from PricingTool. Never
hardcode.") makes this the check most likely to reach a real client with a
real wrong number, so it is deliberately STRICTER than the existing
``wa_finalize.py::price_tokens_outside_sources`` veto it is inspired by:
that function also accepts amounts found in retrieved KB chunks (legitimate
for regulatory fees quoted from a source, not from PricingTool); this check
accepts ONLY amounts present in ``GroundingBundle.pricing`` — a
Bali-Zero-service price with no PricingSnapshot backing is an unsupported
claim regardless of what a retrieved chunk happens to say near it.

The currency-amount extraction logic (multiplier canonicalization,
newline-safety, per-token source extraction) is adapted from that same
proven implementation rather than re-derived — see its own comments for the
three concrete adversarial cases it defends against (an amount must never
cross a newline or absorb a following bare number; "Rp 99 juta" must
canonicalize identically to "Rp 99.000.000"; source numbers are extracted
per TOKEN, never a whole-string concatenation). Duplicated rather than
imported (contracts.py's own precedent: a services/client_bot/-layer
contract file does not reach into services/integrations/ for this) — see
module docstring in contracts.py for the same call on ``_SHA256_HEX``.

SPEC-price-service-binding.md (2026-08-25) — service-identity binding
(P1/P2/P3): "verbatim match against the snapshot" alone answers "is this
amount A real Bali Zero price anywhere", never "is this amount THE price
of the service actually under discussion". Two amounts can both be real
(e.g. E33G KITAS Rp 12.000.000 and Working KITAS Rp 25.000.000) and a
candidate can quote the WRONG one for the question asked — the catalogue-
wide check below (layer 1, unchanged, kept for candidates that carry no
structural claim at all) cannot see that; it can only see "25.000.000 is
a real number somewhere". The per-claim binding below (layer 2, new) is
what catches it: a "price" claim now carries ``price_service_key``
(contracts.py P2), and this module verifies the amount(s) IN THAT CLAIM'S
OWN TEXT against ONLY the matching ``PricingSnapshot`` item's price, never
the whole catalogue. Layer 1 stays because ``PricingSnapshot`` items are
not required to carry an identity at all (a caller may hand this a
snapshot built by hand, pre-dating P1) and a bare currency amount with no
claim behind it (check 6's territory, untouched here) still needs a
some-real-number-somewhere floor.

This module deliberately has NO visibility into ``GroundingBundle.history``
— it receives only ``candidate`` and ``pricing``. A price claim whose
service was established in a PRIOR conversation turn must still carry its
own ``price_service_key`` on THIS turn's claim; binding it correctly from
prior-turn context is the generating provider's job, upstream of this
check, not something re-derived here from conversation history. Stated
explicitly per the orchestrator's 2026-08-25 ruling ("that decision must be
stated, not left for the implementation to settle by accident").

Author: Claude Opus 5 (lane B1b — client-bot engine; lane B1c — P1-P5
service-identity binding, 2026-08-25).
"""

from __future__ import annotations

import re

from backend.services.client_bot.contracts import BrainCandidate, PricingSnapshot
from backend.services.client_bot.policy.check_result import CheckOutcome
from backend.services.client_bot.policy.types import GateReason, GateVerdict

__all__ = ["check_pricing"]

_AMOUNT_MULTIPLIERS: dict[str, float] = {
    "k": 1e3,
    "rb": 1e3,
    "ribu": 1e3,
    "jt": 1e6,
    "juta": 1e6,
    "miliar": 1e9,
    "milyar": 1e9,
    "bn": 1e9,
    "triliun": 1e12,
}
_MULT_PATTERN = r"(?:jt|juta|rb|ribu|k|miliar|milyar|bn|triliun)"
_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:(?P<cur1>\bRp\.?|\bIDR|\bUSD|\$)[ \t]*(?P<amt1>\d(?:[\d.,]*\d)?)"
    r"(?:[ \t]*(?P<mul1>" + _MULT_PATTERN + r")\b)?)"
    r"|(?:(?P<amt2>\d(?:[\d.,]*\d)?)(?:[ \t]*(?P<mul2>" + _MULT_PATTERN + r")\b)?"
    r"[ \t]*(?P<cur2>IDR|USD)\b)",
    re.IGNORECASE,
)
# IDR prices below Rp 1.000 do not exist in this business (and would fire on
# noise); dollar prices are real from $10 up. Same floors as wa_finalize.py.
_VETO_FLOORS: dict[str, int] = {"USD": 10, "IDR": 1000}


def _canonical_currency(cur: str) -> str:
    c = cur.strip().rstrip(".").upper()
    return "USD" if c in ("$", "USD") else "IDR"


def _canonical_value(amount: str, multiplier: str | None) -> int | None:
    s = amount.strip()
    if not s:
        return None
    if multiplier:
        normalized = s.replace(",", ".")
        try:
            if normalized.count(".") == 1 and len(normalized.split(".")[1]) <= 2:
                base = float(normalized)
            else:
                base = float(re.sub(r"[.,]", "", s))
        except ValueError:
            return None
        return int(round(base * _AMOUNT_MULTIPLIERS[multiplier.lower()]))
    digits = re.sub(r"[.,]", "", s)
    if not digits.isdigit():
        return None
    return int(digits)


def _currency_amounts(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for m in _CURRENCY_AMOUNT_RE.finditer(text):
        cur = m.group("cur1") or m.group("cur2") or ""
        amt = m.group("amt1") or m.group("amt2") or ""
        mul = m.group("mul1") or m.group("mul2")
        value = _canonical_value(amt, mul)
        if value is not None:
            out.append((_canonical_currency(cur), value))
    return out


def _walk_numeric_values(node: object, values: set[int]) -> None:
    """Every canonical numeric value reachable inside ``node`` — a price
    entry's ``price``/``tier_range`` fields are formatted strings
    ("790.000 IDR"), not raw numbers (``PricingService``'s own 2026
    schema), so this walks every string value rather than assuming a fixed
    key name. Per-token, same as ``_currency_amounts`` — never a
    whole-dict-concatenation. ``values`` is mutated in place so this can be
    called once per whole snapshot (layer 1) or once per single item
    (layer 2, P1-P3) without re-deriving the walk.
    """
    if isinstance(node, dict):
        for v in node.values():
            _walk_numeric_values(v, values)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _walk_numeric_values(v, values)
    elif isinstance(node, str):
        for _cur, value in _currency_amounts(node):
            values.add(value)
        for token in re.findall(r"\d(?:[\d.,]*\d)?", node):
            value = _canonical_value(token, None)
            if value is not None:
                values.add(value)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        values.add(int(node))


def _snapshot_values(pricing: PricingSnapshot) -> set[int]:
    """Every canonical numeric value reachable ANYWHERE in the snapshot,
    merged across every item — the catalogue-wide "is this a real Bali
    Zero price at all" test (layer 1). This is deliberately the ONLY
    question this function answers; it is NOT a substitute for
    ``_snapshot_index_by_key`` below, which is what actually binds an
    amount to the specific service it must price.
    """
    values: set[int] = set()
    for item in pricing.items:
        _walk_numeric_values(item, values)
    return values


def _item_identity(item: dict[str, object]) -> str | None:
    """An item's stable service identity, if it declares one.

    ``GroundingBundleBuilder._build_pricing_snapshot`` (P1) names it
    ``"key"`` — mirroring ``PricingService.get_service_by_key()``'s own
    return shape. Some hand-authored ``PricingSnapshot`` fixtures pre-date
    that binding and use ``"service"`` instead (B6b's ``PRICING_CORRECT``/
    ``PRICING_INVENTED`` goldens, authorized verbatim by the 2026-08-25
    orchestrator ruling on the frozen-fixture collision) — both are
    recognized so neither shape is silently unbound. An item with neither
    field has no identity a claim can bind to; callers treat that as "key
    not found", the same as any other absent key.
    """
    for field_name in ("key", "service"):
        value = item.get(field_name)
        if isinstance(value, str) and value:
            return value
    return None


def _snapshot_index_by_key(pricing: PricingSnapshot) -> dict[str, set[int]]:
    """Maps each item's declared identity to the numeric value(s) reachable
    INSIDE THAT ITEM ALONE (P1-P3) — the structural binding a price claim's
    ``price_service_key`` is checked against: "the amount(s)... must match
    THAT item's price, and only that item's", never the whole catalogue
    (``_snapshot_values`` above).

    If two items happen to share the same identity string (a real,
    pre-existing limitation of ``PricingService.get_service_by_key()``:
    the live 2026 catalogue has duplicate service names across different
    sub-categories, e.g. "Tier 0-50" in both ``monthly_tax_basic`` and
    ``monthly_tax_bundled``), their value sets are merged rather than one
    silently overwriting the other — permissive (either underlying price
    is accepted for that name) but never wrong in the direction that
    matters here: it can never accept an amount that belongs to some
    THIRD, unrelated service.
    """
    index: dict[str, set[int]] = {}
    for item in pricing.items:
        key = _item_identity(item)
        if key is None:
            continue
        index.setdefault(key, set())
        _walk_numeric_values(item, index[key])
    return index


def check_pricing(candidate: BrainCandidate, pricing: PricingSnapshot | None) -> CheckOutcome | None:
    """None means pass. A price-kind claim always counts as "price-bearing"
    even if its text carries no regex-detectable amount (a claim the model
    labeled ``kind="price"`` with no PricingTool backing at all is still a
    price claim it must not make) — the currency-amount scan additionally
    catches a price asserted in prose that was never inventoried as a claim
    at all (defense in depth with check 6, not a substitute for it: a model
    that both omits the price claim AND states a number is caught here even
    if check 6 has not run yet in a given call order).

    Two layers, in order:

    1. Catalogue-wide (unchanged): every currency amount anywhere in
       ``candidate.answer`` must be a real number SOMEWHERE in the
       snapshot. Catches a fabricated number outright; cannot catch a real
       number attached to the wrong service (SPEC-price-service-binding.md).
    2. Per-claim service binding (P1-P3, new): every "price" claim's OWN
       ``price_service_key`` must resolve to an item in the snapshot, and
       every amount detected in THAT CLAIM'S OWN ``text`` must match ONLY
       that item's price. This is what catches a real price quoted for the
       wrong service — the defect this spec exists to close.
    """
    price_claims = [c for c in candidate.claims if c.kind == "price"]
    amounts_in_answer = _currency_amounts(candidate.answer)

    if pricing is None:
        if price_claims or amounts_in_answer:
            return CheckOutcome(
                verdict=GateVerdict.HANDOFF,
                reason=GateReason.NO_PRICING_SNAPSHOT_AVAILABLE,
                reason_detail="no_pricing_snapshot_available",
            )
        return None

    snapshot_values = _snapshot_values(pricing)

    for cur, value in amounts_in_answer:
        if value < _VETO_FLOORS[cur]:
            continue
        if value not in snapshot_values:
            return CheckOutcome(
                verdict=GateVerdict.HANDOFF,
                reason=GateReason.PRICE_NOT_IN_SNAPSHOT,
                reason_detail="quoted_amount_not_in_snapshot",
            )

    if price_claims and not amounts_in_answer:
        # A price-kind claim exists but the answer text carries no
        # regex-detectable currency amount at all — the model asserted a
        # price claim without ever writing a matchable number (e.g. a
        # recomputed/derived phrase like "twice the standard fee"). That is
        # exactly PRICE_RECOMPUTED_BY_MODEL: a price relationship the
        # snapshot did not supply verbatim.
        return CheckOutcome(
            verdict=GateVerdict.HANDOFF,
            reason=GateReason.PRICE_RECOMPUTED_BY_MODEL,
            reason_detail="price_recomputed_not_verbatim",
        )

    # Layer 2 — service-identity binding (SPEC-price-service-binding.md
    # P1-P3). Every "price" claim's ``kind`` guarantees (contracts.py's own
    # model_validator) that ``price_service_key`` is populated here — there
    # is no branch for "kind is price but the key is missing" because that
    # candidate could never have been constructed.
    if price_claims:
        by_key = _snapshot_index_by_key(pricing)
        for claim in price_claims:
            claim_amounts = _currency_amounts(claim.text)
            if not claim_amounts:
                # No regex-detectable amount in THIS claim's own text — the
                # answer-level RECOMPUTED branch above already fires when
                # the whole answer has no amount either; a claim whose own
                # text is bare prose but some OTHER claim/sentence in the
                # answer does carry an amount has nothing here to bind.
                continue
            claimed_key = claim.price_service_key
            assert claimed_key is not None, (
                "unreachable: Claim's own model_validator requires "
                "price_service_key whenever kind == 'price'"
            )
            allowed_values = by_key.get(claimed_key)
            if allowed_values is None:
                # The claimed service key names nothing this snapshot
                # carries at all (scoped out of the domain, or simply
                # absent) — no price for that service exists to compare
                # against, which is the same failure mode as an amount
                # that is not in the snapshot at all.
                return CheckOutcome(
                    verdict=GateVerdict.HANDOFF,
                    reason=GateReason.PRICE_NOT_IN_SNAPSHOT,
                    reason_detail="price_service_key_not_in_snapshot",
                )
            for cur, value in claim_amounts:
                if value < _VETO_FLOORS[cur]:
                    continue
                if value not in allowed_values:
                    # The amount IS a real number somewhere in the whole
                    # catalogue (layer 1 above already let it through) but
                    # NOT the price of the service this claim itself names
                    # — a real price for the wrong service.
                    return CheckOutcome(
                        verdict=GateVerdict.HANDOFF,
                        reason=GateReason.PRICE_NOT_IN_SNAPSHOT,
                        reason_detail="quoted_amount_not_for_claimed_service",
                    )

    return None
