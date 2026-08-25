"""The probe must refuse to grade what it cannot grade.

An adversarial pass over `kb/ops/probe_retrieval.py` on 2026-08-25 found two ways to
make it report success without measuring anything:

  A. `verbatim_phrase` had no floor inside the probe. Run live, the phrases "", "a",
     "   ", "." and "dan" every one reported GREEN at rank 1. The mechanism is not
     corpus-dependent: "" is a substring of every string in Python, so such a journey
     greens against any collection, for any question. The G3 contract's 12-character
     minimum is real but lives in a different program, which a lane running the probe
     by hand never executes.

  B. `--collection this_collection_does_not_exist_zzz999` exited 0 "AT TARGET".
     `search_service.py:522-531` answers an unrecognised collection name by logging
     to stderr and searching `legal_unified` instead, so a typo does not error — it
     grades a corpus the caller never asked for.

Both are now refusals, and both predicates are pure so their guilt cases are provable
without a Qdrant connection. These tests exist to fail if either floor is removed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _probe():
    """Load kb/ops/probe_retrieval.py by path — it is a script, not a package."""
    root = Path(__file__).resolve()
    for parent in root.parents:
        if (parent / "kb" / "ops" / "probe_retrieval.py").exists():
            path = parent / "kb" / "ops" / "probe_retrieval.py"
            break
    else:  # pragma: no cover - the repo layout would have to change
        pytest.fail(f"kb/ops/probe_retrieval.py not found from {root}")
    spec = importlib.util.spec_from_file_location("_probe_retrieval", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_probe_retrieval", mod)
    spec.loader.exec_module(mod)
    return mod


PROBE = _probe()


# ── A. the phrase floor ──────────────────────────────────────────────────────

USABLE = [
    "izin tinggal terbatas berlaku paling lama",
    "modal disetor paling sedikit",
    # Boilerplate, and deliberately kept here: the LENGTH predicate must accept it,
    # because catching it is a different rule's job (indiscriminate_phrases, below).
    "peraturan perundang-undangan",
    "hak pakai di atas tanah",
]


@pytest.mark.parametrize("phrase", USABLE, ids=lambda p: p[:24])
def test_innocence_a_real_phrase_is_usable(phrase):
    """If these were refused, every guilt case below would be vacuous."""
    assert PROBE.unusable_phrase(phrase) is None


UNUSABLE = [
    ("empty string greens against everything", "", "substring of every string"),
    ("whitespace only normalises to empty", "   \n\t ", "substring of every string"),
    ("single character", "a", "matches by accident"),
    ("a single full stop", ".", "matches by accident"),
    ("a common Indonesian word", "dan", "matches by accident"),
    ("one character under the floor", "elevenchar", "matches by accident"),
    ("None where a string was expected", None, "substring of every string"),
]


@pytest.mark.parametrize("name,phrase,expected", UNUSABLE, ids=[c[0] for c in UNUSABLE])
def test_guilt_a_phrase_that_cannot_grade_is_refused(name, phrase, expected):
    why = PROBE.unusable_phrase(phrase)
    assert why is not None, f"{name}: the probe accepted {phrase!r} as gradeable"
    assert expected in why, f"{name}: refused for the wrong reason: {why}"


def test_the_floor_is_the_same_number_the_contract_gate_uses():
    """Two floors that can drift apart are one floor and one decoration."""
    assert PROBE.MIN_PHRASE_CHARS == 12


def test_the_empty_string_really_does_match_everything():
    """The premise behind rule A, asserted rather than assumed.

    If this ever stops being true of Python, the phrase floor is protecting against
    something that no longer exists and the comment above it is a lie.
    """
    assert "" in "any legal text whatsoever"
    assert PROBE.normalize("   ") == ""


# ── B. the collection floor ──────────────────────────────────────────────────

def test_innocence_the_collections_the_lanes_actually_use_are_known():
    """The registry names lane A and lane C were told to use must pass."""
    assert PROBE.unknown_collections(
        ["legal_unified", "visa_oracle", "immigration_circulars", "tax_genius_hybrid"]
    ) == []


STRANGERS = [
    ("the refuter's literal reproduction", "this_collection_does_not_exist_zzz999"),
    ("a plausible typo of the default", "legal_unifed"),
    ("a collection that sounds right but is not registered", "kbli_2025"),
    ("empty string", ""),
]


@pytest.mark.parametrize("name,collection", STRANGERS, ids=[c[0] for c in STRANGERS])
def test_guilt_an_unregistered_collection_is_refused(name, collection):
    assert PROBE.unknown_collections([collection]) == [collection], (
        f"{name}: {collection!r} was accepted, so a run against it would "
        f"silently grade legal_unified instead"
    )


def test_a_mixed_set_reports_only_the_strangers_and_sorts_them():
    assert PROBE.unknown_collections(
        ["legal_unified", "zzz_nope", "visa_oracle", "aaa_nope", "zzz_nope"]
    ) == ["aaa_nope", "zzz_nope"]


def test_the_predicate_agrees_with_the_registry_rather_than_a_copy_of_it():
    """A hardcoded allow-list would pass every test above and rot silently."""
    from backend.core.collection_registry import LOGICAL_TO_PHYSICAL_COLLECTIONS

    assert PROBE.unknown_collections(sorted(LOGICAL_TO_PHYSICAL_COLLECTIONS)) == []


# ── the refusals are wired, not merely defined ───────────────────────────────

def test_both_predicates_are_actually_consulted_by_the_run_path():
    """A predicate nobody calls is decoration. Read the source of run() and prove it.

    Deliberately a source check rather than a behavioural one: exercising run() needs
    a live Qdrant, and a test that needs production to prove a refusal is a test that
    gets skipped in CI and protects nothing.
    """
    import inspect

    src = inspect.getsource(PROBE.run)
    assert "unusable_phrase(" in src, "the phrase floor is defined but never called"
    assert "unknown_collections(" in src, "the collection floor is defined but never called"
    assert "unusable_phrase" in src.split("SearchService()")[0], (
        "the phrase floor runs AFTER production is touched — it must refuse first"
    )
    assert "collection_manager.get_collection" in src, (
        "nothing checks the exact predicate that triggers the silent substitution"
    )


# ── C. the discrimination floor ──────────────────────────────────────────────
# Length was never the property that mattered. Measured 2026-08-25 in visa_oracle:
# one compliance paragraph repeats across ~85 of its 90 points, so a phrase drawn
# from it is hundreds of characters long — clearing MIN_PHRASE_CHARS untouched —
# and matches nearly every document in the collection.

CONTROL_CHUNKS = [
    {"text": "Pada saat Undang-Undang ini mulai berlaku, semua peraturan "
             "perundang-undangan yang merupakan peraturan pelaksanaan tetap berlaku."},
    {"text": "Ketentuan lebih lanjut diatur dengan peraturan perundang-undangan."},
    {"text": "Setiap orang yang melanggar ketentuan sebagaimana dimaksud dipidana."},
]

# indiscriminate_phrases() takes a controls MAP (collection name -> that
# collection's own chunks) plus the run's default collection, not a flat chunk
# list — see its docstring (finding 10, 2026-08-26). Every test in this section
# that does not itself override `collection:` on a journey resolves to
# DEFAULT_COLLECTION, so CONTROLS is what the old bare CONTROL_CHUNKS used to be.
DEFAULT_COLLECTION = "legal_unified"
CONTROLS = {DEFAULT_COLLECTION: CONTROL_CHUNKS}


def _j(phrase):
    return {"question": "q", "verbatim_phrase": phrase}


def test_innocence_a_phrase_only_its_own_instrument_could_produce_is_not_flagged():
    journeys = [
        _j("izin tinggal terbatas berlaku paling lama"),
        _j("modal disetor paling sedikit Rp10.000.000.000"),
        _j("Perolehan tanah Hak Pengelolaan atau Hak Atas Tanah"),
    ]
    assert PROBE.indiscriminate_phrases(journeys, CONTROLS, DEFAULT_COLLECTION) == []


def test_guilt_a_phrase_lifted_from_the_control_results_is_refused():
    journeys = [_j("izin tinggal terbatas berlaku paling lama"),
                _j("merupakan peraturan pelaksanaan")]
    flagged = PROBE.indiscriminate_phrases(journeys, CONTROLS, DEFAULT_COLLECTION)
    assert [i for i, _ in flagged] == [2], flagged


def test_guilt_the_control_phrase_itself_is_the_canonical_case():
    flagged = PROBE.indiscriminate_phrases(
        [_j(PROBE.CONTROL_PHRASE)], CONTROLS, DEFAULT_COLLECTION)
    assert len(flagged) == 1


def test_guilt_it_reports_every_offender_not_just_the_first():
    journeys = [_j("melanggar ketentuan sebagaimana dimaksud"), _j("izin tinggal terbatas berlaku"),
                _j("Ketentuan lebih lanjut diatur")]
    assert [i for i, _ in PROBE.indiscriminate_phrases(
        journeys, CONTROLS, DEFAULT_COLLECTION)] == [1, 3]


def test_it_normalises_before_comparing_so_casing_cannot_evade_it():
    flagged = PROBE.indiscriminate_phrases(
        [_j("MERUPAKAN   PERATURAN\n  PELAKSANAAN")], CONTROLS, DEFAULT_COLLECTION)
    assert len(flagged) == 1, "case and whitespace were enough to slip past the floor"


def test_a_phrase_cannot_match_across_two_unrelated_chunks_joined_together():
    """The haystack joins chunks with a separator on purpose.

    Without one, the tail of chunk 1 and the head of chunk 2 form a span that exists
    in no document, and a phrase straddling that seam would be flagged for a reason
    the corpus never produced.

    The two chunks below are built so the seam is genuinely CONTIGUOUS — no
    punctuation between them. The first version of this test used chunks whose tail
    ended in a full stop, so it passed whether or not a separator was used: the
    period was doing the work. Mutating the separator away left it green, which is
    how the flaw was found. If you edit these fixtures, delete the separator from
    indiscriminate_phrases() and confirm this test goes RED before trusting it.
    """
    chunks = [
        {"text": "ketentuan dalam Pasal ini tetap berlaku"},
        {"text": "Ketentuan lebih lanjut diatur dengan Peraturan Menteri"},
    ]
    straddle = "tetap berlaku ketentuan lebih lanjut"
    joined_without_separator = " ".join(
        PROBE.normalize(c["text"]) for c in chunks)
    assert straddle in joined_without_separator, (
        "the fixture no longer creates a seam — this test would pass vacuously"
    )
    assert PROBE.indiscriminate_phrases(
        [_j(straddle)], {DEFAULT_COLLECTION: chunks}, DEFAULT_COLLECTION) == []


def test_an_empty_phrase_is_left_to_the_length_rule():
    """Two rules, two jobs. If this one also claimed empties, its guilt cases would
    pass for the wrong reason and the length floor could be deleted unnoticed."""
    assert PROBE.indiscriminate_phrases([_j("")], CONTROLS, DEFAULT_COLLECTION) == []
    assert PROBE.unusable_phrase("") is not None


def test_the_discrimination_floor_runs_after_the_control_and_before_any_grading():
    import inspect

    src = inspect.getsource(PROBE.run)
    assert "indiscriminate_phrases(" in src, "the floor is defined but never called"
    before_loop = src.split("for i, journey in enumerate(journeys")[0]
    assert "indiscriminate_phrases(" in before_loop, (
        "the floor runs after grading has begun — it must refuse first"
    )
    assert src.index("CONTROL_PHRASE") < src.index("indiscriminate_phrases("), (
        "it must run AFTER the control, since it consumes the control's chunks"
    )


# ── C2. the per-collection floor — PENDING-ARMS finding opened 2026-08-26 ─────
# (refuter finding 10). The single global control used to let a journey scoped
# to a DIFFERENT collection escape the discrimination check entirely: its phrase
# was compared against the wrong corpus's boilerplate.

def test_a_journey_overriding_collection_is_checked_against_ITS_OWN_control():
    """Guilt: a phrase that is boilerplate in visa_oracle, for a journey scoped to
    visa_oracle, must be caught by visa_oracle's OWN control — not missed because
    the only control fetched was legal_unified's."""
    visa_chunks = [{"text": "Setiap pemegang visa wajib melaporkan perubahan alamat "
                             "kepada kantor imigrasi setempat paling lambat 30 hari."}]
    controls = {DEFAULT_COLLECTION: CONTROL_CHUNKS, "visa_oracle": visa_chunks}
    j = _j("wajib melaporkan perubahan alamat kepada kantor imigrasi")
    j["collection"] = "visa_oracle"
    flagged = PROBE.indiscriminate_phrases([j], controls, DEFAULT_COLLECTION)
    assert [i for i, _ in flagged] == [1], (
        "a journey scoped to visa_oracle must be checked against visa_oracle's own "
        "control, not legal_unified's"
    )


