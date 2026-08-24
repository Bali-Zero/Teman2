"""Adapt one Magazine `ops_intents` row into a canonical `ActionIntent` (CONTRACTS.md §13.2).

Headline structural finding (matrix §1.0, re-confirmed §1.1, corrected
independent review round 2, 2026-08-24): the same fused `ops_intents` row
that `action_item_adapter.py` reads also carries every legacy fact this
kind can use -- there is no second legacy table. This adapter therefore
COMPOSES `action_item_adapter.adapt_ops_intent_to_action_item` rather than
re-deriving the paired `ActionItem` independently, for a structural reason,
not a convenience one: `action_intent.verify_action_intent_matches_action_item`
requires `action_intent.action_item_ref` to pin the `ActionItem`'s EXACT
`object_hash`, and `requested_action_spec_ref`/`risk_class`/`sensitivity` to
be byte-identical across both objects. Computing the real `ActionItem` first
and reading these fields off the constructed object is the only way to
satisfy that cross-object invariant without either re-implementing
`action_item_adapter`'s logic a second time (drift risk between two
independent derivations of the same row) or leaving `action_item_ref` as
ANOTHER synthesized-unbacked placeholder when the object it names in fact
exists. Matrix §1.1 calls `action_item_ref` "unmappable as-is... there is no
second object to reference" -- true before `action_item_adapter.py` existed;
not true since it landed (`origin/main`, PR #4749/#4758). This adapter's own
argument for treating that row as settled-by-composition, not as an open
ruling, is offered here for the conductor to see, same disclosure spirit as
every other placeholder below -- it is not asserted as matrix-endorsed
either.

Several `ActionIntent` fields have NO usable legacy analogue at all (matrix
§1.1, corrected round 2, 2026-08-24):

- `target{system,object_ref,surface}`: Magazine's real `target_id` is
  DERIVED at read time by `targetId()` (`operations-repository.ts:518-525`),
  not stored -- re-implementing that kind-specific derivation is out of this
  adapter's scope. `intent_kind` (a real, legacy-sourced fact) is carried as
  `object_ref.object_kind`; the rest of the reference is a disclosed
  placeholder.
- `authority_required.scope` / `.expires_after_seconds`: legacy hardcodes a
  role CHECK constant with no scope or expiry concept at all. `role` maps
  directly from `effective_role`; `expires_after_seconds` is DERIVED from
  the real `created_at`->`expires_at` delta (matrix §1.2's confirmed 24h
  operator-authorization window), which is a genuine fact -- but reusing an
  intent-level window as a per-authorization-grant expiry is this adapter's
  own placeholder, not a matrix-endorsed equivalence.
- `input_revision_hash` / `arguments_hash`: the matrix's own words -- "needs
  a ruling on which canonical hash slot [`request_hash`] actually satisfies"
  -- name an unresolved ambiguity between exactly these two fields. This
  adapter reuses the one legacy `request_hash` for BOTH, disclosed as a
  placeholder pending that ruling, not as a settled 1:2 mapping.

All three are disclosed exactly like `action_item_adapter.py`'s
priority/sla.due_at/current_intent_ref: a placeholder value, a prose
warning, AND a machine-checkable `pending_ruling` marker in
`extensions['com.balizero.research-os-adapters'].payload['pending_ruling']`
-- never silently asserted as a matrix-approved resolution.
"""

from __future__ import annotations

from research_os.models.action_intent import ActionIntent, AuthorityRequired, Target
from research_os.models.action_item import ActionItemRef
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
    legacy_content_hash,
    parse_legacy_timestamp,
    synthetic_uuid,
    unbacked_object_hash,
    unbacked_refs_extension,
)

SOURCE_SYSTEM = "bali-zero-magazine"
SOURCE_KIND = "ops_intents"
CANONICAL_KIND = "action_intent"

