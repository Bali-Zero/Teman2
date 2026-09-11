"""Production `naga_bitemporal_reader` vs R1's `research_os_reader_reference` — parity, plus the
two documented, spec-directed divergences (hash recompute; `unparseable_instant`).

Every temporal case named in `R2-build-spec.md` §4 is here: both interval boundaries; zero and
non-zero microseconds; unknown bounds; a correction recorded before and after discovery; a
scheduled change known in advance (a separate family under one `subject_key`); an existing
finite expiry; a no-answer result; a quarantined fork; the future-duplicate-terminal Quarantine
case (R1 blocker 2); an edge whose family_id spelling differs from the claims' (R1 blocker 1).
No skip, no xfail.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from research_os.hashing import object_hash

from backend.services.research_os.naga_bitemporal_reader import (
    SUBJECT_KEY_NAMESPACE,
    Abstain,
    Answer,
    Quarantine,
    instant_key,
    read,
    registered_family_name,
)

from .conftest import P06_BUNDLE

_SUBJECT = "id/synthetic-instrument-01/art-1"
_SEED_COHORT = P06_BUNDLE / "fixtures/seed_public_regulatory/01_z2_seed_cohort.json"
_SEED_PAIR_SUBJECT = "id/permenkumham-synth-40-2026/pasal-5-ayat-2"


# --------------------------------------------------------------------------------------
# Fixture builders — reader-shaped, minimal, but hash-COMPUTED (never a placeholder string)
# so the production reader's recompute-based `hash_mismatch` check stays silent by default.
# --------------------------------------------------------------------------------------


def _statement(*, consequential: bool) -> dict[str, Any]:
    if consequential:
        return {
            "subject_ref": {"object_kind": "regulation", "object_id": "synthetic-instrument-01"},
            "predicate": "synthetic.fee.amount",
            "object_ref_or_value": 1234000,
        }
    return {
        "subject_ref": {"object_kind": "topic", "object_id": "synthetic-topic-01"},
        "predicate": "synthetic.note",
        "object_ref_or_value": "a descriptive note",
    }


def _claim(
    claim_id: str,
    family_id: str,
    *,
    valid_from: str | None,
    valid_to: str | None,
    recorded_at: str,
    subject_key: str = _SUBJECT,
    consequential: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "claim_id": claim_id,
        "claim_family_id": family_id,
        "contract_version": "research-os/v1.0.0",
        "statement": _statement(consequential=consequential),
        "time": {"valid_from": valid_from, "valid_to": valid_to, "recorded_at": recorded_at},
        "extensions": {
            SUBJECT_KEY_NAMESPACE: {
                "extension_version": "1.0.0",
                "payload": {
                    "subject_key": subject_key,
                    "jurisdiction": subject_key.split("/")[0],
                    "instrument": subject_key.split("/")[1],
                    "provision": subject_key.split("/")[2],
                },
            }
        },
        "object_hash": "0" * 64,
    }
    payload["object_hash"] = object_hash(payload)
    return payload


def _edge(family_id: str, predecessor: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    return {
        "family_id": registered_family_name(family_id),
        "predecessor_ref": {
            "object_kind": "claim",
            "object_id": predecessor["claim_id"],
            "object_hash": predecessor["object_hash"],
        },
        "successor_ref": {
            "object_kind": "claim",
            "object_id": successor["claim_id"],
            "object_hash": successor["object_hash"],
        },
    }


def _objects(claims: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {"claims": claims, "object_successor_edges": edges}


def _assert_agrees_with_reference(prod: Any, ref: Any) -> None:
    """Production and R1's reference must answer the SAME way on the SAME corpus."""

    ref_type = type(ref).__name__
    if ref_type == "Answer":
        assert isinstance(prod, Answer), (prod, ref)
        assert prod.claim_id == ref.claim_id
        assert prod.object_hash == ref.object_hash
        assert prod.claim_family_id == ref.claim_family_id
    elif ref_type == "Abstain":
        assert isinstance(prod, Abstain), (prod, ref)
        assert prod.reason == ref.reason
    elif ref_type == "Quarantine":
        assert isinstance(prod, Quarantine), (prod, ref)
        assert prod.family_ids == ref.family_ids
        assert prod.reasons == ref.reasons
    else:  # pragma: no cover - defensive, should be unreachable
        raise AssertionError(f"unrecognised reference result type: {ref_type}")


