"""D4's admission decision, executed — one row per exclusion reason, plus the three counts.

WHAT THIS PINS. That admission is a DECISION and not a mapping: each rule of D4 is exercised on
a record that fails exactly that rule, the reason is asserted by name, and the fully-sourced
record is admitted. Plus the finding D4 makes structural: mapping coverage, available source
information and admissible records are three different numbers, and on a mixed cohort they
differ from each other.

WHAT IT DOES NOT PIN. No legacy table is read, no adapter runs, nothing touches PostgreSQL. The
records here are legacy-SHAPED — built to carry the defects `01-naga-baseline-inventory.md` and
`02-p04-adapter-mapping.md` measured in the real schema (a `content_hash` that hashes the URL
string, a freeform `source_span_hint`, no `IntelEvent`) — but they are fixtures, not rows. R2's
dry run against the real 3,119 rows is the observation; this is its specification.

THE HONEST EXPECTATION. On today's legacy corpus this predicate admits ZERO. That is asserted
below as a positive result, not worked around.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from research_os.hashing import object_hash

from .research_os_admission_reference import (
    EXCLUSION_REASONS,
    Admitted,
    Excluded,
    admit,
    counts,
)

_BODY = (
    "SYNTHETIC INSTRUMENT 01. Article 1 paragraph 1. The processing fee for a Class A "
    "application is IDR 1,234,000 with effect from 1 March 2026."
)
_QUOTE = "The processing fee for a Class A application is IDR 1,234,000"
_URL = "https://example.invalid/synthetic-instrument-01"
_EVENT_ID = "11111111-0000-4000-8000-0000000000e1"

_REPO_ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "packages" / "research-os-core").is_dir()
)
_SEED_COHORT_PATH = (
    _REPO_ROOT
    / "research/operations/execution/research-os-v1.0.0/evidence/p06"
    / "ros-v1-p06-naga-prep-b01/fixtures/seed_public_regulatory/01_z2_seed_cohort.json"
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intel_event(event_id: str = _EVENT_ID) -> dict[str, Any]:
    """A minimal schema-valid, hash-correct canonical `IntelEvent` for the admissible fixture.

    Exists so `_source()` can give rule 5's cured predicate something real to resolve
    `_admissible_record()`'s `source_event_ref` against -- the presence-only predecessor never
    needed this because it never looked past the id string.
    """

    node: dict[str, Any] = {
        "event_id": event_id,
        "contract_version": "research-os/v1.0.0",
        "tenant": "bali-zero",
        "event_type": "naga.regulatory_document.fetched",
        "producer": {
            "name": "naga.orchestrator.v1",
            "version": "1.0.0",
            "machine_class": "synthetic-fixture",
        },
        "source": {"uri": _URL, "source_type": "government.gazette"},
        "times": {
            "observed_at": "2026-03-01T00:00:00Z",
            "ingested_at": "2026-03-01T00:05:00Z",
        },
        "identity": {
            "content_hash": _sha256(_BODY),
            "idempotency_key": "synthetic-instrument-01",
        },
        "classification": {"risk_class": "green", "sensitivity": "public"},
        "lineage": {
            "pipeline_run_id": "22222222-0000-4000-8000-000000000002",
            "input_event_refs": [],
        },
        "payload_ref": {"ref_type": "reference", "uri": _URL, "content_hash": _sha256(_BODY)},
        "retention": {"retention_class": "public_record", "legal_hold": False},
        "object_hash": "0" * 64,
    }
    node["object_hash"] = object_hash(node)
    return node


_VERSION_ID = "synthetic-instrument-01@2026-03-01"
_LOCATOR = "art-1/para-1"


def _source() -> dict[str, Any]:
    """The SourceSnapshot: body, the events it can resolve, and the two mappings rules 3 and 4
    resolve against — the version registered for THIS body hash, and where each locator IS."""

    start = _BODY.index(_QUOTE)
    return {
        "body": _BODY,
        "intel_events": {_EVENT_ID: _intel_event()},
        "document_versions": {_VERSION_ID: _sha256(_BODY)},
        "locators": {_LOCATOR: {"start": start, "end": start + len(_QUOTE)}},
    }


def _admissible_record() -> dict[str, Any]:
    """A fully-sourced record: every D4 input present and internally consistent.

    Every figure is invented. This is the shape the Z2 seed cohort has and the shape a legacy
    row does NOT have — the distance between this dict and `_legacy_record()` is exactly the
    work `naga_admission.py` will have to do before anything can be backfilled.
    """

    return {
        "id": "synthetic-0001",
        "document_id": _URL,
        "document_version_id": "synthetic-instrument-01@2026-03-01",
        "document_content_hash": _sha256(_BODY),
        "source_span": {
            "locator": "art-1/para-1",
            "quoted_text": _QUOTE,
            "quote_hash": _sha256(_QUOTE),
        },
        "statement": {
            "subject_ref": "synthetic.instrument.01",
            "predicate": "synthetic.fee.amount",
            "object_ref_or_value": "IDR 1,234,000",
            "derived_from_span": True,
        },
        "source_event_ref": {"event_id": "11111111-0000-4000-8000-0000000000e1"},
        "classification": {"risk_class": "low", "sensitivity": "public", "rights": "public-domain"},
        "retention": {"retention_class": "regulatory-5y"},
        "review": {"state": "unreviewed"},
        "manifest_family_id": "aaaaaaaa-0000-4000-8000-00000000000a",
    }


def _legacy_record() -> dict[str, Any]:
    """A NAGA row as it really is today, in the three ways that matter.

    `content_hash` is `sha256(url)` — the URL STRING, per the migration read in
    `01-naga-baseline-inventory.md` §2; the span is the freeform `source_span_hint`; and there
    is no `IntelEvent`, because NAGA sources are not events (G6, a cross-packet dependency on
    P05). Nothing here is invented for convenience: each defect is one the bundle measured.
    """

    return {
        "id": "legacy-0001",
        "document_id": _URL,
        "document_content_hash": _sha256(_URL),
        "source_span_hint": "somewhere in article 1",
        "claim_text": "the processing fee is IDR 1,234,000",
        "review": {"state": "unreviewed"},
    }


def test_the_fully_sourced_record_is_admitted() -> None:
    """Innocence control. Without it every negative row below could pass vacuously.

    If `_admissible_record()` were itself inadmissible for some unrelated reason, every negative
    test would still be green while proving nothing about the rule it names.
    """

    decision = admit(_admissible_record(), _source())
    assert isinstance(decision, Admitted), decision
    assert decision.family_id == "aaaaaaaa-0000-4000-8000-00000000000a"


def test_a_legacy_shaped_record_is_excluded_and_names_its_first_defect() -> None:
    """The real corpus, honestly: today's NAGA row does not get in.

    Its first failing rule is `statement_not_from_source`, because there is no atomizer and no
    quoted span — so no triple can be derived from a source. That is not a bug to route around;
    it is the reason the statement atomizer is on the deferred list.
    """

    decision = admit(_legacy_record(), _source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "statement_not_from_source"


def test_a_url_content_hash_is_excluded_by_name() -> None:
    """`content_hash_is_url` — the exclusion `02-p04-adapter-mapping.md:83-84` demands.

    Detected POSITIVELY: the stored hash is compared against `sha256(document_id)`, so renaming
    the column or copying the value elsewhere does not hide it. The record is otherwise fully
    sourced, so this row fails for exactly one reason.
    """

    record = _admissible_record()
    record["document_content_hash"] = _sha256(_URL)
    decision = admit(record, _source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "content_hash_is_url"


def test_a_missing_exact_span_is_excluded_by_name() -> None:
    """`exact_span_missing` — a locator plus a quote hash, or nothing.

    Two mutations, one row: dropping the locator and corrupting the quote hash must BOTH be
    caught, because a `quote_hash` that does not hash its quote is a provenance claim that does
    not hold, and it would otherwise pass a presence-only check.
    """

    without_locator = _admissible_record()
    without_locator["source_span"].pop("locator")
    first = admit(without_locator, _source())
    assert isinstance(first, Excluded) and first.reason == "exact_span_missing"

    wrong_hash = _admissible_record()
    wrong_hash["source_span"]["quote_hash"] = _sha256("a different quotation entirely")
    second = admit(wrong_hash, _source())
    assert isinstance(second, Excluded) and second.reason == "exact_span_missing"


def test_a_fabricated_triple_is_excluded_by_name() -> None:
    """`statement_not_from_source` — `02-p04-adapter-mapping.md:59`, no fabricated triples.

    The quoted text is changed to something the document body does not contain: the span no
    longer anchors anything, so the triple is not derivable from a source even though every
    other field is present and internally consistent.
    """

    record = _admissible_record()
    record["source_span"]["quoted_text"] = "a sentence that appears nowhere in the document"
    record["source_span"]["quote_hash"] = _sha256(record["source_span"]["quoted_text"])
    decision = admit(record, _source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "statement_not_from_source"


def test_an_absent_intel_event_reference_is_excluded_by_name() -> None:
    """A `source_event_ref` naming an event NOT in the snapshot is a dangling reference.

    Presence of an `event_id` string is not provenance -- RESOLUTION is
    (R1-build-spec.md §3 rule 5, `02-p04-adapter-mapping.md:87`). The event_id here is a
    syntactically fine UUID that simply names nothing in `source["intel_events"]`: the
    presence-only predecessor would have PASSED this mutation, because it never looked past the
    string itself.
    """

    record = _admissible_record()
    record["source_event_ref"] = {"event_id": "99999999-0000-4000-8000-000000000000"}
    decision = admit(record, _source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "intel_event_identity_missing"


def test_a_resolved_but_invalid_intel_event_is_excluded_by_name() -> None:
    """Resolving to *something* is not enough -- the something must be a real `IntelEvent`.

    Two shapes of the same failure, both load-bearing: an object missing a required
    `IntelEvent` field never validates against `intel_event.schema.json` or
    `IntelEvent.model_validate`, and an object whose stored `object_hash` has been tampered with
    never matches the RECOMPUTED `research_os.hashing.object_hash`. The predicate trusts neither
    the `source_event_ref`'s say-so nor the resolved object's own claimed hash -- both mutations
    leave `record["source_event_ref"]` completely untouched, so only the cured resolution step
    can be catching them.
    """

    malformed_source = _source()
    malformed_node = malformed_source["intel_events"][_EVENT_ID]
    del malformed_node["classification"]
    # Rehash AFTER the deletion (codex round 1, MEDIUM at :246): with a stale hash the
    # hash gate alone rejected this, so schema/model validation could be deleted unnoticed.
    malformed_node["object_hash"] = object_hash(malformed_node)
    decision = admit(_admissible_record(), malformed_source)
    assert isinstance(decision, Excluded)
    assert decision.reason == "intel_event_identity_missing"

    tampered_source = _source()
    tampered_source["intel_events"][_EVENT_ID]["object_hash"] = _sha256("not the real content")
    decision2 = admit(_admissible_record(), tampered_source)
    assert isinstance(decision2, Excluded)
    assert decision2.reason == "intel_event_identity_missing"


def test_an_unrelated_valid_intel_event_is_not_provenance_for_this_record() -> None:
    """Codex round 1 BLOCKER 1: resolution without BINDING.

    The borrowed event is schema-valid, model-valid and hash-correct — it is simply the event
    for ANOTHER document. Resolution alone admitted it; binding to this record's own
    `document_id` and body hash does not. The innocence half is the same snapshot with the
    record pointing at its own event, which is admitted.
    """

    other_uri = "https://example.invalid/synthetic-instrument-02"
    other_hash = _sha256("SYNTHETIC INSTRUMENT 02. An unrelated document.")
    other_id = "11111111-0000-4000-8000-0000000000e2"

    def borrow(**changes: Any) -> Excluded | Admitted:
        # ONE binding gate broken per case, every other field left bound, so each gate is
        # proven on its own (a single borrowed event breaking all three at once let any one
        # gate be deleted unnoticed — measured by mutation on the first version of this row).
        node = _intel_event(other_id)
        node["source"]["uri"] = changes.get("uri", _URL)
        node["identity"]["content_hash"] = changes.get("identity_hash", _sha256(_BODY))
        node["payload_ref"]["content_hash"] = changes.get("payload_hash", _sha256(_BODY))
        node["object_hash"] = object_hash(node)
        source = _source()
        source["intel_events"][other_id] = node
        record = _admissible_record()
        record["source_event_ref"] = {"event_id": other_id}
        return admit(record, source)

    for case in ({"uri": other_uri}, {"identity_hash": other_hash}, {"payload_hash": other_hash}):
        decision = borrow(**case)
        assert isinstance(decision, Excluded), case
        assert decision.reason == "intel_event_identity_missing", case
    assert isinstance(borrow(), Admitted)


def test_a_stated_event_hash_that_disagrees_is_a_rejection() -> None:
    """A `source_event_ref.object_hash` is a claim about the resolved event, never a hint."""

    record = _admissible_record()
    record["source_event_ref"] = {"event_id": _EVENT_ID, "object_hash": "f" * 64}
    decision = admit(record, _source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "intel_event_identity_missing"

    record["source_event_ref"]["object_hash"] = _intel_event()["object_hash"]
    assert isinstance(admit(record, _source()), Admitted)


def test_an_invented_or_mismatched_version_is_excluded_by_name() -> None:
    """Codex round 1 BLOCKER 4: the version must be the one FOR this `(document_id, body hash)`."""

    invented = _admissible_record()
    invented["document_version_id"] = "synthetic-instrument-01@invented"
    first = admit(invented, _source())
    assert isinstance(first, Excluded) and first.reason == "source_version_missing"

    other_body = _source()
    other_body["document_versions"][_VERSION_ID] = _sha256("a different body")
    second = admit(_admissible_record(), other_body)
    assert isinstance(second, Excluded) and second.reason == "source_version_missing"


def test_a_genuine_quote_at_a_fictional_locator_is_excluded_by_name() -> None:
    """Codex round 1 BLOCKER 3: a truthy locator is not a location.

    Both halves keep the quote and its hash genuine: a locator naming nothing, and a locator
    whose offsets point somewhere else in the same body.
    """

    fictional = _admissible_record()
    fictional["source_span"]["locator"] = "art-9/para-9"
    first = admit(fictional, _source())
    assert isinstance(first, Excluded) and first.reason == "exact_span_missing"

    elsewhere = _source()
    elsewhere["locators"][_LOCATOR] = {"start": 0, "end": len(_QUOTE)}
    second = admit(_admissible_record(), elsewhere)
    assert isinstance(second, Excluded) and second.reason == "exact_span_missing"


def test_a_flagged_triple_whose_value_is_not_in_the_span_is_excluded_by_name() -> None:
    """Codex round 1 BLOCKER 2: `derived_from_span: true` is a promise, not a derivation."""

    record = _admissible_record()
    record["statement"]["object_ref_or_value"] = "IDR 9,999,000"
    assert record["statement"]["derived_from_span"] is True
    decision = admit(record, _source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "statement_not_from_source"


def test_two_simultaneous_defects_report_the_earlier_rule() -> None:
    """Codex round 1 MEDIUM at :315: the ORDER is part of the contract, so pin it with pairs.

    Every other row carries one defect; a reordering of rules 2–10 would pass them all.
    """

    version_and_span = _admissible_record()
    version_and_span["document_version_id"] = "invented"
    version_and_span["source_span"]["locator"] = "nowhere"
    first = admit(version_and_span, _source())
    assert isinstance(first, Excluded) and first.reason == "source_version_missing"

    span_and_event = _admissible_record()
    span_and_event["source_span"]["locator"] = "nowhere"
    span_and_event["source_event_ref"] = {"event_id": "99999999-0000-4000-8000-000000000000"}
    second = admit(span_and_event, _source())
    assert isinstance(second, Excluded) and second.reason == "exact_span_missing"

    rights_and_retention = _admissible_record()
    del rights_and_retention["classification"]["rights"]
    rights_and_retention["retention"] = {}
    third = admit(rights_and_retention, _source())
    assert isinstance(third, Excluded) and third.reason == "rights_missing"


def test_the_seed_cohorts_fully_sourced_records_are_admitted() -> None:
    """R1-build-spec.md §5c's Z2 seed cohort, driven through the CURED predicate end to end.

    Every record in `01_z2_seed_cohort.json` carries a `source["intel_events"]` mapping whose
    entry is a real, schema-valid, hash-verified canonical `IntelEvent` reachable from the
    record's own `source_event_ref` -- this is the fixture's own top-level `expected_behavior`
    claim ("Every record's record+source pair must be Admitted"), exercised here rather than
    left as an unread comment. It is also the non-regression guard for the rule 5 cure: curing
    presence-into-resolution must not turn the honestly-sourced seed cohort into a false
    exclusion.
    """

    doc = json.loads(_SEED_COHORT_PATH.read_text(encoding="utf-8"))
    assert doc["records"], "the seed cohort must carry at least one record"
    for entry in doc["records"]:
        decision = admit(entry["record"], entry["source"])
        assert isinstance(decision, Admitted), f"{entry['label']}: {decision}"


@pytest.mark.parametrize(
    "reason,mutate",
    [
        ("source_version_missing", lambda r: r.pop("document_version_id")),
        ("intel_event_identity_missing", lambda r: r.pop("source_event_ref")),
        ("rights_missing", lambda r: r["classification"].pop("rights")),
        ("retention_missing", lambda r: r["retention"].pop("retention_class")),
        ("classification_missing", lambda r: r["classification"].pop("risk_class")),
        ("review_state_missing", lambda r: r["review"].pop("state")),
        ("family_identity_unresolvable", lambda r: r.pop("manifest_family_id")),
    ],
)
def test_every_remaining_rule_excludes_by_its_own_name(reason: str, mutate) -> None:
    """One mutation per rule, so a rule that stopped firing is named, not averaged away.

    Batching these would let six of the seven rules rot while the seventh kept the test green.
    """

    record = _admissible_record()
    mutate(record)
    decision = admit(record, _source())
    assert isinstance(decision, Excluded), f"{reason}: expected an exclusion, got {decision}"
    assert decision.reason == reason


def test_nothing_is_defaulted_silently() -> None:
    """The rule D4 states as a prohibition, asserted as a property of the whole vocabulary.

    For every reason in `EXCLUSION_REASONS` there must exist a record that triggers it — a
    reason nobody can reach is a reason that will silently stop being enforced. Reached by
    stripping the admissible record down one field at a time, which is also a check that the
    vocabulary and the rule table have not drifted apart.
    """

    reachable = set()
    for reason, mutate in (
        ("statement_not_from_source", lambda r: r["statement"].__setitem__("derived_from_span", False)),
        ("content_hash_is_url", lambda r: r.__setitem__("document_content_hash", _sha256(_URL))),
        ("source_version_missing", lambda r: r.pop("document_version_id")),
        ("exact_span_missing", lambda r: r["source_span"].pop("locator")),
        ("intel_event_identity_missing", lambda r: r.pop("source_event_ref")),
        ("rights_missing", lambda r: r["classification"].pop("rights")),
        ("retention_missing", lambda r: r["retention"].pop("retention_class")),
        ("classification_missing", lambda r: r["classification"].pop("sensitivity")),
        ("review_state_missing", lambda r: r["review"].pop("state")),
        ("family_identity_unresolvable", lambda r: r.pop("manifest_family_id")),
    ):
        record = _admissible_record()
        mutate(record)
        decision = admit(record, _source())
        assert isinstance(decision, Excluded)
        assert decision.reason == reason, (
            f"mutation aimed at {reason!r} was excluded for {decision.reason!r}"
        )
        reachable.add(decision.reason)

    assert reachable == set(EXCLUSION_REASONS), (
        "every declared reason must be reachable; unreachable: "
        f"{sorted(set(EXCLUSION_REASONS) - reachable)}"
    )


def test_a_dry_run_that_admits_zero_is_a_valid_outcome() -> None:
    """The expected result against today's legacy corpus, asserted rather than feared.

    Ten legacy-shaped records in, zero admitted, ten reasons out — one per record, none of them
    blank. A run that admitted any of them would mean a rule had been relaxed.
    """

    records = []
    for index in range(10):
        record = _legacy_record()
        record["id"] = f"legacy-{index:04d}"
        records.append(record)

    decisions = [admit(record, _source()) for record in records]
    assert all(isinstance(decision, Excluded) for decision in decisions)
    assert len({decision.legacy_claim_id for decision in decisions}) == 10
    assert all(decision.reason for decision in decisions)


def test_the_three_counts_are_three_different_measurements() -> None:
    """D4's structural point, on a MIXED cohort: the three numbers differ from each other.

    Documented mapping coverage counts paths in a document. Available source information counts
    records that carry any source material at all. Admissible records counts decisions. They are
    computed from three separate inputs, so no two can be derived from each other — and on this
    cohort all three are pairwise different, which is the assertion that catches a report that
    quietly collapses two of them into one.
    """

    documented_paths = [("document_id",), ("source_span", "locator"), ("times", "recorded_at")]
    records = [
        _admissible_record(),
        _legacy_record(),
        dict(_legacy_record(), id="legacy-0002"),
        {"id": "empty-0001", "document_id": _URL},
    ]
    sources = {_URL: _source()}

    measured = counts(records, sources, documented_paths)
    assert measured.documented_mapping_coverage == 3
    assert measured.available_source_information == 4
    assert measured.admissible_records == 1
    values = (
        measured.documented_mapping_coverage,
        measured.available_source_information,
        measured.admissible_records,
    )
    assert len(set(values)) == 3, f"the three counts collapsed into {values}"
