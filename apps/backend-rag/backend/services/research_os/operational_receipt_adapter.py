"""Adapt one Magazine `ops_receipts` row (+ its parent `ops_intents` row) into
a canonical `OperationalReceipt` (CONTRACTS.md §13.5).

Signature note: this adapter takes BOTH the `ops_receipts` row AND its parent
`ops_intents` row (`ops_receipts.intent_id` is a UNIQUE FK, matrix §1.5),
because `subject_refs` should point at the REAL `ActionItem` this receipt
closes out, not a bare legacy FK -- the same composition argument
`action_intent_adapter.py` makes for `action_item_ref`: the referenced object
genuinely exists once `action_item_adapter.adapt_ops_intent_to_action_item`
is called on the same row, so a synthesized-unbacked placeholder would be a
strictly worse disclosure than the real thing.

`receipt_type` is always `"execution.result"`: matrix §1.5 observes "every
legacy receipt is implicitly execution.result-shaped" (there is no
queue-only/team/routing receipt concept in Magazine's schema at all) --
this adapter's own reasoned choice, not left open, since `ops_receipts`
structurally cannot express any other v1 receipt_type. That choice makes
`execution_attempt_ref` and `terminal_outcome` MANDATORY per
`operational_receipt.py`'s own validator; `execution_attempt_ref` is a
SYNTHESIZED_UNBACKED `{execution_attempt_id, object_hash}` pointer (matrix
§1.4/§1.3: `ExecutionAttempt.approval_receipt_ref` is itself mandatory and
`ApprovalReceipt` is a confirmed true-negative -- constructing a real
`ExecutionAttempt` object is out of scope for this deliverable's three
slices; only a REFERENCE to one is needed here, the same "disclosed
dangling pointer, not a fabricated object" argument `synthesis.py`'s module
docstring already makes for `decision_packet_ref`/`requested_action_spec_ref`).

Fields the corrected matrix (§1.5) grades 🔴 "unmappable as-is -- needs a
ruling" (`execution_attempt_ref`, `idempotency_key`) are disclosed via both
`loss_report.warnings` (prose) and a machine-checkable `pending_ruling`
marker, same two-channel discipline as the sibling adapters. `classification`
(`risk_class`/`sensitivity`) is ALSO in `pending_ruling`, even though it is
not itself a legacy field: it is copied verbatim from the composed sibling
`ActionItem`, which defaults it to green/internal placeholders (matrix
§1.0/§1.1) -- a Kimi K3 adversarial review of the sibling `ActionIntent`
adapter (2026-08-24) found that an inherited placeholder disclosed only in
prose is invisible to a consumer reading just the machine-checkable channel;
this adapter closes that gap from the start rather than after review.
`operational_receipt_family_id`/`supersedes_operational_receipt_ref` are
NOT pending_ruling: matrix §1.5 confirms `ops_receipts.intent_id UNIQUE`
STRUCTURALLY forbids more than one receipt per intent, which is a settled
true-negative (no correction/supersession model is expressible here at
all), not an open question awaiting a ruling.
"""

from __future__ import annotations

import json

from research_os.enums import ExecutionTerminalOutcome, ReconciliationState
from research_os.models.operational_receipt import (
    ActorOrExecutor,
    ExecutionAttemptRef,
    OperationalReceipt,
    Reconciliation,
)
from research_os.primitives import Classification, ExactObjectRef, Lineage, Producer, Retention

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.legacy_magazine import (
    OPS_INTENT_TERMINAL_STATUSES,
    OpsIntentRow,
    OpsReceiptRow,
)
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

_EXECUTION_RESULT_RECEIPT_TYPE = "execution.result"

# legacy status -> ExecutionTerminalOutcome. Same 4-way mapping the sibling
# adapters use for the identical legacy vocabulary (legacy's outcome_unknown
# ~= canonical's unknown, cancelled_revoked ~= cancelled -- matrix §1.5).
_TERMINAL_OUTCOME_MAP: dict[str, ExecutionTerminalOutcome] = {
    "succeeded": ExecutionTerminalOutcome.SUCCEEDED,
    "failed": ExecutionTerminalOutcome.FAILED,
    "cancelled_revoked": ExecutionTerminalOutcome.CANCELLED,
    "outcome_unknown": ExecutionTerminalOutcome.UNKNOWN,
}


def _reject(source_id: str, row: OpsReceiptRow, reason: str) -> AdapterResult[OperationalReceipt]:
    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=source_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(LegacyFieldReport(k, LegacyFieldFate.REJECTED, None, reason) for k in row),
    )
    return AdapterResult(canonical=None, loss_report=report, accepted=False)


def _extract_outcome_code(receipt_json: str, status: str) -> tuple[str, bool]:
    """Best-effort parse of the opaque `receipt_json` blob for a `code` key
    (matrix §1.5: `receipt.code` e.g. `"effect_acknowledged"`,
    `operations-repository.ts:100`). Returns (value, was_parsed) -- the
    second element lets the caller disclose a fallback honestly rather than
    silently treating a parse failure the same as a real value.
    """

    try:
        parsed = json.loads(receipt_json)
        code = parsed.get("code") if isinstance(parsed, dict) else None
        if isinstance(code, str) and code:
            return code, True
    except (json.JSONDecodeError, AttributeError):
        pass
    return f"unbacked-outcome-{status}", False