def test_a_journey_overriding_collection_is_NOT_flagged_by_a_DIFFERENT_collections_boilerplate():
    """Innocence, the mirror of the guilt case above: legal_unified's own
    boilerplate (the standard CONTROL_PHRASE) must NOT leak into the check for a
    journey scoped to visa_oracle, whose own control does not contain it. Before
    this fix there was only ONE haystack, so this direction could not even be
    expressed — every journey shared it regardless of `collection:`."""
    controls = {DEFAULT_COLLECTION: CONTROL_CHUNKS, "visa_oracle": [
        {"text": "izin tinggal terbatas berlaku paling lama dua tahun"}
    ]}
    j = _j(PROBE.CONTROL_PHRASE)  # boilerplate ONLY in legal_unified's control
    j["collection"] = "visa_oracle"
    flagged = PROBE.indiscriminate_phrases([j], controls, DEFAULT_COLLECTION)
    assert flagged == [], (
        "legal_unified's boilerplate leaked into the check for a journey scoped "
        "to visa_oracle — the control is not being resolved per-journey"
    )


def test_a_journey_with_no_collection_override_still_uses_the_default():
    """Innocence for the common case — every real journeys file today omits
    `collection:` entirely, and this must behave exactly as it did before the
    fix."""
    assert PROBE.indiscriminate_phrases(
        [_j("izin tinggal terbatas berlaku paling lama")], CONTROLS, DEFAULT_COLLECTION
    ) == []


