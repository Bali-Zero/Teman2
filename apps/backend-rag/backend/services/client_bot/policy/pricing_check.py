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

Author: Claude Opus 5 (lane B1b — client-bot engine).
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


def _snapshot_values(pricing: PricingSnapshot) -> set[int]:
    """Every canonical numeric value reachable inside the frozen snapshot's
    items — a price entry's ``price``/``tier_range`` fields are formatted
    strings ("790.000 IDR"), not raw numbers (``PricingService``'s own
    2026 schema), so this walks every string value in every item dict
    rather than assuming a fixed key name. Per-token, same as
    ``_currency_amounts`` — never a whole-dict-concatenation.
    """
    values: set[int] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                _walk(v)
        elif isinstance(node, str):
            for _cur, value in _currency_amounts(node):
                values.add(value)
            for token in re.findall(r"\d(?:[\d.,]*\d)?", node):
                value = _canonical_value(token, None)
                if value is not None:
                    values.add(value)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            values.add(int(node))

    for item in pricing.items:
        _walk(item)
    return values


def check_pricing(candidate: BrainCandidate, pricing: PricingSnapshot | None) -> CheckOutcome | None:
    """None means pass. A price-kind claim always counts as "price-bearing"
    even if its text carries no regex-detectable amount (a claim the model
    labeled ``kind="price"`` with no PricingTool backing at all is still a
    price claim it must not make) — the currency-amount scan additionally
    catches a price asserted in prose that was never inventoried as a claim
    at all (defense in depth with check 6, not a substitute for it: a model
    that both omits the price claim AND states a number is caught here even
    if check 6 has not run yet in a given call order).
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

    return None