# --------------------------------------------------------------------------------------
# Instants: measured domain agreement with R1's `parse_instant`/`instant_sort_key`.
# --------------------------------------------------------------------------------------


class TestInstantKeyDomain:
    """`instant_key`'s domain, MEASURED against R1's `parse_instant` — never assumed."""

    _VALID_SPELLINGS = [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01t00:00:00z",
        "2026-01-01T00:00:00.000000Z",
        "2026-01-01T00:00:00.1Z",
        "2026-01-01T00:00:00.100000Z",
        "2026-01-01T00:00:00.11Z",
        "2026-01-01T00:00:00.1234567Z",  # 7-digit fraction, truncated to 6
        "2028-02-29T00:00:00Z",  # a REAL leap day (2028 is a leap year)
    ]

    #: Every shape named in R2-build-spec.md §4: calendar-invalid (Feb 30, a non-leap-year Feb
    #: 29, hour 24, second 60, year 0000, month 13, day 00) and non-ASCII decimal digits — plus
    #: the structurally-wrong shapes the migration spec pins for the SQL twin (empty, no zone,
    #: a non-UTC offset, free text).
    _INVALID_SHAPES = [
        "",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00+07:00",
        "not-an-instant",
        "2026-02-30T00:00:00Z",
        "2026-02-29T00:00:00Z",  # 2026 is NOT a leap year
        "2026-01-01T24:00:00Z",
        "2026-01-01T00:00:60Z",
        "0000-01-01T00:00:00Z",
        "2026-13-01T00:00:00Z",
        "2026-01-00T00:00:00Z",
        "٢٠٢٦-01-01T00:00:00Z",  # Arabic-Indic year digits
        "٢٠٢٦-٠١-٠١T٠٠:٠٠:٠٠Z",
    ]

    @pytest.mark.parametrize("text", _VALID_SPELLINGS)
    def test_agrees_with_r1_on_every_admitted_spelling(self, text: str, r1_reader_reference) -> None:
        assert instant_key(text) == r1_reader_reference.instant_sort_key(text)

    @pytest.mark.parametrize("text", _INVALID_SHAPES)
    def test_returns_none_exactly_where_r1_raises(self, text: str, r1_reader_reference) -> None:
        with pytest.raises(ValueError):
            r1_reader_reference.parse_instant(text)
        assert instant_key(text) is None, text

    @pytest.mark.parametrize(
        "left,right",
        [
            ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00+00:00"),
            ("2026-01-01T00:00:00Z", "2026-01-01t00:00:00Z"),
            ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00.000000Z"),
            ("2026-01-01T00:00:00.1Z", "2026-01-01T00:00:00.100000Z"),
            ("2026-01-01T00:00:00.1Z", "2026-01-01T00:00:00.1000004Z"),
        ],
    )
    def test_folding_pairs_agree_with_r1(self, left: str, right: str, r1_reader_reference) -> None:
        assert instant_key(left) == instant_key(right)
        assert instant_key(left) == r1_reader_reference.instant_sort_key(left)
        assert instant_key(right) == r1_reader_reference.instant_sort_key(right)

    def test_distinguishes_1z_from_11z(self) -> None:
        assert instant_key("2026-01-01T00:00:00.1Z") != instant_key("2026-01-01T00:00:00.11Z")

    def test_byte_order_agrees_with_chronological_order(self, r1_reader_reference) -> None:
        instants = [
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00.000001Z",
            "2026-01-01T00:00:00.1Z",
            "2026-01-01T00:00:00.11Z",
            "2026-01-01T00:00:01Z",
        ]
        assert sorted(instants, key=instant_key) == sorted(
            instants, key=r1_reader_reference.parse_instant
        )
        assert {len(instant_key(value)) for value in instants} == {27}


# --------------------------------------------------------------------------------------
# Boundaries — both interval edges, zero/non-zero microseconds.
# --------------------------------------------------------------------------------------


