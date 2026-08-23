"""Adapt one Magazine `ops_intents` row into a canonical `ActionIntent` (CONTRACTS.md §13.2).

Depends on `action_item_adapter.adapt_ops_intent_to_action_item` for the
SAME row: `action_item_ref` must pin the exact `ActionItem` revision this
intent was materialized alongside (per the fused-row design in that
module), so the item is built first and its real `object_hash` is used
here -- that one reference is genuinely backed, unlike
`requested_action_spec_ref` (see `synthesis.py`).

Deliberately excluded from this slice, with reasons (not silently skipped):

- `ApprovalReceipt` (subject=action_intent): CONFIRMED zero legacy source
  anywhere in the repo outside `research_os`'s own tests (matrix §1.3,
  closed by §2.0's independent grep). There is no legacy decision to adapt
  FROM -- an adapter here would be an unconditional no-op stub, not a
  mapping.
- `ExecutionAttempt`: its `approval_receipt_ref` is non-optional and would
  have to point at the `ApprovalReceipt` that does not exist above.
  Fabricating one to satisfy the constructor would assert an approval event
  that never happened -- a materially worse fabrication than this module's
  disclosed unbacked bookkeeping refs, because it misrepresents an
  AUTHORIZATION decision, not a missing provenance pointer. Deferred to a
  ruling, per CONTRACTS.md's own instruction to stop and propose rather
  than silently reinterpret a frozen invariant.
"""

from __future__ import annotations

from research_os.enums import RiskClass, Sensitivity
from research_os.models.action_intent import ActionIntent, AuthorityRequired, Target
from research_os.models.action_item import ActionItemRef, RequestedActionSpecRef
from research_os.primitives import ExactObjectRef, Lineage, Producer, Retention

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
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
    parse_legacy_timestamp,
    synthetic_uuid,
    unbacked_object_hash,
    unbacked_refs_extension,
)

SOURCE_SYSTEM = "bali-zero-magazine"
SOURCE_KIND = "ops_intents"
CANONICAL_KIND = "action_intent"


