"""Adapt one Magazine `ops_intents` row into a canonical `ActionItem` (CONTRACTS.md §13.1).

Headline structural finding (matrix §1.0, re-confirmed by reading
`schema.ts` directly this session): Magazine fuses queue-ownership
(`ActionItem`) and authorization-bearing execution (`ActionIntent`) into ONE
row. This adapter treats that fused row as the queue-registration moment:
`ActionItem` revision 1, `current_intent_ref=None` always.

CORRECTED (independent reviewer, REFUSE verdict, claim #12): matrix item 6
does NOT recommend this. It presents two candidate rulings -- a
self-referencing pointer, or synthesizing the field as absent -- and
explicitly defers the choice ("Ruling must decide"). `None` here is this
adapter's own placeholder pending that ruling, not a matrix-endorsed
resolution; the reasoning that follows (there was never a moment the two
objects existed independently, so a degenerate "no linked intent yet" reads
more honestly than a self-referencing pointer) is this adapter's OWN
argument for the placeholder, offered to the conductor for a ruling, not
authority borrowed from the matrix. The disclosure is also machine-checkable
via `extensions['com.balizero.research-os-adapters'].payload['pending_ruling']`
(see `synthesis.py`), not prose alone.

Two fields are non-optional on the canonical model with NO legacy source at
all: `decision_packet_ref` and `requested_action_spec_ref`. See
`synthesis.py`'s module docstring for why this adapter uses a disclosed
SYNTHESIZED_UNBACKED reference for both rather than fabricating a full
upstream `DecisionPacket`/`WorkflowRun` chain.
"""

from __future__ import annotations

from research_os.enums import QueueState, RiskClass, Sensitivity
from research_os.models.action_item import (
    ActionItem,
    DecisionPacketRef,
    RequestedActionSpecRef,
    Sla,
)
from research_os.primitives import Lineage, Producer, Retention

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.legacy_magazine import OpsIntentRow
from backend.services.research_os.loss_report import (
    AdapterLossReport,
    AdapterResult,
    LegacyFieldFate,
    LegacyFieldReport,
    assert_every_legacy_field_accounted_for,
)
from backend.services.research_os.synthesis import (
    build_with_object_hash,
    legacy_content_hash,
    parse_legacy_timestamp,
    synthetic_uuid,
    unbacked_object_hash,
    unbacked_refs_extension,
)

SOURCE_SYSTEM = "bali-zero-magazine"
SOURCE_KIND = "ops_intents"
CANONICAL_KIND = "action_item"

# queue_state: legacy execution-lifecycle states approximated onto
# canonical queue-triage states (matrix §1.2 -- flagged there as an
# imperfect match, not a silent rename).
_QUEUE_STATE_MAP: dict[str, QueueState] = {
    "queued": QueueState.NEW,
    "claimed": QueueState.ASSIGNED,
    "running": QueueState.ASSIGNED,
    "succeeded": QueueState.CLOSED,
    "failed": QueueState.CLOSED,
    "cancelled_revoked": QueueState.CLOSED,
    "outcome_unknown": QueueState.CLOSED,
}
# close_reason only applies once queue_state == CLOSED; canonical's 5-value
# vocabulary (completed|rejected|duplicate|obsolete|invalid) has no
# "failed"/"unknown" member, so failed/outcome_unknown are approximated
# onto the closest available value and disclosed as such.
_CLOSE_REASON_MAP: dict[str, str] = {
    "succeeded": "completed",
    "failed": "invalid",
    "cancelled_revoked": "obsolete",
    "outcome_unknown": "invalid",
}


def action_item_family_id_for(intent_id: str) -> str:
    return f"bali-zero-magazine.ops-intent.{intent_id}"