# No scope concept exists anywhere on ops_intents (matrix §1.1) -- disclosed
# placeholder string, not a real scope grant. Kept as a module constant so
# every call site (and every test asserting against it) names the same
# literal rather than re-typing a magic string.
_UNBACKED_AUTHORITY_SCOPE = "unbacked:no-scope-concept-in-legacy"


def adapt_ops_intent_to_action_intent(row: OpsIntentRow) -> AdapterResult[ActionIntent]:
    intent_id = row["intent_id"]

    # Same fused row, same admissibility criteria (matrix §1.0): a row the
    # sibling adapter judges inadmissible as an ActionItem has no
    # independent legacy source that could make it a valid ActionIntent
    # either. Delegate the accept/reject decision rather than duplicating
    # it (status-enum validity, clock-skew check) a second time.
    item_result = adapt_ops_intent_to_action_item(row)
    if not item_result.accepted:
        shared_reason = (
            item_result.loss_report.fields[0].reason
            if item_result.loss_report.fields
            else "action_item adaptation rejected this row"
        )
        report = AdapterLossReport(
            source_system=SOURCE_SYSTEM,
            source_kind=SOURCE_KIND,
            source_id=intent_id,
            canonical_kind=CANONICAL_KIND,
            fields=tuple(
                LegacyFieldReport(
                    k,
                    LegacyFieldFate.REJECTED,
                    None,
                    f"same row rejected by action_item adaptation: {shared_reason}",
                )
                for k in row
            ),
        )
        return AdapterResult(canonical=None, loss_report=report, accepted=False)

    item = item_result.canonical
    assert item is not None  # accepted=True guarantees this (AdapterResult's own invariant)

    created_at = parse_legacy_timestamp(row["created_at"])
    expires_at = parse_legacy_timestamp(row["expires_at"])

    action_item_ref = ActionItemRef(
        action_item_id=item.action_item_id, object_hash=item.object_hash
    )

    target = Target(
        system=SOURCE_SYSTEM,
        object_ref=ExactObjectRef(
            object_kind=row["intent_kind"],
            object_id=f"unbacked:{intent_id}",
            object_hash=unbacked_object_hash("target", intent_id),
        ),
        surface=None,
    )

    authority_required = AuthorityRequired(
        role=row["effective_role"],
        scope=_UNBACKED_AUTHORITY_SCOPE,
        # `expires_at` bounds a real 24h operator-authorization window at
        # intent-creation time (matrix §1.2, `operations-repository.ts`,
        # `delta > 86_400_000` throws) -- the duration itself is a genuine
        # fact; reusing it as this DIFFERENT field's expiry is the
        # disclosed placeholder part, not the number.
        expires_after_seconds=max(1, int((expires_at - created_at).total_seconds())),
    )

    intent = build_with_object_hash(
        ActionIntent,
        action_intent_id=synthetic_uuid("ops_intent", intent_id, "action_intent"),
        contract_version="research-os/v1.0.0",
        tenant="bali-zero",
        action_item_ref=action_item_ref,
        requested_action_spec_ref=item.requested_action_spec_ref,
        action_type=row["intent_kind"],
        target=target,
        arguments_ref=f"ops_intent:{intent_id}:params_json",
        arguments_hash=row["request_hash"],
        input_revision_hash=row["request_hash"],
        risk_class=item.risk_class,
        sensitivity=item.sensitivity,
        authority_required=authority_required,
        idempotency_key=row["idempotency_key"],
        expected_outcome_types=(),
        created_at=created_at,
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
            "requested_action_spec_ref",
            pending_ruling=(
                "target",
                "authority_required.scope",
                "authority_required.expires_after_seconds",
                "arguments_hash",
                "input_revision_hash",
            ),
        ),
    )

    fields: list[LegacyFieldReport] = [
        LegacyFieldReport(
            "intent_id",
            LegacyFieldFate.MAPPED,
            "action_intent_id",
            "synthesized 1:1 from the fused row (see synthesis.synthetic_uuid), same "
            "ID-split convention action_item_adapter.py already established for action_item_id",
        ),
        LegacyFieldReport(
            "actor_key",
            LegacyFieldFate.OMITTED,
            None,
            "names who requested the action; ActionIntent carries no requester-identity "
            "field -- the closest analog, ActionItem.owner_ref, lives on the sibling kind",
        ),
        LegacyFieldReport(
            "effective_role",
            LegacyFieldFate.APPROXIMATED,
            "authority_required.role",
            "static schema CHECK constant ('operator') carried as the role value; "
            "scope/expires_after_seconds still have no legacy source (see pending_ruling)",
        ),
        LegacyFieldReport(
            "policy_version",
            LegacyFieldFate.OMITTED,
            None,
            "no canonical field for a policy-engine version on ActionIntent",
        ),
        LegacyFieldReport(
            "idempotency_key",
            LegacyFieldFate.MAPPED,
            "idempotency_key",
            "exact name and semantic match",
        ),
        LegacyFieldReport(
            "intent_kind",
            LegacyFieldFate.MAPPED,
            "action_type",
            "direct semantic match onto a closed 5-value legacy enum, narrower than "
            "canonical's open RegisteredName (a safe subset); also reused as "
            "target.object_ref.object_kind, a real fact even though the rest of that "
            "reference is a disclosed placeholder",
        ),
        LegacyFieldReport(
            "params_json",
            LegacyFieldFate.APPROXIMATED,
            "arguments_ref",
            "params_json is inlined content, not a durable external pointer -- carried "
            "through as a descriptive reference string, not a real dereferenceable ref",
        ),
        LegacyFieldReport(
            "request_hash",
            LegacyFieldFate.APPROXIMATED,
            "arguments_hash / input_revision_hash / lineage.input_hashes",
            "one compound legacy hash reused across three canonical slots; the matrix's "
            "own words say this needs a ruling on which slot it actually satisfies -- "
            "disclosed via pending_ruling, not asserted as a settled 1:many mapping",
        ),
        LegacyFieldReport(
            "reason_code",
            LegacyFieldFate.OMITTED,
            None,
            "no canonical field for a request-time reason on ActionIntent",
        ),
        LegacyFieldReport(
            "status",
            LegacyFieldFate.OMITTED,
            None,
            "belongs to ActionItem.queue_state / ExecutionAttempt.state, kinds this "
            "slice does not produce",
        ),
        LegacyFieldReport(
            "attempt_limit",
            LegacyFieldFate.OMITTED,
            None,
            "no canonical ActionIntent field for a retry ceiling",
        ),
        LegacyFieldReport(
            "attempt_count",
            LegacyFieldFate.OMITTED,
            None,
            "belongs to ExecutionAttempt.attempt_number, a kind this slice excludes",
        ),
        LegacyFieldReport(
            "worker_id",
            LegacyFieldFate.OMITTED,
            None,
            "names the executing worker, belongs to ExecutionAttempt.executor",
        ),
        LegacyFieldReport(
            "claim_token",
            LegacyFieldFate.OMITTED,
            None,
            "execution-lease credential, not an authorization concept",
        ),
        LegacyFieldReport(
            "fencing_token",
            LegacyFieldFate.OMITTED,
            None,
            "optimistic-concurrency counter, no canonical ActionIntent equivalent",
        ),
        LegacyFieldReport(
            "heartbeat_at",
            LegacyFieldFate.OMITTED,
            None,
            "execution heartbeat, not an authorization-time concept",
        ),
        LegacyFieldReport(
            "lease_deadline",
            LegacyFieldFate.OMITTED,
            None,
            "execution-lease deadline, distinct from the authorization window used above",
        ),
        LegacyFieldReport(
            "effect_token",
            LegacyFieldFate.OMITTED,
            None,
            "execution-effect credential, no canonical ActionIntent field",
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
            "execution attestation detail, not an authorization concept",
        ),
        LegacyFieldReport(
            "attestation_expires_at",
            LegacyFieldFate.OMITTED,
            None,
            "execution attestation detail, not an authorization concept",
        ),
        LegacyFieldReport(
            "effect_consumed_at",
            LegacyFieldFate.OMITTED,
            None,
            "execution-effect timestamp, not authorization-time",
        ),
        LegacyFieldReport(
            "expires_at",
            LegacyFieldFate.APPROXIMATED,
            "authority_required.expires_after_seconds",
            "the real created_at->expires_at delta is used as the derived duration; "
            "using it for THIS field is this adapter's own placeholder (pending_ruling)",
        ),
        LegacyFieldReport(
            "started_at",
            LegacyFieldFate.OMITTED,
            None,
            "belongs to ExecutionAttempt.started_at, a kind this slice excludes",
        ),
        LegacyFieldReport(
            "completed_at",
            LegacyFieldFate.OMITTED,
            None,
            "execution timestamp, not an authorization-time concept",
        ),
        LegacyFieldReport(
            "failure_code",
            LegacyFieldFate.OMITTED,
            None,
            "belongs to ActionItem.close_reason, a kind this slice excludes",
        ),
        LegacyFieldReport("created_at", LegacyFieldFate.MAPPED, "created_at", "exact match"),
    ]

    warnings = (
        "requested_action_spec_ref is SYNTHESIZED_UNBACKED, identical to the value "
        "action_item_adapter.py already disclosed for the sibling ActionItem built from "
        "this same row -- taken directly from that object (not re-synthesized) so "
        "verify_action_intent_matches_action_item's equality invariant holds by "
        "construction, not by two independent derivations happening to agree.",
        "action_item_ref is NOT synthesized-unbacked: it pins the REAL ActionItem this "
        "same adapter package constructs from the identical row via "
        "action_item_adapter.adapt_ops_intent_to_action_item. Matrix §1.1 calls this "
        "field 'unmappable as-is... there is no second object to reference' -- true "
        "before that adapter existed, not true since it landed. This is this adapter's "
        "own argument for treating the row as settled by composition, offered to the "
        "conductor to see, not asserted as matrix-endorsed.",
        "risk_class/sensitivity are taken directly from the sibling ActionItem (not "
        "independently defaulted) to satisfy verify_action_intent_matches_action_item's "
        "cross-object equality invariant -- see that ActionItem's own disclosure for why "
        "they default to green/internal.",
        "target{system,object_ref,surface} is a synthesized placeholder: Magazine's real "
        "target_id is DERIVED by targetId() (kind-specific logic, not ported here) rather "
        "than stored. object_ref.object_kind carries the real intent_kind fact; the rest "
        "does not resolve to any materialized target object. Disclosed via pending_ruling, "
        "not asserted as the matrix's resolution (the matrix records this pairing as "
        "'needs a ruling', not this placeholder).",
        "authority_required.scope has no legacy source of any kind (disclosed placeholder "
        "string); authority_required.expires_after_seconds derives from a real "
        "created_at->expires_at delta but reuses an intent-level 24h authorization window "
        "as a per-grant expiry, which is this adapter's own placeholder pending a ruling, "
        "not a matrix-endorsed equivalence.",
        "arguments_hash and input_revision_hash both reuse the single legacy request_hash: "
        "the matrix's own words say this needs a ruling on which canonical hash slot it "
        "actually satisfies. Populating BOTH from the same value is this adapter's own "
        "placeholder pending that ruling, not a settled 1:many mapping.",
    )

    report = AdapterLossReport(
        source_system=SOURCE_SYSTEM,
        source_kind=SOURCE_KIND,
        source_id=intent_id,
        canonical_kind=CANONICAL_KIND,
        fields=tuple(fields),
        warnings=warnings,
    )
    assert_every_legacy_field_accounted_for(dict(row), report)
    return AdapterResult(canonical=intent, loss_report=report, accepted=True)
