from __future__ import annotations

from research_os.models.action_intent import verify_action_intent_matches_action_item

from backend.services.research_os.action_intent_adapter import adapt_ops_intent_to_action_intent
from backend.services.research_os.action_item_adapter import adapt_ops_intent_to_action_item
from backend.services.research_os.loss_report import (
    LegacyFieldFate,
    LossReportIncompleteError,
    assert_every_legacy_field_accounted_for,
)
from backend.tests.services.research_os.conftest import make_ops_intent_row

# The classification fields `verify_action_intent_matches_action_item` requires
# the two sibling objects to hold identically (that function compares six things
# in total; these are the two that are also adapter-chosen placeholders). Written
# out by hand ON PURPOSE: the invariant lives in imperative `if ... raise` code
# with no runtime handle on its field list, so there is nothing honest to derive
# this from. Adding a third shared placeholder means extending this tuple --
# a real limitation, stated rather than dressed up as automatic coverage.
_CLASSIFICATION_FIELDS_SHARED_BY_INVARIANT = ("risk_class", "sensitivity")


def test_adapts_a_succeeded_row_into_a_valid_action_intent(ops_intent_row):
    result = adapt_ops_intent_to_action_intent(ops_intent_row)

    assert result.accepted
    intent = result.canonical
    assert intent is not None
    assert intent.action_type == "rerun_collector"
    assert intent.idempotency_key == "idem-key-0001"


def test_every_legacy_field_is_accounted_for_never_silently_dropped(ops_intent_row):
    result = adapt_ops_intent_to_action_intent(ops_intent_row)

    # Re-run the same check the adapter runs internally, independently from
    # the test suite -- the exit criterion is a PARITY test, not a trust of
    # the adapter's own bookkeeping.
    assert_every_legacy_field_accounted_for(dict(ops_intent_row), result.loss_report)
    fates = result.loss_report.fates()
    assert set(fates) == set(ops_intent_row)
    assert all(isinstance(f, LegacyFieldFate) for f in fates.values())


def test_cross_object_invariant_holds_against_the_sibling_action_item(ops_intent_row):
    """The strongest possible test for this slice: not a hand-rolled
    assertion about what the adapter SHOULD have done, but a direct call to
    the package's own cross-object invariant function
    (`action_intent.verify_action_intent_matches_action_item`), which raises
    `ValueError` naming the exact diverged field on any mismatch. A silent
    pass here means the two sibling adapters, run independently on the same
    row, produced objects the canonical package itself considers consistent.
    """

    item_result = adapt_ops_intent_to_action_item(ops_intent_row)
    intent_result = adapt_ops_intent_to_action_intent(ops_intent_row)
    assert item_result.accepted and intent_result.accepted
    item = item_result.canonical
    intent = intent_result.canonical
    assert item is not None and intent is not None

    verify_action_intent_matches_action_item(item, intent)  # raises on any mismatch


def test_action_item_ref_pins_the_real_sibling_action_item(ops_intent_row):
    item_result = adapt_ops_intent_to_action_item(ops_intent_row)
    intent_result = adapt_ops_intent_to_action_intent(ops_intent_row)
    item = item_result.canonical
    intent = intent_result.canonical
    assert item is not None and intent is not None

    assert intent.action_item_ref.action_item_id == item.action_item_id
    assert intent.action_item_ref.object_hash == item.object_hash


def test_requested_action_spec_ref_and_risk_fields_match_sibling_exactly(ops_intent_row):
    """Per `action_intent.py`'s own cross-object invariant: these three
    fields must be BYTE-IDENTICAL across the two sibling objects, not
    independently re-derived values that happen to agree.
    """

    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    assert item is not None and intent is not None

    assert intent.requested_action_spec_ref == item.requested_action_spec_ref
    assert intent.risk_class == item.risk_class
    assert intent.sensitivity == item.sensitivity


