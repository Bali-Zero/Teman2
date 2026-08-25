"""ClientBotEngine — the top-level orchestrator tying every B1b module
together (research capture Sol §1.1 runtime flow, MANDATE.md F1).

Runtime flow, one call to `handle()`: ConversationContextLoader.load() ->
GroundingBundleBuilder.build() -> ClientBrainProviderRouter.route() ->
FinalPolicyGate.evaluate() -> (regenerate once, only on TEXT_DEFECT) ->
per-surface send-gate check -> EngineResult.

SHIPS DARK by construction (team-lead mandate — "everything OFF behind a
dark flag using kill-switch names CLIENT_BOT_{WA,IG,PORTAL,KBLI}_SEND_
ENABLED"): every one of the four send-gate settings
(`client_bot_{wa,ig,portal,kbli}_send_enabled`, config.py) defaults False,
and — as of this lane's diff — no adapter, router, or webhook handler
anywhere in the repo imports `ClientBotEngine` at all. Calling `handle()`
today changes NOTHING about what WhatsApp/Instagram/Portal/KBLI widget do
in production, because nothing calls it — not because a flag happens to
be off.

`AllProvidersExhaustedError` -> a terminal `FinalDecision(verdict=HANDOFF,
reason=PROVIDERS_EXHAUSTED)` built directly here, NEVER routed through
`FinalPolicyGate.evaluate()` — there is no candidate to evaluate (see
`GateReason.PROVIDERS_EXHAUSTED`'s own docstring, policy/types.py, and
`provider_router.py`'s module docstring, which names this exact split).

The one-retry rule (Sol §1.6, closing line) is `FinalDecision.is_retryable`
itself — only a TEXT_DEFECT verdict is retried, and only once, replaying
the SAME frozen `BrainRequest` (never a different one): evidence, pricing,
assignment, and safety failures are never "fixed" by asking a provider the
same question again against the same frozen facts.

`run_shadow()` (provider_router.py's routing rule 6) is deliberately NOT
called from `handle()` — its own docstring already frames it as a
separate, explicit, non-blocking method a caller MAY invoke after
`route()` returns, not a step this orchestrator owns; wiring a shadow-leg
cron/hook is a future lane's decision, not something to bolt onto the
critical path silently.

`DeliveryFence` (check 1, `final_gate.py`) needs LIVE thread-ownership
state this engine cannot originate on its own — the outbox worker wired to
`wa_broker`'s CAS primitives owns that in production. With no
`delivery_fence_probe` injected, this engine fails CLOSED (every fence
field reports "not owned" -> check 1 DROPs every request) — the same
fail-safe-by-default posture `FinalPolicyGate`'s own optional collaborators
already establish (see its class docstring), never an optimistic "assume
I own the thread" default.

Known, documented inefficiency (not a correctness bug): check 1 depends
only on `fence`, never on the candidate, but this engine still generates a
candidate before evaluating it even when the fence will DROP the result —
avoiding a wasted provider call would mean duplicating check 1's exact
ordering from `final_gate.py` in a second place, a maintenance risk this
first cut deliberately avoids taking on.

**Evidence retrieval is a stub, and every `EngineResult` says so (team
lead, 2026-08-25).** `GroundingBundleBuilder`'s default `EvidenceRetriever`
is empty (see its own module docstring) — with no retriever wired, checks
6/8/9 abstain/handoff on every claim that needs evidence, which is SAFE
but is NOT a measurement: a 100%-handoff shadow run against a stubbed
engine and a 100%-handoff shadow run against a correctly-retrieving one
are indistinguishable from the verdicts alone. `EngineResult.
evidence_retrieval_stubbed` (mirrored on `ClientBotEngine.
evidence_retrieval_is_stubbed`) makes that fact a structural part of every
single result this engine returns, not a fact a caller has to already know
or dig out of a log — check it before treating any containment/abstain-
rate number computed from this engine as a quality signal. **No shadow
number from this engine measures answer quality until the RAG seam
(`GroundingBundleBuilder`'s `EvidenceRetriever`) is wired.**

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from backend.channels.models import CanonicalMessage, ClientSurface
from backend.channels.profiles import PROFILES_BY_SURFACE
from backend.services.client_bot.context import ConversationContextLoader
from backend.services.client_bot.contracts import BrainRequest
from backend.services.client_bot.grounding import GroundingBundleBuilder
from backend.services.client_bot.observability import (
    client_bot_containment_total,
    client_bot_gate_eval_seconds,
    client_bot_response_latency_seconds,
    record_gate_verdict,
)
from backend.services.client_bot.policy.final_gate import DeliveryFence, FinalPolicyGate
from backend.services.client_bot.policy.types import FinalDecision, GateReason, GateVerdict
from backend.services.client_bot.provider_router import (
    AllProvidersExhaustedError,
    ClientBrainProviderRouter,
    ProviderAttempt,
)

logger = logging.getLogger("zantara.backend")

__all__ = ["ClientBotEngine", "EngineResult", "SendGateCheck", "default_send_gate_from_settings"]


class SendGateCheck(Protocol):
    """Reads exactly one of the four per-surface send-gate settings
    (`client_bot_{wa,ig,portal,kbli}_send_enabled`, config.py — the same
    rows `kill_switches.py` registers under `TripwirePlane.CLIENT_SEND`).
    Injected rather than importing `Settings` directly, so this module —
    and its tests — carries no import-time coupling to the app-wide config
    singleton, the same pattern `ClientBrainProviderRouter.from_settings()`
    already uses for provider config.
    """

    def __call__(self, surface: ClientSurface) -> bool: ...


def default_send_gate_from_settings(settings: object) -> SendGateCheck:
    """App-wiring convenience for a future caller: reads the 4 kill-
    switch-registry env vars once via the live `Settings` singleton.
    `settings` is typed `object` for the same reason
    `ClientBrainProviderRouter.from_settings()` types it that way — no
    import-time dependency on `backend.app.core.config`.
    """
    by_surface = {
        ClientSurface.WHATSAPP: "client_bot_wa_send_enabled",
        ClientSurface.INSTAGRAM: "client_bot_ig_send_enabled",
        ClientSurface.PORTAL: "client_bot_portal_send_enabled",
        ClientSurface.KBLI_WIDGET: "client_bot_kbli_send_enabled",
    }

    def _check(surface: ClientSurface) -> bool:
        attr = by_surface.get(surface)
        if attr is None:
            return False
        return bool(getattr(settings, attr, False))

    return _check


def _fail_closed_fence(_message: CanonicalMessage) -> DeliveryFence:
    """Default when the caller wires no live thread-ownership probe — see
    module docstring for why this fails CLOSED rather than optimistically
    open.
    """
    return DeliveryFence(
        thread_owned=False,
        thread_epoch_current=False,
        human_taken_over=False,
        terminal_response_already_sent=False,
        service_window_expired=False,
    )


def _providers_exhausted_decision(request_id: UUID, attempts: tuple[ProviderAttempt, ...]) -> FinalDecision:
    summary = ",".join(f"{a.provider_name}:{a.kind.value}" for a in attempts) or "no_eligible_provider"
    return FinalDecision(
        decision_id=uuid.uuid4(),
        request_id=request_id,
        verdict=GateVerdict.HANDOFF,
        reason=GateReason.PROVIDERS_EXHAUSTED,
        reason_detail=summary[:200],
        rendered_text=None,
        evaluated_at=datetime.now(timezone.utc),
    )


@dataclass(frozen=True)
class EngineResult:
    """What `ClientBotEngine.handle()` returns. `should_send` is the ONLY
    field a caller needs to decide whether to actually deliver
    `decision.rendered_text` — it is `False` whenever the per-surface send
    gate is off (shadow mode) REGARDLESS of `decision.verdict`, so a
    caller can never accidentally deliver a shadow-mode ALLOW by reading
    `decision.verdict` alone.

    `evidence_retrieval_stubbed` is the OTHER field every caller must read
    before drawing a conclusion from `decision`: `True` means this specific
    call ran with zero real evidence retrieval (see module docstring's
    "safe is not the same as measured" note) — a caller building a shadow-
    run summary, a containment-rate dashboard, or any other quality signal
    from a batch of `EngineResult`s MUST check this on every one, because
    it can flip per-call once a real `EvidenceRetriever` exists (a
    per-domain rollout is a realistic future shape, not a hypothetical).
    """

    decision: FinalDecision
    should_send: bool
    regenerated: bool
    evidence_retrieval_stubbed: bool


class ClientBotEngine:
    def __init__(
        self,
        *,
        provider_router: ClientBrainProviderRouter,
        context_loader: ConversationContextLoader | None = None,
        grounding_builder: GroundingBundleBuilder | None = None,
        policy_gate: FinalPolicyGate | None = None,
        send_gate: SendGateCheck | None = None,
        delivery_fence_probe: Callable[[CanonicalMessage], DeliveryFence] | None = None,
    ) -> None:
        self._provider_router = provider_router
        self._context_loader = context_loader or ConversationContextLoader()
        self._grounding_builder = grounding_builder or GroundingBundleBuilder()
        self._policy_gate = policy_gate or FinalPolicyGate()
        # None means "always OFF" — the fail-dark default the module
        # docstring promises: a caller that forgets to wire a send gate at
        # all gets shadow mode, never an accidental live send.
        self._send_gate: SendGateCheck = send_gate or (lambda _surface: False)
        self._delivery_fence_probe = delivery_fence_probe or _fail_closed_fence

    @property
    def evidence_retrieval_is_stubbed(self) -> bool:
        """Mirrors `GroundingBundleBuilder.evidence_retrieval_is_stubbed` —
        exposed here too so a caller never has to reach past this engine
        into its collaborator to find out. See module docstring.
        """
        return self._grounding_builder.evidence_retrieval_is_stubbed

    async def handle(self, message: CanonicalMessage, *, domain: str | None = None) -> EngineResult:
        started = time.monotonic()
        profile = PROFILES_BY_SURFACE[message.surface]

        history = await self._context_loader.load(message.conversation_id, profile)
        grounding = await self._grounding_builder.build(
            query=message.text or "", profile=profile, domain=domain, history=history
        )
        request = BrainRequest(
            request_id=uuid.uuid4(),
            message=message,
            profile=profile,
            grounding=grounding,
            deadline_at=datetime.now(timezone.utc) + timedelta(milliseconds=profile.provider_deadline_ms),
        )
        fence = self._delivery_fence_probe(message)

        try:
            decision, regenerated = await self._route_and_evaluate(request, fence)
        except AllProvidersExhaustedError as exc:
            decision = _providers_exhausted_decision(request.request_id, exc.attempts)
            regenerated = False

        surface_value = message.surface.value
        record_gate_verdict(surface_value, decision.verdict.value, decision.reason.value)
        if decision.verdict == GateVerdict.ALLOW:
            client_bot_containment_total.labels(surface=surface_value).inc()
        client_bot_response_latency_seconds.labels(surface=surface_value).observe(time.monotonic() - started)

        should_send = decision.verdict == GateVerdict.ALLOW and self._send_gate(message.surface)
        if decision.verdict == GateVerdict.ALLOW and not should_send:
            logger.info(
                "client-bot engine: ALLOW on request %s but surface %s send gate is OFF — "
                "shadow mode, not delivered",
                request.request_id,
                surface_value,
            )

        return EngineResult(
            decision=decision,
            should_send=should_send,
            regenerated=regenerated,
            evidence_retrieval_stubbed=self._grounding_builder.evidence_retrieval_is_stubbed,
        )

    async def _route_and_evaluate(
        self, request: BrainRequest, fence: DeliveryFence
    ) -> tuple[FinalDecision, bool]:
        decision = await self._generate_and_gate(request, fence)
        if not decision.is_retryable:
            return decision, False

        # One regeneration attempt (Sol §1.6, closing line) — only
        # TEXT_DEFECT is eligible; the SAME frozen request/grounding is
        # replayed, never a different one, so the regenerated candidate is
        # judged against the identical facts the first attempt saw.
        logger.info(
            "client-bot engine: TEXT_DEFECT (%s) on request %s — regenerating once",
            decision.reason.value,
            request.request_id,
        )
        decision = await self._generate_and_gate(request, fence)
        return decision, True

    async def _generate_and_gate(self, request: BrainRequest, fence: DeliveryFence) -> FinalDecision:
        candidate = await self._provider_router.route(request)
        gate_started = time.monotonic()
        decision = await self._policy_gate.evaluate(candidate, request, fence)
        client_bot_gate_eval_seconds.labels(surface=request.message.surface.value).observe(
            time.monotonic() - gate_started
        )
        return decision