def _scheduled_pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    first = _claim(
        "11111111-0000-4000-8000-000000000001",
        "aaaaaaaa-0000-4000-8000-00000000000a",
        valid_from="2026-01-01T00:00:00Z",
        valid_to="2026-07-01T00:00:00Z",
        recorded_at="2025-12-15T00:00:00Z",
    )
    second = _claim(
        "22222222-0000-4000-8000-000000000002",
        "bbbbbbbb-0000-4000-8000-00000000000b",
        valid_from="2026-07-01T00:00:00Z",
        valid_to=None,
        recorded_at="2025-12-15T00:00:00Z",
    )
    return [first, second], []


def test_the_lower_boundary_is_included(r1_reader_reference) -> None:
    claims, edges = _scheduled_pair()
    prod = read(_SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Answer)
    assert prod.claim_id == "22222222-0000-4000-8000-000000000002"


def test_the_upper_boundary_is_excluded(r1_reader_reference) -> None:
    claims, edges = _scheduled_pair()
    at_boundary = read(
        _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, edges)
    )
    ref_at_boundary = r1_reader_reference.read(
        claims, edges, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )
    _assert_agrees_with_reference(at_boundary, ref_at_boundary)
    assert isinstance(at_boundary, Answer)
    assert at_boundary.claim_id != "11111111-0000-4000-8000-000000000001"

    just_before = read(
        _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z", _objects(claims, edges)
    )
    ref_just_before = r1_reader_reference.read(
        claims, edges, _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z"
    )
    _assert_agrees_with_reference(just_before, ref_just_before)
    assert isinstance(just_before, Answer)
    assert just_before.claim_id == "11111111-0000-4000-8000-000000000001"


def test_a_microsecond_decides_which_interval_answers(r1_reader_reference) -> None:
    claims, edges = _scheduled_pair()
    before = read(
        _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z", _objects(claims, edges)
    )
    after = read(
        _SUBJECT, "2026-07-01T00:00:00.000000Z", "2026-08-01T00:00:00Z", _objects(claims, edges)
    )
    assert isinstance(before, Answer) and isinstance(after, Answer)
    assert before.claim_id != after.claim_id
    _assert_agrees_with_reference(
        before,
        r1_reader_reference.read(claims, edges, _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z"),
    )
    _assert_agrees_with_reference(
        after,
        r1_reader_reference.read(claims, edges, _SUBJECT, "2026-07-01T00:00:00.000000Z", "2026-08-01T00:00:00Z"),
    )


def test_an_open_upper_bound_answers_for_every_later_instant(r1_reader_reference) -> None:
    claims, edges = _scheduled_pair()
    for instant in ("2026-07-01T00:00:00Z", "2030-01-01T00:00:00Z", "2999-12-31T23:59:59Z"):
        prod = read(_SUBJECT, instant, "2026-08-01T00:00:00Z", _objects(claims, edges))
        ref = r1_reader_reference.read(claims, edges, _SUBJECT, instant, "2026-08-01T00:00:00Z")
        _assert_agrees_with_reference(prod, ref)
        assert isinstance(prod, Answer), instant
        assert prod.claim_id == "22222222-0000-4000-8000-000000000002"


# --------------------------------------------------------------------------------------
# System time — a correction recorded before and after discovery; a no-answer result.
# --------------------------------------------------------------------------------------


def _corrected_pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    family = "cccccccc-0000-4000-8000-00000000000c"
    original = _claim(
        "33333333-0000-4000-8000-000000000003",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-01-10T00:00:00Z",
    )
    corrected = _claim(
        "44444444-0000-4000-8000-000000000004",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-03-01T00:00:00Z",
    )
    return [original, corrected], [_edge(family, original, corrected)]


def test_before_discovery_the_old_version_answers(r1_reader_reference) -> None:
    claims, edges = _corrected_pair()
    prod = read(_SUBJECT, "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SUBJECT, "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Answer)
    assert prod.claim_id == "33333333-0000-4000-8000-000000000003"


def test_after_discovery_the_correction_answers_and_the_predecessor_is_untouched(r1_reader_reference) -> None:
    claims, edges = _corrected_pair()
    before = json.loads(json.dumps(claims[0]))
    prod = read(_SUBJECT, "2026-02-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SUBJECT, "2026-02-01T00:00:00Z", "2026-06-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Answer)
    assert prod.claim_id == "44444444-0000-4000-8000-000000000004"
    assert claims[0] == before, "the reader mutated the predecessor"


def test_before_anything_was_recorded_the_reader_abstains(r1_reader_reference) -> None:
    claims, edges = _corrected_pair()
    prod = read(_SUBJECT, "2026-02-01T00:00:00Z", "2025-11-01T00:00:00Z", _objects(claims, edges))
    assert prod == Abstain("no_version_recorded_by_known_at")
    _assert_agrees_with_reference(
        prod, r1_reader_reference.read(claims, edges, _SUBJECT, "2026-02-01T00:00:00Z", "2025-11-01T00:00:00Z")
    )


# --------------------------------------------------------------------------------------
# Finite expiry, abstention, quarantine.
# --------------------------------------------------------------------------------------


def test_a_finite_expiry_is_never_extended_by_succession(r1_reader_reference) -> None:
    family = "dddddddd-0000-4000-8000-00000000000d"
    expiring = _claim(
        "55555555-0000-4000-8000-000000000005",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to="2026-06-01T00:00:00Z",
        recorded_at="2026-01-01T00:00:00Z",
    )
    prod = read(_SUBJECT, "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", _objects([expiring], []))
    assert prod == Abstain("no_valid_interval_covers_valid_at")
    _assert_agrees_with_reference(
        prod, r1_reader_reference.read([expiring], [], _SUBJECT, "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z")
    )


def test_an_unknown_subject_key_abstains_rather_than_guessing(r1_reader_reference) -> None:
    claims, edges = _scheduled_pair()
    other_key = "id/no-such-instrument/art-9"
    prod = read(other_key, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, edges))
    assert prod == Abstain("no_family_for_subject_key")
    _assert_agrees_with_reference(
        prod, r1_reader_reference.read(claims, edges, other_key, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z")
    )


def test_a_fork_quarantines_and_never_picks_a_winner(r1_reader_reference) -> None:
    family = "eeeeeeee-0000-4000-8000-00000000000e"
    predecessor = _claim(
        "66666666-0000-4000-8000-000000000006", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="2026-01-01T00:00:00Z",
    )
    left = _claim(
        "77777777-0000-4000-8000-000000000007", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="2026-02-01T00:00:00Z",
    )
    right = _claim(
        "88888888-0000-4000-8000-000000000008", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="2026-02-02T00:00:00Z",
    )
    edges = [_edge(family, predecessor, left), _edge(family, predecessor, right)]
    claims = [predecessor, left, right]

    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Quarantine)
    assert "fork" in prod.reasons
    assert not isinstance(prod, Answer)


