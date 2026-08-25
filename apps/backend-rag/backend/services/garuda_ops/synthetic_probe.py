"""SYN-01 synthetic purchase probe, per `products/garuda-voa/journeys/SLO.md`:

    "Synthetic eligibility -> local OCR feedback -> sandbox checkout ->
    valid signed sandbox webhook -> paid -> one Received practice. ... If no
    complete signed result is recorded within 15 minutes of its scheduled
    start, set the public flag off and alert the owner. A late probe cannot
    auto-enable the flag."

**Honest state, corrected 2026-08-25 (staleness tripwire finding)**: only
the first stage can run for real. L1's retention-policy migration (281)
merged, but seeds no GARUDA_CHECK policy row -- `garuda_flow/public_api.py`
fails closed by construction until Zero signs one
(`get_garuda_check_store()` still returns `UnconfiguredCheckStore`). L3's
order/payment-port package (`garuda_orders/`, `payments/xendit.py`) and its
router are merged and mounted, but the orchestrator's composition step has
not yet wired a real `GarudaOrderRepository`/`PaymentProvider` onto
`app.state` -- every request 503s by design
(`test_blocked_stage_staleness.py` holds the mechanical proxy for each of
these). L4's portal has no practice-serving module yet, and no production
code wires `garuda_ops/crm_handoff.py`'s `CrmHandoffService` to a real
event journal either. Faking success for stages 2-5 would be exactly the
"green mascherava organi morti" failure this lane was explicitly warned
against (cicatrix-superscar.md family #2). Each stage below either runs for
real or raises `StageBlockedOnDependency` naming the blocking lane — the
runner records that distinction and the dead-man verdict (`deadman.py`) is
computed honestly from it: **a probe that cannot complete end-to-end is
correctly DEAD**, not a passing green with an asterisk. This matches the
product's own current state ("ship dark, flag off") — the probe is not
lying about a live system, it is accurately reporting a system not yet
capable of the journey it must eventually run.

**A prose reason has no mechanism keeping it in sync with the codebase it
describes** — `test_blocked_stage_staleness.py` is that mechanism: it
expresses each `_blocked_stage` reason below as a mechanically checkable
predicate and goes RED the moment the predicate stops holding, rather than
leaving a stage BLOCKED on a stale sentence nobody is looking at.

The runner is otherwise stage-agnostic: once each stage's real precondition
is met, its `_blocked_stage` placeholder is replaced by a real
implementation with no change to `run_probe` or to the dead-man wiring.
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
    "orchestrator",
    # CORRECTED 2026-08-25 (staleness tripwire finding): L3 merged (#4893) --
    # services/garuda_orders/ (8 modules) and services/payments/xendit.py
    # both exist, and garuda_orders_router.py is mounted. The REAL remaining
    # blocker is the orchestrator's own composition step: get_repository()
    # in garuda_orders_router.py fails closed with 503 until a real
    # GarudaOrderRepository is assigned onto
    # app.state.garuda_order_repository, which no production file does yet
    # (see test_blocked_stage_staleness.py::test_sandbox_checkout_claim_is_still_true).
    "L3's order/payment-port package is merged, but no production code "
    "wires a real GarudaOrderRepository onto app.state.garuda_order_repository "
    "yet -- get_repository() in garuda_orders_router.py fails closed with 503",
)
SignedWebhookStage = _blocked_stage(
    "signed_webhook_paid",
    "orchestrator",
    # CORRECTED 2026-08-25 (staleness tripwire finding): the Xendit
    # sandbox adapter (services/payments/xendit.py) and the webhook route
    # (garuda_orders_router.py:receive_payment_webhook) both exist and are
    # mounted. The REAL remaining blocker, same composition gap as
    # sandbox_checkout: no production code assigns
    # app.state.garuda_payment_provider, so the route 503s before it can
    # ever call verify_signature/parse_event.
    "the Xendit sandbox webhook adapter and route are merged, but no "
    "production code wires a real PaymentProvider onto "
    "app.state.garuda_payment_provider yet -- the route fails closed with 503",
)
ReceivedPracticeStage = _blocked_stage(
    "received_practice",
    "orchestrator",
    # CORRECTED (same staleness-tripwire class as sandbox_checkout /
    # signed_webhook_paid above): `services/garuda_portal/practice.py` now
    # exists and PR-01 is real -- `PracticeRepository.get_order_and_
    # practice_view` mints a `Received` practice the moment it observes a
    # paid order, and `garuda_orders_router.py::get_order_and_practice`
    # calls it instead of hardcoding `None`. The REAL remaining blocker is
    # upstream of this stage entirely: `sandbox_checkout`/`signed_webhook_
    # paid` above are themselves still blocked on the orchestrator's own
    # composition gap (no production code wires `app.state.garuda_order_
    # repository` / `app.state.garuda_payment_provider`), so this probe
    # never reaches a genuinely paid order to hand this stage in the first
    # place -- `run_probe` stops at the first non-success (see its own
    # comment) two stages before this one runs. This stage's own
    # capability is no longer the gap; the pipeline upstream of it is.
    "L4's garuda_portal/practice module is real (PR-01 implemented, "
    "wired into garuda_orders_router.py), but this stage is still "
    "unreachable in run_probe -- sandbox_checkout/signed_webhook_paid "
    "block first on the SAME orchestrator composition gap those stages "
    "already name",
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
        except Exception as exc:  # deliberate broad catch, see below
            # Corrected after cross-family refuter review (Kimi K3,
            # 2026-08-25, finding 9): an unexpected exception used to
            # escape `run_probe` entirely, leaving NO bound `ProbeRunResult`
            # — SYN-01's "one signed probe result binds ALL stage outcomes"
            # cannot be honoured for a crash if there is no result to bind.
            # A real regression must produce a FAILED result (which flows
            # into `all_succeeded=False`, same as any other non-success),
            # not vanish into cron logs where nothing downstream can
            # classify it. This is intentionally the broadest possible
            # catch — a stage crashing for any reason is still real signal.
            result = ProbeStageResult(stage.name, ProbeStageStatus.FAILED, repr(exc))
        results.append(result)
        if result.status != ProbeStageStatus.SUCCEEDED:
            # SYN-01 binds ALL stage outcomes into one result — a probe that
            # cannot complete a stage does not attempt the next one, which
            # would depend on state the failed/blocked stage never produced.
            break
    return ProbeRunResult(tuple(results))
