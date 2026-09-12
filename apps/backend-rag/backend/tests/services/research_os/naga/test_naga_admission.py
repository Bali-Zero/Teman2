"""Production `naga_admission` vs R1's `research_os_admission_reference` — parity.

Every reason in `EXCLUSION_REASONS`, first-defect ordering, the four presence-is-not-resolution
traps, and the three counts diverging on a mixed cohort — all measured against R1's committed
reference AND against R1's shipped Z2 seed cohort fixture. No skip, no xfail.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from research_os.hashing import object_hash

from backend.services.research_os.naga_admission import (
    EXCLUSION_REASONS,
    Admitted,
    Excluded,
    admit,
    summarize,
    three_way_counts,
)

from .conftest import REPO_ROOT

_BODY = (
    "SYNTHETIC INSTRUMENT 01. Article 1 paragraph 1. The processing fee for a Class A "
    "application is IDR 1,234,000 with effect from 1 March 2026."
)
_QUOTE = "The processing fee for a Class A application is IDR 1,234,000"
_URL = "https://example.invalid/synthetic-instrument-01"
_EVENT_ID = "11111111-0000-4000-8000-0000000000e1"
_VERSION_ID = "synthetic-instrument-01@2026-03-01"
_LOCATOR = "art-1/para-1"

_SEED_COHORT_PATH = (
    REPO_ROOT
    / "research/operations/execution/research-os-v1.0.0/evidence/p06"
    / "ros-v1-p06-naga-prep-b01/fixtures/seed_public_regulatory/01_z2_seed_cohort.json"
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intel_event(event_id: str = _EVENT_ID) -> dict[str, Any]:
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
        "times": {"observed_at": "2026-03-01T00:00:00Z", "ingested_at": "2026-03-01T00:05:00Z"},
        "identity": {"content_hash": _sha256(_BODY), "idempotency_key": "synthetic-instrument-01"},
        "classification": {"risk_class": "green", "sensitivity": "public"},
        "lineage": {"pipeline_run_id": "22222222-0000-4000-8000-000000000002", "input_event_refs": []},
        "payload_ref": {"ref_type": "reference", "uri": _URL, "content_hash": _sha256(_BODY)},
        "retention": {"retention_class": "public_record", "legal_hold": False},
        "object_hash": "0" * 64,
    }
    node["object_hash"] = object_hash(node)
    return node


def _source() -> dict[str, Any]:
    start = _BODY.index(_QUOTE)
    return {
        "body": _BODY,
        "intel_events": {_EVENT_ID: _intel_event()},
        "document_versions": {_VERSION_ID: {"document_id": _URL, "content_hash": _sha256(_BODY)}},
        "locators": {_LOCATOR: {"start": start, "end": start + len(_QUOTE)}},
    }


def _admissible_record() -> dict[str, Any]:
    return {
        "id": "synthetic-0001",
        "document_id": _URL,
        "document_version_id": _VERSION_ID,
        "document_content_hash": _sha256(_BODY),
        "source_span": {
            "locator": _LOCATOR,
            "quoted_text": _QUOTE,
            "quote_hash": _sha256(_QUOTE),
        },
        "statement": {
            "subject_ref": "synthetic.instrument.01",
            "predicate": "synthetic.fee.amount",
            "object_ref_or_value": "IDR 1,234,000",
            "value_span": {"start": _QUOTE.index("IDR 1,234,000"), "end": len(_QUOTE)},
            "derived_from_span": True,
        },
        "source_event_ref": {"event_id": _EVENT_ID},
        "classification": {"risk_class": "low", "sensitivity": "public", "rights": "public-domain"},
        "retention": {"retention_class": "regulatory-5y"},
        "review": {"state": "unreviewed"},
        "manifest_family_id": "aaaaaaaa-0000-4000-8000-00000000000a",
    }


def _legacy_record() -> dict[str, Any]:
    return {
        "id": "legacy-0001",
        "document_id": _URL,
        "document_content_hash": _sha256(_URL),
        "source_span_hint": "somewhere in article 1",
        "claim_text": "the processing fee is IDR 1,234,000",
        "review": {"state": "unreviewed"},
    }


def _assert_agrees(prod: Any, ref: Any) -> None:
    ref_type = type(ref).__name__
    if ref_type == "Admitted":
        assert isinstance(prod, Admitted), (prod, ref)
        assert prod.legacy_claim_id == ref.legacy_claim_id
        assert prod.family_id == ref.family_id
    elif ref_type == "Excluded":
        assert isinstance(prod, Excluded), (prod, ref)
        assert prod.legacy_claim_id == ref.legacy_claim_id
        assert prod.reason == ref.reason
    else:  # pragma: no cover - defensive
        raise AssertionError(f"unrecognised reference decision type: {ref_type}")


def test_exclusion_reasons_are_r1s_vocabulary_verbatim(r1_admission_reference) -> None:
    assert EXCLUSION_REASONS == r1_admission_reference.EXCLUSION_REASONS


def test_the_fully_sourced_record_is_admitted(r1_admission_reference) -> None:
    record, source = _admissible_record(), _source()
    decision = admit(record, source_snapshot=source)
    assert isinstance(decision, Admitted), decision
    assert decision.family_id == "aaaaaaaa-0000-4000-8000-00000000000a"
    _assert_agrees(decision, r1_admission_reference.admit(record, source))


def test_a_legacy_shaped_record_is_excluded_and_names_its_first_defect(r1_admission_reference) -> None:
    record, source = _legacy_record(), _source()
    decision = admit(record, source_snapshot=source)
    assert isinstance(decision, Excluded)
    assert decision.reason == "statement_not_from_source"
    _assert_agrees(decision, r1_admission_reference.admit(record, source))


def test_a_url_content_hash_is_excluded_by_name(r1_admission_reference) -> None:
    record = _admissible_record()
    record["document_content_hash"] = _sha256(_URL)
    decision = admit(record, source_snapshot=_source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "content_hash_is_url"
    _assert_agrees(decision, r1_admission_reference.admit(record, _source()))


def test_a_missing_exact_span_is_excluded_by_name(r1_admission_reference) -> None:
    without_locator = _admissible_record()
    without_locator["source_span"].pop("locator")
    first = admit(without_locator, source_snapshot=_source())
    assert isinstance(first, Excluded) and first.reason == "exact_span_missing"
    _assert_agrees(first, r1_admission_reference.admit(without_locator, _source()))

    wrong_hash = _admissible_record()
    wrong_hash["source_span"]["quote_hash"] = _sha256("a different quotation entirely")
    second = admit(wrong_hash, source_snapshot=_source())
    assert isinstance(second, Excluded) and second.reason == "exact_span_missing"
    _assert_agrees(second, r1_admission_reference.admit(wrong_hash, _source()))


def test_a_fabricated_triple_is_excluded_by_name(r1_admission_reference) -> None:
    record = _admissible_record()
    record["source_span"]["quoted_text"] = "a sentence that appears nowhere in the document"
    record["source_span"]["quote_hash"] = _sha256(record["source_span"]["quoted_text"])
    decision = admit(record, source_snapshot=_source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "statement_not_from_source"
    _assert_agrees(decision, r1_admission_reference.admit(record, _source()))


def test_an_absent_intel_event_reference_is_excluded_by_name(r1_admission_reference) -> None:
    record = _admissible_record()
    record["source_event_ref"] = {"event_id": "99999999-0000-4000-8000-000000000000"}
    decision = admit(record, source_snapshot=_source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "intel_event_identity_missing"
    _assert_agrees(decision, r1_admission_reference.admit(record, _source()))


def test_a_resolved_but_invalid_intel_event_is_excluded_by_name(r1_admission_reference) -> None:
    malformed_source = _source()
    malformed_node = malformed_source["intel_events"][_EVENT_ID]
    del malformed_node["classification"]
    malformed_node["object_hash"] = object_hash(malformed_node)
    decision = admit(_admissible_record(), source_snapshot=malformed_source)
    assert isinstance(decision, Excluded)
    assert decision.reason == "intel_event_identity_missing"
    _assert_agrees(decision, r1_admission_reference.admit(_admissible_record(), malformed_source))

    tampered_source = _source()
    tampered_source["intel_events"][_EVENT_ID]["object_hash"] = _sha256("not the real content")
    decision2 = admit(_admissible_record(), source_snapshot=tampered_source)
    assert isinstance(decision2, Excluded)
    assert decision2.reason == "intel_event_identity_missing"
    _assert_agrees(decision2, r1_admission_reference.admit(_admissible_record(), tampered_source))


def test_an_unrelated_valid_intel_event_is_not_provenance_for_this_record(r1_admission_reference) -> None:
    other_uri = "https://example.invalid/synthetic-instrument-02"
    other_hash = _sha256("SYNTHETIC INSTRUMENT 02. An unrelated document.")
    other_id = "11111111-0000-4000-8000-0000000000e2"

    def borrow(**changes: Any) -> Any:
        node = _intel_event(other_id)
        node["source"]["uri"] = changes.get("uri", _URL)
        node["identity"]["content_hash"] = changes.get("identity_hash", _sha256(_BODY))
        node["payload_ref"]["content_hash"] = changes.get("payload_hash", _sha256(_BODY))
        node["object_hash"] = object_hash(node)
        source = _source()
        source["intel_events"][other_id] = node
        record = _admissible_record()
        record["source_event_ref"] = {"event_id": other_id}
        return admit(record, source_snapshot=source), r1_admission_reference.admit(record, source)

    for case in ({"uri": other_uri}, {"identity_hash": other_hash}, {"payload_hash": other_hash}):
        decision, ref_decision = borrow(**case)
        assert isinstance(decision, Excluded), case
        assert decision.reason == "intel_event_identity_missing", case
        _assert_agrees(decision, ref_decision)

    decision, ref_decision = borrow()
    assert isinstance(decision, Admitted)
    _assert_agrees(decision, ref_decision)


def test_a_stated_event_hash_that_disagrees_is_a_rejection(r1_admission_reference) -> None:
    record = _admissible_record()
    record["source_event_ref"] = {"event_id": _EVENT_ID, "object_hash": "f" * 64}
    decision = admit(record, source_snapshot=_source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "intel_event_identity_missing"
    _assert_agrees(decision, r1_admission_reference.admit(record, _source()))

    record["source_event_ref"]["object_hash"] = _intel_event()["object_hash"]
    decision2 = admit(record, source_snapshot=_source())
    assert isinstance(decision2, Admitted)
    _assert_agrees(decision2, r1_admission_reference.admit(record, _source()))


def test_an_invented_or_mismatched_version_is_excluded_by_name(r1_admission_reference) -> None:
    invented = _admissible_record()
    invented["document_version_id"] = "synthetic-instrument-01@invented"
    first = admit(invented, source_snapshot=_source())
    assert isinstance(first, Excluded) and first.reason == "source_version_missing"
    _assert_agrees(first, r1_admission_reference.admit(invented, _source()))

    other_body = _source()
    other_body["document_versions"][_VERSION_ID] = {
        "document_id": _URL,
        "content_hash": _sha256("a different body"),
    }
    second = admit(_admissible_record(), source_snapshot=other_body)
    assert isinstance(second, Excluded) and second.reason == "source_version_missing"
    _assert_agrees(second, r1_admission_reference.admit(_admissible_record(), other_body))

    other_document = _source()
    other_document["document_versions"][_VERSION_ID] = {
        "document_id": "https://example.invalid/another-document",
        "content_hash": _sha256(_BODY),
    }
    third = admit(_admissible_record(), source_snapshot=other_document)
    assert isinstance(third, Excluded) and third.reason == "source_version_missing"
    _assert_agrees(third, r1_admission_reference.admit(_admissible_record(), other_document))


def test_a_value_that_merely_shares_a_number_with_the_span_is_excluded_by_name(r1_admission_reference) -> None:
    quote = _BODY[_BODY.index("Article 1") : _BODY.index(_QUOTE) + len(_QUOTE)]
    source = _source()
    begin = _BODY.index(quote)
    source["locators"]["art-1"] = {"start": begin, "end": begin + len(quote)}

    def with_value(value: Any, anchor: dict[str, int] | None) -> tuple[Any, Any]:
        record = _admissible_record()
        record["source_span"] = {"locator": "art-1", "quoted_text": quote, "quote_hash": _sha256(quote)}
        record["statement"]["object_ref_or_value"] = value
        record["statement"]["value_span"] = anchor
        return admit(record, source_snapshot=source), r1_admission_reference.admit(record, source)

    article = quote.index("1")
    fee = quote.index("1,234,000")
    for value, anchor in (
        ("1 year", {"start": article, "end": article + 1}),
        ("1,234,000 days of detention", {"start": fee, "end": fee + len("1,234,000")}),
        (1234, {"start": fee, "end": fee + len("1,234")}),
        (1234000, None),
        (1234000, {"start": article, "end": article + 1}),
    ):
        decision, ref_decision = with_value(value, anchor)
        assert isinstance(decision, Excluded), (value, anchor)
        assert decision.reason == "statement_not_from_source", (value, anchor)
        _assert_agrees(decision, ref_decision)

    decision, ref_decision = with_value(1234000, {"start": fee, "end": fee + len("1,234,000")})
    assert isinstance(decision, Admitted)
    _assert_agrees(decision, ref_decision)


def test_a_genuine_quote_at_a_fictional_locator_is_excluded_by_name(r1_admission_reference) -> None:
    fictional = _admissible_record()
    fictional["source_span"]["locator"] = "art-9/para-9"
    first = admit(fictional, source_snapshot=_source())
    assert isinstance(first, Excluded) and first.reason == "exact_span_missing"
    _assert_agrees(first, r1_admission_reference.admit(fictional, _source()))

    elsewhere = _source()
    elsewhere["locators"][_LOCATOR] = {"start": 0, "end": len(_QUOTE)}
    second = admit(_admissible_record(), source_snapshot=elsewhere)
    assert isinstance(second, Excluded) and second.reason == "exact_span_missing"
    _assert_agrees(second, r1_admission_reference.admit(_admissible_record(), elsewhere))


def test_a_flagged_triple_whose_value_is_not_in_the_span_is_excluded_by_name(r1_admission_reference) -> None:
    record = _admissible_record()
    record["statement"]["object_ref_or_value"] = "IDR 9,999,000"
    assert record["statement"]["derived_from_span"] is True
    decision = admit(record, source_snapshot=_source())
    assert isinstance(decision, Excluded)
    assert decision.reason == "statement_not_from_source"
    _assert_agrees(decision, r1_admission_reference.admit(record, _source()))


def test_two_simultaneous_defects_report_the_earlier_rule(r1_admission_reference) -> None:
    version_and_span = _admissible_record()
    version_and_span["document_version_id"] = "invented"
    version_and_span["source_span"]["locator"] = "nowhere"
    first = admit(version_and_span, source_snapshot=_source())
    assert isinstance(first, Excluded) and first.reason == "source_version_missing"
    _assert_agrees(first, r1_admission_reference.admit(version_and_span, _source()))

    span_and_event = _admissible_record()
    span_and_event["source_span"]["locator"] = "nowhere"
    span_and_event["source_event_ref"] = {"event_id": "99999999-0000-4000-8000-000000000000"}
    second = admit(span_and_event, source_snapshot=_source())
    assert isinstance(second, Excluded) and second.reason == "exact_span_missing"
    _assert_agrees(second, r1_admission_reference.admit(span_and_event, _source()))

    rights_and_retention = _admissible_record()
    del rights_and_retention["classification"]["rights"]
    rights_and_retention["retention"] = {}
    third = admit(rights_and_retention, source_snapshot=_source())
    assert isinstance(third, Excluded) and third.reason == "rights_missing"
    _assert_agrees(third, r1_admission_reference.admit(rights_and_retention, _source()))

    retention_and_classification = _admissible_record()
    retention_and_classification["retention"] = {}
    retention_and_classification["classification"] = {"rights": "public-domain"}
    fourth = admit(retention_and_classification, source_snapshot=_source())
    assert isinstance(fourth, Excluded) and fourth.reason == "retention_missing"
    _assert_agrees(fourth, r1_admission_reference.admit(retention_and_classification, _source()))

    classification_and_review = _admissible_record()
    classification_and_review["classification"] = {"rights": "public-domain"}
    del classification_and_review["review"]
    fifth = admit(classification_and_review, source_snapshot=_source())
    assert isinstance(fifth, Excluded) and fifth.reason == "classification_missing"
    _assert_agrees(fifth, r1_admission_reference.admit(classification_and_review, _source()))

    review_and_family = _admissible_record()
    del review_and_family["review"]
    del review_and_family["manifest_family_id"]
    sixth = admit(review_and_family, source_snapshot=_source())
    assert isinstance(sixth, Excluded) and sixth.reason == "review_state_missing"
    _assert_agrees(sixth, r1_admission_reference.admit(review_and_family, _source()))


def test_the_seed_cohorts_fully_sourced_records_are_admitted(r1_admission_reference) -> None:
    doc = json.loads(_SEED_COHORT_PATH.read_text(encoding="utf-8"))
    assert doc["records"], "the seed cohort must carry at least one record"
    for entry in doc["records"]:
        decision = admit(entry["record"], source_snapshot=entry["source"])
        assert isinstance(decision, Admitted), f"{entry['label']}: {decision}"
        _assert_agrees(decision, r1_admission_reference.admit(entry["record"], entry["source"]))


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
def test_every_remaining_rule_excludes_by_its_own_name(reason: str, mutate: Any, r1_admission_reference) -> None:
    record = _admissible_record()
    mutate(record)
    decision = admit(record, source_snapshot=_source())
    assert isinstance(decision, Excluded), f"{reason}: expected an exclusion, got {decision}"
    assert decision.reason == reason
    _assert_agrees(decision, r1_admission_reference.admit(record, _source()))


def test_nothing_is_defaulted_silently() -> None:
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
        decision = admit(record, source_snapshot=_source())
        assert isinstance(decision, Excluded)
        assert decision.reason == reason, f"mutation aimed at {reason!r} was excluded for {decision.reason!r}"
        reachable.add(decision.reason)

    assert reachable == set(EXCLUSION_REASONS), (
        f"every declared reason must be reachable; unreachable: {sorted(set(EXCLUSION_REASONS) - reachable)}"
    )


def test_a_dry_run_that_admits_zero_is_a_valid_outcome() -> None:
    records = []
    for index in range(10):
        record = _legacy_record()
        record["id"] = f"legacy-{index:04d}"
        records.append(record)

    decisions = [admit(record, source_snapshot=_source()) for record in records]
    assert all(isinstance(decision, Excluded) for decision in decisions)
    assert len({decision.legacy_claim_id for decision in decisions}) == 10
    assert all(decision.reason for decision in decisions)

    summary = summarize(decisions)
    assert summary.admitted == 0
    assert summary.excluded == 10
    assert summary.excluded_by_reason == {"statement_not_from_source": 10}


def test_summarize_reports_admitted_and_excluded_by_reason_separately() -> None:
    decisions = [
        admit(_admissible_record(), source_snapshot=_source()),
        admit(_legacy_record(), source_snapshot=_source()),
        admit(dict(_legacy_record(), id="legacy-0002"), source_snapshot=_source()),
    ]
    summary = summarize(decisions)
    assert summary.admitted == 1
    assert summary.excluded == 2
    assert summary.excluded_by_reason == {"statement_not_from_source": 2}


def test_the_three_counts_are_three_different_measurements() -> None:
    documented_paths = [("document_id",), ("source_span", "locator"), ("times", "recorded_at")]
    records = [
        _admissible_record(),
        _legacy_record(),
        dict(_legacy_record(), id="legacy-0002"),
        {"id": "empty-0001", "document_id": _URL},
    ]
    sources = {_URL: _source()}

    measured = three_way_counts(records, sources, documented_paths)
    assert measured.documented_mapping_coverage == 3
    assert measured.available_source_information == 4
    assert measured.admissible_records == 1
    values = (
        measured.documented_mapping_coverage,
        measured.available_source_information,
        measured.admissible_records,
    )
    assert len(set(values)) == 3, f"the three counts collapsed into {values}"


def test_the_three_counts_agree_with_r1s_reference(r1_admission_reference) -> None:
    documented_paths = [("document_id",), ("source_span", "locator"), ("times", "recorded_at")]
    records = [
        _admissible_record(),
        _legacy_record(),
        dict(_legacy_record(), id="legacy-0002"),
        {"id": "empty-0001", "document_id": _URL},
    ]
    sources = {_URL: _source()}

    measured = three_way_counts(records, sources, documented_paths)
    reference = r1_admission_reference.counts(records, sources, documented_paths)
    assert measured.documented_mapping_coverage == reference.documented_mapping_coverage
    assert measured.available_source_information == reference.available_source_information
    assert measured.admissible_records == reference.admissible_records
