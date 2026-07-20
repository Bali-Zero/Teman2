"""Resolves a persona fixture's ``expected`` block into a normalized,
per-product expectation record -- shared by the replay test and the report
generator so both consume the exact same oracle logic.

Two authoring tiers per persona (see each persona JSON's ``expected`` key):

1. **Explicit** (``expected["products"][<code>]``): hand-authored, the
   persona's actual point -- e.g. "C1 is SUPPORTED with these reason codes".
   Asserted verbatim.
2. **Default** (``expected["default"]``): applies to every product NOT
   listed explicitly. Two kinds, both independently checkable against the
   COMPILED PACK alone (never against the adapter's own output -- that would
   be circular):
   - ``UNSUPPORTED_NO_PURPOSE_OVERLAP``: valid only for a product whose own
     ``covered_purposes`` (from the compiled pack) does not intersect the
     persona's requested purposes at all -- structurally, no ELIGIBILITY
     rule on that product could ever put it in ``true_support`` for any of
     the requested purposes, so the outcome is a mechanical
     ``UNSUPPORTED`` with ``missing_purposes`` = the full requested set.
     ``resolve_expected`` RAISES if a persona tries to apply this default to
     a product whose purposes DO overlap -- that product needs an explicit
     entry (see ``adapter.py``'s module docstring point 1 and the
     19-07-2026 audit that caught exactly this gap for E33G against three
     TOURISM-only personas before it shipped).
   - ``DOMINANT_GLOBAL``: a GLOBAL HARD_FILTER/HUMAN_REVIEW rule in the
     designed pack fires identically for every product (this harness's pack
     never scopes a HARD_FILTER/HUMAN_REVIEW rule to PRODUCTS), so every
     product collapses to the same EXCLUDED/REVIEW/BLOCKED_UNKNOWN outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.services.visa_engine.compiler import CompiledRulePack

from .harness_utils import product_by_code


@dataclass(frozen=True, slots=True)
class ExpectedProof:
    proof_state: str
    reason_codes: tuple[str, ...] = ()
    covered_purposes: frozenset[str] = field(default_factory=frozenset)
    missing_purposes: frozenset[str] = field(default_factory=frozenset)
    missing_facts: tuple[str, ...] | None = None  # None = not asserted for this entry


def _product_covered_purposes(pack: CompiledRulePack, product_code: str) -> frozenset[str]:
    product = product_by_code(pack, product_code)
    return frozenset(p.value for p in product.product.covered_purposes)


def resolve_expected(
    persona_expected: dict[str, Any], product_code: str, pack: CompiledRulePack
) -> ExpectedProof:
    explicit = persona_expected.get("products", {})
    if product_code in explicit:
        e = explicit[product_code]
        return ExpectedProof(
            proof_state=e["proof_state"],
            reason_codes=tuple(e.get("reason_codes", ())),
            covered_purposes=frozenset(e.get("covered_purposes", ())),
            missing_purposes=frozenset(e.get("missing_purposes", ())),
            missing_facts=tuple(e["missing_facts"]) if "missing_facts" in e else None,
        )

    default = persona_expected.get("default")
    if default is None:
        raise ValueError(
            f"persona expected block has no explicit entry for {product_code!r} and no 'default'"
        )

    kind = default["kind"]
    if kind == "UNSUPPORTED_NO_PURPOSE_OVERLAP":
        requested = frozenset(default["requested_purposes"])
        product_covered = _product_covered_purposes(pack, product_code)
        overlap = product_covered & requested
        if overlap:
            raise ValueError(
                f"product {product_code!r} covers purpose(s) {sorted(overlap)} that overlap "
                f"the persona's requested purposes {sorted(requested)} -- this product needs "
                "an EXPLICIT expected entry, the structural no-overlap default does not apply"
            )
        return ExpectedProof(proof_state="UNSUPPORTED", missing_purposes=requested)

    if kind == "DOMINANT_GLOBAL":
        reason_codes = tuple(default.get("reason_codes", ()))
        missing_facts = persona_expected.get("default_missing_facts")
        return ExpectedProof(
            proof_state=default["state"],
            reason_codes=reason_codes,
            missing_facts=tuple(missing_facts) if missing_facts is not None else None,
        )

    raise ValueError(f"unknown default kind {kind!r}")
