"""Tripwire: every `_blocked_stage` reason in `synthetic_probe.py` makes a
factual claim about the codebase ("this package doesn't exist yet", "no
adapter is wired onto app.state yet"). A hand-maintained prose reason has
no mechanism forcing someone to come back and edit it once the thing it
names has shipped — the failure mode is not "green mascherava organi
morti" (family #2), it is the opposite: a stage stays BLOCKED, and the
whole SYN-01 probe stays DEAD, long after its stated reason stopped being
true, because nothing red ever tells anyone to look.

Each test below expresses one stage's reason as a mechanically checkable
predicate over the actual codebase (file existence, a specific
`app.state.*` assignment, a specific function's return type) and asserts
the predicate still holds. Deliberately NOT a keyword grep of the reason
string (cicatrix-superscar.md family #3, guard-over-match) — each
assertion checks the underlying fact the prose describes, independent of
how the string is worded. When a lane ships the thing a reason names, the
predicate goes false and the corresponding test goes RED: that red is the
actionable signal, "this stage is ready to be unblocked (or its reason
needs to be rewritten to the real remaining blocker) — go look."
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.app.routers.garuda_voa_public import get_garuda_check_store
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.public_api import UnconfiguredCheckStore
from backend.services.garuda_ops.synthetic_probe import DEFAULT_STAGES, ProbeStageStatus

_TODAY = garuda_today()

# apps/backend-rag/backend/tests/services/garuda_ops/test_x.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]

# The exact set of stage names this file has a predicate for. The meta-test
# below asserts the DEFAULT_STAGES's actual BLOCKED names equal this set —
# so a newly-added `_blocked_stage` with no predicate here fails loudly
# instead of silently escaping coverage.
_STAGES_WITH_A_STALENESS_PREDICATE = frozenset(
    {"persistence_policy", "sandbox_checkout", "signed_webhook_paid", "received_practice"}
)


def _production_python_files() -> list[Path]:
    """Every `.py` file this backend ships, excluding its own test tree and
    the local virtualenv — the files that could plausibly wire a real
    adapter onto `app.state`."""
    files = []
    for path in _BACKEND_ROOT.rglob("*.py"):
        parts = path.parts
        if "tests" in parts or ".venv" in parts:
            continue
        files.append(path)
    return files


def _any_production_file_matches(pattern: re.Pattern[str]) -> bool:
    for path in _production_python_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pattern.search(text):
            return True
    return False


@pytest.mark.asyncio
async def test_every_currently_blocked_stage_has_a_staleness_predicate() -> None:
    """Forces coverage to stay complete: if `DEFAULT_STAGES` grows a 5th
    BLOCKED stage (or one of today's 4 stops being BLOCKED), this test
    fails until `_STAGES_WITH_A_STALENESS_PREDICATE` — and a predicate test
    below it — is updated to match."""
    blocked_names = set()
    for stage_cls in DEFAULT_STAGES:
        result = await stage_cls().run(today=_TODAY)
        if result.status is ProbeStageStatus.BLOCKED:
            blocked_names.add(result.name)
    assert blocked_names == _STAGES_WITH_A_STALENESS_PREDICATE


def test_persistence_policy_claim_is_still_true() -> None:
    """persistence_policy's reason: "no signed retention-policy row for
    garuda_voa_checks yet -- garuda_flow/public_api.py fails closed by
    design until it exists". The live DB row is not something a unit test
    can see, but `public_api.py`'s own docstring names the mechanical
    proxy: a real adapter is wired in "by replacing the
    `get_garuda_check_store` dependency in the router" — as long as that
    dependency still returns `UnconfiguredCheckStore`, no adapter has been
    wired and the claim holds."""
    store = get_garuda_check_store()
    assert isinstance(store, UnconfiguredCheckStore), (
        "get_garuda_check_store() no longer returns UnconfiguredCheckStore -- "
        "a real CheckStore adapter has been wired in. persistence_policy's "
        "reason is stale: go verify a signed GARUDA_CHECK retention-policy "
        "row actually exists, then unblock the stage."
    )


def test_sandbox_checkout_claim_is_still_true() -> None:
    """sandbox_checkout's reason claims: "no order/payment-port package
    exists (owner decision 1: payment provider)". FALSE as of this PR --
    `services/garuda_orders/` (8 modules) and `services/payments/xendit.py`
    both exist, and `garuda_orders_router.py` is mounted
    (`router_manifest.py`/`router_registration.py`). This is the red-first
    proof: the package claim is stale, which is exactly why this test
    checks the package's ACTUAL remaining precondition instead --
    `get_repository()` in `garuda_orders_router.py` fails closed with 503
    until the orchestrator assigns a real `GarudaOrderRepository` onto
    `app.state.garuda_order_repository`, which no production file does
    (only `test_webhook_router.py` does, for its own fakes)."""
    assignment = re.compile(r"garuda_order_repository\s*=(?!=)")
    assert not _any_production_file_matches(assignment), (
        "a production file now assigns app.state.garuda_order_repository -- "
        "sandbox_checkout's real blocker (no orchestrator wiring) may be "
        "gone. Go verify end-to-end and unblock the stage."
    )


def test_signed_webhook_paid_claim_is_still_true() -> None:
    """signed_webhook_paid's reason claims: "no payment-port/webhook
    implementation exists yet". FALSE as of this PR --
    `services/payments/xendit.py` implements `verify_signature`/
    `parse_event`/`refund` against `payments/port.py`'s `PaymentProvider`,
    and `garuda_orders_router.py:receive_payment_webhook` calls both. The
    real remaining precondition: `request.app.state.garuda_payment_provider`
    is read (never assigned) by that route outside tests, so every real
    callback still 503s."""
    assignment = re.compile(r"garuda_payment_provider\s*=(?!=)")
    assert not _any_production_file_matches(assignment), (
        "a production file now assigns app.state.garuda_payment_provider -- "
        "signed_webhook_paid's real blocker (no orchestrator wiring) may be "
        "gone. Go verify end-to-end and unblock the stage."
    )


def test_received_practice_claim_is_still_true() -> None:
    """received_practice's reason (post-L4-practice-module correction):
    "L4's garuda_portal/practice module is real ... but this stage is
    still unreachable ... sandbox_checkout/signed_webhook_paid block first
    on the SAME orchestrator composition gap".

    CORRECTED (team-lead review, 2026-08-25): the first version of this
    predicate checked `services/garuda_portal/practice.py`'s mere
    existence by FIXED PATH -- one step better than the glob it replaced
    (`sorted(p.name for p in garuda_portal_dir.glob("*practice*"))`,
    #4912's own recorded dissent on that PR), but still a filename check,
    not a behavioural one: a refactor that renamed `practice.py` to
    `progress.py` while keeping the class/wiring intact would fail this
    test for the WRONG reason (file missing) even though the capability
    is fully alive, and a refactor that gutted the wiring but left the
    file's name untouched would pass it for the WRONG reason too. Two
    behavioural predicates replace it, mirroring the shape
    `test_sandbox_checkout_claim_is_still_true` /
    `test_signed_webhook_paid_claim_is_still_true` already use (a
    regex over ACTUAL CODE BEHAVIOUR, immune to which file it lives in):

    1. A production file still calls `PracticeRepository(...).
       get_order_and_practice_view(...)` -- the wiring `garuda_orders_
       router.py::get_order_and_practice` actually performs, independent
       of which module defines the class or what it is named on disk.
    2. No production file still returns the OLD hardcoded
       `"practice": None` literal `get_order_and_practice` used to answer
       unconditionally before this wiring existed -- a direct regression
       guard: if that literal ever comes back, this assertion (not just
       the router's own tests) catches it.

    What must ALSO stay true (unchanged from the prior version): the
    stage is STILL unreachable via the SAME two upstream composition gaps
    `test_sandbox_checkout_claim_is_still_true` /
    `test_signed_webhook_paid_claim_is_still_true` already check -- if
    either goes stale (a production file starts assigning
    `app.state.garuda_order_repository` or `app.state.garuda_payment_
    provider`), THIS stage's reason is equally stale, because `run_probe`
    would then be able to reach a real paid order and hand it to this
    stage for the first time."""
    wiring_call = re.compile(r"PracticeRepository\([^)]*\)\.get_order_and_practice_view\(")
    assert _any_production_file_matches(wiring_call), (
        "no production file calls PracticeRepository(...).get_order_and_practice_view(...) "
        "-- received_practice's reason claims this wiring is real and answers "
        "get_order_and_practice. Go verify and rewrite the reason to whatever "
        "actually serves (or fails to serve) practice now."
    )
    hardcoded_null_practice = re.compile(r'"practice"\s*:\s*None')
    assert not _any_production_file_matches(hardcoded_null_practice), (
        'a production file still returns the literal "practice": None -- '
        "received_practice's reason claims that hardcode was replaced by real "
        "PR-01 serving. Regression: go verify get_order_and_practice again."
    )
    order_repo_assignment = re.compile(r"garuda_order_repository\s*=(?!=)")
    payment_provider_assignment = re.compile(r"garuda_payment_provider\s*=(?!=)")
    assert not _any_production_file_matches(order_repo_assignment), (
        "a production file now assigns app.state.garuda_order_repository -- "
        "received_practice's real blocker (the SAME orchestrator composition "
        "gap sandbox_checkout names) may be gone too. Go verify end-to-end "
        "and unblock the stage."
    )
    assert not _any_production_file_matches(payment_provider_assignment), (
        "a production file now assigns app.state.garuda_payment_provider -- "
        "received_practice's real blocker (the SAME orchestrator composition "
        "gap signed_webhook_paid names) may be gone too. Go verify end-to-end "
        "and unblock the stage."
    )