def adapt_ops_intent_to_action_intent(row: OpsIntentRow) -> AdapterResult[ActionIntent]:
    intent_id = row["intent_id"]

    item_result = adapt_ops_intent_to_action_item(row)
    if not item_result.accepted or item_result.canonical is None:
        # Same row was already rejected while building its ActionItem half
        # (bad clock data) -- propagate that rejection rather than build a
        # half of the pair that would reference a nonexistent sibling.
        report = AdapterLossReport(
            source_system=SOURCE_SYSTEM,
            source_kind=SOURCE_KIND,
            source_id=intent_id,
            canonical_kind=CANONICAL_KIND,
            fields=tuple(
                LegacyFieldReport(k, LegacyFieldFate.REJECTED, None, "sibling ActionItem adaptation was rejected")
                for k in row
            ),
        )
        return AdapterResult(canonical=None, loss_report=report, accepted=False)
    item = item_result.canonical

    created_at = parse_legacy_timestamp(row["created_at"])
    expires_at = parse_legacy_timestamp(row["expires_at"])
    expires_after_seconds = max(1, int((expires_at - created_at).total_seconds()))

    requested_action_spec_ref = RequestedActionSpecRef(
        requested_action_spec_id=synthetic_uuid("ops_intent", intent_id, "requested_action_spec"),
        object_hash=unbacked_object_hash("requested_action_spec", intent_id),
    )
    target = Target(
        system="bali-zero-magazine",
        object_ref=ExactObjectRef(
            object_kind=row["intent_kind"],
            object_id=intent_id,
            object_hash=unbacked_object_hash("target", row["intent_kind"], row["params_json"]),
        ),
        surface=None,
    )
    authority_required = AuthorityRequired(
        role=row["effective_role"],
        scope="bali-zero-magazine.ops-action",
        expires_after_seconds=expires_after_seconds,
    )

    intent = build_with_object_hash(
        ActionIntent,
        action_intent_id=synthetic_uuid("ops_intent", intent_id, "action_intent"),
        contract_version="research-os/v1.0.0",
        tenant="bali-zero",
        action_item_ref=ActionItemRef(action_item_id=item.action_item_id, object_hash=item.object_hash),
        requested_action_spec_ref=requested_action_spec_ref,
        action_type=row["intent_kind"],
        target=target,
        arguments_ref=f"ops_intents:{intent_id}:params_json",
        arguments_hash=row["request_hash"],
        input_revision_hash=row["request_hash"],
        risk_class=RiskClass.GREEN,
        sensitivity=Sensitivity.INTERNAL,
        authority_required=authority_required,
        idempotency_key=row["idempotency_key"],
        expected_outcome_types=(),
        created_at=created_at,
        producer=Producer(name="bali-zero-magazine", version="ops_intents/v1"),
        lineage=Lineage(workflow_run_ref=None, input_hashes=(row["request_hash"],)),
        retention=Retention(
            retention_class="operational", retain_until=None, legal_hold=False, rights_expires_at=None
        ),
        extensions=unbacked_refs_extension("requested_action_spec_ref", "target.object_ref.object_hash"),
    )

    fields = [
        LegacyFieldReport("intent_id", LegacyFieldFate.MAPPED, "action_intent_id / target.object_ref.object_id", "synthesized id + direct target identity"),
        LegacyFieldReport("actor_key", LegacyFieldFate.OMITTED, None, "names who requested the action; no canonical ActionIntent field for the requester's identity (producer is the system, not the human)"),
        LegacyFieldReport("effective_role", LegacyFieldFate.MAPPED, "authority_required.role", "direct: legacy hardcodes this to a single CHECK constant"),
        LegacyFieldReport("policy_version", LegacyFieldFate.OMITTED, None, "no canonical field for a policy-engine version"),
        LegacyFieldReport("idempotency_key", LegacyFieldFate.MAPPED, "idempotency_key", "direct name and semantic match"),
        LegacyFieldReport("intent_kind", LegacyFieldFate.MAPPED, "action_type / target.object_ref.object_kind", "closed 5-value legacy enum is a safe subset of canonical's open RegisteredName"),
        LegacyFieldReport("params_json", LegacyFieldFate.APPROXIMATED, "arguments_ref / target.object_ref.object_hash", "inlined content, not a durable external pointer; content-hashed rather than dereferenced"),
        LegacyFieldReport("request_hash", LegacyFieldFate.APPROXIMATED, "arguments_hash / input_revision_hash / lineage.input_hashes", "one compound hash covering MORE than either canonical slot (also covers schema_version/intent_kind/reason_code/expires_at) -- reused for both since no narrower legacy hash exists"),
        LegacyFieldReport("reason_code", LegacyFieldFate.OMITTED, None, "no canonical ActionIntent field for a human-readable request reason"),
        LegacyFieldReport("status", LegacyFieldFate.OMITTED, None, "execution-lifecycle state belongs to ActionItem.queue_state / a receipt, not this kind"),
        LegacyFieldReport("attempt_limit", LegacyFieldFate.OMITTED, None, "retry ceiling, no canonical ActionIntent field"),
        LegacyFieldReport("attempt_count", LegacyFieldFate.OMITTED, None, "belongs to the excluded ExecutionAttempt kind"),
        LegacyFieldReport("worker_id", LegacyFieldFate.OMITTED, None, "belongs to the excluded ExecutionAttempt.executor"),
        LegacyFieldReport("claim_token", LegacyFieldFate.OMITTED, None, "execution-lease credential, belongs to the excluded ExecutionAttempt kind"),
        LegacyFieldReport("fencing_token", LegacyFieldFate.OMITTED, None, "optimistic-concurrency counter, no canonical equivalent"),
        LegacyFieldReport("heartbeat_at", LegacyFieldFate.OMITTED, None, "execution liveness signal, belongs to the excluded ExecutionAttempt kind"),
        LegacyFieldReport("lease_deadline", LegacyFieldFate.OMITTED, None, "execution-lease deadline, distinct from the request TTL used for authority_required.expires_after_seconds"),
        LegacyFieldReport("effect_token", LegacyFieldFate.OMITTED, None, "execution-effect credential, belongs to a receipt kind"),
        LegacyFieldReport("pre_effect_attested_at", LegacyFieldFate.OMITTED, None, "execution attestation timestamp, belongs to a receipt kind"),
        LegacyFieldReport("attested_policy_version", LegacyFieldFate.OMITTED, None, "execution attestation detail, belongs to a receipt kind"),
        LegacyFieldReport("attestation_expires_at", LegacyFieldFate.OMITTED, None, "execution attestation detail, belongs to a receipt kind"),
        LegacyFieldReport("effect_consumed_at", LegacyFieldFate.OMITTED, None, "execution-effect timestamp, belongs to a receipt kind"),
        LegacyFieldReport("expires_at", LegacyFieldFate.MAPPED, "authority_required.expires_after_seconds", "derived as (expires_at - created_at); a genuine legacy-derived value, not a synthesized constant"),
        LegacyFieldReport("started_at", LegacyFieldFate.OMITTED, None, "belongs to the excluded ExecutionAttempt kind"),
        LegacyFieldReport("completed_at", LegacyFieldFate.OMITTED, None, "belongs to a receipt kind, not ActionIntent"),
        LegacyFieldReport("failure_code", LegacyFieldFate.OMITTED, None, "belongs to ActionItem.close_reason / a receipt kind"),
        LegacyFieldReport("created_at", LegacyFieldFate.MAPPED, "created_at", "direct match"),
    ]
    warnings = [
        "requested_action_spec_ref and target.object_ref.object_hash are SYNTHESIZED_UNBACKED / "
        "content-hash placeholders, not canonical-object hashes -- see synthesis.py's module "
        "docstring. target.object_ref.object_hash also does not reproduce Magazine's own kind-specific "
        "targetId() derivation (matrix item 2); it is a content hash of params_json instead, disclosed "
        "as a differently-derived target identity.",
        "risk_class/sensitivity defaulted to green/internal: no legacy classification signal exists; "
        "inert while the shadow dual-write flag defaults off (see shadow.py).",
        "action_item_ref IS genuinely backed: it is this exact row's freshly-built ActionItem's real "
        "object_hash, not a placeholder.",
    ]

    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=intent_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(fields),
        warnings=tuple(warnings),
    )
    assert_every_legacy_field_accounted_for(dict(row), report)
    return AdapterResult(canonical=intent, loss_report=report, accepted=True)
