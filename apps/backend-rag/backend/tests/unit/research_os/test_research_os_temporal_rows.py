"""D3's temporal case list, executed — one row per case, no skip, no xfail.

WHAT THIS PINS. `R-research-os.md` §0 lists the temporal cases both windows must answer:
both interval boundaries; zero and non-zero microseconds; unknown bounds; a correction recorded
before and after discovery; a scheduled change known in advance; an existing finite expiry; a
no-answer result; a quarantined fork. Each is a test here, over the reference reader in
`research_os_reader_reference.py`, which is the executable form of the D3 decision R2 implements
in SQL.

WHAT IT DOES NOT PIN, said plainly so a green run is not over-read. No PostgreSQL, no persistence
path, no hashing and no schema validation happen here — those are `test_research_os_p06_fixture_bundle.py`'s
and R2's jobs. This module pins SEMANTICS: given a corpus, which claim answers (T, S), and what
the reader does when none does or when the graph is unsound.

WHY THE CORPORA ARE BUILT IN THE TEST FOR SOME ROWS AND LOADED FROM THE BUNDLE FOR OTHERS. The
boundary, microsecond, fork and ambiguity rows are statements about the ALGORITHM, and a
hand-built two-claim corpus makes the mutation that would break them obvious. The correction,
scheduled-change and finite-expiry rows are statements about the FIXTURES the P06 bundle ships
and R2 will import, so they load those files: a test that invented its own version of
`bitemporal/03` would pass while the shipped fixture said something else, which is the failure
mode `test_naga_evidence_mapping_preconditions.py`'s own docstring records having had once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .research_os_reader_reference import (
    SUBJECT_KEY_NAMESPACE,
    Abstain,
    Answer,
    Quarantine,
    instant_sort_key,
    parse_instant,
    read,
)

_REPO_ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "packages" / "research-os-core").is_dir()
)
_BUNDLE = (
    _REPO_ROOT
    / "research/operations/execution/research-os-v1.0.0/evidence/p06"
    / "ros-v1-p06-naga-prep-b01"
)
_SUBJECT = "id/synthetic-instrument-01/art-1"


def _claim(
    claim_id: str,
    family_id: str,
    *,
    valid_from: str | None,
    valid_to: str | None,
    recorded_at: str,
    subject_key: str = _SUBJECT,
    object_hash: str | None = None,
    consequential: bool = True,
) -> dict[str, Any]:
    """A reader-shaped claim. Only the fields the READER reads, and nothing else.

    Deliberately NOT a schema-valid canonical Claim: this module tests the reader's rule, and a
    full canonical object here would bury the two instants that decide each row under thirty
    fields that decide nothing. Schema validity of the objects R2 imports is asserted in
    `test_research_os_p06_fixture_bundle.py`, against the real fixtures, with the real schemas.
    """

    return {
        "claim_id": claim_id,
        "claim_family_id": family_id,
        "object_hash": object_hash or (claim_id[-1] * 64),
        "consequential": consequential,
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
    }


def _edge(family_id: str, predecessor: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "predecessor_ref": {
            "claim_id": predecessor["claim_id"],
            "object_hash": predecessor["object_hash"],
        },
        "successor_ref": {
            "claim_id": successor["claim_id"],
            "object_hash": successor["object_hash"],
        },
    }


# --------------------------------------------------------------------------------------
# Instants: the defect ledger row 21 has carried open since 2026-08-26.
# --------------------------------------------------------------------------------------


def test_raw_text_order_disagrees_with_chronological_order() -> None:
    """The whole reason D2 exists, pinned as an executable fact rather than a sentence.

    `.` is 0x2E and `Z` is 0x5A, so `"...:00Z"` sorts AFTER `"...:00.000001Z"` as raw text
    while it is chronologically BEFORE it. Any reader or index that compares the canonical wire
    form as text answers bitemporal questions wrongly, and does so silently. If this assertion
    ever flips, either Python's string order changed or someone normalised the fixtures on the
    way in — both are things a maintainer must see.
    """

    zero_fraction = "2026-01-01T00:00:00Z"
    one_microsecond = "2026-01-01T00:00:00.000001Z"

    assert zero_fraction > one_microsecond, "text order"
    assert parse_instant(zero_fraction) < parse_instant(one_microsecond), "real order"


@pytest.mark.parametrize(
    "left,right",
    [
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00+00:00"),
        ("2026-01-01T00:00:00Z", "2026-01-01t00:00:00Z"),
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00.000000Z"),
        ("2026-01-01T00:00:00.1Z", "2026-01-01T00:00:00.100000Z"),
    ],
)
def test_every_admitted_spelling_of_one_instant_folds_to_one_value(left: str, right: str) -> None:
    """Cross-representation equality, over the spellings the PUBLISHED schema admits.

    `UtcDateTime`'s JSON-schema pattern is `(?:Z|\\+00:00)$` with `format: date-time`, which
    admits a lowercase `t`, an arbitrary-width fraction and either terminator. D2's SQL key must
    fold the same set; this row is the Python side of that agreement, and R2's migration tests
    assert the SQL side against the same table.
    """

    assert parse_instant(left) == parse_instant(right)
    assert instant_sort_key(left) == instant_sort_key(right)


def test_the_sort_key_orders_what_the_parse_orders() -> None:
    """D2's key is fixed-width and byte-ordered; this asserts it agrees with real time.

    A key that is merely fixed-width is not enough — it must ORDER correctly. The pair below is
    the one that breaks naive text comparison, so a key that regressed to `text` would fail
    here before it ever reached PostgreSQL.
    """

    instants = [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00.000001Z",
        "2026-01-01T00:00:00.1Z",
        "2026-01-01T00:00:00.11Z",
        "2026-01-01T00:00:01Z",
    ]
    assert sorted(instants, key=instant_sort_key) == sorted(instants, key=parse_instant)
    assert {len(instant_sort_key(value)) for value in instants} == {27}


# --------------------------------------------------------------------------------------
# Boundaries — case 1 and case 2.
# --------------------------------------------------------------------------------------


def _scheduled_pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Two SCHEDULED intervals: two families, one `subject_key`, no edge between them.

    This is D3(ii) in miniature and the shape `bitemporal/03` is rewritten to. They are not two
    members of one family because `CONTRACTS.md:141` requires a unique terminal member per
    family and `graph.py` quarantines two edge-less members without looking at valid intervals
    at all — so a "correct" calendar sequence modelled as one family would quarantine forever.
    """

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