def test_a_two_collection_fixture_flags_only_the_boilerplate_hit_regardless_of_entry_order():
    """PENDING-ARMS proof-of-armed spec, verbatim: two entries on two different
    collections, phrase boilerplate in the SECOND collection only, exits non-zero
    — and this must hold in BOTH orders, because a fixture that leaves state
    behind between calls is green alphabetically and red under xdist on the same
    SHA (cicatrix family #9/#37). indiscriminate_phrases() builds its haystack
    into a dict LOCAL to the call, never module-level, so there is nothing to
    leave behind — this proves that rather than assuming it.
    """
    controls = {
        DEFAULT_COLLECTION: CONTROL_CHUNKS,
        "visa_oracle": [{"text": "Setiap pemegang visa wajib melaporkan perubahan "
                                  "alamat kepada kantor imigrasi setempat"}],
    }
    clean = _j("izin tinggal terbatas berlaku paling lama")
    boilerplate = _j("wajib melaporkan perubahan alamat kepada kantor imigrasi")
    boilerplate["collection"] = "visa_oracle"

    forward = PROBE.indiscriminate_phrases([clean, boilerplate], controls, DEFAULT_COLLECTION)
    assert [i for i, _ in forward] == [2], forward

    reversed_order = PROBE.indiscriminate_phrases(
        [boilerplate, clean], controls, DEFAULT_COLLECTION)
    assert [i for i, _ in reversed_order] == [1], reversed_order


