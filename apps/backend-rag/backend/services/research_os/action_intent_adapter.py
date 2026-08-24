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
and reading these fields off the constructed object is the most direct way
to satisfy that cross-object invariant without re-implementing
`action_item_adapter`'s logic a second time (drift risk between two
independent derivations of the same row) or leaving `action_item_ref` as
ANOTHER synthesized-unbacked placeholder when the object it names in fact
exists -- NOT, as an earlier version of this docstring overstated, "the
only way": a shared private derivation helper for the common sub-facts
would give the same by-construction equality without this adapter
inheriting the sibling's admissibility policy (see the Kimi K3 finding
below). Matrix §1.1 calls `action_item_ref` "unmappable as-is... there is
no second object to reference" -- true before `action_item_adapter.py`
existed; not true since it landed (`origin/main`, PR #4749/#4758). This
adapter's own argument for treating that row as settled-by-composition, not
as an open ruling, is offered here for the conductor to see, same
disclosure spirit as every other placeholder below -- it is not asserted as
matrix-endorsed either.

KIMI K3 ADVERSARIAL REVIEW (this session, 2026-08-24) examined this
composition and the three placeholder families below; its findings that
changed this file (not just disclosure) are folded in at each site:

1. **The cross-object invariant is tautological for this source** (composed
   fields can never diverge, so a bug in the sibling propagates to both
   objects and still verifies) -- disclosed as a residual risk, not fixed
   in code: the alternative (independent re-derivation) reintroduces the
   drift risk composition was chosen to avoid.
2. **`target`'s premise was FALSE, not merely open.** The claim below (an
   earlier version read "no usable legacy analogue... re-implementing that
   kind-specific derivation is out of this adapter's scope") does not
   survive a read of the actual legacy code: `targetId()`/`targetKey()`
   (`operations-repository.ts:518-533`) are a 6-line, 4-branch pure
   function over `params_json`, a field this adapter already has. This
   adapter now PORTS that derivation (`_derive_target`, below) rather than
   fabricating an intent-scoped placeholder that broke Magazine's own
   target-key co-reference (its concurrency model IS target-key fencing).
   `object_kind` also no longer asserts `intent_kind` (the ACTION type) as
   if it were the TARGET's kind -- that was a false statement, not a
   disclosed gap.
3. **`arguments_hash` reusing `request_hash` was a materially worse lie
   than a marked placeholder**: `request_hash` hashes the whole request
   ENVELOPE (`schema_version`+`intent_kind`+`reason_code`+`expires_at`+
   `params`, `operations-repository.ts:710-720`), not the arguments alone
   -- it is syntactically a valid sha256 (so it passes `Sha256Hex`
   validation) but can never verify against a consumer's own recomputed
   hash of `arguments_ref`'s content. This adapter now hashes the REAL
   argument content (`legacy_content_hash(params_json)`) instead --
   verifiable, not merely disclosed. `input_revision_hash` still reuses
   `request_hash` and stays a disclosed placeholder (its semantics shift
   when `expires_at` changes with no input change -- genuinely unresolved,
   left to the ruling).
4. **`expires_after_seconds`'s `max(1, ...)` clamp was a latent
   fabrication path**, unreachable today only because the sibling rejects
   `expires_at <= created_at` first -- if that sibling check is ever
   revisited, the clamp would silently manufacture a 1-second grant instead
   of failing. Removed: the field's own `gt=0` validator now does the
   rejecting, honestly, if that assumption ever breaks.

Two fields the matrix (§1.1, corrected round 2, 2026-08-24) still grades
🔴 "unmappable as-is -- needs a ruling" remain genuine open placeholders
after the above:

- `authority_required.scope` / `.expires_after_seconds`: legacy hardcodes a
  role CHECK constant with no scope or expiry concept at all. `role` maps
  directly from `effective_role`; `expires_after_seconds` is DERIVED from
  the real `created_at`->`expires_at` delta (matrix §1.2's confirmed 24h
  operator-authorization window), which is a genuine fact -- but reusing an
  intent-level window as a per-authorization-grant expiry is this adapter's
  own placeholder, not a matrix-endorsed equivalence.
- `input_revision_hash`: the matrix's own words -- "needs a ruling on which
  canonical hash slot [`request_hash`] actually satisfies" -- this adapter
  keeps `request_hash` here (not `arguments_hash`, now resolved above),
  disclosed as a placeholder pending that ruling.
- `risk_class`/`sensitivity`: composed from the sibling `ActionItem`, which
  itself defaults them to green/internal placeholders -- the Kimi K3 review
  found this inherited-placeholder fact was disclosed only in prose on an
  earlier version of this file and invisible to a consumer reading just the
  machine-checkable channel; both are now named in `pending_ruling` too.

All are disclosed a placeholder value, a prose warning, AND a
machine-checkable `pending_ruling` marker in
`extensions['com.balizero.research-os-adapters'].payload['pending_ruling']`
-- never silently asserted as a matrix-approved resolution.
"""

from __future__ import annotations

import json

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

# Port of Magazine's own targetId()/targetKey() derivation
# (operations-repository.ts:518-533): intent_kind -> (real target kind,
# the params_json field holding the real target id). A Kimi K3 adversarial
# review (2026-08-24) found the previous version of this adapter declined
# this derivation on a false premise ("no usable legacy analogue") and
# fabricated an intent-scoped id instead, which silently broke Magazine's
# own target-key co-reference (its concurrency model IS target-key
# fencing: two intents on the same story must share one target).
_TARGET_KIND_FIELD: dict[str, tuple[str, str]] = {
    "rerun_collector": ("collector", "failed_run_id"),
    "rebuild_edition": ("edition", "edition_id"),
    "refresh_research_job": ("research", "research_job_id"),
    "quarantine_story": ("story", "story_id"),
    "release_story": ("story", "story_id"),
}


def _derive_target(intent_kind: str, params_json: str, intent_id: str) -> tuple[str, str, bool]:
    """Returns (target_kind, target_id, derived). `derived=True` means both
    values are REAL legacy facts read off `params_json`, matching
    Magazine's own `targetId()`/`targetKey()` logic exactly. `derived=False`
    is the defensive fallback -- `intent_kind` unrecognized, `params_json`
    unparseable, or the expected key absent/empty -- in which case the
    caller falls back to an intent-scoped unbacked pointer rather than
    crashing or fabricating a target identity. Should not trigger for any
    row that passed the sibling ActionItem adapter's own validation, since
    `intent_kind` is already a closed 5-value CHECK-constrained enum and
    `params_json` is NOT NULL on the legacy schema -- disclosed defensively,
    not because it is expected to occur.
    """

    mapping = _TARGET_KIND_FIELD.get(intent_kind)
    if mapping is None:
        return intent_kind, intent_id, False
    target_kind, field_name = mapping
    try:
        parsed = json.loads(params_json)
        value = parsed.get(field_name) if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, AttributeError):
        value = None
    if isinstance(value, str) and value:
        return target_kind, value, True
    return intent_kind, intent_id, False


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

    target_kind, target_ref_id, target_derived = _derive_target(
        row["intent_kind"], row["params_json"], intent_id
    )
    target = Target(
        system=SOURCE_SYSTEM,
        object_ref=ExactObjectRef(
            object_kind=target_kind,
            object_id=target_ref_id if target_derived else f"unbacked:{intent_id}",
            object_hash=unbacked_object_hash(
                "target", target_ref_id if target_derived else intent_id
            ),
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
        # disclosed placeholder part, not the number. No `max(1, ...)`
        # clamp: the sibling ActionItem adapter already rejects any row
        # with expires_at <= created_at before this code path is reached,
        # so a non-positive delta here would be this adapter's own bug --
        # let AuthorityRequired's `gt=0` validator raise honestly rather
        # than silently fabricate a 1-second grant (Kimi K3 finding).
        expires_after_seconds=int((expires_at - created_at).total_seconds()),
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
        # A REAL, recomputable content hash of the arguments this ref
        # names -- NOT row["request_hash"] (an idempotency fingerprint
        # over the whole request ENVELOPE, {schema_version, intent_kind,
        # reason_code, expires_at, params}, operations-repository.ts:
        # 710-720). request_hash is syntactically a valid sha256 so it
        # would have passed Sha256Hex validation while never verifying
        # against a consumer's own recompute of params_json's content --
        # a Kimi K3 review (2026-08-24) called that shape strictly worse
        # than a marked placeholder. legacy_content_hash(params_json) is
        # genuinely recomputable by any consumer holding the same raw row.
        arguments_hash=legacy_content_hash(row["params_json"]),
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
                "input_revision_hash",
                "risk_class",
                "sensitivity",
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
            "action_type / target.object_ref (input to _derive_target)",
            "direct semantic match onto a closed 5-value legacy enum, narrower than "
            "canonical's open RegisteredName (a safe subset); also selects which "
            "params_json field _derive_target reads for the real target kind+id (a "
            "port of Magazine's own targetId()/targetKey() switch) -- intent_kind "
            "itself is no longer asserted AS the target's kind (that was a false "
            "statement an earlier version of this adapter made, per the Kimi K3 review)",
        ),
        LegacyFieldReport(
            "params_json",
            LegacyFieldFate.APPROXIMATED,
            "arguments_ref / arguments_hash / target.object_ref (via _derive_target)",
            "params_json is inlined content, not a durable external pointer -- carried "
            "through as a descriptive reference string (arguments_ref) for which "
            "arguments_hash is now a REAL, recomputable content hash "
            "(legacy_content_hash(params_json), not row['request_hash']); also the "
            "source _derive_target reads to recover the real target kind+id per "
            "Magazine's own targetId()/targetKey() logic",
        ),
        LegacyFieldReport(
            "request_hash",
            LegacyFieldFate.APPROXIMATED,
            "input_revision_hash / lineage.input_hashes",
            "an idempotency fingerprint over the WHOLE request envelope "
            "(schema_version+intent_kind+reason_code+expires_at+params, "
            "operations-repository.ts:710-720), not a pure content-revision hash of "
            "the arguments alone -- reused here ONLY for input_revision_hash "
            "(disclosed placeholder pending a ruling: a Kimi K3 review found its "
            "'revision' changes when only expires_at changes, with no input change) "
            "and lineage.input_hashes (a hash-of-hash provenance token, the most "
            "defensible of its uses -- no longer also reused for arguments_hash, "
            "which now derives from params_json content instead)",
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
        "they default to green/internal. Both are in pending_ruling (not just this prose): "
        "a Kimi K3 review (2026-08-24) found an inherited placeholder disclosed only in "
        "prose is invisible to a consumer reading just the machine-checkable channel.",
        "target{system,object_ref,surface}: object_ref.object_kind/object_id now derive "
        "from a real port of Magazine's targetId()/targetKey() logic (_derive_target, "
        "reading params_json per intent_kind) -- NOT the intent_kind-as-target_kind / "
        "intent_id-as-target_id placeholder an earlier version of this adapter shipped, "
        "which a Kimi K3 review found (a) asserted a false fact (the ACTION type "
        "presented as the TARGET's kind) and (b) broke Magazine's own target-key "
        "co-reference (its concurrency model IS target-key fencing -- two intents on "
        "the same story must resolve to the same target). object_hash remains a "
        "synthesized-unbacked hash (no real canonical Target object exists to hash), "
        "and this field stays in pending_ruling on that basis, not because the kind/id "
        "are fabricated anymore -- falls back to the old intent-scoped placeholder only "
        "if params_json fails to parse or the expected key is absent (should not occur "
        "for a row that passed the sibling adapter's own validation; disclosed "
        "defensively, see _derive_target's docstring).",
        "authority_required.scope has no legacy source of any kind (disclosed placeholder "
        "string); authority_required.expires_after_seconds derives from a real "
        "created_at->expires_at delta but reuses an intent-level 24h authorization window "
        "as a per-grant expiry, which is this adapter's own placeholder pending a ruling, "
        "not a matrix-endorsed equivalence. No max(1, ...) clamp: a Kimi K3 review found "
        "the clamp was a latent fabrication path (unreachable only because the sibling "
        "rejects expires_at<=created_at first) -- removed so the field's own gt=0 "
        "validator rejects honestly if that assumption is ever violated, rather than "
        "silently manufacturing a 1-second grant.",
        "arguments_hash is now legacy_content_hash(params_json) -- a REAL, recomputable "
        "content hash of the actual arguments, not row['request_hash'] (an idempotency "
        "fingerprint over the whole request envelope, which a Kimi K3 review found would "
        "have impersonated a verifiable integrity hash while never actually verifying). "
        "input_revision_hash still reuses request_hash and remains a disclosed "
        "placeholder pending a ruling on whether that's the right source at all -- its "
        "'revision' changes whenever expires_at changes with no input change.",
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