def test_a_quarantined_family_is_not_bypassed_by_a_sound_one(r1_reader_reference) -> None:
    sound, _ = _scheduled_pair()
    family = "ffffffff-0000-4000-8000-00000000000f"
    predecessor = _claim(
        "99999999-0000-4000-8000-000000000009", family,
        valid_from="2020-01-01T00:00:00Z", valid_to="2020-02-01T00:00:00Z", recorded_at="2020-01-01T00:00:00Z",
    )
    left = _claim(
        "aaaaaaa1-0000-4000-8000-00000000000a", family,
        valid_from="2020-01-01T00:00:00Z", valid_to="2020-02-01T00:00:00Z", recorded_at="2020-03-01T00:00:00Z",
    )
    right = _claim(
        "aaaaaaa2-0000-4000-8000-00000000000b", family,
        valid_from="2020-01-01T00:00:00Z", valid_to="2020-02-01T00:00:00Z", recorded_at="2020-04-01T00:00:00Z",
    )
    edges = [_edge(family, predecessor, left), _edge(family, predecessor, right)]
    claims = [*sound, predecessor, left, right]

    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SUBJECT, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Quarantine), "a sound family answered past a forked one"
    assert "fork" in prod.reasons


def test_two_families_answering_the_same_question_quarantine_rather_than_rank(r1_reader_reference) -> None:
    first = _claim(
        "bbbbbbb1-0000-4000-8000-00000000001a", "11111111-1111-4000-8000-00000000001a",
        valid_from="2026-01-01T00:00:00Z", valid_to="2026-12-01T00:00:00Z", recorded_at="2025-12-15T00:00:00Z",
    )
    second = _claim(
        "bbbbbbb2-0000-4000-8000-00000000001b", "22222222-2222-4000-8000-00000000001b",
        valid_from="2026-06-01T00:00:00Z", valid_to=None, recorded_at="2025-12-15T00:00:00Z",
    )
    claims = [first, second]
    prod = read(_SUBJECT, "2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z", _objects(claims, []))
    ref = r1_reader_reference.read(claims, [], _SUBJECT, "2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Quarantine)
    assert "ambiguous_subject_key" in prod.reasons
    assert prod.family_ids == tuple(sorted({first["claim_family_id"], second["claim_family_id"]}))


def test_a_null_valid_from_on_a_consequential_claim_is_inadmissible(r1_reader_reference) -> None:
    family = "cccccccc-1111-4000-8000-00000000001c"
    unbounded = _claim(
        "ccccccc1-0000-4000-8000-00000000001c", family,
        valid_from=None, valid_to=None, recorded_at="2026-01-01T00:00:00Z", consequential=True,
    )
    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects([unbounded], []))
    ref = r1_reader_reference.read([unbounded], [], _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Quarantine)
    assert "null_valid_from_on_consequential_claim" in prod.reasons

    harmless = _claim(
        "ccccccc1-0000-4000-8000-00000000001c", family,
        valid_from=None, valid_to=None, recorded_at="2026-01-01T00:00:00Z", consequential=False,
    )
    harmless_prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects([harmless], []))
    assert isinstance(harmless_prod, Answer)
    _assert_agrees_with_reference(
        harmless_prod,
        r1_reader_reference.read([harmless], [], _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z"),
    )


def test_the_answer_carries_an_identity_and_not_a_value() -> None:
    claims, edges = _scheduled_pair()
    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, edges))
    assert isinstance(prod, Answer)
    assert {f.name for f in prod.__dataclass_fields__.values()} == {
        "claim_id",
        "object_hash",
        "claim_family_id",
    }


