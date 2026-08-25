"""GateVerdict / GateReason / FinalDecision — the FinalPolicyGate output contract.

Frozen per docs/plans/2026-08-25-due-bot-live/MANDATE.md F1 and
research/operations/2026-08-25-due-bot-7-lens-research.md §1.6.

``FinalPolicyGate.evaluate()`` itself (``final_gate.py`` + the per-check
modules — ``evidence_check.py``, ``pricing_check.py``, ``egress_check.py``,
``surface_check.py``) is explicitly OUT OF SCOPE for this unit. This module
only freezes the TYPES that gate produces and consumes: the 6-member
``GateVerdict`` (verbatim from §1.6), a ``GateReason`` taxonomy that names
every specific failure mode the 11 ordered checks describe, and the
``FinalDecision`` record that carries one of each plus the atomic rendered
text when (and only when) the verdict is ``ALLOW``.

Author: Claude Opus 5 (lane B1a — client-bot contract freeze)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "FinalDecision",
    "GateReason",
    "GateVerdict",
]


class GateVerdict(StrEnum):
    """The 6 members are frozen verbatim (research capture §1.6)."""

    ALLOW = "allow"
    ABSTAIN = "abstain"
    HANDOFF = "handoff"
    TEXT_DEFECT = "text_defect"
    POLICY_BLOCKED = "policy_blocked"
    DROP = "drop"


class GateReason(StrEnum):
    """One member per named failure mode across the 11 ordered checks (§1.6).

    This enum is an INVENTION grounded in the check descriptions — the
    research capture names failure modes in prose ("the outbox worker no
    longer owns the message", "the event has already produced a terminal
    response", ...) but never enumerates them as a closed type. Member
    names transcribe that prose; they are NOT prefixed with a check number
    so a future reordering of the 11 checks does not force a rename. See
    the report's decision log for the full mapping check-by-check.

    Deliberately NOT validated against GateVerdict here (e.g. "only these
    reasons may pair with ABSTAIN") — that mapping is FinalPolicyGate
    business logic, which owns the check ordering and is out of scope for
    this contract-freeze unit. Baking a verdict<->reason lookup table into
    the frozen type would duplicate a table the gate itself must own.
    """

    # Terminal success (no failure) — always paired with GateVerdict.ALLOW.
    PASSED_ALL_CHECKS = "passed_all_checks"

    # Check 1 — delivery and thread fence (-> DROP)
    THREAD_OWNERSHIP_LOST = "thread_ownership_lost"
    THREAD_EPOCH_STALE = "thread_epoch_stale"
    HUMAN_TAKEOVER_ACTIVE = "human_takeover_active"
    DUPLICATE_TERMINAL_RESPONSE = "duplicate_terminal_response"
    SERVICE_WINDOW_EXPIRED = "service_window_expired"

    # Check 2 — candidate schema and package integrity (-> TEXT_DEFECT)
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    UNKNOWN_FIELD_PRESENT = "unknown_field_present"
    INVALID_ENCODING = "invalid_encoding"
    PACKAGE_HASH_MISMATCH = "package_hash_mismatch"
    BOUNDS_EXCEEDED = "bounds_exceeded"

    # Check 3 — secret/internal-reasoning/instruction-scaffold egress
    # (-> TEXT_DEFECT, or terminal POLICY_BLOCKED for a canary/secret hit)
    SECRET_EGRESS_DETECTED = "secret_egress_detected"
    INTERNAL_REASONING_LEAK = "internal_reasoning_leak"
    INSTRUCTION_SCAFFOLD_LEAK = "instruction_scaffold_leak"
    CANARY_HIT = "canary_hit"

    # Check 4 — explicit disposition and safety (-> ABSTAIN or HANDOFF)
    MODEL_ABSTAINED = "model_abstained"
    MODEL_REQUESTED_HANDOFF = "model_requested_handoff"
    OUT_OF_SCOPE_REGULATED_REQUEST = "out_of_scope_regulated_request"
    HUMAN_DECISION_REQUIRED = "human_decision_required"

    # Engine-level — not one of the 11 ordered FinalPolicyGate checks against
    # a candidate, because no candidate exists to check (-> HANDOFF). Added
    # B1b: the B6b golden fixture 16 ("client.both-providers-unavailable")
    # originally stood this case in with HUMAN_DECISION_REQUIRED (check 4)
    # for lack of a dedicated member, and said so in its own notes — a
    # deliberate placeholder, not an oversight. The two are NOT the same
    # failure: HUMAN_DECISION_REQUIRED means the model produced a candidate
    # that a human must judge; PROVIDERS_EXHAUSTED means the machinery never
    # produced a candidate at all (every ClientBrainProvider failed before
    # generation). Sharing one code made it impossible for a tripwire to
    # distinguish "we hand off a lot because the questions are hard" from
    # "we hand off a lot because the brain is down" — exactly the split the
    # F11 tripwires need. Raised only by the engine/provider-router path
    # (never by FinalPolicyGate.evaluate() itself, which always receives a
    # real candidate).
    PROVIDERS_EXHAUSTED = "providers_exhausted"

    # Check 5 — surface/domain boundary (-> ABSTAIN or surface redirect)
    DOMAIN_OUT_OF_SURFACE_SCOPE = "domain_out_of_surface_scope"
    UNAUTHENTICATED_PORTAL_CONTEXT_LEAK = "unauthenticated_portal_context_leak"
    ATTACHMENT_PROFILE_MISMATCH = "attachment_profile_mismatch"

    # Check 6 — claim inventory completeness (-> fail closed / ABSTAIN)
    UNINVENTORIED_REGULATED_STATEMENT = "uninventoried_regulated_statement"
    UNINVENTORIED_NUMERIC_STATEMENT = "uninventoried_numeric_statement"

    # Check 7 — PricingTool enforcement (-> POLICY_BLOCKED, normally HANDOFF)
    PRICE_NOT_IN_SNAPSHOT = "price_not_in_snapshot"
    PRICE_RECOMPUTED_BY_MODEL = "price_recomputed_by_model"
    NO_PRICING_SNAPSHOT_AVAILABLE = "no_pricing_snapshot_available"

    # Check 8 — evidence support (-> ABSTAIN or HANDOFF)
    CLAIM_MISSING_EVIDENCE_ID = "claim_missing_evidence_id"
    EVIDENCE_DETERMINISTIC_CHECK_FAILED = "evidence_deterministic_check_failed"
    EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD = "evidence_semantic_support_below_threshold"
    EVIDENCE_VERIFIER_OUTAGE = "evidence_verifier_outage"

    # Check 9 — citation integrity (-> ABSTAIN)
    CITATION_ID_NOT_IN_BUNDLE = "citation_id_not_in_bundle"
    CITATION_TO_UNUSED_EVIDENCE = "citation_to_unused_evidence"
    CLAIM_MISSING_DISPLAYED_CITATION = "claim_missing_displayed_citation"
    KBLI_CLASSIFICATION_MISSING_ALL_FACTUAL_CITATION = (
        "kbli_classification_missing_all_factual_citation"
    )

    # Check 10 — language and surface rendering (-> TEXT_DEFECT)
    RENDER_LANGUAGE_MISMATCH = "render_language_mismatch"
    RENDER_FORMAT_VIOLATION = "render_format_violation"
    RENDERER_ADDED_CONTENT = "renderer_added_content"

    # Check 11 — hard length and delivery constraints
    # (-> TEXT_DEFECT, eligible for the one allowed provider fallback)
    LENGTH_EXCEEDS_HARD_LIMIT = "length_exceeds_hard_limit"
    IDEMPOTENCY_CONFLICT_AT_INSERT = "idempotency_conflict_at_insert"


class FinalDecision(BaseModel):
    """What ``FinalPolicyGate.evaluate()`` returns. Never carries a "fixed" fact.

    ``rendered_text`` is populated if and only if ``verdict == ALLOW`` — the
    gate does not rewrite/repair regulatory content; a defect either passes
    or the request abstains/hands off/drops (research capture §1.6, closing
    paragraph: "It never 'fixes' regulatory facts in free text.").
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID
    request_id: UUID
    verdict: GateVerdict
    reason: GateReason
    # A rule identifier only — research capture §1.6 check 3: "Log only the
    # rule identifier and hashes, never the detected secret." This field
    # inherits that discipline: it is not a place to put raw offending text.
    reason_detail: Annotated[str, Field(max_length=200)] | None = None
    rendered_text: Annotated[str, Field(max_length=20_000)] | None = None
    evaluated_at: datetime

    @model_validator(mode="after")
    def _rendered_text_only_on_allow(self) -> FinalDecision:
        if self.verdict == GateVerdict.ALLOW and self.rendered_text is None:
            raise ValueError("rendered_text is required when verdict is ALLOW")
        if self.verdict != GateVerdict.ALLOW and self.rendered_text is not None:
            raise ValueError("rendered_text must be unset unless verdict is ALLOW")
        return self

    @property
    def is_retryable(self) -> bool:
        """Only TEXT_DEFECT is eligible for one provider fallback (§1.6, closing line)."""
        return self.verdict == GateVerdict.TEXT_DEFECT