def adapt_ops_intent_to_action_item(row: OpsIntentRow) -> AdapterResult[ActionItem]:
    intent_id = row["intent_id"]
    status = row["status"]
    queue_state = _QUEUE_STATE_MAP.get(status)
    fields: list[LegacyFieldReport] = []
    warnings: list[str] = []

    if queue_state is None:
        report = AdapterLossReport(
            source_system=SOURCE_SYSTEM,
            source_kind=SOURCE_KIND,
            source_id=intent_id,
            canonical_kind=CANONICAL_KIND,
            fields=tuple(
                LegacyFieldReport(
                    k, LegacyFieldFate.REJECTED, None, f"unrecognized status {status!r}"
                )
                for k in row
            ),
        )
        return AdapterResult(canonical=None, loss_report=report, accepted=False)

    close_reason = _CLOSE_REASON_MAP.get(status) if queue_state == QueueState.CLOSED else None
    created_at = parse_legacy_timestamp(row["created_at"])
    # `recorded_at`: ops_intents has NO updated_at column at all (verified
    # this session, not in the matrix) -- approximate "last known change" as
    # the latest of completed_at/heartbeat_at/created_at that is present.
    recorded_candidates = [row.get("completed_at"), row.get("heartbeat_at")]
    recorded_at = created_at
    for candidate in recorded_candidates:
        if candidate:
            parsed = parse_legacy_timestamp(candidate)
            if parsed > recorded_at:
                recorded_at = parsed
    due_at = parse_legacy_timestamp(row["expires_at"])
    if due_at <= created_at:
        # Sla requires due_at strictly after opened_at; a row whose expiry
        # already precedes its own creation (clock skew / bad data) cannot
        # be adapted into a valid Sla -- reject rather than fabricate.
        report = AdapterLossReport(
            source_system=SOURCE_SYSTEM,
            source_kind=SOURCE_KIND,
            source_id=intent_id,
            canonical_kind=CANONICAL_KIND,
            fields=tuple(
                LegacyFieldReport(
                    k, LegacyFieldFate.REJECTED, None, "expires_at does not postdate created_at"
                )
                for k in row
            ),
        )
        return AdapterResult(canonical=None, loss_report=report, accepted=False)

    decision_packet_ref = DecisionPacketRef(
        decision_packet_id=synthetic_uuid("ops_intent", intent_id, "decision_packet"),
        object_hash=unbacked_object_hash("decision_packet", intent_id),
    )
    requested_action_spec_ref = RequestedActionSpecRef(
        requested_action_spec_id=synthetic_uuid("ops_intent", intent_id, "requested_action_spec"),
        object_hash=unbacked_object_hash("requested_action_spec", intent_id),
    )

    item = build_with_object_hash(
        ActionItem,
        action_item_id=synthetic_uuid("ops_intent", intent_id, "action_item"),
        action_item_family_id=action_item_family_id_for(intent_id),
        revision=1,
        supersedes_action_item_ref=None,
        contract_version="research-os/v1.0.0",
        tenant="bali-zero",
        decision_packet_ref=decision_packet_ref,
        requested_action_spec_ref=requested_action_spec_ref,
        queue_state=queue_state,
        owner_ref=None,
        risk_class=RiskClass.GREEN,
        sensitivity=Sensitivity.INTERNAL,
        priority="p2",
        sla=Sla(opened_at=created_at, due_at=due_at),
        current_intent_ref=None,
        close_reason=close_reason,
        created_at=created_at,
        recorded_at=recorded_at,
        producer=Producer(name="bali-zero-magazine", version="ops_intents/v1"),
        lineage=Lineage(
            workflow_run_ref=None, input_hashes=(legacy_content_hash(row["request_hash"]),)
        ),
        retention=Retention(
            retention_class="operational",
            retain_until=None,
            legal_hold=False,
            rights_expires_at=None,
        ),
        extensions=unbacked_refs_extension(
            "decision_packet_ref",
            "requested_action_spec_ref",
            pending_ruling=(
                "priority",
                "sla.due_at",
                "current_intent_ref",
                # `risk_class`/`sensitivity` added 2026-08-26 (D3 residue audit).
                # They were already declared by the SIBLING adapter
                # (`action_intent_adapter.py`, after a Kimi K3 review on
                # 2026-08-24) which INHERITS them from this object to satisfy
                # `verify_action_intent_matches_action_item`'s cross-object
                # equality invariant -- while THIS adapter, the object that
                # ORIGINATES both values, did not declare them. That review's
                # cure landed on the heir and not on the source, so for one
                # legacy row a consumer branching on the machine-checkable
                # channel distrusted the ActionIntent's classification and
                # trusted the ActionItem's -- for the two same fields carrying
                # the two same values, by invariant.
                "risk_class",
                "sensitivity",
            ),
        ),
    )

    fields.extend(
        [
            LegacyFieldReport(
                "intent_id",
                LegacyFieldFate.MAPPED,
                "action_item_id",
                "synthesized 1:1 from the fused row (see synthesis.synthetic_uuid)",
            ),
            LegacyFieldReport(
                "actor_key",
                LegacyFieldFate.OMITTED,
                "owner_ref",
                "names who requested the action, not a queue-ownership actor; no ActorRef scheme fits",
            ),
            LegacyFieldReport(
                "effective_role",
                LegacyFieldFate.OMITTED,
                None,
                "static schema CHECK constant ('operator'), belongs to ActionIntent.authority_required, not this kind",
            ),
            LegacyFieldReport(
                "policy_version",
                LegacyFieldFate.OMITTED,
                None,
                "no canonical field for a policy-engine version on ActionItem",
            ),
            LegacyFieldReport(
                "idempotency_key",
                LegacyFieldFate.OMITTED,
                None,
                "ActionItem carries no idempotency_key field (that lives on ActionIntent)",
            ),
            LegacyFieldReport(
                "intent_kind",
                LegacyFieldFate.OMITTED,
                None,
                "action_type lives on ActionIntent, not ActionItem",
            ),
            LegacyFieldReport(
                "params_json",
                LegacyFieldFate.OMITTED,
                None,
                "arguments live on ActionIntent, not ActionItem",
            ),
            LegacyFieldReport(
                "request_hash",
                LegacyFieldFate.APPROXIMATED,
                "lineage.input_hashes",
                "carried through as a content-hash input, not this kind's own object_hash",
            ),
            LegacyFieldReport(
                "reason_code",
                LegacyFieldFate.OMITTED,
                None,
                "no canonical field for a request-time reason on ActionItem",
            ),
            LegacyFieldReport(
                "status",
                LegacyFieldFate.APPROXIMATED,
                "queue_state",
                "execution-lifecycle states mapped onto queue-triage states; not a 1:1 value match",
            ),
            LegacyFieldReport(
                "attempt_limit",
                LegacyFieldFate.OMITTED,
                None,
                "no canonical ActionItem field for a retry ceiling",
            ),
            LegacyFieldReport(
                "attempt_count",
                LegacyFieldFate.OMITTED,
                None,
                "belongs to ExecutionAttempt.attempt_number, a kind this slice excludes (see action_intent_adapter)",
            ),
            LegacyFieldReport(
                "worker_id",
                LegacyFieldFate.OMITTED,
                "owner_ref",
                "names the executing worker, closer to ExecutionAttempt.executor than queue ownership",
            ),
            LegacyFieldReport(
                "claim_token",
                LegacyFieldFate.OMITTED,
                None,
                "execution-lease credential, not a queue concept",
            ),
            LegacyFieldReport(
                "fencing_token",
                LegacyFieldFate.OMITTED,
                None,
                "optimistic-concurrency counter, no canonical ActionItem equivalent",
            ),
            LegacyFieldReport(
                "heartbeat_at",
                LegacyFieldFate.APPROXIMATED,
                "recorded_at",
                "used only as one candidate input to the recorded_at approximation (no updated_at column exists)",
            ),
            LegacyFieldReport(
                "lease_deadline",
                LegacyFieldFate.OMITTED,
                None,
                "execution-lease deadline, distinct from the request-level expires_at used for sla.due_at",
            ),
            LegacyFieldReport(
                "effect_token",
                LegacyFieldFate.OMITTED,
                None,
                "execution-effect credential, no canonical ActionItem field",
            ),
            LegacyFieldReport(
                "pre_effect_attested_at",
                LegacyFieldFate.OMITTED,
                None,
                "execution attestation timestamp, belongs to a receipt/attempt kind",
            ),
            LegacyFieldReport(
                "attested_policy_version",
                LegacyFieldFate.OMITTED,
                None,
                "execution attestation detail, not a queue concept",
            ),
            LegacyFieldReport(
                "attestation_expires_at",
                LegacyFieldFate.OMITTED,
                None,
                "execution attestation detail, not a queue concept",
            ),
            LegacyFieldReport(
                "effect_consumed_at",
                LegacyFieldFate.OMITTED,
                None,
                "execution-effect timestamp, not a queue concept",
            ),
            LegacyFieldReport(
                "expires_at",
                LegacyFieldFate.APPROXIMATED,
                "sla.due_at",
                "CORRECTED (independent review, claim #11): matrix §1.2 marks this pairing 'unmappable as-is -- needs a ruling', not merely an imperfect fit. `expires_at` bounds a 24h operator-authorization window at intent-creation time (operations-repository.ts:699, `delta > 86_400_000` throws), not a queue-SLA due-date concept at all. Mapping it onto sla.due_at anyway is this adapter's own placeholder pending a ruling, not a matrix-endorsed equivalence -- disclosed, not asserted",
            ),
            LegacyFieldReport(
                "started_at",
                LegacyFieldFate.OMITTED,
                None,
                "belongs to ExecutionAttempt.started_at, a kind this slice excludes",
            ),
            LegacyFieldReport(
                "completed_at",
                LegacyFieldFate.APPROXIMATED,
                "recorded_at",
                "used only as one candidate input to the recorded_at approximation",
            ),
            LegacyFieldReport(
                "failure_code",
                LegacyFieldFate.APPROXIMATED,
                "close_reason",
                "only covers the failure case; folded into close_reason alongside status",
            ),
            LegacyFieldReport(
                "created_at", LegacyFieldFate.MAPPED, "created_at / sla.opened_at", "direct match"
            ),
        ]
    )
    warnings.extend(
        [
            "decision_packet_ref and requested_action_spec_ref are SYNTHESIZED_UNBACKED: "
            "Magazine's ops-action pipeline never ran a decision-packet gate (matrix §1.0/§1.1); "
            "these refs are deterministic placeholders that do not resolve to any materialized "
            "DecisionPacket/RequestedActionSpec object. This is a ruling gap the matrix under-scoped "
            "(it recorded 'no legacy source', not that the field is constructor-blocking) -- flagged "
            "for the conductor, not silently resolved. Disclosure is ALSO machine-checkable, not only "
            "prose: extensions['com.balizero.research-os-adapters'].payload['unbacked_refs'] names "
            "both fields, per an adversarial review (Kimi K3) that a loss report alone is documentation "
            "a consumer could skip.",
            "priority defaulted to 'p2': ops_intents has no priority concept at all -- genuine "
            "information loss, not an adapter shortfall (matrix §0). CORRECTED (independent "
            "review, REFUSE verdict, claim #10): matrix §0 does not endorse a default value -- "
            "its own words are 'Ruling must decide: is a Magazine-sourced ActionItem valid with "
            "priority/sla permanently null/defaulted, or does adopting this source require first "
            "extending the Magazine schema to capture them' (i.e. whether this source is adoptable "
            "at all, not merely which value to pick). 'p2' is this adapter's own placeholder "
            "pending that ruling, not a matrix-approved value. Do not trust this value for triage "
            "ordering.",
            "risk_class/sensitivity defaulted to green/internal: no legacy classification signal "
            "exists. CORRECTED (D3 residue audit, 2026-08-26): the previous wording claimed these "
            "defaults were 'inert while the shadow dual-write flag defaults off (see shadow.py)'. "
            "There is no such flag and no such module -- `shadow.py` has never existed in this "
            "package (verified against origin/main, not inferred), and the phased dual-write/read "
            "plan that would introduce it is D8, an OPEN condition on "
            "`contract-pass-001.md` §9 (under "
            "`research/operations/execution/research-os-v1.0.0/evidence/p04/`) owned by another "
            "lane. So that sentence "
            "asserted a SAFETY property resting on a switch nobody had built. What actually makes "
            "these defaults inert today is narrower, and verifiable: this package has ZERO "
            "production consumers -- a repo-wide import search on 2026-08-26 found every importer "
            "to be a test, independently reproduced by a cross-family refuter. Stated as the "
            "MEASUREMENT it is, not as a property: `_core_path.py` exists precisely so this "
            "package imports without a packaging declaration, so a string-based consumer would "
            "leave no manifest trace for either search to find. Re-run it, do not inherit it. On "
            "that measurement, no adapter output reaches any "
            "store. Read that as an absence of a write path, never as a guarantee from a flag. "
            "On how bad the defaults are, precisely -- an earlier revision of THIS warning said "
            "'the LEAST restrictive pair the contract can express', which a cross-family refuter "
            "(Kimi K3, 2026-08-26) refuted by reading the enums, and the correction is narrower "
            "but not milder: GREEN is indeed the floor of RiskClass (GREEN < AMBER < RED), while "
            "INTERNAL is NOT the floor of Sensitivity -- PUBLIC is, and `ActionItem.sensitivity` "
            "carries no constraint excluding it. What matters is unchanged, because the hazard "
            "was never 'the minimum' but the DIRECTION: INTERNAL sits below CONFIDENTIAL, "
            "RESTRICTED_OSINT and CLIENT_PII, so a Magazine row that deserves any of those three "
            "is silently under-classified by a value chosen for absence of signal, not by "
            "assessment. Whoever builds the write path must resolve classification FIRST. Both "
            "fields are now in pending_ruling too (not "
            "just this prose) -- see the call site for why declaring them only on the sibling "
            "ActionIntent left the originating object looking trustworthy.",
            "current_intent_ref is always None for Magazine-sourced items: the fused row means there "
            "was never a moment the queue-side and execution-side objects existed independently. "
            "CORRECTED (independent review, REFUSE verdict, claim #12): matrix item 6 presents "
            "this as ONE of two candidate rulings (the other being a self-referencing pointer) and "
            "explicitly defers the choice to a ruling not yet issued -- it does not recommend None. "
            "This value is this adapter's own placeholder pending that ruling, disclosed "
            "machine-checkably via "
            "extensions['com.balizero.research-os-adapters'].payload['pending_ruling'].",
        ]
    )

    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=intent_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(fields),
        warnings=tuple(warnings),
    )
    assert_every_legacy_field_accounted_for(dict(row), report)
    return AdapterResult(canonical=item, loss_report=report, accepted=True)