def test_a_collection_absent_from_controls_has_an_empty_haystack_not_a_crash():
    """A journey resolving to a collection this run never fetched a control for
    must not KeyError — `controls.get(collection, [])` inside indiscriminate_phrases
    is what this pins. Whether that shape can occur in run() is a separate
    question (run() fetches a control for every name in `asked`, which is built
    FROM the same resolve_collection() calls); this proves the function itself
    degrades safely rather than crashing if it ever did."""
    j = _j("izin tinggal terbatas berlaku paling lama")
    j["collection"] = "a_collection_no_control_was_fetched_for"
    assert PROBE.indiscriminate_phrases([j], CONTROLS, DEFAULT_COLLECTION) == []


# ── D. the refusals ACT, they are not merely mentioned ───────────────────────
# The source-inspection tests above prove each predicate is CALLED. They cannot
# prove its answer is acted on: replacing `if unusable:` with `if False:` leaves
# the call in the source and those tests green. Measured — that mutation survived
# them. These call run() for real instead.
#
# This costs no Qdrant connection BY CONSTRUCTION: both refusals are placed before
# SearchService is constructed, so a test that reaches production has caught the
# refusal moving to the wrong side of that line, which is itself the defect.

import asyncio
import json as _json


def _journeys_file(tmp_path, phrase, collection=None):
    entry = {
        "question": "berapa lama izin tinggal berlaku",
        "verbatim_phrase": phrase,
        "instrument_id": "X_1_2026",
        "probe_state": "red",
        "probe_run_at": "2026-08-25",
    }
    if collection:
        entry["collection"] = collection
    path = tmp_path / "probe_case.yaml"
    path.write_text(
        _json.dumps({"schema_version": 1, "lane": "A", "journeys": [entry]}),
        encoding="utf-8",
    )
    return path