def test_a_field_shared_by_invariant_is_declared_pending_by_both_siblings_or_neither(
    ops_intent_row,
):
    """The structural half of the test above, and the reason it exists.

    `test_requested_action_spec_ref_and_risk_fields_match_sibling_exactly`
    proves the two objects carry the SAME VALUE. It says nothing about
    whether they make the same CLAIM about that value -- and for eight
    weeks they did not. `action_intent_adapter` declared `risk_class` and
    `sensitivity` in its `pending_ruling` (a Kimi K3 review, 2026-08-24,
    found an inherited placeholder disclosed only in prose is invisible to
    a consumer reading the machine-checkable channel); `action_item_adapter`
    -- the object that ORIGINATES both values, from which the intent
    inherits them precisely to satisfy the invariant above -- did not. The
    cure had landed on the heir and not on the source.

    The observable consequence was a contradiction, not an untidiness: for
    ONE legacy row, a consumer branching on `pending_ruling` distrusted the
    ActionIntent's classification and trusted the ActionItem's, for the two
    same fields holding the two same values by invariant. Whichever way it
    resolved that, one of the two answers was wrong.

    On the shape of the check, corrected after an adversarial review (Kimi
    K3, 2026-08-26) refuted the first version of this docstring. That version
    claimed the field set was "derived from the invariant, not a remembered
    list". It was not: the names were hardcoded and equality merely FILTERED
    them -- and that filter was the actual defect, not just an overclaim. If
    the cross-object invariant ever broke on one of these fields, that field
    would compare unequal, drop OUT of the set, and leave this guard silently
    weaker exactly when the objects had started to disagree. A guard whose
    coverage shrinks in the presence of the fault is worse than no guard.

    So equality is now a PRECONDITION, not a filter: the package's own
    `verify_action_intent_matches_action_item` runs first and raises on any
    divergence, and only then -- with the two fields guaranteed equal by the
    invariant itself -- is the declaration compared. The names stay written
    out, honestly, because there is no runtime handle on that function's
    field list; if a third shared placeholder is added, `_CLASSIFICATION_
    FIELDS_SHARED_BY_INVARIANT` must be extended by hand, and that is a
    stated limitation rather than a claim of automatic coverage.

    GUILT: drop `risk_class`/`sensitivity` from either adapter's
    `pending_ruling` tuple and this goes red. INNOCENCE: it passes when both
    declare them, and equally when NEITHER does -- it forbids divergence,
    not any particular resolution, because the resolution is a ruling that
    is genuinely still open (`contract-pass-001.md` §9, under
    `research/operations/execution/research-os-v1.0.0/evidence/p04/`).
    """

    item = adapt_ops_intent_to_action_item(ops_intent_row).canonical
    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    assert item is not None and intent is not None

    # PRECONDITION, not a filter. If the two objects have diverged on any
    # shared field, this raises and names it -- rather than letting the
    # diverged field quietly leave the set this guard then checks.
    verify_action_intent_matches_action_item(item, intent)

    ns = "com.balizero.research-os-adapters"
    item_pending = set(item.extensions[ns].payload.get("pending_ruling", []))
    intent_pending = set(intent.extensions[ns].payload.get("pending_ruling", []))

    diverged = {
        name
        for name in _CLASSIFICATION_FIELDS_SHARED_BY_INVARIANT
        if (name in item_pending) != (name in intent_pending)
    }
    assert not diverged, (
        f"{sorted(diverged)}: these fields are equal across the two sibling objects by "
        "invariant, but only one adapter declares them in pending_ruling. A consumer "
        "branching on the machine-checkable channel gets two different answers about "
        "the same value. Declare them on BOTH adapters, or on neither."
    )


def test_unbacked_refs_are_machine_checkable_not_only_prose(ops_intent_row):
    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    marker = intent.extensions["com.balizero.research-os-adapters"]
    assert marker.extension_version == "1.1.0"
    assert set(marker.payload["unbacked_refs"]) == {"requested_action_spec_ref"}


def test_pending_ruling_is_machine_checkable_not_only_prose(ops_intent_row):
    """Matrix §1.1 (corrected, independent review round 2, 2026-08-24) grades
    `action_intent_id`/`action_item_ref`/`target`/`input_revision_hash`/
    `authority_required` all 🔴 "unmappable as-is -- needs a ruling". Of
    these, `action_intent_id` and `action_item_ref` are settled by this
    adapter's own composition argument (see the adapter's module docstring),
    not left pending; the rest carry genuinely open placeholders and must
    be machine-checkable, not only prose.
    """

    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    marker = intent.extensions["com.balizero.research-os-adapters"]
    assert set(marker.payload["pending_ruling"]) == {
        "target",
        "authority_required.scope",
        "authority_required.expires_after_seconds",
        "input_revision_hash",
        "risk_class",
        "sensitivity",
    }


def test_extensions_is_always_explicitly_set_never_omitted(ops_intent_row):
    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    assert "extensions" in intent.model_fields_set


def test_status_value_set_map_covers_every_legacy_status():
    for status in [
        "queued",
        "claimed",
        "running",
        "succeeded",
        "failed",
        "cancelled_revoked",
        "outcome_unknown",
    ]:
        row = make_ops_intent_row(status=status)
        result = adapt_ops_intent_to_action_intent(row)
        assert result.accepted, f"status={status} should be adaptable"


