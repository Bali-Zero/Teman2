"""FinalPolicyGate — the 11 ordered checks, one FinalDecision (research
capture Sol §1.6). "It never 'fixes' regulatory facts in free text."

Checks 1 (delivery/thread fence), 2 (schema/package integrity — the parts
not already structurally guaranteed by ``BrainCandidate``'s own pydantic
types), and 4 (explicit disposition) are implemented directly in this
module — they are either trivial dispatch on the candidate's own fields
(check 4) or need live/injected state a pure function cannot own (check 1's
``DeliveryFence``, check 11's idempotency probe). Checks 3/5/6/7/8/9/10/11
(text) delegate to the four sibling ``policy/*_check.py`` modules Sol's own
layout names.

Check 4's handoff branch ALWAYS normalizes to
``GateReason.MODEL_REQUESTED_HANDOFF`` — it does not echo
``candidate.handoff_reason_code`` into the gate's own reason (verified
against both B6b golden fixtures in
``client.handoff-insert-succeeds-and-fails``, which use the identical
model-supplied ``handoff_reason_code`` for both the succeeds- and
fails-insert variants and expect the SAME ``GateReason`` either way). What
distinguishes a real handoff from a failed one is ``reason_detail``, set
from ``ClientHandoffService.create_handoff()``'s own
``HandoffOutcome`` (F10: the durable insert is attempted BEFORE this gate
is allowed to return HANDOFF at all, never after).

Only ``TEXT_DEFECT`` is eligible for the one provider fallback/regeneration
(``FinalDecision.is_retryable``) — evidence, pricing, assignment, and
safety failures are never "fixed" by asking another provider the same
question against the same frozen facts (Sol §1.6, closing line). This
module does not implement that retry itself — the caller (``engine.py``)
owns the "regenerate once on TEXT_DEFECT" loop, calling ``evaluate()``
again with the regenerated candidate.

``evaluate()`` is async (Golden Rule 4): its collaborators
(``semantic_verifier``, the handoff service) may do real I/O.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.services.client_bot.contracts import BrainCandidate, BrainRequest
from backend.services.client_bot.policy import (
    egress_check,
    evidence_check,
    pricing_check,
    surface_check,
)
from backend.services.client_bot.policy.evidence_check import SemanticVerifier
from backend.services.client_bot.policy.handoff import ClientHandoffService
from backend.services.client_bot.policy.types import FinalDecision, GateReason, GateVerdict

logger = logging.getLogger("zantara.backend")

__all__ = ["DeliveryFence", "FinalPolicyGate"]

# No NUL, and no C0 control characters other than the three whitespace
# forms an answer legitimately contains (\t \n \r). Matches check 2's
# "Valid UTF-8; no NUL/control payload" line — Python str is already
# guaranteed valid Unicode by the time it reaches here (decoding happens
# at the provider/JSON boundary, out of this module's scope); what a
# pydantic str field does NOT reject on its own is a stray control byte
# that decoded successfully but has no business in client-facing prose.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class DeliveryFence:
    """Check 1's live state — computed by the caller (the outbox worker /
    engine, wired to the existing wa_broker CAS primitives), never by this
    gate. A pure ``FinalPolicyGate`` cannot know whether a human has taken
    over a thread; it can only ask.
    """

    thread_owned: bool
    thread_epoch_current: bool
    human_taken_over: bool
    terminal_response_already_sent: bool
    service_window_expired: bool


class FinalPolicyGate:
    """Stateless except for its injected collaborators — construct once,
    call ``evaluate()`` per candidate. Collaborators are optional and
    fail-safe by default (see each parameter's docstring) so a gate built
    with zero wiring still behaves SAFELY (never a false ALLOW), just more
    conservatively than a fully-wired one.
    """

    def __init__(
        self,
        *,
        semantic_verifier: SemanticVerifier | None = None,
        handoff_service: ClientHandoffService | None = None,
        idempotency_probe: Callable[[], bool] | None = None,
        canary_tokens: Sequence[str] = (),
    ) -> None:
        self._semantic_verifier = semantic_verifier
        # None means "no repository wired" — ClientHandoffService itself
        # already fails safe to ROW_INSERT_FAILED in that case; a gate
        # built with zero wiring still gets a real (conservative) service.
        self._handoff_service = handoff_service or ClientHandoffService()
        # None means "no live probe wired — defer to the outbox table's own
        # UNIQUE(wamid)-style constraint as the actual dedup authority"
        # (wa_broker.py already has one). A probe that returns False means
        # an ACTUAL conflict was detected at this specific call site.
        self._idempotency_probe = idempotency_probe
        self._canary_tokens = tuple(canary_tokens)

    async def evaluate(
        self, candidate: BrainCandidate, request: BrainRequest, delivery_fence: DeliveryFence
    ) -> FinalDecision:
        verdict, reason, reason_detail, rendered_text = await self._run_checks(
            candidate, request, delivery_fence
        )
        return FinalDecision(
            decision_id=uuid.uuid4(),
            request_id=request.request_id,
            verdict=verdict,
            reason=reason,
            reason_detail=reason_detail,
            rendered_text=rendered_text,
            evaluated_at=datetime.now(timezone.utc),
        )

    async def _run_checks(
        self, candidate: BrainCandidate, request: BrainRequest, fence: DeliveryFence
    ) -> tuple[GateVerdict, GateReason, str | None, str | None]:
        # Check 1 — delivery and thread fence (-> DROP, never regenerated).
        if not fence.thread_owned:
            return GateVerdict.DROP, GateReason.THREAD_OWNERSHIP_LOST, None, None
        if not fence.thread_epoch_current:
            return GateVerdict.DROP, GateReason.THREAD_EPOCH_STALE, None, None
        if fence.human_taken_over:
            return GateVerdict.DROP, GateReason.HUMAN_TAKEOVER_ACTIVE, None, None
        if fence.terminal_response_already_sent:
            return GateVerdict.DROP, GateReason.DUPLICATE_TERMINAL_RESPONSE, None, None
        if fence.service_window_expired:
            return GateVerdict.DROP, GateReason.SERVICE_WINDOW_EXPIRED, None, None

        # Check 2 — schema/package integrity (schema_version and unknown-field
        # shape are already structurally guaranteed by BrainCandidate's own
        # frozen pydantic type by the time a real instance reaches here —
        # see this module's docstring; only hash equality and control-byte
        # scanning are genuine runtime concerns).
        if candidate.package_sha256 != request.grounding.package_sha256:
            return GateVerdict.TEXT_DEFECT, GateReason.PACKAGE_HASH_MISMATCH, None, None
        if _CONTROL_CHAR_RE.search(candidate.answer):
            return GateVerdict.TEXT_DEFECT, GateReason.INVALID_ENCODING, None, None

        # Check 3 — secret/internal-reasoning/instruction-scaffold egress.
        egress_outcome = egress_check.check_egress(candidate.answer, self._canary_tokens)
        if egress_outcome is not None:
            return egress_outcome.verdict, egress_outcome.reason, egress_outcome.reason_detail, None

        # Check 5 — surface/domain boundary. Runs BEFORE check 4's
        # disposition dispatch, out of Sol's literal numeric order: domain
        # scope is a structural fact of request.grounding.domain vs.
        # request.profile — computable independently of what the candidate
        # decided to do, and MORE SPECIFIC than a generic self-abstain when
        # both apply. Verified against the B6b golden fixture
        # "client.kbli-outside-widget-domain": the candidate there is
        # itself an abstain (the model correctly declined), yet the fixture
        # requires DOMAIN_OUT_OF_SURFACE_SCOPE, not MODEL_ABSTAINED — the
        # gate's own structural judgment about domain scope must not be
        # demoted to the model's generic self-report.
        domain_outcome = surface_check.check_domain_boundary(
            request.message, request.profile, request.grounding.domain
        )
        if domain_outcome is not None:
            return domain_outcome.verdict, domain_outcome.reason, domain_outcome.reason_detail, None

        # Check 4 — explicit disposition and safety.
        if candidate.disposition == "abstain":
            return GateVerdict.ABSTAIN, GateReason.MODEL_ABSTAINED, None, None
        if candidate.disposition == "handoff":
            outcome = await self._handoff_service.create_handoff(candidate, request)
            return GateVerdict.HANDOFF, GateReason.MODEL_REQUESTED_HANDOFF, outcome.value, None

        # From here, disposition == "answer" — checks 6-11 apply.
        citation_policy_all_factual = request.grounding.domain == "kbli"

        inventory_outcome = evidence_check.check_claim_inventory(candidate)
        if inventory_outcome is not None:
            return inventory_outcome.verdict, inventory_outcome.reason, inventory_outcome.reason_detail, None

        pricing_outcome = pricing_check.check_pricing(candidate, request.grounding.pricing)
        if pricing_outcome is not None:
            return pricing_outcome.verdict, pricing_outcome.reason, pricing_outcome.reason_detail, None

        support_outcome = await evidence_check.check_evidence_support(
            candidate,
            request.grounding,
            citation_policy_all_factual=citation_policy_all_factual,
            semantic_verifier=self._semantic_verifier,
        )
        if support_outcome is not None:
            return support_outcome.verdict, support_outcome.reason, support_outcome.reason_detail, None

        citation_outcome = evidence_check.check_citation_integrity(
            candidate, request.grounding, citation_policy_all_factual=citation_policy_all_factual
        )
        if citation_outcome is not None:
            return citation_outcome.verdict, citation_outcome.reason, citation_outcome.reason_detail, None

        render_outcome, rendered_text = surface_check.check_render_and_length(
            candidate, request.message, request.profile
        )
        if render_outcome is not None:
            return render_outcome.verdict, render_outcome.reason, render_outcome.reason_detail, None

        # Check 11 (idempotency half) — recheck immediately before the
        # caller would insert into the outbox.
        if self._idempotency_probe is not None and not self._idempotency_probe():
            return GateVerdict.TEXT_DEFECT, GateReason.IDEMPOTENCY_CONFLICT_AT_INSERT, None, None

        return GateVerdict.ALLOW, GateReason.PASSED_ALL_CHECKS, None, rendered_text