def test_the_lower_boundary_is_included() -> None:
    """`valid_at == valid_from` is IN. Half-open, `CONTRACTS.md:88`."""

    claims, edges = _scheduled_pair()
    result = read(claims, edges, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert isinstance(result, Answer)
    assert result.claim_id == "22222222-0000-4000-8000-000000000002"


def test_the_upper_boundary_is_excluded() -> None:
    """`valid_at == valid_to` is OUT, and the SAME instant answers from the next interval.

    The two assertions together are the falsifiable pair: flipping the interval to closed would
    make the changeover instant admissible in BOTH families and the reader would quarantine on
    `ambiguous_subject_key` instead of answering — so a mutation cannot pass this row quietly.
    """

    claims, edges = _scheduled_pair()
    result = read(claims, edges, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert isinstance(result, Answer)
    assert result.claim_id != "11111111-0000-4000-8000-000000000001"

    just_before = read(claims, edges, _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z")
    assert isinstance(just_before, Answer)
    assert just_before.claim_id == "11111111-0000-4000-8000-000000000001"


def test_a_microsecond_decides_which_interval_answers() -> None:
    """Case 3 and 4 as a reader question, not only as a parse question.

    One microsecond either side of the changeover picks a different family. A reader that
    truncated to the second — or compared raw text — would return the same claim for both.
    """

    claims, edges = _scheduled_pair()
    before = read(claims, edges, _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z")
    after = read(claims, edges, _SUBJECT, "2026-07-01T00:00:00.000000Z", "2026-08-01T00:00:00Z")
    assert isinstance(before, Answer) and isinstance(after, Answer)
    assert before.claim_id != after.claim_id


def test_an_open_upper_bound_answers_for_every_later_instant() -> None:
    """Case 5 — `valid_to: null` means open, not missing."""

    claims, edges = _scheduled_pair()
    for instant in ("2026-07-01T00:00:00Z", "2030-01-01T00:00:00Z", "2999-12-31T23:59:59Z"):
        result = read(claims, edges, _SUBJECT, instant, "2026-08-01T00:00:00Z")
        assert isinstance(result, Answer), instant
        assert result.claim_id == "22222222-0000-4000-8000-000000000002"


# --------------------------------------------------------------------------------------
# System time — cases 6 and 7.
# --------------------------------------------------------------------------------------


def _corrected_pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One family, one CORRECTION: the successor says the predecessor was wrong all along.

    Both cover the same valid interval — that is what makes it a correction and not a schedule —
    and the predecessor is left byte-identical, `status` and `valid_to` untouched (RULING B1,
    2026-08-26: supersession is derived at read, «il vecchio resta intatto»).
    """

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


def test_before_discovery_the_old_version_answers() -> None:
    """Case 6. At S before the correction was recorded, we believed the original.

    This is the row that proves the reader implements SYSTEM time and not just "latest": a
    reader that returned the newest version regardless of S would answer with the correction
    here, and be wrong about what Nuzantara actually held on that date.
    """

    claims, edges = _corrected_pair()
    result = read(claims, edges, _SUBJECT, "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z")
    assert isinstance(result, Answer)
    assert result.claim_id == "33333333-0000-4000-8000-000000000003"


def test_after_discovery_the_correction_answers_and_the_predecessor_is_untouched() -> None:
    """Case 7, plus RULING B1's invariant asserted on the same corpus.

    The predecessor dict is compared to a fresh copy AFTER the read: the reader must not have
    written supersession onto it. `CONTRACTS.md:267` — "the predecessor is never updated".
    """

    claims, edges = _corrected_pair()
    before = json.loads(json.dumps(claims[0]))
    result = read(claims, edges, _SUBJECT, "2026-02-01T00:00:00Z", "2026-06-01T00:00:00Z")
    assert isinstance(result, Answer)
    assert result.claim_id == "44444444-0000-4000-8000-000000000004"
    assert claims[0] == before, "the reader mutated the predecessor"


def test_before_anything_was_recorded_the_reader_abstains() -> None:
    """Case 10 as a SYSTEM-time abstention, with its reason named.

    Returned as a value, never as `None`: a caller that forgets to branch gets an `Abstain`
    object, which cannot be mistaken for a claim.
    """

    claims, edges = _corrected_pair()
    result = read(claims, edges, _SUBJECT, "2026-02-01T00:00:00Z", "2025-11-01T00:00:00Z")
    assert result == Abstain("no_version_recorded_by_known_at")
    assert not isinstance(result, Answer)


# --------------------------------------------------------------------------------------
# Finite expiry, abstention, quarantine — cases 9, 10, 11.
# --------------------------------------------------------------------------------------


def test_a_finite_expiry_is_never_extended_by_succession() -> None:
    """Case 9. Past a finite `valid_to` with nothing after it, the answer is abstention.

    The tempting bug is to treat "no successor" as "still current, therefore still true", which
    silently extends every expired claim forever. The reader must separate CURRENT (system time)
    from TRUE AT T (valid time), and this row fails the moment they are conflated.
    """

    family = "dddddddd-0000-4000-8000-00000000000d"
    expiring = _claim(
        "55555555-0000-4000-8000-000000000005",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to="2026-06-01T00:00:00Z",
        recorded_at="2026-01-01T00:00:00Z",
    )
    result = read([expiring], [], _SUBJECT, "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z")
    assert result == Abstain("no_valid_interval_covers_valid_at")


def test_an_unknown_subject_key_abstains_rather_than_guessing() -> None:
    """The reader never scans for something plausible when the key matches nothing."""

    claims, edges = _scheduled_pair()
    result = read(claims, edges, "id/no-such-instrument/art-9", "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert result == Abstain("no_family_for_subject_key")


def test_a_fork_quarantines_and_never_picks_a_winner() -> None:
    """Case 11. Two successors for one predecessor.

    `CONTRACTS.md:141`: forks quarantine the family instead of selecting a winner. The row
    asserts BOTH halves — that the result is a `Quarantine` naming `fork`, AND that it is not an
    `Answer` — because a reader that returned the newest successor would be "reasonable", wrong,
    and invisible.
    """

    family = "eeeeeeee-0000-4000-8000-00000000000e"
    predecessor = _claim(
        "66666666-0000-4000-8000-000000000006",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-01-01T00:00:00Z",
    )
    left = _claim(
        "77777777-0000-4000-8000-000000000007",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-02-01T00:00:00Z",
    )
    right = _claim(
        "88888888-0000-4000-8000-000000000008",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-02-02T00:00:00Z",
    )
    edges = [_edge(family, predecessor, left), _edge(family, predecessor, right)]

    result = read([predecessor, left, right], edges, _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    assert isinstance(result, Quarantine)
    assert "fork" in result.reasons
    assert not isinstance(result, Answer)


def test_a_quarantined_family_is_not_bypassed_by_a_sound_one() -> None:
    """The bypass `CONTRACTS.md:141` forbids, made into a row.

    A sound family under the same `subject_key` would happily answer. It must not: reporting
    the quarantine is the point, and filtering it away to keep the API tidy is how a fork
    becomes invisible. This is the row that pins the ORDER of D3's steps — integrity BEFORE the
    temporal filters — and it goes red the moment they are swapped.
    """

    sound, _ = _scheduled_pair()
    family = "ffffffff-0000-4000-8000-00000000000f"
    predecessor = _claim(
        "99999999-0000-4000-8000-000000000009",
        family,
        valid_from="2020-01-01T00:00:00Z",
        valid_to="2020-02-01T00:00:00Z",
        recorded_at="2020-01-01T00:00:00Z",
    )
    left = _claim(
        "aaaaaaa1-0000-4000-8000-00000000000a",
        family,
        valid_from="2020-01-01T00:00:00Z",
        valid_to="2020-02-01T00:00:00Z",
        recorded_at="2020-03-01T00:00:00Z",
    )
    right = _claim(
        "aaaaaaa2-0000-4000-8000-00000000000b",
        family,
        valid_from="2020-01-01T00:00:00Z",
        valid_to="2020-02-01T00:00:00Z",
        recorded_at="2020-04-01T00:00:00Z",
    )
    edges = [_edge(family, predecessor, left), _edge(family, predecessor, right)]

    result = read(
        [*sound, predecessor, left, right],
        edges,
        _SUBJECT,
        "2026-03-01T00:00:00Z",
        "2026-08-01T00:00:00Z",
    )
    assert isinstance(result, Quarantine), "a sound family answered past a forked one"
    assert "fork" in result.reasons


def test_two_families_answering_the_same_question_quarantine_rather_than_rank() -> None:
    """`ambiguous_subject_key` — a modelling defect the reader must not paper over.

    Two OVERLAPPING scheduled intervals under one key is a data error. Ranking them by
    `recorded_at` would produce a confident, wrong answer forever.
    """

    first = _claim(
        "bbbbbbb1-0000-4000-8000-00000000001a",
        "11111111-1111-4000-8000-00000000001a",
        valid_from="2026-01-01T00:00:00Z",
        valid_to="2026-12-01T00:00:00Z",
        recorded_at="2025-12-15T00:00:00Z",
    )
    second = _claim(
        "bbbbbbb2-0000-4000-8000-00000000001b",
        "22222222-2222-4000-8000-00000000001b",
        valid_from="2026-06-01T00:00:00Z",
        valid_to=None,
        recorded_at="2025-12-15T00:00:00Z",
    )
    result = read([first, second], [], _SUBJECT, "2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z")
    assert isinstance(result, Quarantine)
    assert "ambiguous_subject_key" in result.reasons


def test_a_null_valid_from_on_a_consequential_claim_is_inadmissible() -> None:
    """`CONTRACTS.md:266` — consequential claims require explicit valid time.

    The negative half matters more than the positive one: the SAME corpus with
    `consequential: False` answers, so the row proves the rule keys on consequence and not on
    the missing bound alone.
    """

    family = "cccccccc-1111-4000-8000-00000000001c"
    unbounded = _claim(
        "ccccccc1-0000-4000-8000-00000000001c",
        family,
        valid_from=None,
        valid_to=None,
        recorded_at="2026-01-01T00:00:00Z",
        consequential=True,
    )
    result = read([unbounded], [], _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    assert isinstance(result, Quarantine)
    assert "null_valid_from_on_consequential_claim" in result.reasons

    harmless = dict(unbounded, consequential=False)
    assert isinstance(read([harmless], [], _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z"), Answer)


def test_the_answer_carries_an_identity_and_not_a_value() -> None:
    """An `Answer` is `(claim_id, object_hash, claim_family_id)` — nothing a caller can trust blind.

    A reader that returned the claim's VALUE would let every downstream consumer skip the hash
    check, which is how a mutated payload becomes an answer.
    """

    claims, edges = _scheduled_pair()
    result = read(claims, edges, _SUBJECT, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert isinstance(result, Answer)
    assert set(vars(result)) == {"claim_id", "object_hash", "claim_family_id"}
