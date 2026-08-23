"""Adapt one Magazine `ops_receipts` row into a canonical `OperationalReceipt`
(CONTRACTS.md §13.5).

Needs its parent `ops_intents` row for context Magazine only records once,
on the intent (`completed_at`, the target-identifying `intent_id`) --
`ops_receipts.intent_id` is a `UNIQUE FK` (schema.ts:927-930), so the join
is 1:1 and lossless, not a fan-out.

`execution_attempt_ref` is populated with a SYNTHESIZED_UNBACKED pointer
(same category as `action_item_adapter`'s `decision_packet_ref` -- a
disclosed dangling reference, never a fabricated event). This is NOT the
same class of fabrication `action_intent_adapter` refused for
`ExecutionAttempt`/`ApprovalReceipt`: those would assert an authorization
decision that never happened; this is a null bookkeeping pointer, exactly
like every other unbacked ref in this package.
"""

from __future__ import annotations

from research_os.enums import ExecutionTerminalOutcome, ReconciliationState, RiskClass, Sensitivity
from research_os.models.operational_receipt import (
    ActorOrExecutor,
    ExecutionAttemptRef,
    OperationalReceipt,
    Reconciliation,
)
from research_os.primitives import Classification, ExactObjectRef, Lineage, Producer, Retention

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.legacy_magazine import OpsIntentRow, OpsReceiptRow
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
SOURCE_KIND = "ops_receipts"
CANONICAL_KIND = "operational_receipt"

_TERMINAL_OUTCOME_MAP: dict[str, ExecutionTerminalOutcome] = {
    "succeeded": ExecutionTerminalOutcome.SUCCEEDED,
    "failed": ExecutionTerminalOutcome.FAILED,
    "cancelled_revoked": ExecutionTerminalOutcome.CANCELLED,
    "outcome_unknown": ExecutionTerminalOutcome.UNKNOWN,
}