def test_structural_non_uniqueness_quarantines_even_when_every_member_is_in_the_future(
    r1_reader_reference,
) -> None:
    """R1 blocker 2: integrity runs BEFORE any temporal filter."""

    family = "dddddddd-2222-4000-8000-00000000002d"
    left = _claim(
        "d0000001-0000-4000-8000-00000000002d", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="2027-01-01T00:00:00Z",
    )
    right = _claim(
        "d0000002-0000-4000-8000-00000000002d", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="2027-02-01T00:00:00Z",
    )
    claims = [left, right]
    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects(claims, []))
    ref = r1_reader_reference.read(claims, [], _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Quarantine)
    assert "non_unique_current_member" in prod.reasons
    assert not isinstance(prod, Abstain)


# --------------------------------------------------------------------------------------
# The shipped P06 seed-cohort correction pair — real, committed canonical bytes.
# --------------------------------------------------------------------------------------


def _seed_correction_pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pair = json.loads(_SEED_COHORT.read_text(encoding="utf-8"))["correction_pair"]
    return pair["claims"], pair["object_successor_edges"]


def test_the_shipped_correction_edge_is_consumed_before_discovery(r1_reader_reference) -> None:
    claims, edges = _seed_correction_pair()
    prod = read(_SEED_PAIR_SUBJECT, "2026-08-01T00:00:00Z", "2026-03-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SEED_PAIR_SUBJECT, "2026-08-01T00:00:00Z", "2026-03-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Answer)
    assert prod.claim_id == claims[0]["claim_id"]