def test_unrecognized_status_is_rejected_with_full_field_ledger():
    row = make_ops_intent_row(status="not_a_real_status")
    result = adapt_ops_intent_to_action_intent(row)

    assert not result.accepted
    assert result.canonical is None
    assert set(result.loss_report.fates()) == set(row)
    assert all(f == LegacyFieldFate.REJECTED for f in result.loss_report.fates().values())


def test_clock_skew_row_is_rejected_not_silently_coerced():
    row = make_ops_intent_row(
        created_at="2026-08-20T12:00:00+00:00", expires_at="2026-08-20T10:00:00+00:00"
    )
    result = adapt_ops_intent_to_action_intent(row)

    assert not result.accepted
    assert result.canonical is None


def test_incomplete_loss_report_is_caught_by_the_guard(ops_intent_row):
    result = adapt_ops_intent_to_action_intent(ops_intent_row)
    truncated_fields = result.loss_report.fields[:-1]
    from dataclasses import replace

    truncated_report = replace(result.loss_report, fields=truncated_fields)

    try:
        assert_every_legacy_field_accounted_for(dict(ops_intent_row), truncated_report)
        raised = False
    except LossReportIncompleteError:
        raised = True
    assert raised, "dropping one field's report entry must be caught, not silently pass"


def test_authority_required_expires_after_seconds_is_derived_not_arbitrary(ops_intent_row):
    """`created_at`->`expires_at` in the fixture is exactly 2 hours apart --
    a concrete, checkable number rather than trusting the derivation is
    correct by inspection alone.
    """

    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    assert intent.authority_required.expires_after_seconds == 2 * 60 * 60


def test_target_derives_real_kind_and_id_from_params_json_when_available():
    """The DEFAULT ops_intent_row fixture uses intent_kind='rerun_collector'
    with params_json='{"collector": "regulatory-watcher"}' -- no
    'failed_run_id' key, so it exercises the FALLBACK path (see the next
    test). This test constructs a row whose params_json actually matches
    what Magazine's own targetId()/targetKey() derivation
    (operations-repository.ts:518-533) expects for each of the 5 known
    intent_kind values, and confirms the adapter now ports that derivation
    instead of fabricating an intent-scoped placeholder.
    """

    cases = [
        ("rerun_collector", "failed_run_id", "run-xyz-1", "collector"),
        ("rebuild_edition", "edition_id", "edition-2026-08", "edition"),
        ("refresh_research_job", "research_job_id", "job-42", "research"),
        ("quarantine_story", "story_id", "story-99", "story"),
        ("release_story", "story_id", "story-100", "story"),
    ]
    for intent_kind, field_name, real_id, expected_target_kind in cases:
        import json as _json

        row = make_ops_intent_row(
            intent_kind=intent_kind, params_json=_json.dumps({field_name: real_id})
        )
        intent = adapt_ops_intent_to_action_intent(row).canonical
        assert intent is not None, f"{intent_kind} row should be adaptable"
        assert intent.target.object_ref.object_kind == expected_target_kind, intent_kind
        assert intent.target.object_ref.object_id == real_id, intent_kind
        assert not intent.target.object_ref.object_id.startswith("unbacked:"), intent_kind


def test_target_falls_back_to_unbacked_placeholder_when_params_json_lacks_expected_key(
    ops_intent_row,
):
    """The DEFAULT fixture's params_json does not carry the 'failed_run_id'
    key that intent_kind='rerun_collector' expects -- this must fall back
    to the old intent-scoped unbacked pointer, not crash and not silently
    use the wrong value.
    """

    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    assert intent is not None
    assert intent.target.object_ref.object_kind == "rerun_collector"
    assert intent.target.object_ref.object_id == f"unbacked:{ops_intent_row['intent_id']}"


def test_target_falls_back_when_params_json_is_unparseable():
    row = make_ops_intent_row(intent_kind="quarantine_story", params_json="not valid json{{{")
    intent = adapt_ops_intent_to_action_intent(row).canonical
    assert intent is not None
    assert intent.target.object_ref.object_id == f"unbacked:{row['intent_id']}"


def test_arguments_hash_is_a_real_recomputable_hash_of_params_json(ops_intent_row):
    """arguments_hash must be a content hash of the actual arguments
    (params_json), NOT the legacy request_hash -- a Kimi K3 review found
    reusing request_hash would impersonate a verifiable integrity hash
    while never actually verifying (request_hash hashes the whole request
    envelope, not just the arguments).
    """

    from backend.services.research_os.synthesis import legacy_content_hash

    intent = adapt_ops_intent_to_action_intent(ops_intent_row).canonical
    assert intent is not None
    assert intent.arguments_hash == legacy_content_hash(ops_intent_row["params_json"])
    assert intent.arguments_hash != ops_intent_row["request_hash"]
