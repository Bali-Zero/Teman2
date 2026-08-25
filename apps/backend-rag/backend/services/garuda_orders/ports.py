"""Cross-lane seam: L3 depends on this Protocol, never on L2's table shape.

`products/garuda-voa/LANES.md` scopes `garuda_voa_checks` / the new public
eligibility-check store to L2. L3 needs one fact from it — the frozen
case_type of a reviewed, creator-owned check — to create an order. The
orchestrator wires the real adapter at router-composition time, the same
seam pattern L2 already used for `CheckStore` over `UnconfiguredCheckStore`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.services.garuda_flow.intake import CaseType


@dataclass(frozen=True, slots=True)
class ReviewedCheckSnapshot:
    result_id: str
    case_type: CaseType
    review_confirmed: bool


class EligibilityCheckLookup(Protocol):
    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        """None for malformed/absent/non-owned — the router turns that into
        the contract's non-enumerating RESULT_NOT_FOUND, never a 401/403
        that would disclose existence."""
        ...


class UnconfiguredEligibilityCheckLookup:
    """Fails closed until the orchestrator wires the real L2 adapter.

    Mirrors `garuda_flow.public_api.UnconfiguredCheckStore` — the same
    "no caller wired yet, fail closed rather than pretend" shape.
    """

    async def get_reviewed_check(self, result_id: str) -> ReviewedCheckSnapshot | None:
        raise RuntimeError(
            "EligibilityCheckLookup not configured — the orchestrator must wire "
            "the real L2 adapter before createOrderFromCheck can serve traffic"
        )


__all__ = ["EligibilityCheckLookup", "ReviewedCheckSnapshot", "UnconfiguredEligibilityCheckLookup"]