def test_run_actually_refuses_a_short_phrase(tmp_path, capsys):
    path = _journeys_file(tmp_path, "dan")
    assert asyncio.run(PROBE.run([str(path)])) == 3
    assert "cannot grade anything" in capsys.readouterr().out


def test_run_actually_refuses_an_unregistered_collection(tmp_path, capsys):
    path = _journeys_file(tmp_path, "izin tinggal terbatas berlaku paling lama",
                          collection="this_collection_does_not_exist_zzz999")
    assert asyncio.run(PROBE.run([str(path)])) == 3
    assert "registry does not define" in capsys.readouterr().out


def test_the_refusals_reach_the_json_path_too(tmp_path, capsys):
    """A refusal that only exists on the human path is invisible to probe_history."""
    path = _journeys_file(tmp_path, "dan")
    assert asyncio.run(PROBE.run([str(path), "--json"])) == 3
    payload = _json.loads(capsys.readouterr().out.strip())
    assert payload["verdict"] == "broken"
    assert payload["reason"] == "unusable_phrase"
    assert payload["journeys"] == []


# ── E. the manager-level floor, provable without production ──────────────────
# This is the predicate search_service.py itself evaluates before substituting
# legal_unified. Its first version was unreachable by any test, because exercising
# it meant constructing SearchService. A floor whose only proof needs production is
# a floor nobody checks — hence the injected lookup.

SERVED = {"legal_unified": object(), "visa_oracle": object(),
          "immigration_circulars": None}


def _lookup(name):
    return SERVED.get(name)


def test_innocence_collections_the_manager_serves_are_not_flagged():
    assert PROBE.unserved_collections(["legal_unified", "visa_oracle"], _lookup) == []


def test_guilt_a_registered_name_the_manager_cannot_hand_back_is_flagged():
    """immigration_circulars is in the registry — this is the OTHER trigger."""
    assert PROBE.unserved_collections(
        ["legal_unified", "immigration_circulars"], _lookup) == ["immigration_circulars"]


def test_guilt_a_name_the_manager_never_heard_of_is_flagged():
    assert PROBE.unserved_collections(["nope_zzz"], _lookup) == ["nope_zzz"]


def test_it_reports_every_unserved_name_sorted_and_deduplicated():
    assert PROBE.unserved_collections(
        ["zzz", "aaa", "zzz", "legal_unified"], _lookup) == ["aaa", "zzz"]


def test_the_two_collection_floors_are_different_checks():
    """The registry knows immigration_circulars; a manager that cannot serve it is a
    separate failure. If one rule could stand in for the other, the silent
    substitution would still have one live trigger."""
    from backend.core.collection_registry import is_known_collection

    assert is_known_collection("immigration_circulars")
    assert PROBE.unknown_collections(["immigration_circulars"]) == []
    assert PROBE.unserved_collections(["immigration_circulars"], _lookup) == [
        "immigration_circulars"]


# ── Section F: the two expectations are not mirror images ────────────────────
#
# `retrieves` asks about ATTRIBUTION — did the RIGHT instrument answer? A phrase
# found under another document is not evidence for this one.
#
# `must_not_retrieve` asks about REACHABILITY — can a reader be shown this text
# at all? Immigration journey 2's poison is the body of a Tegal regency
# correspondence manual; if it comes back attributed to some OTHER document, the
# reader still gets municipal letterhead rules inside a Golden Visa answer.
#
# Until 2026-08-26 both were derived from `hit == (expectation == "retrieves")`
# with `hit = measured_state == "green"`, which made `misattributed` SATISFY a
# canary: the guard fell silent in exactly the case where the corpus was worse,
# because a poison phrase floating loose under someone else's identity is a more
# broken corpus, not a less broken one.