def adapt_ops_receipt_to_operational_receipt(
    receipt_row: OpsReceiptRow, intent_row: OpsIntentRow
) -> AdapterResult[OperationalReceipt]:
    receipt_id = receipt_row["receipt_id"]

    if receipt_row["intent_id"] != intent_row["intent_id"]:
        return _reject(
            receipt_id,
            receipt_row,
            f"receipt_row.intent_id ({receipt_row['intent_id']!r}) does not match the "
            f"supplied intent_row.intent_id ({intent_row['intent_id']!r}) -- mismatched pairing",
        )

    item_result = adapt_ops_intent_to_action_item(intent_row)
    if not item_result.accepted:
        shared_reason = (
            item_result.loss_report.fields[0].reason
            if item_result.loss_report.fields
            else "action_item adaptation rejected the parent intent row"
        )
        return _reject(
            receipt_id,
            receipt_row,
            f"parent ops_intents row rejected by action_item adaptation: {shared_reason}",
        )
    item = item_result.canonical
    assert item is not None

    status = receipt_row["status"]
    if status not in OPS_INTENT_TERMINAL_STATUSES:
        return _reject(receipt_id, receipt_row, f"non-terminal status {status!r} on a receipt row")

    terminal_outcome = _TERMINAL_OUTCOME_MAP[status]

    recorded_at = parse_legacy_timestamp(receipt_row["created_at"])
    # `observed_at`: the parent intent's own completion instant when present
    # (matrix §1.5's own suggested split, `OperationResult.completed_at`),
    # falling back to this receipt's own created_at when the parent has none
    # -- disclosed, not asserted as the confirmed intended split (matrix's
    # own words: "not confirmed... both could plausibly collapse to the
    # same instant in practice").
    completed_at = intent_row.get("completed_at")
    observed_at = parse_legacy_timestamp(completed_at) if completed_at else recorded_at
    if observed_at > recorded_at:
        return _reject(
            receipt_id,
            receipt_row,
            "parent intent's completed_at postdates this receipt's own created_at (clock skew)",
        )

    outcome_code, outcome_code_parsed = _extract_outcome_code(receipt_row["receipt_json"], status)

    subject_refs = (
        ExactObjectRef(
            object_kind="action_item",
            object_id=str(item.action_item_id),
            object_hash=item.object_hash,
        ),
    )
    execution_attempt_ref = ExecutionAttemptRef(
        execution_attempt_id=synthetic_uuid(
            "ops_intent", intent_row["intent_id"], "execution_attempt"
        ),
        object_hash=unbacked_object_hash("execution_attempt", intent_row["intent_id"]),
    )

    receipt = build_with_object_hash(
        OperationalReceipt,
        operational_receipt_id=receipt_row["receipt_id"],
        operational_receipt_family_id=f"bali-zero-magazine.ops-receipt.{receipt_id}",
        contract_version="research-os/v1.0.0",
        tenant="bali-zero",
        receipt_type=_EXECUTION_RESULT_RECEIPT_TYPE,
        supersedes_operational_receipt_ref=None,
        subject_refs=subject_refs,
        execution_attempt_ref=execution_attempt_ref,
        classification=Classification(risk_class=item.risk_class, sensitivity=item.sensitivity),
        actor_or_executor=ActorOrExecutor(
            producer=Producer(name=receipt_row["key_id"], version="ops_receipts/v1"),
            actor_ref=None,
        ),
        terminal_outcome=terminal_outcome,
        outcome_code=outcome_code,
        effects=(),
        artifact_refs=(),
        evidence_refs=(),
        observed_at=observed_at,
        recorded_at=recorded_at,
        idempotency_key=receipt_row["intent_id"],
        reconciliation=Reconciliation(
            state=ReconciliationState.NOT_APPLICABLE, checked_at=None, evidence_refs=()
        ),
        producer=Producer(name=SOURCE_SYSTEM, version="ops_receipts/v1"),
        lineage=Lineage(
            workflow_run_ref=None,
            input_hashes=(
                legacy_content_hash(receipt_row["receipt_hash"]),
                legacy_content_hash(receipt_row["body_hash"]),
            ),
        ),
        retention=Retention(
            retention_class="operational",
            retain_until=None,
            legal_hold=False,
            rights_expires_at=None,
        ),
        extensions=unbacked_refs_extension(
            "execution_attempt_ref",
            pending_ruling=(
                "execution_attempt_ref",
                "idempotency_key",
                "classification.risk_class",
                "classification.sensitivity",
            ),
        ),
    )

    fields = [
        LegacyFieldReport(
            "receipt_id",
            LegacyFieldFate.MAPPED,
            "operational_receipt_id",
            "direct: this row's own natural id, no split needed",
        ),
        LegacyFieldReport(
            "intent_id",
            LegacyFieldFate.MAPPED,
            "subject_refs / idempotency_key",
            "pins the REAL sibling ActionItem (composed via action_item_adapter, not a placeholder) "
            "for subject_refs; also reused as idempotency_key's disclosed placeholder (pending_ruling) "
            "since ops_receipts has no dedicated idempotency column of its own",
        ),
        LegacyFieldReport(
            "status",
            LegacyFieldFate.MAPPED,
            "terminal_outcome",
            "direct 4-way match onto ExecutionTerminalOutcome, same mapping the sibling adapters use "
            "for this legacy vocabulary",
        ),
        LegacyFieldReport(
            "receipt_json",
            LegacyFieldFate.APPROXIMATED,
            "outcome_code",
            f"best-effort JSON parse for a 'code' key (parsed={outcome_code_parsed}); effects[]/"
            "artifact_refs/evidence_refs are NOT extracted -- matrix §1.5 flags this blob as opaque, "
            "shape varies by intent_kind, no guaranteed structure to parse those three fields from",
        ),
        LegacyFieldReport(
            "receipt_hash",
            LegacyFieldFate.APPROXIMATED,
            "lineage.input_hashes",
            "content-hash input, not this kind's own object_hash",
        ),
        LegacyFieldReport(
            "request_hash",
            LegacyFieldFate.OMITTED,
            None,
            "duplicated from the parent ops_intents row (legacy_magazine.py's own docstring); "
            "already accounted for by the ActionItem/ActionIntent adapters on that row",
        ),
        LegacyFieldReport(
            "key_id",
            LegacyFieldFate.APPROXIMATED,
            "actor_or_executor.producer.name",
            "names the signer (matrix §1.5), repurposed as a producer name -- not a perfect fit, "
            "same caveat class as the sibling adapters' actor_key/producer pairing",
        ),
        LegacyFieldReport(
            "body_hash",
            LegacyFieldFate.APPROXIMATED,
            "lineage.input_hashes",
            "content-hash input, paired with receipt_hash",
        ),
        LegacyFieldReport(
            "fencing_token",
            LegacyFieldFate.OMITTED,
            None,
            "optimistic-concurrency counter, no canonical OperationalReceipt equivalent",
        ),
        LegacyFieldReport(
            "attested_policy_version",
            LegacyFieldFate.OMITTED,
            None,
            "execution attestation detail, no canonical field",
        ),
        LegacyFieldReport(
            "created_at",
            LegacyFieldFate.MAPPED,
            "recorded_at (+ observed_at fallback)",
            "direct match for recorded_at; also observed_at when the parent intent has no completed_at",
        ),
    ]

    warnings = (
        "execution_attempt_ref is SYNTHESIZED_UNBACKED: no real ExecutionAttempt object is "
        "constructed anywhere in this deliverable's three slices (its own mandatory "
        "approval_receipt_ref would have to point at ApprovalReceipt, a confirmed true-negative, "
        "matrix §1.3/§2.0) -- only a reference is needed here, disclosed via pending_ruling, not "
        "asserted as resolved.",
        "idempotency_key reuses intent_id as a placeholder: ops_receipts has no receipt-level "
        "idempotency column at all; matrix §1.5's own words -- idempotency is enforced structurally "
        "by intent_id UNIQUE, a different mechanism than a comparable key. Disclosed via "
        "pending_ruling, not a settled equivalence.",
        "receipt_type is always 'execution.result': this adapter's own reasoned choice (matrix §1.5: "
        "'every legacy receipt is implicitly execution.result-shaped'), not left open -- ops_receipts "
        "structurally cannot express any other v1 receipt_type.",
        "operational_receipt_family_id/supersedes_operational_receipt_ref: ops_receipts.intent_id is "
        "UNIQUE (schema.ts:927-930), STRUCTURALLY forbidding more than one receipt per intent -- a "
        "settled true-negative (matrix §1.5), not an open ruling. supersedes_operational_receipt_ref "
        "is always None; family_id is a disclosed placeholder with no correction-chain meaning.",
        "classification (risk_class/sensitivity) is taken directly from the sibling ActionItem for "
        "consistency, not independently defaulted -- see that ActionItem's own disclosure for why "
        "those default to green/internal. Disclosed via pending_ruling (not just this prose): a "
        "consumer reading only the machine-checkable channel would otherwise miss that these are "
        "inherited placeholders, not this adapter's own settled mapping (Kimi K3 adversarial review, "
        "2026-08-24, flagged this exact gap on the sibling ActionIntent adapter).",
        "reconciliation defaults to state=NOT_APPLICABLE: no reconciliation process exists anywhere "
        "on this legacy source -- a settled default (not pending_ruling), since 'no reconciliation "
        "was ever run' is itself an accurate, closed-vocabulary fact about this source.",
        "effects[]/artifact_refs/evidence_refs default to empty tuples: receipt_json's shape varies "
        "by intent_kind with no guaranteed internal structure (matrix §1.5) -- extracting these would "
        "require per-intent_kind parsing logic out of this adapter's scope.",
    )

    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=receipt_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(fields),
        warnings=warnings,
    )
    assert_every_legacy_field_accounted_for(dict(receipt_row), report)
    return AdapterResult(canonical=receipt, loss_report=report, accepted=True)