def test_the_shipped_correction_edge_is_consumed_after_discovery(r1_reader_reference) -> None:
    claims, edges = _seed_correction_pair()
    prod = read(_SEED_PAIR_SUBJECT, "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, edges))
    ref = r1_reader_reference.read(claims, edges, _SEED_PAIR_SUBJECT, "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Answer)
    assert prod.claim_id == claims[1]["claim_id"]
    assert prod.object_hash == claims[1]["object_hash"]


def test_an_edge_naming_the_wrong_family_quarantines_and_is_never_dropped(r1_reader_reference) -> None:
    claims, edges = _seed_correction_pair()
    wrong = [dict(edges[0], family_id=claims[0]["claim_family_id"])]
    prod = read(_SEED_PAIR_SUBJECT, "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z", _objects(claims, wrong))
    ref = r1_reader_reference.read(claims, wrong, _SEED_PAIR_SUBJECT, "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)
    assert isinstance(prod, Quarantine)
    assert "family_identity_mismatch" in prod.reasons


def test_a_canonical_claim_is_consequential_by_its_payload_not_by_a_flag(r1_reader_reference) -> None:
    record = json.loads(_SEED_COHORT.read_text(encoding="utf-8"))["records"][0]
    claim = json.loads(json.dumps(record["canonical"]["claim"]))
    assert "consequential" not in claim
    claim["time"]["valid_from"] = None
    # object_hash on the payload is now stale relative to the mutated time block — this row is
    # about consequence-detection, not about hash integrity, so keep the mutated field but
    # recompute the hash it must carry for the production reader's recompute check to stay
    # silent (mirrors what a real writer would have done; the point under test is `time`, not
    # `object_hash`).
    unhashed = dict(claim)
    del unhashed["object_hash"]
    claim["object_hash"] = object_hash(unhashed)
    subject = claim["extensions"][SUBJECT_KEY_NAMESPACE]["payload"]["subject_key"]

    prod = read(subject, "2026-03-01T00:00:00Z", "2026-10-01T00:00:00Z", _objects([claim], []))
    assert isinstance(prod, Quarantine)
    assert "null_valid_from_on_consequential_claim" in prod.reasons

    # R1's reference never recomputes a hash, so it is indifferent to the object_hash edit —
    # feed it the ORIGINAL (unedited) object_hash to keep the comparison about `time` only.
    reference_claim = dict(claim, object_hash=record["canonical"]["claim"]["object_hash"])
    ref = r1_reader_reference.read([reference_claim], [], subject, "2026-03-01T00:00:00Z", "2026-10-01T00:00:00Z")
    _assert_agrees_with_reference(prod, ref)


# --------------------------------------------------------------------------------------
# Deliberate, documented divergences from R1's reference — both spec-directed.
# --------------------------------------------------------------------------------------


def test_production_recomputes_the_hash_r1_reference_only_compares_declared_values(
    r1_reader_reference,
) -> None:
    """DIVERGENCE (named, expected): R2-build-spec.md §4 step 2 — "hash_mismatch (recompute via
    core hashing)". A solo claim (no edge) whose declared `object_hash` disagrees with its own
    payload is invisible to R1's reference (it only ever compares a member's declared hash
    against an EDGE's stated hash; with no edge, no comparison happens at all) but is caught by
    the production reader, which always recomputes a member's hash independently.
    """

    family = "11112222-0000-4000-8000-0000000000ab"
    claim = _claim(
        "abcdefab-0000-4000-8000-000000000001", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="2026-01-01T00:00:00Z",
    )
    tampered = dict(claim, object_hash="0" * 64)

    ref = r1_reader_reference.read([tampered], [], _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    assert isinstance(ref, r1_reader_reference.Answer), "R1's reference never recomputes a hash"

    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects([tampered], []))
    assert isinstance(prod, Quarantine)
    assert "hash_mismatch" in prod.reasons


def test_an_unparseable_recorded_at_quarantines_instead_of_crashing() -> None:
    """DIVERGENCE (named, expected): R1's reference has no vocabulary entry for this because
    every fixture it ships parses — `_current_at` calls `parse_instant` unconditionally, so a
    malformed `recorded_at` would raise `ValueError` UNCAUGHT there (not run here, to avoid
    asserting a crash as a passing test). Production adds `unparseable_instant`, a NEW Quarantine
    reason (append-only per D4's "we may add reasons" posture, extended here to the reader for
    the same "never crash on this data, always name a reason" rationale).
    """

    family = "22223333-0000-4000-8000-0000000000ab"
    claim = _claim(
        "abcdefab-0000-4000-8000-000000000002", family,
        valid_from="2026-01-01T00:00:00Z", valid_to=None, recorded_at="not-an-instant",
    )
    prod = read(_SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z", _objects([claim], []))
    assert isinstance(prod, Quarantine)
    assert "unparseable_instant" in prod.reasons
