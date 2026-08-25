"""SYN-01 synthetic purchase probe, per `products/garuda-voa/journeys/SLO.md`:

    "Synthetic eligibility -> local OCR feedback -> sandbox checkout ->
    valid signed sandbox webhook -> paid -> one Received practice. ... If no
    complete signed result is recorded within 15 minutes of its scheduled
    start, set the public flag off and alert the owner. A late probe cannot
    auto-enable the flag."

**Honest state at the time this lane was built**: only the first stage can
run for real. L1 (retention policy, prerequisite for ANY persistence per
`garuda_flow/public_api.py`'s own docstring), L3 (checkout/orders/payments)
and L4/L5 (portal/documents) had not merged (LANES.md: L3 `blocked (owner
decision 1)`; no `garuda_orders`/`garuda_portal`/`garuda_documents` package
existed). Faking success for stages 2-5 would be exactly the "green
mascherava organi morti" failure this lane was explicitly warned against
(cicatrix-superscar.md family #2). Each stage below either runs for real or
raises `StageBlockedOnDependency` naming the blocking lane — the runner
records that distinction and the dead-man verdict (`deadman.py`) is computed
honestly from it: **a probe that cannot complete end-to-end is correctly
DEAD**, not a passing green with an asterisk. This matches the product's own
current state ("ship dark, flag off") — the probe is not lying about a live
system, it is accurately reporting a system not yet capable of the journey
it must eventually run.

The runner is otherwise stage-agnostic: once L1/L3/L4/L5 land, each
`StageBlockedOnDependency` stage is replaced by a real implementation with
no change to `run_probe` or to the dead-man wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Protocol

from backend.services.garuda_flow.intake import CaseType, Purpose
from backend.services.garuda_flow.public_api import PriceUnresolvable, evaluate_public_check

# A fixture guaranteed ACCEPT under `eligibility.screen` at any `today` this
# probe runs on: issuance, well inside validity, tourism, single traveller,
# self-pay, no prior extension. If this ever declines, the engine itself
# regressed — which is exactly what stage 1 exists to catch.
_SYNTHETIC_NATIONALITY = "AUS"


def _synthetic_entry_and_expiry(today: date) -> tuple[date, date, date | None]:
    # +10 days clears both the issuance submission cutoff (submit_by_date is
    # the last open day strictly BEFORE entry_date — same-day/next-day entry
    # can decline as ARRIVAL_TOO_SOON) and the eVOA usability window, without
    # depending on where `today` falls relative to a weekend/cuti bersama.
    entry_date = today + timedelta(days=10)
    passport_expiry_date = date(today.year + 2, today.month, min(today.day, 28))
    return entry_date, passport_expiry_date, None


class ProbeStageStatus(str, Enum):
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"  # a downstream lane's dependency has not merged yet
    FAILED = "failed"  # ran, and the system misbehaved — a real regression


@dataclass(frozen=True, slots=True)
class ProbeStageResult:
    name: str
    status: ProbeStageStatus
    detail: str


class StageBlockedOnDependency(Exception):
    def __init__(self, blocking_lane: str, reason: str) -> None:
        self.blocking_lane = blocking_lane
        self.reason = reason
        super().__init__(f"blocked on {blocking_lane}: {reason}")


class ProbeStage(Protocol):
    name: str

    async def run(self, *, today: date) -> ProbeStageResult: ...


class EligibilityVerdictStage:
    """Stage 1/5: the pure verdict+price computation — no persistence, no
    network. This is real today; `evaluate_public_check` does no I/O."""

    name = "eligibility_verdict"

    async def run(self, *, today: date) -> ProbeStageResult:
        entry_date, passport_expiry_date, voa_expiry_date = _synthetic_entry_and_expiry(today)
        try:
            outcome = evaluate_public_check(
                case_type=CaseType.ISSUANCE,
                nationality=_SYNTHETIC_NATIONALITY,
                entry_date=entry_date,
                passport_expiry_date=passport_expiry_date,
                voa_expiry_date=voa_expiry_date,
                purpose=Purpose.TOURISM,
                travellers=1,
                self_pay=True,
                extension_already_used=False,
                today=today,
            )
        except PriceUnresolvable as exc:
            return ProbeStageResult(self.name, ProbeStageStatus.FAILED, str(exc))

        if not outcome.accepted:
            return ProbeStageResult(
                self.name,
                ProbeStageStatus.FAILED,
                f"synthetic fixture declined: {[c.value for c in outcome.reason_codes]}",
            )
        return ProbeStageResult(self.name, ProbeStageStatus.SUCCEEDED, "accepted with price")


def _blocked_stage(name: str, blocking_lane: str, reason: str) -> type[ProbeStage]:
    class _Blocked:
        def __init__(self) -> None:
            self.name = name

        async def run(self, *, today: date) -> ProbeStageResult:
            return ProbeStageResult(
                name, ProbeStageStatus.BLOCKED, f"{blocking_lane}: {reason}"
            )

    return _Blocked


PersistenceStage = _blocked_stage(
    "persistence_policy",
    "L1",
    "no signed retention-policy row for garuda_voa_checks yet — "
    "garuda_flow/public_api.py fails closed by design until it exists",
)
SandboxCheckoutStage = _blocked_stage(
    "sandbox_checkout",
    "L3",
    "no order/payment-port package exists (owner decision 1: payment provider)",
)
SignedWebhookStage = _blocked_stage(
    "signed_webhook_paid",
    "L3",
    "no payment-port/webhook implementation exists yet",
)
ReceivedPracticeStage = _blocked_stage(
    "received_practice",
    "L4",
    "no garuda_portal/practice package exists yet",
)

DEFAULT_STAGES: tuple[type[ProbeStage], ...] = (
    EligibilityVerdictStage,
    PersistenceStage,
    SandboxCheckoutStage,
    SignedWebhookStage,
    ReceivedPracticeStage,
)


@dataclass(frozen=True, slots=True)
class ProbeRunResult:
    stage_results: tuple[ProbeStageResult, ...]

    @property
    def all_succeeded(self) -> bool:
        return all(r.status == ProbeStageStatus.SUCCEEDED for r in self.stage_results)

    @property
    def first_non_success(self) -> ProbeStageResult | None:
        for r in self.stage_results:
            if r.status != ProbeStageStatus.SUCCEEDED:
                return r
        return None


async def run_probe(
    stages: tuple[type[ProbeStage], ...] = DEFAULT_STAGES, *, today: date
) -> ProbeRunResult:
    results = []
    for stage_cls in stages:
        stage = stage_cls()
        try:
            result = await stage.run(today=today)
        except StageBlockedOnDependency as exc:
            # A future real stage implementation may discover its
            # dependency is unmet only at run time (e.g. a feature flag
            # still off) — this is the other legal way to report BLOCKED,
            # alongside a stage that already knows it is blocked (the
            # `_blocked_stage` placeholders above).
            result = ProbeStageResult(
                stage.name, ProbeStageStatus.BLOCKED, str(exc)
            )
        results.append(result)
        if result.status != ProbeStageStatus.SUCCEEDED:
            # SYN-01 binds ALL stage outcomes into one result — a probe that
            # cannot complete a stage does not attempt the next one, which
            # would depend on state the failed/blocked stage never produced.
            break
    return ProbeRunResult(tuple(results))