def adapt_ops_receipt_to_operational_receipt(
    receipt_row: OpsReceiptRow, parent_intent_row: OpsIntentRow
) -> AdapterResult[OperationalReceipt]:
    receipt_id = receipt_row["receipt_id"]
    intent_id = receipt_row["intent_id"]
    terminal_outcome = _TERMINAL_OUTCOME_MAP.get(receipt_row["status"])

    if terminal_outcome is None or parent_intent_row.get("intent_id") != intent_id:
        reason = (
            f"unrecognized receipt status {receipt_row['status']!r}"
            if terminal_outcome is None
            else "parent_intent_row does not match receipt_row.intent_id"
        )
        report = AdapterLossReport(
            source_system=SOURCE_SYSTEM,
            source_kind=SOURCE_KIND,
            source_id=receipt_id,
            canonical_kind=CANONICAL_KIND,
            fields=tuple(
                LegacyFieldReport(k, LegacyFieldFate.REJECTED, None, reason) for k in receipt_row
            ),
        )
        return AdapterResult(canonical=None, loss_report=report, accepted=False)

    recorded_at = parse_legacy_timestamp(receipt_row["created_at"])
    completed_at = parent_intent_row.get("completed_at")
    observed_at = recorded_at
    if completed_at:
        parsed = parse_legacy_timestamp(completed_at)
        if parsed <= recorded_at:
            observed_at = parsed
    # else: no legacy completion timestamp available; observed_at falls
    # back to the receipt's own filing time (an approximation, disclosed
    # below), rather than rejecting a row Magazine itself considers valid.

    subject_ref = ExactObjectRef(
        object_kind="ops_intent",
        object_id=intent_id,
        object_hash=legacy_content_hash("ops_intent", intent_id, receipt_row["request_hash"]),
    )
    execution_attempt_ref = ExecutionAttemptRef(
        execution_attempt_id=synthetic_uuid("ops_intent", intent_id, "execution_attempt"),
        object_hash=unbacked_object_hash("execution_attempt", intent_id),
    )

    receipt = build_with_object_hash(
        OperationalReceipt,
        operational_receipt_id=synthetic_uuid("ops_receipt", receipt_id, "operational_receipt"),
        operational_receipt_family_id=f"bali-zero-magazine.ops-receipt.{receipt_id}",
        contract_version="research-os/v1.0.0",
        tenant="bali-zero",
        receipt_type="execution.result",
        supersedes_operational_receipt_ref=None,
        subject_refs=(subject_ref,),
        execution_attempt_ref=execution_attempt_ref,
        classification=Classification(risk_class=RiskClass.GREEN, sensitivity=Sensitivity.INTERNAL),
        actor_or_executor=ActorOrExecutor(
            producer=Producer(name="bali-zero-magazine", version="ops_receipts/v1"), actor_ref=None
        ),
        terminal_outcome=terminal_outcome,
        outcome_code=f"bali-zero-magazine.{receipt_row['status']}",
        effects=(),
        artifact_refs=(),
        evidence_refs=(),
        observed_at=observed_at,
        recorded_at=recorded_at,
        idempotency_key=receipt_id,
        reconciliation=Reconciliation(
            state=ReconciliationState.NOT_APPLICABLE, checked_at=None, evidence_refs=()
        ),
        producer=Producer(name="bali-zero-magazine", version="ops_receipts/v1"),
        lineage=Lineage(
            workflow_run_ref=None,
            input_hashes=(receipt_row["receipt_hash"], receipt_row["request_hash"], receipt_row["body_hash"]),
        ),
        retention=Retention(
            retention_class="operational", retain_until=None, legal_hold=False, rights_expires_at=None
        ),
        extensions=unbacked_refs_extension("execution_attempt_ref"),
    )

    fields = [
        LegacyFieldReport("receipt_id", LegacyFieldFate.MAPPED, "operational_receipt_id / idempotency_key", "direct id + reused as the idempotency stand-in (see request below)"),
        LegacyFieldReport("intent_id", LegacyFieldFate.MAPPED, "subject_refs[0]", "the one bare FK becomes a typed ExactObjectRef, content-hashed (not Magazine's own hash, since none exists at this granularity)"),
        LegacyFieldReport("status", LegacyFieldFate.MAPPED, "terminal_outcome / outcome_code", "direct enum match (outcome_unknown -> unknown); outcome_code is a namespaced echo of status, not a parse of receipt_json.code (see warnings)"),
        LegacyFieldReport("receipt_json", LegacyFieldFate.OMITTED, None, "opaque blob whose shape varies by intent_kind (matrix item 8); no per-kind parser is written in this slice, so effects[]/artifact_refs/evidence_refs stay empty rather than guess a shape"),
        LegacyFieldReport("receipt_hash", LegacyFieldFate.APPROXIMATED, "lineage.input_hashes", "carried through as a lineage input, not validated against this adapter's own hashing recipe (matrix: 'a hash exists, not the hash')"),
        LegacyFieldReport("request_hash", LegacyFieldFate.APPROXIMATED, "lineage.input_hashes / subject_refs[0].object_hash input", "duplicated from the parent ops_intents row; used as one input among several, not on its own"),
        LegacyFieldReport("key_id", LegacyFieldFate.OMITTED, "actor_or_executor.actor_ref", "names the signer (e.g. 'server-terminal'), does not fit ActorRef's hmac-sha256 pseudonym scheme; actor_ref left None"),
        LegacyFieldReport("body_hash", LegacyFieldFate.APPROXIMATED, "lineage.input_hashes", "carried through as a lineage input only"),
        LegacyFieldReport("fencing_token", LegacyFieldFate.OMITTED, "execution_attempt_ref", "a bare int fencing token is not an {execution_attempt_id, object_hash} pair; the ref is synthesized instead (see warnings), not derived from this field"),
        LegacyFieldReport("attested_policy_version", LegacyFieldFate.OMITTED, None, "no canonical OperationalReceipt field for a policy-attestation version"),
        LegacyFieldReport("created_at", LegacyFieldFate.MAPPED, "recorded_at", "direct: when the receipt was filed"),
    ]
    warnings = [
        "execution_attempt_ref is SYNTHESIZED_UNBACKED: this slice deliberately excludes the "
        "ExecutionAttempt kind (see action_intent_adapter.py's module docstring) because its own "
        "required approval_receipt_ref has zero legacy source. This ref is therefore a disclosed "
        "dangling pointer, not a claim that a materialized ExecutionAttempt exists.",
        "outcome_code is derived from receipt.status, not parsed from receipt_json's candidate "
        "'code' field -- that field lives inside an opaque, per-intent_kind-shaped blob this adapter "
        "does not parse (matrix item 8).",
        "idempotency_key reuses receipt_id: ops_receipts has no receipt-level idempotency-key column; "
        "at-most-one-receipt-per-intent is enforced structurally by intent_id UNIQUE instead (matrix "
        "item 9), which is a different mechanism this adapter cannot reproduce as a comparable key.",
        "risk_class/sensitivity defaulted to green/internal: no legacy classification signal exists; "
        "inert while the shadow dual-write flag defaults off (see shadow.py).",
    ]

    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=receipt_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(fields),
        warnings=tuple(warnings),
    )
    assert_every_legacy_field_accounted_for(dict(receipt_row), report)
    return AdapterResult(canonical=receipt, loss_report=report, accepted=True)