def test_retrieves_is_satisfied_only_by_the_right_instrument():
    assert PROBE.journey_satisfaction("green", "retrieves") is True


def test_retrieves_is_not_satisfied_by_a_hit_on_the_wrong_instrument():
    assert PROBE.journey_satisfaction("misattributed", "retrieves") is False


def test_retrieves_is_not_satisfied_when_nothing_came_back():
    assert PROBE.journey_satisfaction("red", "retrieves") is False


def test_a_canary_is_satisfied_only_when_the_poison_is_unreachable():
    assert PROBE.journey_satisfaction("red", "must_not_retrieve") is True


def test_guilt_a_canary_is_violated_by_a_correctly_attributed_hit():
    assert PROBE.journey_satisfaction("green", "must_not_retrieve") is False


def test_guilt_a_canary_is_violated_by_a_misattributed_hit_too():
    """The regression this section exists for.

    The reader is harmed by seeing the poison text, not by the label attached to
    it. A rule that clears the canary here would go quiet on a corpus where the
    poison has ALSO lost its identity.
    """
    assert PROBE.journey_satisfaction("misattributed", "must_not_retrieve") is False


def test_the_two_expectations_disagree_on_misattributed_and_that_is_the_point():
    """Guards the asymmetry itself, not either half of it.

    A future simplification back to one symmetric formula makes both sides equal
    and this fails — which is the only way the asymmetry survives someone tidying
    it up without reading why it is there.
    """
    assert PROBE.journey_satisfaction("misattributed", "retrieves") is False
    assert PROBE.journey_satisfaction("misattributed", "must_not_retrieve") is False
    assert PROBE.journey_satisfaction("green", "retrieves") != PROBE.journey_satisfaction(
        "green", "must_not_retrieve"
    )


# ── F2. fail-closed, not fail-open — PENDING-ARMS guard 1, cross-family
# completeness review (2026-08-26). The old must_not_retrieve formula was a
# DENY-list (`not in ("green", "misattributed")`): anything the function was not
# explicitly told to distrust was treated as safe, including values no real
# caller in this module ever produces. A canary must default the OTHER way.

def test_guilt_an_unrecognised_measured_state_does_not_satisfy_a_canary():
    """A case mismatch, a None, or plain garbage must not silently clear a
    canary just because it isn't spelled exactly 'green' or 'misattributed'."""
    assert PROBE.journey_satisfaction("GREEN", "must_not_retrieve") is False
    assert PROBE.journey_satisfaction(None, "must_not_retrieve") is False
    assert PROBE.journey_satisfaction("banana", "must_not_retrieve") is False
    assert PROBE.journey_satisfaction("untested", "must_not_retrieve") is False


def test_guilt_an_unrecognised_expectation_satisfies_nothing():
    """Guards the other argument: a missing/mistyped expectation must not fall
    through to either the 'retrieves' or the 'must_not_retrieve' branch by
    accident — it must land on the explicit refusal."""
    assert PROBE.journey_satisfaction("green", None) is False
    assert PROBE.journey_satisfaction("red", "must_not_retrive_typo") is False
    assert PROBE.journey_satisfaction("green", "") is False


REAL_STATE_TABLE = [
    ("green", "retrieves", True),
    ("misattributed", "retrieves", False),
    ("red", "retrieves", False),
    ("green", "must_not_retrieve", False),
    ("misattributed", "must_not_retrieve", False),
    ("red", "must_not_retrieve", True),
]


@pytest.mark.parametrize("state,expectation,expected", REAL_STATE_TABLE,
                         ids=[f"{s}+{e}" for s, e, _ in REAL_STATE_TABLE])
def test_innocence_the_three_real_measured_states_are_unchanged_by_the_fail_closed_rewrite(
    state, expectation, expected
):
    """The allow-list rewrite must not change behaviour for any value production
    code actually produces — locate_phrase() only ever returns green/misattributed
    /red, and run() only ever passes 'retrieves' or 'must_not_retrieve'. Each of
    the six combinations is asserted against its actual expected value here (not
    merely "does not raise") — a single consolidated truth table, same shape as
    the six individual tests above it, so a future edit that silently narrows
    ANY one of the six is caught by name, not just by absence of an exception."""
    assert PROBE.journey_satisfaction(state, expectation) is expected
