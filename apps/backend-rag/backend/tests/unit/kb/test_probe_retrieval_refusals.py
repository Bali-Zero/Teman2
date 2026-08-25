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


def _j(phrase):
    return {"question": "q", "verbatim_phrase": phrase}


def test_innocence_a_phrase_only_its_own_instrument_could_produce_is_not_flagged():
    journeys = [
        _j("izin tinggal terbatas berlaku paling lama"),
        _j("modal disetor paling sedikit Rp10.000.000.000"),
        _j("Perolehan tanah Hak Pengelolaan atau Hak Atas Tanah"),
    ]
    assert PROBE.indiscriminate_phrases(journeys, CONTROL_CHUNKS) == []


def test_guilt_a_phrase_lifted_from_the_control_results_is_refused():
    journeys = [_j("izin tinggal terbatas berlaku paling lama"),
                _j("merupakan peraturan pelaksanaan")]
    flagged = PROBE.indiscriminate_phrases(journeys, CONTROL_CHUNKS)
    assert [i for i, _ in flagged] == [2], flagged


def test_guilt_the_control_phrase_itself_is_the_canonical_case():
    flagged = PROBE.indiscriminate_phrases([_j(PROBE.CONTROL_PHRASE)], CONTROL_CHUNKS)
    assert len(flagged) == 1


def test_guilt_it_reports_every_offender_not_just_the_first():
    journeys = [_j("melanggar ketentuan sebagaimana dimaksud"), _j("izin tinggal terbatas berlaku"),
                _j("Ketentuan lebih lanjut diatur")]
    assert [i for i, _ in PROBE.indiscriminate_phrases(journeys, CONTROL_CHUNKS)] == [1, 3]


def test_it_normalises_before_comparing_so_casing_cannot_evade_it():
    flagged = PROBE.indiscriminate_phrases(
        [_j("MERUPAKAN   PERATURAN\n  PELAKSANAAN")], CONTROL_CHUNKS)
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
    assert PROBE.indiscriminate_phrases([_j(straddle)], chunks) == []


def test_an_empty_phrase_is_left_to_the_length_rule():
    """Two rules, two jobs. If this one also claimed empties, its guilt cases would
    pass for the wrong reason and the length floor could be deleted unnoticed."""
    assert PROBE.indiscriminate_phrases([_j("")], CONTROL_CHUNKS) == []
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
